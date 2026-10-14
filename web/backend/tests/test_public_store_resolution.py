import os
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from routes import public_site_routes
from services import observability_service
from services.ecommerce_cache_service import clear_ecommerce_cache


def hosted_request(host="store-a.madarportal.com", cookies=""):
    headers = [(b"host", host.encode())]
    if cookies:
        headers.append((b"cookie", cookies.encode()))
    return Request({
        "type": "http", "method": "GET", "path": "/public/sites/store-a/catalog", "headers": headers,
        "query_string": b"", "client": ("203.0.113.9", 1), "server": (host, 443), "scheme": "https",
    })


class FakeDatabase:
    """Records every read; website_settings rows carry the tenants embed."""

    def __init__(self):
        self.reads = []
        self.lock = threading.Lock()
        self.delay = 0.0
        self.settings = [{"id": 1, "tenant_id": 7, "subdomain": "store-a", "standard_path_slug": "store-a", "brand": "A"}]
        self.tenants = {7: "active", 8: "active"}
        self.embed_error = None

    def table(self, name):
        return FakeQuery(self, name)


class FakeQuery:
    def __init__(self, database, name):
        self.database, self.name, self.filters, self.columns = database, name, [], ""

    def select(self, columns, count=None):
        self.columns = columns
        return self

    def ilike(self, field, value):
        self.filters.append((field, str(value).lower()))
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def limit(self, _size):
        return self

    def execute(self):
        with self.database.lock:
            self.database.reads.append((self.name, self.columns))
        if self.database.delay:
            time.sleep(self.database.delay)
        if self.name == "website_settings":
            if "tenants(" in self.columns and self.database.embed_error:
                raise Exception(self.database.embed_error)
            matched = [dict(row) for row in self.database.settings if all(str(row.get(f, "")).lower() == v for f, v in self.filters)]
            if "tenant_lifecycle:tenants(lifecycle_state)" in self.columns:
                for row in matched:
                    state = self.database.tenants.get(row["tenant_id"])
                    row["tenant_lifecycle"] = None if state is None else {"lifecycle_state": state}
            return SimpleNamespace(data=matched)
        if self.name == "tenants":
            filters = dict(self.filters)
            state = self.database.tenants.get(int(filters["tenant_id"]))
            return SimpleNamespace(data=[{"tenant_id": filters["tenant_id"]}] if state == filters.get("lifecycle_state") else [])
        raise AssertionError(f"unexpected table {self.name}")


class StoreResolutionTests(unittest.TestCase):
    def setUp(self):
        clear_ecommerce_cache()
        self.db = FakeDatabase()
        self.entitlement_calls = []
        self.suspended = set()

        def entitlement(settings, capability, **_kwargs):
            self.entitlement_calls.append((settings.get("tenant_id"), capability))
            if settings.get("tenant_id") in self.suspended:
                raise HTTPException(status_code=503, detail={"code": "tenant_service_unavailable"})
            return {}

        for patcher in (
            patch.object(public_site_routes, "service_supabase", self.db),
            patch("services.tenant_lifecycle_service.service_supabase", self.db),
            patch.object(public_site_routes, "require_public_runtime_entitlement", side_effect=entitlement),
            patch.dict(os.environ, {"MADAR_TEST_TENANT_LIFECYCLE_LOOKUPS": "true"}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(clear_ecommerce_cache)

    def tables_read(self):
        return [name for name, _columns in self.db.reads]

    def resolve(self, request=None):
        return public_site_routes.resolve_public_store_settings("store-a", request=request or hosted_request())

    # Phase 2: settings + lifecycle in one read, then fresh entitlement.
    def test_cold_resolution_reads_settings_and_lifecycle_together(self):
        settings = self.resolve()
        assert settings["tenant_id"] == 7 and "tenant_lifecycle" not in settings
        assert self.tables_read() == ["website_settings"]
        assert self.entitlement_calls == [(7, "ecommerce")]

    def test_inactive_or_missing_tenant_is_not_found(self):
        for state in ("deletion_pending", None):
            clear_ecommerce_cache()
            self.db.tenants[7] = state
            with self.assertRaises(HTTPException) as raised:
                self.resolve()
            assert raised.exception.status_code == 404
        assert self.entitlement_calls == []

    def test_ambiguous_hostname_stays_ambiguous_even_if_one_tenant_is_inactive(self):
        self.db.settings.append({"id": 2, "tenant_id": 8, "subdomain": "store-a", "standard_path_slug": "other"})
        self.db.tenants[8] = "deletion_pending"
        with self.assertRaises(HTTPException) as raised:
            self.resolve()
        assert raised.exception.status_code == 409

    def test_legacy_schema_without_lifecycle_embed_uses_standalone_check(self):
        self.db.embed_error = "column tenants.lifecycle_state does not exist"
        assert self.resolve()["tenant_id"] == 7
        assert self.tables_read() == ["website_settings", "website_settings", "tenants"]

    # Phase 1: a cache hit re-verifies lifecycle and entitlement every time.
    def test_cache_hit_rechecks_lifecycle_so_deletion_takes_effect_immediately(self):
        self.resolve()
        self.db.reads.clear()
        assert self.resolve()["tenant_id"] == 7
        assert sorted(self.tables_read()) == ["tenants"]
        self.db.tenants[7] = "deletion_pending"
        with self.assertRaises(HTTPException) as raised:
            self.resolve()
        assert raised.exception.status_code == 404

    def test_cache_hit_rechecks_entitlement_so_suspension_takes_effect_immediately(self):
        self.resolve()
        self.resolve()
        assert len(self.entitlement_calls) == 2
        self.suspended.add(7)
        with self.assertRaises(HTTPException) as raised:
            self.resolve()
        assert raised.exception.status_code == 503

    def test_cache_hit_reports_deletion_before_entitlement(self):
        self.resolve()
        self.db.tenants[7] = "deletion_pending"
        self.suspended.add(7)
        with self.assertRaises(HTTPException) as raised:
            self.resolve()
        assert raised.exception.status_code == 404

    def test_cache_hit_still_enforces_host_identity(self):
        self.resolve()
        with self.assertRaises(HTTPException) as raised:
            self.resolve(hosted_request(host="store-b.madarportal.com"))
        assert raised.exception.status_code == 404

    # Phase 3: concurrent cold resolutions share one in-flight resolution.
    def run_concurrently(self, count=8):
        results, errors, start = [], [], threading.Barrier(count)

        def worker():
            start.wait()
            try:
                results.append(self.resolve())
            except HTTPException as error:
                errors.append(error)

        threads = [threading.Thread(target=worker) for _ in range(count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return results, errors

    def test_concurrent_cold_resolutions_share_one_settings_read(self):
        self.db.delay = 0.05
        results, errors = self.run_concurrently()
        assert not errors and len(results) == 8
        assert self.tables_read().count("website_settings") == 1
        assert len(self.entitlement_calls) == 1
        assert len({id(result) for result in results}) == 8  # no shared mutable objects
        assert public_site_routes._store_resolutions_in_flight == {}
        self.resolve()  # later requests verify afresh
        assert len(self.entitlement_calls) == 2

    def test_shared_failure_reaches_every_waiter_and_clears_the_key(self):
        self.db.delay = 0.05
        self.db.tenants[7] = "deletion_pending"
        results, errors = self.run_concurrently()
        assert not results and len(errors) == 8 and {error.status_code for error in errors} == {404}
        assert len({id(error) for error in errors}) == 8
        assert public_site_routes._store_resolutions_in_flight == {}
        self.db.tenants[7] = "active"
        self.db.delay = 0
        assert self.resolve()["tenant_id"] == 7

    def test_in_flight_resolution_is_never_shared_across_hosts(self):
        self.db.settings.append({"id": 2, "tenant_id": 8, "subdomain": "store-b", "standard_path_slug": "store-b"})
        self.db.delay = 0.05
        seen = {}

        def worker(host, identifier):
            seen[host] = public_site_routes.resolve_public_store_settings(identifier, request=hosted_request(host=host))["tenant_id"]

        threads = [
            threading.Thread(target=worker, args=("store-a.madarportal.com", "store-a")),
            threading.Thread(target=worker, args=("store-b.madarportal.com", "store-b")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert seen == {"store-a.madarportal.com": 7, "store-b.madarportal.com": 8}

    # Phase 6: compact timing names, durations only.
    def test_store_resolution_timing_is_compact(self):
        token = observability_service.begin_request_timings()
        try:
            self.resolve()
            self.resolve()
            header = observability_service.server_timing_value()
        finally:
            observability_service.end_request_timings(token)
        for name in ("store_resolution", "site_resolution", "tenant_lifecycle", "entitlement"):
            assert f"{name};dur=" in header
        assert "_start" not in header and len(header) <= 1024


class AnonymousVisitorStatusTests(unittest.TestCase):
    def call(self, cookies="", host="store-a.madarportal.com", subdomain="store-a"):
        return public_site_routes.tenant_visitor_status(subdomain, hosted_request(host=host, cookies=cookies), SimpleNamespace())

    def test_anonymous_visitor_needs_no_lookup(self):
        with patch.object(public_site_routes, "require_tenant_visitor") as visitor:
            assert self.call() == {"logged_in": False, "user": None}
        visitor.assert_not_called()

    def test_session_cookies_still_take_the_validated_path(self):
        for cookies in ("madar_access_token=a", "madar_refresh_token=r", "madar_access_token=a; madar_refresh_token=r"):
            with patch.object(public_site_routes, "require_tenant_visitor", return_value=({"id": 5, "email": "v@example.test"}, {"role": "member"})) as visitor, \
                    patch.object(public_site_routes, "build_user_payload", return_value={"id": 5}):
                assert self.call(cookies) == {"logged_in": True, "user": {"id": 5}, "role": "member"}
            visitor.assert_called_once()

    def test_expired_or_invalid_credentials_keep_the_existing_answer(self):
        with patch.object(public_site_routes, "require_tenant_visitor", side_effect=HTTPException(status_code=401)) as visitor:
            assert self.call("madar_access_token=expired") == {"logged_in": False, "user": None}
        visitor.assert_called_once()

    def test_cross_tenant_request_is_rejected_even_without_cookies(self):
        with self.assertRaises(HTTPException) as raised:
            self.call(host="store-b.madarportal.com", subdomain="store-a")
        assert raised.exception.status_code == 404


if __name__ == "__main__":
    unittest.main()
