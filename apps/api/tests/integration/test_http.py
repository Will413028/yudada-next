import asyncio
import os

import httpx

from scripts.seed import seed


def test_real_http_returns_migrated_database_rows() -> None:
    origin = os.environ["API_ORIGIN"]
    response = httpx.get(f"{origin}/api/v1/apps")
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "00000000-0000-4000-8000-000000000001",
            "name": "探索你的學習風格",
            "description": "認識自己的學習偏好。",
            "cover_id": None,
        }
    ]
    assert httpx.get(f"{origin}/api/v1/health").json() == {"status": "ok"}
    docs = httpx.get(f"{origin}/api/v1/docs")
    assert docs.status_code == 200
    assert "/api/v1/openapi.json" in docs.text
    assert "/api/v1/apps" in httpx.get(f"{origin}/api/v1/openapi.json").json()["paths"]


def test_api_reads_changed_database_value() -> None:
    async def update_name(name: str) -> None:
        await seed(name)

    try:
        asyncio.run(update_name("資料庫更新測試"))
        rows = httpx.get(f"{os.environ['API_ORIGIN']}/api/v1/apps").json()
        assert rows[0]["name"] == "資料庫更新測試"
    finally:
        asyncio.run(update_name("探索你的學習風格"))
