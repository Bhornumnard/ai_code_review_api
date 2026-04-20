from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps.admin_auth import enforce_admin_login_rate_limit, require_admin_user
from app.core.config import Settings, get_settings
from app.db import get_db
from app.db_models import AdminUser, ApiKey
from app.models.admin import (
    AdminLoginRequest,
    AdminTokenResponse,
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    ApiKeyUpdateRequest,
)
from app.services.auth_service import authenticate_admin, create_client_api_key, ensure_not_expired, normalize_expires_at

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/auth/login", response_model=AdminTokenResponse)
def admin_login(
    payload: AdminLoginRequest,
    _: None = Depends(enforce_admin_login_rate_limit),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AdminTokenResponse:
    """Authenticate admin credentials and return JWT bearer token."""
    token = authenticate_admin(db, payload.username, payload.password, settings)
    return AdminTokenResponse(access_token=token)


@router.post("/keys", response_model=ApiKeyCreateResponse)
def create_api_key(
    payload: ApiKeyCreateRequest,
    _: AdminUser = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> ApiKeyCreateResponse:
    """Create client API key with custom expiry and per-key rate limit."""
    record, plain_key = create_client_api_key(
        db=db,
        name=payload.name,
        expires_at=payload.expires_at,
        rate_limit_per_minute=payload.rate_limit_per_minute,
    )
    return ApiKeyCreateResponse(
        id=record.id,
        name=record.name,
        key_prefix=record.key_prefix,
        is_active=record.is_active,
        expires_at=record.expires_at,
        rate_limit_per_minute=record.rate_limit_per_minute,
        created_at=record.created_at,
        updated_at=record.updated_at,
        last_used_at=record.last_used_at,
        api_key=plain_key,
    )


@router.get("/keys", response_model=list[ApiKeyResponse])
def list_api_keys(
    _: AdminUser = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> list[ApiKeyResponse]:
    """List all managed client API keys without exposing full secret values."""
    rows = db.query(ApiKey).order_by(ApiKey.id.desc()).all()
    return [
        ApiKeyResponse(
            id=row.id,
            name=row.name,
            key_prefix=row.key_prefix,
            is_active=row.is_active,
            expires_at=row.expires_at,
            rate_limit_per_minute=row.rate_limit_per_minute,
            created_at=row.created_at,
            updated_at=row.updated_at,
            last_used_at=row.last_used_at,
        )
        for row in rows
    ]


@router.patch("/keys/{key_id}", response_model=ApiKeyResponse)
def update_api_key(
    key_id: int,
    payload: ApiKeyUpdateRequest,
    _: AdminUser = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> ApiKeyResponse:
    """Update selected policy fields for an existing client API key."""
    row = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found.")

    if payload.expires_at is not None:
        expires_at = normalize_expires_at(payload.expires_at)
        ensure_not_expired(expires_at)
        row.expires_at = expires_at
    if payload.rate_limit_per_minute is not None:
        row.rate_limit_per_minute = payload.rate_limit_per_minute
    if payload.is_active is not None:
        row.is_active = payload.is_active

    db.commit()
    db.refresh(row)
    return ApiKeyResponse(
        id=row.id,
        name=row.name,
        key_prefix=row.key_prefix,
        is_active=row.is_active,
        expires_at=row.expires_at,
        rate_limit_per_minute=row.rate_limit_per_minute,
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_used_at=row.last_used_at,
    )


@router.post("/keys/{key_id}/revoke", response_model=ApiKeyResponse)
def revoke_api_key(
    key_id: int,
    _: AdminUser = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> ApiKeyResponse:
    """Revoke key by setting active status to false."""
    row = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found.")
    row.is_active = False
    db.commit()
    db.refresh(row)
    return ApiKeyResponse(
        id=row.id,
        name=row.name,
        key_prefix=row.key_prefix,
        is_active=row.is_active,
        expires_at=row.expires_at,
        rate_limit_per_minute=row.rate_limit_per_minute,
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_used_at=row.last_used_at,
    )
