"""In-app only. Caller owns transaction; delivery never invokes a mail provider."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.models import CandidateNote, Membership, Notification, User
from app.resumes import SessionDep
from app.tenancy import TenantContextDep

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


async def notify(session, *, org_id, recipient_id, kind, dedupe_key, note_id=None):
    """Reusable idempotent delivery for trusted workflow callers (17/23/24).

    Stable workflow dedupe keys; no user-supplied URLs or content. Inactive owners
    receive no new delivery. Recipient references are also tenant-FK protected.
    """
    active = await session.scalar(
        select(User.id)
        .join(Membership)
        .where(Membership.org_id == org_id, User.id == recipient_id, User.is_active.is_(True))
    )
    if not active:
        return
    await session.execute(
        insert(Notification)
        .values(
            org_id=org_id,
            recipient_id=recipient_id,
            kind=kind,
            dedupe_key=dedupe_key,
            note_id=note_id,
        )
        .on_conflict_do_nothing(index_elements=["org_id", "recipient_id", "dedupe_key"])
    )


@router.get("")
async def inbox(ctx: TenantContextDep, session: SessionDep) -> dict:
    scope = (Notification.org_id == ctx.org.id, Notification.recipient_id == ctx.user.id)
    unread = await session.scalar(
        select(func.count()).select_from(Notification).where(*scope, Notification.read_at.is_(None))
    )
    rows = (
        await session.execute(
            select(Notification, CandidateNote)
            .outerjoin(
                CandidateNote,
                (CandidateNote.id == Notification.note_id)
                & (CandidateNote.org_id == Notification.org_id),
            )
            .where(*scope)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(100)
        )
    ).all()
    items = []
    for item, note in rows:
        href = None
        if note:
            href = f"/candidates/{note.candidate_id}?tab=notes&note={note.id}"
            if note.application_id:
                href += f"&application={note.application_id}"
        items.append(
            {
                "id": item.id,
                "kind": item.kind,
                "created_at": item.created_at,
                "read_at": item.read_at,
                "href": href,
            }
        )
    return {"items": items, "unread_count": unread}


class ReadState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    read: bool


@router.patch("/{notification_id}")
async def read_state(
    notification_id: UUID, data: ReadState, ctx: TenantContextDep, session: SessionDep
) -> dict:
    item = await session.scalar(
        select(Notification)
        .where(
            Notification.id == notification_id,
            Notification.org_id == ctx.org.id,
            Notification.recipient_id == ctx.user.id,
        )
        .with_for_update()
    )
    if item is None:
        raise HTTPException(404, "NOTIFICATION_NOT_FOUND")
    item.read_at = (item.read_at or datetime.now(UTC)) if data.read else None
    result = {"id": item.id, "read_at": item.read_at}
    await session.commit()
    return result
