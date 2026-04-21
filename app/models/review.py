from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ProviderEnum(str, Enum):
    """Supported LLM provider names accepted by the API.

    `anthropic` is kept as an accepted alias for `claude` so existing
    callers do not break if they already use either spelling.
    """
    openai = "openai"
    gemini = "gemini"
    claude = "claude"
    anthropic = "anthropic"


class ProviderInfo(BaseModel):
    """Metadata for a single available LLM provider.

    `available` is True when a matching API key is found in settings.
    `is_default` marks the provider that will be used when none is
    specified in the review request.
    """
    name: str
    available: bool
    is_default: bool


class ProvidersResponse(BaseModel):
    """Response shape for `GET /v1/providers`.

    Lists every known provider alongside whether it is currently
    configured so clients can decide which provider to request.
    """
    providers: list[ProviderInfo]


class ReviewRequest(BaseModel):
    """Incoming request body for `/v1/review`.

    - `language`: controls prompt style and validation.
    - `code`: source code to analyze.
    - `provider`: optional override; must be a configured provider.
      Default provider is used if omitted.
    - `context`: optional extra explanation from caller.
    - `review_language`: output language for review text (`en` or `th`).
    """
    language: Literal["python", "javascript"]
    code: str = Field(min_length=1)
    provider: ProviderEnum | None = None
    context: str | None = None
    review_language: Literal["en", "th"] = "en"


class ReviewIssue(BaseModel):
    """One review issue item returned by LLM and normalized by API.

    `line` is optional because some models may describe issues globally
    without exact line numbers.
    """
    severity: Literal["low", "medium", "high"]
    message: str
    line: int | None = None


class ReviewResponse(BaseModel):
    """Standardized response shape returned to API clients.

    Keeping one stable schema lets clients switch providers without changing
    frontend/backend integration code.
    """
    provider_used: str
    language: str
    summary: str
    issues: list[ReviewIssue]
    suggestions: list[str]
    raw: str | None = None
