import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from data_analysis import services as data_services
from data_analysis.ai import service as ai_service
from data_analysis.ai import usage as ai_usage
from data_analysis.ai.settings import get_ai_limits_for_plan, normalize_plan_name
from data_analysis.routes.data_routes import get_storage_scope
from services.auth_service import require_regular_user_id
from services.rate_limit_service import enforce_data_workspace_rate_limit


router = APIRouter(
    prefix="/users/{user_id}/analysis",
    tags=["Analysis"],
)
logger = logging.getLogger(__name__)


class AnalysisRunRequest(BaseModel):
    input_path: str
    cleaning_actions: list[dict[str, Any]] = []
    analysis_requests: list[dict[str, Any]]
    language: str = "en"
    symbols: dict[str, Any] = {}


class AssistedAnalysisRequest(BaseModel):
    input_path: str
    cleaning_actions: list[dict[str, Any]] = []
    question: str | None = None
    metric: dict[str, Any] | None = None
    language: str = "en"
    symbols: dict[str, Any] = {}


class AIAnalysisRequest(BaseModel):
    input_path: str
    user_message: str
    cleaning_actions: list[dict[str, Any]] = []
    dataset_name: str | None = None


def _resolve_ai_plan(user_data: dict[str, Any]) -> str:
    user_type = str(user_data.get("user_type") or "user").strip().lower()

    if user_type == "admin":
        return "enterprise"

    payment_status = str(user_data.get("payment_status") or "").strip().lower()
    plan = str(user_data.get("plan") or user_data.get("subscription_type") or "").strip().lower()

    if payment_status == "active" and plan:
        return normalize_plan_name("pro" if plan not in {"free", "pro", "enterprise"} else plan)

    return "free"


def _get_ai_context(
    user_id: int,
    request: Request,
    response: Response,
) -> tuple[str, str, dict[str, Any]]:
    _, user_data = require_regular_user_id(user_id, request, response)
    tenant_id = user_data.get("tenant_id")
    scoped_user_id = user_data.get("id")

    if tenant_id is None or scoped_user_id is None:
        raise HTTPException(status_code=400, detail="User storage scope is not available.")

    return (
        data_services.safe_scope_value(tenant_id),
        data_services.safe_scope_value(scoped_user_id),
        user_data,
    )


def _limit_response(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "type": "error",
            "code": "daily_ai_message_limit_reached",
            "message": message,
        },
    )


def _result_status(result: dict[str, Any]) -> int:
    if result.get("success") is not False:
        return 200

    code = str(result.get("code") or "")

    if code in {
        "daily_ai_message_limit_reached",
        "global_free_ai_limit_reached",
        "daily_code_generation_limit_reached",
        "global_free_code_generation_limit_reached",
    }:
        return 429

    if code in {"ai_provider_error", "code_generation_failed"}:
        return 502

    if result.get("type") == "blocked":
        return 400

    return 400


@router.get("/catalog")
def analysis_catalog(user_id: int, fastapi_request: Request, response: Response, language: str = "en"):
    get_storage_scope(fastapi_request, response, user_id)
    return data_services.get_analysis_catalog(language)


@router.post("/run")
def run_analysis(user_id: int, request: AnalysisRunRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, scoped_user_id = get_storage_scope(fastapi_request, response, user_id)
        enforce_data_workspace_rate_limit(
            fastapi_request,
            scoped_user_id,
            "analysis_run",
            tenant_id=tenant_id,
        )
        return data_services.run_analysis(
            input_path=request.input_path,
            cleaning_actions=request.cleaning_actions,
            analysis_requests=request.analysis_requests,
            language=request.language,
            symbols=request.symbols,
            tenant_id=tenant_id,
            user_id=scoped_user_id,
        )

    except HTTPException:
        raise

    except Exception as error:
        logger.warning("data.analysis.run_failed", extra={"user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=400, detail="Could not run analysis.")


@router.post("/assist")
def assisted_analysis(user_id: int, request: AssistedAnalysisRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, scoped_user_id = get_storage_scope(fastapi_request, response, user_id)
        enforce_data_workspace_rate_limit(
            fastapi_request,
            scoped_user_id,
            "analysis_assist",
            tenant_id=tenant_id,
        )
        return data_services.run_assisted_analysis(
            input_path=request.input_path,
            cleaning_actions=request.cleaning_actions,
            question=request.question,
            metric=request.metric,
            language=request.language,
            symbols=request.symbols,
            tenant_id=tenant_id,
            user_id=scoped_user_id,
        )

    except HTTPException:
        raise

    except Exception as error:
        logger.warning("data.analysis.assist_failed", extra={"user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=400, detail="Could not run assisted analysis.")


@router.post("/ai")
def ai_analysis(user_id: int, request: AIAnalysisRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, scoped_user_id, user_data = _get_ai_context(user_id, fastapi_request, response)
        enforce_data_workspace_rate_limit(
            fastapi_request,
            scoped_user_id,
            "analysis_assist",
            tenant_id=tenant_id,
        )

        user_plan = _resolve_ai_plan(user_data)
        df = data_services.read_dataset(
            request.input_path,
            tenant_id=tenant_id,
            user_id=scoped_user_id,
        )

        if request.cleaning_actions:
            cleaner = data_services.build_authorized_cleaner(
                request.input_path,
                tenant_id=tenant_id,
                user_id=scoped_user_id,
            )
            df = cleaner.apply_pipeline(request.cleaning_actions)

        preflight_error = ai_service.validate_ai_request_before_provider(
            df=df,
            user_message=request.user_message,
            user_plan=user_plan,
            dataset_name=request.dataset_name or request.input_path,
        )

        if preflight_error:
            return JSONResponse(status_code=_result_status(preflight_error), content=preflight_error)

        usage_date = date.today()
        limits = get_ai_limits_for_plan(user_plan)
        daily_usage = ai_usage.get_daily_ai_usage(
            user_id=scoped_user_id,
            usage_date=usage_date,
        )
        global_usage = ai_usage.get_global_daily_ai_usage(usage_date=usage_date)

        if daily_usage["message_count"] >= limits.daily_messages:
            return _limit_response(
                "You reached today’s AI analysis limit. Try again tomorrow or upgrade for more AI analysis."
            )

        if (
            limits.global_daily_messages is not None
            and global_usage["message_count"] >= limits.global_daily_messages
        ):
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "type": "error",
                    "code": "global_free_ai_limit_reached",
                    "message": "The free AI analysis pool is busy today. Try again later or upgrade for more access.",
                },
            )

        reservation = ai_usage.reserve_daily_ai_usage(
            user_id=scoped_user_id,
            tenant_id=tenant_id,
            usage_date=usage_date,
            message_limit=limits.daily_messages,
            code_generation_limit=limits.daily_code_generations,
            message_delta=1,
            code_generation_delta=0,
        )

        if not reservation.get("accepted"):
            return _limit_response(
                "You reached today’s AI analysis limit. Try again tomorrow or upgrade for more AI analysis."
            )

        def reserve_code_generation() -> bool:
            current_global_usage = ai_usage.get_global_daily_ai_usage(usage_date=usage_date)

            if (
                limits.global_daily_code_generations is not None
                and current_global_usage["code_generation_count"] >= limits.global_daily_code_generations
            ):
                return False

            code_reservation = ai_usage.reserve_daily_ai_usage(
                user_id=scoped_user_id,
                tenant_id=tenant_id,
                usage_date=usage_date,
                message_limit=limits.daily_messages,
                code_generation_limit=limits.daily_code_generations,
                message_delta=0,
                code_generation_delta=1,
            )
            return bool(code_reservation.get("accepted"))

        result = ai_service.run_ai_analysis_on_dataframe(
            df=df,
            user_message=request.user_message,
            user_plan=user_plan,
            dataset_name=request.dataset_name or request.input_path,
            daily_messages_used=int(daily_usage["message_count"]),
            daily_code_generations_used=int(daily_usage["code_generation_count"]),
            global_daily_messages_used=int(global_usage["message_count"]),
            global_daily_code_generations_used=int(global_usage["code_generation_count"]),
            reserve_code_generation=reserve_code_generation,
        )

        return JSONResponse(status_code=_result_status(result), content=result)

    except HTTPException:
        raise

    except Exception as error:
        logger.warning("data.analysis.ai_failed", extra={"user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=400, detail="Could not run AI analysis.")
