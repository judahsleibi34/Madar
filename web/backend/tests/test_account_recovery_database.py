"""Real HTTP/SQL candidate167 recovery acceptance; NOT erasure acceptance."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from fastapi import HTTPException
from postgrest import SyncPostgrestClient
from postgrest.exceptions import APIError

from tests.disposable_database_support import connect_disposable_database
from tests import test_schema166_deletion_compatibility_database as fixtures


@unittest.skipUnless(os.getenv("DELETION166_REST_URL"), "Requires the candidate167 disposable harness")
class AccountRecoveryDatabaseTests(unittest.TestCase):
    add_user = fixtures.Schema166DeletionCompatibilityTests.add_user
    dataset = fixtures.Schema166DeletionCompatibilityTests.dataset
    rpc = fixtures.Schema166DeletionCompatibilityTests.rpc

    def setUp(self):
        self.db = connect_disposable_database(os.environ["DELETION_FENCING_SYNTHETIC_DATABASE_DSN"],
            markers={"madar-notification-synthetic-rehearsal"})
        self.addCleanup(self.db.close)
        self.assertEqual(self.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0], 167)
        self.client = SyncPostgrestClient(os.environ["DELETION166_REST_URL"], headers={
            "Authorization": "Bearer " + os.environ["DELETION166_SERVICE_JWT"]})
        self.addCleanup(self.client.aclose)
        self.tenant = self.db.execute("insert into public.tenants(brand_name,owner_name) values('Recovery167','Fixture') returning tenant_id").fetchone()[0]
        self.user = self.add_user("member")
        self.owner = self.add_user("owner")
        self.admin = self.add_user("member")
        self.db.execute("update public.users set user_type='admin' where id=%s", (self.admin,))
        self.project = str(uuid4())
        self.db.execute("insert into public.builder_projects(id,tenant_id,owner_user_id,name,slug,status,draft_schema) values(%s,%s,%s,'Independent project',%s,'draft','{\"workspaceKind\":\"data\"}')", (self.project, self.tenant, self.owner, self.project))

    def enroll(self):
        return self.rpc("create_data_deletion_request", {"p_request_type": "user",
            "p_target_user_id": self.user, "p_target_tenant_id": None,
            "p_requested_by_user_id": self.user, "p_retention_until": "2000-01-01T00:00:00Z"})

    def recover(self, request):
        return self.rpc("recover_account_deletion167", {"p_request_id": request["id"], "p_actor_user_id": self.admin})

    def hold(self, request):
        return self.db.execute("select to_jsonb(h) from public.account_recovery_holds167 h where request_id=%s", (request["id"],)).fetchone()[0]

    def eligible_clock_fixture(self, request, age):
        # Only the marked superuser fixture can move persisted time; public RPCs
        # have no p_now/test-clock parameter and use the server clock exclusively.
        self.db.execute("with t as materialized(select clock_timestamp() as at_time) update public.account_recovery_holds167 set requested_at=t.at_time-%s::interval,erase_not_before=t.at_time-%s::interval+interval '2160 hours' from t where request_id=%s", (age, age, request["id"]))

    def test_day0_deadline_is_server_authoritative_and_account_stays_disabled(self):
        request = self.enroll()
        self.assertEqual(request["state"], "waiting_retention")
        self.assertEqual(self.hold(request)["state"], "recovery_pending")
        seconds = self.db.execute("select extract(epoch from erase_not_before-requested_at) from public.account_recovery_holds167 where request_id=%s", (request["id"],)).fetchone()[0]
        self.assertEqual(seconds, 90 * 24 * 3600)
        self.assertEqual(self.db.execute("select account_status from public.users where id=%s", (self.user,)).fetchone()[0], "deletion_pending")
        self.assertEqual(self.rpc("evaluate_account_erasure167", {"p_request_id": request["id"]})["state"], "recovery_pending")

    def test_day89_and_full90_day_boundary_never_enable_physical_erasure(self):
        request = self.enroll()
        self.eligible_clock_fixture(request, "89 days")
        self.assertEqual(self.rpc("evaluate_account_erasure167", {"p_request_id": request["id"]})["state"], "recovery_pending")
        self.eligible_clock_fixture(request, "90 days")
        boundary = self.rpc("evaluate_account_erasure167", {"p_request_id": request["id"]})
        self.assertEqual(boundary["state"], "erasure_blocked")
        self.assertEqual(boundary["blocker_code"], "erasure_inventory_unverified")
        self.assertEqual(self.rpc("evaluate_account_erasure167", {"p_request_id": request["id"]}), boundary)
        self.assertEqual(self.db.execute("select count(*) from public.data_deletion_effects where request_id=%s", (request["id"],)).fetchone()[0], 0)

    def test_recovery_is_authorized_idempotent_and_preserves_original_deadline(self):
        request = self.enroll()
        original = self.hold(request)
        with self.assertRaises(APIError):
            self.rpc("recover_account_deletion167", {"p_request_id": request["id"], "p_actor_user_id": self.owner})
        with self.assertRaisesRegex(APIError, "account_recovery_authorization_required"):
            self.rpc("cancel_data_deletion_request_v2", {"p_request_id": request["id"]})
        self.assertEqual(self.recover(request)["state"], "cancelled_before_execution")
        self.assertEqual(self.recover(request)["state"], "cancelled_before_execution")
        self.assertEqual(self.hold(request)["erase_not_before"], original["erase_not_before"])
        self.assertEqual(self.db.execute("select account_status from public.users where id=%s", (self.user,)).fetchone()[0], "active")

    def test_duplicate_concurrent_requests_do_not_extend_window(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(lambda _: self.enroll(), range(8)))
        self.assertEqual(len({row["id"] for row in rows}), 1)
        self.assertEqual(len({row["retention_until"] for row in rows}), 1)

    def test_recovery_and_eligibility_race_cannot_start_erasure(self):
        request = self.enroll()
        self.eligible_clock_fixture(request, "91 days")
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(self.recover, request)
            b = pool.submit(self.rpc, "evaluate_account_erasure167", {"p_request_id": request["id"]})
            a.result(); b.result()
        self.assertEqual(self.hold(request)["state"], "recovered")
        self.assertEqual(self.db.execute("select count(*) from public.data_deletion_effects where request_id=%s", (request["id"],)).fetchone()[0], 0)

    def test_shared_project_owned_content_is_preserved_and_blocks_erasure(self):
        _content, _digest, _key, _storage, dataset, version = self.dataset()
        before = self.db.execute("select to_jsonb(p) from public.builder_projects p where id=%s", (self.project,)).fetchone()[0]
        request = self.enroll()
        self.eligible_clock_fixture(request, "91 days")
        result = self.rpc("evaluate_account_erasure167", {"p_request_id": request["id"]})
        self.assertEqual(result["blocker_code"], "shared_project_ownership")
        self.assertEqual(self.db.execute("select to_jsonb(p) from public.builder_projects p where id=%s", (self.project,)).fetchone()[0], before)
        self.assertEqual(self.db.execute("select count(*) from public.data_dataset_versions where dataset_id=%s and id=%s", (dataset, version)).fetchone()[0], 1)

    def test_account_status_and_legacy_erasure_bypasses_are_denied(self):
        from workers import data_deletion_worker as worker
        request = self.enroll()
        self.assertEqual(self.rpc("data_deletion_ownership_protocol", {}), 0)
        with self.assertRaises(RuntimeError):
            worker.require_deletion_ownership_protocol(client=self.client)
        with self.assertRaises(APIError):
            self.rpc("claim_data_deletion_requests_v2", {"p_worker_id": "stale", "p_limit": 1, "p_lease_seconds": 300})
        with self.assertRaises(APIError):
            self.rpc("cancel_data_deletion_request160", {"p_request_id": request["id"]})
        with self.assertRaisesRegex(APIError, "account_recovery_hold_active"):
            self.client.table("users").update({"account_status": "active"}).eq("id", self.user).execute()

    def test_frozen_work_and_owner_swap_are_denied_independent_owner_is_unchanged(self):
        source = self.db.execute("insert into public.data_sources(tenant_id,project_id,creator_user_id,source_type,display_name) values(%s,%s,%s,'spreadsheet_upload','Recoverable') returning id", (self.tenant, self.project, self.user)).fetchone()[0]
        self.enroll()
        with self.assertRaisesRegex(APIError, "account_processing_frozen"):
            self.client.table("data_sources").update({"creator_user_id": self.owner}).eq("id", str(source)).execute()
        other = self.db.execute("insert into public.data_sources(tenant_id,project_id,creator_user_id,source_type,display_name) values(%s,%s,%s,'spreadsheet_upload','Independent') returning id", (self.tenant, self.project, self.owner)).fetchone()[0]
        self.assertIsNotNone(other)

    def test_inventory_retains_provider_identity_and_source_parquet_scope(self):
        self.dataset()
        provider_key = f"tenant_{self.tenant}/dataset/{uuid4()}/{'a' * 64}.csv"
        self.db.execute("insert into public.storage_objects(tenant_id,user_id,category,storage_key,size_bytes,sha256,storage_backend,storage_bucket,provider_object_key,verified_size_bytes,verified_sha256,integrity_verified_at) values(%s,%s,'dataset',%s,20,%s,'supabase_private','madar-data-immutable',%s,20,%s,now())", (self.tenant, self.user, f"tenant_{self.tenant}/user_{self.user}/provider.csv", 'a' * 64, provider_key, 'a' * 64))
        request = self.enroll()
        rows = self.db.execute("select resource_kind,identity from public.account_erasure_inventory167 where request_id=%s", (request["id"],)).fetchall()
        provider = next(row[1] for row in rows if row[0] == 'provider_storage')
        self.assertEqual(provider['provider_key'], provider_key)
        self.assertEqual(provider['bucket'], 'madar-data-immutable')
        self.assertEqual(sum(kind == 'parquet_scope' for kind, _ in rows), 2)

    def test_active_and_archived_report_files_are_preserved_and_inventoried(self):
        from services import bi_reporting_service as reports
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory, patch.object(reports, 'get_private_charts_dir', return_value=Path(directory)):
            paths = []
            report_ids = []
            for archived in (False, True):
                report_id = str(uuid4())
                report_ids.append(report_id)
                artifact = reports._write_csv_artifact(run={'id': report_id, 'tenant_id': self.tenant}, results=[])
                path = Path(directory) / artifact['storage_key'];paths.append(path)
                self.db.execute("insert into public.bi_report_runs(id,tenant_id,project_id,creator_user_id,dashboard_revision,trigger_type,deduplication_key,status,definition_snapshot,version_vector,result_snapshot,artifact_storage_key,artifact_filename,artifact_content_type,artifact_size_bytes,artifact_sha256,completed_at,archived_at) values(%s,%s,%s,%s,1,'manual',%s,'completed','{}','[]','{}',%s,%s,%s,%s,%s,now(),case when %s then now() end)", (report_id,self.tenant,self.project,self.user,report_id,artifact['storage_key'],artifact['filename'],artifact['content_type'],artifact['size_bytes'],artifact['sha256'],archived))
            old_token=str(uuid4())
            job=self.db.execute("insert into public.bi_report_cleanup_jobs(report_id,tenant_id,project_id,owner_user_id,available_at,status,lease_owner,lease_token,lease_fence,lease_expires_at) values(%s,%s,%s,%s,now(),'processing','old-cleaner',%s,7,now()+interval '5 minutes') returning id",(report_ids[0],self.tenant,self.project,self.user,old_token)).fetchone()[0]
            request = self.enroll()
            self.assertEqual(self.db.execute("select count(*) from public.account_erasure_inventory167 where request_id=%s and resource_kind='report_directory'", (request['id'],)).fetchone()[0], 2)
            self.assertEqual(self.db.execute("select status,lease_fence from public.bi_report_cleanup_jobs where id=%s",(job,)).fetchone(),('cancelled',8))
            with self.assertRaisesRegex(APIError,'account_processing_frozen'):
                self.rpc('authorize_bi_report_cleanup166',{'p_job_id':str(job),'p_lease_token':old_token,'p_lease_fence':7,'p_now':self.db.execute('select now()::text').fetchone()[0]})
            self.recover(request)
            with self.assertRaisesRegex(APIError,'report_cleanup_claim_lost'):
                self.rpc('authorize_bi_report_cleanup166',{'p_job_id':str(job),'p_lease_token':old_token,'p_lease_fence':7,'p_now':self.db.execute('select now()::text').fetchone()[0]})
            self.assertTrue(all(path.exists() for path in paths))

    def test_tenant_policy_remains_separate_and_no_client_roles_gain_authority(self):
        with self.assertRaisesRegex(APIError, 'tenant_erasure_policy_unapproved'):
            self.rpc('create_data_deletion_request', {'p_request_type':'tenant','p_target_user_id':None,
                'p_target_tenant_id':self.tenant,'p_requested_by_user_id':self.owner,'p_retention_until':None})
        with SyncPostgrestClient(os.environ['DELETION166_REST_URL'], headers={
                'Authorization':'Bearer '+os.environ['DELETION166_ANON_JWT']}) as client:
            with self.assertRaises(APIError):
                client.rpc('recover_account_deletion167', {'p_request_id':str(uuid4()),'p_actor_user_id':self.admin}).execute()
            with self.assertRaises(APIError):
                client.table('account_erasure_inventory167').select('*').execute()

    def test_report_worker_refuses_frozen_account_before_execution(self):
        from services import bi_reporting_service as reports
        self.enroll()
        with self.assertRaises(HTTPException) as caught:
            reports.execute_run({'tenant_id':self.tenant,'creator_user_id':self.user},client=self.client)
        self.assertEqual(caught.exception.status_code,409)

    def test_real_dashboard_report_exports_survive_hold_and_recovery(self):
        from services import bi_reporting_service as reports, bi_dashboard_service as dashboards
        from unittest.mock import patch
        content, digest, key, _storage, dataset, version = self.dataset()
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'DATA_UPLOAD_DIR':directory, 'PRIVATE_CHARTS_DIR':directory}):
            path=Path(directory)/key;path.parent.mkdir(parents=True);path.write_bytes(content)
            args=dict(tenant_id=self.tenant,project_id=self.project,user_id=self.user,client=self.client)
            dashboard=dashboards.create_dashboard(**args,name='Recovery checkpoint',description='Fixture')
            dashboards.add_widget(**args,dashboard_id=dashboard['id'],expected_revision=dashboard['revision'],
                widget_type='kpi',title='Rows',dataset_id=str(dataset),dataset_version_id=str(version),
                version_policy='pinned',analysis_spec={'operation':'count'},layout_config={},display_options={})
            run=reports.enqueue_report(**args,dashboard_id=dashboard['id'],trigger_type='manual',idempotency_key=str(uuid4()))
            claimed=next(row for row in reports.claim_runs(worker_id='recovery167',limit=20,client=self.client) if row['id']==run['id'])
            result=reports.process_claimed_run(claimed,client=self.client)
            self.assertEqual(result['status'],'completed',result)
            report=self.client.table('bi_report_runs').select('*').eq('id',run['id']).execute().data[0]
            self.assertEqual(report['version_vector'][0]['dataset_version_id'],str(version))
            self.assertEqual(report['version_vector'][0]['content_hash'],digest)
            exports=[]
            for kind in ('pdf','xlsx'):
                export,*_rest=reports.report_export_artifact(**args,report_id=run['id'],export_format=kind,language='en')
                self.assertTrue(export.is_file());exports.append((export,export.read_bytes()))
            request=self.enroll()
            self.assertTrue(path.exists())
            self.recover(request)
            self.assertEqual(path.read_bytes(),content)
            for export,original in exports:self.assertEqual(export.read_bytes(),original)

    def test_pre_freeze_report_claim_stays_fenced_after_recovery_and_other_owner_claims(self):
        run_id=str(uuid4())
        self.db.execute("insert into public.bi_report_runs(id,tenant_id,project_id,creator_user_id,dashboard_revision,trigger_type,deduplication_key,definition_snapshot,version_vector) values(%s,%s,%s,%s,1,'manual',%s,'{}','[]')",(run_id,self.tenant,self.project,self.user,run_id))
        now=self.db.execute('select now()::text').fetchone()[0]
        claim=next(row for row in self.rpc('claim_bi_report_runs164',{'p_worker_id':'old','p_limit':20,'p_lease_seconds':300,'p_now':now}) if row['id']==run_id)
        other_id=str(uuid4())
        self.db.execute("insert into public.bi_report_runs(id,tenant_id,project_id,creator_user_id,dashboard_revision,trigger_type,deduplication_key,definition_snapshot,version_vector) values(%s,%s,%s,%s,1,'manual',%s,'{}','[]')",(other_id,self.tenant,self.project,self.owner,other_id))
        request=self.enroll()
        claimed=self.rpc('claim_bi_report_runs164',{'p_worker_id':'independent','p_limit':20,'p_lease_seconds':300,'p_now':self.db.execute('select now()::text').fetchone()[0]})
        self.assertIn(other_id,[row['id'] for row in claimed])
        self.assertNotIn(run_id,[row['id'] for row in claimed])
        self.recover(request)
        acknowledged=self.rpc('complete_bi_report_run164',{'p_run_id':run_id,'p_lease_token':claim['lease_token'],
            'p_lease_fence':claim['lease_fence'],'p_status':'needs_attention','p_result_snapshot':{},'p_warnings':[],
            'p_artifact_storage_key':None,'p_artifact_filename':None,'p_artifact_content_type':None,
            'p_artifact_size_bytes':None,'p_artifact_sha256':None,'p_now':self.db.execute('select now()::text').fetchone()[0]})
        self.assertFalse(acknowledged)
