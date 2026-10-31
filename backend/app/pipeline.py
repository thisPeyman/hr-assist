"""Human-controlled Role and Application workflow. No automatic stage moves."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select

from app.models import (
    ApplicationActivity,
    Candidate,
    CandidateApplication,
    Membership,
    OrgActivity,
    PipelineStage,
    Role,
    User,
)
from app.pipeline_defaults import ENDING_KINDS
from app.profiles import lock_org
from app.resumes import SessionDep
from app.tenancy import TenantContextDep

router = APIRouter(prefix="/api", tags=["pipeline"])


class RoleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    owner_id: UUID | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError("empty title")
        return value.strip()


class RoleEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["draft", "open"] | None = None
    owner_id: UUID | None = None


async def owner_for(session, org_id, owner_id):
    if owner_id is not None and not await session.scalar(
        select(User.id)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.org_id == org_id, User.id == owner_id, User.is_active.is_(True))
    ):
        raise HTTPException(422, "INVALID_OWNER")


async def role_for(session, org_id, role_id):
    role = await session.scalar(select(Role).where(Role.org_id == org_id, Role.id == role_id))
    if role is None:
        raise HTTPException(404, "ROLE_NOT_FOUND")
    return role


def role_data(role):
    return {"id": role.id, "title": role.title, "status": role.status, "owner_id": role.owner_id}


async def stages_for(session, org_id):
    return [
        {"id": s.id, "name": s.name, "kind": s.kind, "position": s.position}
        for s in (
            await session.scalars(
                select(PipelineStage)
                .where(PipelineStage.org_id == org_id)
                .order_by(PipelineStage.position, PipelineStage.id)
            )
        ).all()
    ]


@router.get("/pipeline/stages")
async def stages(ctx: TenantContextDep, session: SessionDep) -> dict:
    return {"items": await stages_for(session, ctx.org.id)}


@router.get("/pipeline/owners")
async def owners(ctx: TenantContextDep, session: SessionDep) -> dict:
    users = (
        await session.scalars(
            select(User)
            .join(Membership)
            .where(Membership.org_id == ctx.org.id)
            .order_by(User.email)
        )
    ).all()
    return {"items": [{"id": u.id, "email": u.email, "active": u.is_active} for u in users]}


@router.get("/roles")
async def roles(ctx: TenantContextDep, session: SessionDep) -> dict:
    return {
        "items": [
            role_data(r)
            for r in (
                await session.scalars(
                    select(Role)
                    .where(Role.org_id == ctx.org.id)
                    .order_by(Role.created_at.desc(), Role.id)
                )
            ).all()
        ]
    }


@router.post("/roles", status_code=201)
async def create_role(data: RoleInput, ctx: TenantContextDep, session: SessionDep) -> dict:
    await lock_org(session, ctx.org.id)
    await owner_for(session, ctx.org.id, data.owner_id)
    role = Role(org_id=ctx.org.id, title=data.title, owner_id=data.owner_id, status="draft")
    session.add(role)
    await session.flush()
    session.add(
        OrgActivity(
            org_id=ctx.org.id,
            actor_user_id=ctx.user.id,
            event_type="role_created",
            data={"role_id": str(role.id)},
        )
    )
    result = role_data(role)
    await session.commit()
    return result


@router.patch("/roles/{role_id}")
async def edit_role(
    role_id: UUID, data: RoleEdit, ctx: TenantContextDep, session: SessionDep
) -> dict:
    await lock_org(session, ctx.org.id)
    role = await role_for(session, ctx.org.id, role_id)
    changes = data.model_dump(exclude_unset=True)
    if "owner_id" in changes:
        await owner_for(session, ctx.org.id, data.owner_id)
    if "title" in changes and not (data.title or "").strip():
        raise HTTPException(422, "ROLE_TITLE_REQUIRED")
    if "status" in changes and (
        data.status is None
        or (role.status != data.status and (role.status, data.status) != ("draft", "open"))
    ):
        raise HTTPException(409, "INVALID_ROLE_TRANSITION")
    for key, value in changes.items():
        setattr(role, key, value.strip() if key == "title" else value)
    session.add(
        OrgActivity(
            org_id=ctx.org.id,
            actor_user_id=ctx.user.id,
            event_type="role_updated",
            data={
                "role_id": str(role.id),
                "changes": {k: str(v) if isinstance(v, UUID) else v for k, v in changes.items()},
            },
        )
    )
    result = role_data(role)
    await session.commit()
    return result


@router.get("/pipeline/board")
async def board(ctx: TenantContextDep, session: SessionDep) -> dict:
    return {
        "stages": await stages_for(session, ctx.org.id),
        "roles": (await roles(ctx, session))["items"],
        "applications": await application_rows(session, ctx.org.id),
    }


class AddApplication(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: UUID
    owner_id: UUID | None = None


class StageMove(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage_id: UUID
    expected_stage_id: UUID
    context: str | None = Field(default=None, max_length=4000)
    reason: Literal["experience", "skills", "expectations", "timing", "other"] | None = None


class OwnerEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_id: UUID | None


def application_data(application):
    return {
        "id": application.id,
        "candidate_id": application.candidate_id,
        "role_id": application.role_id,
        "stage_id": application.stage_id,
        "owner_id": application.owner_id,
    }


def application_event(session, application, event, actor=None, **data):
    session.add(
        ApplicationActivity(
            org_id=application.org_id,
            application_id=application.id,
            actor_user_id=actor,
            event_type=event,
            data=data,
        )
    )


async def application_for(session, org_id, application_id):
    application = await session.scalar(
        select(CandidateApplication).where(
            CandidateApplication.org_id == org_id, CandidateApplication.id == application_id
        )
    )
    if application is None:
        raise HTTPException(404, "APPLICATION_NOT_FOUND")
    return application


async def stage_for(session, org_id, stage_id):
    stage = await session.scalar(
        select(PipelineStage).where(PipelineStage.org_id == org_id, PipelineStage.id == stage_id)
    )
    if stage is None:
        raise HTTPException(404, "STAGE_NOT_FOUND")
    return stage


async def application_rows(session, org_id, candidate_id=None):
    query = (
        select(CandidateApplication, Candidate, Role, PipelineStage)
        .join(Candidate, CandidateApplication.candidate_id == Candidate.id)
        .join(Role, CandidateApplication.role_id == Role.id)
        .join(PipelineStage, CandidateApplication.stage_id == PipelineStage.id)
        .where(
            CandidateApplication.org_id == org_id,
            Candidate.org_id == org_id,
            Role.org_id == org_id,
            PipelineStage.org_id == org_id,
        )
    )
    if candidate_id is not None:
        query = query.where(CandidateApplication.candidate_id == candidate_id)
    rows = (
        await session.execute(
            query.order_by(CandidateApplication.created_at, CandidateApplication.id)
        )
    ).all()
    return [
        {
            **application_data(a),
            "full_name": c.full_name,
            "headline": c.headline
            or next(
                (
                    job.get("title")
                    for job in ((c.profile or {}).get("work_experience") or [])
                    if job.get("current") and job.get("title")
                ),
                None,
            ),
            "role_title": r.title,
            "stage": s.name,
            "stage_kind": s.kind,
        }
        for a, c, r, s in rows
    ]


@router.post("/roles/{role_id}/applications")
async def add_application(
    role_id: UUID, data: AddApplication, ctx: TenantContextDep, session: SessionDep
) -> dict:
    # Same lock as identity Merge: an add cannot race a candidate's deletion/coalescing.
    await lock_org(session, ctx.org.id)
    role = await role_for(session, ctx.org.id, role_id)
    if role.status != "open":
        raise HTTPException(409, "ROLE_NOT_OPEN")
    if not await session.scalar(
        select(Candidate.id).where(
            Candidate.id == data.candidate_id, Candidate.org_id == ctx.org.id
        )
    ):
        raise HTTPException(404, "CANDIDATE_NOT_FOUND")
    await owner_for(session, ctx.org.id, data.owner_id)
    application = await session.scalar(
        select(CandidateApplication).where(
            CandidateApplication.org_id == ctx.org.id,
            CandidateApplication.candidate_id == data.candidate_id,
            CandidateApplication.role_id == role.id,
        )
    )
    sourced = await session.scalar(
        select(PipelineStage).where(
            PipelineStage.org_id == ctx.org.id, PipelineStage.kind == "sourced"
        )
    )
    if application is None:
        application = CandidateApplication(
            org_id=ctx.org.id,
            candidate_id=data.candidate_id,
            role_id=role.id,
            role_title=role.title,
            stage_id=sourced.id,
            stage=sourced.kind,
            owner_id=data.owner_id,
            data={},
        )
        session.add(application)
        await session.flush()
        application_event(
            session, application, "application_added", ctx.user.id, stage_id=str(sourced.id)
        )
    else:
        current = await stage_for(session, ctx.org.id, application.stage_id)
        if current.kind in ENDING_KINDS:
            old_stage = application.stage_id
            application.stage_id, application.stage = sourced.id, sourced.kind
            application_event(
                session,
                application,
                "application_reopened",
                ctx.user.id,
                from_stage_id=str(old_stage),
                to_stage_id=str(sourced.id),
            )
    result = application_data(application)
    await session.commit()
    return result


@router.get("/applications/{application_id}")
async def application_detail(
    application_id: UUID, ctx: TenantContextDep, session: SessionDep
) -> dict:
    application = await application_for(session, ctx.org.id, application_id)
    events = (
        await session.scalars(
            select(ApplicationActivity)
            .where(
                ApplicationActivity.org_id == ctx.org.id,
                ApplicationActivity.application_id == application.id,
            )
            .order_by(ApplicationActivity.created_at, ApplicationActivity.id)
        )
    ).all()
    return {
        **application_data(application),
        "activity": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "actor_user_id": e.actor_user_id,
                "data": e.data,
                "created_at": e.created_at,
            }
            for e in events
        ],
    }


@router.post("/applications/{application_id}/stage")
async def move_application(
    application_id: UUID, data: StageMove, ctx: TenantContextDep, session: SessionDep
) -> dict:
    await lock_org(session, ctx.org.id)
    application = await application_for(session, ctx.org.id, application_id)
    destination = await stage_for(session, ctx.org.id, data.stage_id)
    if application.stage_id != data.expected_stage_id:
        raise HTTPException(409, "APPLICATION_CHANGED_REFRESH")
    if data.reason is not None and destination.kind != "rejected":
        raise HTTPException(422, "REASON_ONLY_FOR_REJECTION")
    if application.stage_id != destination.id:
        previous = await stage_for(session, ctx.org.id, application.stage_id)
        application.stage_id, application.stage = destination.id, destination.kind
        application_event(
            session,
            application,
            "stage_changed",
            ctx.user.id,
            from_stage_id=str(previous.id),
            to_stage_id=str(destination.id),
            from_stage_name=previous.name,
            to_stage_name=destination.name,
            context=(data.context or "").strip() or None,
            reason=data.reason,
        )
    result = application_data(application)
    await session.commit()
    return result


@router.patch("/applications/{application_id}/owner")
async def assign_application(
    application_id: UUID, data: OwnerEdit, ctx: TenantContextDep, session: SessionDep
) -> dict:
    await lock_org(session, ctx.org.id)
    application = await application_for(session, ctx.org.id, application_id)
    await owner_for(session, ctx.org.id, data.owner_id)
    if application.owner_id != data.owner_id:
        previous = application.owner_id
        application.owner_id = data.owner_id
        application_event(
            session,
            application,
            "owner_changed",
            ctx.user.id,
            from_owner_id=str(previous) if previous else None,
            to_owner_id=str(data.owner_id) if data.owner_id else None,
        )
    result = application_data(application)
    await session.commit()
    return result
