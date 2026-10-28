"""Canonical candidate profile, human decisions, merge, and cached summary API."""

import copy
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import defer

from app.models import (
    Candidate,
    CandidateActivity,
    CandidateApplication,
    CandidateNote,
    ProfileChange,
    ResumeFile,
    ResumeSummary,
)
from app.parsing.llm import get_extractor
from app.parsing.schema import ResumeExtractionData, build_profile
from app.profiles import (
    activity,
    fields,
    lock_org,
    merge_candidates,
    put,
    similar_candidates,
    sync_candidate,
)
from app.resumes import SessionDep
from app.summaries import ensure_summary
from app.tenancy import TenantContextDep

router = APIRouter(prefix="/api/candidates", tags=["candidate profiles"])


async def candidate_for(session, org_id, candidate_id):
    candidate = (
        await session.execute(
            select(Candidate).where(Candidate.id == candidate_id, Candidate.org_id == org_id)
        )
    ).scalar_one_or_none()
    if candidate is None:
        raise HTTPException(404, "CANDIDATE_NOT_FOUND")
    return candidate


@router.get("/{candidate_id}/workspace")
async def workspace(candidate_id: UUID, ctx: TenantContextDep, session: SessionDep) -> dict:
    candidate = await candidate_for(session, ctx.org.id, candidate_id)
    resume = (
        await session.execute(
            select(ResumeFile)
            .options(defer(ResumeFile.bytes))
            .where(ResumeFile.candidate_id == candidate.id)
            .order_by(ResumeFile.created_at.desc(), ResumeFile.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    summary = (
        await session.execute(
            select(ResumeSummary).where(
                ResumeSummary.candidate_id == candidate.id,
                ResumeSummary.resume_version == candidate.latest_resume_version,
            )
        )
    ).scalar_one_or_none()
    changes = (
        (
            await session.execute(
                select(ProfileChange)
                .where(
                    ProfileChange.candidate_id == candidate.id, ProfileChange.status == "pending"
                )
                .order_by(ProfileChange.created_at)
            )
        )
        .scalars()
        .all()
    )
    events = (
        (
            await session.execute(
                select(CandidateActivity)
                .where(CandidateActivity.candidate_id == candidate.id)
                .order_by(CandidateActivity.created_at.desc(), CandidateActivity.id.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    notes = (
        (
            await session.execute(
                select(CandidateNote)
                .where(CandidateNote.candidate_id == candidate.id)
                .order_by(CandidateNote.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    applications = (
        (
            await session.execute(
                select(CandidateApplication)
                .where(CandidateApplication.candidate_id == candidate.id)
                .order_by(CandidateApplication.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "id": candidate.id,
        "full_name": candidate.full_name,
        "new_resume_received": candidate.new_resume_received,
        "profile": candidate.profile,
        "resume_id": resume.id if resume else None,
        "resume_version": candidate.latest_resume_version,
        "summary": {
            "status": summary.status,
            "content": summary.content,
            "error": summary.error,
            "generated_at": summary.generated_at,
            "model": summary.model,
            "prompt_version": summary.prompt_version,
        }
        if summary
        else None,
        "changes": [
            {
                "id": change.id,
                "field_path": change.field_path,
                "old_value": change.old_value,
                "new_value": change.new_value,
                "resume_version": change.resume_version,
            }
            for change in changes
        ],
        "duplicates": await similar_candidates(session, candidate),
        "activity": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "data": event.data,
                "created_at": event.created_at,
            }
            for event in events
        ],
        "notes": [
            {"id": note.id, "body": note.body, "created_at": note.created_at} for note in notes
        ],
        "applications": [
            {"id": application.id, "role_title": application.role_title, "stage": application.stage}
            for application in applications
        ],
    }


class ProfileEdit(BaseModel):
    profile: dict


@router.put("/{candidate_id}/profile")
async def edit_profile(
    candidate_id: UUID, data: ProfileEdit, ctx: TenantContextDep, session: SessionDep
) -> dict:
    await lock_org(session, ctx.org.id)
    candidate = await candidate_for(session, ctx.org.id, candidate_id)
    try:
        payload = copy.deepcopy(data.profile)
        for field in ("skills", "industries"):
            if isinstance(payload.get(field), list):
                payload[field] = [
                    value.strip()
                    for value in payload[field]
                    if isinstance(value, str) and value.strip()
                ]
        jobs = payload.get("work_experience")
        for job in jobs if isinstance(jobs, list) else []:
            if isinstance(job, dict) and isinstance(job.get("bullets"), list):
                job["bullets"] = [
                    value for value in job["bullets"] if isinstance(value, str) and value.strip()
                ]
        extraction = ResumeExtractionData.model_validate(
            {**payload, "is_resume": True, "confidence": 1, "needs_review": False}
        )
    except ValidationError as exc:
        raise HTTPException(422, "INVALID_PROFILE") from exc
    if not (extraction.contact.full_name or "").strip():
        raise HTTPException(422, "PROFILE_NAME_REQUIRED")
    profile = build_profile(extraction)
    before = fields(candidate.profile)
    changed = {
        path: {"old": before.get(path), "new": value}
        for path, value in fields(profile).items()
        if value != before.get(path)
    }
    candidate.profile = profile
    candidate.new_resume_received = False
    candidate.human_fields = sorted(set(candidate.human_fields or []) | set(changed))
    sync_candidate(candidate)
    activity(session, candidate, "profile_edited", ctx.user.id, changes=changed)
    await session.commit()
    return {"id": candidate.id}


class ChangeDecision(BaseModel):
    action: Literal["accept", "reject"]


@router.post("/{candidate_id}/changes/{change_id}")
async def decide_change(
    candidate_id: UUID,
    change_id: UUID,
    data: ChangeDecision,
    ctx: TenantContextDep,
    session: SessionDep,
) -> dict:
    await lock_org(session, ctx.org.id)
    candidate = await candidate_for(session, ctx.org.id, candidate_id)
    change = (
        await session.execute(
            select(ProfileChange).where(
                ProfileChange.id == change_id,
                ProfileChange.candidate_id == candidate.id,
                ProfileChange.org_id == ctx.org.id,
            )
        )
    ).scalar_one_or_none()
    if change is None:
        raise HTTPException(404, "CHANGE_NOT_FOUND")
    if change.status != "pending":
        raise HTTPException(409, "CHANGE_ALREADY_RESOLVED")
    if data.action == "accept":
        if fields(candidate.profile).get(change.field_path) != change.old_value:
            raise HTTPException(409, "PROFILE_CHANGED_REFRESH")
        profile = copy.deepcopy(candidate.profile or {})
        put(profile, change.field_path, change.new_value)
        candidate.profile = profile
        candidate.human_fields = sorted(set(candidate.human_fields or []) | {change.field_path})
        sync_candidate(candidate)
    change.status = "accepted" if data.action == "accept" else "rejected"
    activity(
        session,
        candidate,
        "profile_change_" + change.status,
        ctx.user.id,
        field=change.field_path,
        old=change.old_value,
        new=change.new_value,
        resume_version=change.resume_version,
    )
    await session.commit()
    return {"id": change.id, "status": change.status}


class MergeRequest(BaseModel):
    target_id: UUID


@router.post("/{candidate_id}/merge")
async def merge(
    candidate_id: UUID, data: MergeRequest, ctx: TenantContextDep, session: SessionDep
) -> dict:
    if data.target_id == candidate_id:
        raise HTTPException(422, "CANNOT_MERGE_SELF")
    await lock_org(session, ctx.org.id)
    source = await candidate_for(session, ctx.org.id, candidate_id)
    target = await candidate_for(session, ctx.org.id, data.target_id)
    await merge_candidates(session, target, source, ctx.user.id)
    target_id = target.id
    await session.commit()
    return {"candidate_id": target_id}


@router.post("/{candidate_id}/summary/regenerate")
async def regenerate(
    candidate_id: UUID,
    ctx: TenantContextDep,
    session: SessionDep,
    generator: Annotated[object, Depends(get_extractor)],
) -> dict:
    await lock_org(session, ctx.org.id)
    candidate = await candidate_for(session, ctx.org.id, candidate_id)
    if not candidate.latest_resume_version:
        raise HTTPException(409, "RESUME_VERSION_MISSING")
    row = await ensure_summary(
        session,
        candidate,
        candidate.latest_resume_version,
        candidate.profile or {},
        generator,
        force=True,
        actor=ctx.user.id,
    )
    await session.commit()
    return {"status": row.status, "error": row.error}


class NoteInput(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


@router.post("/{candidate_id}/acknowledge-resume")
async def acknowledge(candidate_id: UUID, ctx: TenantContextDep, session: SessionDep) -> dict:
    await lock_org(session, ctx.org.id)
    candidate = await candidate_for(session, ctx.org.id, candidate_id)
    candidate.new_resume_received = False
    activity(session, candidate, "new_resume_acknowledged", ctx.user.id)
    await session.commit()
    return {"id": candidate.id}


@router.post("/{candidate_id}/notes", status_code=201)
async def add_note(
    candidate_id: UUID, data: NoteInput, ctx: TenantContextDep, session: SessionDep
) -> dict:
    await lock_org(session, ctx.org.id)
    candidate = await candidate_for(session, ctx.org.id, candidate_id)
    if not data.body.strip():
        raise HTTPException(422, "EMPTY_NOTE")
    note = CandidateNote(
        org_id=ctx.org.id, candidate_id=candidate.id, author_id=ctx.user.id, body=data.body.strip()
    )
    session.add(note)
    activity(session, candidate, "note_added", ctx.user.id)
    await session.commit()
    return {"id": note.id}
