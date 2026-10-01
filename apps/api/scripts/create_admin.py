"""Explicit local administrator creation; password is read from an interactive prompt."""

import asyncio
import getpass

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts import Registration
from app.db import create_engine
from app.models import User
from app.security import hasher


async def create(body: Registration) -> None:
    engine = create_engine()
    try:
        async with AsyncSession(engine) as session, session.begin():
            if await session.scalar(select(User.id).where(User.account == body.account)):
                raise SystemExit("Account already exists; existing users are not promoted")
            session.add(
                User(
                    account=body.account,
                    display_name=body.display_name,
                    password_hash=await asyncio.to_thread(hasher.hash, body.password),
                    role="admin",
                )
            )
    finally:
        await engine.dispose()
    print("Administrator created")


if __name__ == "__main__":
    account = input("Account: ").strip()
    name = input("Display name: ").strip()
    password = getpass.getpass("Password (12–128 characters): ")
    if password != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords do not match")
    try:
        body = Registration(account=account, display_name=name, password=password)
    except ValidationError:
        raise SystemExit("Invalid account, display name, or password length") from None
    asyncio.run(create(body))
