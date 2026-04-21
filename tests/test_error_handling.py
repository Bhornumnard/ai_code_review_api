"""Tests for standardised error handling.

Every non-2xx response from the API must conform to one consistent JSON shape:

  {
    "detail":  "<string>",
    "code":    "<snake_case_string>"
  }

Validation errors (422) also carry an additional `errors` list:

  {
    "detail":  "Request validation failed.",
    "code":    "validation_error",
    "errors":  [{"field": "...", "message": "..."}]
  }

These tests verify that the error envelope is applied consistently across
auth failures, rate-limit rejections, validation errors, and custom routes.
"""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.utils.exceptions import register_exception_handlers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_error_shape(body: dict, expected_code: str | None = None) -> None:
    """Assert a response body matches the standard error envelope."""
    assert "detail" in body, f"Missing 'detail' key in: {body}"
    assert "code" in body, f"Missing 'code' key in: {body}"
    assert isinstance(body["detail"], str), "'detail' must be a string"
    assert isinstance(body["code"], str), "'code' must be a string"
    if expected_code is not None:
        assert body["code"] == expected_code, (
            f"Expected code '{expected_code}', got '{body['code']}'"
        )


# ---------------------------------------------------------------------------
# Minimal test app that exercises all exception paths
# ---------------------------------------------------------------------------

@pytest.fixture
def error_test_client() -> TestClient:
    """Build a tiny app that exercises each exception type directly."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/trigger/400")
    def trigger_400():
        raise HTTPException(status_code=400, detail="bad input")

    @app.get("/trigger/401")
    def trigger_401():
        raise HTTPException(status_code=401, detail="not authenticated")

    @app.get("/trigger/404")
    def trigger_404():
        raise HTTPException(status_code=404, detail="not found")

    @app.get("/trigger/409")
    def trigger_409():
        raise HTTPException(status_code=409, detail="conflict")

    @app.get("/trigger/429")
    def trigger_429():
        raise HTTPException(status_code=429, detail="rate limit exceeded")

    @app.get("/trigger/502")
    def trigger_502():
        raise HTTPException(status_code=502, detail="upstream error")

    @app.get("/trigger/500")
    def trigger_500():
        raise RuntimeError("something went very wrong")

    @app.post("/trigger/422")
    def trigger_422(body: dict):
        pass

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Tests: error envelope shape
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status_code,expected_code", [
    (400, "bad_request"),
    (401, "unauthorized"),
    (404, "not_found"),
    (409, "conflict"),
    (429, "rate_limited"),
    (502, "bad_gateway"),
])
def test_http_exception_returns_standard_shape(error_test_client, status_code, expected_code):
    """HTTPException of any status code must return the standard envelope."""
    response = error_test_client.get(f"/trigger/{status_code}")
    assert response.status_code == status_code
    _assert_error_shape(response.json(), expected_code=expected_code)


def test_unhandled_exception_returns_500_standard_shape(error_test_client):
    """Bare Python exceptions must be caught and return 500 with standard shape."""
    response = error_test_client.get("/trigger/500")
    assert response.status_code == 500
    body = response.json()
    _assert_error_shape(body, expected_code="internal_error")
    # Must NOT leak the raw exception message to the caller.
    assert "something went very wrong" not in body["detail"]


def test_validation_error_returns_standard_shape(error_test_client):
    """Pydantic validation errors (422) must match the standard envelope."""
    # Sending a non-JSON body to a route that expects JSON triggers 422.
    response = error_test_client.post(
        "/trigger/422",
        content="not-json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    body = response.json()
    _assert_error_shape(body, expected_code="validation_error")
    assert "errors" in body, "422 body must include 'errors' list"
    assert isinstance(body["errors"], list)


def test_validation_error_detail_is_string(error_test_client):
    """Validation error 'detail' must be a plain string, not a list."""
    response = error_test_client.post(
        "/trigger/422",
        content="not-json",
        headers={"Content-Type": "application/json"},
    )
    body = response.json()
    assert isinstance(body["detail"], str)


def test_validation_error_errors_have_field_and_message(error_test_client):
    """Each item in 'errors' must have 'field' and 'message' keys."""
    response = error_test_client.post(
        "/trigger/422",
        content="not-json",
        headers={"Content-Type": "application/json"},
    )
    for err in response.json()["errors"]:
        assert "field" in err
        assert "message" in err


# ---------------------------------------------------------------------------
# Tests: real review and admin routes return the standard shape
# ---------------------------------------------------------------------------

def test_review_missing_key_returns_standard_shape(client):
    """Auth failure on /v1/review must conform to standard error envelope."""
    response = client.post("/v1/review", json={"language": "python", "code": "x"})
    assert response.status_code == 401
    _assert_error_shape(response.json(), expected_code="unauthorized")


def test_review_invalid_provider_returns_standard_shape(client):
    """Pydantic enum validation failure on /v1/review must use standard shape."""
    response = client.post(
        "/v1/review",
        headers={"X-API-Key": "test-client-key"},
        json={"language": "python", "code": "x", "provider": "unknown_llm"},
    )
    assert response.status_code == 422
    _assert_error_shape(response.json(), expected_code="validation_error")
    assert isinstance(response.json()["errors"], list)


def test_review_unconfigured_provider_returns_standard_shape(client):
    """Unconfigured provider on /v1/review must return standard 400 shape."""
    response = client.post(
        "/v1/review",
        headers={"X-API-Key": "test-client-key"},
        json={"language": "python", "code": "x", "provider": "gemini"},
    )
    assert response.status_code == 400
    _assert_error_shape(response.json(), expected_code="bad_request")


def test_admin_login_wrong_password_returns_standard_shape(client):
    """Failed admin login must return standard error envelope."""
    response = client.post(
        "/admin/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert response.status_code == 401
    _assert_error_shape(response.json(), expected_code="unauthorized")


def test_admin_missing_token_returns_standard_shape(client):
    """Missing JWT on admin routes must return standard error envelope."""
    response = client.get("/admin/keys")
    assert response.status_code == 401
    _assert_error_shape(response.json(), expected_code="unauthorized")
