import asyncio
import os
import uuid

import httpx

from app.accounts import Registration
from scripts.create_admin import create
from tests.integration.test_accounts import register


def test_publication_review_restore_and_version_order() -> None:
    origin = os.environ["PUBLIC_ORIGIN"]
    account = "review_" + uuid.uuid4().hex
    asyncio.run(
        create(
            Registration(
                account=account, password="publication_fixture_password_123", display_name="審核者"
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
            json={
                "account": account,
                "password": "publication_fixture_password_123",
            },
        )
        assert login.status_code == 200
        admin.headers.update({"Origin": origin, "X-CSRF-Token": login.json()["csrf_token"]})
        assert owner.get("/api/v1/admin/reviews").status_code == 403
        content = {
            "questions": [
                {
                    "title": "題目",
                    "options": [
                        {"key": "A", "text": "甲", "property": "I"},
                        {"key": "B", "text": "乙", "property": "E"},
                    ],
                }
            ],
            "rules": [
                {"name": "探索型", "properties": ["I"]},
                {"name": "交流型", "properties": ["E"]},
            ],
        }
        draft = owner.post("/api/v1/apps", json={"title": "第一版", "content": content}).json()
        app_id = draft["app_id"]
        path = f"/api/v1/apps/{app_id}"
        assert other.post(path + "/submissions", json={"expected_revision": 1}).status_code == 404
        assert owner.post(path + "/submissions", json={"expected_revision": 2}).status_code == 409
        first = owner.post(path + "/submissions", json={"expected_revision": 1})
        assert first.status_code == 201
        first_id = first.json()["version_id"]
        assert owner.get(path + "/submissions").headers["cache-control"] == "no-store"
        assert other.get(path + "/submissions").headers["cache-control"] == "no-store"
        assert owner.post(path + "/submissions", json={"expected_revision": 1}).status_code == 409
        assert guest.get(path).status_code == 404
        assert guest.get(path + "/qr").status_code == 404
        assert guest.get(f"/api/v1/versions/{first_id}/questions").status_code == 404
        assert (
            admin.post(f"/api/v1/admin/reviews/{first_id}", json={"status": "approved"}).status_code
            == 200
        )
        assert (
            admin.post(f"/api/v1/admin/reviews/{first_id}", json={"status": "approved"}).status_code
            == 409
        )
        assert guest.get(path).json()["name"] == "第一版"
        assert guest.get(path).json()["share_url"] == f"{origin}/apps/{app_id}"
        qr = guest.get(path + "/qr")
        assert qr.status_code == 200 and qr.content.startswith(b"\x89PNG\r\n")
        assert [row["id"] for row in guest.get("/api/v1/apps?q=第一版").json()] == [app_id]
        answer = owner.post(
            f"/api/v1/versions/{first_id}/answers",
            headers={"Idempotency-Key": uuid.uuid4().hex},
            json={"choices": ["A"]},
        )
        assert answer.status_code == 201
        answer_id = answer.json()["id"]
        updated = owner.patch(
            path + "/draft",
            json={
                "title": "第二版",
                "content": content,
                "expected_revision": 1,
            },
        )
        assert updated.status_code == 200
        second = owner.post(path + "/submissions", json={"expected_revision": 2}).json()
        second_id = second["version_id"]
        assert guest.get(path).json()["name"] == "第一版"
        assert guest.get("/api/v1/apps?q=第二版").json() == []
        assert (
            admin.post(
                f"/api/v1/admin/reviews/{second_id}",
                json={
                    "status": "rejected",
                    "reason": "請補充介紹",
                },
            ).status_code
            == 200
        )
        assert guest.get(path).json()["version_id"] == first_id
        assert guest.get(f"/api/v1/versions/{second_id}/questions").status_code == 404
        assert owner.post(path + "/publish", json={"version_id": second_id}).status_code == 404
        third = owner.post(path + "/submissions", json={"expected_revision": 2}).json()
        third_id = third["version_id"]
        owner.patch(
            path + "/draft", json={"title": "第四版", "content": content, "expected_revision": 2}
        )
        fourth_id = owner.post(path + "/submissions", json={"expected_revision": 3}).json()[
            "version_id"
        ]
        assert (
            admin.post(
                f"/api/v1/admin/reviews/{fourth_id}", json={"status": "approved"}
            ).status_code
            == 200
        )
        assert (
            admin.post(f"/api/v1/admin/reviews/{third_id}", json={"status": "approved"}).status_code
            == 409
        )
        assert guest.get(path).json()["name"] == "第四版"
        assert owner.post(path + "/publish", json={"version_id": first_id}).status_code == 409
        assert other.delete(path).status_code == 404
        assert owner.post(path + "/unpublish").status_code == 204
        assert guest.get(path + "/qr").status_code == 404
        assert (
            admin.post(f"/api/v1/admin/reviews/{third_id}", json={"status": "approved"}).status_code
            == 409
        )
        assert owner.post(path + "/publish", json={"version_id": first_id}).status_code == 409
        assert guest.get(path).status_code == 404
        assert guest.get(f"/api/v1/versions/{first_id}/questions").status_code == 404
        assert owner.get(f"/api/v1/answers/{answer_id}").status_code == 200
        assert owner.post(path + "/publish", json={"version_id": fourth_id}).status_code == 204
        assert owner.delete(path).status_code == 204
        assert guest.get(path).status_code == 404
        assert owner.get(path + "/draft").status_code == 404
        assert (
            admin.post(f"/api/v1/admin/reviews/{third_id}", json={"status": "approved"}).status_code
            == 404
        )
        assert owner.post(path + "/restore").status_code == 204
        assert (
            admin.post(f"/api/v1/admin/reviews/{third_id}", json={"status": "approved"}).status_code
            == 409
        )
        assert guest.get(path).status_code == 404
        assert owner.get(path + "/draft").status_code == 200
        assert owner.post(path + "/publish", json={"version_id": fourth_id}).status_code == 204
        assert (
            owner.get(f"/api/v1/answers/{answer_id}").json()["result_snapshot"]["app_name"]
            == "第一版"
        )
        assert owner.delete(path).status_code == 204
