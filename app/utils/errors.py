class LLMServiceError(Exception):
    """Raised when an LLM provider call fails."""


class UnsupportedProviderError(Exception):
    """Raised when the requested provider is not supported."""
