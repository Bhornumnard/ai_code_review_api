import anyio

from app.models.review import ReviewIssue, ReviewRequest, ReviewResponse
from app.services.llm.base import BaseLLMReviewService
from app.utils.errors import LLMServiceError
from app.utils.parsing import parse_llm_review_json
from app.utils.prompts import build_review_prompt


class GeminiReviewService(BaseLLMReviewService):
    """Code review implementation using Google Gemini API."""

    def __init__(self, api_key: str):
        """Save provider API key for later SDK calls."""
        self.api_key = api_key

    async def review_code(self, request: ReviewRequest) -> ReviewResponse:
        """Review code with Gemini and normalize output to `ReviewResponse`.

        This keeps API response format consistent with OpenAI/Claude paths,
        even though the underlying SDK call style differs.
        """
        try:
            raw = await anyio.to_thread.run_sync(self._call_provider, request)
            parsed = parse_llm_review_json(raw)
            issues = [ReviewIssue(**item) for item in parsed.get("issues", [])]
            suggestions = [str(item) for item in parsed.get("suggestions", [])]
            return ReviewResponse(
                provider_used="gemini",
                language=request.language,
                summary=parsed.get("summary", "No summary returned."),
                issues=issues,
                suggestions=suggestions,
                raw=raw,
            )
        except Exception as exc:  # pragma: no cover - network/provider runtime
            raise LLMServiceError(f"Gemini review failed: {exc}") from exc

    def _call_provider(self, request: ReviewRequest) -> str:
        """Execute blocking Gemini SDK request in a worker thread."""
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = build_review_prompt(
            request.language,
            request.code,
            request.context,
            request.review_language,
        )
        result = model.generate_content(prompt)
        return result.text or "{}"
