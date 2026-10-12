"""The migration boundary must preserve original columns, Auth and assets."""
import copy
import unittest
from unittest.mock import patch
from deployment.lib import completed_normal_database as m


class CustomerPreservationTests(unittest.TestCase):
    def setUp(self):
        names=['public.application_schema_state',*(f'public.table_{i:02}' for i in range(95)),
            'auth.users','auth.identities','auth.mfa_factors','storage.objects','storage.buckets']
        self.before={'schema':115,'columns':{n:['id','original_value'] for n in names},
            'roots':{n:{'table':n,'count':3,'sha256':'a'*64} for n in names}}
        self.after=copy.deepcopy(self.before);self.after['schema']=136
        self.after['roots']['public.application_schema_state']['sha256']='b'*64

    def test_only_schema_row_change_preserves_all_96_original_tables_and_auth_storage(self):
        result=m.verify_migration_customer_preservation(self.before,self.after)
        self.assertTrue(result['only_schema_state_changed']);self.assertFalse(result['database_restored'])

    def test_customer_password_mfa_tenant_and_object_changes_fail_closed(self):
        for name in ['public.table_02','auth.users','auth.identities','auth.mfa_factors','storage.objects','storage.buckets']:
            with self.subTest(name=name):
                changed=copy.deepcopy(self.after);changed['roots'][name]['sha256']='c'*64
                with self.assertRaisesRegex(RuntimeError,'existing_customer_values_changed'):
                    m.verify_migration_customer_preservation(self.before,changed)

    def test_missing_table_column_or_schema_state_row_is_not_a_pass(self):
        for kind in ('table','column','schema_row'):
            changed=copy.deepcopy(self.after)
            if kind=='table':del changed['roots']['auth.mfa_factors']
            elif kind=='column':changed['columns']['public.table_00'].append('new')
            else:changed['roots']['public.application_schema_state']['count']=0
            with self.subTest(kind=kind),self.assertRaises(RuntimeError):
                m.verify_migration_customer_preservation(self.before,changed)

    def test_changed_snapshot_native_schema_is_rejected_before_sql(self):
        with patch.object(m,'observe_native',return_value=136):
            with self.assertRaisesRegex(RuntimeError,'source_schema_changed'):
                m.migration_customer_snapshot({'version':1,'operation':'completed-normal-schema115-136-upgrade'},object())


if __name__=='__main__':unittest.main()
