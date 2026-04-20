from typing import Literal

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    """Incoming request body for `/v1/review`.

    - `language`: controls prompt style and validation.
    - `code`: source code to analyze.
    - `provider`: optional override; default provider is used if omitted.
    - `context`: optional extra explanation from caller.
    - `review_language`: output language for review text (`en` or `th`).
    """
    language: Literal["python", "javascript"]
    code: str = Field(min_length=1)
    provider: Literal["openai", "claude", "anthropic", "gemini"] | None = None
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
