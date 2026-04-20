from datetime import datetime, timedelta, timezone


def _admin_token(client) -> str:
    """Login helper returning admin bearer token."""
    response = client.post(
        "/admin/auth/login",
        json={"username": "admin", "password": "admin1234"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_admin_login_fail_wrong_password(client):
    """Admin login must fail for invalid credentials."""
    response = client.post(
        "/admin/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert response.status_code == 401


def test_admin_key_management_flow(client):
    """Admin can create, list, update, and revoke API keys."""
    token = _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/admin/keys",
        headers=headers,
        json={"name": "mobile-app", "rate_limit_per_minute": 33},
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["name"] == "mobile-app"
    assert created["rate_limit_per_minute"] == 33
    assert created["api_key"].startswith("ak_live_")
    key_id = created["id"]

    list_response = client.get("/admin/keys", headers=headers)
    assert list_response.status_code == 200
    names = [item["name"] for item in list_response.json()]
    assert "mobile-app" in names

    update_response = client.patch(
        f"/admin/keys/{key_id}",
        headers=headers,
        json={"rate_limit_per_minute": 77},
    )
    assert update_response.status_code == 200
    assert update_response.json()["rate_limit_per_minute"] == 77

    revoke_response = client.post(f"/admin/keys/{key_id}/revoke", headers=headers)
    assert revoke_response.status_code == 200
    assert revoke_response.json()["is_active"] is False


def test_admin_routes_require_bearer_token(client):
    """Admin management routes must require bearer authentication."""
    response = client.get("/admin/keys")
    assert response.status_code == 401


def test_admin_routes_reject_invalid_bearer_token(client):
    """Admin management routes must reject invalid JWT access token."""
    response = client.get("/admin/keys", headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401


def test_admin_login_rate_limited(client):
    """Repeated failed admin logins should be throttled with 429."""
    for _ in range(5):
        response = client.post(
            "/admin/auth/login",
            json={"username": "admin", "password": "wrong"},
        )
        assert response.status_code == 401

    blocked = client.post(
        "/admin/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert blocked.status_code == 429


def test_admin_create_key_rejects_past_expires_at(client):
    """Creating key with past expires_at should return 400."""
    token = _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    response = client.post(
        "/admin/keys",
        headers=headers,
        json={"name": "past-expire-key", "rate_limit_per_minute": 10, "expires_at": past},
    )
    assert response.status_code == 400
    assert "future" in response.json()["detail"].lower()


def test_admin_update_key_rejects_past_expires_at(client):
    """Updating key with past expires_at should return 400."""
    token = _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    create_response = client.post(
        "/admin/keys",
        headers=headers,
        json={"name": "update-past-key", "rate_limit_per_minute": 10},
    )
    assert create_response.status_code == 200
    key_id = create_response.json()["id"]
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    response = client.patch(
        f"/admin/keys/{key_id}",
        headers=headers,
        json={"expires_at": past},
    )
    assert response.status_code == 400
    assert "future" in response.json()["detail"].lower()
