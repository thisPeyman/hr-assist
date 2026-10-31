"""One editable Note store for Candidate and Application collaboration."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select

from app.models import Candidate, CandidateNote, Membership, NoteMention, User
from app.notifications import notify
from app.pipeline import application_event, application_for
from app.profiles import activity, lock_org
from app.resumes import SessionDep
from app.tenancy import TenantContextDep

router = APIRouter(prefix="/api", tags=["notes"])


class NoteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=10000)
    mention_user_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("body")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("EMPTY_NOTE")
        return value.strip()


async def note_rows(session, org_id, candidate_id, application_id=None):
    query = select(CandidateNote).where(
        CandidateNote.org_id == org_id, CandidateNote.candidate_id == candidate_id
    )
    if application_id is not None:
        query = query.where(CandidateNote.application_id == application_id)
    notes = (
        await session.scalars(
            query.order_by(CandidateNote.created_at.desc(), CandidateNote.id.desc())
        )
    ).all()
    if not notes:
        return []
    mentions = (
        await session.execute(
            select(NoteMention.note_id, User)
            .join(User, User.id == NoteMention.user_id)
            .where(NoteMention.org_id == org_id, NoteMention.note_id.in_([n.id for n in notes]))
        )
    ).all()
    users = {
        u.id: u
        for u in (
            await session.scalars(select(User).join(Membership).where(Membership.org_id == org_id))
        ).all()
    }

    def person(user_id):
        user = users.get(user_id)
        return {
            "id": user_id,
            "email": user.email if user else None,
            "active": user.is_active if user else False,
        }

    return [
        {
            "id": n.id,
            "candidate_id": n.candidate_id,
            "application_id": n.application_id,
            "body": n.body,
            "created_at": n.created_at,
            "edited_at": n.edited_at,
            "author": person(n.author_id),
            "editor": person(n.editor_id) if n.editor_id else None,
            "mention_user_ids": sorted([u.id for key, u in mentions if key == n.id]),
            "mentions": [person(u.id) for key, u in mentions if key == n.id],
        }
        for n in notes
    ]


async def save_note(session, ctx, candidate, data, *, application=None, note=None):
    recipients = set(data.mention_user_ids)
    active = set(
        (
            await session.scalars(
                select(User.id)
                .join(Membership)
                .where(
                    Membership.org_id == ctx.org.id,
                    User.id.in_(recipients | {ctx.user.id}),
                    User.is_active.is_(True),
                )
            )
        ).all()
    )
    if ctx.user.id not in active:
        raise HTTPException(403, "INACTIVE_NOTE_AUTHOR")
    old = set()
    if note:
        old = set(
            (
                await session.scalars(
                    select(NoteMention.user_id).where(
                        NoteMention.org_id == ctx.org.id, NoteMention.note_id == note.id
                    )
                )
            ).all()
        )
    # Existing inactive mentions may be retained as attribution, but never newly selected.
    if recipients - old - active:
        raise HTTPException(422, "INVALID_MENTION")
    if note is None:
        note = CandidateNote(
            org_id=ctx.org.id,
            candidate_id=candidate.id,
            application_id=application.id if application else None,
            author_id=ctx.user.id,
            body=data.body,
        )
        session.add(note)
        event = "note_added"
    else:
        if note.body == data.body and old == recipients:
            return note
        note.body, note.edited_at, note.editor_id = data.body, datetime.now(UTC), ctx.user.id
        event = "note_edited"
    await session.flush()
    await session.execute(
        delete(NoteMention).where(
            NoteMention.org_id == ctx.org.id,
            NoteMention.note_id == note.id,
            NoteMention.user_id.in_(old - recipients),
        )
    )
    for user_id in recipients - old:
        session.add(NoteMention(org_id=ctx.org.id, note_id=note.id, user_id=user_id))
        await notify(
            session,
            org_id=ctx.org.id,
            recipient_id=user_id,
            kind="note_mention",
            dedupe_key=f"note_mention:{note.id}",
            note_id=note.id,
        )
    # No private body text in immutable Activity; editor/author live on Note.
    if application:
        application_event(session, application, event, ctx.user.id, note_id=str(note.id))
    else:
        activity(session, candidate, event, ctx.user.id, note_id=str(note.id))
    await session.flush()
    return note


async def candidate_for(session, org_id, candidate_id):
    candidate = await session.scalar(
        select(Candidate).where(Candidate.org_id == org_id, Candidate.id == candidate_id)
    )
    if candidate is None:
        raise HTTPException(404, "CANDIDATE_NOT_FOUND")
    return candidate


async def result_for(session, org_id, note):
    return next(
        n for n in await note_rows(session, org_id, note.candidate_id) if n["id"] == note.id
    )


@router.get("/notes/mention-users")
async def mention_users(ctx: TenantContextDep, session: SessionDep) -> dict:
    users = (
        await session.scalars(
            select(User)
            .join(Membership)
            .where(Membership.org_id == ctx.org.id, User.is_active.is_(True))
            .order_by(User.email)
        )
    ).all()
    return {"items": [{"id": u.id, "email": u.email, "active": True} for u in users]}


@router.post("/candidates/{candidate_id}/notes", status_code=201)
async def add_candidate_note(
    candidate_id: UUID, data: NoteInput, ctx: TenantContextDep, session: SessionDep
) -> dict:
    await lock_org(session, ctx.org.id)
    candidate = await candidate_for(session, ctx.org.id, candidate_id)
    note = await save_note(session, ctx, candidate, data)
    result = await result_for(session, ctx.org.id, note)
    await session.commit()
    return result


@router.post("/applications/{application_id}/notes", status_code=201)
async def add_application_note(
    application_id: UUID, data: NoteInput, ctx: TenantContextDep, session: SessionDep
) -> dict:
    await lock_org(session, ctx.org.id)
    application = await application_for(session, ctx.org.id, application_id)
    candidate = await candidate_for(session, ctx.org.id, application.candidate_id)
    note = await save_note(session, ctx, candidate, data, application=application)
    result = await result_for(session, ctx.org.id, note)
    await session.commit()
    return result


@router.put("/notes/{note_id}")
async def edit_note(
    note_id: UUID, data: NoteInput, ctx: TenantContextDep, session: SessionDep
) -> dict:
    await lock_org(session, ctx.org.id)
    note = await session.scalar(
        select(CandidateNote).where(CandidateNote.org_id == ctx.org.id, CandidateNote.id == note_id)
    )
    if note is None:
        raise HTTPException(404, "NOTE_NOT_FOUND")
    candidate = await candidate_for(session, ctx.org.id, note.candidate_id)
    application = (
        await application_for(session, ctx.org.id, note.application_id)
        if note.application_id
        else None
    )
    await save_note(session, ctx, candidate, data, application=application, note=note)
    result = await result_for(session, ctx.org.id, note)
    await session.commit()
    return result
