"""Test fixtures: fresh migrated database + app/httpx clients.

Environment is pinned at import time (before ``app`` loads its settings) so the
test session always targets the throwaway ``hr_test`` database. The privileged
URL defaults to the local peer-auth cluster; CI points ``HR_TEST_ADMIN_URL``
and ``HR_TEST_APP_URL`` at its postgres service container.
"""

import os
import uuid
from urllib.parse import urlsplit, urlunsplit

TEST_DB_NAME = "hr_test"

_ADMIN_BASE = os.environ.get(
    "HR_TEST_ADMIN_URL", "postgresql+asyncpg://peyman@/postgres?host=/var/run/postgresql"
)


def _with_db(url: str, dbname: str) -> str:
    """Swap the database name in a URL without touching its query string."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{dbname}", parts.query, parts.fragment))


TEST_SUPERUSER_URL = _with_db(_ADMIN_BASE, TEST_DB_NAME)
TEST_APP_URL = os.environ.get(
    "HR_TEST_APP_URL",
    f"postgresql+asyncpg://hr_app:hr_app_dev@127.0.0.1:5432/{TEST_DB_NAME}",
)

os.environ["HR_MIGRATION_DATABASE_URL"] = TEST_SUPERUSER_URL
os.environ["HR_APP_DATABASE_URL"] = TEST_APP_URL
os.environ["HR_APP_DB_PASSWORD"] = "hr_app_dev"
os.environ["HR_COOKIE_SECURE"] = "false"
os.environ["HR_RESUME_AI_PROVIDER"] = "openai"
os.environ["HR_OPENAI_API_KEY"] = ""
os.environ["HR_GROQ_API_KEY"] = ""

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.main import app as fastapi_app  # noqa: E402


@pytest.fixture(scope="session")
def migrated_db_url() -> str:
    """Create a fresh database and run all migrations against it."""
    import asyncio

    async def _prepare() -> None:
        admin = create_async_engine(_ADMIN_BASE, isolation_level="AUTOCOMMIT")
        async with admin.connect() as conn:
            await conn.execute(
                text(f"drop database if exists {TEST_DB_NAME} with (force)")
            )
            await conn.execute(text(f"create database {TEST_DB_NAME}"))
        await admin.dispose()

    asyncio.run(_prepare())

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    return TEST_SUPERUSER_URL


@pytest_asyncio.fixture
async def superuser_engine(migrated_db_url):
    engine = create_async_engine(migrated_db_url)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(superuser_engine):
    """Wipe app tables between tests so each test starts from a blank org set."""
    yield
    async with superuser_engine.begin() as conn:
        await conn.execute(
            text(
                "truncate table access_tokens, memberships, org_activity, orgs, users,"
                " resume_extractions, parse_jobs, resume_files,"
                " candidate_activity, candidates cascade"
            )
        )


@pytest_asyncio.fixture
async def app_engine():
    """Engine connected the way the app does: as the non-superuser ``hr_app``."""
    engine = create_async_engine(TEST_APP_URL)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def app_session_factory(app_engine):
    """Session factory bound to the hr_app engine (RLS-active)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    return async_sessionmaker(app_engine, expire_on_commit=False)


async def seed_org_with_admin(session_factory) -> tuple[str, str]:
    """A minimal (org_id, user_id) pair for pipeline/queue tests."""
    import uuid

    marker = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        from sqlalchemy import text

        user_id = (
            (
                await session.execute(
                    text(
                        "insert into users (email, hashed_password) "
                        "values (:e, 'x') returning id"
                    ),
                    {"e": f"hr-{marker}@example.com"},
                )
            ).scalar(),
        )[0]
        org_id = (
            (
                await session.execute(
                    text("insert into orgs (name, slug) values ('تست', :s) returning id"),
                    {"s": f"org-{marker}"},
                )
            ).scalar(),
        )[0]
        await session.execute(
            text(
                "insert into memberships (user_id, org_id, role) "
                "values (:u, :o, 'admin')"
            ),
            {"u": str(user_id), "o": str(org_id)},
        )
        await session.commit()
    return str(org_id), str(user_id)


@pytest_asyncio.fixture
async def api_client():
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def new_org_name() -> str:
    return f"شرکت آزمون {uuid.uuid4().hex[:8]}"
