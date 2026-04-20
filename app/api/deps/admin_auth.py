from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.rate_limit import InMemoryRateLimiter
from app.core.security import decode_access_token
from app.db import get_db
from app.db_models import AdminUser

bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def get_admin_login_limiter() -> InMemoryRateLimiter:
    """Provide shared limiter for admin login endpoint."""
    settings = get_settings()
    return InMemoryRateLimiter(limit_per_minute=settings.admin_login_rate_limit_per_minute)


def enforce_admin_login_rate_limit(
    request: Request,
    limiter: InMemoryRateLimiter = Depends(get_admin_login_limiter),
) -> None:
    """Limit admin login attempts per client IP to slow brute-force attacks."""
    client_ip = request.client.host if request.client else "unknown"
    limiter.check(f"admin_login:{client_ip}")


def require_admin_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AdminUser:
    """Validate admin bearer token and return active admin user."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
    username = decode_access_token(credentials.credentials, settings)
    admin = db.query(AdminUser).filter(AdminUser.username == username).first()
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin account.")
    return admin
