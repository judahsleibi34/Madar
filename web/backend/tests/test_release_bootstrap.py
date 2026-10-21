import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest.mock import Mock
from contextlib import nullcontext


WEB_ROOT = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT") or Path(__file__).resolve().parents[2])
SCRIPT = WEB_ROOT / "deployment" / "bin" / "madar-release-deploy"
loader = importlib.machinery.SourceFileLoader("madar_release_deploy_cli", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
release_cli = importlib.util.module_from_spec(spec)
loader.exec_module(release_cli)


SHA = "c" * 40


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeOperations:
    def __init__(self):
        self.calls = []
        self.compatibility = release_cli.Compatibility(
            81, 83, 83, "expand-only", 81, 83,
        )

    def verify_source(self, sha): self.calls.append(("verify_source", sha))
    def build(self, sha, slot):
        self.calls.append(("build", sha, slot))
        return {
            "backend": "backend@sha256:1", "frontend": "frontend@sha256:2",
            "worker": "backend@sha256:1", "build_timestamp": "2026-08-25T00:00:00Z",
        }
    def schema_version(self):
        self.calls.append(("schema_version",))
        return 83
    def preflight(self, sha, slot, images, schema): self.calls.append(("preflight", sha, slot, schema))
    def start_candidate(self, sha, slot, images): self.calls.append(("start_candidate", sha, slot))
    def validate_candidate(self, sha, slot): self.calls.append(("validate_candidate", sha, slot))
    def validate_active_refresh_prerequisites(self, sha, slot, images):
        self.calls.append(("validate_active_refresh_prerequisites", sha, slot))
    def refresh_active_runtime_services(self, sha, slot, images):
        self.calls.append(("refresh_active_runtime_services", sha, slot))
    def validate_stable_candidate(self, sha):
        self.calls.append(("validate_stable_candidate", sha))
    def stop_candidate(self, slot): self.calls.append(("stop_candidate", slot))
    def activate_workers(self, sha, slot, images): self.calls.append(("activate_workers", sha, slot))
    def deactivate_workers(self, release): self.calls.append(("deactivate_workers", release["slot"]))
    def _json(self, url):
        if url.endswith("/health/version"):
            return {"release_sha": SHA}
        return {"ready": True}


class ReleaseBootstrapTests(unittest.TestCase):
    def compatibility(self):
        return release_cli.Compatibility(81, 83, 83, "expand-only", 81, 83)

    def test_maintenance_child_creates_all_roles_without_starting_or_handoff(self):
        from test_schema150_admission import deletion_contract
        from deployment.lib.completed_normal_resources import ROLES
        operations=release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
        operations.completed_normal_admission=deletion_contract()
        operations.state_root=Path('/unused-synthetic-state')
        operations._loaded_serving_slot=Mock(side_effect=AssertionError('fenced ingress has no HTTP'))
        operations._maintenance_creation_guard=Mock(return_value=operations.completed_normal_admission)
        operations.verify_completed_normal_allocation=Mock()
        operations._compose=Mock()
        operations._inhibit_worker_slot=Mock(side_effect=AssertionError('bridge path must not run'))
        with patch.object(release_cli,'runtime_mutation_lock',return_value=nullcontext()):
            operations.start_candidate(SHA,'green',{'fixture':'images'})
        operations._maintenance_creation_guard.assert_called_once_with(SHA,'green')
        operations._compose.assert_called_once_with(SHA,'green',{'fixture':'images'},
            'create','--no-build','--no-recreate',*ROLES,workers_active=True)
        operations._inhibit_worker_slot.assert_not_called()
        operations._loaded_serving_slot.assert_not_called()

    def test_maintenance_creation_guard_binds_fenced_backup_and_original_runtime_state(self):
        from test_schema150_admission import deletion_contract
        from deployment.lib.completed_normal_admission import digest
        from deployment.lib.completed_normal_migration import intent_document
        import copy
        contract=deletion_contract();sha=contract['candidate']['source_sha']
        witness={'intent':intent_document(contract),'provider_maintenance':{'version':1,
            'binding':{'operation':contract['operation'],'context_sha256':digest(contract),'source_sha':sha,
                'controller_sha':contract['candidate']['controller_sha'],'inventory_sha256':contract['writer_inventory_sha256'],
                'system_identifier':contract['database']['system_identifier'],'source_schema':146,'target_schema':150},
            'journal_sha256':'a'*64,'preimage_sha256':'b'*64}}
        with tempfile.TemporaryDirectory() as directory,\
                patch('deployment.lib.completed_normal_admission.require_candidate_authority') as authority,\
                patch('deployment.lib.completed_normal_admission.credential_witness',return_value=witness) as credential:
            operations=release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
            operations.completed_normal_admission=contract;operations.state_root=Path(directory)
            state={'active_slot':contract['origin']['slot'],'known_good_release':{'slot':contract['origin']['slot'],
                'sha':contract['source_roles']['application_sha'],'schema':146}}
            path=Path(directory)/'state.json';path.write_text(json.dumps(state))
            self.assertEqual(operations._maintenance_creation_guard(sha,'green'),contract)
            authority.assert_called_once_with(contract,mode='READ_ONLY')
            credential.assert_called_once_with('migration_inputs','migration_inputs_sha256')
            for mutate in (lambda v:v['provider_maintenance']['binding'].update(system_identifier='999'),
                    lambda v:v['provider_maintenance']['binding'].update(source_sha='0'*40),
                    lambda v:v['provider_maintenance'].update(journal_sha256='invalid'),
                    lambda v:v['intent'].update(manifest_sha256='0'*64)):
                bad=copy.deepcopy(witness);mutate(bad);credential.return_value=bad
                with self.assertRaisesRegex(RuntimeError,'fenced_witness_required'):
                    operations._maintenance_creation_guard(sha,'green')
            credential.return_value=witness
            state['known_good_release']['schema']=147;path.write_text(json.dumps(state))
            with self.assertRaisesRegex(RuntimeError,'origin_changed'):
                operations._maintenance_creation_guard(sha,'green')

    def test_maintenance_preparation_receipt_is_not_worker_activation_or_health(self):
        from test_schema150_admission import deletion_contract
        operations=FakeOperations()
        operations.completed_normal_admission=deletion_contract()
        operations.schema_version=lambda:146
        operations.validate_created_candidate=Mock()
        compatibility=release_cli.Compatibility(146,150,150,'coordinated',146,150)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            record=release_cli.prepare_release(sha=SHA,slot='green',state_root=root,
                compatibility=compatibility,operations=operations)
            self.assertEqual(record['status'],'candidate_created_fenced')
            self.assertFalse(any(c[0] in {'validate_candidate','activate_workers'} for c in operations.calls))
            with self.assertRaisesRegex(RuntimeError,'state_invalid'):
                release_cli.activate_prepared_release(sha=SHA,slot='green',state_root=root,operations=operations)
            second=release_cli.prepare_release(sha=SHA,slot='green',state_root=root,
                compatibility=compatibility,operations=operations)
            self.assertEqual(second,record)
            self.assertEqual(len([c for c in operations.calls if c[0]=='start_candidate']),1)
        self.assertEqual(operations.validate_created_candidate.call_count,2)

    def test_maintenance_create_refuses_missing_authority_before_compose(self):
        from test_schema150_admission import deletion_contract
        operations=release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
        operations.completed_normal_admission=deletion_contract()
        operations.state_root=Path('/unused-synthetic-state')
        operations._loaded_serving_slot=Mock(return_value='blue')
        operations.verify_completed_normal_allocation=Mock()
        operations._compose=Mock()
        with patch.object(release_cli,'runtime_mutation_lock',return_value=nullcontext()),\
                patch('deployment.lib.completed_normal_admission.require_candidate_authority',side_effect=RuntimeError('authority_missing')):
            with self.assertRaisesRegex(RuntimeError,'authority_missing'):
                operations.start_candidate(SHA,'green',{})
        operations._compose.assert_not_called()

    def test_invalid_production_identity_fails_before_release_state_initialization(self):
        with (
            patch.object(
                release_cli,
                "require_production_mutation_identity",
                side_effect=RuntimeError(
                    "production_mutation_identity_invalid"
                ),
            ) as identity_guard,
            patch.object(
                release_cli,
                "load_production_path_contract",
            ) as load_contract,
            patch.object(
                release_cli,
                "require_upgrade_authorization",
            ) as authorization_guard,
            patch.object(
                release_cli.sys,
                "argv",
                [
                    str(release_cli.SCRIPT),
                    SHA,
                ],
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "production_mutation_identity_invalid",
            ):
                release_cli.main()

        identity_guard.assert_called_once_with(
            release_cli.SCRIPT
        )
        load_contract.assert_not_called()
        authorization_guard.assert_not_called()

    def test_schema_probe_uses_apikey_only_for_opaque_server_secret(self):
        headers = release_cli.supabase_server_headers(
            "sb_secret_synthetic_fixture_not_a_credential"
        )
        self.assertEqual({name.lower() for name in headers}, {"apikey"})

    def test_schema_probe_retains_legacy_service_role_bearer(self):
        headers = release_cli.supabase_server_headers(
            "synthetic-legacy-service-role-jwt"
        )
        self.assertEqual(
            {name.lower() for name in headers},
            {"apikey", "authorization"},
        )

    def test_prepare_keeps_workers_and_traffic_inactive(self):
        with tempfile.TemporaryDirectory() as root:
            operations = FakeOperations()
            record = release_cli.prepare_release(
                sha=SHA, slot="green", state_root=Path(root),
                compatibility=self.compatibility(), operations=operations,
            )
            persisted = json.loads((Path(root) / "prepared-release.json").read_text())
        self.assertEqual(record["status"], "candidate_validated_workers_inactive")
        self.assertEqual(persisted["release_sha"], SHA)
        self.assertFalse(any(call[0] == "activate_workers" for call in operations.calls))

    def test_activate_requires_exact_prepared_identity(self):
        with tempfile.TemporaryDirectory() as root:
            operations = FakeOperations()
            release_cli.prepare_release(
                sha=SHA, slot="green", state_root=Path(root),
                compatibility=self.compatibility(), operations=operations,
            )
            with self.assertRaisesRegex(RuntimeError, "identity_mismatch"):
                release_cli.activate_prepared_release(
                    sha="d" * 40, slot="green", state_root=Path(root), operations=operations,
                )
            result = release_cli.activate_prepared_release(
                sha=SHA, slot="green", state_root=Path(root), operations=operations,
            )
        self.assertEqual(result["status"], "candidate_workers_active")

    def test_adoption_requires_workers_and_stable_proxy_identity(self):
        with tempfile.TemporaryDirectory() as root:
            operations = FakeOperations()
            release_cli.prepare_release(
                sha=SHA, slot="green", state_root=Path(root),
                compatibility=self.compatibility(), operations=operations,
            )
            with self.assertRaisesRegex(RuntimeError, "workers_not_active"):
                release_cli.adopt_prepared_release(
                    sha=SHA, slot="green", state_root=Path(root),
                    compatibility=self.compatibility(), operations=operations,
                )
            release_cli.activate_prepared_release(
                sha=SHA, slot="green", state_root=Path(root), operations=operations,
            )
            with patch.object(release_cli.urllib.request, "urlopen", return_value=FakeResponse()):
                result = release_cli.adopt_prepared_release(
                    sha=SHA, slot="green", state_root=Path(root),
                    compatibility=self.compatibility(), operations=operations,
                )
            state = json.loads((Path(root) / "state.json").read_text())
        self.assertEqual(result["phase"], "bootstrap_adopted")
        self.assertEqual(state["known_good_release"]["sha"], SHA)
        self.assertFalse((Path(root) / "prepared-release.json").exists())

    def test_inactive_candidate_masks_active_worker_requirements_until_cutover(self):
        operations = release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
        operations.compatibility = release_cli.Compatibility(
            schema_min=81,
            schema_max=86,
            target_schema=86,
            migration_class="expand-only",
            rollback_schema_min=81,
            rollback_schema_max=86,
        )
        operations.release_root = Path("/tmp/release")
        operations.env_file = Path("/tmp/release.env")
        operations.schema_version = lambda: 83
        images = {
            "backend": "backend@sha256:1", "frontend": "frontend@sha256:2",
            "worker": "backend@sha256:1", "build_timestamp": "2026-08-25T00:00:00Z",
        }
        with patch.dict(os.environ, {
            "MADAR_STORAGE_ROOT": "/var/lib/madar/storage",
            "NOTIFICATION_WORKER_ENABLED": "true",
            "DATA_DELETION_WORKER_ENABLED": "true",
            "CALENDAR_FEATURE_ENABLED": "true",
            "CALENDAR_SYNC_WORKER_ENABLED": "true",
        }, clear=True):
            inactive = operations._environment(SHA, "green", images, workers_active=False)
            active = operations._environment(SHA, "green", images, workers_active=True)
        self.assertEqual(inactive["NOTIFICATION_WORKER_ENABLED"], "false")
        self.assertEqual(inactive["DATA_DELETION_WORKER_ENABLED"], "false")
        self.assertEqual(inactive["CALENDAR_FEATURE_ENABLED"], "false")
        self.assertEqual(inactive["CALENDAR_SYNC_WORKER_ENABLED"], "false")
        self.assertEqual(active["NOTIFICATION_WORKER_ENABLED"], "true")
        self.assertEqual(active["DATA_DELETION_WORKER_ENABLED"], "true")
        self.assertEqual(active["CALENDAR_FEATURE_ENABLED"], "true")
        self.assertEqual(active["CALENDAR_SYNC_WORKER_ENABLED"], "true")

    def test_post_migration_refresh_requires_exact_known_good_and_schema_83(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            operations = FakeOperations()
            state = {
                "active_slot": "green",
                "known_good_release": {
                    "sha": SHA, "slot": "green", "schema": 81,
                    "images": {"backend": "b", "frontend": "f", "worker": "b"},
                },
                "history": [],
            }
            (root_path / "state.json").write_text(json.dumps(state))
            operations.schema_version = lambda: 81
            with self.assertRaisesRegex(RuntimeError, "schema_not_ready"):
                release_cli.refresh_active_workers(
                    sha=SHA, slot="green", state_root=root_path, operations=operations,
                )
            operations.schema_version = lambda: 83
            result = release_cli.refresh_active_workers(
                sha=SHA, slot="green", state_root=root_path, operations=operations,
            )
            persisted = json.loads((root_path / "state.json").read_text())
        self.assertEqual(result["phase"], "post_migration_workers_refreshed")
        self.assertEqual(persisted["known_good_release"]["schema"], 83)
        self.assertIn(("refresh_active_runtime_services", SHA, "green"), operations.calls)


if __name__ == "__main__":
    unittest.main()
