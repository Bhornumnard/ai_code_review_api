from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import (
    build_api_key,
    create_access_token,
    hash_api_key,
    hash_password,
    verify_password,
)
from app.db_models import AdminUser, ApiKey


def normalize_expires_at(expires_at: datetime | None) -> datetime | None:
    """Normalize expires_at value to timezone-aware UTC datetime."""
    if expires_at is None:
        return None
    if expires_at.tzinfo is None:
        return expires_at.replace(tzinfo=timezone.utc)
    return expires_at.astimezone(timezone.utc)


def ensure_not_expired(expires_at: datetime | None) -> None:
    """Reject values that are already expired at write time."""
    normalized = normalize_expires_at(expires_at)
    if normalized is not None and normalized <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="expires_at must be a future datetime.",
        )


def bootstrap_admin_and_keys(db: Session, settings: Settings) -> None:
    """Seed initial admin user on first run."""
    admin = db.query(AdminUser).filter(AdminUser.username == settings.admin_username).first()
    if admin is None:
        db.add(
            AdminUser(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                is_active=True,
            )
        )
    db.commit()


def authenticate_admin(db: Session, username: str, password: str, settings: Settings) -> str:
    """Validate admin credentials and return signed access token."""
    admin = db.query(AdminUser).filter(AdminUser.username == username).first()
    if admin is None or not admin.is_active or not verify_password(password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials.")
    return create_access_token(subject=admin.username, settings=settings)


def create_client_api_key(db: Session, name: str, expires_at: datetime | None, rate_limit_per_minute: int) -> tuple[ApiKey, str]:
    """Create a new client API key and return DB object + plaintext key."""
    if db.query(ApiKey).filter(ApiKey.name == name).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="API key name already exists.")
    expires_at = normalize_expires_at(expires_at)
    ensure_not_expired(expires_at)
    plain_key = build_api_key()
    record = ApiKey(
        name=name,
        key_hash=hash_api_key(plain_key),
        key_prefix=plain_key[:10],
        is_active=True,
        expires_at=expires_at,
        rate_limit_per_minute=rate_limit_per_minute,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record, plain_key


def get_active_api_key_record(db: Session, raw_api_key: str) -> ApiKey:
    """Resolve and validate API key state (exists, active, not expired)."""
    print('raw_api_key : ', raw_api_key)
    record = db.query(ApiKey).filter(ApiKey.key_hash == hash_api_key(raw_api_key)).first()
    print('record : ', record)
    if record is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")
    if not record.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key is inactive.")
    now_utc = datetime.now(timezone.utc)
    expires_at = normalize_expires_at(record.expires_at)
    if expires_at and expires_at <= now_utc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key has expired.")
    record.last_used_at = now_utc
    db.commit()
    return record
