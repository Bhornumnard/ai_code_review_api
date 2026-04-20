from datetime import datetime

from pydantic import BaseModel, Field


class AdminLoginRequest(BaseModel):
    """Login payload for admin authentication."""

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AdminTokenResponse(BaseModel):
    """JWT response returned after successful admin login."""

    access_token: str
    token_type: str = "bearer"


class ApiKeyCreateRequest(BaseModel):
    """Payload for creating a managed client API key."""

    name: str = Field(min_length=2, max_length=120)
    expires_at: datetime | None = None
    rate_limit_per_minute: int = Field(default=10, ge=1, le=10000)


class ApiKeyUpdateRequest(BaseModel):
    """Payload for updating API key policy fields."""

    expires_at: datetime | None = None
    rate_limit_per_minute: int | None = Field(default=None, ge=1, le=10000)
    is_active: bool | None = None


class ApiKeyResponse(BaseModel):
    """Safe API key model for listing/updating managed keys."""

    id: int
    name: str
    key_prefix: str
    is_active: bool
    expires_at: datetime | None
    rate_limit_per_minute: int
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None


class ApiKeyCreateResponse(ApiKeyResponse):
    """Create response includes plaintext key (shown only once)."""

    api_key: str
