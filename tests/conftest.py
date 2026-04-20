from collections.abc import Generator
from pathlib import Path
import sys

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.deps.auth import get_rate_limiter
from app.api.deps.admin_auth import get_admin_login_limiter
from app.api.routes.admin import router as admin_router
from app.api.routes.review import router as review_router
from app.core.config import Settings, get_settings
from app.core.security import hash_api_key, hash_password
from app.db import get_db
from app.db_models import AdminUser, ApiKey


@pytest.fixture
def test_settings() -> Settings:
    """Provide deterministic in-memory settings for all API tests."""
    return Settings(
        app_env="test",
        host="0.0.0.0",
        port=8000,
        database_url="sqlite://",
        default_llm_provider="openai",
        llm_provider_keys=[{"provider": "openai", "key": "test-openai-key"}],
        rate_limit_requests_per_minute=10,
        admin_username="admin",
        admin_password="admin1234",
        admin_jwt_secret="test-super-secret-jwt-key",
        admin_jwt_algorithm="HS256",
        admin_access_token_expire_minutes=30,
        admin_login_rate_limit_per_minute=5,
    )


@pytest.fixture
def db_session(test_settings: Settings) -> Generator[Session, None, None]:
    """Create a clean in-memory database per test function."""
    engine = create_engine(
        test_settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.db import Base

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        admin = AdminUser(
            username=test_settings.admin_username,
            password_hash=hash_password(test_settings.admin_password),
            is_active=True,
        )
        client_key = "test-client-key"
        seeded_key = ApiKey(
            name="seed-test-key",
            key_hash=hash_api_key(client_key),
            key_prefix=client_key[:10],
            is_active=True,
            expires_at=None,
            rate_limit_per_minute=10,
        )
        db.add(admin)
        db.add(seeded_key)
        db.commit()
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session: Session, test_settings: Settings) -> Generator[TestClient, None, None]:
    """Build a test app with dependency overrides and isolated state."""
    get_rate_limiter.cache_clear()
    get_admin_login_limiter.cache_clear()

    app = FastAPI(
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    app.include_router(review_router, prefix="/v1", tags=["review"])
    app.include_router(admin_router)

    def override_get_settings() -> Settings:
        return test_settings

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
