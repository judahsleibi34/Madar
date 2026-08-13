from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


@dataclass(slots=True)
class ApiError(Exception):
    status_code: int
    code: str
    message: str
    headers: dict[str, str] | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorEnvelope(BaseModel):
    error: ErrorBody


def request_id_for(request: Request) -> str:
    return str(getattr(request.state, "request_id", None) or uuid.uuid4())


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorEnvelope(
        error=ErrorBody(code=code, message=message, request_id=request_id_for(request))
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(), headers=headers)


async def api_error_handler(request: Request, error: ApiError) -> JSONResponse:
    return error_response(
        request,
        status_code=error.status_code,
        code=error.code,
        message=error.message,
        headers=error.headers,
    )


async def unhandled_error_handler(request: Request, _error: Exception) -> JSONResponse:
    return error_response(
        request,
        status_code=500,
        code="INTERNAL_ERROR",
        message="The request could not be completed.",
    )


def not_found() -> ApiError:
    return ApiError(404, "RESOURCE_NOT_FOUND", "The requested resource was not found.")


def unauthorized() -> ApiError:
    return ApiError(
        401,
        "AUTHENTICATION_REQUIRED",
        "Valid authentication is required.",
        {"WWW-Authenticate": "Bearer"},
    )
