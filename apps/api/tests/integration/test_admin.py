import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import httpx
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts import Registration
from app.db import create_engine
from app.models import LoginSession, User
from scripts.create_admin import create
from scripts.seed import FIXTURE_ID
from tests.integration.test_accounts import register


def test_admin_guards_deactivation_roles_content_and_answer_restore() -> None:
    origin = os.environ["PUBLIC_ORIGIN"]
    admin_account = "admin_" + uuid.uuid4().hex
    asyncio.run(
        create(
            Registration(
                account=admin_account,
                password="admin_fixture_password_123",
                display_name="管理驗收",
            )
        )
    )
    with (
        httpx.Client(base_url=os.environ["API_ORIGIN"]) as user,
        httpx.Client(base_url=os.environ["API_ORIGIN"]) as admin,
        httpx.Client(base_url=os.environ["API_ORIGIN"]) as guest,
    ):
        account, user_id = register(user)
        login = admin.post(
            "/api/v1/auth/login",
            headers={"Origin": origin},
            json={"account": admin_account, "password": "admin_fixture_password_123"},
        )
        assert login.status_code == 200
        admin.headers.update({"Origin": origin, "X-CSRF-Token": login.json()["csrf_token"]})
        for path in ("users", "apps", "questions", "scoring-rules", "answers", "reviews"):
            assert guest.get(f"/api/v1/admin/{path}").status_code == 401
            assert user.get(f"/api/v1/admin/{path}").status_code == 403
            response = admin.get(f"/api/v1/admin/{path}")
            assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        assert admin.get("/api/v1/admin/users?q=" + account).json()[0]["id"] == user_id
        assert admin.get("/api/v1/admin/users?page_size=101").status_code == 422
        assert "password_hash" not in admin.get(f"/api/v1/admin/users/{user_id}").json()
        assert (
            user.patch(f"/api/v1/admin/users/{user_id}", json={"role": "admin"}).status_code == 403
        )
        assert (
            admin.patch(f"/api/v1/admin/users/{user_id}", json={"active": False}).json()["active"]
            is False
        )
        assert user.get("/api/v1/auth/me").status_code == 401
        assert (
            admin.patch(f"/api/v1/admin/users/{user_id}", json={"active": True}).status_code == 200
        )
        assert user.get("/api/v1/auth/me").status_code == 401
        login = user.post(
            "/api/v1/auth/login", json={"account": account, "password": "local_test_password_123"}
        )
        assert login.status_code == 200
        user.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        created = admin.post(
            "/api/v1/admin/users",
            json={
                "account": "created_" + uuid.uuid4().hex,
                "password": "created_fixture_password_123",
                "display_name": "新使用者",
            },
        )
        assert created.status_code == 201 and created.json()["role"] == "user"
        assert (
            admin.post(
                "/api/v1/admin/users",
                json={
                    "account": created.json()["account"],
                    "password": "created_fixture_password_123",
                    "display_name": "重复",
                },
            ).status_code
            == 409
        )
        draft = user.post("/api/v1/apps", json={"title": "管理修改草稿"}).json()
        app_id = draft["app_id"]
        assert (
            admin.patch(
                f"/api/v1/apps/{app_id}/draft", json={"title": "管理者修改", "expected_revision": 1}
            ).status_code
            == 200
        )
        assert admin.get(f"/api/v1/admin/apps?app_id={app_id}").json()[0]["title"] == "管理者修改"
        for route in ("questions", "scoring-rules"):
            assert admin.get(f"/api/v1/admin/{route}?app_id={app_id}").json()[0]["revision"] == 2
        assert user.delete(f"/api/v1/apps/{app_id}").status_code == 204
        assert admin.get(f"/api/v1/admin/apps?app_id={app_id}").json() == []
        assert (
            admin.get(f"/api/v1/admin/apps?app_id={app_id}&included_deleted=true").json()[0][
                "deleted_at"
            ]
            is not None
        )
        assert user.get("/api/v1/me/apps?deleted=true").json()[0]["app_id"] == app_id
        assert admin.post(f"/api/v1/apps/{app_id}/restore").status_code == 204
        assert guest.get(f"/api/v1/apps/{app_id}").status_code == 404
        version = guest.get(f"/api/v1/apps/{FIXTURE_ID}").json()["version_id"]
        answer = user.post(
            f"/api/v1/versions/{version}/answers",
            headers={"Idempotency-Key": uuid.uuid4().hex},
            json={"choices": ["A", "B"]},
        ).json()
        answer_id = answer["id"]
        assert user.get(f"/api/v1/admin/answers/{answer_id}").status_code == 403
        assert (
            admin.patch(
                f"/api/v1/admin/answers/{answer_id}", json={"choices": ["B", "A"], "hidden": False}
            ).status_code
            == 422
        )
        assert (
            admin.patch(f"/api/v1/admin/answers/{answer_id}", json={"hidden": True}).status_code
            == 200
        )
        assert user.get(f"/api/v1/answers/{answer_id}").status_code == 404
        rows = admin.get(f"/api/v1/admin/answers?app_id={FIXTURE_ID}&included_hidden=true").json()
        assert any(row["id"] == answer_id and row["hidden_at"] is not None for row in rows)
        assert (
            admin.patch(f"/api/v1/admin/answers/{answer_id}", json={"hidden": False}).status_code
            == 200
        )
        assert user.get(f"/api/v1/answers/{answer_id}").json() == answer
        assert (
            admin.patch(f"/api/v1/admin/users/{user_id}", json={"role": "admin"}).status_code == 200
        )
        assert user.get("/api/v1/auth/me").status_code == 401
        login = user.post(
            "/api/v1/auth/login", json={"account": account, "password": "local_test_password_123"}
        )
        assert login.status_code == 200 and login.json()["user"]["role"] == "admin"


def test_waiting_login_cannot_create_session_after_deactivation() -> None:
    origin = os.environ["PUBLIC_ORIGIN"]
    with httpx.Client(base_url=os.environ["API_ORIGIN"]) as owner:
        account, user_id = register(owner)

        def login() -> httpx.Response:
            with httpx.Client(base_url=os.environ["API_ORIGIN"], timeout=30) as fresh:
                return fresh.post(
                    "/api/v1/auth/login",
                    headers={"Origin": origin},
                    json={
                        "account": account,
                        "password": "local_test_password_123",
                    },
                )

        with ThreadPoolExecutor(max_workers=1) as executor:

            async def race() -> None:
                engine = create_engine()
                try:
                    async with AsyncSession(engine) as db:
                        user = await db.scalar(
                            select(User).where(User.id == uuid.UUID(user_id)).with_for_update()
                        )
                        assert user is not None
                        locker = await db.scalar(text("SELECT pg_backend_pid()"))
                        future = executor.submit(login)
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
                            raise AssertionError("Login did not reach the user lock")
                        user.active = False
                        await db.execute(
                            update(LoginSession)
                            .where(LoginSession.user_id == user.id)
                            .values(revoked_at=datetime.now(UTC))
                        )
                        await db.commit()
                        response = await asyncio.to_thread(future.result, 10)
                        assert response.status_code == 401
                        user.active = True
                        await db.commit()
                finally:
                    await engine.dispose()

            asyncio.run(race())
        assert owner.get("/api/v1/auth/me").status_code == 401
        assert login().status_code == 200
