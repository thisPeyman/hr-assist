"""Profile reconciliation and identity matching; human decisions win."""

import copy
import re
import unicodedata
from difflib import SequenceMatcher

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import defer

from app.models import (
    ApplicationActivity,
    Candidate,
    CandidateActivity,
    CandidateApplication,
    CandidateNote,
    ProfileChange,
    ResumeFile,
    ResumeSummary,
)

PROFILE_FIELDS = (
    "headline",
    "summary",
    "skills",
    "industries",
    "work_experience",
    "education",
    "languages",
    "certifications",
    "document_language",
    "extraction_notes",
)
CONTACT_FIELDS = ("full_name", "email", "phone", "location", "links")


def email_key(value):
    return (value or "").strip().casefold() or None


def phone_key(value):
    value = (value or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    number = re.sub(r"\D", "", value)
    if number.startswith("00"):
        number = number[2:]
    if len(number) == 11 and number.startswith("09"):
        number = "98" + number[1:]
    return number or None


def name_key(value):
    return " ".join(
        unicodedata.normalize("NFKC", value or "")
        .translate(str.maketrans("يك", "یک"))
        .replace("\u200c", " ")
        .casefold()
        .split()
    )


async def lock_org(session, org_id):
    await session.execute(
        select(func.pg_advisory_xact_lock(func.hashtextextended("profile:" + str(org_id), 0)))
    )


def fields(profile):
    profile = profile if isinstance(profile, dict) else {}
    contact = profile.get("contact")
    contact = contact if isinstance(contact, dict) else {}
    return {
        **{f"contact.{key}": contact.get(key) for key in CONTACT_FIELDS},
        **{key: profile.get(key) for key in PROFILE_FIELDS},
    }


def put(profile, path, value):
    if path.startswith("contact."):
        profile.setdefault("contact", {})[path.split(".", 1)[1]] = copy.deepcopy(value)
    else:
        profile[path] = copy.deepcopy(value)


def sync_candidate(candidate):
    profile = candidate.profile or {}
    contact = profile.get("contact") or {}
    candidate.full_name = contact.get("full_name") or candidate.full_name
    candidate.email = contact.get("email")
    candidate.phone = contact.get("phone")
    candidate.location = contact.get("location")
    candidate.headline = profile.get("headline")
    candidate.normalized_email = email_key(candidate.email)
    candidate.normalized_phone = phone_key(candidate.phone)


def activity(session, candidate, event, actor=None, **data):
    session.add(
        CandidateActivity(
            org_id=candidate.org_id,
            candidate_id=candidate.id,
            actor_user_id=actor,
            event_type=event,
            data=data,
        )
    )


async def reconcile(session, candidate, incoming, version, actor=None):
    current = copy.deepcopy(candidate.profile or {})
    old_fields = fields(current)
    protected = set(candidate.human_fields or [])
    await session.execute(
        update(ProfileChange)
        .where(
            ProfileChange.candidate_id == candidate.id,
            ProfileChange.status == "pending",
            ProfileChange.resume_version != version,
        )
        .values(status="superseded")
    )
    filled, proposed = [], []
    for path, value in fields(incoming).items():
        old = old_fields.get(path)
        if value in (None, "", [], {}) or value == old:
            continue
        if old in (None, "", [], {}) and path not in protected:
            put(current, path, value)
            filled.append(path)
        else:
            exists = (
                await session.execute(
                    select(ProfileChange.id).where(
                        ProfileChange.candidate_id == candidate.id,
                        ProfileChange.resume_version == version,
                        ProfileChange.field_path == path,
                    )
                )
            ).first()
            if not exists:
                session.add(
                    ProfileChange(
                        org_id=candidate.org_id,
                        candidate_id=candidate.id,
                        resume_version=version,
                        field_path=path,
                        old_value=old,
                        new_value=value,
                        status="pending",
                    )
                )
                proposed.append(path)
    candidate.profile = current
    sync_candidate(candidate)
    if filled or proposed:
        activity(
            session,
            candidate,
            "profile_reconciled",
            actor,
            resume_version=version,
            filled=filled,
            proposed=proposed,
        )


async def retain_latest(session, candidate):
    await session.flush()
    files = list(
        (
            await session.execute(
                select(ResumeFile)
                .options(defer(ResumeFile.bytes))
                .where(
                    ResumeFile.candidate_id == candidate.id, ResumeFile.org_id == candidate.org_id
                )
                .order_by(ResumeFile.created_at.desc(), ResumeFile.id.desc())
            )
        ).scalars()
    )
    if files:
        candidate.latest_resume_version = files[0].sha256
        for old in files[1:]:
            await session.delete(old)
        await session.flush()
    return files[0] if files else None


async def merge_candidates(session, target, source, actor=None):
    if target.id == source.id or target.org_id != source.org_id:
        raise ValueError("invalid merge")
    newest_version = (
        await session.execute(
            select(ResumeFile.sha256)
            .where(
                ResumeFile.candidate_id.in_([target.id, source.id]),
                ResumeFile.org_id == target.org_id,
            )
            .order_by(ResumeFile.created_at.desc(), ResumeFile.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    await reconcile(
        session,
        target,
        source.profile or {},
        newest_version or target.latest_resume_version or source.latest_resume_version or "manual",
        actor,
    )
    target.human_fields = sorted(set(target.human_fields or []) | set(source.human_fields or []))
    counts = {"candidate_applications": await merge_applications(session, target, source, actor)}
    for model in (
        ResumeFile,
        CandidateNote,
        CandidateActivity,
        ProfileChange,
    ):
        result = await session.execute(
            update(model)
            .where(model.candidate_id == source.id, model.org_id == target.org_id)
            .values(candidate_id=target.id)
        )
        counts[model.__tablename__] = result.rowcount
    source_summaries = (
        (
            await session.execute(
                select(ResumeSummary).where(ResumeSummary.candidate_id == source.id)
            )
        )
        .scalars()
        .all()
    )
    for summary in source_summaries:
        exists = (
            await session.execute(
                select(ResumeSummary.id).where(
                    ResumeSummary.candidate_id == target.id,
                    ResumeSummary.resume_version == summary.resume_version,
                )
            )
        ).first()
        if exists:
            await session.delete(summary)
        else:
            summary.candidate_id = target.id
    activity(
        session,
        target,
        "candidate_merged",
        actor,
        source_id=str(source.id),
        source_name=source.full_name,
        transferred=counts,
    )
    await session.delete(source)
    await session.flush()
    await retain_latest(session, target)
    await session.execute(
        update(ProfileChange)
        .where(
            ProfileChange.candidate_id == target.id,
            ProfileChange.status == "pending",
            ProfileChange.resume_version != target.latest_resume_version,
        )
        .values(status="superseded")
    )
    return target


async def merge_applications(session, target, source, actor=None):
    """Union candidacies before Candidate reassignment hits the canonical key.

    Target state wins without a stage/owner transition. All source state survives
    in an event; children are reparented before retiring the duplicate. Future
    application child modules (interviews etc.) must join this explicit boundary.
    Caller holds the shared org identity/workflow transaction lock.
    """
    applications = (
        await session.scalars(
            select(CandidateApplication).where(
                CandidateApplication.org_id == target.org_id,
                CandidateApplication.candidate_id.in_([source.id, target.id]),
            )
        )
    ).all()
    canonical = {a.role_id: a for a in applications if a.candidate_id == target.id}
    incoming = [a for a in applications if a.candidate_id == source.id]
    for application in incoming:
        kept = canonical.get(application.role_id)
        if kept is None:
            application.candidate_id = target.id
            continue
        for child in (CandidateNote, ApplicationActivity):
            await session.execute(
                update(child)
                .where(child.org_id == target.org_id, child.application_id == application.id)
                .values(application_id=kept.id)
            )
        session.add(
            ApplicationActivity(
                org_id=target.org_id,
                application_id=kept.id,
                actor_user_id=actor,
                event_type="application_merged",
                data={
                    "source_application_id": str(application.id),
                    "source_candidate_id": str(source.id),
                    "source_stage_id": str(application.stage_id),
                    "source_owner_id": str(application.owner_id) if application.owner_id else None,
                    "source_created_at": application.created_at.isoformat(),
                    "source_data": application.data,
                    "kept_stage_id": str(kept.stage_id),
                    "kept_owner_id": str(kept.owner_id) if kept.owner_id else None,
                    "resolution": "target_state_preserved",
                },
            )
        )
        await session.delete(application)
    await session.flush()
    return len(incoming)


async def attach_profile(session, resume, incoming, actor=None):
    await lock_org(session, resume.org_id)
    contact = incoming.get("contact") or {}
    email, phone = email_key(contact.get("email")), phone_key(contact.get("phone"))
    conditions = []
    if email:
        conditions.append(Candidate.normalized_email == email)
    if phone:
        conditions.append(Candidate.normalized_phone == phone)
    matches = []
    if conditions:
        matches = list(
            (
                await session.execute(
                    select(Candidate)
                    .where(Candidate.org_id == resume.org_id, or_(*conditions))
                    .order_by(Candidate.created_at, Candidate.id)
                )
            ).scalars()
        )
    if resume.candidate_id is not None:
        linked = (
            await session.execute(
                select(Candidate).where(
                    Candidate.id == resume.candidate_id, Candidate.org_id == resume.org_id
                )
            )
        ).scalar_one()
        matches = [linked, *[item for item in matches if item.id != linked.id]]
    if matches:
        candidate = matches[0]
        candidate._profile_before_attachment = fields(candidate.profile)
        for duplicate in matches[1:]:
            await merge_candidates(session, candidate, duplicate, actor)
        newest = (
            await session.execute(
                select(ResumeFile)
                .options(defer(ResumeFile.bytes))
                .where(ResumeFile.candidate_id == candidate.id)
                .order_by(ResumeFile.created_at.desc(), ResumeFile.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if newest is not None and (newest.created_at, newest.id) > (resume.created_at, resume.id):
            resume.candidate_id = candidate.id
            resume._obsolete = True
            activity(
                session,
                candidate,
                "older_resume_discarded",
                actor,
                resume_version=resume.sha256,
                kept_version=newest.sha256,
            )
            return candidate
        candidate.new_resume_received = True
        await reconcile(session, candidate, incoming, resume.sha256, actor)
        event = "new_resume_added"
    else:
        if not (contact.get("full_name") or "").strip():
            return None
        candidate = Candidate(
            org_id=resume.org_id,
            full_name=contact["full_name"],
            profile=copy.deepcopy(incoming),
            human_fields=[],
        )
        sync_candidate(candidate)
        candidate._profile_before_attachment = None
        session.add(candidate)
        await session.flush()
        event = "resume_added"
    resume.candidate_id = candidate.id
    candidate.latest_resume_version = resume.sha256
    activity(
        session,
        candidate,
        event,
        actor,
        filename=resume.original_filename,
        resume_version=resume.sha256,
    )
    await retain_latest(session, candidate)
    return candidate


async def apply_human_edits(session, candidate, values, actor=None):
    """Apply only intentional edits and retire proposals based on older values."""
    profile = copy.deepcopy(candidate.profile or {})
    before = fields(profile)
    changed = {
        path: {"old": before.get(path), "new": value}
        for path, value in values.items()
        if value != before.get(path)
    }
    for path, value in values.items():
        put(profile, path, value)
    candidate.profile = profile
    candidate.human_fields = sorted(set(candidate.human_fields or []) | set(values))
    sync_candidate(candidate)
    if values:
        await session.execute(
            update(ProfileChange)
            .where(
                ProfileChange.candidate_id == candidate.id,
                ProfileChange.org_id == candidate.org_id,
                ProfileChange.status == "pending",
                ProfileChange.field_path.in_(values),
            )
            .values(status="superseded")
        )
    if changed:
        activity(session, candidate, "profile_edited", actor, changes=changed)


async def similar_candidates(session, candidate):
    peers = (
        await session.execute(
            select(Candidate).where(
                Candidate.org_id == candidate.org_id, Candidate.id != candidate.id
            )
        )
    ).scalars()
    name = name_key(candidate.full_name)
    results = []
    for peer in peers:
        score = SequenceMatcher(None, name, name_key(peer.full_name)).ratio()
        if len(name) >= 4 and score >= 0.82:
            results.append(
                {
                    "id": str(peer.id),
                    "full_name": peer.full_name,
                    "email": peer.email,
                    "phone": peer.phone,
                    "similarity": round(score, 3),
                }
            )
    return sorted(results, key=lambda item: (-item["similarity"], item["id"]))[:10]
