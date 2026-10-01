from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models import Answer
from app.scoring import Content, evaluate
from app.security import DB, Actor
from app.versions import canonical_hash, public_version

router = APIRouter(prefix="/api/v1")


class AnswerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    choices: list[str] = Field(min_length=1, max_length=100)


class AnswerView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    app_id: UUID
    version_id: UUID
    choices: list[str]
    status: str
    result_snapshot: dict[str, object] | None
    created_at: datetime
    hidden_at: datetime | None


@router.post("/versions/{version_id}/answers", response_model=AnswerView, status_code=201)
async def submit_answer(
    version_id: UUID,
    body: AnswerInput,
    actor: Actor,
    session: DB,
    response: Response,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=128, pattern="^[!-~]+$")],
) -> AnswerView:
    payload_hash = canonical_hash({"version_id": str(version_id), "choices": body.choices})
    existing = await session.scalar(
        select(Answer).where(Answer.owner_id == actor.id, Answer.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.payload_hash != payload_hash:
            raise HTTPException(409, "Submission key already used for different answers")
        response.status_code = 200
        return AnswerView.model_validate(existing)
    version = await public_version(version_id, session, for_answer=True)
    if version.strategy != "rules":
        raise HTTPException(503, "AI scoring is not available yet")
    try:
        result = evaluate(Content.model_validate(version.content), version.app_type, body.choices)
    except ValueError as exc:
        raise HTTPException(422, "Invalid answers for this version") from exc
    statement = (
        insert(Answer)
        .values(
            owner_id=actor.id,
            app_id=version.app_id,
            version_id=version.id,
            choices=body.choices,
            payload_hash=payload_hash,
            idempotency_key=idempotency_key,
            status="succeeded",
            result_snapshot={
                **result.model_dump(mode="json"),
                "app_name": version.title,
                "app_description": version.description,
                "strategy_version": version.strategy_version,
            },
        )
        .on_conflict_do_nothing(constraint="uq_answer_owner_key")
        .returning(Answer)
    )
    answer = await session.scalar(statement)
    if answer is None:
        answer = await session.scalar(
            select(Answer).where(
                Answer.owner_id == actor.id, Answer.idempotency_key == idempotency_key
            )
        )
        if answer is None or answer.payload_hash != payload_hash:
            raise HTTPException(409, "Submission key already used for different answers")
        response.status_code = 200
    await session.commit()
    return AnswerView.model_validate(answer)


async def own_answer(answer_id: UUID, actor: Actor, session: DB) -> Answer:
    answer = await session.get(Answer, answer_id)
    if answer is None or answer.owner_id != actor.id or answer.hidden_at is not None:
        raise HTTPException(404, "Answer not found")
    return answer


@router.get("/answers/{answer_id}", response_model=AnswerView)
async def read_answer(answer_id: UUID, actor: Actor, session: DB) -> AnswerView:
    return AnswerView.model_validate(await own_answer(answer_id, actor, session))


@router.get("/me/answers", response_model=list[AnswerView])
async def history(
    actor: Actor,
    session: DB,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    included_hidden: bool = False,
) -> list[AnswerView]:
    query = select(Answer).where(Answer.owner_id == actor.id)
    if not included_hidden:
        query = query.where(Answer.hidden_at.is_(None))
    rows = await session.scalars(
        query.order_by(Answer.created_at.desc(), Answer.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [AnswerView.model_validate(row) for row in rows]


@router.delete("/answers/{answer_id}", status_code=204)
async def hide_answer(answer_id: UUID, actor: Actor, session: DB) -> Response:
    answer = await own_answer(answer_id, actor, session)
    answer.hidden_at = datetime.now(UTC)
    await session.commit()
    return Response(status_code=204)


@router.post("/answers/{answer_id}/restore", status_code=204)
async def restore_answer(answer_id: UUID, actor: Actor, session: DB) -> None:
    answer = await session.get(Answer, answer_id, with_for_update=True)
    if answer is None or answer.owner_id != actor.id:
        raise HTTPException(404, "Answer not found")
    if answer.hidden_at is None:
        raise HTTPException(409, "Answer is already visible")
    answer.hidden_at = None
    await session.commit()
