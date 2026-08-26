"""Supabase API-key header and client compatibility helpers.

Supabase's publishable/secret API keys are opaque API keys, not JWTs.  They
must be sent through the ``apikey`` header and must not be copied into an
``Authorization: Bearer`` header.  Legacy anon/service-role JWT keys retain
their historical dual-header behavior during the migration window.
"""

from __future__ import annotations

from typing import Optional

from supabase import Client, ClientOptions


OPAQUE_API_KEY_PREFIXES = ("sb_publishable_", "sb_secret_")


def is_opaque_supabase_api_key(key: str) -> bool:
    return str(key or "").startswith(OPAQUE_API_KEY_PREFIXES)


def is_supabase_secret_api_key(key: str) -> bool:
    return str(key or "").startswith("sb_secret_")


def supabase_api_headers(
    key: str,
    *,
    authorization: str | None = None,
) -> dict[str, str]:
    """Return safe headers for an API key and optional user JWT.

    An explicit authorization value is expected to be an already formatted
    user-session authorization header.  Without one, opaque API keys are sent
    only as ``apikey``.  Legacy JWT API keys continue to be sent in both
    headers so existing deployments remain compatible during migration.
    """

    headers = {"apikey": key}
    if authorization:
        headers["Authorization"] = authorization
    elif key and not is_opaque_supabase_api_key(key):
        headers["Authorization"] = f"Bearer {key}"
    return headers


class ApiKeyCompatibleClient(Client):
    """Supabase client that does not mislabel opaque API keys as JWTs."""

    def _get_auth_headers(self, authorization: Optional[str] = None) -> dict[str, str]:
        if authorization is None:
            authorization = self.options.headers.get("Authorization")
        return supabase_api_headers(
            self.supabase_key,
            authorization=authorization,
        )


def create_api_key_compatible_client(
    supabase_url: str,
    supabase_key: str,
    options: ClientOptions | None = None,
) -> Client:
    return ApiKeyCompatibleClient.create(supabase_url, supabase_key, options)
