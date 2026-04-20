import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Header, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import Settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def normalize_provider(provider: str) -> str:
    """Normalize provider text to a canonical internal name.

    Example:
    - 'Anthropic' -> 'claude'
    - ' OPENAI ' -> 'openai'
    """
    value = provider.strip().lower()
    if value == "anthropic":
        return "claude"
    return value


def validate_api_key(x_api_key: str | None, settings: Settings) -> str:
    """Validate the incoming API key used to call this service.

    This is the gateway-level auth key (client -> this API), not the
    downstream provider key (this API -> OpenAI/Claude/Gemini).
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header.",
        )
    if x_api_key not in settings.api_auth_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )
    return x_api_key


def x_api_key_header(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str | None:
    """Read the `X-API-Key` header value from the request.

    FastAPI injects this automatically when used as a dependency.
    We keep it in a dedicated function to keep endpoint signatures clean.
    """
    return x_api_key


def hash_api_key(raw_key: str) -> str:
    """Hash a client API key with SHA-256 before persisting/comparing."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def build_api_key(prefix: str = "ak_live") -> str:
    """Generate a new random API key and return the plaintext value once."""
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def hash_password(password: str) -> str:
    """Hash admin password using bcrypt via passlib context."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify admin password against persisted bcrypt hash."""
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(subject: str, settings: Settings) -> str:
    """Create signed JWT token for admin auth with expiration."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.admin_access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.admin_jwt_secret, algorithm=settings.admin_jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> str:
    """Decode JWT and return subject username if token is valid."""
    try:
        payload = jwt.decode(token, settings.admin_jwt_secret, algorithms=[settings.admin_jwt_algorithm])
        subject = payload.get("sub")
        if not subject:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.")
        return str(subject)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.") from exc
