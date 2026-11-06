"""Native source/restore semantic equivalence and adversarial catalog checks."""
import os,unittest
from deployment.lib.migration_drift import observe
SOURCE=os.getenv('MADAR_SEMANTIC_SOURCE_DSN');RESTORE=os.getenv('MADAR_SEMANTIC_RESTORE_DSN')
IDS=(os.getenv('MADAR_SEMANTIC_SOURCE_ID'),os.getenv('MADAR_SEMANTIC_RESTORE_ID'))
@unittest.skipUnless(SOURCE and RESTORE and all(IDS),'Requires exact owned source and logical-restore clusters')
class SemanticRestoreDatabaseTests(unittest.TestCase):
    def setUp(self):
        import psycopg
        self.source=psycopg.connect(SOURCE,autocommit=True);self.restore=psycopg.connect(RESTORE,autocommit=True)
        self.addCleanup(self.source.close);self.addCleanup(self.restore.close)
        a=observe(self.source,required_protocols={},semantic=True);b=observe(self.restore,required_protocols={},semantic=True)
        self.assertEqual((a.system_identifier,b.system_identifier),IDS)
        self.assertNotEqual(IDS[0],IDS[1]);self.assertEqual(a.semantic_sha256,b.semantic_sha256)
        self.baseline=a.semantic_sha256
    def reject(self):
        with self.assertRaisesRegex(RuntimeError,'semantic_drift_before_protocol_execution'):
            observe(self.restore,required_protocols={'deletion':2},expected_semantic_sha256=self.baseline)
    def test_logical_restore_matches_without_replacing_physical_drift_baselines(self):
        a=observe(self.source,required_protocols={},semantic=True);b=observe(self.restore,required_protocols={},semantic=True)
        self.assertNotEqual(a.structure_sha256,b.structure_sha256)
        self.assertEqual(a.semantic_sha256,b.semantic_sha256)
        with self.assertRaisesRegex(RuntimeError,'drift_detected_before_protocol_execution'):
            observe(self.restore,required_protocols={'deletion':2},expected_structure_sha256=a.structure_sha256)
    def test_privilege_escalation_is_not_normalized_away(self):
        try:self.restore.execute('grant select on public.automatic_safe_items to authenticated');self.reject()
        finally:self.restore.execute('revoke select on public.automatic_safe_items from authenticated')
    def test_protocol_substitution_refuses_before_function_execution(self):
        original=self.restore.execute("select pg_get_functiondef('public.data_deletion_ownership_protocol()'::regprocedure)").fetchone()[0]
        try:
            self.restore.execute("create or replace function public.data_deletion_ownership_protocol() returns integer language plpgsql stable security definer set search_path='' as $$begin raise exception 'untrusted_protocol_executed';end$$")
            self.reject()
        finally:self.restore.execute(original)
    def test_bypassrls_role_change_refuses(self):
        self.assertFalse(self.restore.execute("select rolbypassrls from pg_roles where rolname='authenticated'").fetchone()[0])
        try:self.restore.execute('alter role authenticated bypassrls');self.reject()
        finally:self.restore.execute('alter role authenticated nobypassrls')
    def test_internal_fk_trigger_disablement_refuses(self):
        self.assertEqual(self.restore.execute("select count(*)>0 and bool_and(tgenabled='O') from pg_trigger where tgrelid='public.users'::regclass").fetchone(),(True,))
        try:self.restore.execute('alter table public.users disable trigger all');self.reject()
        finally:self.restore.execute('alter table public.users enable trigger all')
