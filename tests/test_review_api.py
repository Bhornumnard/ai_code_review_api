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
