"""Exact 144→146 extension of the existing maintenance coordinator."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from test_completed_normal_application_release import application_contract
from test_completed_normal_manual_execution import ManualExecutionTests
from deployment.lib import completed_normal_admission as admission
from deployment.lib.completed_normal_database import verify_migration_customer_preservation
from deployment.lib.completed_normal_profile import COMMERCIAL, LEGACY, MANUAL, APPLICATION, profile, expected_origin_grant
from deployment.lib.migration_executor import MigrationManifest


def commercial_contract():
    value=application_contract()
    value.update(version=COMMERCIAL.version,operation=COMMERCIAL.operation,database_structure_sha256='c'*64)
    value['candidate'].update(compatible_min=144,compatible_max=146)
    root=Path(value['source_roles']['completion_root'])
    value['historical_files']={str(root/name):'7'*64 for name in admission.APPLICATION_HISTORICAL_NAMES}
    return value


class CommercialContractTests(unittest.TestCase):
    def test_fresh_operation_does_not_rewrite_historical_profiles(self):
        value=commercial_contract();admission.validate_contract(value)
        self.assertIs(profile(value),COMMERCIAL)
        self.assertEqual((COMMERCIAL.source,COMMERCIAL.target,COMMERCIAL.migrations,COMMERCIAL.excluded),(144,146,(145,146),()))
        self.assertEqual((LEGACY.target,MANUAL.target,APPLICATION.target),(136,144,144))
        for wrong in (142,143,147,True):self.assertFalse(COMMERCIAL.supports(wrong))
        for bounds in ((136,144),(144,147),(145,146)):
            bad=copy.deepcopy(value);bad['candidate'].update(zip(('compatible_min','compatible_max'),bounds))
            with self.assertRaises(RuntimeError):admission.validate_contract(bad)
        self.assertEqual(expected_origin_grant(value,'NORMAL')['compatible_max'],144)

    def test_live_writes_do_not_change_authorized_source_but_schema_drift_rejects(self):
        from deployment.lib.completed_normal_database import verify_preparation_baseline
        contract=commercial_contract()
        live={'table_roots_sha256':'0'*64,'identity_roots_sha256':'0'*64}
        with patch('deployment.lib.completed_normal_database.database_structure_digest',return_value='c'*64):
            verify_preparation_baseline(contract,object(),live)
        with patch('deployment.lib.completed_normal_database.database_structure_digest',return_value='f'*64):
            with self.assertRaisesRegex(RuntimeError,'database_structure_changed'):
                verify_preparation_baseline(contract,object(),live)
        with self.assertRaisesRegex(RuntimeError,'current_customer_data_changed'):
            verify_preparation_baseline(application_contract(),object(),live)

    def test_only_original_checksum_pinned_145_and146_are_selected(self):
        root=Path(__file__).resolve().parents[3]
        base=root/'web/deployment/releases'
        manifest=MigrationManifest.load(base/COMMERCIAL.manifest,root)
        self.assertEqual(tuple(m.number for m in manifest.migrations),(145,146))
        original=[]
        for filename in ('migrations-144-145-commercial.json','migrations-145-146-price-book.json'):
            original+=json.loads((base/filename).read_text())['migrations']
        self.assertEqual(json.loads((base/COMMERCIAL.manifest).read_text())['migrations'],original)
        for migration in manifest.migrations:
            import hashlib
            self.assertEqual(hashlib.sha256(migration.path.read_bytes()).hexdigest(),migration.sha256)

    def test_only_exact_verified_catalog_addition_can_change_existing_table_root(self):
        roots={f'public.test{i}':{'table':f'public.test{i}','count':1,'sha256':'a'*64} for i in range(101)}
        for name in ('public.application_schema_state','public.commercial_price_books'):
            roots[name]={'table':name,'count':1,'sha256':'a'*64}
        before={'schema':144,'columns':{'same':['id']},'roots':roots}
        after=copy.deepcopy(before);after['schema']=146
        after['roots']['public.application_schema_state']['sha256']='b'*64
        after['roots']['public.commercial_price_books'].update(count=2,sha256='c'*64)
        after['commercial_addition']={'verified':True,'preserved_original_rows':copy.deepcopy(roots['public.commercial_price_books'])}
        self.assertTrue(verify_migration_customer_preservation(before,after,contract=commercial_contract())['original_rows_preserved'])
        for corrupt in ('customer','catalog','unverified'):
            bad=copy.deepcopy(after)
            if corrupt=='customer':bad['roots']['public.test0']['sha256']='f'*64
            if corrupt=='catalog':bad['commercial_addition']['preserved_original_rows']['sha256']='f'*64
            if corrupt=='unverified':bad['commercial_addition']['verified']=False
            with self.assertRaises(RuntimeError):verify_migration_customer_preservation(before,bad,contract=commercial_contract())


class CommercialExecutionTests(ManualExecutionTests):
    source_schema=144
    target_schema=146
    make_contract=staticmethod(commercial_contract)
    test_only_target_grant_follows_verified_backup_and_actual_sql_completion=None
    test_pre_migration_failures_never_grant_normal=None
    test_post_migration_failure_preserves144_and_revokes_writes=None
    test_changed_retirement_stops_before_candidate_and_sql=None

    def test_normal_only_after_migrations_preservation_and_target_acceptance(self):
        result=self.driver.execute()
        self.assertEqual((result['schema'],result['mode']),(146,'NORMAL'))
        self.assertNotIn('grant_144',self.calls)
        self.assertLess(self.calls.index('backup_pre-migration'),self.calls.index('service_migrate'))
        self.assertLess(self.calls.index('customer_preservation'),self.calls.index('grant_146'))
        self.assertLess(self.calls.index('seal_sql_completion'),self.calls.index('grant_146'))
        self.assertEqual((self.schema,self.owners,self.backup_count),(146,1,2))

    def test_failure_after_sql_preserves_advanced_database_and_revokes_grant(self):
        self.failure='backup_post-migration'
        with self.assertRaises(RuntimeError):self.driver.execute()
        self.assertEqual((self.schema,self.mode),(146,'READ_ONLY'))
        self.assertNotIn('grant_144',self.calls)
        self.assertFalse(json.loads((self.root/'failure.json').read_text())['customer_database_restored'])
