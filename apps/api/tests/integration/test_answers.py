import asyncio
import copy
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import create_engine
from app.models import Answer, AppDraft, AppVersion, LearningApp
from scripts.seed import FIXTURE_CONTENT, FIXTURE_ID, FIXTURE_NAME, seed
from tests.integration.test_accounts import register


def test_published_answers_idempotency_privacy_and_history() -> None:
    with (
        httpx.Client(base_url=os.environ["API_ORIGIN"]) as owner,
        httpx.Client(base_url=os.environ["API_ORIGIN"]) as other,
    ):
        register(owner)
        register(other)
        details = owner.get(f"/api/v1/apps/{FIXTURE_ID}").json()
        version_id = details["version_id"]
        path = f"/api/v1/versions/{version_id}/answers"
        questions = owner.get(f"/api/v1/versions/{version_id}/questions").json()
        assert set(questions[0]["options"][0]) == {"key", "text"}
        assert owner.post(path, json={"choices": ["A", "B"]}).status_code == 422
        for choices in (["A"], ["A", "invalid"]):
            assert (
                owner.post(
                    path, headers={"Idempotency-Key": uuid.uuid4().hex}, json={"choices": choices}
                ).status_code
                == 422
            )
        key = uuid.uuid4().hex
        payload = {"choices": ["A", "B"]}
        first = owner.post(path, headers={"Idempotency-Key": key}, json=payload)
        assert first.status_code == 201
        answer = first.json()
        assert answer["result_snapshot"]["name"] == "探索型"
        assert answer["result_snapshot"]["app_name"] == FIXTURE_NAME
        assert owner.post(path, headers={"Idempotency-Key": key}, json=payload).json() == answer
        assert (
            owner.post(
                path, headers={"Idempotency-Key": key}, json={"choices": ["A", "A"]}
            ).status_code
            == 409
        )
        answer_path = f"/api/v1/answers/{answer['id']}"
        assert other.get(answer_path).status_code == 404
        assert owner.get(answer_path).headers["cache-control"] == "no-store"
        other_answer = other.post(path, headers={"Idempotency-Key": key}, json=payload).json()
        assert other_answer["id"] != answer["id"]
        assert any(row["id"] == answer["id"] for row in owner.get("/api/v1/me/answers").json())

        async def change_draft_and_attempt_version_mutation() -> None:
            engine = create_engine()
            try:
                async with AsyncSession(engine) as db, db.begin():
                    changed = copy.deepcopy(FIXTURE_CONTENT)
                    for question in changed["questions"]:
                        for option in question["options"]:
                            option["property"] = "E"
                    await db.execute(
                        update(AppDraft)
                        .where(AppDraft.app_id == FIXTURE_ID)
                        .values(title="私有新名稱", content=changed)
                    )
                async with AsyncSession(engine) as db:
                    with pytest.raises(DBAPIError, match="immutable"):
                        await db.execute(
                            update(AppVersion)
                            .where(AppVersion.id == uuid.UUID(version_id))
                            .values(title="不可改的已發布內容")
                        )
                    await db.rollback()
            finally:
                await engine.dispose()

        asyncio.run(change_draft_and_attempt_version_mutation())
        assert owner.get(f"/api/v1/apps/{FIXTURE_ID}").json()["name"] == FIXTURE_NAME
        unchanged = owner.post(path, headers={"Idempotency-Key": uuid.uuid4().hex}, json=payload)
        assert unchanged.json()["result_snapshot"]["name"] == "探索型"
        try:
            asyncio.run(seed("新版已核准名稱"))
            assert owner.get(f"/api/v1/apps/{FIXTURE_ID}").json()["version_id"] != version_id
            assert owner.get(answer_path).json() == answer
            assert owner.post(path, headers={"Idempotency-Key": key}, json=payload).json() == answer
        finally:
            asyncio.run(seed(FIXTURE_NAME))
        assert owner.delete(answer_path).status_code == 204
        assert owner.get(answer_path).status_code == 404
        assert not any(row["id"] == answer["id"] for row in owner.get("/api/v1/me/answers").json())
        assert any(
            row["id"] == answer["id"]
            for row in owner.get("/api/v1/me/answers?included_hidden=true").json()
        )
        assert other.post(answer_path + "/restore").status_code == 404
        assert owner.post(answer_path + "/restore").status_code == 204
        assert owner.get(answer_path).json() == answer


def test_concurrent_submission_creates_one_answer_and_unpublish_blocks_new() -> None:
    with httpx.Client(base_url=os.environ["API_ORIGIN"]) as client:
        register(client)
        version = client.get(f"/api/v1/apps/{FIXTURE_ID}").json()["version_id"]
        path = f"/api/v1/versions/{version}/answers"
        key = uuid.uuid4().hex

        def submit() -> httpx.Response:
            return client.post(path, headers={"Idempotency-Key": key}, json={"choices": ["B", "A"]})

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(lambda _: submit(), range(2)))
        assert sorted(response.status_code for response in responses) == [200, 201]
        assert responses[0].json()["id"] == responses[1].json()["id"]

        async def unpublish() -> None:
            engine = create_engine()
            try:
                async with AsyncSession(engine) as db, db.begin():
                    rows = list(
                        await db.scalars(select(Answer).where(Answer.idempotency_key == key))
                    )
                    assert len(rows) == 1
                    await db.execute(
                        update(LearningApp)
                        .where(LearningApp.id == FIXTURE_ID)
                        .values(active_version_id=None)
                    )
            finally:
                await engine.dispose()

        try:
            asyncio.run(unpublish())
            assert submit().status_code == 200
            assert (
                client.post(
                    path,
                    headers={"Idempotency-Key": uuid.uuid4().hex},
                    json={"choices": ["B", "A"]},
                ).status_code
                == 404
            )
            assert client.get(f"/api/v1/answers/{responses[0].json()['id']}").status_code == 200
        finally:
            asyncio.run(seed(FIXTURE_NAME))


def test_unpublish_wins_before_waiting_answer_checks_visibility() -> None:
    with httpx.Client(base_url=os.environ["API_ORIGIN"], timeout=30) as client:
        register(client)
        version = client.get(f"/api/v1/apps/{FIXTURE_ID}").json()["version_id"]
        with ThreadPoolExecutor(max_workers=1) as executor:

            async def race() -> None:
                engine = create_engine()
                try:
                    async with AsyncSession(engine) as db:
                        application = await db.scalar(
                            select(LearningApp)
                            .where(LearningApp.id == FIXTURE_ID)
                            .with_for_update()
                        )
                        assert application is not None
                        locker = await db.scalar(text("SELECT pg_backend_pid()"))
                        future = executor.submit(
                            client.post,
                            f"/api/v1/versions/{version}/answers",
                            headers={"Idempotency-Key": uuid.uuid4().hex},
                            json={"choices": ["A", "B"]},
                        )
                        for _ in range(250):
                            blocked = await db.scalar(
                                text(
                                    "SELECT count(*) FROM pg_stat_activity "
                                    "WHERE :locker = ANY(pg_blocking_pids(pid))"
                                ),
                                {"locker": locker},
                            )
                            if blocked:
                                break
                            await asyncio.sleep(0.02)
                        else:
                            raise AssertionError("Answer did not reach the application lock")
                        application.active_version_id = None
                        await db.commit()
                        response = await asyncio.to_thread(future.result, 10)
                        assert response.status_code == 404
                finally:
                    await engine.dispose()

            try:
                asyncio.run(race())
            finally:
                asyncio.run(seed(FIXTURE_NAME))
