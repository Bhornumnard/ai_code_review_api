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

## Quick Demo

This demo shows the full flow in 4 steps: check providers -> admin login -> create client API key -> call review API.

0) Check which providers are available (no auth needed):

```bash
curl -s http://localhost:8000/v1/providers | python3 -m json.tool
```

1) Login as admin:

```bash
curl -s -X POST "http://localhost:8000/admin/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}'
```

Copy `access_token` from response.

2) Create a client API key:

```bash
curl -s -X POST "http://localhost:8000/admin/keys" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"name":"demo-key","rate_limit_per_minute":10}'
```

Copy `api_key` from response (`api_key` is shown once).

3) Call review endpoint using `X-API-Key`:

```bash
curl -s -X POST "http://localhost:8000/v1/review" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <api_key>" \
  -d '{"language":"python","code":"print(\"hello\")","provider":"openai","review_language":"en"}'
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

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | — | Service health check |
| `GET` | `/v1/providers` | — | List available LLM providers |
| `POST` | `/v1/review` | `X-API-Key` | Review code with LLM |
| `GET` | `/api/docs` | — | Swagger UI |
| `GET` | `/api/redoc` | — | ReDoc |
| `GET` | `/api/openapi.json` | — | OpenAPI schema |
| `POST` | `/admin/auth/login` | — | Admin login (returns JWT) |
| `POST` | `/admin/keys` | Bearer JWT | Create client API key |
| `GET` | `/admin/keys` | Bearer JWT | List client API keys |
| `PATCH` | `/admin/keys/{id}` | Bearer JWT | Update key expiry / rate limit |
| `POST` | `/admin/keys/{id}/revoke` | Bearer JWT | Revoke key |

### GET /v1/providers

No authentication required. Returns each known provider with its availability status and whether it is the default.

```bash
curl -s http://localhost:8000/v1/providers
```

Response:

```json
{
  "providers": [
    { "name": "openai",  "available": true,  "is_default": true  },
    { "name": "claude",  "available": false, "is_default": false },
    { "name": "gemini",  "available": false, "is_default": false }
  ]
}
```

### POST /v1/review — Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `language` | `"python"` \| `"javascript"` | ✅ | Code language |
| `code` | `string` | ✅ | Source code to review |
| `provider` | `"openai"` \| `"claude"` \| `"anthropic"` \| `"gemini"` | — | LLM provider (default: `openai`) |
| `review_language` | `"en"` \| `"th"` | — | Output language (default: `en`) |
| `context` | `string` | — | Extra context for the reviewer |

```json
{
  "language": "python",
  "code": "def add(a, b):\n    return a+b",
  "provider": "openai",
  "review_language": "en",
  "context": "Simple utility function"
}
```

Returns `400` if the requested `provider` has no API key configured.

### POST /v1/review — Response

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