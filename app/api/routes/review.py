from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps.auth import check_rate_limit
from app.core.config import Settings, get_settings
from app.db_models import ApiKey
from app.services.llm.factory import get_llm_service
from app.utils.errors import LLMServiceError, UnsupportedProviderError
from app.models.review import ReviewRequest, ReviewResponse

router = APIRouter()


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
    3) Ask provider service to review code.
    4) Convert domain errors into stable HTTP status codes.
    """
    try:
        service = get_llm_service(settings, payload.provider)
        return await service.review_code(payload)
    except UnsupportedProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LLMServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
