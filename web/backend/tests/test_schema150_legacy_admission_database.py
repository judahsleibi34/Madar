"""Legacy deletion backlog must block pre150 admission on real PostgreSQL.

The fixture is a marked disposable schema149 database. No migration, external
provider call, queue reset or inferred reconciliation is performed here. The
legacy ambiguous-outcome fixture represents an attempted operation, not proof
that a provider actually accepted it. Every fixture rolls back after the test.
"""
import os
from pathlib import Path
import sys
import unittest
from uuid import uuid4

from tests.disposable_database_support import connect_disposable_database

sys.path.insert(0, os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib import schema150_release as release

DSN = os.getenv('SCHEMA150_LEGACY_SYNTHETIC_DATABASE_DSN')


@unittest.skipUnless(DSN, 'Requires marked disposable schema149 PostgreSQL')
class LegacyDeletionAdmissionDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = connect_disposable_database(DSN, markers={'madar-notification-synthetic-rehearsal'})
        self.addCleanup(self.db.close)
        self.assertEqual(self.db.execute(
            "select schema_version from public.application_schema_state where contract_key='core'"
        ).fetchone()[0], 149)
        self.assertEqual(self.db.execute(
            "select count(*) from public.data_deletion_requests where state not in "
            "('completed','completed_with_retained_records','cancelled_before_execution')"
        ).fetchone()[0], 0, 'Unrelated unfinished fixture work must not be modified')
        identifier = self.db.execute('select system_identifier::text from pg_control_system()').fetchone()[0]
        self.contract = {'database': {'system_identifier': identifier}}
        self.key = uuid4()
        self.db.execute("set statement_timeout='5s'; begin")
        self.addCleanup(lambda: self.db.execute('rollback'))

    def observation(self):
        with self.db.cursor() as cursor:
            return release.observe_database_quiescence(cursor, self.contract, 149)

    def test_legacy_retry_with_external_attempt_and_no_live_claim_rejects(self):
        self.db.execute(
            "insert into public.data_deletion_requests(id,request_type,target_user_id_snapshot,state,"
            "attempt_count,last_error_code) values(%s,'user',2147483001,'waiting_retry',1,"
            "'storage_provider_unavailable')", (self.key,))
        self.db.execute(
            "insert into public.data_deletion_steps(request_id,step_key,step_order,state,attempts,"
            "last_error_code) values(%s,'delete_provider_objects',50,'waiting_retry',1,"
            "'storage_provider_unavailable')", (self.key,))
        self.db.execute(
            "insert into public.data_deletion_resources(request_id,resource_kind,resource_key) "
            "values(%s,'supabase_avatar',%s)", (self.key, 'users/' + str(uuid4()) + '/synthetic.png'))
        before = self.db.execute(
            'select to_jsonb(r) from public.data_deletion_requests r where id=%s', (self.key,)).fetchone()[0]
        with self.assertRaisesRegex(RuntimeError, 'not_quiescent'):
            self.observation()
        self.assertEqual(self.db.execute(
            'select to_jsonb(r) from public.data_deletion_requests r where id=%s', (self.key,)).fetchone()[0], before)

    def test_legacy_unstarted_tenant_with_lost_freeze_preimages_rejects(self):
        self.db.execute(
            "insert into public.data_deletion_requests(id,request_type,target_tenant_id_snapshot,"
            "state,freeze_snapshot) values(%s,'tenant',2147483002,'pending',"
            "'{\"lifecycle_state\":\"active\"}'::jsonb)", (self.key,))
        # Migration083 captured tenant user statuses AFTER freezing them. There
        # is no safe automatic inference of the former active/disabled status.
        self.db.execute(
            "insert into public.data_deletion_subjects(request_id,user_id_snapshot,subject_kind,"
            "account_status_snapshot) values(%s,2147483003,'tenant_platform_user','deletion_pending')", (self.key,))
        self.db.execute(
            "insert into public.data_deletion_steps(request_id,step_key,step_order) values(%s,'freeze',10)", (self.key,))
        with self.assertRaisesRegex(RuntimeError, 'not_quiescent'):
            self.observation()
        self.assertEqual(self.db.execute(
            'select account_status_snapshot from public.data_deletion_subjects where request_id=%s',
            (self.key,)).fetchone()[0], 'deletion_pending')

    def test_terminal_cancelled_request_with_pending_steps_is_preserved_and_allowed(self):
        self.db.execute(
            "insert into public.data_deletion_requests(id,request_type,target_user_id_snapshot,state) "
            "values(%s,'user',2147483004,'cancelled_before_execution')", (self.key,))
        keys = ('freeze','revoke_sessions','revoke_integrations','stop_queued_work',
                'delete_provider_objects','delete_host_files','delete_application_data',
                'delete_auth_identities','verify','finalize')
        for order, key in enumerate(keys, 1):
            self.db.execute(
                'insert into public.data_deletion_steps(request_id,step_key,step_order) values(%s,%s,%s)',
                (self.key, key, order * 10))
        observed = self.observation()
        self.assertEqual(observed.get('legacy_deletion_backlog', 0), 0)
        self.assertEqual(self.db.execute(
            "select count(*) from public.data_deletion_steps where request_id=%s and state='pending'",
            (self.key,)).fetchone()[0], 10)


if __name__ == '__main__':
    unittest.main()
