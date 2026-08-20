from unittest.mock import patch

from fastapi import Request, Response

from routes import public_site_routes
from services.ecommerce_cache_service import (
    clear_ecommerce_cache,
    ecommerce_cache_key,
    ecommerce_cache_size,
    get_or_create_ecommerce_cache,
    invalidate_ecommerce_cache,
    read_ecommerce_cache,
    write_ecommerce_cache,
)


def setup_function():
    clear_ecommerce_cache()


def test_cache_keys_are_tenant_and_filter_scoped():
    first = ecommerce_cache_key(1, "catalog", locale="en", category="chairs")
    second = ecommerce_cache_key(2, "catalog", locale="en", category="chairs")
    filtered = ecommerce_cache_key(1, "catalog", locale="ar", category="chairs")
    assert len({first, second, filtered}) == 3


def test_cached_values_are_copied_and_reused():
    key = ecommerce_cache_key(4, "catalog", page=1)
    write_ecommerce_cache(key, 4, {"products": [{"id": "one"}]})
    value = read_ecommerce_cache(key)
    value["products"].append({"id": "mutated"})
    assert read_ecommerce_cache(key) == {"products": [{"id": "one"}]}

    calls = []
    result, hit = get_or_create_ecommerce_cache(
        key,
        4,
        lambda: calls.append(True) or {},
    )
    assert hit is True
    assert not calls
    assert result["products"][0]["id"] == "one"


def test_invalidation_removes_only_one_tenant():
    one = ecommerce_cache_key(1, "catalog")
    two = ecommerce_cache_key(2, "catalog")
    write_ecommerce_cache(one, 1, {"tenant": 1})
    write_ecommerce_cache(two, 2, {"tenant": 2})
    assert invalidate_ecommerce_cache(1) == 1
    assert read_ecommerce_cache(one) is None
    assert read_ecommerce_cache(two) == {"tenant": 2}
    assert ecommerce_cache_size() == 1


def test_public_catalog_route_reuses_warm_tenant_cache():
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/public/sites/demo/catalog",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 1),
        "server": ("testserver", 80),
        "scheme": "http",
    })
    payload = {
        "categories": [],
        "tags": [],
        "products": [{"id": "one"}],
        "pagination": {"page": 1, "limit": 12, "total": 1, "pages": 1},
    }
    with (
        patch.object(public_site_routes, "enforce_public_rate_limit"),
        patch.object(
            public_site_routes,
            "resolve_website_settings",
            return_value={"tenant_id": 7, "published_project_id": "project-1"},
        ),
        patch.object(public_site_routes, "get_bound_published_project", return_value={}),
        patch.object(public_site_routes, "build_public_site_profile", return_value={"subdomain": "demo"}),
        patch.object(public_site_routes, "_catalog_payload", return_value=payload) as build_payload,
    ):
        first_response = Response()
        first = public_site_routes.get_public_catalog(
            "demo",
            request,
            first_response,
        )
        second_response = Response()
        second = public_site_routes.get_public_catalog(
            "demo",
            request,
            second_response,
        )

    assert first["catalog"] == second["catalog"]
    assert build_payload.call_count == 1
    assert first_response.headers["X-Ecommerce-Cache"] == "MISS"
    assert second_response.headers["X-Ecommerce-Cache"] == "HIT"
