import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from routes import calendar_routes, ecommerce_routes
from services.bounded_query_service import DB_PARALLEL_WORKERS, submit_db_read


class BoundedQueryConcurrencyTests(unittest.TestCase):
    def test_process_wide_executor_never_exceeds_its_bound(self):
        lock = threading.Lock()
        release = threading.Event()
        active = 0
        peak = 0

        def blocked_read(value):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            release.wait(timeout=1)
            with lock:
                active -= 1
            return value

        futures = [submit_db_read(blocked_read, value) for value in range(DB_PARALLEL_WORKERS * 3)]
        deadline = time.perf_counter() + 1
        while peak < DB_PARALLEL_WORKERS and time.perf_counter() < deadline:
            time.sleep(0.005)
        release.set()

        self.assertEqual([future.result(timeout=1) for future in futures], list(range(DB_PARALLEL_WORKERS * 3)))
        self.assertEqual(peak, DB_PARALLEL_WORKERS)

    def test_catalog_reference_reads_overlap_and_remain_bounded_under_load(self):
        lock = threading.Lock()
        active = 0
        peak = 0

        def read(payload):
            def loader(_tenant_id):
                nonlocal active, peak
                with lock:
                    active += 1
                    peak = max(peak, active)
                time.sleep(0.02)
                with lock:
                    active -= 1
                return payload
            return loader

        patches = (
            patch.object(ecommerce_routes, "_catalog_tags_for_tenant", read({"tags": []})),
            patch.object(ecommerce_routes, "_catalog_categories_for_tenant", read({"categories": []})),
            patch.object(ecommerce_routes, "_catalog_brands_for_tenant", read({"brands": []})),
            patch.object(ecommerce_routes, "_store_currency_for_tenant", read("ILS")),
        )
        for active_patch in patches:
            active_patch.start()
        try:
            serial_started = time.perf_counter()
            ecommerce_routes._catalog_tags_for_tenant(7)
            ecommerce_routes._catalog_categories_for_tenant(7)
            ecommerce_routes._catalog_brands_for_tenant(7)
            ecommerce_routes._store_currency_for_tenant(7)
            serial_elapsed = time.perf_counter() - serial_started

            parallel_started = time.perf_counter()
            payload = ecommerce_routes._catalog_options_for_tenant(7)
            parallel_elapsed = time.perf_counter() - parallel_started

            load_started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=12) as requests:
                loaded = list(requests.map(ecommerce_routes._catalog_options_for_tenant, range(12)))
            load_elapsed = time.perf_counter() - load_started
        finally:
            for active_patch in reversed(patches):
                active_patch.stop()

        self.assertEqual(payload, {"tags": [], "categories": [], "brands": [], "commerce_currency": "ILS"})
        self.assertEqual(len(loaded), 12)
        self.assertLess(parallel_elapsed, serial_elapsed * 0.7)
        self.assertLess(load_elapsed, serial_elapsed * 2)
        self.assertLessEqual(peak, DB_PARALLEL_WORKERS)

    def test_calendar_fanout_completes_twelve_concurrent_workspaces_within_bound(self):
        lock = threading.Lock()
        active = 0
        peak = 0

        def delayed(result):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.02)
            with lock:
                active -= 1
            return result

        context = SimpleNamespace(
            tenant_id=7,
            user_id=12,
            role="member",
            membership_status="active",
            user={"timezone": "UTC"},
        )
        start = datetime(2026, 7, 1, tzinfo=timezone.utc)
        end = datetime(2026, 7, 8, tzinfo=timezone.utc)

        with patch.object(calendar_routes, "ensure_default_calendar"), patch.object(
            calendar_routes, "list_accessible_calendars", return_value=[]
        ), patch.object(
            calendar_routes, "expand_events", side_effect=lambda *_args: delayed([])
        ), patch.object(
            calendar_routes, "workspace_task_rows", side_effect=lambda *_args: delayed([])
        ), patch.object(
            calendar_routes, "workspace_linked_task_event_ids", return_value=set()
        ):
            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=12) as requests:
                payloads = list(requests.map(
                    lambda _index: calendar_routes._calendar_workspace_payload(context, start, end),
                    range(12),
                ))
            elapsed = time.perf_counter() - started

        self.assertEqual(len(payloads), 12)
        self.assertTrue(all(payload["success"] for payload in payloads))
        self.assertLessEqual(peak, DB_PARALLEL_WORKERS)
        self.assertLess(elapsed, 0.35)


if __name__ == "__main__":
    unittest.main()
