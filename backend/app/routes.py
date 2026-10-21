"""API routes: signup (ours), login/logout (fastapi-users), /api/me."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi_users import InvalidPasswordException
from fastapi_users.authentication.strategy.db import DatabaseStrategy
from fastapi_users.exceptions import UserAlreadyExists
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Membership, Org
from app.tenancy import TenantContextDep
from app.users import (
    COOKIE_NAME,
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
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=settings.session_lifetime_seconds,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


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

    membership, org = (
        await session.execute(
            select(Membership, Org)
            .join(Org, Membership.org_id == Org.id)
            .where(Membership.user_id == user.id)
        )
    ).one()

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


# Login/logout come straight from the library, wired to our cookie backend.
auth_router.include_router(fastapi_users.get_auth_router(auth_backend))
