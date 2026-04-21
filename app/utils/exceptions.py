"""Centralised exception handling for the AI Code Review API.

All HTTP responses, regardless of origin, are normalised here into one
consistent JSON envelope so clients always know what shape to expect.

Response contract
-----------------
Every error response is a JSON object with these top-level keys:

  {
    "detail":  "<human-readable message>",   # always a string
    "code":    "<snake_case_error_code>"      # always present
  }

Validation errors (422) additionally include a field-level breakdown:

  {
    "detail":  "Request validation failed.",
    "code":    "validation_error",
    "errors":  [{"field": "body -> foo", "message": "..."}]
  }

Without this module the default FastAPI/Starlette behaviour is:
- HTTPException        -> {"detail": "<string or dict>"}
- RequestValidationError -> {"detail": [<list of dicts>]}   <- inconsistent
- Unhandled Exception  -> {"detail": "Internal Server Error"} or raw traceback
"""

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared response model (for OpenAPI schema documentation only)
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    """Standard error envelope returned on every non-2xx response.

    Using a single shape lets API clients write one error-handling branch
    instead of branching on status code to figure out the body structure.
    """
    detail: str
    code: str


class ValidationErrorItem(BaseModel):
    """Single field-level validation failure inside a 422 response."""
    field: str
    message: str


class ValidationErrorResponse(BaseModel):
    """Extended error envelope for request validation failures (HTTP 422)."""
    detail: str
    code: str
    errors: list[ValidationErrorItem]


# ---------------------------------------------------------------------------
# Error codes (machine-readable constants used in `code` field)
# ---------------------------------------------------------------------------

CODE_VALIDATION_ERROR = "validation_error"
CODE_NOT_FOUND = "not_found"
CODE_UNAUTHORIZED = "unauthorized"
CODE_FORBIDDEN = "forbidden"
CODE_CONFLICT = "conflict"
CODE_RATE_LIMITED = "rate_limited"
CODE_BAD_GATEWAY = "bad_gateway"
CODE_BAD_REQUEST = "bad_request"
CODE_INTERNAL_ERROR = "internal_error"

# Map HTTP status codes to default machine-readable error codes.
_STATUS_CODE_MAP: dict[int, str] = {
    400: CODE_BAD_REQUEST,
    401: CODE_UNAUTHORIZED,
    403: CODE_FORBIDDEN,
    404: CODE_NOT_FOUND,
    409: CODE_CONFLICT,
    422: CODE_VALIDATION_ERROR,
    429: CODE_RATE_LIMITED,
    502: CODE_BAD_GATEWAY,
}


def _code_for_status(status_code: int) -> str:
    """Return the canonical error code for a given HTTP status code."""
    return _STATUS_CODE_MAP.get(status_code, CODE_INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Normalise FastAPI/Starlette HTTPException into the standard envelope.

    Before this handler:  {"detail": "some message"}       (status varies)
    After this handler:   {"detail": "...", "code": "..."} (same status)

    The `code` is derived from the HTTP status; no caller-side changes needed.
    """
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail, "code": _code_for_status(exc.status_code)},
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Normalise Pydantic request validation errors into the standard envelope.

    FastAPI's default 422 body looks like:
        {"detail": [{"type": "...", "loc": [...], "msg": "..."}]}

    After this handler the body is:
        {
          "detail": "Request validation failed.",
          "code":   "validation_error",
          "errors": [{"field": "body -> field_name", "message": "..."}]
        }

    Field paths use " -> " as a separator so "body > language" becomes
    "body -> language", which reads more naturally in API docs / clients.
    """
    errors: list[dict] = []
    for error in exc.errors():
        loc_parts = [str(part) for part in error.get("loc", [])]
        field = " -> ".join(loc_parts) if loc_parts else "unknown"
        errors.append({"field": field, "message": error.get("msg", "Invalid value.")})

    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed.",
            "code": CODE_VALIDATION_ERROR,
            "errors": errors,
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch all unhandled exceptions and return a safe 500 response.

    Why this matters:
    - Without a catch-all, FastAPI returns a raw "Internal Server Error" or
      even a traceback if debug mode is on, potentially leaking internals.
    - We log the full exception here so developers can diagnose from logs
      without exposing details to callers.
    """
    logger.exception(
        "Unhandled exception on %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected error occurred. Please try again later.",
            "code": CODE_INTERNAL_ERROR,
        },
    )


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_exception_handlers(app: FastAPI) -> None:
    """Attach all standard exception handlers to the FastAPI application.

    Call this once after creating the `FastAPI` instance, before starting
    the server.  Order matters: FastAPI matches the most specific handler
    first, so `RequestValidationError` (subclass of `ValueError`) must be
    registered before the bare `Exception` catch-all.
    """
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)  # type: ignore[arg-type]
