import os
import re
from dataclasses import dataclass
from typing import Any

from starlette.responses import JSONResponse

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
DEFAULT_MAX_REQUEST_BODY_BYTES = 12 * 1024 * 1024
DEFAULT_MAX_BUILDER_ASSET_REQUEST_BODY_BYTES = 252 * 1024 * 1024
DEFAULT_MAX_JSON_BODY_BYTES = 3 * 1024 * 1024
DEFAULT_MAX_SMALL_JSON_BODY_BYTES = 256 * 1024
DEFAULT_MAX_DATA_JSON_BODY_BYTES = 1024 * 1024

PUBLIC_FORM_SUBMISSION_RE = re.compile(r"^/public/sites/[^/]+/forms/[^/]+/submissions$")
USER_SMALL_JSON_RE = re.compile(
    r"^/users/[^/]+/(?:info|profile|billing/checkout|website/settings)$"
)
DATA_JSON_RE = re.compile(
    r"^/users/[^/]+/(?:data/read|cleaning/.*|analysis/.*|visualization/.*)$"
)
UPLOAD_ROUTE_RE = re.compile(r"^/users/[^/]+/(?:data/upload|avatar)$")
USER_BUILDER_RE = re.compile(r"^/users/[^/]+/builder(?:/.*)?$")


class RequestBodyTooLarge(Exception):
    pass


@dataclass(frozen=True)
class RequestBodyLimitConfig:
    max_request_body_bytes: int
    max_builder_asset_request_body_bytes: int
    max_json_body_bytes: int
    max_small_json_body_bytes: int
    max_data_json_body_bytes: int


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default

    return value if value >= 0 else default


def _limit_value(value: int | None, env_name: str, default: int) -> int:
    if value is None:
        return _env_int(env_name, default)

    try:
        parsed_value = int(value)
    except (TypeError, ValueError):
        return default

    return parsed_value if parsed_value >= 0 else default


def _header_value(scope: dict[str, Any], header_name: bytes) -> str:
    for key, value in scope.get("headers") or []:
        if key.lower() == header_name:
            return value.decode("latin-1").strip()

    return ""


def _content_type(scope: dict[str, Any]) -> str:
    return _header_value(scope, b"content-type").split(";", 1)[0].strip().lower()


def _content_length(scope: dict[str, Any]) -> int | None:
    raw_value = _header_value(scope, b"content-length")

    if not raw_value:
        return None

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None

    return value if value >= 0 else None


def _is_json_content_type(content_type: str) -> bool:
    return content_type == "application/json" or content_type.endswith("+json")


def _is_multipart_content_type(content_type: str) -> bool:
    return content_type == "multipart/form-data"


def _is_small_json_path(path: str) -> bool:
    return (
        path.startswith("/auth/")
        or path.startswith("/admin/")
        or path in {
            "/billing/checkout",
            "/billing/webhook",
            "/public/contact",
            "/website/settings",
        }
        or USER_SMALL_JSON_RE.match(path) is not None
        or PUBLIC_FORM_SUBMISSION_RE.match(path) is not None
    )


def _is_data_json_path(path: str) -> bool:
    return DATA_JSON_RE.match(path) is not None


def _is_builder_path(path: str) -> bool:
    return path.startswith("/builder/") or USER_BUILDER_RE.match(path) is not None


def _is_upload_path(path: str) -> bool:
    return UPLOAD_ROUTE_RE.match(path) is not None


def select_request_body_limit(
    *,
    method: str,
    path: str,
    content_type: str,
    config: RequestBodyLimitConfig,
) -> int | None:
    if method.upper() in SAFE_METHODS:
        return None

    if path == "/builder/assets/upload" and _is_multipart_content_type(content_type):
        return config.max_builder_asset_request_body_bytes

    if _is_multipart_content_type(content_type) or _is_upload_path(path):
        return config.max_request_body_bytes

    if _is_small_json_path(path):
        return config.max_small_json_body_bytes

    if _is_data_json_path(path):
        return config.max_data_json_body_bytes

    if _is_builder_path(path):
        return config.max_json_body_bytes

    if _is_json_content_type(content_type):
        return config.max_json_body_bytes

    return config.max_request_body_bytes


class RequestBodyLimitMiddleware:
    def __init__(
        self,
        app,
        *,
        max_request_body_bytes: int | None = None,
        max_builder_asset_request_body_bytes: int | None = None,
        max_json_body_bytes: int | None = None,
        max_small_json_body_bytes: int | None = None,
        max_data_json_body_bytes: int | None = None,
    ):
        self.app = app
        self.config = RequestBodyLimitConfig(
            max_request_body_bytes=_limit_value(
                max_request_body_bytes,
                "MAX_REQUEST_BODY_BYTES",
                DEFAULT_MAX_REQUEST_BODY_BYTES,
            ),
            max_builder_asset_request_body_bytes=_limit_value(
                max_builder_asset_request_body_bytes,
                "MAX_BUILDER_ASSET_REQUEST_BODY_BYTES",
                DEFAULT_MAX_BUILDER_ASSET_REQUEST_BODY_BYTES,
            ),
            max_json_body_bytes=_limit_value(
                max_json_body_bytes,
                "MAX_JSON_BODY_BYTES",
                DEFAULT_MAX_JSON_BODY_BYTES,
            ),
            max_small_json_body_bytes=_limit_value(
                max_small_json_body_bytes,
                "MAX_SMALL_JSON_BODY_BYTES",
                DEFAULT_MAX_SMALL_JSON_BODY_BYTES,
            ),
            max_data_json_body_bytes=_limit_value(
                max_data_json_body_bytes,
                "MAX_DATA_JSON_BODY_BYTES",
                DEFAULT_MAX_DATA_JSON_BODY_BYTES,
            ),
        )

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        limit = select_request_body_limit(
            method=scope.get("method", ""),
            path=scope.get("path", ""),
            content_type=_content_type(scope),
            config=self.config,
        )

        if limit is None:
            await self.app(scope, receive, send)
            return

        content_length = _content_length(scope)

        if content_length is not None and content_length > limit:
            await self._send_too_large(scope, receive, send)
            return

        received_body_bytes = 0
        response_started = False

        async def limited_receive():
            nonlocal received_body_bytes

            message = await receive()

            if message.get("type") == "http.request":
                body = message.get("body") or b""
                received_body_bytes += len(body)

                if received_body_bytes > limit:
                    raise RequestBodyTooLarge

            return message

        async def send_wrapper(message):
            nonlocal response_started

            if message.get("type") == "http.response.start":
                response_started = True

            await send(message)

        try:
            await self.app(scope, limited_receive, send_wrapper)
        except RequestBodyTooLarge:
            if response_started:
                raise

            await self._send_too_large(scope, receive, send)

    async def _send_too_large(self, scope, receive, send):
        response = JSONResponse(
            status_code=413,
            content={"detail": "Request body too large"},
        )
        await response(scope, receive, send)
