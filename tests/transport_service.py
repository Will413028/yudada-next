"""Isolated HTTP test backend; never mounted by the product API."""

import asyncio
import os
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()
active_streams = 0
stream_gate: asyncio.Event | None = None


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/apps")
async def apps(request: Request) -> list[dict[str, str]]:
    name = (
        "SSR Cookie forwarded"
        if request.cookies.get("probe_marker") == "1"
        else "Transport fixture"
    )
    return [{"id": "00000000-0000-4000-8000-000000000001", "name": name}]


@app.get("/api/v1/probe/error")
async def error() -> JSONResponse:
    return JSONResponse(
        {"code": "probe_rejected", "message": "Expected transport failure"},
        status_code=423,
        headers={"x-probe": "preserved"},
    )


@app.post("/api/v1/probe/cookie")
async def set_cookie() -> JSONResponse:
    response = JSONResponse({"status": "ok"})
    response.set_cookie("probe_marker", "1", httponly=True, samesite="lax", path="/")
    return response


@app.get("/api/v1/probe/cookie")
async def get_cookie(request: Request) -> dict[str, bool]:
    return {"forwarded": request.cookies.get("probe_marker") == "1"}


@app.get("/api/v1/probe/active")
async def active() -> dict[str, int]:
    return {"active": active_streams}


@app.get("/api/v1/probe/stream")
async def stream() -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        global active_streams, stream_gate
        active_streams += 1
        gate = asyncio.Event()
        stream_gate = gate
        try:
            yield 'event: question\ndata: {"index":1}\n\n'
            await asyncio.wait_for(gate.wait(), timeout=10)
            yield "event: completed\ndata: {}\n\n"
        finally:
            active_streams -= 1

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "cache-control": "no-cache"
            if os.environ.get("PROBE_BUFFER_STREAM")
            else "no-cache, no-transform"
        },
    )


@app.post("/api/v1/probe/release")
async def release() -> dict[str, bool]:
    if stream_gate is not None:
        stream_gate.set()
    return {"released": stream_gate is not None}
