import asyncio
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException, UploadFile

from data_analysis import services as data_services
from data_analysis.routes import analysis_routes
from data_analysis.routes import data_routes
from services import project_dataset_service


PROJECT_A = "11111111-1111-4111-8111-111111111111"
PROJECT_B = "22222222-2222-4222-8222-222222222222"
DATASET_A = "33333333-3333-4333-8333-333333333333"
VERSION_A = "44444444-4444-4444-8444-444444444444"
VERSION_B = "44444444-4444-4444-8444-444444444445"
STORAGE_A = "55555555-5555-4555-8555-555555555555"
RESERVATION_A = "66666666-6666-4666-8666-666666666666"


class FakeQuery:
    def __init__(self, rows):
        self.rows = [dict(row) for row in rows]
        self._limit = None
        self._range = None

    def select(self, *_args):
        return self

    def eq(self, field, value):
        self.rows = [row for row in self.rows if row.get(field) == value]
        return self

    def neq(self, field, value):
        self.rows = [row for row in self.rows if row.get(field) != value]
        return self

    def in_(self, field, values):
        allowed = set(values)
        self.rows = [row for row in self.rows if row.get(field) in allowed]
        return self

    def order(self, field, desc=False):
        self.rows.sort(key=lambda row: row.get(field) or 0, reverse=desc)
        return self

    def limit(self, value):
        self._limit = value
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def execute(self):
        rows = self.rows
        if self._range is not None:
            rows = rows[self._range[0] : self._range[1] + 1]
        if self._limit is not None:
            rows = rows[: self._limit]
        return SimpleNamespace(data=rows)


class FakeRpc:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return SimpleNamespace(data=self.result)


class FakeClient:
    def __init__(self, tables=None, rpc_result=None):
        self.tables = tables or {}
        self.rpc_result = rpc_result or []
        self.rpc_calls = []

    def table(self, name):
        return FakeQuery(self.tables.get(name, []))

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        return FakeRpc(self.rpc_result)


def project(project_id=PROJECT_A, tenant_id=1, kind="data"):
    return {
        "id": project_id,
        "tenant_id": tenant_id,
        "name": "Project",
        "status": "draft",
        "draft_schema": {"workspaceKind": kind},
    }


class ProjectDatasetServiceTests(unittest.TestCase):
    def test_schema_availability_fails_closed_before_147(self):
        old = FakeClient({"application_schema_state": [{"contract_key": "core", "schema_version": 146}]})
        current = FakeClient({"application_schema_state": [{"contract_key": "core", "schema_version": 147}]})
        self.assertFalse(project_dataset_service.project_datasets_available(client=old))
        self.assertTrue(project_dataset_service.project_datasets_available(client=current))
        with self.assertRaises(HTTPException) as unavailable:
            project_dataset_service.require_project_datasets_schema(client=old)
        self.assertEqual(unavailable.exception.status_code, 503)

    def test_project_identity_is_tenant_scoped_and_requires_data_kind(self):
        client = FakeClient({"builder_projects": [project()]})
        self.assertEqual(
            project_dataset_service.require_data_project(
                PROJECT_A, tenant_id=1, client=client
            )["id"],
            PROJECT_A,
        )
        with self.assertRaises(HTTPException) as cross_tenant:
            project_dataset_service.require_data_project(
                PROJECT_A, tenant_id=2, client=client
            )
        self.assertEqual(cross_tenant.exception.status_code, 404)

        website = FakeClient({"builder_projects": [project(kind="website")]})
        with self.assertRaises(HTTPException) as wrong_kind:
            project_dataset_service.require_data_project(
                PROJECT_A, tenant_id=1, client=website
            )
        self.assertEqual(wrong_kind.exception.status_code, 404)

    def test_initial_dataset_and_version_are_created_atomically(self):
        client = FakeClient(
            rpc_result=[
                {
                    "dataset_id": DATASET_A,
                    "version_id": VERSION_A,
                    "version_number": 1,
                }
            ]
        )
        result = project_dataset_service.create_initial_dataset_version(
            tenant_id=1,
            project_id=PROJECT_A,
            creator_user_id=7,
            display_name="sales.csv",
            artifact={
                "storage_object_id": STORAGE_A,
                "original_filename": "sales.csv",
                "content_type": "text/csv",
                "file_extension": ".csv",
                "file_size": 18,
                "sha256": "a" * 64,
                "response": {"rows": 1, "columns": ["name", "value"], "column_count": 2},
            },
            client=client,
        )
        self.assertEqual(result["persistent_dataset_id"], DATASET_A)
        self.assertEqual(result["dataset_version_id"], VERSION_A)
        self.assertEqual(client.rpc_calls[0][0], "create_project_dataset_with_version147")
        self.assertEqual(client.rpc_calls[0][1]["p_tenant_id"], 1)
        self.assertEqual(client.rpc_calls[0][1]["p_project_id"], PROJECT_A)

    def test_listing_isolated_by_tenant_project_and_uploader(self):
        datasets = [
            {"id": DATASET_A, "tenant_id": 1, "project_id": PROJECT_A, "creator_user_id": 7, "display_name": "A", "status": "active", "updated_at": "2026-01-02"},
            {"id": "66666666-6666-4666-8666-666666666666", "tenant_id": 1, "project_id": PROJECT_B, "creator_user_id": 7, "display_name": "Other project", "status": "active", "updated_at": "2026-01-03"},
            {"id": "77777777-7777-4777-8777-777777777777", "tenant_id": 2, "project_id": PROJECT_A, "creator_user_id": 7, "display_name": "Other tenant", "status": "active", "updated_at": "2026-01-04"},
            {"id": "88888888-8888-4888-8888-888888888888", "tenant_id": 1, "project_id": PROJECT_A, "creator_user_id": 8, "display_name": "Other uploader", "status": "active", "updated_at": "2026-01-05"},
        ]
        versions = [{"id": VERSION_A, "tenant_id": 1, "dataset_id": DATASET_A, "version_number": 1, "version_kind": "original", "size_bytes": 18}]
        client = FakeClient({"builder_projects": [project()], "data_datasets": datasets, "data_dataset_versions": versions})
        result = project_dataset_service.list_project_datasets(
            tenant_id=1,
            project_id=PROJECT_A,
            user_id=7,
            limit=50,
            offset=0,
            client=client,
        )
        self.assertEqual([item["id"] for item in result["items"]], [DATASET_A])
        self.assertEqual(result["items"][0]["latest_version"]["id"], VERSION_A)

    def test_version_history_is_newest_first_and_exactly_scoped(self):
        client = FakeClient({
            "application_schema_state": [{"contract_key": "core", "schema_version": 159}],
            "builder_projects": [project()],
            "data_datasets": [{"id": DATASET_A, "tenant_id": 1, "project_id": PROJECT_A,
                               "creator_user_id": 7, "status": "active"}],
            "data_dataset_versions": [
                {"id": VERSION_A, "tenant_id": 1, "dataset_id": DATASET_A, "version_number": 1,
                 "version_kind": "original", "provenance": {}},
                {"id": VERSION_B, "tenant_id": 1, "dataset_id": DATASET_A, "version_number": 2,
                 "version_kind": "derived", "provenance": {"target_revision": 8}},
                {"id": "99999999-9999-4999-8999-999999999999", "tenant_id": 2,
                 "dataset_id": DATASET_A, "version_number": 99, "provenance": {}},
            ],
        })
        result = project_dataset_service.list_project_dataset_versions(
            tenant_id=1, project_id=PROJECT_A, user_id=7, dataset_id=DATASET_A,
            limit=10, offset=0, client=client,
        )
        self.assertEqual([item["id"] for item in result["items"]], [VERSION_B, VERSION_A])
        self.assertEqual(result["items"][0]["revision"], 8)

    def test_freshness_projection_is_scoped_and_contains_no_credentials(self):
        source_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        resource_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        client = FakeClient({
            "application_schema_state": [{"contract_key": "core", "schema_version": 159}],
            "builder_projects": [project()],
            "data_datasets": [{"id": DATASET_A, "tenant_id": 1, "project_id": PROJECT_A,
                               "creator_user_id": 7, "status": "active", "source_id": source_id,
                               "source_resource_id": resource_id, "updated_at": "now"}],
            "data_sources": [{"id": source_id, "tenant_id": 1, "project_id": PROJECT_A,
                              "creator_user_id": 7, "display_name": "Orders", "status": "active",
                              "sync_state": "ready", "last_successful_sync_at": "then",
                              "latest_version_id": VERSION_B, "secret": "must-not-leak"}],
            "data_source_resources": [{"id": resource_id, "tenant_id": 1, "project_id": PROJECT_A,
                                       "source_id": source_id, "committed_revision": 8,
                                       "latest_checkpoint_version_id": VERSION_B}],
            "data_dataset_checkpoints": [{"tenant_id": 1, "project_id": PROJECT_A,
                                           "dataset_id": DATASET_A, "source_resource_id": resource_id,
                                           "target_revision": 8, "status": "completed"}],
            "data_source_sync_schedules": [], "data_source_webhook_endpoints": [],
        })
        result = project_dataset_service.get_project_dataset_freshness(
            tenant_id=1, project_id=PROJECT_A, user_id=7, dataset_id=DATASET_A, client=client,
        )
        self.assertTrue(result["available"])
        self.assertEqual(result["resource"]["committed_revision"], 8)
        self.assertNotIn("secret", repr(result).lower())

    def test_reopen_rejects_cross_project_cross_tenant_and_other_uploader(self):
        base_tables = {
            "builder_projects": [project()],
            "data_datasets": [
                {"id": DATASET_A, "tenant_id": 1, "project_id": PROJECT_A, "creator_user_id": 7, "display_name": "A", "status": "active"}
            ],
            "data_dataset_versions": [
                {"id": VERSION_A, "tenant_id": 1, "dataset_id": DATASET_A, "version_number": 1, "storage_object_id": STORAGE_A}
            ],
            "storage_objects": [
                {"id": STORAGE_A, "tenant_id": 1, "user_id": 7, "category": "dataset", "storage_key": "tenant_1/user_7/file.csv", "status": "active"}
            ],
        }
        client = FakeClient(base_tables)
        reopened = project_dataset_service.reopen_project_dataset(
            tenant_id=1,
            project_id=PROJECT_A,
            user_id=7,
            dataset_id=DATASET_A,
            client=client,
        )
        self.assertEqual(reopened["storage_identifier"], "file.csv")

        for tenant_id, project_id, user_id in (
            (2, PROJECT_A, 7),
            (1, PROJECT_B, 7),
            (1, PROJECT_A, 8),
        ):
            with self.assertRaises(HTTPException) as denied:
                project_dataset_service.reopen_project_dataset(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    user_id=user_id,
                    dataset_id=DATASET_A,
                    client=client,
                )
            self.assertEqual(denied.exception.status_code, 404)

    def test_exact_version_resolution_is_tenant_project_dataset_and_user_scoped(self):
        base_tables = {
            "builder_projects": [project()],
            "data_datasets": [
                {
                    "id": DATASET_A,
                    "tenant_id": 1,
                    "project_id": PROJECT_A,
                    "creator_user_id": 7,
                    "display_name": "Sales",
                    "status": "active",
                }
            ],
            "data_dataset_versions": [
                {
                    "id": VERSION_A,
                    "tenant_id": 1,
                    "dataset_id": DATASET_A,
                    "version_number": 1,
                    "version_kind": "original",
                    "storage_object_id": STORAGE_A,
                    "content_hash": "a" * 64,
                },
                {
                    "id": VERSION_B,
                    "tenant_id": 1,
                    "dataset_id": "66666666-6666-4666-8666-666666666666",
                    "version_number": 1,
                    "version_kind": "original",
                    "storage_object_id": STORAGE_A,
                },
            ],
            "storage_objects": [
                {
                    "id": STORAGE_A,
                    "tenant_id": 1,
                    "user_id": 7,
                    "category": "dataset",
                    "storage_key": "tenant_1/user_7/opaque.csv",
                    "status": "active",
                }
            ],
        }
        resolved = project_dataset_service.resolve_project_dataset_version(
            tenant_id=1,
            project_id=PROJECT_A,
            user_id=7,
            dataset_id=DATASET_A,
            version_id=VERSION_A,
            client=FakeClient(base_tables),
        )
        self.assertEqual(resolved["storage_identifier"], "opaque.csv")
        self.assertEqual(resolved["version"]["id"], VERSION_A)

        for tenant_id, project_id, user_id, version_id in (
            (2, PROJECT_A, 7, VERSION_A),
            (1, PROJECT_B, 7, VERSION_A),
            (1, PROJECT_A, 8, VERSION_A),
            (1, PROJECT_A, 7, VERSION_B),
        ):
            with self.assertRaises(HTTPException) as denied:
                project_dataset_service.resolve_project_dataset_version(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    user_id=user_id,
                    dataset_id=DATASET_A,
                    version_id=version_id,
                    client=FakeClient(base_tables),
                )
            self.assertEqual(denied.exception.status_code, 404)

    def test_exact_version_resolution_rejects_deleted_or_unauthorized_storage(self):
        for status, storage_user, storage_exists in (
            ("deleted", 7, True),
            ("active", 8, True),
            ("active", 7, False),
        ):
            client = FakeClient({
                "builder_projects": [project()],
                "data_datasets": [
                    {
                        "id": DATASET_A,
                        "tenant_id": 1,
                        "project_id": PROJECT_A,
                        "creator_user_id": 7,
                        "display_name": "Sales",
                        "status": "active",
                    }
                ],
                "data_dataset_versions": [
                    {
                        "id": VERSION_A,
                        "tenant_id": 1,
                        "dataset_id": DATASET_A,
                        "version_number": 1,
                        "version_kind": "original",
                        "storage_object_id": STORAGE_A,
                    }
                ],
                "storage_objects": ([
                    {
                        "id": STORAGE_A,
                        "tenant_id": 1,
                        "user_id": storage_user,
                        "category": "dataset",
                        "storage_key": "tenant_1/user_7/opaque.csv",
                        "status": status,
                    }
                ] if storage_exists else []),
            })
            with self.assertRaises(HTTPException) as denied:
                project_dataset_service.resolve_project_dataset_version(
                    tenant_id=1,
                    project_id=PROJECT_A,
                    user_id=7,
                    dataset_id=DATASET_A,
                    version_id=VERSION_A,
                    client=client,
                )
            self.assertEqual(denied.exception.status_code, 404)


class ProjectDatasetUploadLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.upload_root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _upload(self):
        upload_file = tempfile.SpooledTemporaryFile()
        upload_file.write(b"name,value\nA,1\n")
        upload_file.seek(0)
        self.addCleanup(upload_file.close)
        return UploadFile(
            filename="synthetic.csv",
            file=upload_file,
            headers={"content-type": "text/csv"},
        )

    def test_metadata_failure_releases_quota_before_removing_file(self):
        def fail_metadata(_artifact):
            raise RuntimeError("synthetic metadata failure")

        with (
            patch.object(data_services, "get_data_upload_dir", return_value=self.upload_root),
            patch.object(data_services, "ensure_disk_capacity", return_value=10**12),
            patch.object(data_services, "reserve_storage", return_value="reservation"),
            patch.object(data_services, "finish_storage", return_value=STORAGE_A),
            patch.object(data_services, "release_storage", return_value=True) as release,
        ):
            with self.assertRaises(HTTPException) as failed:
                asyncio.run(
                    data_services.process_upload(
                        self._upload(),
                        tenant_id="1",
                        user_id="7",
                        metadata_persister=fail_metadata,
                    )
                )
        self.assertEqual(failed.exception.status_code, 503)
        release.assert_called_once()
        self.assertEqual(list(self.upload_root.rglob("*.csv")), [])

    def test_legacy_upload_does_not_require_persistent_metadata(self):
        with (
            patch.object(data_services, "get_data_upload_dir", return_value=self.upload_root),
            patch.object(data_services, "ensure_disk_capacity", return_value=10**12),
            patch.object(data_services, "reserve_storage", return_value="reservation"),
            patch.object(data_services, "finish_storage", return_value=None),
        ):
            result = asyncio.run(
                data_services.process_upload(
                    self._upload(), tenant_id="1", user_id="7"
                )
            )
        self.assertEqual(result["original_filename"], "synthetic.csv")
        self.assertTrue((self.upload_root / "tenant_1" / "user_7" / result["file_path"]).is_file())

    def test_unknown_metadata_outcome_preserves_accounted_private_file(self):
        def fail_metadata(_artifact):
            raise RuntimeError("synthetic ambiguous response")

        with (
            patch.object(data_services, "get_data_upload_dir", return_value=self.upload_root),
            patch.object(data_services, "ensure_disk_capacity", return_value=10**12),
            patch.object(data_services, "reserve_storage", return_value="reservation"),
            patch.object(data_services, "finish_storage", return_value=STORAGE_A),
            patch.object(data_services, "release_storage") as release,
        ):
            with self.assertRaises(HTTPException) as failed:
                asyncio.run(data_services.process_upload(
                    self._upload(), tenant_id="1", user_id="7",
                    metadata_persister=fail_metadata,
                    metadata_failure_resolver=lambda _error: None,
                ))
        self.assertEqual(failed.exception.detail["code"], "metadata_outcome_unknown")
        release.assert_not_called()
        self.assertEqual(len(list(self.upload_root.rglob("*.csv"))), 1)

    def test_failed_reservation_attachment_releases_reservation_before_file(self):
        def fail_attachment(_reservation_id):
            raise RuntimeError("synthetic attachment failure")

        with (
            patch.object(data_services, "get_data_upload_dir", return_value=self.upload_root),
            patch.object(data_services, "ensure_disk_capacity", return_value=10**12),
            patch.object(data_services, "reserve_storage", return_value=RESERVATION_A),
            patch.object(data_services, "finish_storage", return_value=None) as finish,
        ):
            with self.assertRaises(HTTPException) as failed:
                asyncio.run(data_services.process_upload(
                    self._upload(), tenant_id="1", user_id="7",
                    storage_reservation_persister=fail_attachment,
                ))
        self.assertEqual(failed.exception.detail["code"], "ingestion_reservation_attachment_failed")
        finish.assert_called_once_with(reservation_id=RESERVATION_A, succeeded=False)
        self.assertEqual(list(self.upload_root.rglob("*.csv")), [])

    def test_unknown_storage_attachment_preserves_accounting_and_private_file(self):
        def fail_attachment(_storage_object_id):
            raise RuntimeError("synthetic response loss")

        with (
            patch.object(data_services, "get_data_upload_dir", return_value=self.upload_root),
            patch.object(data_services, "ensure_disk_capacity", return_value=10**12),
            patch.object(data_services, "reserve_storage", return_value=RESERVATION_A),
            patch.object(data_services, "finish_storage", return_value=STORAGE_A),
            patch.object(data_services, "release_storage") as release,
        ):
            with self.assertRaises(HTTPException) as failed:
                asyncio.run(data_services.process_upload(
                    self._upload(), tenant_id="1", user_id="7",
                    storage_reservation_persister=lambda _reservation_id: None,
                    storage_object_persister=fail_attachment,
                    storage_object_failure_resolver=lambda _storage_object_id: None,
                ))
        self.assertEqual(failed.exception.detail["code"], "metadata_outcome_unknown")
        release.assert_not_called()
        self.assertEqual(len(list(self.upload_root.rglob("*.csv"))), 1)

    def test_confirmed_missing_storage_attachment_compensates_before_file_delete(self):
        with (
            patch.object(data_services, "get_data_upload_dir", return_value=self.upload_root),
            patch.object(data_services, "ensure_disk_capacity", return_value=10**12),
            patch.object(data_services, "reserve_storage", return_value=RESERVATION_A),
            patch.object(data_services, "finish_storage", return_value=STORAGE_A),
            patch.object(data_services, "release_storage", return_value=True) as release,
        ):
            with self.assertRaises(HTTPException):
                asyncio.run(data_services.process_upload(
                    self._upload(), tenant_id="1", user_id="7",
                    storage_reservation_persister=lambda _reservation_id: None,
                    storage_object_persister=lambda _storage_object_id: (_ for _ in ()).throw(RuntimeError("no commit")),
                    storage_object_failure_resolver=lambda _storage_object_id: False,
                ))
        release.assert_called_once()
        self.assertEqual(list(self.upload_root.rglob("*.csv")), [])


class ProjectDatasetRouteTests(unittest.TestCase):
    def test_project_upload_uses_authenticated_scope_and_persists_identity(self):
        async def fake_upload(_file, *, tenant_id, user_id, metadata_persister):
            self.assertEqual((tenant_id, user_id), ("1", "7"))
            persisted = metadata_persister(
                {
                    "storage_object_id": STORAGE_A,
                    "original_filename": "synthetic.csv",
                    "content_type": "text/csv",
                    "file_extension": ".csv",
                    "file_size": 18,
                    "sha256": "a" * 64,
                    "response": {"rows": 1},
                }
            )
            return {"file_path": "opaque.csv", **persisted}

        with (
            patch.object(data_routes, "get_storage_scope", return_value=("1", "7")),
            patch.object(data_routes, "enforce_data_workspace_rate_limit"),
            patch.object(project_dataset_service, "require_project_datasets_schema"),
            patch.object(project_dataset_service, "require_data_project") as require_project,
            patch.object(
                project_dataset_service,
                "create_initial_dataset_version",
                return_value={
                    "persistent_dataset_id": DATASET_A,
                    "dataset_version_id": VERSION_A,
                    "version_number": 1,
                    "project_id": PROJECT_A,
                },
            ) as create_metadata,
            patch.object(data_services, "process_upload", side_effect=fake_upload),
        ):
            result = asyncio.run(
                data_routes.upload_project_dataset(
                    user_id=7,
                    project_id=PROJECT_A,
                    request=SimpleNamespace(),
                    response=SimpleNamespace(),
                    file=UploadFile(filename="synthetic.csv", file=BytesIO(b"x")),
                )
            )
        require_project.assert_called_once_with(PROJECT_A, tenant_id=1)
        self.assertEqual(create_metadata.call_args.kwargs["tenant_id"], 1)
        self.assertEqual(result["persistent_dataset_id"], DATASET_A)

    def test_reopen_reads_only_the_authorized_persistent_storage_identifier(self):
        persistent = {
            "dataset": {"id": DATASET_A, "project_id": PROJECT_A, "display_name": "sales.csv"},
            "version": {"id": VERSION_A, "version_number": 1},
            "storage_identifier": "opaque.csv",
        }
        with (
            patch.object(data_routes, "get_storage_scope", return_value=("1", "7")),
            patch.object(project_dataset_service, "require_project_datasets_schema"),
            patch.object(project_dataset_service, "reopen_project_dataset", return_value=persistent) as reopen,
            patch.object(data_services, "process_read", return_value={"file_path": "opaque.csv", "rows": 1}) as read,
        ):
            result = data_routes.reopen_project_dataset(
                user_id=7,
                project_id=PROJECT_A,
                dataset_id=DATASET_A,
                request=SimpleNamespace(),
                response=SimpleNamespace(),
            )
        reopen.assert_called_once_with(
            tenant_id=1,
            project_id=PROJECT_A,
            user_id=7,
            dataset_id=DATASET_A,
        )
        read.assert_called_once_with("opaque.csv", tenant_id="1", user_id="7")
        self.assertEqual(result["dataset_version_id"], VERSION_A)

    def test_version_aware_assistant_runs_deterministically_with_provenance(self):
        persistent = {
            "dataset": {
                "id": DATASET_A,
                "project_id": PROJECT_A,
                "display_name": "sales.csv",
            },
            "version": {
                "id": VERSION_A,
                "version_number": 1,
                "version_kind": "original",
                "content_hash": "a" * 64,
            },
            "storage_identifier": "opaque.csv",
        }
        with tempfile.TemporaryDirectory() as root:
            upload_root = Path(root)
            user_root = upload_root / "tenant_1" / "user_7"
            user_root.mkdir(parents=True)
            (user_root / "opaque.csv").write_text("department,cost\nA,10\nB,20\n")
            with (
                patch.object(analysis_routes, "get_storage_scope", return_value=("1", "7")),
                patch.object(analysis_routes, "require_entitlement"),
                patch.object(analysis_routes, "enforce_data_workspace_rate_limit"),
                patch.object(project_dataset_service, "require_project_datasets_schema"),
                patch.object(
                    project_dataset_service,
                    "resolve_project_dataset_version",
                    return_value=persistent,
                ) as resolve,
                patch.object(data_services, "get_data_upload_dir", return_value=upload_root),
                patch(
                    "data_analysis.io.data_reading.get_data_upload_dir",
                    return_value=upload_root,
                ),
            ):
                result = analysis_routes.assisted_analysis_for_dataset_version(
                    user_id=7,
                    project_id=PROJECT_A,
                    dataset_id=DATASET_A,
                    version_id=VERSION_A,
                    request=analysis_routes.VersionAssistedAnalysisRequest(
                        question="What is the average cost?"
                    ),
                    fastapi_request=SimpleNamespace(),
                    response=SimpleNamespace(),
                )

        resolve.assert_called_once_with(
            tenant_id=1,
            project_id=PROJECT_A,
            user_id=7,
            dataset_id=DATASET_A,
            version_id=VERSION_A,
        )
        averages = result["result"]["tables"][0]["rows"]
        self.assertEqual(averages[0]["column"], "cost")
        self.assertEqual(averages[0]["mean"], 15.0)
        self.assertEqual(result["provenance"]["dataset_id"], DATASET_A)
        self.assertEqual(result["provenance"]["dataset_version_id"], VERSION_A)
        self.assertNotIn("storage_identifier", result)

    def test_legacy_assistant_route_keeps_filename_contract(self):
        request = analysis_routes.AssistedAnalysisRequest(
            input_path="legacy.csv",
            question="show missing values",
        )
        with (
            patch.object(analysis_routes, "get_storage_scope", return_value=("1", "7")),
            patch.object(analysis_routes, "require_entitlement"),
            patch.object(analysis_routes, "enforce_data_workspace_rate_limit"),
            patch.object(
                data_services,
                "run_assisted_analysis",
                return_value={"result": {"report_id": "offline_question"}},
            ) as run,
        ):
            result = analysis_routes.assisted_analysis(
                user_id=7,
                request=request,
                fastapi_request=SimpleNamespace(),
                response=SimpleNamespace(),
            )
        self.assertEqual(result["result"]["report_id"], "offline_question")
        self.assertEqual(run.call_args.kwargs["input_path"], "legacy.csv")

    def test_version_aware_assistant_fails_closed_before_schema_147(self):
        upgrade_required = HTTPException(
            status_code=503,
            detail={"code": "project_datasets_upgrade_required"},
        )
        with (
            patch.object(analysis_routes, "get_storage_scope", return_value=("1", "7")),
            patch.object(analysis_routes, "require_entitlement"),
            patch.object(analysis_routes, "enforce_data_workspace_rate_limit"),
            patch.object(
                project_dataset_service,
                "require_project_datasets_schema",
                side_effect=upgrade_required,
            ),
            patch.object(project_dataset_service, "resolve_project_dataset_version") as resolve,
        ):
            with self.assertRaises(HTTPException) as unavailable:
                analysis_routes.assisted_analysis_for_dataset_version(
                    user_id=7,
                    project_id=PROJECT_A,
                    dataset_id=DATASET_A,
                    version_id=VERSION_A,
                    request=analysis_routes.VersionAssistedAnalysisRequest(question="summary"),
                    fastapi_request=SimpleNamespace(),
                    response=SimpleNamespace(),
                )
        self.assertEqual(unavailable.exception.status_code, 503)
        resolve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
