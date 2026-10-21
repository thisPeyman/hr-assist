"""fastapi-users wiring: schemas, UserManager, cookie backend.

Auth is self-rolled *on* the library (spec §10): fastapi-users supplies the
argon2 PasswordHelper (pwdlib), the cookie transport, the database session
strategy, and the login/logout routers. We take over exactly one piece —
``UserManager.create`` — so signup creates Org + User + Membership + the
org_created Activity row as a single atomic transaction.
"""

import re
import secrets
import uuid
from typing import Annotated

from fastapi import Depends, Request
from fastapi_users import (
    BaseUserManager,
    FastAPIUsers,
    InvalidPasswordException,
    UUIDIDMixin,
    schemas,
)
from fastapi_users.authentication import AuthenticationBackend, CookieTransport
from fastapi_users.authentication.strategy.db import DatabaseStrategy
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.exceptions import UserAlreadyExists
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyAccessTokenDatabase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import AccessToken, Membership, MembershipRole, Org, OrgActivity, User
from app.rls import set_current_org

# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class UserRead(schemas.BaseUser[uuid.UUID]):
    pass


class UserCreate(schemas.BaseUserCreate):
    org_name: str


class UserUpdate(schemas.BaseUserUpdate):
    pass


# --------------------------------------------------------------------------
# UserManager
# --------------------------------------------------------------------------

_MIN_PASSWORD_LENGTH = 8


def org_slug_base(name: str) -> str:
    """ASCII slug for the org; Persian-only names fall back to ``org``.

    The slug feeds the org's future email-in address; transliteration of
    Persian names is deliberately left to ticket 18.
    """
    words = re.findall(r"[a-z0-9]+", name.lower())
    return "-".join(words)[:48] if words else "org"


async def unique_org_slug(session: AsyncSession, name: str) -> str:
    base = org_slug_base(name)
    slug = base
    while (
        await session.scalar(select(Org).where(Org.slug == slug)) is not None
    ):  # race window closed by the unique constraint; v1 accepts the 500 retry
        slug = f"{base}-{secrets.token_hex(3)}"
    return slug


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.reset_password_token_secret
    verification_token_secret = settings.verification_token_secret

    async def validate_password(self, password: str, user) -> None:
        if len(password) < _MIN_PASSWORD_LENGTH:
            raise InvalidPasswordException(
                reason="PASSWORD_TOO_SHORT",
            )

    async def create(
        self,
        user_create: schemas.UC,
        safe: bool = False,
        request: Request | None = None,
    ) -> User:
        await self.validate_password(user_create.password, user_create)

        existing = await self.user_db.get_by_email(user_create.email)
        if existing is not None:
            raise UserAlreadyExists()

        session: AsyncSession = self.user_db.session
        user = User(
            email=user_create.email,
            hashed_password=self.password_helper.hash(user_create.password),
            is_active=True,  # signup is immediately active (spec §10: no mailbox yet)
            is_verified=False,  # verification arrives with ticket 18
        )
        org = Org(
            name=user_create.org_name,
            slug=await unique_org_slug(session, user_create.org_name),
        )
        session.add_all([user, org])
        await session.flush()  # assign user.id / org.id for the FKs below

        session.add_all(
            [
                Membership(
                    user_id=user.id, org_id=org.id, role=MembershipRole.ADMIN
                ),
                OrgActivity(
                    org_id=org.id,
                    actor_user_id=user.id,
                    event_type="org_created",
                    data={"org_name": org.name},
                ),
            ]
        )
        # Tenant GUC first, so the org_activity INSERT passes its own RLS gate.
        await set_current_org(session, org.id)
        await session.commit()
        await session.refresh(user)

        await self.on_after_register(user, request)
        return user


async def get_user_db(
    session: Annotated[AsyncSession, Depends(get_session)],
):
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(
    user_db: Annotated[SQLAlchemyUserDatabase, Depends(get_user_db)],
):
    yield UserManager(user_db)


UserManagerDep = Annotated[UserManager, Depends(get_user_manager)]


# --------------------------------------------------------------------------
# Cookie session backend
# --------------------------------------------------------------------------

COOKIE_NAME = "hr_session"

cookie_transport = CookieTransport(
    cookie_name=COOKIE_NAME,
    cookie_max_age=settings.session_lifetime_seconds,
    cookie_secure=settings.cookie_secure,
    cookie_httponly=True,
    cookie_samesite="lax",
)


async def get_access_token_db(
    session: Annotated[AsyncSession, Depends(get_session)],
):
    yield SQLAlchemyAccessTokenDatabase(session, AccessToken)


async def get_database_strategy(
    token_db: Annotated[SQLAlchemyAccessTokenDatabase, Depends(get_access_token_db)],
) -> DatabaseStrategy:
    return DatabaseStrategy(token_db, lifetime_seconds=settings.session_lifetime_seconds)


auth_backend = AuthenticationBackend(
    name="session",
    transport=cookie_transport,
    get_strategy=get_database_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

CurrentUserDep = Annotated[User, Depends(fastapi_users.current_user(active=True))]
