"""Real thread interleavings at the cache/read versus mutation boundary."""

from concurrent.futures import ThreadPoolExecutor
import threading
import unittest

from services import calendar_workspace_cache_service as calendar
from services import ecommerce_cache_service as catalog


class CacheInvalidationRaceTests(unittest.TestCase):
    def setUp(self):
        catalog.clear_ecommerce_cache()
        calendar.clear_calendar_workspace_cache()
        self.addCleanup(catalog.clear_ecommerce_cache)
        self.addCleanup(calendar.clear_calendar_workspace_cache)

    def assert_race_is_fenced(self, load, read, invalidate, *, clear=None):
        started = threading.Event()
        finish = threading.Event()

        def stale_snapshot():
            started.set()
            if not finish.wait(5):
                raise AssertionError("test did not release the in-flight loader")
            return {"items": ["deleted"]}

        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(load, "tenant-7-resource", 7, stale_snapshot)
            try:
                self.assertTrue(started.wait(5), "cache loader did not start")
                if clear:
                    clear()
                else:
                    invalidate(7)
                # A newer request can publish current data before the old
                # database snapshot finishes. It must survive that completion.
                self.assertEqual(load("tenant-7-resource", 7, lambda: {"items": []}), ({"items": []}, False))
            finally:
                finish.set()
            self.assertEqual(pending.result(timeout=5), ({"items": ["deleted"]}, False))
        self.assertEqual(read("tenant-7-resource"), {"items": []})

    def test_catalog_inflight_read_cannot_resurrect_invalidated_data(self):
        self.assert_race_is_fenced(catalog.get_or_create_ecommerce_cache,
                                  catalog.read_ecommerce_cache, catalog.invalidate_ecommerce_cache)

    def test_catalog_clear_fences_reads_started_before_clear(self):
        self.assert_race_is_fenced(catalog.get_or_create_ecommerce_cache,
                                  catalog.read_ecommerce_cache, catalog.invalidate_ecommerce_cache,
                                  clear=catalog.clear_ecommerce_cache)

    def test_calendar_inflight_read_cannot_overwrite_newer_data(self):
        self.assert_race_is_fenced(calendar.get_or_create_calendar_workspace,
                                  calendar.read_calendar_workspace_cache, calendar.invalidate_calendar_workspace_cache)

    def test_calendar_clear_fences_reads_started_before_clear(self):
        self.assert_race_is_fenced(calendar.get_or_create_calendar_workspace,
                                  calendar.read_calendar_workspace_cache, calendar.invalidate_calendar_workspace_cache,
                                  clear=calendar.clear_calendar_workspace_cache)

    def test_calendar_cache_defensively_checks_expected_tenant(self):
        calendar.write_calendar_workspace_cache("wrong-key", 7, {"tenant": 7})
        result, hit = calendar.get_or_create_calendar_workspace("wrong-key", 8, lambda: {"tenant": 8})
        self.assertFalse(hit)
        self.assertEqual(result, {"tenant": 8})

    def test_fill_tracking_is_released_after_success_failure_and_invalidation(self):
        for module, load, invalidate in (
            (catalog, catalog.get_or_create_ecommerce_cache, catalog.invalidate_ecommerce_cache),
            (calendar, calendar.get_or_create_calendar_workspace, calendar.invalidate_calendar_workspace_cache),
        ):
            with self.subTest(module=module.__name__):
                def failed_load():
                    raise RuntimeError("synthetic loader failure")
                with self.assertRaisesRegex(RuntimeError, "synthetic"):
                    load("failed", 7, failed_load)
                self.assertEqual(module._inflight, {})
                load("succeeded", 7, lambda: {"items": []})
                self.assertEqual(module._inflight, {})
                for tenant in range(1000):
                    invalidate(tenant)
                self.assertEqual(module._inflight, {})
