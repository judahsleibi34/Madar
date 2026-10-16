from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from services import admin_user_service


class AdminUserQueryContractTests(unittest.TestCase):
    def query(self, rows, total):
        query = Mock()
        for name in ("select", "order", "ilike", "range"):
            getattr(query, name).return_value = query
        query.execute.return_value = SimpleNamespace(data=rows, count=total)
        return query

    def test_filtered_pagination_preserves_count_and_extra_row_contract(self):
        rows = [{"id": index, "tenant_id": None} for index in (3, 4, 5)]
        query = self.query(rows, None)
        count = self.query([], 41)
        client = Mock()
        client.table.side_effect = [query, count]
        with patch.object(admin_user_service, "service_supabase", client):
            result = admin_user_service.list_users_with_features(page=2, page_size=2, search="fixture@example.com")
        self.assertEqual(client.table.call_count, 2)
        query.select.assert_called_once_with(admin_user_service.USER_SELECT_COLUMNS)
        count.select.assert_called_once_with("id", count="exact")
        query.ilike.assert_called_once_with("email", "%fixture@example.com%")
        count.ilike.assert_called_once_with("email", "%fixture@example.com%")
        query.range.assert_called_once_with(2, 4)
        query.execute.assert_called_once()
        self.assertEqual([row["id"] for row in result["items"]], [3, 4])
        self.assertEqual(result["pagination"]["total_count"], 41)
        self.assertTrue(result["pagination"]["has_more"])

    def test_empty_offset_page_retains_filtered_total(self):
        query = self.query([], None)
        count = self.query([], 3)
        client = Mock()
        client.table.side_effect = [query, count]
        with patch.object(admin_user_service, "service_supabase", client):
            result = admin_user_service.list_users_with_features(limit=10, offset=100)
        self.assertEqual(result["items"], [])
        self.assertEqual(result["pagination"]["total_count"], 3)
        self.assertFalse(result["pagination"]["has_more"])
        query.execute.assert_called_once()

    def test_count_dependency_failure_remains_an_error_without_disclosing_values(self):
        from fastapi import HTTPException
        page = self.query([], None)
        count = self.query([], 3)
        count.execute.side_effect = RuntimeError("private-provider-value")
        client = Mock()
        client.table.side_effect = [page, count]
        with patch.object(admin_user_service, "service_supabase", client):
            with self.assertRaises(HTTPException) as caught:
                admin_user_service.list_users_with_features(offset=100, search="fixture")
        self.assertEqual(caught.exception.status_code, 500)
        self.assertNotIn("private-provider-value", str(caught.exception.detail))
