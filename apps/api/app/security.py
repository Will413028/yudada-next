import asyncio
import hashlib
import hmac
import os
import secrets
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LoginBucket, LoginSession, User

hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
COOKIE = "yudada_session"
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_token(token: str) -> str:
    return digest("csrf:" + token)


def public_origin() -> str:
    origin = os.environ.get("PUBLIC_ORIGIN", "http://127.0.0.1:3300").rstrip("/")
    if os.environ.get("APP_ENV", "development") == "production" and not origin.startswith(
        "https://"
    ):
        raise RuntimeError("Production PUBLIC_ORIGIN must use HTTPS")
    return origin


def check_origin(request: Request) -> None:
    if request.headers.get("origin") != public_origin():
        raise HTTPException(403, "Invalid request origin")


async def database(request: Request) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(request.app.state.engine, expire_on_commit=False) as session:
        yield session


DB = Annotated[AsyncSession, Depends(database)]


async def verify_password(encoded: str, password: str) -> bool:
    def verify() -> bool:
        try:
            return hasher.verify(encoded, password)
        except (VerificationError, InvalidHashError):
            return False

    return await asyncio.to_thread(verify)


async def throttle(session: AsyncSession, request: Request, account: str) -> None:
    now = datetime.now(UTC)
    address = request.client.host if request.client else "unknown"
    for key, limit in [(digest("account:" + account), 10), (digest("ip:" + address), 100)]:
        statement = insert(LoginBucket).values(key=key, attempts=1, window_start=now)
        from sqlalchemy import case

        expired = LoginBucket.window_start < now - timedelta(minutes=1)
        upsert = statement.on_conflict_do_update(
            index_elements=[LoginBucket.key],
            set_={
                "attempts": case((expired, 1), else_=LoginBucket.attempts + 1),
                "window_start": case((expired, now), else_=LoginBucket.window_start),
            },
        ).returning(LoginBucket.attempts)
        count = await session.scalar(upsert)
        await session.commit()
        if count is not None and count > limit:
            raise HTTPException(429, "Too many attempts", headers={"Retry-After": "60"})


async def current_user(request: Request, session: DB) -> User:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Authentication required")
    now = datetime.now(UTC)
    # A conditional UPDATE makes idle expiry and session revocation authoritative in DB.
    user_id = await session.scalar(
        update(LoginSession)
        .where(
            LoginSession.token_hash == digest(token),
            LoginSession.revoked_at.is_(None),
            LoginSession.expires_at > now,
            LoginSession.last_seen_at > now - timedelta(minutes=30),
        )
        .values(last_seen_at=now)
        .returning(LoginSession.user_id)
    )
    await session.commit()
    user = await session.get(User, user_id) if user_id else None
    if user is None or not user.active:
        raise HTTPException(401, "Authentication required")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_origin(request)
        if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), csrf_token(token)):
            raise HTTPException(403, "Invalid CSRF token")
    return user


Actor = Annotated[User, Depends(current_user)]


async def new_session(session: AsyncSession, user: User, request: Request) -> str:
    await session.refresh(user, with_for_update=True)
    if not user.active:
        raise HTTPException(401, "Invalid account or password")
    old = request.cookies.get(COOKIE)
    if old:
        await session.execute(
            update(LoginSession)
            .where(LoginSession.token_hash == digest(old))
            .values(revoked_at=datetime.now(UTC))
        )
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    session.add(
        LoginSession(
            token_hash=digest(token),
            user_id=user.id,
            expires_at=now + timedelta(hours=24),
            last_seen_at=now,
        )
    )
    await session.commit()
    return token
