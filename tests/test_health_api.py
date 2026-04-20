def test_health_ok(client):
    """Health endpoint should return ok status payload."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_swagger_docs_path_available(client):
    """Swagger UI should be exposed at custom docs path."""
    response = client.get("/api/docs")
    assert response.status_code == 200
    assert "Swagger UI" in response.text


def test_redoc_path_available(client):
    """ReDoc should be exposed at custom redoc path."""
    response = client.get("/api/redoc")
    assert response.status_code == 200
    assert "ReDoc" in response.text


def test_openapi_schema_path_available(client):
    """OpenAPI JSON should be exposed at configured schema path."""
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["openapi"].startswith("3.")
    assert payload["info"]["title"] == "FastAPI"
