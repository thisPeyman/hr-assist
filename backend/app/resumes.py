"""Tenant-scoped resume workspace: list, inspect, correct, and remove files."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select, tuple_
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
    resume_id: UUID, changes: ResumeEdit, ctx: TenantContextDep, session: SessionDep
) -> ResumeDetail:
    from app.profiles import fields, lock_org, sync_candidate

    await lock_org(session, ctx.org.id)
    resume = await _resume(session, ctx.org.id, resume_id)
    job = (await _latest_jobs(session, [resume.id])).get(resume.id)
    if job is not None and blocked(job):
        raise HTTPException(status_code=409, detail="DOCUMENT_QUARANTINED")
    candidate = await _candidate(session, ctx.org.id, resume.candidate_id)
    if candidate is None:
        candidate = Candidate(org_id=ctx.org.id, full_name=changes.full_name.strip())
        session.add(candidate)
        await session.flush()
        resume.candidate_id = candidate.id
    before = fields(candidate.profile)
    contact = dict((candidate.profile or {}).get("contact") or {})
    contact.update(
        full_name=changes.full_name.strip(),
        email=changes.email,
        phone=changes.phone,
        location=changes.location,
    )
    profile = dict(candidate.profile or {})
    profile.update(
        contact=contact,
        headline=changes.headline,
        summary=changes.summary,
        skills=[skill.strip() for skill in changes.skills if skill.strip()],
    )
    candidate.full_name = changes.full_name.strip()
    candidate.email = changes.email
    candidate.phone = changes.phone
    candidate.location = changes.location
    candidate.headline = changes.headline
    candidate.profile = profile
    changed = [path for path, value in fields(profile).items() if value != before.get(path)]
    candidate.human_fields = sorted(set(candidate.human_fields or []) | set(changed))
    sync_candidate(candidate)
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
    from app.profiles import lock_org

    await lock_org(session, ctx.org.id)
    resume = await _resume(session, ctx.org.id, resume_id)
    candidate = await _candidate(session, ctx.org.id, resume.candidate_id)
    await session.delete(resume)
    await session.flush()
    if candidate is not None:
        remaining = (
            await session.execute(
                select(func.count())
                .select_from(ResumeFile)
                .where(ResumeFile.org_id == ctx.org.id, ResumeFile.candidate_id == candidate.id)
            )
        ).scalar_one()
        if remaining == 0:
            await session.delete(candidate)
    await session.commit()
