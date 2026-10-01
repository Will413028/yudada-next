import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import create_engine
from app.models import LoginSession, User

ORIGIN = os.environ.get("PUBLIC_ORIGIN", "http://127.0.0.1:3300")


def register(client: httpx.Client) -> tuple[str, str]:
    account = "test_" + uuid.uuid4().hex
    result = client.post(
        "/api/v1/auth/register",
        headers={"Origin": ORIGIN},
        json={"account": account, "password": "local_test_password_123", "display_name": "測試者"},
    )
    assert result.status_code == 201
    assert "password_hash" not in result.json()["user"]
    assert "token_hash" not in result.json()
    cookie = result.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    client.headers.update({"Origin": ORIGIN, "X-CSRF-Token": result.json()["csrf_token"]})
    return account, result.json()["user"]["id"]


def test_owner_csrf_revision_and_logout() -> None:
    with (
        httpx.Client(base_url=os.environ["API_ORIGIN"]) as owner,
        httpx.Client(base_url=os.environ["API_ORIGIN"]) as other,
        httpx.Client(base_url=os.environ["API_ORIGIN"]) as guest,
    ):
        assert guest.get("/api/v1/me/apps").status_code == 401
        register(owner)
        register(other)
        created = owner.post("/api/v1/apps", json={"title": "私有草稿"})
        assert created.status_code == 201
        app_id = created.json()["app_id"]
        path = f"/api/v1/apps/{app_id}/draft"
        assert owner.get(path).headers["cache-control"] == "no-store"
        assert guest.get(path).headers["cache-control"] == "no-store"
        assert other.get(path).headers["cache-control"] == "no-store"
        assert other.get(path).status_code == 404
        assert guest.get(path).status_code == 401
        assert other.patch(path, json={"title": "竄改", "expected_revision": 1}).status_code == 404
        assert (
            owner.patch(
                path,
                headers={"X-CSRF-Token": "wrong"},
                json={"title": "竄改", "expected_revision": 1},
            ).status_code
            == 403
        )
        assert (
            owner.patch(
                path,
                headers={"Origin": "https://evil.example"},
                json={"title": "竄改", "expected_revision": 1},
            ).status_code
            == 403
        )
        updated = owner.patch(path, json={"title": "更新", "expected_revision": 1})
        assert updated.status_code == 200 and updated.json()["revision"] == 2
        assert owner.patch(path, json={"title": "覆寫", "expected_revision": 1}).status_code == 409
        assert owner.get(path).json()["title"] == "更新"
        assert not any(row["id"] == app_id for row in guest.get("/api/v1/apps").json())
        assert owner.patch("/api/v1/me", json={"display_name": "新的名字"}).status_code == 200
        assert owner.get("/api/v1/auth/me").json()["user"]["display_name"] == "新的名字"
        assert owner.post("/api/v1/auth/logout").status_code == 204
        assert owner.get("/api/v1/auth/me").status_code == 401


def test_rotation_idle_expiry_disabled_user_and_throttle() -> None:
    with httpx.Client(base_url=os.environ["API_ORIGIN"]) as client:
        account, user_id = register(client)
        old_cookie = client.cookies.get("yudada_session")
        result = client.post(
            "/api/v1/auth/login",
            json={"account": account.upper(), "password": "local_test_password_123"},
        )
        assert result.status_code == 200
        assert client.cookies.get("yudada_session") != old_cookie
        with httpx.Client(base_url=os.environ["API_ORIGIN"]) as stale:
            stale.cookies.set("yudada_session", old_cookie or "")
            assert stale.get("/api/v1/auth/me").status_code == 401

        async def expire() -> None:
            engine = create_engine()
            try:
                async with AsyncSession(engine) as db, db.begin():
                    await db.execute(
                        update(LoginSession)
                        .where(LoginSession.user_id == uuid.UUID(user_id))
                        .values(last_seen_at=datetime.now(UTC) - timedelta(minutes=31))
                    )
            finally:
                await engine.dispose()

        asyncio.run(expire())
        assert client.get("/api/v1/auth/me").status_code == 401
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"account": account, "password": "local_test_password_123"},
            ).status_code
            == 200
        )

        async def deactivate() -> None:
            engine = create_engine()
            try:
                async with AsyncSession(engine) as db, db.begin():
                    user = await db.scalar(select(User).where(User.id == uuid.UUID(user_id)))
                    assert user is not None
                    user.active = False
            finally:
                await engine.dispose()

        asyncio.run(deactivate())
        assert client.get("/api/v1/auth/me").status_code == 401
        response = client.post(
            "/api/v1/auth/login", json={"account": account, "password": "local_test_password_123"}
        )
        assert response.status_code == 401
        assert response.json()["message"] == "Invalid account or password"
        missing = "missing_" + uuid.uuid4().hex
        for _ in range(10):
            response = client.post(
                "/api/v1/auth/login",
                json={"account": missing, "password": "local_test_password_123"},
            )
            assert response.status_code == 401
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"account": missing, "password": "local_test_password_123"},
            ).status_code
            == 429
        )


def test_admin_creation_is_explicit_and_never_promotes_existing_accounts() -> None:
    import pytest

    from app.accounts import Registration
    from scripts.create_admin import create

    with httpx.Client(base_url=os.environ["API_ORIGIN"]) as owner:
        account, _ = register(owner)
        created = owner.post("/api/v1/apps", json={"title": "管理者權限驗收"})
        assert created.status_code == 201
        app_id = created.json()["app_id"]
        with pytest.raises(SystemExit, match="already exists"):
            asyncio.run(
                create(
                    Registration(
                        account=account, display_name="拒絕升權", password="local_admin_fixture_123"
                    )
                )
            )
        assert owner.get("/api/v1/auth/me").json()["user"]["role"] == "user"
        admin_account = "admin_" + uuid.uuid4().hex
        asyncio.run(
            create(
                Registration(
                    account=admin_account,
                    display_name="測試管理者",
                    password="local_admin_fixture_123",
                )
            )
        )
        with httpx.Client(base_url=os.environ["API_ORIGIN"]) as admin:
            logged_in = admin.post(
                "/api/v1/auth/login",
                headers={"Origin": ORIGIN},
                json={"account": admin_account, "password": "local_admin_fixture_123"},
            )
            assert logged_in.status_code == 200
            assert logged_in.json()["user"]["role"] == "admin"
            admin.headers.update({"Origin": ORIGIN, "X-CSRF-Token": logged_in.json()["csrf_token"]})
            assert admin.get(f"/api/v1/apps/{app_id}/draft").status_code == 200
            assert (
                admin.patch(
                    f"/api/v1/apps/{app_id}/draft",
                    json={"title": "合法管理者編輯", "expected_revision": 1},
                ).status_code
                == 200
            )
