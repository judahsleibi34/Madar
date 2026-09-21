import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from routes import ecommerce_routes as routes


class CustomDeliveryLocationTests(unittest.TestCase):
    def test_flexible_hierarchy_and_country_only(self):
        location = routes.CustomDeliveryAreaCreate(country=" Jordan ", levels=[" Amman ", "Downtown"])
        self.assertEqual(location.country, "Jordan")
        self.assertEqual(location.levels, ["Amman", "Downtown"])
        self.assertEqual(routes.CustomDeliveryAreaCreate(country="Canada").levels, [])
        for payload in ({"country": " "}, {"country": "Jordan", "levels": [" "]}, {"country": "Jordan", "levels": ["x"] * 6}):
            with self.assertRaises(ValidationError):
                routes.CustomDeliveryAreaCreate(**payload)

    def test_custom_namespace_is_private_and_shared_areas_remain_available(self):
        self.assertTrue(routes._delivery_area_belongs_to_tenant({"code": "ramallah"}, 7))
        self.assertTrue(routes._delivery_area_belongs_to_tenant({"code": "custom-7-abc"}, 7))
        self.assertFalse(routes._delivery_area_belongs_to_tenant({"code": "custom-70-abc"}, 7))
        self.assertFalse(routes._delivery_area_belongs_to_tenant({"code": "custom-8-abc"}, 7))

    @patch.object(routes, "invalidate_ecommerce_cache")
    @patch.object(routes, "_require_role")
    @patch.object(routes, "_require_ecommerce_access", return_value=SimpleNamespace(tenant_id=7))
    @patch.object(routes, "_rows", side_effect=[[], []])
    @patch.object(routes, "service_supabase")
    def test_creation_uses_server_owned_code_and_is_not_enabled_until_save(self, database, rows, access, role, invalidate):
        result = routes.create_custom_delivery_area(routes.CustomDeliveryAreaCreate(country="Jordan", levels=["Amman", "Downtown"]), None, None)
        area = result["area"]
        self.assertTrue(area["code"].startswith("custom-7-"))
        self.assertEqual(area["name_en"], "Jordan / Amman / Downtown")
        self.assertEqual(area["name_ar"], area["name_en"])
        self.assertFalse(area["enabled"])
        database.table.return_value.insert.assert_called_once()
        database.rpc.assert_not_called()
        role.assert_called_once()

    @patch.object(routes, "_require_ecommerce_access", return_value=SimpleNamespace(tenant_id=7))
    @patch.object(routes, "_rows", side_effect=[[{"id": "shared", "code": "ramallah"}, {"id": "own", "code": "custom-7-own"}, {"id": "other", "code": "custom-8-other"}], []])
    @patch.object(routes, "service_supabase")
    def test_list_does_not_expose_other_store_locations(self, database, rows, access):
        result = routes.get_delivery_areas(None, None)
        self.assertEqual([area["id"] for area in result["areas"]], ["shared", "own"])

    @patch.object(routes, "_require_role")
    @patch.object(routes, "_require_ecommerce_access", return_value=SimpleNamespace(tenant_id=7))
    @patch.object(routes, "_rows", return_value=[{"id": "11111111-1111-4111-8111-111111111111", "code": "custom-8-other"}])
    @patch.object(routes, "service_supabase")
    def test_save_rejects_other_store_location_before_rpc(self, database, rows, access, role):
        with self.assertRaises(HTTPException) as caught:
            routes.update_delivery_areas(routes.DeliveryAreasUpdate(enabled_service_area_ids=["11111111-1111-4111-8111-111111111111"]), None, None)
        self.assertEqual(caught.exception.status_code, 400)
        database.rpc.assert_not_called()

    @patch.object(routes, "_require_role")
    @patch.object(routes, "_require_ecommerce_access", return_value=SimpleNamespace(tenant_id=7))
    @patch.object(routes, "_rows", return_value=[{"id": "existing", "name_en": "Jordan / Amman"}])
    @patch.object(routes, "service_supabase")
    def test_duplicate_locations_are_rejected(self, database, rows, access, role):
        with self.assertRaises(HTTPException) as caught:
            routes.create_custom_delivery_area(routes.CustomDeliveryAreaCreate(country="Jordan", levels=["Amman"]), None, None)
        self.assertEqual(caught.exception.status_code, 409)
        database.table.return_value.insert.assert_not_called()

    @patch.object(routes, "invalidate_ecommerce_cache")
    @patch.object(routes, "_require_role")
    @patch.object(routes, "_require_ecommerce_access", return_value=SimpleNamespace(tenant_id=7))
    @patch.object(routes, "_rows", return_value=[{"id": "11111111-1111-4111-8111-111111111111", "code": "custom-7-own"}])
    @patch.object(routes, "service_supabase")
    def test_owner_can_soft_delete_custom_location(self, database, rows, access, role, invalidate):
        result = routes.delete_custom_delivery_area("11111111-1111-4111-8111-111111111111", None, None)
        self.assertTrue(result["deleted"])
        database.table.assert_any_call("ecommerce_delivery_pricing")
        database.table.assert_any_call("ecommerce_tenant_service_areas")
        database.table.assert_any_call("ecommerce_service_areas")
        database.table.return_value.update.assert_called_once_with({"active": False})
        invalidate.assert_called_once_with(7)

    @patch.object(routes, "_require_role")
    @patch.object(routes, "_require_ecommerce_access", return_value=SimpleNamespace(tenant_id=7))
    @patch.object(routes, "_rows", return_value=[])
    @patch.object(routes, "service_supabase")
    def test_other_store_cannot_delete_custom_location(self, database, rows, access, role):
        with self.assertRaises(HTTPException) as caught:
            routes.delete_custom_delivery_area("11111111-1111-4111-8111-111111111111", None, None)
        self.assertEqual(caught.exception.status_code, 404)
        database.table.return_value.update.assert_not_called()

    @patch.object(routes, "_require_role")
    @patch.object(routes, "_require_ecommerce_access", return_value=SimpleNamespace(tenant_id=7))
    @patch.object(routes, "_rows", side_effect=[[], [
        {"id": "22222222-2222-4222-8222-222222222222", "code": "nablus"},
    ], []])
    @patch.object(routes, "service_supabase")
    def test_pricing_rejects_disabled_destination(self, database, rows, access, role):
        payload = routes.DeliveryPricingBulkUpdate(
            prices=[{"service_area_id": "22222222-2222-4222-8222-222222222222", "price": 5}],
        )
        with self.assertRaises(HTTPException) as caught:
            routes.update_delivery_pricing(payload, None, None)
        self.assertEqual(caught.exception.status_code, 400)
        database.table.return_value.insert.assert_not_called()

    @patch.object(routes, "_require_role")
    @patch.object(routes, "_require_ecommerce_access", return_value=SimpleNamespace(tenant_id=7))
    @patch.object(routes, "_rows", side_effect=[[], [
        {"id": "22222222-2222-4222-8222-222222222222", "code": "nablus"},
    ], [
        {"service_area_id": "22222222-2222-4222-8222-222222222222"},
        {"service_area_id": "33333333-3333-4333-8333-333333333333"},
    ]])
    @patch.object(routes, "service_supabase")
    def test_pricing_requires_a_price_for_every_enabled_area(self, database, rows, access, role):
        payload = routes.DeliveryPricingBulkUpdate(
            prices=[{"service_area_id": "22222222-2222-4222-8222-222222222222", "price": 5}],
        )
        with self.assertRaises(HTTPException) as caught:
            routes.update_delivery_pricing(payload, None, None)
        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn("every enabled area", caught.exception.detail)
        database.table.return_value.insert.assert_not_called()

    @patch.object(routes, "_require_role")
    @patch.object(routes, "_require_ecommerce_access", return_value=SimpleNamespace(tenant_id=7))
    @patch.object(routes, "_rows", side_effect=RuntimeError("missing relation"))
    @patch.object(routes, "service_supabase")
    def test_pricing_save_reports_upgrade_required_instead_of_500(self, database, rows, access, role):
        payload = routes.DeliveryPricingBulkUpdate(
            prices=[],
        )
        with self.assertRaises(HTTPException) as caught:
            routes.update_delivery_pricing(payload, None, None)
        self.assertEqual(caught.exception.status_code, 503)
        self.assertIn("migration 104", caught.exception.detail)
