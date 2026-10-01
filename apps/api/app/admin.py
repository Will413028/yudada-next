import asyncio
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError

from app.accounts import Profile, Registration
from app.answers import AnswerView
from app.drafts import DraftView
from app.models import Answer, AppDraft, LearningApp, LoginSession, User
from app.publication import require_admin
from app.scoring import Question, Rule
from app.security import DB, Actor, hasher

router = APIRouter(prefix="/api/v1/admin")


class AdminUserView(Profile):
    active: bool
    created_at: datetime


class AdminUserCreate(Registration):
    role: Literal["user", "admin"] = "user"


class AdminUserPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    role: Literal["user", "admin"] | None = None
    active: bool | None = None


@router.get("/users", response_model=list[AdminUserView])
async def users(
    actor: Actor,
    session: DB,
    q: str = Query("", max_length=120),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> list[AdminUserView]:
    require_admin(actor)
    query = select(User)
    if q:
        query = query.where(
            or_(
                User.account.contains(q, autoescape=True),
                User.display_name.contains(q, autoescape=True),
            )
        )
    rows = await session.scalars(
        query.order_by(User.created_at.desc(), User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [AdminUserView.model_validate(row) for row in rows]


@router.get("/users/{user_id}", response_model=AdminUserView)
async def user_detail(user_id: UUID, actor: Actor, session: DB) -> AdminUserView:
    require_admin(actor)
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return AdminUserView.model_validate(user)


@router.post("/users", response_model=AdminUserView, status_code=201)
async def create_user(body: AdminUserCreate, actor: Actor, session: DB) -> AdminUserView:
    require_admin(actor)
    user = User(
        account=body.account,
        display_name=body.display_name,
        role=body.role,
        password_hash=await asyncio.to_thread(hasher.hash, body.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(409, "Account unavailable") from None
    return AdminUserView.model_validate(user)


@router.patch("/users/{user_id}", response_model=AdminUserView)
async def edit_user(
    user_id: UUID, body: AdminUserPatch, actor: Actor, session: DB
) -> AdminUserView:
    require_admin(actor)
    user = await session.get(User, user_id, with_for_update=True, populate_existing=True)
    if user is None:
        raise HTTPException(404, "User not found")
    if body.display_name is not None:
        user.display_name = body.display_name
    revoke = (body.active is False) or (body.role is not None and body.role != user.role)
    if body.role is not None:
        user.role = body.role
    if body.active is not None:
        user.active = body.active
    if revoke:
        await session.execute(
            update(LoginSession)
            .where(LoginSession.user_id == user_id, LoginSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
    await session.commit()
    return AdminUserView.model_validate(user)


class AdminAppView(DraftView):
    owner_id: UUID
    active_version_id: UUID | None
    deleted_at: datetime | None


@router.get("/apps", response_model=list[AdminAppView])
async def applications(
    actor: Actor,
    session: DB,
    q: str = Query("", max_length=120),
    included_deleted: bool = False,
    app_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> list[AdminAppView]:
    require_admin(actor)
    query = select(AppDraft, LearningApp).join(LearningApp)
    if not included_deleted:
        query = query.where(LearningApp.deleted_at.is_(None))
    if app_id is not None:
        query = query.where(LearningApp.id == app_id)
    if q:
        query = query.where(
            or_(
                AppDraft.title.contains(q, autoescape=True),
                AppDraft.description.contains(q, autoescape=True),
            )
        )
    rows = await session.execute(
        query.order_by(AppDraft.app_id).offset((page - 1) * page_size).limit(page_size)
    )
    return [
        AdminAppView(
            **DraftView.model_validate(draft).model_dump(exclude={"deleted_at"}),
            owner_id=application.owner_id,
            active_version_id=application.active_version_id,
            deleted_at=application.deleted_at,
        )
        for draft, application in rows
    ]


class AdminQuestions(BaseModel):
    app_id: UUID
    title: str
    revision: int
    questions: list[Question]


class AdminRules(BaseModel):
    app_id: UUID
    title: str
    revision: int
    rules: list[Rule]


@router.get("/questions", response_model=list[AdminQuestions])
async def questions(
    actor: Actor,
    session: DB,
    app_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> list[AdminQuestions]:
    rows = await applications(
        actor, session, q="", included_deleted=False, app_id=app_id, page=page, page_size=page_size
    )
    return [
        AdminQuestions(
            app_id=row.app_id,
            title=row.title,
            revision=row.revision,
            questions=row.content.questions,
        )
        for row in rows
    ]


@router.get("/scoring-rules", response_model=list[AdminRules])
async def scoring_rules(
    actor: Actor,
    session: DB,
    app_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> list[AdminRules]:
    rows = await applications(
        actor, session, q="", included_deleted=False, app_id=app_id, page=page, page_size=page_size
    )
    return [
        AdminRules(
            app_id=row.app_id, title=row.title, revision=row.revision, rules=row.content.rules
        )
        for row in rows
    ]


class AdminAnswerView(AnswerView):
    owner_id: UUID
    hidden_at: datetime | None


@router.get("/answers", response_model=list[AdminAnswerView])
async def answers(
    actor: Actor,
    session: DB,
    included_hidden: bool = False,
    app_id: UUID | None = None,
    version_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> list[AdminAnswerView]:
    require_admin(actor)
    query = select(Answer)
    if not included_hidden:
        query = query.where(Answer.hidden_at.is_(None))
    if app_id is not None:
        query = query.where(Answer.app_id == app_id)
    if version_id is not None:
        query = query.where(Answer.version_id == version_id)
    rows = await session.scalars(
        query.order_by(Answer.created_at.desc(), Answer.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [AdminAnswerView.model_validate(row) for row in rows]


@router.get("/answers/{answer_id}", response_model=AdminAnswerView)
async def answer_detail(answer_id: UUID, actor: Actor, session: DB) -> AdminAnswerView:
    require_admin(actor)
    answer = await session.get(Answer, answer_id)
    if answer is None:
        raise HTTPException(404, "Answer not found")
    return AdminAnswerView.model_validate(answer)


class AnswerVisibility(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hidden: bool


@router.patch("/answers/{answer_id}", response_model=AdminAnswerView)
async def answer_visibility(
    answer_id: UUID, body: AnswerVisibility, actor: Actor, session: DB
) -> AdminAnswerView:
    require_admin(actor)
    answer = await session.get(Answer, answer_id, with_for_update=True)
    if answer is None:
        raise HTTPException(404, "Answer not found")
    answer.hidden_at = datetime.now(UTC) if body.hidden else None
    await session.commit()
    return AdminAnswerView.model_validate(answer)
