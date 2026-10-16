from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from services import admin_user_service


class AdminUserQueryCountTests(unittest.TestCase):
    def query(self, rows, total):
        query = Mock()
        for name in ("select", "order", "ilike", "range"):
            getattr(query, name).return_value = query
        query.execute.return_value = SimpleNamespace(data=rows, count=total)
        return query

    def test_filtered_pagination_and_count_share_one_provider_request(self):
        rows = [{"id": index, "tenant_id": None} for index in (3, 4, 5)]
        query = self.query(rows, 41)
        client = Mock()
        client.table.return_value = query
        with patch.object(admin_user_service, "service_supabase", client):
            result = admin_user_service.list_users_with_features(page=2, page_size=2, search="fixture@example.com")
        client.table.assert_called_once_with("users")
        query.select.assert_called_once_with(admin_user_service.USER_SELECT_COLUMNS, count="exact")
        query.ilike.assert_called_once_with("email", "%fixture@example.com%")
        query.range.assert_called_once_with(2, 4)
        query.execute.assert_called_once()
        self.assertEqual([row["id"] for row in result["items"]], [3, 4])
        self.assertEqual(result["pagination"]["total_count"], 41)
        self.assertTrue(result["pagination"]["has_more"])

    def test_empty_offset_page_retains_filtered_total_from_response_metadata(self):
        query = self.query([], 3)
        client = Mock()
        client.table.return_value = query
        with patch.object(admin_user_service, "service_supabase", client):
            result = admin_user_service.list_users_with_features(limit=10, offset=100)
        self.assertEqual(result["items"], [])
        self.assertEqual(result["pagination"]["total_count"], 3)
        self.assertFalse(result["pagination"]["has_more"])
        query.execute.assert_called_once()

    def test_native_unsatisfiable_range_retains_empty_page_contract(self):
        class RangeError(RuntimeError):
            code = "PGRST103"
        page = self.query([], None)
        page.execute.side_effect = RangeError("Requested range not satisfiable")
        count = self.query([], 3)
        client = Mock()
        client.table.side_effect = [page, count]
        with patch.object(admin_user_service, "service_supabase", client):
            result = admin_user_service.list_users_with_features(offset=100, search="fixture")
        self.assertEqual(result["items"], [])
        self.assertEqual(result["pagination"]["total_count"], 3)
        count.select.assert_called_once_with("id", count="exact")
        count.ilike.assert_called_once_with("email", "%fixture%")
        count.range.assert_called_once_with(0, 0)
