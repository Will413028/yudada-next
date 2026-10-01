import asyncio
import os
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import create_engine
from app.models import AppVersion, LearningApp, PublicationReview
from app.versions import canonical_hash
from scripts.seed import FIXTURE_CONTENT, FIXTURE_OWNER


def test_public_pagination_and_pending_versions_are_not_visible() -> None:
    app_ids = [uuid.uuid4() for _ in range(21)]
    version_ids = [uuid.uuid4() for _ in app_ids]

    async def setup() -> None:
        engine = create_engine()
        try:
            async with AsyncSession(engine) as db, db.begin():
                for index, (app_id, version_id) in enumerate(
                    zip(app_ids, version_ids, strict=True)
                ):
                    app = LearningApp(id=app_id, owner_id=FIXTURE_OWNER)
                    db.add(app)
                    await db.flush()
                    db.add(
                        AppVersion(
                            id=version_id,
                            app_id=app_id,
                            sequence=1,
                            title=f"分頁 fixture {index}",
                            description="",
                            app_type="assessment",
                            strategy="rules",
                            content=FIXTURE_CONTENT,
                            content_hash=canonical_hash(FIXTURE_CONTENT),
                        )
                    )
                    await db.flush()
                    db.add(
                        PublicationReview(
                            version_id=version_id, status="approved" if index < 20 else "pending"
                        )
                    )
                    app.active_version_id = version_id
        finally:
            await engine.dispose()

    async def cleanup() -> None:
        engine = create_engine()
        try:
            async with AsyncSession(engine) as db, db.begin():
                await db.execute(
                    update(LearningApp)
                    .where(LearningApp.id.in_(app_ids))
                    .values(
                        active_version_id=None,
                        deleted_at=datetime.now(UTC),
                    )
                )
        finally:
            await engine.dispose()

    try:
        asyncio.run(setup())
        with httpx.Client(base_url=os.environ["API_ORIGIN"]) as client:
            first = client.get("/api/v1/apps").json()
            second = client.get("/api/v1/apps?page=2").json()
            assert len(first) == 20 and len(second) == 1
            assert len({row["id"] for row in first + second}) == 21
            assert client.get("/api/v1/apps?page_size=101").status_code == 422
            assert client.get("/api/v1/apps?page=0").status_code == 422
            assert client.get(f"/api/v1/apps/{app_ids[-1]}").status_code == 404
            assert client.get(f"/api/v1/versions/{version_ids[-1]}/questions").status_code == 404
    finally:
        asyncio.run(cleanup())
