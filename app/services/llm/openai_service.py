import json

import anyio

from app.models.review import ReviewIssue, ReviewRequest, ReviewResponse
from app.services.llm.base import BaseLLMReviewService
from app.utils.errors import LLMServiceError
from app.utils.parsing import parse_llm_review_json
from app.utils.prompts import build_review_prompt


class OpenAIReviewService(BaseLLMReviewService):
    """Code review implementation using OpenAI Chat Completions API."""

    def __init__(self, api_key: str):
        """Save provider API key for later SDK calls."""
        self.api_key = api_key

    async def review_code(self, request: ReviewRequest) -> ReviewResponse:
        """Review code with OpenAI and normalize output to `ReviewResponse`.

        Steps:
        1) Build unified review prompt from request.
        2) Call OpenAI chat completion API.
        3) Parse model output as JSON.
        4) Convert parsed data into strongly-typed response model.

        Any provider/network/parsing failure is wrapped as `LLMServiceError`
        so route layer can return consistent HTTP 502 behavior.
        """
        try:
            raw = await anyio.to_thread.run_sync(self._call_provider, request)
            parsed = parse_llm_review_json(raw)
            issues = [ReviewIssue(**item) for item in parsed.get("issues", [])]
            suggestions = [str(item) for item in parsed.get("suggestions", [])]
            return ReviewResponse(
                provider_used="openai",
                language=request.language,
                summary=parsed.get("summary", "No summary returned."),
                issues=issues,
                suggestions=suggestions,
                raw=raw,
            )
        except Exception as exc:  # pragma: no cover - network/provider runtime
            raise LLMServiceError(f"OpenAI review failed: {exc}") from exc

    def _call_provider(self, request: ReviewRequest) -> str:
        """Execute blocking OpenAI SDK request in a worker thread."""
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        prompt = build_review_prompt(
            request.language,
            request.code,
            request.context,
            request.review_language,
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert code reviewer."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content or "{}"
