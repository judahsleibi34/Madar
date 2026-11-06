"""Explicit legacy catalog projection for service-only unit fixtures.

These fixtures have no live PostgreSQL account catalog. Model its read-only
schema row instead of relaxing production unknown-schema/session/work guards.
This is not application, migration, recovery or authorization acceptance.
"""
from types import SimpleNamespace
from unittest.mock import patch


class SchemaStateQuery:
    def __init__(self, schema=160):
        if type(schema) is not int or not 146 <= schema <= 166:
            raise ValueError('legacy_unit_schema_required')
        self.schema=schema
    def select(self, fields):
        if fields != 'schema_version':raise AssertionError('unexpected_schema_projection')
        return self
    def eq(self, key, value):
        if (key,value)!=('contract_key','core'):raise AssertionError('unexpected_schema_identity')
        return self
    def limit(self, count):
        if count!=1:raise AssertionError('unbounded_schema_projection')
        return self
    def execute(self):return SimpleNamespace(data=[{'schema_version':self.schema}])


def install_legacy_schema(test_case, *, schema=160):
    """Supply only the unit fixture's metadata; retain all other client behavior."""
    from database import service_supabase
    native_table=service_supabase.table
    def table(name):
        return SchemaStateQuery(schema) if name=='application_schema_state' else native_table(name)
    scoped=patch.object(service_supabase,'table',side_effect=table)
    scoped.start();test_case.addCleanup(scoped.stop)
