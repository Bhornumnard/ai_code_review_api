from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.rate_limit import InMemoryRateLimiter
from app.core.security import x_api_key_header
from app.db import get_db
from app.db_models import ApiKey
from app.services.auth_service import get_active_api_key_record


@lru_cache
def get_rate_limiter() -> InMemoryRateLimiter:
    """Create and cache one shared limiter for the whole process.

    We cache this so all requests use the same in-memory counters.
    If we recreated limiter per request, rate limiting would not work.
    """
    settings = get_settings()
    return InMemoryRateLimiter(limit_per_minute=settings.rate_limit_requests_per_minute)


def require_api_key(
    x_api_key: str | None = Depends(x_api_key_header),
    db: Session = Depends(get_db),
) -> ApiKey:
    """Authorize request by validating `X-API-Key`.

    Returns the validated API key record so downstream dependencies can use it
    (for example, as the rate-limit key).
    """
    if x_api_key is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header.")
    return get_active_api_key_record(db, x_api_key)


def check_rate_limit(
    api_key: ApiKey = Depends(require_api_key),
    limiter: InMemoryRateLimiter = Depends(get_rate_limiter),
) -> ApiKey:
    """Apply rate-limit check after auth and before endpoint logic.

    Dependency order:
    1) `require_api_key` validates caller identity.
    2) `check_rate_limit` counts usage for that key.
    3) Endpoint runs only when both checks pass.
    """
    limiter.check(f"api_key:{api_key.id}", api_key.rate_limit_per_minute)
    return api_key
