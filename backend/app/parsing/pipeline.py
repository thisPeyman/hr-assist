"""The parse pipeline state machine (spec §7.3): one job, run to an explicit
terminal status. Never drops, never raises past the boundary.

Terminal statuses:
- ``extracted``     — Candidate in the pool with a structured Profile
- ``needs_review``  — a human should look (bad document, low confidence,
                      missing identity, or the retry ladder exhausted)
- ``not_a_resume``  — the model routed the document out (cover letter, …)
- ``failed``        — infrastructure failure (API unreachable, unexpected bug)
``ocr_applied``/``vision_used`` arrive with ticket 21.
"""

import time
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    Candidate,
    CandidateActivity,
    ParseJob,
    ParseJobStatus,
    ResumeExtraction,
    ResumeFile,
)
from app.parsing.extract_text import ExtractionError, extract_text
from app.parsing.llm import ResumeExtractor, run_extraction_ladder
from app.parsing.schema import build_profile


def _finish(job: ParseJob, status: ParseJobStatus, reason: str | None = None) -> None:
    job.status = status
    job.reason = reason
    job.finished_at = datetime.now(UTC)


async def process_parse_job(
    session: AsyncSession,
    job: ParseJob,
    resume_file: ResumeFile,
    *,
    extractor: ResumeExtractor,
    actor_user_id: uuid.UUID | str | None = None,
) -> ParseJobStatus:
    """Run one job inside the caller's transaction; returns the terminal status.

    The caller commits. Every path through here ends in a terminal status —
    an unexpected exception is caught and recorded as ``failed`` rather than
    leaving the job pending forever.
    """
    try:
        return await _process(
            session, job, resume_file, extractor=extractor, actor_user_id=actor_user_id
        )
    except Exception as exc:  # noqa: BLE001 — the job must end terminal, not pending
        _finish(job, ParseJobStatus.FAILED, reason=f"error:{type(exc).__name__}: {exc}")
        return job.status


async def _process(
    session: AsyncSession,
    job: ParseJob,
    resume_file: ResumeFile,
    *,
    extractor: ResumeExtractor,
    actor_user_id: uuid.UUID | str | None,
) -> ParseJobStatus:
    # ---- Layer 1: OSS text extraction (free, local) ------------------------
    started = time.monotonic()
    try:
        extracted = extract_text(resume_file.bytes, resume_file.original_filename)
    except ExtractionError as exc:
        _finish(job, ParseJobStatus.NEEDS_REVIEW, reason=f"extraction:{exc.reason}")
        return job.status
    job.extract_ms = int((time.monotonic() - started) * 1000)

    # Original raw text is kept no matter what happens next (re-parse campaigns
    # are UPDATE + re-enqueue; the needs_review queue shows the document).
    extraction_row = ResumeExtraction(
        org_id=job.org_id,
        parse_job_id=job.id,
        resume_file_id=resume_file.id,
        raw_text=extracted.text,
    )
    session.add(extraction_row)

    # ---- Layer 2: the one paid call + retry ladder -------------------------
    started = time.monotonic()
    outcome = await run_extraction_ladder(extractor, extracted.text)
    job.llm_ms = int((time.monotonic() - started) * 1000)
    job.attempts = outcome.attempts
    job.prompt_version = outcome.prompt_version
    job.schema_version = outcome.schema_version
    if outcome.model:
        job.model = outcome.model
        extraction_row.model = outcome.model
        extraction_row.prompt_version = outcome.prompt_version
        extraction_row.schema_version = outcome.schema_version

    if outcome.kind == "api_error":
        _finish(job, ParseJobStatus.FAILED, reason=f"api_error:{outcome.error}")
        return job.status
    if outcome.kind == "invalid":
        _finish(job, ParseJobStatus.NEEDS_REVIEW, reason="validation_failed")
        return job.status

    assert outcome.extraction is not None and outcome.raw_json is not None
    extraction = outcome.extraction
    extraction_row.raw_json = outcome.raw_json

    if extracted.truncated and "input_truncated" not in extraction.extraction_notes:
        extraction.extraction_notes.append("input_truncated")

    # ---- Routing: every document lands somewhere explicit ------------------
    if not extraction.is_resume:
        _finish(job, ParseJobStatus.NOT_A_RESUME)
        return job.status

    contact = extraction.contact
    if not (contact.full_name or contact.email or contact.phone):
        _finish(job, ParseJobStatus.NEEDS_REVIEW, reason="missing_identity")
        return job.status
    if not contact.full_name:
        # Contact exists but no name — the needs_review queue (ticket 20)
        # shows the partial data; email/phone Merge is ticket 13.
        _finish(job, ParseJobStatus.NEEDS_REVIEW, reason="missing_name")
        return job.status

    if extraction.needs_review:
        reason = "model_flagged"
    elif extraction.confidence < settings.resume_extract_confidence_threshold:
        reason = "low_confidence"
    else:
        reason = None

    candidate = Candidate(
        org_id=job.org_id,
        full_name=contact.full_name,
        headline=extraction.headline,
        email=contact.email,
        phone=contact.phone,
        location=contact.location,
        profile=build_profile(extraction),
    )
    session.add(candidate)
    await session.flush()  # candidate.id for the link + activity

    resume_file.candidate_id = candidate.id
    if actor_user_id is not None:
        actor_user_id = (
            uuid.UUID(actor_user_id) if isinstance(actor_user_id, str) else actor_user_id
        )
    session.add(
        CandidateActivity(
            org_id=job.org_id,
            candidate_id=candidate.id,
            actor_user_id=actor_user_id,
            event_type="resume_added",
            data={
                "filename": resume_file.original_filename,
                "parse_status": ParseJobStatus.NEEDS_REVIEW.value
                if reason
                else ParseJobStatus.EXTRACTED.value,
            },
        )
    )

    _finish(
        job,
        ParseJobStatus.NEEDS_REVIEW if reason else ParseJobStatus.EXTRACTED,
        reason=reason,
    )
    return job.status
