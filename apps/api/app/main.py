from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts import router as accounts_router
from app.admin import router as admin_router
from app.answers import router as answers_router
from app.db import create_engine
from app.drafts import router as drafts_router
from app.models import AppVersion, LearningApp, PublicationReview
from app.publication import router as publication_router
from app.security import public_origin
from app.uploads import router as uploads_router
from app.versions import router as versions_router


class AppSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str = ""
    cover_id: UUID | None = None


class HealthStatus(BaseModel):
    status: str


class ApiError(BaseModel):
    code: str
    message: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    public_origin()
    engine = create_engine()
    app.state.engine = engine
    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(
    title="yudada API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)
app.include_router(accounts_router)
app.include_router(drafts_router)
app.include_router(versions_router)
app.include_router(answers_router)
app.include_router(publication_router)
app.include_router(uploads_router)
app.include_router(admin_router)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={
            "code": f"http_{exc.status_code}",
            "message": str(exc.detail),
            "request_id": getattr(request.state, "request_id", ""),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "code": "validation_error",
            "message": "Request validation failed",
            "request_id": request.state.request_id,
        },
    )


@app.middleware("http")
async def private_response(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    import uuid

    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    if (
        request.url.path.startswith(
            ("/api/v1/auth", "/api/v1/me", "/api/v1/admin", "/api/v1/answers")
        )
        or request.url.path.endswith(("/draft", "/submissions"))
        or request.method not in {"GET", "HEAD", "OPTIONS"}
    ):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/v1/health", response_model=HealthStatus, responses={503: {"model": ApiError}})
async def health(request: Request) -> HealthStatus | JSONResponse:
    try:
        async with request.app.state.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"code": "database_unavailable", "message": "Service unavailable"},
        )
    return HealthStatus(status="ok")


@app.get("/api/v1/apps", response_model=list[AppSummary])
async def list_apps(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str = Query("", max_length=120),
) -> list[AppSummary]:
    async with AsyncSession(request.app.state.engine) as session:
        rows = await session.execute(
            select(
                LearningApp.id,
                AppVersion.title.label("name"),
                AppVersion.description,
                AppVersion.cover_id,
            )
            .join(AppVersion, LearningApp.active_version_id == AppVersion.id)
            .join(PublicationReview, PublicationReview.version_id == AppVersion.id)
            .where(
                LearningApp.deleted_at.is_(None),
                PublicationReview.status == "approved",
                AppVersion.app_id == LearningApp.id,
                or_(
                    AppVersion.title.contains(q, autoescape=True),
                    AppVersion.description.contains(q, autoescape=True),
                ),
            )
            .order_by(LearningApp.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [AppSummary.model_validate(row) for row in rows]
