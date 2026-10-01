from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select

from app.models import AppDraft, AppVersion, LearningApp, PublicationReview, UploadReference
from app.scoring import Content, validate_publication
from app.security import DB, Actor
from app.uploads import content_images, validate_uploads
from app.versions import canonical_hash

router = APIRouter(prefix="/api/v1")


def require_admin(actor: Actor) -> None:
    if actor.role != "admin":
        raise HTTPException(403, "Administrator required")


async def locked_app(
    app_id: UUID, actor: Actor, session: DB, *, include_deleted: bool = False
) -> LearningApp:
    application = await session.scalar(
        select(LearningApp).where(LearningApp.id == app_id).with_for_update()
    )
    if (
        application is None
        or (application.deleted_at is not None and not include_deleted)
        or (application.owner_id != actor.id and actor.role != "admin")
    ):
        raise HTTPException(404, "Application not found")
    return application


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)


class ReviewView(BaseModel):
    version_id: UUID
    app_id: UUID
    sequence: int
    title: str
    description: str
    app_type: str
    strategy: str
    cover_id: UUID | None
    content: Content
    status: str
    reason: str
    reviewer_id: UUID | None
    reviewed_at: datetime | None


def review_view(version: AppVersion, review: PublicationReview) -> ReviewView:
    return ReviewView(
        version_id=version.id,
        app_id=version.app_id,
        sequence=version.sequence,
        title=version.title,
        description=version.description,
        app_type=version.app_type,
        strategy=version.strategy,
        cover_id=version.cover_id,
        content=Content.model_validate(version.content),
        status=review.status,
        reason=review.reason,
        reviewer_id=review.reviewer_id,
        reviewed_at=review.reviewed_at,
    )


async def latest_approved_sequence(app_id: UUID, session: DB) -> int:
    sequence = await session.scalar(
        select(func.max(AppVersion.sequence))
        .join(PublicationReview)
        .where(AppVersion.app_id == app_id, PublicationReview.status == "approved")
    )
    return sequence or 0


@router.post("/apps/{app_id}/submissions", response_model=ReviewView, status_code=201)
async def submit(app_id: UUID, body: Submission, actor: Actor, session: DB) -> ReviewView:
    application = await locked_app(app_id, actor, session)
    draft = await session.scalar(
        select(AppDraft).where(AppDraft.app_id == app_id).with_for_update()
    )
    if draft is None:
        raise HTTPException(404, "Draft not found")
    if draft.revision != body.expected_revision:
        raise HTTPException(409, "Draft changed; reload before submitting")
    try:
        content = Content.model_validate(draft.content)
        validate_publication(content, draft.app_type, draft.strategy)
    except (ValidationError, ValueError):
        raise HTTPException(
            422, "Complete valid questions and scoring rules before submitting"
        ) from None
    payload = {
        "title": draft.title,
        "description": draft.description,
        "app_type": draft.app_type,
        "strategy": draft.strategy,
        "content": content.model_dump(mode="json"),
        "cover_id": str(draft.cover_id) if draft.cover_id is not None else None,
    }
    references = content_images(content, draft.cover_id)
    await validate_uploads(references, application.owner_id, actor, session)
    content_hash = canonical_hash(payload)
    duplicate = await session.scalar(
        select(AppVersion.id)
        .join(PublicationReview)
        .where(
            AppVersion.app_id == app_id,
            AppVersion.content_hash == content_hash,
            PublicationReview.status == "pending",
        )
    )
    if duplicate is not None:
        raise HTTPException(409, "This content is already awaiting review")
    sequence = await session.scalar(
        select(func.max(AppVersion.sequence)).where(AppVersion.app_id == app_id)
    )
    version = AppVersion(
        app_id=app_id,
        sequence=(sequence or 0) + 1,
        content_hash=content_hash,
        strategy_version="rules-v1" if draft.strategy == "rules" else "ai-v1",
        title=draft.title,
        description=draft.description,
        app_type=draft.app_type,
        strategy=draft.strategy,
        content=content.model_dump(mode="json"),
        cover_id=draft.cover_id,
    )
    session.add(version)
    await session.flush()
    review = PublicationReview(version_id=version.id, status="pending")
    session.add(review)
    session.add_all(
        [
            UploadReference(upload_id=upload_id, version_id=version.id)
            for upload_id in {reference[0] for reference in references}
        ]
    )
    await session.commit()
    return review_view(version, review)


@router.get("/apps/{app_id}/submissions", response_model=list[ReviewView])
async def submissions(
    app_id: UUID,
    actor: Actor,
    session: DB,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> list[ReviewView]:
    await locked_app(app_id, actor, session, include_deleted=True)
    rows = await session.execute(
        select(AppVersion, PublicationReview)
        .join(PublicationReview)
        .where(AppVersion.app_id == app_id)
        .order_by(AppVersion.sequence.desc(), AppVersion.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [review_view(version, review) for version, review in rows]


@router.get("/admin/reviews", response_model=list[ReviewView])
async def reviews(
    actor: Actor,
    session: DB,
    status: Literal["pending", "approved", "rejected"] = "pending",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> list[ReviewView]:
    require_admin(actor)
    rows = await session.execute(
        select(AppVersion, PublicationReview)
        .join(PublicationReview)
        .join(LearningApp, LearningApp.id == AppVersion.app_id)
        .where(PublicationReview.status == status, LearningApp.deleted_at.is_(None))
        .order_by(AppVersion.app_id, AppVersion.sequence, AppVersion.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [review_view(version, review) for version, review in rows]


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["approved", "rejected"]
    reason: str = Field(default="", max_length=2000)


@router.post("/admin/reviews/{version_id}", response_model=ReviewView)
async def decide(version_id: UUID, body: ReviewDecision, actor: Actor, session: DB) -> ReviewView:
    require_admin(actor)
    version = await session.get(AppVersion, version_id)
    if version is None:
        raise HTTPException(404, "Version not found")
    application = await locked_app(version.app_id, actor, session)
    review = await session.get(PublicationReview, version_id, with_for_update=True)
    if review is None or review.status != "pending":
        raise HTTPException(409, "Review is no longer pending")
    if body.status == "approved":
        if await latest_approved_sequence(version.app_id, session) >= version.sequence:
            raise HTTPException(409, "Cannot publish an older version")
        application.active_version_id = version_id
    review.status = body.status
    review.reason = body.reason
    review.reviewer_id = actor.id
    review.reviewed_at = datetime.now(UTC)
    await session.commit()
    return review_view(version, review)


@router.post("/apps/{app_id}/unpublish", status_code=204)
async def unpublish(app_id: UUID, actor: Actor, session: DB) -> None:
    application = await locked_app(app_id, actor, session)
    application.active_version_id = None
    await session.commit()


@router.delete("/apps/{app_id}", status_code=204)
async def delete_app(app_id: UUID, actor: Actor, session: DB) -> None:
    application = await locked_app(app_id, actor, session)
    application.deleted_at = datetime.now(UTC)
    application.active_version_id = None
    await session.commit()


@router.post("/apps/{app_id}/restore", status_code=204)
async def restore_app(app_id: UUID, actor: Actor, session: DB) -> None:
    application = await locked_app(app_id, actor, session, include_deleted=True)
    if application.deleted_at is None:
        raise HTTPException(409, "Application is not deleted")
    application.deleted_at = None
    application.active_version_id = None
    await session.commit()


class PublishVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version_id: UUID


@router.post("/apps/{app_id}/publish", status_code=204)
async def publish(app_id: UUID, body: PublishVersion, actor: Actor, session: DB) -> None:
    application = await locked_app(app_id, actor, session)
    version = await session.get(AppVersion, body.version_id)
    review = await session.get(PublicationReview, body.version_id)
    if version is None or version.app_id != app_id or review is None or review.status != "approved":
        raise HTTPException(404, "Approved version not found")
    if await latest_approved_sequence(app_id, session) > version.sequence:
        raise HTTPException(409, "Cannot publish an older version")
    application.active_version_id = version.id
    await session.commit()
