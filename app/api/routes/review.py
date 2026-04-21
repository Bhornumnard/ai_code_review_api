from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps.auth import check_rate_limit
from app.core.config import Settings, get_settings
from app.core.security import normalize_provider
from app.db_models import ApiKey
from app.services.llm.factory import get_llm_service
from app.utils.errors import LLMServiceError, UnsupportedProviderError
from app.models.review import ProviderEnum, ProviderInfo, ProvidersResponse, ReviewRequest, ReviewResponse

router = APIRouter()

# Canonical provider names shown to callers (exclude the `anthropic` alias
# so the list stays concise; it still works as input via the Enum).
_CANONICAL_PROVIDERS: list[str] = ["openai", "claude", "gemini"]


@router.get("/providers", response_model=ProvidersResponse)
async def list_providers(settings: Settings = Depends(get_settings)) -> ProvidersResponse:
    """Return all known LLM providers and their availability.

    This endpoint requires **no authentication** and is safe to call
    before creating an API key.  Clients can use it to discover which
    providers are currently configured and which one is the default.

    A provider is marked `available: true` when an API key for it is
    present in `LLM_PROVIDER_KEYS` settings.  The `is_default` flag
    marks the provider selected when `provider` is omitted from a review
    request.
    """
    key_map = settings.llm_key_map
    default = normalize_provider(settings.default_llm_provider)

    providers = [
        ProviderInfo(
            name=name,
            available=name in key_map,
            is_default=(name == default),
        )
        for name in _CANONICAL_PROVIDERS
    ]
    return ProvidersResponse(providers=providers)


@router.post("/review", response_model=ReviewResponse)
async def review_code(
    payload: ReviewRequest,
    _: ApiKey = Depends(check_rate_limit),
    settings: Settings = Depends(get_settings),
) -> ReviewResponse:
    """Handle code review requests and return normalized review output.

    Flow:
    1) Auth + rate-limit checks run via dependencies.
    2) Resolve provider service using request provider or default.
       Returns 400 if the requested provider has no configured API key.
    3) Ask provider service to review code.
    4) Convert domain errors into stable HTTP status codes.
    """
    try:
        # Pass the enum value (a plain string) to the factory.
        provider_str = payload.provider.value if payload.provider else None
        service = get_llm_service(settings, provider_str)
        return await service.review_code(payload)
    except UnsupportedProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LLMServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
