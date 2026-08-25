import unittest
from os import environ
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from services import entitlement_service
from services.hosted_address_service import (
    hosted_address_is_valid,
    normalize_hosted_address,
    validate_hosted_address,
)
from services.commercial_catalog import (
    ADD_ON_IDS,
    BASE_PLAN_IDS,
    GIB,
    get_catalog,
    validate_catalog,
)


class CommercialCatalogTests(unittest.TestCase):
    def test_catalog_has_final_plan_ids_prices_and_no_whatsapp(self):
        catalog = get_catalog()
        plans = {
            item["id"]: item
            for item in catalog["products"]
            if item["type"] == "base_plan"
        }

        self.assertEqual(tuple(plans), BASE_PLAN_IDS)
        self.assertEqual(
            {key: plans[key]["price_minor"] for key in BASE_PLAN_IDS},
            {"forms": 1500, "website": 2000, "business": 2500, "business_plus": 3000},
        )
        self.assertEqual(catalog["currency"], "USD")
        self.assertNotIn("whatsapp", str(catalog).lower())
        self.assertIsNone(validate_catalog())

    def test_unlimited_volume_allowances_are_not_commercial_quotas(self):
        for plan in get_catalog()["products"]:
            if plan["type"] != "base_plan":
                continue
            allowances = plan["allowances"]
            self.assertIsNone(allowances["forms"])
            self.assertIsNone(allowances["form_submissions"])
            self.assertIsNone(allowances["reservation_requests"])

    def test_future_products_cannot_be_publicly_activated(self):
        products = {
            item["id"]: item
            for item in get_catalog()["products"]
            if item["type"] in {"add_on", "token_pack"}
        }
        for product_id in (
            "additional_workspace_seat",
            "workspace_seat_pack_5",
            "google_drive_private",
            "ocr",
            "hosted_email_mailbox",
            "custom_domain",
        ):
            self.assertIn(product_id, ADD_ON_IDS)
            self.assertTrue(products[product_id]["coming_soon"])
            self.assertFalse(products[product_id]["publicly_available"])

    def test_migration_is_mirrored_and_keeps_commercial_mutations_backend_only(self):
        root = next(
            parent
            for parent in (Path(__file__).resolve(), *Path(__file__).resolve().parents)
            if (parent / "database/migrations").is_dir()
            and (parent / "supabase/migrations").is_dir()
        )
        database_sql = (
            root / "database/migrations/071_create_commercial_entitlements.sql"
        ).read_text(encoding="utf-8").lower()
        supabase_sql = (
            root / "supabase/migrations/071_create_commercial_entitlements.sql"
        ).read_text(encoding="utf-8").lower()
        self.assertEqual(database_sql, supabase_sql)
        self.assertIn("tenant_subscriptions_one_active_idx", database_sql)
        self.assertIn("website_settings_standard_path_slug_unique_idx", database_sql)
        self.assertIn("validate constraint website_settings_standard_path_slug_check", database_sql)
        self.assertIn("legacy_subdomain_routing_preserved", database_sql)
        self.assertIn("'pending_review'", database_sql)
        self.assertIn("tenant_addons_one_active_ai_package_idx", database_sql)
        self.assertIn("v_lock_group", database_sql)
        self.assertIn("deficit_standard_tokens", database_sql)
        self.assertIn("pg_advisory_xact_lock", database_sql)
        self.assertIn("revoke all on table public.tenant_subscriptions", database_sql)
        self.assertIn("grant execute on function public.reserve_ai_standard_tokens", database_sql)
        self.assertNotIn("grant usage, select on all sequences", database_sql)
        self.assertNotIn("monthly_form_limit", database_sql)
        self.assertNotIn("monthly_submission_limit", database_sql)
        self.assertNotIn("monthly_reservation_limit", database_sql)


class HostedAddressRuleTests(unittest.TestCase):
    def test_normalization_trims_and_lowercases(self):
        self.assertEqual(normalize_hosted_address("  Example-Site  "), "example-site")

    def test_runtime_validation_rejects_malformed_and_reserved_values(self):
        for value in ("", "two words", "../site", "-leading", "trailing-", "Admin"):
            with self.subTest(value=value):
                self.assertFalse(hosted_address_is_valid(value))
                with self.assertRaises(HTTPException):
                    validate_hosted_address(value)

    def test_runtime_validation_accepts_canonical_slug(self):
        self.assertEqual(validate_hosted_address(" Shop-123 "), "shop-123")


class EntitlementMatrixTests(unittest.TestCase):
    def canonical_state(self, plan_id, addons=None):
        subscription = {
            "id": 1,
            "tenant_id": 7,
            "plan_id": plan_id,
            "state": "active",
        }
        return [subscription], list(addons or [])

    def state_for(self, plan_id, addons=None):
        with patch.dict(
            environ,
            {"COMMERCIAL_ENTITLEMENT_TEST_LOOKUPS": "true"},
        ), patch.object(
            entitlement_service,
            "_canonical_records",
            return_value=self.canonical_state(plan_id, addons),
        ), patch.object(
            entitlement_service,
            "_rows",
            return_value=[],
        ):
            return entitlement_service.get_tenant_entitlements(7)

    def test_base_plan_capability_matrix(self):
        forms = set(self.state_for("forms")["capabilities"])
        website = set(self.state_for("website")["capabilities"])
        business = set(self.state_for("business")["capabilities"])
        plus = set(self.state_for("business_plus")["capabilities"])

        self.assertIn("forms", forms)
        self.assertNotIn("page_builder", forms)
        self.assertIn("standard_hosted_address", website)
        self.assertNotIn("reservations", website)
        self.assertIn("data_exports", business)
        self.assertNotIn("internal_calendar", business)
        self.assertIn("reservations", plus)
        self.assertIn("internal_calendar", plus)

    def test_storage_addons_aggregate_exact_bytes(self):
        addons = [{
            "addon_id": "additional_storage_5gb",
            "state": "active",
            "quantity": 2,
        }]
        state = self.state_for("website", addons)
        self.assertEqual(state["allowances"]["storage_bytes"], 12 * GIB)

    def test_workspace_seat_addons_aggregate(self):
        addons = [
            {"addon_id": "additional_workspace_seat", "state": "active", "quantity": 2},
            {"addon_id": "workspace_seat_pack_5", "state": "active", "quantity": 1},
        ]
        # The customer invitation UI remains unavailable, but administrative
        # assignment exercises the server-side capacity primitive.
        with patch.dict(
            environ,
            {"COMMERCIAL_ENTITLEMENT_TEST_LOOKUPS": "true"},
        ), patch.object(
            entitlement_service,
            "_canonical_records",
            return_value=self.canonical_state("business", addons),
        ), patch.object(entitlement_service, "_rows", return_value=[]):
            self.assertEqual(entitlement_service.get_workspace_seat_capacity(7), 8)

    def test_branded_subdomain_requires_addon_or_reviewed_grandfathering(self):
        state = self.state_for("website")
        self.assertNotIn("branded_madar_subdomain", state["capabilities"])
        with patch.object(entitlement_service, "has_entitlement", return_value=False):
            with self.assertRaises(HTTPException) as context:
                entitlement_service.require_branded_subdomain({"tenant_id": 7})
            self.assertEqual(context.exception.status_code, 402)

        entitlement_service.require_branded_subdomain({
            "tenant_id": 7,
            "branded_subdomain_commercial_status": "grandfathered",
        })

    def test_pending_legacy_route_is_runtime_only(self):
        settings = {
            "tenant_id": 7,
            "published_project_id": "project-1",
            "legacy_subdomain_routing_preserved": True,
            "branded_subdomain_commercial_status": "pending_review",
        }
        with patch.object(entitlement_service, "has_entitlement", return_value=False):
            with self.assertRaises(HTTPException):
                entitlement_service.require_branded_subdomain(settings)
            entitlement_service.require_branded_subdomain(
                settings,
                allow_legacy_routing=True,
            )

    def test_unpublished_pending_legacy_route_is_not_served(self):
        settings = {
            "tenant_id": 7,
            "published_project_id": None,
            "legacy_subdomain_routing_preserved": True,
            "branded_subdomain_commercial_status": "pending_review",
        }
        with patch.object(entitlement_service, "has_entitlement", return_value=False):
            with self.assertRaises(HTTPException):
                entitlement_service.require_branded_subdomain(
                    settings,
                    allow_legacy_routing=True,
                )

    def test_removed_legacy_route_is_not_compatible(self):
        settings = {
            "tenant_id": 7,
            "published_project_id": "project-1",
            "legacy_subdomain_routing_preserved": True,
            "branded_subdomain_commercial_status": "removed",
        }
        with patch.object(entitlement_service, "has_entitlement", return_value=False):
            with self.assertRaises(HTTPException):
                entitlement_service.require_branded_subdomain(
                    settings,
                    allow_legacy_routing=True,
                )

    def test_forged_client_capabilities_are_irrelevant(self):
        with patch.object(
            entitlement_service,
            "get_tenant_entitlements",
            return_value={
                "capabilities": ["forms"],
                "plan_id": "forms",
            },
        ):
            with self.assertRaises(HTTPException):
                entitlement_service.require_entitlement(7, "website_publish")

    def test_missing_subscription_fails_closed(self):
        with patch.dict(environ, {"COMMERCIAL_ENTITLEMENT_TEST_LOOKUPS": "true"}), \
             patch.object(entitlement_service, "_canonical_records", return_value=([], [])), \
             patch.object(entitlement_service, "_legacy_features", return_value=[]):
            state = entitlement_service.get_tenant_entitlements(7)
        self.assertEqual(state["capabilities"], [])
        self.assertEqual(state["allowances"], {})
        self.assertTrue(state["review_required"])

    def test_duplicate_entitled_subscription_is_rejected(self):
        rows = [
            {"id": 1, "tenant_id": 7, "plan_id": "forms", "state": "active"},
            {"id": 2, "tenant_id": 7, "plan_id": "website", "state": "grace"},
        ]
        with patch.dict(environ, {"COMMERCIAL_ENTITLEMENT_TEST_LOOKUPS": "true"}), \
             patch.object(entitlement_service, "_canonical_records", return_value=(rows, [])):
            with self.assertRaises(HTTPException) as context:
                entitlement_service.get_tenant_entitlements(7)
        self.assertEqual(context.exception.status_code, 503)

    def test_inactive_subscription_grants_nothing(self):
        with patch.dict(environ, {"COMMERCIAL_ENTITLEMENT_TEST_LOOKUPS": "true"}), \
             patch.object(entitlement_service, "_canonical_records", return_value=([{
                 "id": 1, "tenant_id": 7, "plan_id": "business_plus", "state": "suspended"
             }], [])), patch.object(entitlement_service, "_legacy_features", return_value=[]):
            state = entitlement_service.get_tenant_entitlements(7)
        self.assertEqual(state["source"], "canonical_inactive")
        self.assertEqual(state["capabilities"], [])

    def test_trial_and_grace_are_explicit_entitled_states(self):
        for subscription_state in ("trial", "grace"):
            rows = [{"id": 1, "tenant_id": 7, "plan_id": "website", "state": subscription_state}]
            with self.subTest(state=subscription_state), patch.dict(
                environ, {"COMMERCIAL_ENTITLEMENT_TEST_LOOKUPS": "true"}
            ), patch.object(entitlement_service, "_canonical_records", return_value=(rows, [])), patch.object(
                entitlement_service, "_rows", return_value=[]
            ):
                state = entitlement_service.get_tenant_entitlements(7)
            self.assertIn("website_publish", state["capabilities"])

    def test_cancelled_expired_past_due_and_malformed_states_grant_nothing(self):
        for subscription_state in ("cancelled", "expired", "past_due", "", "unknown"):
            rows = [{"id": 1, "tenant_id": 7, "plan_id": "business_plus", "state": subscription_state}]
            with self.subTest(state=subscription_state), patch.dict(
                environ, {"COMMERCIAL_ENTITLEMENT_TEST_LOOKUPS": "true"}
            ), patch.object(entitlement_service, "_canonical_records", return_value=(rows, [])), patch.object(
                entitlement_service, "_legacy_features", return_value=[]
            ):
                state = entitlement_service.get_tenant_entitlements(7)
            self.assertEqual(state["capabilities"], [])

    def test_unknown_active_plan_and_dependency_failure_fail_closed(self):
        with patch.dict(environ, {"COMMERCIAL_ENTITLEMENT_TEST_LOOKUPS": "true"}), patch.object(
            entitlement_service,
            "_canonical_records",
            return_value=([{"id": 1, "tenant_id": 7, "plan_id": "forged", "state": "active"}], []),
        ), patch.object(entitlement_service, "_rows", return_value=[]):
            state = entitlement_service.get_tenant_entitlements(7)
        self.assertEqual(state["capabilities"], [])
        with patch.object(entitlement_service.service_supabase, "table", side_effect=TimeoutError("offline")):
            with self.assertRaises(HTTPException) as context:
                entitlement_service._canonical_records(7)
        self.assertEqual(context.exception.status_code, 503)

    def test_licensed_ai_is_separate_from_provider_availability(self):
        addon = [{"addon_id": "ai_analytics_starter", "state": "active", "quantity": 1}]
        with patch.dict(environ, {
            "COMMERCIAL_ENTITLEMENT_TEST_LOOKUPS": "true",
            "AI_FEATURE_ENABLED": "false",
        }, clear=False), patch.object(
            entitlement_service, "_canonical_records", return_value=self.canonical_state("business", addon)
        ), patch.object(entitlement_service, "_rows", return_value=[]):
            state = entitlement_service.get_tenant_entitlements(7)
        self.assertIn("ai_analytics", state["capabilities"])
        self.assertNotIn("ai_analytics", state["operational_capabilities"])
        self.assertEqual(state["capability_availability"]["ai_analytics"], "provider_unavailable")


if __name__ == "__main__":
    unittest.main()
