"""Engine + request-scoped session.

Handlers own their commits; ``get_session`` only closes. The RLS tenant GUC is
transaction-local (see ``app.tenancy``), so handlers must not commit in the
middle of tenant reads/writes — one request, one transaction.
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine = create_async_engine(settings.app_database_url, pool_pre_ping=True)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
