"""Accepted Profile projection; normalized once for both SQL and provider inputs."""

import hashlib
import math
import re
import unicodedata
from datetime import UTC, datetime

from sqlalchemy import select


def normalize(value: str) -> str:
    return " ".join(
        unicodedata.normalize("NFKC", value)
        .translate(str.maketrans("يك۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "یک01234567890123456789"))
        .replace("\u200c", " ")
        .casefold()
        .split()
    )


def experience(profile):
    """Conservative union: incomplete/Jalali/invalid dates make total unknown.

    Floor rather than round so a threshold never includes an unearned tenth.
    No work history means unknown, not zero. Current roles end at today's date.
    """
    intervals = []
    today = datetime.now(UTC).date()
    for job in profile.get("work_experience") or []:
        start, end = job.get("start_date"), job.get("end_date")
        if job.get("current") and not end:
            end = today.isoformat()
        if not all(
            isinstance(v, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", v)
            for v in (start, end)
        ):
            return None
        try:
            first, last = datetime.fromisoformat(start).date(), datetime.fromisoformat(end).date()
        except ValueError:
            return None
        if first.year < 1900 or first > last or last > today:
            return None
        intervals.append((first, last))
    merged = []
    for first, last in sorted(intervals):
        if merged and first <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(last, merged[-1][1]))
        else:
            merged.append((first, last))
    return math.floor(sum((b - a).days for a, b in merged) / 365.25 * 10) / 10 if merged else None


def document(profile, full_name):
    """One bounded document, never raw/unaccepted extraction or arbitrary Notes.

    Work bullets + accepted summary are the condensed resume text. Do not index
    raw text: it can contradict a human correction or a rejected proposal.
    """
    parts = [full_name, profile.get("headline"), profile.get("summary")]
    parts += profile.get("skills") or []
    parts += profile.get("industries") or []
    parts += [(profile.get("contact") or {}).get("location")]
    for job in profile.get("work_experience") or []:
        parts += [job.get("title"), job.get("company"), job.get("location")]
        parts += (job.get("bullets") or [])[:8]
    for edu in profile.get("education") or []:
        parts += [edu.get("degree"), edu.get("field"), edu.get("institution")]
    return normalize(" ".join(str(p) for p in parts if p))[:16000]


async def refresh_document(session, candidate):
    from app.ai.actions import get_embedding_provider
    from app.models import CandidateSearchDoc

    profile = candidate.profile or {}
    candidate.years_experience_total = experience(profile)
    candidate.experience_computed_at = datetime.now(UTC)
    await session.flush()
    row = await session.scalar(
        select(CandidateSearchDoc).where(
            CandidateSearchDoc.org_id == candidate.org_id,
            CandidateSearchDoc.candidate_id == candidate.id,
        )
    )
    text = document(profile, candidate.full_name)
    digest = hashlib.sha256(text.encode()).hexdigest()
    provider = get_embedding_provider()
    if row is None:
        row = CandidateSearchDoc(org_id=candidate.org_id, candidate_id=candidate.id)
        session.add(row)
    unchanged = row.content_hash == digest
    row.search_text, row.normalized_name = text, normalize(candidate.full_name)
    row.updated_at = datetime.now(UTC)
    if (
        unchanged
        and row.embedding_status == "ready"
        and (row.embedding_model, row.embedding_dimensions) == (provider.model, provider.dimensions)
    ):
        return
    # Never serve stale content/model vectors after an edit or configuration change.
    row.content_hash, row.embedding = digest, None
    row.embedding_model, row.embedding_dimensions = provider.model, provider.dimensions
    try:
        vector = await provider.embed(text)
        row.embedding = vector
        row.embedding_status = "ready"
    except Exception:
        row.embedding_status = "unavailable"
    await session.flush()
