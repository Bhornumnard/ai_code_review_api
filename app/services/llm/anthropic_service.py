import anyio

from app.models.review import ReviewIssue, ReviewRequest, ReviewResponse
from app.services.llm.base import BaseLLMReviewService
from app.utils.errors import LLMServiceError
from app.utils.parsing import parse_llm_review_json
from app.utils.prompts import build_review_prompt


class AnthropicReviewService(BaseLLMReviewService):
    """Code review implementation using Anthropic Claude Messages API."""

    def __init__(self, api_key: str):
        """Save provider API key for later SDK calls."""
        self.api_key = api_key

    async def review_code(self, request: ReviewRequest) -> ReviewResponse:
        """Review code with Claude and normalize output to `ReviewResponse`.

        Steps match other providers so behavior stays consistent:
        prompt build -> provider call -> JSON parse -> model response.
        """
        try:
            raw = await anyio.to_thread.run_sync(self._call_provider, request)
            parsed = parse_llm_review_json(raw)
            issues = [ReviewIssue(**item) for item in parsed.get("issues", [])]
            suggestions = [str(item) for item in parsed.get("suggestions", [])]
            return ReviewResponse(
                provider_used="claude",
                language=request.language,
                summary=parsed.get("summary", "No summary returned."),
                issues=issues,
                suggestions=suggestions,
                raw=raw,
            )
        except Exception as exc:  # pragma: no cover - network/provider runtime
            raise LLMServiceError(f"Anthropic review failed: {exc}") from exc

    def _call_provider(self, request: ReviewRequest) -> str:
        """Execute blocking Anthropic SDK request in a worker thread."""
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        prompt = build_review_prompt(
            request.language,
            request.code,
            request.context,
            request.review_language,
        )
        response = client.messages.create(
            model="claude-3-5-sonnet-latest",
            max_tokens=1000,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text if response.content else "{}"
