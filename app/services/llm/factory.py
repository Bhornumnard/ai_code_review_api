from app.core.config import Settings
from app.core.security import normalize_provider
from app.services.llm.anthropic_service import AnthropicReviewService
from app.services.llm.base import BaseLLMReviewService
from app.services.llm.gemini_service import GeminiReviewService
from app.services.llm.openai_service import OpenAIReviewService
from app.utils.errors import UnsupportedProviderError


def get_llm_service(settings: Settings, provider: str | None = None) -> BaseLLMReviewService:
    """Resolve and instantiate the correct provider service object.

    Selection rules:
    - If request includes `provider`, use it.
    - Otherwise use `settings.default_llm_provider`.
    - Normalize aliases (e.g. anthropic -> claude).
    - Ensure API key exists for selected provider.
    """
    requested_provider = normalize_provider(provider or settings.default_llm_provider)
    key_map = settings.llm_key_map

    if requested_provider not in key_map:
        raise UnsupportedProviderError(f"No API key configured for provider '{requested_provider}'.")

    api_key = key_map[requested_provider]
    if requested_provider == "openai":
        return OpenAIReviewService(api_key=api_key)
    if requested_provider == "claude":
        return AnthropicReviewService(api_key=api_key)
    if requested_provider == "gemini":
        return GeminiReviewService(api_key=api_key)

    raise UnsupportedProviderError(f"Unsupported provider '{requested_provider}'.")
