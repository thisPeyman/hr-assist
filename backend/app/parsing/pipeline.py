"""The parse pipeline state machine (spec §7.3): one job, run to an explicit
terminal status. Never drops, never raises past the boundary.

Terminal statuses:
- ``extracted``     — Candidate in the pool with a structured Profile
- ``needs_review``  — a human should look (bad document, low confidence,
                      missing identity, or the retry ladder exhausted)
- ``not_a_resume``  — the model routed the document out (cover letter, …)
- ``failed``        — infrastructure failure (API unreachable, unexpected bug)
Successful OCR and visual routes record ``ocr_applied``/``vision_used``.
"""

import asyncio
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    ParseJob,
    ParseJobStatus,
    ResumeExtraction,
    ResumeFile,
)
from app.parsing.documents import prepare_document
from app.parsing.extract_text import ExtractionError
from app.parsing.llm import ResumeExtractor, VisionResumeExtractor, run_extraction_ladder
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
    actor_user_id: uuid.UUID | None = None,
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
    actor_user_id: uuid.UUID | None,
) -> ParseJobStatus:
    # ---- Layer 1: OSS text extraction (free, local) ------------------------
    started = time.monotonic()
    try:
        extracted = await asyncio.to_thread(
            prepare_document, resume_file.bytes, resume_file.original_filename
        )
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
        raw_text=extracted.raw_text if extracted.raw_text is not None else extracted.text,
    )
    session.add(extraction_row)

    # ---- Layer 2: the one paid call + retry ladder -------------------------
    started = time.monotonic()
    transport = (
        VisionResumeExtractor(extractor, extracted.images) if extracted.images else extractor
    )
    outcome = await run_extraction_ladder(transport, extracted.text)
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
        _finish(
            job,
            ParseJobStatus.NEEDS_REVIEW if extracted.images else ParseJobStatus.FAILED,
            reason=f"api_error:{outcome.error}",
        )
        return job.status
    if outcome.kind == "invalid":
        # Keep whatever the model did emit: the needs_review queue (ticket 20)
        # shows the document plus the partial payload.
        extraction_row.raw_json = outcome.raw_json
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

    if extraction.needs_review:
        reason = "model_flagged"
    elif not (contact.email or contact.phone):
        reason = "missing_contact"
    elif extraction.confidence < settings.resume_extract_confidence_threshold:
        reason = "low_confidence"
    else:
        reason = None

    if resume_file.candidate_id is not None:
        # A replay must never overwrite a Profile accepted by a human.
        _finish(job, ParseJobStatus.NEEDS_REVIEW, reason="existing_profile")
        return job.status

    from app.profiles import attach_profile
    from app.summaries import ensure_summary

    profile = build_profile(extraction)
    candidate = await attach_profile(session, resume_file, profile, actor_user_id)
    if candidate is None:
        _finish(job, ParseJobStatus.NEEDS_REVIEW, reason="missing_name")
        return job.status
    if getattr(resume_file, "_obsolete", False):
        _finish(job, ParseJobStatus.EXTRACTED, "older_resume_discarded")
        await session.flush()
        # The newest-file-only policy removes this obsolete job by FK cascade.
        # Keep the response snapshot detached so commit cannot update a deleted row.
        session.expunge(job)
        session.expunge(extraction_row)
        await session.delete(resume_file)
        await session.flush()
        return job.status
    await ensure_summary(session, candidate, resume_file.sha256, profile, extractor)

    _finish(
        job,
        ParseJobStatus.NEEDS_REVIEW if reason else ParseJobStatus(extracted.route),
        reason=reason,
    )
    return job.status
