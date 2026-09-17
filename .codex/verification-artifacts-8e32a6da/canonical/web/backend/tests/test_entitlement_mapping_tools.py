import unittest
from unittest.mock import patch

from scripts.apply_entitlement_mapping import MappingValidationError, validate_mapping
from scripts import report_entitlement_migration


def approved(tenant_id, *, state="active", plan_id="forms", mapping_id=None):
    return {
        "tenant_id": tenant_id,
        "target_state": state,
        "plan_id": plan_id,
        "grace_until": "2026-12-01T00:00:00Z" if state in {"grace", "grandfathered"} else None,
        "grandfather_reason": "explicit transition" if state == "grandfathered" else None,
        "approved_by": "authorized-operator",
        "approved_at": "2026-08-25T00:00:00Z",
        "mapping_id": mapping_id or f"mapping-{tenant_id}",
        "addons": [],
    }


class EntitlementMappingValidationTests(unittest.TestCase):
    def test_every_canonical_transition_target_is_representable(self):
        records = [
            approved(1, state="active"),
            approved(2, state="trial"),
            approved(3, state="grace"),
            approved(4, state="grandfathered"),
            approved(5, state="inactive", plan_id=None),
        ]
        result = validate_mapping({"tenants": records}, {1, 2, 3, 4, 5})
        self.assertEqual([row["target_state"] for row in result], ["active", "trial", "grace", "grandfathered", "inactive"])

    def test_missing_unknown_duplicate_and_unapproved_records_fail_closed(self):
        bad_documents = [
            ({"tenants": [approved(1)]}, {1, 2}),
            ({"tenants": [approved(1), approved(3)]}, {1, 2}),
            ({"tenants": [approved(1), approved(1, mapping_id="duplicate")]}, {1}),
            ({"tenants": [{**approved(1), "approved_by": None}]}, {1}),
            ({"tenants": [{**approved(1), "target_state": "grace", "grace_until": None}]}, {1}),
            ({"tenants": [{**approved(1), "plan_id": "unknown"}]}, {1}),
        ]
        for document, tenants in bad_documents:
            with self.subTest(document=document), self.assertRaises(MappingValidationError):
                validate_mapping(document, tenants)

    def test_addons_are_explicit_bounded_and_unique(self):
        record = approved(1)
        record["addons"] = [{"addon_id": "additional_storage_5gb", "quantity": 2}]
        self.assertEqual(validate_mapping({"tenants": [record]}, {1})[0]["addons"][0]["quantity"], 2)
        record["addons"] *= 2
        with self.assertRaises(MappingValidationError):
            validate_mapping({"tenants": [record]}, {1})


class EntitlementInventoryTests(unittest.TestCase):
    def test_effective_state_denies_missing_and_ambiguous_records(self):
        self.assertEqual(report_entitlement_migration._effective_state([], [])["state"], "missing")
        ambiguous = [
            {"plan_id": "forms", "state": "active"},
            {"plan_id": "website", "state": "trial"},
        ]
        state = report_entitlement_migration._effective_state(ambiguous, [])
        self.assertEqual(state["state"], "ambiguous")
        self.assertEqual(state["capabilities"], [])

    def test_usage_suggestion_is_advisory_and_requires_human_approval(self):
        suggestion = report_entitlement_migration._suggest_mapping(
            ["internal_calendar", "website_publish"], []
        )
        self.assertEqual(suggestion["mapping"], "business_plus candidate")
        self.assertTrue(suggestion["human_approval_needed"])

    def test_inventory_database_primitive_is_select_only(self):
        query = unittest.mock.MagicMock()
        query.select.return_value = query
        query.limit.return_value = query
        query.execute.return_value.data = [{"tenant_id": 1}]
        client = unittest.mock.MagicMock()
        client.table.return_value = query
        with patch.object(report_entitlement_migration, "service_supabase", client):
            self.assertEqual(report_entitlement_migration.rows("tenants", "tenant_id"), [{"tenant_id": 1}])
        query.insert.assert_not_called()
        query.update.assert_not_called()
        query.delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
