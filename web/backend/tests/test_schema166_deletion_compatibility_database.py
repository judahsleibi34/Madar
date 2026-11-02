"""Negative acceptance: schema166 must stay closed until lifecycle gaps are fixed.

Only the marked, loopback disposable harness may write fixtures. Direct fenced
RPC probes diagnose incompatible operations; they do not enable the worker or
replace the database protocol marker. No real Auth/Storage provider is used.
"""
import hashlib
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from postgrest import SyncPostgrestClient
from postgrest.exceptions import APIError

from tests.disposable_database_support import connect_disposable_database


DSN = os.getenv("DELETION_FENCING_SYNTHETIC_DATABASE_DSN")
REST = os.getenv("DELETION166_REST_URL")


@unittest.skipUnless(DSN and REST, "Requires the marked schema166 HTTP rehearsal")
class Schema166DeletionCompatibilityTests(unittest.TestCase):
    def setUp(self):
        # Verify ownership BEFORE creating an HTTP client or writing anything.
        self.db = connect_disposable_database(
            DSN, markers={"madar-notification-synthetic-rehearsal"})
        self.addCleanup(self.db.close)
        self.assertEqual(self.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0], 166)
        from urllib.parse import urlsplit
        self.assertEqual(urlsplit(REST).hostname, "127.0.0.1")
        self.client = SyncPostgrestClient(REST, headers={
            "Authorization": "Bearer " + os.environ["DELETION166_SERVICE_JWT"]}, timeout=10)
        self.addCleanup(self.client.aclose)
        for attempt in range(40):
            try:
                self.assertEqual(self.rpc("data_deletion_ownership_protocol", {}), 0)
                break
            except Exception:
                if attempt == 39:
                    raise
                time.sleep(.25)
        self.tenant = self.db.execute("insert into public.tenants(brand_name,owner_name) values('Deletion166 fixture','Fixture') returning tenant_id").fetchone()[0]
        self.user = self.add_user("member")
        self.owner = self.add_user("owner")
        self.project = str(uuid4())
        # Shared project: deleting a contributor must not destroy its owner.
        self.db.execute("insert into public.builder_projects(id,tenant_id,owner_user_id,name,slug,status,draft_schema) values(%s,%s,%s,'Deletion166',%s,'draft','{\"workspaceKind\":\"data\"}')",
                        (self.project, self.tenant, self.owner, "deletion166-" + self.project))

    def add_user(self, role, tenant=None):
        tenant = self.tenant if tenant is None else tenant
        auth = uuid4()
        email = str(auth) + "@example.invalid"
        self.db.execute("insert into auth.users(id,email,email_confirmed_at) values(%s,%s,now())", (auth, email))
        user = self.db.execute("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified) values(%s,'Deletion166','Fixture',%s,%s,'active',true) returning id", (auth, email, tenant)).fetchone()[0]
        self.db.execute("insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,%s,'active')", (tenant, user, auth, role))
        return user

    def rpc(self, name, body):
        return self.client.rpc(name, body).execute().data

    def request(self, kind="user"):
        row = self.rpc("create_data_deletion_request", {
            "p_request_type": kind, "p_target_user_id": self.user if kind == "user" else None,
            "p_target_tenant_id": self.tenant if kind == "tenant" else None,
            "p_requested_by_user_id": self.user if kind == "user" else self.owner,
            "p_retention_until": None})
        self.addCleanup(self.db.execute, "delete from public.data_deletion_requests where id=%s", (row["id"],))
        return row

    def diagnostic_step(self, request, step_key):
        # Test-only minimal plan; never attempts finalization or claims success.
        # Preserve the production authorization/freeze and all fencing RPCs.
        self.db.execute("delete from public.data_deletion_steps where request_id=%s and step_key<>%s", (request["id"], step_key))
        claims = self.rpc("claim_data_deletion_requests_v2", {
            "p_worker_id": "disposable166", "p_limit": 25, "p_lease_seconds": 300})
        claim = next(row for row in claims if row["id"] == request["id"])
        args = {"p_request_id": claim["id"], "p_owner": claim["lease_owner"],
                "p_generation": claim["claim_generation"], "p_attempt": claim["attempt_count"]}
        step = self.rpc("transition_data_deletion_v2", {
            **args, "p_action": "begin", "p_step_id": None, "p_step_attempt": None, "p_data": {}})
        return claim, step, {**args, "p_step_id": step["id"], "p_step_attempt": step["attempts"]}

    def dataset(self):
        content = b"group,amount\na,1\nb,2\n"
        digest = hashlib.sha256(content).hexdigest()
        key = f"tenant_{self.tenant}/user_{self.user}/source.csv"
        storage = self.db.execute("insert into public.storage_objects(tenant_id,user_id,category,storage_key,size_bytes,sha256) values(%s,%s,'dataset',%s,%s,%s) returning id", (self.tenant, self.user, key, len(content), digest)).fetchone()[0]
        dataset = self.db.execute("insert into public.data_datasets(tenant_id,project_id,creator_user_id,display_name) values(%s,%s,%s,'Fixture') returning id", (self.tenant, self.project, self.user)).fetchone()[0]
        version = self.db.execute("insert into public.data_dataset_versions(tenant_id,dataset_id,version_number,storage_object_id,created_by_user_id,original_filename,content_type,file_extension,size_bytes,content_hash) values(%s,%s,1,%s,%s,'source.csv','text/csv','.csv',%s,%s) returning id", (self.tenant, dataset, storage, self.user, len(content), digest)).fetchone()[0]
        return content, digest, key, storage, dataset, version

    def test_real_worker_refuses_before_claim_or_request_mutation(self):
        import database
        from services import provider_recovery
        from workers import data_deletion_worker as worker
        self.dataset()
        row = self.request()
        before = self.db.execute("select to_jsonb(r) from public.data_deletion_requests r where id=%s", (row["id"],)).fetchone()[0]
        with patch.object(database, "service_supabase", self.client), patch.object(
                provider_recovery, "worker_consumption_allowed", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "data_deletion_ownership_protocol_required"):
                worker.run_batch(worker_id="blocked166", batch_size=1)
        after = self.db.execute("select to_jsonb(r) from public.data_deletion_requests r where id=%s", (row["id"],)).fetchone()[0]
        self.assertEqual(before, after)
        self.assertFalse(worker.STATE["consuming"])

    def test_immutable_confirmation_fails_after_source_and_parquet_unlink(self):
        from services import data_deletion_service as deletion, parquet_cache_service as cache
        content, digest, key, storage, dataset, version = self.dataset()
        request = self.request()
        claim, step, args = self.diagnostic_step(request, "delete_host_files")
        resource = self.client.table("data_deletion_resources").select("*").eq("request_id", request["id"]).execute().data[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / key
            source.parent.mkdir(parents=True)
            source.write_bytes(content)
            with patch.dict(os.environ, {"DATA_UPLOAD_DIR": directory, "PARQUET_CACHE_ENABLED": "true"}), patch.object(cache, "MIN_SOURCE_BYTES", 1):
                artifact = cache.get_or_create(source_path=str(source), tenant_id=self.tenant,
                    user_id=self.user, project_id=self.project, dataset_id=str(dataset),
                    version_id=str(version), source_hash=digest, source_size=len(content), declared_rows=2)
                self.assertIsNotNone(artifact)
                with patch.dict(deletion.HOST_RESOURCE_ROOTS, {"host_dataset": lambda: root}):
                    with self.assertRaisesRegex(Exception, "dataset_version_storage_referenced"):
                        deletion._step_delete_host_files({**claim, "_step": step}, client=self.client)
                self.assertFalse(source.exists())
                self.assertFalse(artifact.path.exists())
                self.assertFalse(artifact.path.with_suffix(".json").exists())
        self.assertEqual(self.db.execute("select status from public.storage_objects where id=%s", (storage,)).fetchone()[0], "active")
        self.assertEqual(self.db.execute("select state from public.data_deletion_effects where request_id=%s", (request["id"],)).fetchone()[0], "intent")
        # Retry must fail closed instead of repeating an uncertain external effect.
        with self.assertRaisesRegex(APIError, "deletion_external_outcome_uncertain"):
            self.rpc("data_deletion_effect_v2", {**args, "p_kind": "resource", "p_target": str(resource["id"]), "p_action": "intent", "p_outcome": None})

    def test_bi_creator_reference_blocks_fenced_user_deletion(self):
        dashboard = self.rpc("create_bi_dashboard163", {"p_tenant_id": self.tenant,
            "p_project_id": self.project, "p_creator_user_id": self.user,
            "p_name": "Deletion166", "p_description": "Fixture"})
        request = self.request()
        _claim, _step, args = self.diagnostic_step(request, "delete_application_data")
        with self.assertRaisesRegex(APIError, "bi_dashboards_creator_fk163"):
            self.rpc("run_data_deletion_local_step_v2", args)
        self.assertEqual(self.db.execute("select count(*) from public.bi_dashboards where id=%s", (dashboard["id"],)).fetchone()[0], 1)
        self.assertEqual(self.db.execute("select count(*) from public.users where id=%s", (self.user,)).fetchone()[0], 1)

    def test_report_files_are_missing_from_manifest_and_cleanup_is_opt_in(self):
        from services import bi_reporting_service as reporting
        run_id = str(uuid4())
        with tempfile.TemporaryDirectory() as directory, patch.object(reporting, "get_private_charts_dir", return_value=Path(directory)):
            artifact = reporting._write_csv_artifact(run={"id": run_id, "tenant_id": self.tenant}, results=[])
            path = Path(directory) / artifact["storage_key"]
            self.db.execute("insert into public.bi_report_runs(id,tenant_id,project_id,creator_user_id,dashboard_revision,trigger_type,deduplication_key,status,definition_snapshot,version_vector,result_snapshot,artifact_storage_key,artifact_filename,artifact_content_type,artifact_size_bytes,artifact_sha256,completed_at) values(%s,%s,%s,%s,1,'manual',%s,'completed','{}','[]','{}',%s,%s,%s,%s,%s,now())", (run_id, self.tenant, self.project, self.user, run_id,
                artifact["storage_key"], artifact["filename"], artifact["content_type"], artifact["size_bytes"], artifact["sha256"]))
            result = self.rpc("enqueue_bi_report_lifecycle166", {"p_report_id": run_id})
            self.assertFalse(result["cleanup"])
            for kind in ("user", "tenant"):
                # Restore freeze via the actual cancellation RPC between requests.
                request = self.request(kind)
                resources = self.client.table("data_deletion_resources").select("*").eq("request_id", request["id"]).execute().data
                self.assertNotIn(artifact["storage_key"], [row["resource_key"] for row in resources])
                self.assertTrue(path.exists())
                self.rpc("cancel_data_deletion_request_v2", {"p_request_id": request["id"]})

    def test_foreign_requester_and_unprivileged_http_role_are_denied(self):
        other_tenant = self.db.execute("insert into public.tenants(brand_name,owner_name) values('Foreign deletion fixture','Fixture') returning tenant_id").fetchone()[0]
        outsider = self.add_user("owner", other_tenant)
        with self.assertRaises(APIError):
            self.rpc("create_data_deletion_request", {"p_request_type": "tenant", "p_target_user_id": None,
                "p_target_tenant_id": self.tenant, "p_requested_by_user_id": outsider, "p_retention_until": None})
        with SyncPostgrestClient(REST, headers={"Authorization": "Bearer " + os.environ["DELETION166_ANON_JWT"]}) as client:
            with self.assertRaises(APIError):
                client.rpc("claim_data_deletion_requests_v2", {"p_worker_id": "foreign", "p_limit": 1, "p_lease_seconds": 300}).execute()
            with self.assertRaises(APIError):
                client.table("bi_report_runs").select("*").execute()
        self.assertEqual(self.db.execute("select lifecycle_state from public.tenants where tenant_id=%s", (self.tenant,)).fetchone()[0], "active")

    def test_shared_provider_identity_is_not_carried_into_manifest(self):
        key = f"tenant_{self.tenant}/user_{self.user}/shared.csv"
        provider_key = f"tenant_{self.tenant}/dataset/{uuid4()}/{'a' * 64}.csv"
        self.db.execute("insert into public.storage_objects(tenant_id,user_id,category,storage_key,size_bytes,sha256,storage_backend,storage_bucket,provider_object_key,verified_size_bytes,verified_sha256,integrity_verified_at) values(%s,%s,'dataset',%s,20,%s,'supabase_private','madar-data-immutable',%s,20,%s,now())", (self.tenant, self.user, key, 'a' * 64, provider_key, 'a' * 64))
        request = self.request()
        resources = self.client.table("data_deletion_resources").select("*").eq("request_id", request["id"]).execute().data
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["resource_kind"], "host_dataset")
        self.assertEqual(resources[0]["resource_key"], key)
        self.assertNotIn(provider_key, str(resources))

    def test_existing_opt_in_retention_worker_removes_report_and_exports(self):
        from services import bi_reporting_service as reporting, bi_report_delivery_service as delivery
        run_id = str(uuid4())
        with tempfile.TemporaryDirectory() as directory, patch.object(reporting, "get_private_charts_dir", return_value=Path(directory)), patch.object(delivery, "get_private_charts_dir", return_value=Path(directory)):
            artifact = reporting._write_csv_artifact(run={"id": run_id, "tenant_id": self.tenant}, results=[])
            path = Path(directory) / artifact["storage_key"]
            exports = path.parent / "exports"
            exports.mkdir()
            # Cleanup treats already generated exports as opaque private files.
            (exports / "report.pdf").write_bytes(b"disposable opaque export")
            (exports / "report.xlsx").write_bytes(b"disposable opaque export")
            self.db.execute("insert into public.bi_report_runs(id,tenant_id,project_id,creator_user_id,dashboard_revision,trigger_type,deduplication_key,status,definition_snapshot,version_vector,result_snapshot,artifact_storage_key,artifact_filename,artifact_content_type,artifact_size_bytes,artifact_sha256,completed_at) values(%s,%s,%s,%s,1,'manual',%s,'completed','{}','[]','{}',%s,%s,%s,%s,%s,now()-interval '31 days')", (run_id, self.tenant, self.project, self.user, run_id,
                artifact["storage_key"], artifact["filename"], artifact["content_type"], artifact["size_bytes"], artifact["sha256"]))
            self.rpc("configure_bi_report_lifecycle166", {"p_tenant_id": self.tenant,
                "p_project_id": self.project, "p_owner_user_id": self.user, "p_expected_revision": None,
                "p_retention_days": 30, "p_cleanup_enabled": True})
            self.assertTrue(self.rpc("enqueue_bi_report_lifecycle166", {"p_report_id": run_id})["cleanup"])
            jobs = delivery.claim_cleanup(worker_id="disposable-retention166", client=self.client)
            job = next(row for row in jobs if row["report_id"] == run_id)
            result = delivery.process_cleanup(job, client=self.client)
            self.assertEqual(result["status"], "completed")
            self.assertFalse(path.parent.exists())
            self.assertTrue(self.db.execute("select artifact_deleted_at is not null from public.bi_report_runs where id=%s", (run_id,)).fetchone()[0])
            self.assertEqual(self.db.execute("select count(*) from public.users where id=%s", (self.user,)).fetchone()[0], 1)

    def test_deletion_stop_work_does_not_stop_new_report_queue(self):
        run_id = str(uuid4())
        self.db.execute("insert into public.bi_report_runs(id,tenant_id,project_id,creator_user_id,dashboard_revision,trigger_type,deduplication_key,definition_snapshot,version_vector) values(%s,%s,%s,%s,1,'manual',%s,'{}','[]')", (run_id, self.tenant, self.project, self.user, run_id))
        request = self.request("tenant")
        _claim, _step, args = self.diagnostic_step(request, "stop_queued_work")
        self.rpc("run_data_deletion_local_step_v2", args)
        self.assertEqual(self.db.execute("select status from public.bi_report_runs where id=%s", (run_id,)).fetchone()[0], "queued")
        rows = self.rpc("claim_bi_report_runs164", {"p_worker_id": "disposable-report166",
            "p_limit": 20, "p_lease_seconds": 300, "p_now": self.db.execute("select now()::text").fetchone()[0]})
        self.assertIn(run_id, [row["id"] for row in rows])
        self.assertEqual(self.db.execute("select lifecycle_state from public.tenants where tenant_id=%s", (self.tenant,)).fetchone()[0], "deletion_pending")

    def test_source_archive_and_supported_reactivation_preserve_immutable_content(self):
        from fastapi import HTTPException
        from services import project_data_source_service as sources, parquet_cache_service as cache
        content, digest, key, storage, dataset, version = self.dataset()
        source = sources.create_project_data_source(tenant_id=self.tenant, project_id=self.project,
            user_id=self.user, source_type="spreadsheet_upload", display_name="Recoverable source", client=self.client)
        self.db.execute("update public.data_datasets set source_id=%s where id=%s", (source["id"], dataset))
        self.db.execute("update public.data_sources set latest_dataset_id=%s,latest_version_id=%s where id=%s", (dataset, version, source["id"]))
        args = dict(tenant_id=self.tenant, project_id=self.project, user_id=self.user,
                    source_id=source["id"], client=self.client)
        before = self.db.execute("select to_jsonb(v) from public.data_dataset_versions v where id=%s", (version,)).fetchone()[0]
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"DATA_UPLOAD_DIR": directory, "PARQUET_CACHE_ENABLED": "true"}), patch.object(cache, "MIN_SOURCE_BYTES", 1):
            path = Path(directory) / key
            path.parent.mkdir(parents=True)
            path.write_bytes(content)
            artifact = cache.get_or_create(source_path=str(path), tenant_id=self.tenant,
                user_id=self.user, project_id=self.project, dataset_id=str(dataset),
                version_id=str(version), source_hash=digest, source_size=len(content), declared_rows=2)
            self.assertIsNotNone(artifact)
            for status in ("archived", "archived", "active"):
                changed = sources.update_project_data_source_status(**args, status=status)
                self.assertEqual(changed["status"], status)
                self.assertEqual(path.read_bytes(), content)
                self.assertTrue(artifact.path.exists())
                listed = sources.list_project_data_sources(tenant_id=self.tenant, project_id=self.project,
                    user_id=self.user, limit=20, offset=0, client=self.client)["items"]
                self.assertEqual(source["id"] in [row["id"] for row in listed], status == "active")
            with self.assertRaises(HTTPException) as denied:
                sources.update_project_data_source_status(**{**args, "user_id": self.owner}, status="archived")
            self.assertEqual(denied.exception.status_code, 404)
        self.assertEqual(self.db.execute("select to_jsonb(v) from public.data_dataset_versions v where id=%s", (version,)).fetchone()[0], before)
        self.assertEqual(self.db.execute("select status from public.storage_objects where id=%s", (storage,)).fetchone()[0], "active")

    def test_ordinary_report_archive_retains_content_and_is_missing_from_erasure_inventory(self):
        from fastapi import HTTPException
        from services import bi_reporting_service as reporting
        run_id = str(uuid4())
        with tempfile.TemporaryDirectory() as directory, patch.object(reporting, "get_private_charts_dir", return_value=Path(directory)):
            artifact = reporting._write_csv_artifact(run={"id": run_id, "tenant_id": self.tenant}, results=[])
            path = Path(directory) / artifact["storage_key"]
            original = path.read_bytes()
            exports = path.parent / "exports"
            exports.mkdir()
            (exports / "report.pdf").write_bytes(b"recoverable opaque PDF fixture")
            self.db.execute("insert into public.bi_report_runs(id,tenant_id,project_id,creator_user_id,dashboard_revision,trigger_type,deduplication_key,status,definition_snapshot,version_vector,result_snapshot,artifact_storage_key,artifact_filename,artifact_content_type,artifact_size_bytes,artifact_sha256,completed_at) values(%s,%s,%s,%s,1,'manual',%s,'completed','{}','[]','{}',%s,%s,%s,%s,%s,now())", (run_id, self.tenant, self.project, self.user, run_id,
                artifact["storage_key"], artifact["filename"], artifact["content_type"], artifact["size_bytes"], artifact["sha256"]))
            args = dict(tenant_id=self.tenant, project_id=self.project, user_id=self.user,
                        report_id=run_id, client=self.client)
            with self.assertRaises(HTTPException):
                reporting.archive_report(**{**args, "user_id": self.owner})
            reporting.archive_report(**args)
            self.assertEqual(path.read_bytes(), original)
            self.assertTrue((exports / "report.pdf").exists())
            self.assertTrue(self.db.execute("select archived_at is not null and artifact_deleted_at is null from public.bi_report_runs where id=%s", (run_id,)).fetchone()[0])
            self.assertNotIn(run_id, [row["id"] for row in reporting.list_reports(
                tenant_id=self.tenant, project_id=self.project, user_id=self.user, client=self.client)["items"]])
            # Current API offers no restoration: retrying Archive must not purge.
            with self.assertRaises(HTTPException):
                reporting.archive_report(**args)
            for kind in ("user", "tenant"):
                request = self.request(kind)
                resources = self.client.table("data_deletion_resources").select("*").eq("request_id", request["id"]).execute().data
                self.assertNotIn(artifact["storage_key"], [row["resource_key"] for row in resources])
                self.rpc("cancel_data_deletion_request_v2", {"p_request_id": request["id"]})
                self.assertEqual(path.read_bytes(), original)
                self.assertTrue((exports / "report.pdf").exists())
