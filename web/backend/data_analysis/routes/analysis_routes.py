import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from data_analysis import services as data_services
from data_analysis.ai import service as ai_service
from data_analysis.ai import usage as ai_usage
from data_analysis.ai.settings import get_model_config_for_plan
from data_analysis.ai import token_metering
from data_analysis.routes.data_routes import get_storage_scope
from services import entitlement_service
from services.entitlement_service import require_entitlement
from services.rate_limit_service import enforce_data_workspace_rate_limit
from services.tenant_service import require_active_tenant_user_id


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


def _resolve_ai_plan(tenant_id: int | str) -> str:
    # These are internal execution profiles, not commercial plan identifiers.
    # Business already maps to "pro" in the AI runtime; its canonical expanded
    # analysis capability carries that behavior to Business Plus centrally.
    entitlements = entitlement_service.get_tenant_entitlements(tenant_id)
    return (
        "pro"
        if "expanded_data_analysis" in entitlements.get("capabilities", [])
        else "free"
    )


def _get_ai_context(
    user_id: int,
    request: Request,
    response: Response,
) -> tuple[str, str, dict[str, Any]]:
    context = require_active_tenant_user_id(user_id, request, response)
    require_entitlement(context.tenant_id, "standard_data_analysis")
    require_entitlement(context.tenant_id, "ai_analytics")
    user_data = context.user
    tenant_id = context.tenant_id
    scoped_user_id = context.user_id

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
    tenant_id, _ = get_storage_scope(fastapi_request, response, user_id)
    require_entitlement(tenant_id, "standard_data_analysis")
    return data_services.get_analysis_catalog(language)


@router.post("/run")
def run_analysis(user_id: int, request: AnalysisRunRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, scoped_user_id = get_storage_scope(fastapi_request, response, user_id)
        require_entitlement(tenant_id, "standard_data_analysis")
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
        require_entitlement(tenant_id, "standard_data_analysis")
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
    token_reservation_id = ""
    try:
        tenant_id, scoped_user_id, user_data = _get_ai_context(user_id, fastapi_request, response)
        enforce_data_workspace_rate_limit(
            fastapi_request,
            scoped_user_id,
            "analysis_assist",
            tenant_id=tenant_id,
        )

        user_plan = _resolve_ai_plan(tenant_id)
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

        model_config = get_model_config_for_plan(user_plan)
        multipliers = token_metering.get_model_multipliers(
            model_config.provider,
            model_config.model,
        )
        # Reserve conservatively for a planner and optional code-generator call.
        # Finalization releases the unused capacity using provider metadata.
        maximum_standard_tokens = token_metering.normalize_standard_tokens(
            input_tokens=40_000,
            cached_input_tokens=0,
            output_tokens=model_config.max_output_tokens * 2,
            multipliers=multipliers,
        )
        supplied_request_id = str(
            fastapi_request.headers.get("Idempotency-Key")
            or fastapi_request.headers.get("X-Request-ID")
            or ""
        ).strip()
        reservation = token_metering.reserve_tokens(
            tenant_id=int(tenant_id),
            user_id=int(scoped_user_id),
            operation_type="analytics",
            maximum_standard_tokens=maximum_standard_tokens,
            request_id=supplied_request_id or None,
        )
        token_reservation_id = str(reservation.get("request_id") or "")

        captured_usage: list[dict[str, Any]] = []
        try:
            with token_metering.capture_provider_usage() as captured_usage:
                result = ai_service.run_ai_analysis_on_dataframe(
                    df=df,
                    user_message=request.user_message,
                    user_plan=user_plan,
                    dataset_name=request.dataset_name or request.input_path,
                    # Legacy question counters no longer determine commercial access.
                    # Zeros retain non-commercial row/code safety checks in the AI service.
                    daily_messages_used=0,
                    daily_code_generations_used=0,
                    global_daily_messages_used=0,
                    global_daily_code_generations_used=0,
                    reserve_code_generation=lambda: True,
                )
        except Exception:
            # A provider exception consumes nothing when usage is unknown. If the
            # provider already reported usage, charge only that confirmed amount.
            if captured_usage:
                failed_usage = token_metering.aggregate_usage(
                    captured_usage,
                    fallback_input={},
                    fallback_output={},
                    provider=model_config.provider,
                    model=model_config.model,
                )
                token_metering.finalize_tokens(
                    token_reservation_id,
                    failed_usage,
                    request_status="provider_error",
                )
                token_reservation_id = ""
            raise

        provider_attempt_succeeded = result.get("code") not in {
            "ai_provider_error",
            "code_generation_failed",
        }
        if captured_usage or provider_attempt_succeeded:
            usage_record = token_metering.aggregate_usage(
                captured_usage,
                fallback_input={
                    "question": request.user_message,
                    "dataset_name": request.dataset_name or request.input_path,
                },
                fallback_output=result,
                provider=model_config.provider,
                model=model_config.model,
            )
            consumed = token_metering.finalize_tokens(
                token_reservation_id,
                usage_record,
                request_status="succeeded" if result.get("success") is not False else "failed",
            )
            result["token_usage"] = {
                "standard_tokens": consumed,
                "estimated": usage_record["estimated"],
                "source": usage_record["usage_source"],
            }
        else:
            token_metering.release_tokens(token_reservation_id)

        return JSONResponse(status_code=_result_status(result), content=result)

    except HTTPException:
        raise

    except Exception as error:
        if token_reservation_id:
            try:
                token_metering.release_tokens(token_reservation_id)
            except Exception:
                logger.warning(
                    "data.analysis.ai_token_release_failed",
                    extra={"user_id": user_id, "error_type": type(error).__name__},
                )
        logger.warning("data.analysis.ai_failed", extra={"user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=400, detail="Could not run AI analysis.")
