"""Tenant-scoped document review, immutable raw extraction and human decisions."""

import asyncio
from datetime import UTC, datetime
from typing import Annotated, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import (
    Candidate,
    CandidateActivity,
    InboundMail,
    ParseJob,
    ParseJobStatus,
    ResumeExtraction,
    ResumeFile,
)
from app.parsing.documents import render_images, scan_attachment
from app.parsing.extract_text import ExtractionError, sniff_kind
from app.parsing.llm import get_extractor
from app.parsing.schema import ResumeExtractionData, build_profile
from app.tenancy import TenantContextDep

review_router = APIRouter(prefix="/api", tags=["review"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
REVIEW_STATUSES = [ParseJobStatus.NEEDS_REVIEW, ParseJobStatus.FAILED]


def blocked(job: ParseJob) -> bool:
    return bool(job.reason and "inbound:" in job.reason)


def job_item(job: ParseJob, resume: ResumeFile) -> dict:
    return {
        "id": str(job.id),
        "filename": resume.original_filename,
        "status": job.status.value,
        "reason": job.reason,
        "created_at": job.created_at,
        "candidate_id": resume.candidate_id,
        "blocked": blocked(job),
    }


@review_router.get("/ingestion/settings")
async def ingestion_settings(ctx: TenantContextDep, session: SessionDep) -> dict:
    review_count = (
        await session.execute(
            select(func.count())
            .select_from(ParseJob)
            .where(
                ParseJob.org_id == ctx.org.id,
                ParseJob.status.in_(REVIEW_STATUSES),
                func.coalesce(ParseJob.reason, "").not_like("human_dismissed%"),
            )
        )
    ).scalar_one()
    mail_failure_count = (
        await session.execute(
            select(func.count())
            .select_from(InboundMail)
            .where(InboundMail.org_id == ctx.org.id, InboundMail.status == "failed")
        )
    ).scalar_one()
    return {
        "email_address": f"resumes+{ctx.org.slug}@{settings.inbound_domain}"
        if settings.inbound_domain
        else None,
        "email_enabled": bool(settings.inbound_domain and settings.inbound_webhook_secret),
        "review_count": review_count + mail_failure_count,
    }


@review_router.get("/review")
async def list_review(
    ctx: TenantContextDep,
    session: SessionDep,
    view: Literal["review", "all"] = "review",
) -> dict:
    query = (
        select(ParseJob, ResumeFile)
        .join(ResumeFile, ParseJob.resume_file_id == ResumeFile.id)
        .where(ParseJob.org_id == ctx.org.id, ResumeFile.org_id == ctx.org.id)
        .order_by(ParseJob.created_at.desc(), ParseJob.id.desc())
        .limit(200)
    )
    if view == "review":
        query = query.where(
            ParseJob.status.in_(REVIEW_STATUSES),
            func.coalesce(ParseJob.reason, "").not_like("human_dismissed%"),
        )
    rows = (await session.execute(query)).all()
    failures = (
        (
            await session.execute(
                select(InboundMail)
                .where(InboundMail.org_id == ctx.org.id, InboundMail.status == "failed")
                .order_by(InboundMail.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [job_item(job, resume) for job, resume in rows],
        "mail_failures": [
            {"id": str(mail.id), "reason": mail.reason, "created_at": mail.created_at}
            for mail in failures
        ],
    }


async def load_job(session: AsyncSession, org_id: UUID, job_id: UUID, *, lock=False):
    query = select(ParseJob).where(ParseJob.id == job_id, ParseJob.org_id == org_id)
    if lock:
        query = query.with_for_update()
    job = (await session.execute(query)).scalar_one_or_none()
    if job is None:
        raise HTTPException(404, "DOCUMENT_NOT_FOUND")
    resume = (
        await session.execute(
            select(ResumeFile).where(
                ResumeFile.id == job.resume_file_id, ResumeFile.org_id == org_id
            )
        )
    ).scalar_one()
    return job, resume


@review_router.get("/review/{job_id}")
async def review_detail(job_id: UUID, ctx: TenantContextDep, session: SessionDep) -> dict:
    job, resume = await load_job(session, ctx.org.id, job_id)
    extraction = (
        await session.execute(
            select(ResumeExtraction)
            .where(ResumeExtraction.parse_job_id == job.id, ResumeExtraction.org_id == ctx.org.id)
            .order_by(ResumeExtraction.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return {
        **job_item(job, resume),
        "raw_text": extraction.raw_text if extraction else None,
        "raw_json": extraction.raw_json if extraction else None,
        "candidate_profile": (await session.get(Candidate, resume.candidate_id)).profile
        if resume.candidate_id
        else None,
    }


@review_router.get("/review/{job_id}/document")
async def original_document(job_id: UUID, ctx: TenantContextDep, session: SessionDep) -> Response:
    job, resume = await load_job(session, ctx.org.id, job_id)
    if blocked(job):
        raise HTTPException(409, "DOCUMENT_QUARANTINED")
    # Download only: never execute untrusted HTML or embedded document content in our origin.
    filename = quote(resume.original_filename, safe="")
    return Response(
        resume.bytes,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@review_router.get("/review/{job_id}/preview")
async def document_preview(
    job_id: UUID,
    ctx: TenantContextDep,
    session: SessionDep,
    page: Annotated[int, Query(ge=0, lt=20)] = 0,
) -> Response:
    job, resume = await load_job(session, ctx.org.id, job_id)
    if blocked(job):
        raise HTTPException(409, "DOCUMENT_QUARANTINED")
    try:
        kind = sniff_kind(resume.bytes, resume.original_filename)
        if kind not in {"pdf", "image"}:
            raise ExtractionError("preview_unavailable")
        images = await asyncio.to_thread(render_images, resume.bytes, pdf=kind == "pdf")
        if page >= len(images):
            raise ExtractionError("preview_unavailable")
    except ExtractionError as exc:
        raise HTTPException(404, "PREVIEW_UNAVAILABLE") from exc
    return Response(
        images[page],
        media_type="image/png",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Page-Count": str(len(images)),
        },
    )


class ReviewDecision(BaseModel):
    action: Literal["accept", "not_a_resume", "failed", "rescan"]
    extraction: ResumeExtractionData | None = None
    edited_fields: list[str] | None = None
    expected_values: dict = Field(default_factory=dict)


@review_router.post("/review/{job_id}/resolve")
async def resolve_review(
    job_id: UUID,
    decision: ReviewDecision,
    ctx: TenantContextDep,
    session: SessionDep,
    generator: Annotated[object, Depends(get_extractor)],
) -> dict:
    from app.profiles import lock_org

    await lock_org(session, ctx.org.id)
    job, resume = await load_job(session, ctx.org.id, job_id, lock=True)
    if job.status not in REVIEW_STATUSES or (job.reason or "").startswith("human_dismissed"):
        raise HTTPException(409, "DOCUMENT_ALREADY_RESOLVED")
    if decision.action == "rescan":
        if not blocked(job) or job.reason not in {
            "inbound:scanner_unavailable",
            "inbound:malware_detected",
        }:
            raise HTTPException(409, "DOCUMENT_QUARANTINED")
        try:
            await asyncio.to_thread(scan_attachment, resume.bytes)
        except ExtractionError as exc:
            job.reason = f"inbound:{exc.reason}"
        else:
            job.status = ParseJobStatus.PENDING
            job.reason = None
            job.finished_at = None
        await session.commit()
        return {"candidate_id": None}
    if decision.action != "accept":
        job.status = ParseJobStatus(decision.action)
        job.reason = f"human_dismissed:{job.reason or ''}"
        job.finished_at = datetime.now(UTC)
        await session.commit()
        return {"candidate_id": None}
    if blocked(job):
        raise HTTPException(409, "DOCUMENT_QUARANTINED")
    extraction = decision.extraction
    if extraction is None or not (extraction.contact.full_name or "").strip():
        raise HTTPException(422, "PROFILE_NAME_REQUIRED")
    extraction.contact.full_name = extraction.contact.full_name.strip()
    from app.profiles import apply_human_edits, attach_profile, fields
    from app.summaries import ensure_summary

    raw = (
        await session.execute(
            select(ResumeExtraction)
            .where(ResumeExtraction.parse_job_id == job.id, ResumeExtraction.org_id == ctx.org.id)
            .order_by(ResumeExtraction.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    baseline = fields(raw.raw_json if raw else None)
    incoming = build_profile(extraction)
    incoming_fields = fields(incoming)
    edited = decision.edited_fields
    if edited is None:
        edited = [path for path, value in incoming_fields.items() if value != baseline.get(path)]
    if any(path not in incoming_fields for path in edited):
        raise HTTPException(422, "INVALID_PROFILE")
    candidate = await attach_profile(session, resume, incoming, ctx.user.id)
    if getattr(resume, "_obsolete", False):
        # Roll back all attachment side effects; old reviews never replace newer versions.
        raise HTTPException(409, "RESUME_SUPERSEDED")
    previous = candidate._profile_before_attachment
    if decision.edited_fields is None and previous is not None:
        # Legacy clients have no baseline token. Inferred edits can only replace
        # the extraction value they actually saw; other conflicts remain diffs.
        edited = [path for path in edited if previous.get(path) == baseline.get(path)]
    for path in edited:
        expected = decision.expected_values.get(path, baseline.get(path))
        if (
            previous is not None
            and previous.get(path) != incoming_fields[path]
            and previous.get(path) != expected
        ):
            raise HTTPException(409, "PROFILE_CHANGED_REFRESH")
    await apply_human_edits(
        session, candidate, {path: incoming_fields[path] for path in edited}, ctx.user.id
    )
    await ensure_summary(session, candidate, resume.sha256, candidate.profile, generator)
    session.add(
        CandidateActivity(
            org_id=ctx.org.id,
            candidate_id=candidate.id,
            actor_user_id=ctx.user.id,
            event_type="profile_review_accepted",
            data={"parse_job_id": str(job.id)},
        )
    )
    job.status = ParseJobStatus.EXTRACTED
    job.reason = "human_accepted"
    job.finished_at = datetime.now(UTC)
    candidate_id = str(candidate.id)
    await session.commit()
    return {"candidate_id": candidate_id}
