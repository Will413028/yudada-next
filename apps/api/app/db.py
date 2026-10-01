import os

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL must be configured")
    if not url.startswith("postgresql+asyncpg://"):
        raise RuntimeError("DATABASE_URL must use PostgreSQL with asyncpg")
    return url


def create_engine() -> AsyncEngine:
    return create_async_engine(database_url(), pool_pre_ping=True, hide_parameters=True)
