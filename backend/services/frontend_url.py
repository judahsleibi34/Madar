import os
from urllib.parse import urlparse


DEFAULT_FRONTEND_URL = "http://localhost:5173"


def _split_frontend_urls(value: str) -> list[str]:
    return [url.strip().rstrip("/") for url in (value or "").split(",") if url.strip()]


def _is_local_url(url: str) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    return hostname in {"localhost", "127.0.0.1", "::1"}


def resolve_frontend_url() -> str:
    explicit_url = (os.getenv("FRONTEND_URL") or "").strip().rstrip("/")

    if explicit_url:
        return explicit_url

    configured_urls = _split_frontend_urls(
        os.getenv("FRONTEND_URLS", DEFAULT_FRONTEND_URL)
    )

    for url in configured_urls:
        if url.startswith("https://") and not _is_local_url(url):
            return url

    if configured_urls:
        return configured_urls[0]

    return DEFAULT_FRONTEND_URL
