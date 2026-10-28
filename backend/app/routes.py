"""API routes: signup (ours), login/logout (fastapi-users), /api/me,
and ticket 11's ingest + Talent Pool endpoints."""

import hashlib
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, status
from fastapi_users import InvalidPasswordException
from fastapi_users.authentication.strategy.db import DatabaseStrategy
from fastapi_users.exceptions import UserAlreadyExists
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Candidate, ParseJob, ParseJobStatus, ResumeFile
from app.parsing.extract_text import sniff_kind
from app.parsing.llm import ResumeExtractor, get_extractor
from app.parsing.pipeline import process_parse_job
from app.tenancy import TenantContextDep, load_membership_with_org
from app.users import (
    SESSION_COOKIE_ATTRS,
    UserCreate,
    UserManagerDep,
    auth_backend,
    fastapi_users,
    get_database_strategy,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])
api_router = APIRouter(prefix="/api", tags=["api"])


class OrgOut(BaseModel):
    id: UUID
    name: str
    slug: str


class SignupResponse(BaseModel):
    id: UUID
    email: str
    is_active: bool
    is_superuser: bool
    is_verified: bool
    org: OrgOut
    role: Literal["admin", "member"]


class MeResponse(BaseModel):
    id: UUID
    email: str
    org: OrgOut
    role: Literal["admin", "member"]


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(value=token, **SESSION_COOKIE_ATTRS)


@auth_router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    response_model=SignupResponse,
    name="auth:signup",
)
async def signup(
    user_create: UserCreate,
    request: Request,
    response: Response,
    user_manager: UserManagerDep,
    strategy: Annotated[DatabaseStrategy, Depends(get_database_strategy)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SignupResponse:
    try:
        user = await user_manager.create(user_create, safe=True, request=request)
    except InvalidPasswordException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "REGISTER_INVALID_PASSWORD", "reason": exc.reason},
        ) from exc
    except UserAlreadyExists as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="REGISTER_USER_ALREADY_EXISTS",
        ) from exc

    loaded = await load_membership_with_org(session, user.id)
    if loaded is None:  # unreachable: signup just created it
        raise HTTPException(status_code=500, detail="SIGNUP_MEMBERSHIP_MISSING")
    membership, org = loaded

    # Signup is immediately active (spec §10): hand back a session cookie too.
    token = await strategy.write_token(user)
    set_session_cookie(response, token)

    return SignupResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        is_verified=user.is_verified,
        org=OrgOut(id=org.id, name=org.name, slug=org.slug),
        role=membership.role.value,
    )


@api_router.get("/me", response_model=MeResponse, name="api:me")
async def me(ctx: TenantContextDep) -> MeResponse:
    return MeResponse(
        id=ctx.user.id,
        email=ctx.user.email,
        org=OrgOut(id=ctx.org.id, name=ctx.org.name, slug=ctx.org.slug),
        role=ctx.membership.role.value,
    )


# --------------------------------------------------------------------------
# Ticket 11 — upload → parse → Candidate in the Talent Pool (spec §7.2–7.3)
# --------------------------------------------------------------------------


class JobOut(BaseModel):
    id: UUID
    status: str
    reason: str | None
    attempts: int
    model: str | None
    prompt_version: str | None
    schema_version: int | None


class CandidateSummary(BaseModel):
    id: UUID
    full_name: str
    headline: str | None
    email: str | None
    created_at: datetime
    new_resume_received: bool = False


class ResumeOut(BaseModel):
    id: UUID
    filename: str
    parse_status: str
    parse_reason: str | None
    uploaded_at: datetime


class CandidateDetail(CandidateSummary):
    phone: str | None
    location: str | None
    profile: dict | None
    resume: ResumeOut | None


class CandidateList(BaseModel):
    items: list[CandidateSummary]


class UploadOutcome(BaseModel):
    duplicate: bool
    job: JobOut | None
    candidate: CandidateSummary | None


_MIME_BY_KIND = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
}


def _job_out(job: ParseJob) -> JobOut:
    return JobOut(
        id=job.id,
        status=job.status.value,
        reason=job.reason,
        attempts=job.attempts,
        model=job.model,
        prompt_version=job.prompt_version,
        schema_version=job.schema_version,
    )


async def _latest_job(session: AsyncSession, resume_file_id: UUID) -> ParseJob | None:
    return (
        await session.execute(
            select(ParseJob)
            .where(ParseJob.resume_file_id == resume_file_id)
            .order_by(ParseJob.created_at.desc(), ParseJob.id.desc())
            .limit(1)
        )
    ).scalar()


def _summary(candidate: Candidate) -> CandidateSummary:
    return CandidateSummary(
        id=candidate.id,
        full_name=candidate.full_name,
        headline=candidate.headline,
        email=candidate.email,
        created_at=candidate.created_at,
        new_resume_received=candidate.new_resume_received,
    )


@api_router.post(
    "/candidates/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=UploadOutcome,
    name="api:candidates:upload",
)
async def upload_resume(
    ctx: TenantContextDep,
    file: UploadFile,
    session: Annotated[AsyncSession, Depends(get_session)],
    extractor: Annotated[ResumeExtractor, Depends(get_extractor)],
) -> UploadOutcome:
    """GUI upload — the sync path for sub-minute UX on single uploads (spec §7.2).

    The job runs inline inside this request's transaction; every path ends in
    an explicit terminal status the response reports. If the model call reaches
    a terminal ``failed`` state, a later upload of the same bytes retries that
    stored ResumeFile instead of creating a duplicate Candidate. Interrupted
    requests that roll back still leave the user holding the original file.
    """
    data = await file.read(settings.resume_max_bytes + 1)
    if not data:
        raise HTTPException(status_code=400, detail="EMPTY_FILE")
    if len(data) > settings.resume_max_bytes:
        raise HTTPException(status_code=413, detail="FILE_TOO_LARGE")

    sha256 = hashlib.sha256(data).hexdigest()
    try:
        mime = _MIME_BY_KIND[sniff_kind(data, file.filename or "")]
    except Exception:  # noqa: BLE001 — unsupported formats ride the pipeline
        mime = "application/octet-stream"  # to an explicit needs_review

    duplicate: ResumeFile | None = (
        await session.execute(
            select(ResumeFile).where(
                ResumeFile.org_id == ctx.org.id, ResumeFile.sha256 == sha256
            )
        )
    ).scalar_one_or_none()

    resume: ResumeFile | None = None
    if duplicate is None:
        # Race-free dedupe: two concurrent uploads of the same file both pass
        # the SELECT above — the unique index decides, and the loser sees no
        # row returned and takes the duplicate path (spec §7.3).
        inserted_id = (
            await session.execute(
                pg_insert(ResumeFile)
                .values(
                    org_id=ctx.org.id,
                    original_filename=file.filename or "resume",
                    mime_type=mime,
                    sha256=sha256,
                    bytes=data,
                )
                .on_conflict_do_nothing(index_elements=["org_id", "sha256"])
                .returning(ResumeFile.id)
            )
        ).scalar()
        if inserted_id is not None:
            resume = await session.get(ResumeFile, inserted_id)
        else:  # lost the insert race
            duplicate = (
                await session.execute(
                    select(ResumeFile).where(
                        ResumeFile.org_id == ctx.org.id, ResumeFile.sha256 == sha256
                    )
                )
            ).scalar_one()

    if duplicate is not None:
        # A failed inline request may have committed the uploaded bytes before
        # the model call failed. Let the user upload the same file again and
        # retry that existing ResumeFile, without ever creating a duplicate
        # Candidate or ResumeFile.
        job = await _latest_job(session, duplicate.id)
        retryable_ai_error = bool(
            job
            and job.status == ParseJobStatus.NEEDS_REVIEW
            and (
                job.reason == "vision_unavailable"
                or (job.reason or "").startswith("api_error:")
            )
        )
        if job is not None and (
            (job.status == ParseJobStatus.FAILED and "inbound:" not in (job.reason or ""))
            or retryable_ai_error
        ):
            retry_job = ParseJob(org_id=ctx.org.id, resume_file_id=duplicate.id)
            session.add(retry_job)
            await session.flush()
            await process_parse_job(
                session,
                retry_job,
                duplicate,
                extractor=extractor,
                actor_user_id=ctx.user.id,
            )
            candidate = (
                await session.get(Candidate, duplicate.candidate_id)
                if duplicate.candidate_id is not None
                else None
            )
            await session.commit()
            return UploadOutcome(
                duplicate=False,
                job=_job_out(retry_job),
                candidate=_summary(candidate) if candidate is not None else None,
            )

        # Identical file: SHA-256 dedupe — the earlier terminal judgment
        # stands; never a duplicate Candidate (spec §7.3).
        candidate = (
            await session.get(Candidate, duplicate.candidate_id)
            if duplicate.candidate_id is not None
            else None
        )
        return UploadOutcome(
            duplicate=True,
            job=_job_out(job) if job is not None else None,
            candidate=_summary(candidate) if candidate is not None else None,
        )

    assert resume is not None  # inserted above, or the duplicate path returned

    job = ParseJob(org_id=ctx.org.id, resume_file_id=resume.id)
    session.add(job)
    await session.flush()

    await process_parse_job(
        session, job, resume, extractor=extractor, actor_user_id=ctx.user.id
    )
    # Read within the request transaction: the tenant GUC is transaction-local
    # and the RLS policy would hide the row after commit.
    candidate = (
        await session.get(Candidate, resume.candidate_id)
        if resume.candidate_id is not None
        else None
    )
    summary = _summary(candidate) if candidate is not None else None
    await session.commit()

    return UploadOutcome(
        duplicate=False,
        job=_job_out(job),
        candidate=summary,
    )


@api_router.get("/candidates", response_model=CandidateList, name="api:candidates:list")
async def list_candidates(
    ctx: TenantContextDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CandidateList:
    candidates = (
        (
            await session.execute(
                select(Candidate)
                .where(Candidate.org_id == ctx.org.id)
                .order_by(Candidate.created_at.desc(), Candidate.id.desc())
            )
        )
        .scalars()
        .all()
    )
    return CandidateList(items=[_summary(candidate) for candidate in candidates])


@api_router.get(
    "/candidates/{candidate_id}",
    response_model=CandidateDetail,
    name="api:candidates:detail",
)
async def get_candidate(
    candidate_id: UUID,
    ctx: TenantContextDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CandidateDetail:
    candidate = (
        await session.execute(
            select(Candidate).where(
                Candidate.id == candidate_id, Candidate.org_id == ctx.org.id
            )
        )
    ).scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="CANDIDATE_NOT_FOUND")

    resume = (
        await session.execute(
            select(ResumeFile)
            .where(ResumeFile.candidate_id == candidate.id)
            .order_by(ResumeFile.created_at.desc(), ResumeFile.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    resume_out: ResumeOut | None = None
    if resume is not None:
        job = await _latest_job(session, resume.id)
        resume_out = ResumeOut(
            id=resume.id,
            filename=resume.original_filename,
            parse_status=job.status.value if job is not None else "pending",
            parse_reason=job.reason if job is not None else None,
            uploaded_at=resume.created_at,
        )

    return CandidateDetail(
        **_summary(candidate).model_dump(),
        phone=candidate.phone,
        location=candidate.location,
        profile=candidate.profile,
        resume=resume_out,
    )


# Login/logout come straight from the library, wired to our cookie backend.
auth_router.include_router(fastapi_users.get_auth_router(auth_backend))
