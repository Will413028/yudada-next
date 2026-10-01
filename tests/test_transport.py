import os
import time

import httpx
import pytest

ORIGIN = os.environ["WEB_ORIGIN"]


def test_same_origin_preserves_non_2xx_and_headers() -> None:
    response = httpx.get(f"{ORIGIN}/api/v1/probe/error")
    assert response.status_code == 423
    assert response.headers["x-probe"] == "preserved"
    assert response.json()["code"] == "probe_rejected"


def test_set_cookie_browser_forwarding_and_ssr_forwarding() -> None:
    with httpx.Client(base_url=ORIGIN) as client:
        response = client.post("/api/v1/probe/cookie")
        assert response.status_code == 200
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=lax" in response.headers["set-cookie"]
        assert client.get("/api/v1/probe/cookie").json() == {"forwarded": True}
        page = client.get("/")
        assert page.status_code == 200
        assert "SSR Cookie forwarded" in page.text
    assert "SSR Cookie forwarded" not in httpx.get(ORIGIN).text


def test_sse_flushes_before_completion_and_cancel_releases_upstream() -> None:
    with httpx.Client(timeout=5) as client:
        with client.stream("GET", f"{ORIGIN}/api/v1/probe/stream") as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            lines = response.iter_lines()
            assert next(lines) == "event: question"
            assert next(lines) == 'data: {"index":1}'
            assert next(lines) == ""
            # Completion requires this signal; a buffering proxy times out before reaching it.
            assert client.get(f"{ORIGIN}/api/v1/probe/active").json()["active"] == 1
            assert client.post(f"{ORIGIN}/api/v1/probe/release").json() == {"released": True}
            assert next(lines) == "event: completed"
        with client.stream("GET", f"{ORIGIN}/api/v1/probe/stream") as response:
            assert next(response.iter_lines()) == "event: question"
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if client.get(f"{ORIGIN}/api/v1/probe/active").json()["active"] == 0:
                break
            time.sleep(0.05)
        assert client.get(f"{ORIGIN}/api/v1/probe/active").json()["active"] == 0


def test_sse_read_timeout_does_not_become_completion() -> None:
    with httpx.Client(timeout=httpx.Timeout(5, read=0.3)) as client:
        with client.stream("GET", f"{ORIGIN}/api/v1/probe/stream") as response:
            lines = response.iter_lines()
            assert next(lines) == "event: question"
            assert next(lines) == 'data: {"index":1}'
            assert next(lines) == ""
            with pytest.raises(httpx.ReadTimeout):
                next(lines)
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        if httpx.get(f"{ORIGIN}/api/v1/probe/active").json()["active"] == 0:
            break
        time.sleep(0.05)
    assert httpx.get(f"{ORIGIN}/api/v1/probe/active").json()["active"] == 0
