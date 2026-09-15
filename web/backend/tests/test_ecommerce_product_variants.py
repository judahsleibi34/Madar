import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from routes import ecommerce_routes
from routes.ecommerce_routes import ProductPayload
from routes.public_site_routes import PublicStoreOrderCreate


WEB_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = WEB_ROOT / "database" / "migrations" / "096_create_ecommerce_product_variants.sql"
MIRROR = WEB_ROOT / "supabase" / "migrations" / "096_create_ecommerce_product_variants.sql"
PRESENTATION_MIGRATION = WEB_ROOT / "database" / "migrations" / "099_add_variant_attribute_presentation.sql"
PRESENTATION_MIRROR = WEB_ROOT / "supabase" / "migrations" / "099_add_variant_attribute_presentation.sql"
PRODUCT_ID = "11111111-1111-1111-1111-111111111111"
OPTION_ID = "22222222-2222-2222-2222-222222222222"
VALUE_ID = "33333333-3333-3333-3333-333333333333"
VARIANT_ID = "44444444-4444-4444-4444-444444444444"


def product_payload(**overrides):
    payload = {
        "slug": "shirt", "sku": "SHIRT", "translations": {"en": {"name": "Shirt", "description": ""}},
        "status": "draft", "price": "20.00", "currency": "ILS",
    }
    payload.update(overrides)
    return payload


class EcommerceProductVariantTests(unittest.TestCase):
    def test_simple_product_needs_no_fake_variant(self):
        product = ProductPayload(**product_payload())
        self.assertIsNone(product.options)
        self.assertIsNone(product.variants)

    def test_arbitrary_localized_option_value_and_explicit_variant_validate(self):
        product = ProductPayload(**product_payload(
            attributes=[{"id": VALUE_ID, "name_translations": {"en": "Material", "ar": "الخامة"}, "value_translations": {"en": "Cotton", "ar": "قطن"}}],
            options=[{"id": OPTION_ID, "code": "finish", "name_translations": {"en": "Finish", "ar": "التشطيب"}, "values": [{"id": VALUE_ID, "code": "matte", "value_translations": {"en": "Matte", "ar": "مطفي"}}]}],
            variants=[{"id": VARIANT_ID, "sku": "SHIRT-MATTE", "option_value_ids": [VALUE_ID]}],
        ))
        self.assertEqual(product.options[0].name_translations["en"], "Finish")
        self.assertEqual(product.variants[0].option_value_ids[0], product.options[0].values[0].id)
        self.assertEqual(product.options[0].display_type, "text")
        self.assertIsNone(product.options[0].values[0].color_hex)

    def test_generic_color_presentation_requires_and_preserves_real_swatch(self):
        product = ProductPayload(**product_payload(
            options=[{"id": OPTION_ID, "code": "finish", "display_type": "color", "name_translations": {"en": "Finish", "ar": "التشطيب"}, "values": [
                {"id": VALUE_ID, "code": "matte-red", "value_translations": {"en": "Matte red", "ar": "أحمر مطفي"}, "color_hex": "#E53935"},
            ]}],
            variants=[{"id": VARIANT_ID, "sku": "SHIRT-MATTE-RED", "option_value_ids": [VALUE_ID]}],
        ))
        self.assertEqual(product.options[0].display_type, "color")
        self.assertEqual(product.options[0].values[0].color_hex, "#E53935")

        with self.assertRaises(ValidationError):
            ProductPayload(**product_payload(options=[{
                "id": OPTION_ID, "code": "finish", "display_type": "color",
                "name_translations": {"en": "Finish"},
                "values": [{"id": VALUE_ID, "code": "matte", "value_translations": {"en": "Matte"}}],
            }], variants=[]))

    def test_color_metadata_is_sent_through_the_v2_aggregate_rpc(self):
        product = ProductPayload(**product_payload(
            options=[{"id": OPTION_ID, "code": "finish", "display_type": "color", "name_translations": {"en": "Finish"}, "values": [
                {"id": VALUE_ID, "code": "red", "value_translations": {"en": "Red"}, "color_hex": "#E53935"},
            ]}],
            variants=[{"id": VARIANT_ID, "sku": "SHIRT-RED", "option_value_ids": [VALUE_ID]}],
        ))

        class Query:
            def execute(self):
                return type("Result", (), {"data": {"saved": True}})()

        class Service:
            def __init__(self):
                self.calls = []

            def rpc(self, name, params):
                self.calls.append((name, params))
                return Query()

        service = Service()
        with patch.object(ecommerce_routes, "service_supabase", service):
            ecommerce_routes._save_product_aggregate(7, PRODUCT_ID, product)

        self.assertEqual(service.calls[0][0], "save_ecommerce_product_aggregate_v2_safe")
        option = service.calls[0][1]["p_options"][0]
        self.assertEqual(option["display_type"], "color")
        self.assertEqual(option["values"][0]["color_hex"], "#E53935")

        with self.assertRaises(ValidationError):
            ProductPayload(**product_payload(options=[{
                "id": OPTION_ID, "code": "size", "display_type": "text",
                "name_translations": {"en": "Size"},
                "values": [{"id": VALUE_ID, "code": "s", "value_translations": {"en": "S"}, "color_hex": "#FFFFFF"}],
            }], variants=[]))

    def test_duplicate_option_and_value_names_are_rejected(self):
        duplicate_options = [
            {"id": OPTION_ID, "code": "finish", "name_translations": {"en": "Finish"}, "values": []},
            {"id": "55555555-5555-5555-5555-555555555555", "code": "finish-two", "name_translations": {"en": "finish"}, "values": []},
        ]
        with self.assertRaises(ValidationError):
            ProductPayload(**product_payload(options=duplicate_options, variants=[]))

        duplicate_values = [{"id": OPTION_ID, "code": "finish", "name_translations": {"en": "Finish"}, "values": [
            {"id": VALUE_ID, "code": "matte", "value_translations": {"en": "Matte"}},
            {"id": "66666666-6666-6666-6666-666666666666", "code": "matte-two", "value_translations": {"en": "matte"}},
        ]}]
        with self.assertRaises(ValidationError):
            ProductPayload(**product_payload(options=duplicate_values, variants=[]))

    def test_variant_requires_options_and_valid_effective_compare_at_price(self):
        with self.assertRaises(ValidationError):
            ProductPayload(**product_payload(variants=[{"id": VARIANT_ID, "sku": "FAKE", "option_value_ids": [VALUE_ID]}]))

        with self.assertRaises(ValidationError):
            ProductPayload(**product_payload(
                price="20.00",
                compare_at_price="25.00",
                options=[{"id": OPTION_ID, "code": "finish", "name_translations": {"en": "Finish"}, "values": [
                    {"id": VALUE_ID, "code": "matte", "value_translations": {"en": "Matte"}},
                ]}],
                variants=[{"id": VARIANT_ID, "sku": "SHIRT-MATTE", "price_override": "30.00", "option_value_ids": [VALUE_ID]}],
            ))

    def test_variant_cannot_reference_foreign_value(self):
        with self.assertRaises(ValidationError):
            ProductPayload(**product_payload(
                options=[{"id": OPTION_ID, "code": "finish", "name_translations": {"en": "Finish"}, "values": [{"id": VALUE_ID, "code": "matte", "value_translations": {"en": "Matte"}}]}],
                variants=[{"id": VARIANT_ID, "sku": "SHIRT-X", "option_value_ids": ["77777777-7777-7777-7777-777777777777"]}],
            ))

    def test_checkout_contract_accepts_variant_and_keeps_simple_legacy_item(self):
        base = {"idempotency_key": "checkout-1234567890abcdef", "customer_name": "Buyer", "email": "buyer@example.com", "phone": "+970590000000", "service_area_id": "95000000-0000-0000-0000-000000000001", "street": "Main Street"}
        simple = PublicStoreOrderCreate(**base, items=[{"product_id": PRODUCT_ID, "quantity": 1}])
        variant = PublicStoreOrderCreate(**base, items=[{"product_id": PRODUCT_ID, "variant_id": VARIANT_ID, "quantity": 1}])
        self.assertIsNone(simple.items[0].variant_id)
        self.assertEqual(str(variant.items[0].variant_id), VARIANT_ID)

    def test_database_contract_is_mirrored_tenant_safe_and_atomic(self):
        self.assertEqual(MIGRATION.read_bytes(), MIRROR.read_bytes())
        sql = MIGRATION.read_text(encoding="utf-8").lower()
        for table in ("ecommerce_product_attributes", "ecommerce_product_options", "ecommerce_product_option_values", "ecommerce_product_variants", "ecommerce_variant_option_values"):
            self.assertIn(f"create table public.{table}", sql)
        self.assertIn("unique (tenant_id,product_id,normalized_name)", sql)
        self.assertIn("unique (tenant_id,product_id,option_signature)", sql)
        self.assertIn("save_ecommerce_product_aggregate_safe", sql)
        self.assertIn("for update", sql)
        self.assertIn("v_requested.variant_id", sql)
        self.assertIn("selected_options_snapshot", sql)
        self.assertIn("set inventory_quantity=inventory_quantity-v_allocated", sql)
        self.assertIn("set inventory_quantity=inventory_quantity+v_item.inventory_allocated_quantity", sql)
        self.assertIn("v_schema_version<>95", sql)
        self.assertIn("set schema_version = 96", sql)

    def test_presentation_extension_is_mirrored_forward_only_and_wraps_atomic_save(self):
        self.assertEqual(PRESENTATION_MIGRATION.read_bytes(), PRESENTATION_MIRROR.read_bytes())
        sql = PRESENTATION_MIGRATION.read_text(encoding="utf-8").lower()
        self.assertIn("add column display_type text not null default 'text'", sql)
        self.assertIn("add column color_hex text", sql)
        self.assertIn("save_ecommerce_product_aggregate_v2_safe", sql)
        self.assertIn("perform public.save_ecommerce_product_aggregate_safe", sql)
        self.assertIn("v_schema_version<>98", sql)
        self.assertIn("schema_version=99", sql)
        self.assertNotIn("drop table", sql)


if __name__ == "__main__":
    unittest.main()
