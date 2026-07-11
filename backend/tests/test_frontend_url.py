from services.frontend_url import resolve_frontend_url


def test_resolve_frontend_url_prefers_explicit_frontend_url(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://madar.example.com/")
    monkeypatch.setenv(
        "FRONTEND_URLS",
        "http://localhost:5173,https://fallback.example.com",
    )

    assert resolve_frontend_url() == "https://madar.example.com"


def test_resolve_frontend_url_skips_localhost_when_public_url_exists(monkeypatch):
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    monkeypatch.setenv(
        "FRONTEND_URLS",
        "http://localhost:3000,http://localhost:5173,https://madar.example.com",
    )

    assert resolve_frontend_url() == "https://madar.example.com"


def test_resolve_frontend_url_allows_localhost_for_development(monkeypatch):
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    monkeypatch.setenv("FRONTEND_URLS", "http://localhost:5173")

    assert resolve_frontend_url() == "http://localhost:5173"
