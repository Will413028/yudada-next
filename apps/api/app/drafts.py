from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, update

from app.models import AppDraft, LearningApp
from app.publication import locked_app
from app.scoring import DraftContent
from app.security import DB, Actor
from app.uploads import content_images, validate_uploads

router = APIRouter(prefix="/api/v1")


class DraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    app_type: str = Field(default="assessment", pattern="^(assessment|score)$")
    strategy: str = Field(default="rules", pattern="^(rules|ai)$")
    content: DraftContent = Field(default_factory=DraftContent)
    cover_id: UUID | None = None

    @model_validator(mode="after")
    def supported_strategy(self) -> "DraftInput":
        if self.app_type == "score" and self.strategy == "ai":
            raise ValueError("Score applications require rule scoring")
        return self


class DraftPatch(DraftInput):
    expected_revision: int = Field(ge=1)


class DraftView(DraftInput):
    model_config = ConfigDict(from_attributes=True)
    app_id: UUID
    revision: int
    deleted_at: datetime | None = None


async def owned_app(app_id: UUID, actor: Actor, session: DB) -> LearningApp:
    application = await session.get(LearningApp, app_id)
    if (
        application is None
        or application.deleted_at is not None
        or (application.owner_id != actor.id and actor.role != "admin")
    ):
        raise HTTPException(404, "Application not found")
    return application


@router.post("/apps", response_model=DraftView, status_code=201)
async def create_app(body: DraftInput, actor: Actor, session: DB) -> DraftView:
    await validate_uploads(content_images(body.content, body.cover_id), actor.id, actor, session)
    application = LearningApp(owner_id=actor.id)
    session.add(application)
    await session.flush()
    draft = AppDraft(app_id=application.id, revision=1, **body.model_dump(mode="json"))
    session.add(draft)
    await session.commit()
    return DraftView.model_validate(draft)


@router.get("/me/apps", response_model=list[DraftView])
async def my_apps(
    actor: Actor,
    session: DB,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    deleted: bool = False,
) -> list[DraftView]:
    rows = await session.execute(
        select(AppDraft, LearningApp)
        .join(LearningApp)
        .where(
            LearningApp.owner_id == actor.id,
            LearningApp.deleted_at.is_not(None) if deleted else LearningApp.deleted_at.is_(None),
        )
        .order_by(AppDraft.app_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [
        DraftView.model_validate(draft).model_copy(update={"deleted_at": application.deleted_at})
        for draft, application in rows
    ]


@router.get("/apps/{app_id}/draft", response_model=DraftView)
async def read_draft(app_id: UUID, actor: Actor, session: DB) -> DraftView:
    await owned_app(app_id, actor, session)
    draft = await session.get(AppDraft, app_id)
    if draft is None:
        raise HTTPException(404, "Draft not found")
    return DraftView.model_validate(draft)


@router.patch("/apps/{app_id}/draft", response_model=DraftView)
async def edit_draft(app_id: UUID, body: DraftPatch, actor: Actor, session: DB) -> DraftView:
    application = await locked_app(app_id, actor, session)
    await validate_uploads(
        content_images(body.content, body.cover_id), application.owner_id, actor, session
    )
    values = body.model_dump(mode="json", exclude={"expected_revision"})
    draft = await session.scalar(
        update(AppDraft)
        .where(AppDraft.app_id == app_id, AppDraft.revision == body.expected_revision)
        .values(**values, revision=AppDraft.revision + 1)
        .returning(AppDraft)
    )
    if draft is None:
        raise HTTPException(409, "Draft changed; reload before editing")
    await session.commit()
    return DraftView.model_validate(draft)
