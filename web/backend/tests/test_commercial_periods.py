import unittest
from datetime import datetime, timezone
from os import environ
from unittest.mock import patch
from services import entitlement_service as service

NOW = datetime(2026, 9, 8, tzinfo=timezone.utc)


class CommercialPeriodTests(unittest.TestCase):
    def test_half_open_boundaries(self):
        for start, end, expected in [
            ("2026-09-08T00:00:00Z", "2026-09-09T00:00:00Z", True),
            ("2026-09-07T00:00:00Z", "2026-09-08T00:00:00Z", False),
            ("2026-09-09T00:00:00Z", "2026-09-10T00:00:00Z", False),
            ("2026-09-08T03:00:00+03:00", "2026-09-09T00:00:00Z", True),
            ("2026-09-08", None, False),
            ("invalid", None, False),
            ("2026-09-09T00:00:00Z", "2026-09-08T00:00:00Z", False),
        ]:
            with self.subTest(start=start, end=end):
                self.assertEqual(service._period_is_current({"state": "active", "period_start": start, "period_end": end}, NOW), expected)

    def test_trial_and_grace_require_a_bounded_end(self):
        for state in ("trial", "grace"):
            self.assertFalse(service._period_is_current({"state": state}, NOW))
        self.assertTrue(service._period_is_current({"state": "active"}, NOW))

    def resolve(self, plan="forms", **period):
        subscriptions = [{"id": 1, "tenant_id": 7, "state": "active", "plan_id": plan, **period}]
        addons = [{"state": "active", "addon_id": "ai_analytics_plus", "quantity": 1}]
        with patch.dict(environ, {"COMMERCIAL_ENTITLEMENTS_ENFORCED": "true", "COMMERCIAL_ENTITLEMENT_TEST_LOOKUPS": "true"}), \
             patch.object(service, "_canonical_records", return_value=(subscriptions, addons)), \
             patch.object(service, "_rows", return_value=[]):
            return service.get_tenant_entitlements(7)

    def test_expired_or_future_base_does_not_gain_active_addons(self):
        for period in ({"period_end": "2000-01-01T00:00:00Z"}, {"period_start": "2099-01-01T00:00:00Z"}):
            self.assertEqual(self.resolve(**period)["capabilities"], [])

    def test_unknown_base_cannot_gain_capabilities_from_addons(self):
        self.assertEqual(self.resolve("unknown")["capabilities"], [])

    def test_unknown_capability_denies_even_if_snapshot_contains_it(self):
        from fastapi import HTTPException
        with patch.object(service, "get_tenant_entitlements", return_value={"capabilities": ["unknown"]}):
            with self.assertRaises(HTTPException):
                service.require_entitlement(7, "unknown")
            with self.assertRaises(HTTPException):
                service.require_any_entitlement(7, ["unknown"], message="denied")
