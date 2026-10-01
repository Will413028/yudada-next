import asyncio
import io
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.models import (
    Answer,
    AppVersion,
    LearningApp,
    PublicationReview,
    Upload,
    UploadReference,
    User,
)
from app.scoring import DraftContent
from app.security import COOKIE, DB, Actor, current_user

router = APIRouter(prefix="/api/v1")
MAX_BYTES = 1024 * 1024
Purpose = Literal["avatar", "cover", "result"]


class UploadView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    purpose: str
    media_type: str
    size: int
    width: int
    height: int


def blob_path(upload: Upload) -> Path:
    default = (
        Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
        / "yudada-next/uploads"
    )
    return Path(os.environ.get("UPLOAD_ROOT", str(default))) / str(upload.owner_id) / str(upload.id)


def decode_image(payload: bytes) -> tuple[bytes, str, int, int]:
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(payload), formats=["PNG", "JPEG", "WEBP"]) as image:
            width, height = image.size
            if width > 4096 or height > 4096 or width * height > 16_000_000:
                raise ValueError("Image dimensions exceed the limit")
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError("Animated images are not supported")
            image.load()
            output = io.BytesIO()
            image_format = image.format
            if image_format is None:
                raise ValueError("Unknown image format")
            image.convert("RGBA" if image_format != "JPEG" else "RGB").save(
                output, format=image_format
            )
            result = output.getvalue()
            if len(result) > MAX_BYTES:
                raise ValueError("Decoded image exceeds the size limit")
            return (
                result,
                {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[image_format],
                width,
                height,
            )
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ValueError(
            "Upload a valid PNG, JPEG or WebP within the size and dimension limits"
        ) from None


async def validate_uploads(
    references: list[tuple[UUID, Purpose]], owner_id: UUID, actor: Actor, session: DB
) -> None:
    for upload_id, purpose in sorted(set(references), key=lambda value: str(value[0])):
        upload = await session.get(Upload, upload_id, with_for_update=True)
        if (
            upload is None
            or upload.deleted_at is not None
            or upload.purpose != purpose
            or (upload.owner_id != owner_id and actor.role != "admin")
        ):
            raise HTTPException(422, "Image reference is unavailable")


def content_images(content: DraftContent, cover_id: UUID | None) -> list[tuple[UUID, Purpose]]:
    references: list[tuple[UUID, Purpose]] = [
        (rule.image_id, "result") for rule in content.rules if rule.image_id is not None
    ]
    if cover_id is not None:
        references.append((cover_id, "cover"))
    return references


@router.post(
    "/uploads",
    response_model=UploadView,
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
)
async def upload_image(request: Request, purpose: Purpose, actor: Actor, session: DB) -> UploadView:
    payload = bytearray()
    async for chunk in request.stream():
        if len(payload) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, "Image must be at most 1 MiB")
        payload.extend(chunk)
    try:
        data, media_type, width, height = await asyncio.to_thread(decode_image, bytes(payload))
    except ValueError:
        raise HTTPException(422, "Invalid or unsupported image") from None
    upload = Upload(
        owner_id=actor.id,
        purpose=purpose,
        media_type=media_type,
        size=len(data),
        width=width,
        height=height,
    )
    session.add(upload)
    await session.flush()
    path = blob_path(upload)

    def write() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as output:
            output.write(data)

    await asyncio.to_thread(write)
    try:
        await session.commit()
    except Exception:
        await asyncio.to_thread(path.unlink, missing_ok=True)
        raise
    return UploadView.model_validate(upload)


async def viewer(request: Request, session: DB) -> User | None:
    if not request.cookies.get(COOKIE):
        return None
    try:
        return await current_user(request, session)
    except HTTPException as exc:
        if exc.status_code != 401:
            raise
        return None


async def may_read(upload_id: UUID, actor: User | None, session: DB) -> bool:
    public_reference = await session.scalar(
        select(UploadReference.upload_id)
        .join(AppVersion, AppVersion.id == UploadReference.version_id)
        .join(PublicationReview, PublicationReview.version_id == AppVersion.id)
        .join(LearningApp, LearningApp.id == AppVersion.app_id)
        .where(
            UploadReference.upload_id == upload_id,
            PublicationReview.status == "approved",
            LearningApp.deleted_at.is_(None),
            LearningApp.active_version_id.is_not(None),
        )
        .limit(1)
    )
    if public_reference is not None:
        return True
    avatar = await session.scalar(
        select(User.id)
        .join(LearningApp, LearningApp.owner_id == User.id)
        .join(AppVersion, AppVersion.id == LearningApp.active_version_id)
        .join(PublicationReview, PublicationReview.version_id == AppVersion.id)
        .where(
            User.avatar_id == upload_id,
            LearningApp.deleted_at.is_(None),
            PublicationReview.status == "approved",
            AppVersion.app_id == LearningApp.id,
        )
        .limit(1)
    )
    if avatar is not None:
        return True
    if actor is None:
        return False
    answer = await session.scalar(
        select(Answer.id)
        .where(
            Answer.owner_id == actor.id,
            Answer.hidden_at.is_(None),
            Answer.result_snapshot["image_id"].as_string() == str(upload_id),
        )
        .limit(1)
    )
    return answer is not None


@router.get("/uploads/{upload_id}", response_class=Response)
async def read_image(
    upload_id: UUID, session: DB, actor: Annotated[User | None, Depends(viewer)]
) -> Response:
    upload = await session.get(Upload, upload_id)
    if upload is None:
        raise HTTPException(404, "Image not found")
    if not (actor is not None and (actor.id == upload.owner_id or actor.role == "admin")):
        if not await may_read(upload_id, actor, session):
            raise HTTPException(404, "Image not found")
    try:
        data = await asyncio.to_thread(blob_path(upload).read_bytes)
    except FileNotFoundError:
        raise HTTPException(404, "Image not found") from None
    return Response(
        data,
        media_type=upload.media_type,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.delete("/uploads/{upload_id}", status_code=204)
async def hide_image(upload_id: UUID, actor: Actor, session: DB) -> None:
    upload = await session.get(Upload, upload_id, with_for_update=True)
    if upload is None or (upload.owner_id != actor.id and actor.role != "admin"):
        raise HTTPException(404, "Image not found")
    upload.deleted_at = datetime.now(UTC)
    await session.commit()
