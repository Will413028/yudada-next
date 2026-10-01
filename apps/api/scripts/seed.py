"""Explicit local fixture, separate from schema migrations."""

import argparse
import asyncio
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import create_engine
from app.models import AppDraft, AppVersion, LearningApp, PublicationReview, User
from app.versions import canonical_hash

FIXTURE_ID = UUID("00000000-0000-4000-8000-000000000001")
FIXTURE_NAME = "探索你的學習風格"
FIXTURE_OWNER = UUID("00000000-0000-4000-8000-000000000002")
FIXTURE_CONTENT = {
    "questions": [
        {
            "title": "學習新事物時，你偏好？",
            "options": [
                {"key": "A", "text": "先自己研究", "property": "I", "score": 0},
                {"key": "B", "text": "與朋友討論", "property": "E", "score": 1},
            ],
        },
        {
            "title": "遇到難題時，你通常？",
            "options": [
                {"key": "A", "text": "找人一起想", "property": "E", "score": 1},
                {"key": "B", "text": "安靜地思考", "property": "I", "score": 0},
            ],
        },
    ],
    "rules": [
        {"name": "交流型", "description": "透過交流整理想法。", "properties": ["E"]},
        {"name": "探索型", "description": "透過獨立探索建立理解。", "properties": ["I"]},
    ],
}


async def seed(name: str) -> None:
    engine = create_engine()
    try:
        async with AsyncSession(engine) as session, session.begin():
            if await session.get(User, FIXTURE_OWNER) is None:
                session.add(
                    User(
                        id=FIXTURE_OWNER,
                        account="fixture-owner",
                        password_hash="!",
                        display_name="示範作者",
                        role="user",
                        active=False,
                    )
                )
                await session.flush()
            app = await session.get(LearningApp, FIXTURE_ID)
            if app is None:
                app = LearningApp(id=FIXTURE_ID, owner_id=FIXTURE_OWNER)
                session.add(app)
                await session.flush()
                session.add(
                    AppDraft(
                        app_id=FIXTURE_ID,
                        title=name,
                        description="認識自己的學習偏好。",
                        content=FIXTURE_CONTENT,
                    )
                )
            current = (
                await session.get(AppVersion, app.active_version_id)
                if app.active_version_id
                else None
            )
            if current is not None and current.title == name:
                return
            sequence = (
                await session.scalar(
                    select(func.max(AppVersion.sequence)).where(AppVersion.app_id == FIXTURE_ID)
                )
                or 0
            ) + 1
            version = AppVersion(
                app_id=FIXTURE_ID,
                sequence=sequence,
                title=name,
                description="認識自己的學習偏好。",
                app_type="assessment",
                strategy="rules",
                content=FIXTURE_CONTENT,
                content_hash=canonical_hash(FIXTURE_CONTENT),
            )
            session.add(version)
            await session.flush()
            session.add(
                PublicationReview(version_id=version.id, status="approved", reason="Local fixture")
            )
            app.active_version_id = version.id
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default=FIXTURE_NAME)
    asyncio.run(seed(parser.parse_args().name))
