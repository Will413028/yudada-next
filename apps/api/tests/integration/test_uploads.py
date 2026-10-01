import asyncio
import io
import os
import uuid

import httpx
from PIL import Image

from app.accounts import Registration
from scripts.create_admin import create
from tests.integration.test_accounts import register


def test_images_are_owner_scoped_until_publication_and_retained_for_answers() -> None:
    image = io.BytesIO()
    Image.new("RGB", (8, 9), "blue").save(image, format="PNG")
    origin = os.environ["PUBLIC_ORIGIN"]
    account = "images_" + uuid.uuid4().hex
    asyncio.run(
        create(
            Registration(
                account=account, password="images_fixture_password_123", display_name="圖片管理者"
            )
        )
    )
    with (
        httpx.Client(base_url=os.environ["API_ORIGIN"]) as owner,
        httpx.Client(base_url=os.environ["API_ORIGIN"]) as other,
        httpx.Client(base_url=os.environ["API_ORIGIN"]) as admin,
        httpx.Client(base_url=os.environ["API_ORIGIN"]) as guest,
    ):
        register(owner)
        register(other)
        login = admin.post(
            "/api/v1/auth/login",
            headers={"Origin": origin},
            json={"account": account, "password": "images_fixture_password_123"},
        )
        assert login.status_code == 200
        admin.headers.update({"Origin": origin, "X-CSRF-Token": login.json()["csrf_token"]})
        assert (
            guest.post("/api/v1/uploads?purpose=cover", content=image.getvalue()).status_code == 401
        )
        assert (
            owner.post(
                "/api/v1/uploads?purpose=cover",
                content=b"<svg/>",
                headers={"Content-Type": "image/png"},
            ).status_code
            == 422
        )
        assert (
            owner.post(
                "/api/v1/uploads?purpose=cover", content=b"x" * (1024 * 1024 + 1)
            ).status_code
            == 413
        )
        ids = {}
        for purpose in ("cover", "result", "avatar"):
            uploaded = owner.post(
                f"/api/v1/uploads?purpose={purpose}",
                content=image.getvalue(),
                headers={"X-Filename": "../../index.html"},
            )
            assert uploaded.status_code == 201
            assert uploaded.json()["media_type"] == "image/png"
            ids[purpose] = uploaded.json()["id"]
            path = f"/api/v1/uploads/{ids[purpose]}"
            assert guest.get(path).status_code == 404
            assert other.get(path).status_code == 404
            assert owner.get(path).headers["cache-control"] == "no-store"
            assert owner.get(path).headers["x-content-type-options"] == "nosniff"
            assert other.delete(path).status_code == 404
        assert (
            other.post(
                "/api/v1/apps", json={"title": "非法圖片", "cover_id": ids["cover"]}
            ).status_code
            == 422
        )
        assert (
            owner.post(
                "/api/v1/apps", json={"title": "錯誤用途", "cover_id": ids["avatar"]}
            ).status_code
            == 422
        )
        assert (
            owner.patch(
                "/api/v1/me", json={"display_name": "含頭像", "avatar_id": ids["avatar"]}
            ).status_code
            == 200
        )
        assert (
            owner.patch("/api/v1/me", json={"display_name": "保留頭像"}).json()["avatar_id"]
            == ids["avatar"]
        )
        assert (
            other.patch(
                "/api/v1/me", json={"display_name": "其他人", "avatar_id": ids["avatar"]}
            ).status_code
            == 422
        )
        content = {
            "questions": [
                {
                    "title": "圖片題目",
                    "options": [
                        {"key": "A", "text": "甲", "property": "I"},
                        {"key": "B", "text": "乙", "property": "E"},
                    ],
                }
            ],
            "rules": [
                {"name": "探索型", "properties": ["I"], "image_id": ids["result"]},
                {"name": "交流型", "properties": ["E"]},
            ],
        }
        app = owner.post(
            "/api/v1/apps", json={"title": "圖片應用", "cover_id": ids["cover"], "content": content}
        ).json()
        app_id = app["app_id"]
        version = owner.post(
            f"/api/v1/apps/{app_id}/submissions", json={"expected_revision": 1}
        ).json()["version_id"]
        assert guest.get(f"/api/v1/uploads/{ids['cover']}").status_code == 404
        assert (
            admin.post(f"/api/v1/admin/reviews/{version}", json={"status": "approved"}).status_code
            == 200
        )
        for upload_id in ids.values():
            assert guest.get(f"/api/v1/uploads/{upload_id}").status_code == 200
        answer = other.post(
            f"/api/v1/versions/{version}/answers",
            headers={"Idempotency-Key": uuid.uuid4().hex},
            json={"choices": ["A"]},
        )
        assert answer.status_code == 201
        result_path = f"/api/v1/uploads/{ids['result']}"
        original = other.get(result_path).content
        assert owner.delete(result_path).status_code == 204
        assert guest.get(result_path).content == original
        assert (
            owner.post(
                "/api/v1/apps", json={"title": "不可重新引用", "content": content}
            ).status_code
            == 422
        )
        assert owner.delete(f"/api/v1/apps/{app_id}").status_code == 204
        assert guest.get(result_path).status_code == 404
        assert other.get(result_path).status_code == 200
        assert other.get(result_path).content == original
        assert owner.get(result_path).content == original
