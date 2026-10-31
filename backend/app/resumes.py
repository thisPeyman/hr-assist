"""Tenant-scoped resume workspace: list, inspect, correct, and remove files."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.db import get_session
from app.models import (
    Candidate,
    CandidateActivity,
    ParseJob,
    ParseJobStatus,
    ResumeExtraction,
    ResumeFile,
)
from app.parsing.llm import get_extractor
from app.review import blocked
from app.tenancy import TenantContextDep

resumes_router = APIRouter(prefix="/api/resumes", tags=["resumes"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


class ResumeItem(BaseModel):
    id: UUID
    filename: str
    created_at: datetime
    status: str
    reason: str | None
    latest_job_id: UUID | None
    candidate_id: UUID | None
    candidate_name: str | None
    candidate_email: str | None


class ResumeList(BaseModel):
    items: list[ResumeItem]
    next_cursor: str | None


class ResumeDetail(ResumeItem):
    profile: dict | None


class ResumeEdit(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=200)
    headline: str | None = Field(default=None, max_length=300)
    summary: str | None = Field(default=None, max_length=5000)
    skills: list[str] = Field(default_factory=list, max_length=100)
    expected_values: dict | None = None

    @field_validator("full_name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("full name is required")
        return value.strip()


def _item(resume: ResumeFile, candidate: Candidate | None, job: ParseJob | None) -> ResumeItem:
    return ResumeItem(
        id=resume.id,
        filename=resume.original_filename,
        created_at=resume.created_at,
        status=job.status.value if job else "pending",
        reason=job.reason if job else None,
        latest_job_id=job.id if job else None,
        candidate_id=candidate.id if candidate else None,
        candidate_name=candidate.full_name if candidate else None,
        candidate_email=candidate.email if candidate else None,
    )


async def _latest_jobs(session: AsyncSession, resume_ids: list[UUID]) -> dict[UUID, ParseJob]:
    if not resume_ids:
        return {}
    jobs = (
        await session.execute(
            select(ParseJob)
            .where(ParseJob.resume_file_id.in_(resume_ids))
            .order_by(ParseJob.resume_file_id, ParseJob.created_at.desc(), ParseJob.id.desc())
        )
    ).scalars()
    latest: dict[UUID, ParseJob] = {}
    for job in jobs:
        latest.setdefault(job.resume_file_id, job)
    return latest


async def _resume(session: AsyncSession, org_id: UUID, resume_id: UUID) -> ResumeFile:
    result = (
        await session.execute(
            select(ResumeFile)
            .options(defer(ResumeFile.bytes))
            .where(ResumeFile.id == resume_id, ResumeFile.org_id == org_id)
        )
    ).scalar_one_or_none()
    if result is None:
        raise HTTPException(status_code=404, detail="RESUME_NOT_FOUND")
    return result


async def _candidate(
    session: AsyncSession, org_id: UUID, candidate_id: UUID | None
) -> Candidate | None:
    if candidate_id is None:
        return None
    return (
        await session.execute(
            select(Candidate).where(Candidate.id == candidate_id, Candidate.org_id == org_id)
        )
    ).scalar_one_or_none()


@resumes_router.get("", response_model=ResumeList)
async def list_resumes(
    ctx: TenantContextDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    search: Annotated[str, Query(max_length=120)] = "",
    before: str | None = None,
) -> ResumeList:
    query = (
        select(ResumeFile, Candidate)
        .options(defer(ResumeFile.bytes))
        .outerjoin(Candidate, ResumeFile.candidate_id == Candidate.id)
        .where(ResumeFile.org_id == ctx.org.id)
    )
    if search.strip():
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                ResumeFile.original_filename.ilike(pattern),
                Candidate.full_name.ilike(pattern),
                Candidate.email.ilike(pattern),
            )
        )
    if before:
        try:
            timestamp, identifier = before.rsplit("|", 1)
            point = datetime.fromisoformat(timestamp)
            if point.tzinfo is None:
                raise ValueError("timezone required")
            cursor_id = UUID(identifier)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="INVALID_CURSOR") from exc
        query = query.where(tuple_(ResumeFile.created_at, ResumeFile.id) < (point, cursor_id))
    rows = (
        await session.execute(
            query.order_by(ResumeFile.created_at.desc(), ResumeFile.id.desc()).limit(limit + 1)
        )
    ).all()
    page = rows[:limit]
    latest = await _latest_jobs(session, [resume.id for resume, _ in page])
    next_cursor = None
    if len(rows) > limit and page:
        last = page[-1][0]
        next_cursor = f"{last.created_at.isoformat()}|{last.id}"
    return ResumeList(
        items=[_item(resume, candidate, latest.get(resume.id)) for resume, candidate in page],
        next_cursor=next_cursor,
    )


@resumes_router.get("/{resume_id}", response_model=ResumeDetail)
async def get_resume(resume_id: UUID, ctx: TenantContextDep, session: SessionDep) -> ResumeDetail:
    resume = await _resume(session, ctx.org.id, resume_id)
    candidate = await _candidate(session, ctx.org.id, resume.candidate_id)
    job = (await _latest_jobs(session, [resume.id])).get(resume.id)
    profile = candidate.profile if candidate else None
    if profile is None and job is not None:
        extraction = (
            await session.execute(
                select(ResumeExtraction)
                .where(
                    ResumeExtraction.parse_job_id == job.id, ResumeExtraction.org_id == ctx.org.id
                )
                .order_by(ResumeExtraction.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        profile = extraction.raw_json if extraction else None
    return ResumeDetail(**_item(resume, candidate, job).model_dump(), profile=profile)


@resumes_router.patch("/{resume_id}", response_model=ResumeDetail)
async def update_resume(
    resume_id: UUID,
    changes: ResumeEdit,
    ctx: TenantContextDep,
    session: SessionDep,
    generator: Annotated[object, Depends(get_extractor)],
) -> ResumeDetail:
    from app.profiles import apply_human_edits, attach_profile, lock_org, put
    from app.summaries import ensure_summary

    await lock_org(session, ctx.org.id)
    resume = await _resume(session, ctx.org.id, resume_id)
    job = (await _latest_jobs(session, [resume.id])).get(resume.id)
    if job is not None and blocked(job):
        raise HTTPException(status_code=409, detail="DOCUMENT_QUARANTINED")
    candidate = await _candidate(session, ctx.org.id, resume.candidate_id)
    values = {}
    for key in changes.model_fields_set - {"expected_values"}:
        path = f"contact.{key}" if key in {"full_name", "email", "phone", "location"} else key
        value = getattr(changes, key)
        values[path] = [s.strip() for s in value if s.strip()] if key == "skills" else value
    # Omitted PATCH fields are not instructions to erase existing information.
    profile = {}
    if candidate is None and job is not None:
        raw = (
            await session.execute(
                select(ResumeExtraction)
                .where(
                    ResumeExtraction.parse_job_id == job.id, ResumeExtraction.org_id == ctx.org.id
                )
                .order_by(ResumeExtraction.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if raw and raw.raw_json:
            # Use the same safe partial-profile normalization as the review form.
            from pydantic import ValidationError

            from app.parsing.schema import ResumeExtractionData, build_profile

            try:
                profile = build_profile(ResumeExtractionData.model_validate(raw.raw_json))
            except ValidationError:
                pass
    for path, value in values.items():
        put(profile, path, value)
    candidate = await attach_profile(session, resume, profile, ctx.user.id)
    if getattr(resume, "_obsolete", False):
        raise HTTPException(409, "RESUME_SUPERSEDED")
    before = candidate._profile_before_attachment
    if changes.expected_values is not None and before is not None:
        for path in values:
            if before.get(path) != values[path] and before.get(path) != changes.expected_values.get(
                path
            ):
                raise HTTPException(409, "PROFILE_CHANGED_REFRESH")
    await apply_human_edits(session, candidate, values, ctx.user.id)
    profile = candidate.profile
    changed = list(values)
    await ensure_summary(session, candidate, resume.sha256, profile, generator)
    session.add(
        CandidateActivity(
            org_id=ctx.org.id,
            candidate_id=candidate.id,
            actor_user_id=ctx.user.id,
            event_type="resume_profile_edited",
            data={"resume_file_id": str(resume.id), "fields": changed},
        )
    )
    if job is not None and job.status in {ParseJobStatus.NEEDS_REVIEW, ParseJobStatus.FAILED}:
        job.status = ParseJobStatus.EXTRACTED
        job.reason = "human_accepted"
        job.finished_at = datetime.now(UTC)
    await session.commit()
    return ResumeDetail(**_item(resume, candidate, job).model_dump(), profile=profile)


@resumes_router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(resume_id: UUID, ctx: TenantContextDep, session: SessionDep) -> None:
    from app.profiles import activity, lock_org

    await lock_org(session, ctx.org.id)
    resume = await _resume(session, ctx.org.id, resume_id)
    candidate = await _candidate(session, ctx.org.id, resume.candidate_id)
    if candidate is not None:
        activity(session, candidate, "resume_deleted", ctx.user.id, resume_version=resume.sha256)
    await session.delete(resume)
    await session.commit()
