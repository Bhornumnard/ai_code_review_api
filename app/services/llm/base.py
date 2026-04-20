from abc import ABC, abstractmethod

from app.models.review import ReviewRequest, ReviewResponse


class BaseLLMReviewService(ABC):
    """Abstract contract that all provider implementations must follow.

    This keeps route logic provider-agnostic: route code calls one method
    regardless of whether backend provider is OpenAI, Claude, or Gemini.
    """

    @abstractmethod
    async def review_code(self, request: ReviewRequest) -> ReviewResponse:
        """Run provider-specific review and return normalized response.

        Implementations should:
        - build a provider prompt,
        - call provider SDK/API,
        - parse provider output,
        - return `ReviewResponse`.
        """
        raise NotImplementedError
