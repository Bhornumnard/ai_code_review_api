import json
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["openai", "claude", "anthropic", "gemini"]


class ProviderKey(BaseModel):
    """Represent one LLM provider credential object.

    Expected shape in env JSON:
    {"provider": "<openai|claude|anthropic|gemini>", "key": "<api-key>"}
    """
    provider: ProviderName
    key: str = Field(min_length=1)


class Settings(BaseSettings):
    """Centralized runtime configuration loaded from environment variables.

    Pydantic handles type conversion/validation automatically. We also add
    custom validators for fields that can arrive as JSON strings.
    """
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = "sqlite:///./app.db"
    default_llm_provider: ProviderName = "openai"
    llm_provider_keys: list[ProviderKey] = Field(default_factory=list)
    rate_limit_requests_per_minute: int = 10
    admin_username: str = "admin"
    admin_password: str = "admin1234"
    admin_jwt_secret: str = "change-this-admin-secret"
    admin_jwt_algorithm: str = "HS256"
    admin_access_token_expire_minutes: int = 15
    admin_login_rate_limit_per_minute: int = 5

    @field_validator("llm_provider_keys", mode="before")
    @classmethod
    def parse_provider_keys(cls, value: Any) -> Any:
        """Normalize `LLM_PROVIDER_KEYS` into a Python list.

        Why this exists:
        - `.env` values are strings by default.
        - We want to accept JSON text for convenience.
        - The app logic expects a list-like structure.
        """
        if value in (None, "", []):
            return []
        if isinstance(value, str):
            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise ValueError("LLM_PROVIDER_KEYS must be a JSON array.")
            return parsed
        return value

    @property
    def llm_key_map(self) -> dict[str, str]:
        """Build a quick lookup map from provider name to API key.

        We normalize `anthropic` to `claude` so downstream code only handles
        one canonical name for the Anthropic provider.
        """
        key_map: dict[str, str] = {}
        for item in self.llm_provider_keys:
            provider = "claude" if item.provider == "anthropic" else item.provider
            key_map[provider] = item.key
        return key_map

    def validate_runtime_config(self) -> None:
        """Validate required settings before serving any request.

        Raises:
        - ValueError: when required keys are missing or malformed.
        """
        if self.default_llm_provider not in {"openai", "claude", "anthropic", "gemini"}:
            raise ValueError("DEFAULT_LLM_PROVIDER must be one of openai, claude, anthropic, gemini.")
        if not self.llm_provider_keys:
            raise ValueError("LLM_PROVIDER_KEYS must contain at least one provider key.")
        if not self.admin_jwt_secret or len(self.admin_jwt_secret) < 32:
            raise ValueError("ADMIN_JWT_SECRET must be at least 32 characters.")
        try:
            # Ensure provider keys have valid shape
            _ = [ProviderKey.model_validate(item) if isinstance(item, dict) else item for item in self.llm_provider_keys]
        except ValidationError as exc:
            raise ValueError(f"Invalid LLM_PROVIDER_KEYS format: {exc}") from exc


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    `lru_cache` ensures environment parsing is done only once per process,
    which avoids repeated parsing work on every request dependency call.
    """
    return Settings()
