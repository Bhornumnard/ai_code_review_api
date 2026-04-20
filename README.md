# ai_code_review_api

AI Code Review API is a backend service built with FastAPI and Python that reviews source code through JSON-based HTTP APIs.

## Features

- FastAPI backend in Python
- Reviews Python and JavaScript code
- Multi-provider LLM selection: OpenAI, Anthropic (Claude), Google Gemini
- Default provider is OpenAI when `provider` is not passed
- API key authentication via `X-API-Key`
- Per-key expiration and per-key rate limit policies
- Separate admin authentication (JWT) for key management routes
- Docker-ready setup

## Provider Key Format

Configure LLM provider keys as a JSON array:

```env
LLM_PROVIDER_KEYS=[{"provider":"openai","key":"..."},{"provider":"claude","key":"..."},{"provider":"gemini","key":"..."}]
```

Supported provider values:

- `openai`
- `claude` (or `anthropic`)
- `gemini`

## Local Setup

1. Install `uv` (if not already installed).
2. Sync project dependencies.
3. Create `.env` from `.env.example`.
4. Run the server.

```bash
uv sync --all-groups
cp .env.example .env
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Dependency Management (uv)

- Main dependencies are defined in `pyproject.toml`
- Lockfile is managed in `uv.lock`
- Add package: `uv add <package>`
- Add dev package: `uv add --dev <package>`
- Update lockfile: `uv lock`
- Run tests: `uv run pytest -q`

## Required Environment Variables

Example values are provided in `.env.example`.

- `DEFAULT_LLM_PROVIDER` (default: `openai`)
- `LLM_PROVIDER_KEYS` (JSON array with `{provider,key}`)
- `DATABASE_URL` (default: `sqlite:///./app.db`)
- `ADMIN_USERNAME`, `ADMIN_PASSWORD`
- `ADMIN_JWT_SECRET`, `ADMIN_JWT_ALGORITHM`, `ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES`
- `ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE` (default: `5`)
- `RATE_LIMIT_REQUESTS_PER_MINUTE` (default: `10`)

## API Endpoints

- `GET /health` -> service health check
- `GET /api/docs` -> Swagger UI
- `GET /api/redoc` -> ReDoc
- `GET /api/openapi.json` -> OpenAPI schema
- `POST /v1/review` -> review code
- `POST /admin/auth/login` -> admin login (returns bearer token)
- `POST /admin/keys` -> create client API key (admin only)
- `GET /admin/keys` -> list client API keys (admin only)
- `PATCH /admin/keys/{id}` -> update expiry, active, rate limit (admin only)
- `POST /admin/keys/{id}/revoke` -> revoke key (admin only)

### Request Example

```json
{
  "language": "python",
  "code": "def add(a, b):\n    return a+b",
  "provider": "openai",
  "review_language": "en",
  "context": "Simple utility function"
}
```

### Response Example

```json
{
  "provider_used": "openai",
  "language": "python",
  "summary": "The code works, but style and validation can be improved.",
  "issues": [
    {
      "severity": "low",
      "message": "Missing spacing around operator.",
      "line": 2
    }
  ],
  "suggestions": [
    "Use PEP 8 spacing around operators.",
    "Add input type validation if needed."
  ],
  "raw": "{\"summary\":\"...\",\"issues\":[],\"suggestions\":[]}"
}
```

## Authentication

### Client API Authentication

Pass API key in request header:

```http
X-API-Key: your-api-key
```

Requests with missing or invalid keys return `401 Unauthorized`.

Note: client API keys for `/v1/review` must be created via admin endpoints (`/admin/keys`).

### Admin Authentication

Login to get JWT:

```json
POST /admin/auth/login
{
  "username": "admin",
  "password": "your-password"
}
```

Use returned access token:

```http
Authorization: Bearer <access_token>
```

## Rate Limiting

Each API key has its own `rate_limit_per_minute` policy.
Exceeding the key limit returns `429 Too Many Requests`.

## Docker Usage

```bash
cp .env.example .env
docker compose up --build
```

Service runs at `http://localhost:8000`.