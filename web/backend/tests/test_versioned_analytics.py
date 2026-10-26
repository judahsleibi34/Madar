import unittest
from unittest.mock import patch

import pandas as pd
from fastapi import HTTPException

from services import versioned_analytics_service


PROJECT = "11111111-1111-4111-8111-111111111111"
DATASET = "22222222-2222-4222-8222-222222222222"
VERSION = "33333333-3333-4333-8333-333333333333"


def resolved(*, size=100, rows=4):
    return {
        "dataset": {"id": DATASET, "project_id": PROJECT},
        "version": {
            "id": VERSION, "version_number": 3, "version_kind": "derived",
            "size_bytes": size, "content_hash": "a" * 64,
            "file_metadata": {"rows": rows},
        },
        "storage_identifier": "version-3.csv",
    }


class VersionedAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame({
            "name": ["C", "A", "B", "D"],
            "amount": [30, 10, 20, None],
            "observed_at": ["2026-03-03", "2026-03-01", "2026-03-02", None],
        })

    def explore(self, **overrides):
        values = {
            "tenant_id": 1, "project_id": PROJECT, "user_id": 7,
            "dataset_id": DATASET, "version_id": VERSION, "columns": [],
            "filters": [], "sort": [], "limit": 100, "offset": 0,
        }
        values.update(overrides)
        with patch.object(versioned_analytics_service.project_dataset_service,
                          "resolve_project_dataset_version", return_value=resolved()) as resolve, \
             patch.object(versioned_analytics_service.data_services,
                          "read_dataset", return_value=self.frame.copy()) as read:
            result = versioned_analytics_service.explore_dataset_version(**values)
        resolve.assert_called_once_with(
            tenant_id=1, project_id=PROJECT, user_id=7,
            dataset_id=DATASET, version_id=VERSION, client=None,
        )
        read.assert_called_once_with("version-3.csv", tenant_id="1", user_id="7")
        return result

    def test_exact_version_filter_sort_and_paging(self):
        result = self.explore(
            columns=["name", "amount"],
            filters=[{"field": "amount", "operator": "gte", "value": "15"}],
            sort=[{"field": "amount", "direction": "desc"}], limit=1, offset=1,
        )
        self.assertEqual(result["rows"], [{"name": "B", "amount": 20.0}])
        self.assertEqual(result["pagination"], {
            "limit": 1, "offset": 1, "returned": 1, "total": 2, "has_more": False,
        })
        self.assertEqual(result["provenance"]["dataset_version_id"], VERSION)

    def test_date_and_missing_filters_are_typed(self):
        result = self.explore(filters=[
            {"field": "observed_at", "operator": "gte", "value": "2026-03-02"},
            {"field": "amount", "operator": "not_missing"},
        ])
        self.assertEqual([row["name"] for row in result["rows"]], ["C", "B"])

    def test_unknown_fields_and_text_ranges_fail_closed(self):
        for filters in (
            [{"field": "private", "operator": "eq", "value": "x"}],
            [{"field": "name", "operator": "gte", "value": "A"}],
        ):
            with self.subTest(filters=filters), self.assertRaises(HTTPException) as denied:
                self.explore(filters=filters)
            self.assertEqual(denied.exception.status_code, 422)

    def test_query_bounds_are_enforced_before_storage_read(self):
        with self.assertRaises(HTTPException) as denied:
            self.explore(limit=101)
        self.assertEqual(denied.exception.status_code, 422)

        with patch.object(versioned_analytics_service.project_dataset_service,
                          "resolve_project_dataset_version", return_value=resolved(size=11 * 1024 * 1024)), \
             patch.object(versioned_analytics_service.data_services, "read_dataset") as read:
            with self.assertRaises(HTTPException) as too_large:
                versioned_analytics_service.explore_dataset_version(
                    tenant_id=1, project_id=PROJECT, user_id=7, dataset_id=DATASET,
                    version_id=VERSION, columns=[], filters=[], sort=[], limit=10, offset=0,
                )
        self.assertEqual(too_large.exception.status_code, 413)
        read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
