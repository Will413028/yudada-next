import asyncio
import hashlib
import io
import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select

from app.models import AppVersion, LearningApp, PublicationReview
from app.scoring import Content
from app.security import DB, public_origin

router = APIRouter(prefix="/api/v1")


def canonical_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


async def public_version(version_id: UUID, session: DB, *, for_answer: bool = False) -> AppVersion:
    if for_answer:
        app_id = await session.scalar(select(AppVersion.app_id).where(AppVersion.id == version_id))
        if app_id is None:
            raise HTTPException(404, "Published version not found")
        await session.scalar(select(LearningApp).where(LearningApp.id == app_id).with_for_update())
    version = await session.scalar(
        select(AppVersion)
        .join(LearningApp, LearningApp.id == AppVersion.app_id)
        .join(PublicationReview)
        .where(
            AppVersion.id == version_id,
            LearningApp.deleted_at.is_(None),
            LearningApp.active_version_id.is_not(None),
            PublicationReview.status == "approved",
        )
    )
    if version is None:
        raise HTTPException(404, "Published version not found")
    return version


class PublicApp(BaseModel):
    id: UUID
    version_id: UUID
    name: str
    description: str
    app_type: str
    strategy: str
    cover_id: UUID | None
    share_url: str


@router.get("/apps/{app_id}", response_model=PublicApp)
async def app_detail(app_id: UUID, session: DB) -> PublicApp:
    application = await session.get(LearningApp, app_id)
    if application is None or application.active_version_id is None:
        raise HTTPException(404, "Application not found")
    version = await public_version(application.active_version_id, session)
    if version.app_id != app_id:
        raise HTTPException(404, "Application not found")
    return PublicApp(
        id=app_id,
        version_id=version.id,
        name=version.title,
        description=version.description,
        app_type=version.app_type,
        strategy=version.strategy,
        cover_id=version.cover_id,
        share_url=f"{public_origin()}/apps/{app_id}",
    )


@router.get("/apps/{app_id}/qr", response_class=Response)
async def share_qr(app_id: UUID, session: DB) -> Response:
    detail = await app_detail(app_id, session)

    def generate() -> bytes:
        import qrcode

        output = io.BytesIO()
        qrcode.make(detail.share_url).save(output)
        return output.getvalue()

    return Response(
        await asyncio.to_thread(generate),
        media_type="image/png",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


class PublicOption(BaseModel):
    key: str
    text: str


class PublicQuestion(BaseModel):
    title: str
    options: list[PublicOption]


@router.get("/versions/{version_id}/questions", response_model=list[PublicQuestion])
async def questions(version_id: UUID, session: DB) -> list[PublicQuestion]:
    version = await public_version(version_id, session)
    content = Content.model_validate(version.content)
    return [
        PublicQuestion(
            title=question.title,
            options=[PublicOption(key=option.key, text=option.text) for option in question.options],
        )
        for question in content.questions
    ]
