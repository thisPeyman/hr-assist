"""Tenant context: app-layer scoping + the Postgres RLS GUC, hand in hand.

Every authenticated request resolves the user's Org (via their Membership —
one Org per User in v1), then pins ``app.current_org_id`` for the lifetime of
the request transaction. Because the setting is transaction-local it can never
leak onto another pooled connection; because the RLS policy reads it, even a
query that forgets its ``WHERE org_id = ...`` cannot cross tenants.
"""

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Membership, Org, User
from app.rls import set_current_org
from app.users import CurrentUserDep


@dataclass
class TenantContext:
    user: User
    org: Org
    membership: Membership


async def load_membership_with_org(
    session: AsyncSession, user_id: uuid.UUID
) -> tuple[Membership, Org] | None:
    """The user's single (v1) membership, joined to its Org."""
    row = (
        await session.execute(
            select(Membership, Org)
            .join(Org, Membership.org_id == Org.id)
            .where(Membership.user_id == user_id)
        )
    ).first()
    return (row[0], row[1]) if row is not None else None


async def get_tenant_context(
    user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TenantContext:
    loaded = await load_membership_with_org(session, user.id)
    if loaded is None:
        # v1: every user has exactly one membership, created at signup.
        raise HTTPException(status_code=403, detail="NO_MEMBERSHIP")
    membership, org = loaded
    await set_current_org(session, membership.org_id)
    await session.execute(
        text("select set_config('app.current_user_id', :user_id, true)"),
        {"user_id": str(user.id)},
    )
    return TenantContext(user=user, org=org, membership=membership)


TenantContextDep = Annotated[TenantContext, Depends(get_tenant_context)]
