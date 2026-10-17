from types import SimpleNamespace
import unittest
from unittest.mock import patch

from routes import calendar_routes as calendar


class Query:
    def __init__(self, database):
        self.database = database
        self.filters = []

    def select(self, _fields): return self
    def eq(self, key, value): self.filters.append((key, {value})); return self
    def in_(self, key, values): self.filters.append((key, set(values))); return self
    def order(self, key, desc=False): self.ordering = key, desc; return self
    def limit(self, count): self.maximum = count; return self

    def execute(self):
        self.database.queries.append(self.filters)
        rows = [row for row in self.database.rows if all(row[key] in values for key, values in self.filters)]
        key, reverse = self.ordering
        return SimpleNamespace(data=sorted(rows, key=lambda row: row[key], reverse=reverse)[:self.maximum])


class CalendarReviewBatchTests(unittest.TestCase):
    def test_large_workspace_keeps_global_newest_limit_and_authorized_scope(self):
        identifiers = {f'event-{index:03}' for index in range(121)}
        database = SimpleNamespace(queries=[], rows=[{
            'id': f'review-{index:03}', 'event_id': f'event-{index:03}', 'tenant_id': 7,
            'created_at': f'2026-01-01T00:{index // 60:02}:{index % 60:02}Z',
            'disposition': 'quarantined',
        } for index in range(121)])
        database.rows += [dict(database.rows[-1], id='foreign-tenant', tenant_id=8, created_at='2099'),
                          dict(database.rows[-1], id='foreign-event', event_id='unauthorized', created_at='2099'),
                          dict(database.rows[-1], id='released-review', disposition='released', created_at='2099')]
        def table(name):
            self.assertEqual(name, 'calendar_invitation_reviews')
            return Query(database)
        database.table = table
        with patch.object(calendar, 'service_supabase', database), patch.object(calendar, 'sanitized_invitation', side_effect=lambda row: {'id': row['id']}):
            result = calendar.workspace_invitation_reviews(SimpleNamespace(tenant_id=7), identifiers)
        self.assertEqual([row['id'] for row in result], [f'review-{index:03}' for index in range(120, 70, -1)])
        self.assertEqual(len(database.queries), 3)
        self.assertTrue(all(len(dict(filters)['event_id']) <= 50 for filters in database.queries))

    def test_empty_authorized_event_set_performs_no_query(self):
        with patch.object(calendar, 'service_supabase') as database:
            self.assertEqual(calendar.workspace_invitation_reviews(SimpleNamespace(tenant_id=7), set()), [])
        database.table.assert_not_called()
