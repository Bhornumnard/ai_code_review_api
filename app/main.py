from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.routes.admin import router as admin_router
from app.api.routes.review import router as review_router
from app.core.config import get_settings
from app.db import SessionLocal, init_db
from app.services.auth_service import bootstrap_admin_and_keys


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Run startup checks before the API starts serving requests.

    FastAPI calls this function once when the app starts.
    We load environment settings and validate required values
    (such as API keys and provider configuration) early so the app
    fails fast with a clear error instead of failing on the first request.
    """
    settings = get_settings()
    settings.validate_runtime_config()
    init_db()
    db = SessionLocal()
    try:
        bootstrap_admin_and_keys(db, settings)
    finally:
        db.close()
    yield


app = FastAPI(
    title="AI Code Review API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)


@app.get("/health")
async def health() -> JSONResponse:
    """Return a simple status payload used by health checks.

    This endpoint is intentionally lightweight so tools like Docker,
    load balancers, or uptime monitors can quickly verify the service
    process is alive.
    """
    return JSONResponse({"status": "ok"})


app.include_router(review_router, prefix="/v1", tags=["review"])
app.include_router(admin_router)
