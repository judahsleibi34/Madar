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


def resolve_frontend_url_for_request(request_origin: str | None) -> str:
    """Use a configured browser origin when it is explicitly allowlisted.

    This lets local development recovery links return to the local frontend even
    when ``FRONTEND_URL`` names the production canonical URL. Arbitrary Origin
    headers are never reflected into provider redirects.
    """
    clean_origin = (request_origin or "").strip().rstrip("/")
    configured_urls = set(
        _split_frontend_urls(os.getenv("FRONTEND_URLS", DEFAULT_FRONTEND_URL))
    )
    explicit_url = (os.getenv("FRONTEND_URL") or "").strip().rstrip("/")
    if explicit_url:
        configured_urls.add(explicit_url)

    if clean_origin and clean_origin in configured_urls:
        return clean_origin

    return resolve_frontend_url()
