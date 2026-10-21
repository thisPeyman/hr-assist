"""Postgres RLS GUC mechanics.

``set_current_org`` pins the tenant for the current transaction so the
``org_activity_isolation`` policy (migration 0002) can scope every statement —
the database-level half of app-layer scoping + RLS belt-and-braces.
"""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ORG_GUC = "app.current_org_id"

_SET_GUC = text("select set_config('app.current_org_id', :v, true)")


async def set_current_org(session: AsyncSession, org_id: uuid.UUID) -> None:
    """Pin the tenant for the rest of the current transaction.

    ``is_local => true`` keeps the value alive only until the next COMMIT or
    ROLLBACK, so it can never leak onto another pooled connection.
    """
    await session.execute(_SET_GUC, {"v": str(org_id)})
