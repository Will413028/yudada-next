import asyncio
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.models import LoginSession, User
from app.security import (
    COOKIE,
    DB,
    DUMMY_HASH,
    Actor,
    check_origin,
    csrf_token,
    digest,
    hasher,
    new_session,
    public_origin,
    throttle,
    verify_password,
)
from app.uploads import validate_uploads

router = APIRouter(prefix="/api/v1")


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=12, max_length=128)

    @field_validator("account")
    @classmethod
    def normalize(cls, value: str) -> str:
        return value.lower()


class Registration(Credentials):
    display_name: str = Field(min_length=1, max_length=80)


class Profile(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    account: str
    display_name: str
    role: str
    avatar_id: UUID | None


class Identity(BaseModel):
    user: Profile
    csrf_token: str


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=80)
    avatar_id: UUID | None = None


async def finish_login(user: User, session: DB, request: Request, response: Response) -> Identity:
    token = await new_session(session, user, request)
    response.set_cookie(
        COOKIE,
        token,
        max_age=86400,
        httponly=True,
        secure=public_origin().startswith("https://"),
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return Identity(user=Profile.model_validate(user), csrf_token=csrf_token(token))


@router.post("/auth/register", response_model=Identity, status_code=201)
async def register(
    body: Registration, request: Request, response: Response, session: DB
) -> Identity:
    check_origin(request)
    await throttle(session, request, body.account)
    user = User(
        account=body.account,
        display_name=body.display_name,
        password_hash=await asyncio.to_thread(hasher.hash, body.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(409, "Registration unavailable") from None
    return await finish_login(user, session, request, response)


@router.post("/auth/login", response_model=Identity)
async def login(body: Credentials, request: Request, response: Response, session: DB) -> Identity:
    check_origin(request)
    await throttle(session, request, body.account)
    user = await session.scalar(select(User).where(User.account == body.account))
    valid = await verify_password(user.password_hash if user else DUMMY_HASH, body.password)
    if not valid or user is None or not user.active:
        raise HTTPException(401, "Invalid account or password")
    return await finish_login(user, session, request, response)


@router.get("/auth/me", response_model=Identity)
async def identity(request: Request, response: Response, actor: Actor) -> Identity:
    response.headers["Cache-Control"] = "no-store"
    return Identity(
        user=Profile.model_validate(actor), csrf_token=csrf_token(request.cookies[COOKIE])
    )


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, response: Response, actor: Actor, session: DB) -> None:
    await session.execute(
        update(LoginSession)
        .where(LoginSession.token_hash == digest(request.cookies[COOKIE]))
        .values(revoked_at=datetime.now(UTC))
    )
    await session.commit()
    response.delete_cookie(COOKIE, path="/")


@router.get("/me", response_model=Profile)
async def profile(actor: Actor) -> Profile:
    return Profile.model_validate(actor)


@router.patch("/me", response_model=Profile)
async def edit_profile(body: ProfilePatch, actor: Actor, session: DB) -> Profile:
    if "avatar_id" in body.model_fields_set:
        if body.avatar_id is not None:
            await validate_uploads([(body.avatar_id, "avatar")], actor.id, actor, session)
        actor.avatar_id = body.avatar_id
    actor.display_name = body.display_name
    await session.commit()
    return Profile.model_validate(actor)
