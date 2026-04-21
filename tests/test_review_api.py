from datetime import datetime, timedelta, timezone

from app.db_models import ApiKey
from app.models.review import ReviewIssue, ReviewResponse


class DummyReviewService:
    """Test double for LLM service to avoid external API calls."""

    async def review_code(self, request):
        return ReviewResponse(
            provider_used=request.provider or "openai",
            language=request.language,
            summary="Test summary",
            issues=[ReviewIssue(severity="low", message="Minor issue", line=1)],
            suggestions=["Improve naming."],
            raw='{"summary":"Test summary"}',
        )


def test_review_requires_api_key(client):
    """Review route must reject requests without X-API-Key."""
    response = client.post(
        "/v1/review",
        json={"language": "python", "code": "print('ok')"},
    )
    assert response.status_code == 401
    assert "Missing X-API-Key" in response.json()["detail"]


def test_review_success(client, monkeypatch):
    """Review route should return normalized payload for valid key."""
    monkeypatch.setattr("app.api.routes.review.get_llm_service", lambda settings, provider: DummyReviewService())

    response = client.post(
        "/v1/review",
        headers={"X-API-Key": "test-client-key"},
        json={"language": "python", "code": "print('ok')"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider_used"] == "openai"
    assert payload["language"] == "python"
    assert payload["summary"] == "Test summary"


def test_review_accepts_review_language_th(client, monkeypatch):
    """Review route should accept review_language=th payload."""
    monkeypatch.setattr("app.api.routes.review.get_llm_service", lambda settings, provider: DummyReviewService())
    response = client.post(
        "/v1/review",
        headers={"X-API-Key": "test-client-key"},
        json={"language": "python", "code": "print('ok')", "review_language": "th"},
    )
    assert response.status_code == 200


def test_review_rejects_invalid_review_language(client):
    """Invalid review_language should fail request validation."""
    response = client.post(
        "/v1/review",
        headers={"X-API-Key": "test-client-key"},
        json={"language": "python", "code": "print('ok')", "review_language": "jp"},
    )
    assert response.status_code == 422


def test_review_accepts_valid_provider_enum(client, monkeypatch):
    """Review route should accept provider values from the enum."""
    monkeypatch.setattr("app.api.routes.review.get_llm_service", lambda settings, provider: DummyReviewService())
    for provider in ("openai", "claude", "anthropic", "gemini"):
        response = client.post(
            "/v1/review",
            headers={"X-API-Key": "test-client-key"},
            json={"language": "python", "code": "print('ok')", "provider": provider},
        )
        # DummyReviewService is used so the only constraint is the enum validation.
        assert response.status_code == 200, f"provider={provider} got {response.status_code}"


def test_review_rejects_unknown_provider(client):
    """Unknown provider value must fail Pydantic validation (422)."""
    response = client.post(
        "/v1/review",
        headers={"X-API-Key": "test-client-key"},
        json={"language": "python", "code": "print('ok')", "provider": "gpt4"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /v1/providers
# ---------------------------------------------------------------------------

def test_providers_no_auth_required(client):
    """Providers endpoint must be accessible without any API key."""
    response = client.get("/v1/providers")
    assert response.status_code == 200


def test_providers_returns_all_canonical_providers(client):
    """Response must include openai, claude and gemini entries."""
    response = client.get("/v1/providers")
    names = {p["name"] for p in response.json()["providers"]}
    assert {"openai", "claude", "gemini"} == names


def test_providers_marks_configured_provider_available(client):
    """Provider with a key in settings must be marked available=true."""
    response = client.get("/v1/providers")
    providers = {p["name"]: p for p in response.json()["providers"]}
    # test_settings only configures openai
    assert providers["openai"]["available"] is True
    assert providers["claude"]["available"] is False
    assert providers["gemini"]["available"] is False


def test_providers_marks_default_correctly(client):
    """Default provider must have is_default=true; others must not."""
    response = client.get("/v1/providers")
    providers = {p["name"]: p for p in response.json()["providers"]}
    # test_settings sets default_llm_provider="openai"
    assert providers["openai"]["is_default"] is True
    assert providers["claude"]["is_default"] is False
    assert providers["gemini"]["is_default"] is False


def test_providers_multiple_keys_all_marked_available(test_settings, db_session):
    """All providers with configured keys must be marked available."""
    import pytest
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.deps.auth import get_rate_limiter
    from app.api.deps.admin_auth import get_admin_login_limiter
    from app.api.routes.review import router as review_router
    from app.db import get_db
    from app.core.config import Settings, get_settings

    multi_settings = Settings(
        app_env="test",
        database_url="sqlite://",
        default_llm_provider="gemini",
        llm_provider_keys=[
            {"provider": "openai", "key": "key-a"},
            {"provider": "claude", "key": "key-b"},
            {"provider": "gemini", "key": "key-c"},
        ],
        admin_username="admin",
        admin_password="admin1234",
        admin_jwt_secret="test-super-secret-jwt-key-32chars",
        admin_jwt_algorithm="HS256",
        admin_access_token_expire_minutes=30,
        admin_login_rate_limit_per_minute=5,
    )
    get_rate_limiter.cache_clear()
    get_admin_login_limiter.cache_clear()
    app = FastAPI()
    app.include_router(review_router, prefix="/v1", tags=["review"])
    app.dependency_overrides[get_settings] = lambda: multi_settings
    app.dependency_overrides[get_db] = lambda: db_session

    with TestClient(app) as c:
        response = c.get("/v1/providers")

    assert response.status_code == 200
    providers = {p["name"]: p for p in response.json()["providers"]}
    assert providers["openai"]["available"] is True
    assert providers["claude"]["available"] is True
    assert providers["gemini"]["available"] is True
    assert providers["gemini"]["is_default"] is True
    assert providers["openai"]["is_default"] is False


def test_review_returns_400_for_unconfigured_provider(client):
    """Requesting a provider with no API key must return 400 (not 422)."""
    # test_settings only has openai key; claude and gemini are unconfigured.
    response = client.post(
        "/v1/review",
        headers={"X-API-Key": "test-client-key"},
        json={"language": "python", "code": "print('ok')", "provider": "gemini"},
    )
    assert response.status_code == 400
    assert "gemini" in response.json()["detail"].lower()


def test_review_rate_limit_per_key(client, db_session, monkeypatch):
    """Second request should fail when key-specific limit is 1/min."""
    monkeypatch.setattr("app.api.routes.review.get_llm_service", lambda settings, provider: DummyReviewService())

    key = db_session.query(ApiKey).filter(ApiKey.name == "seed-test-key").first()
    assert key is not None
    key.rate_limit_per_minute = 1
    db_session.commit()

    ok = client.post(
        "/v1/review",
        headers={"X-API-Key": "test-client-key"},
        json={"language": "javascript", "code": "console.log('ok')"},
    )
    assert ok.status_code == 200

    blocked = client.post(
        "/v1/review",
        headers={"X-API-Key": "test-client-key"},
        json={"language": "javascript", "code": "console.log('again')"},
    )
    assert blocked.status_code == 429


def test_review_rejects_expired_key(client, db_session):
    """Expired API key should be rejected with 401."""
    key = db_session.query(ApiKey).filter(ApiKey.name == "seed-test-key").first()
    assert key is not None
    key.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    response = client.post(
        "/v1/review",
        headers={"X-API-Key": "test-client-key"},
        json={"language": "python", "code": "print('x')"},
    )
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()
