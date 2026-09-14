import json
import sys
import os
import tempfile
import unittest
from pathlib import Path

WEB_ROOT = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB_ROOT))

from deployment.lib.release_deployer import Compatibility, ReleaseDeployer


SHA = "a" * 40


class FakeOperations:
    def __init__(self, fail_at=None, schema=82):
        self.fail_at = fail_at
        self.schema = schema
        self.calls = []
        self.traffic = "blue"

    def _call(self, name, *args):
        self.calls.append((name, *args))
        if self.fail_at == name:
            raise RuntimeError(f"injected_{name}_failure")

    def verify_source(self, sha): self._call("verify_source", sha)
    def build(self, sha, slot):
        self._call("build", sha, slot)
        return {"backend": "backend@sha256:1", "frontend": "frontend@sha256:2", "worker": "worker@sha256:3"}
    def schema_version(self):
        self._call("schema_version")
        return self.schema
    def preflight(self, sha, slot, images, schema): self._call("preflight", sha, slot, schema)
    def start_candidate(self, sha, slot, images): self._call("start_candidate", sha, slot)
    def validate_candidate(self, sha, slot): self._call("validate_candidate", sha, slot)
    def validate_rollback_target(self, release, schema):
        self._call("validate_rollback_target", release["sha"], release["slot"], schema)
        if self.fail_at == "rollback_schema":
            raise RuntimeError("known_good_rollback_schema_incompatible")
        return {"compatible_min": 81, "compatible_max": 83}
    def activate_workers(self, sha, slot, images): self._call("activate_workers", sha, slot)
    def deactivate_workers(self, release): self._call("deactivate_workers", release["slot"])
    def restore_workers(self, release): self._call("restore_workers", release["slot"])
    def switch_traffic(self, slot):
        self._call("switch_traffic", slot)
        self.traffic = slot
    def observe(self, sha, slot): self._call("observe", sha, slot)
    def stop_candidate(self, slot): self._call("stop_candidate", slot)
    def current_traffic_slot(self):
        self._call("current_traffic_slot")
        return self.traffic
    def resolve_serving_slot(self, expected):
        self._call("resolve_serving_slot", tuple(sorted(expected.items())))
        return self.traffic if self.traffic in expected else None
    def validate_recovery_backup(self, schema):
        self._call("validate_recovery_backup", schema)
        return {
            "backup_id": "madar-20260914T000000Z",
            "schema": schema,
            "manifest_sha256": "1" * 64,
            "node1_sha256sums_sha256": "2" * 64,
        }


class ReleaseDeployerTests(unittest.TestCase):
    def compatibility(self):
        return Compatibility(81, 82, 82, "expand-only", 81, 82)

    def deployer(self, root, operations):
        return ReleaseDeployer(state_root=Path(root), compatibility=self.compatibility(), operations=operations)

    def test_success_records_immutable_known_good_release(self):
        with tempfile.TemporaryDirectory() as root:
            operations = FakeOperations()
            result = self.deployer(root, operations).deploy(SHA)
            state = json.loads((Path(root) / "state.json").read_text())
        self.assertEqual(result["status"], "known_good")
        self.assertEqual(state["known_good_release"]["sha"], SHA)
        self.assertEqual(state["active_slot"], "green")
        self.assertEqual(state["known_good_release"]["schema_compatible_max"], 82)

    def test_every_pre_switch_failure_leaves_active_target_untouched(self):
        for phase in ("verify_source", "build", "schema_version", "preflight", "start_candidate", "validate_candidate"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as root:
                operations = FakeOperations(fail_at=phase)
                with self.assertRaises(RuntimeError):
                    self.deployer(root, operations).deploy(SHA)
                switches = [call for call in operations.calls if call[0] == "switch_traffic"]
                self.assertEqual(switches, [])
                self.assertIn(("stop_candidate", "green"), operations.calls)

    def test_post_switch_crash_switches_back_without_rebuild(self):
        with tempfile.TemporaryDirectory() as root:
            operations = FakeOperations(fail_at="observe")
            with self.assertRaises(RuntimeError):
                self.deployer(root, operations).deploy(SHA)
        self.assertEqual(
            [call for call in operations.calls if call[0] == "switch_traffic"],
            [("switch_traffic", "green"), ("switch_traffic", "blue")],
        )
        self.assertIn(("deactivate_workers", "green"), operations.calls)
        self.assertFalse(any(call[0] == "restore_workers" for call in operations.calls))
        self.assertEqual(sum(call[0] == "build" for call in operations.calls), 1)

    def test_rollback_switch_failure_is_durable_and_preserves_candidate(self):
        class RollbackFailureOperations(FakeOperations):
            def switch_traffic(self, slot):
                self.calls.append(("switch_traffic", slot))
                if len([call for call in self.calls if call[0] == "switch_traffic"]) == 2:
                    raise RuntimeError("injected_rollback_switch_failure")

        with tempfile.TemporaryDirectory() as root:
            operations = RollbackFailureOperations(fail_at="observe")
            with self.assertRaisesRegex(RuntimeError, "automatic_rollback_failed_manual_intervention"):
                self.deployer(root, operations).deploy(SHA)
            state = json.loads((Path(root) / "state.json").read_text())
        self.assertEqual(state["in_progress_release"]["phase"], "rollback_failed")
        self.assertEqual(state["rollback_failure"]["required_target"], "blue")
        self.assertFalse(any(call[0] == "stop_candidate" for call in operations.calls))

    def test_worker_cutover_failure_restores_retained_workers_before_traffic_switch(self):
        with tempfile.TemporaryDirectory() as root:
            self.deployer(root, FakeOperations()).deploy(SHA)
            operations = FakeOperations(fail_at="activate_workers")
            with self.assertRaisesRegex(RuntimeError, "injected_activate_workers_failure"):
                self.deployer(root, operations).deploy("b" * 40)
        self.assertFalse(any(call[0] == "switch_traffic" for call in operations.calls))
        self.assertIn(("deactivate_workers", "green"), operations.calls)
        self.assertIn(("restore_workers", "green"), operations.calls)

    def test_db_redis_worker_storage_and_frontend_faults_are_preflight_or_validation_failures(self):
        # The operations layer maps these dependency injections into one of the
        # pre-switch preflight/start/deep-validation phases. The state machine's
        # safety invariant is identical for every dependency.
        for fault_phase in ("preflight", "start_candidate", "validate_candidate"):
            with self.subTest(fault_phase=fault_phase), tempfile.TemporaryDirectory() as root:
                operations = FakeOperations(fail_at=fault_phase)
                with self.assertRaises(RuntimeError):
                    self.deployer(root, operations).deploy(SHA)
                self.assertFalse(any(call[0] == "switch_traffic" for call in operations.calls))

    def test_incompatible_old_or_new_schema_is_rejected_before_start(self):
        for version in (80, 83):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as root:
                operations = FakeOperations(schema=version)
                with self.assertRaisesRegex(RuntimeError, "candidate_schema_incompatible"):
                    self.deployer(root, operations).deploy(SHA)
                self.assertFalse(any(call[0] == "start_candidate" for call in operations.calls))

    def test_repeated_bad_sha_is_circuit_broken_until_manual_retry(self):
        with tempfile.TemporaryDirectory() as root:
            failing = FakeOperations(fail_at="build")
            deployer = self.deployer(root, failing)
            with self.assertRaises(RuntimeError):
                deployer.deploy(SHA)
            second = FakeOperations()
            with self.assertRaisesRegex(RuntimeError, "known_bad_release_suppressed"):
                self.deployer(root, second).deploy(SHA)
            self.assertEqual(second.calls, [])
            result = self.deployer(root, second).deploy(SHA, manual_retry=True)
            self.assertEqual(result["status"], "known_good")

    def test_retained_target_is_attested_against_observed_schema_before_start(self):
        with tempfile.TemporaryDirectory() as root:
            first = self.deployer(root, FakeOperations())
            first.deploy(SHA)
            operations = FakeOperations(fail_at="rollback_schema", schema=82)
            with self.assertRaisesRegex(RuntimeError, "known_good_rollback_schema_incompatible"):
                self.deployer(root, operations).deploy("b" * 40)
            self.assertFalse(any(call[0] == "start_candidate" for call in operations.calls))

    def test_interrupted_release_is_rolled_back_and_archived_before_next_attempt(self):
        class InterruptingOperations(FakeOperations):
            def observe(self, sha, slot):
                self._call("observe", sha, slot)
                raise KeyboardInterrupt()

        with tempfile.TemporaryDirectory() as root:
            interrupted = InterruptingOperations()
            with self.assertRaises(KeyboardInterrupt):
                self.deployer(root, interrupted).deploy(SHA)
            persisted = json.loads((Path(root) / "state.json").read_text())
            self.assertEqual(persisted["in_progress_release"]["phase"], "observation")
            resumed = FakeOperations()
            result = self.deployer(root, resumed).deploy("b" * 40)
            state = json.loads((Path(root) / "state.json").read_text())
        self.assertEqual(result["status"], "known_good")
        self.assertIn(("switch_traffic", "blue"), resumed.calls)
        self.assertIn(("stop_candidate", "green"), resumed.calls)
        self.assertTrue(any(row.get("status") == "interrupted_recovered" for row in state["history"]))


class SchemaRecoveryDeployerTests(unittest.TestCase):
    OLD_SHA = "1" * 40

    @staticmethod
    def compatibility():
        return Compatibility(96, 96, 96, "none", 96, 96)

    def seed(self, root):
        state = {
            "active_slot": "blue",
            "known_good_release": {
                "sha": self.OLD_SHA,
                "slot": "blue",
                "schema": 93,
                "images": {
                    "backend": "old@sha256:1",
                    "frontend": "old@sha256:2",
                    "worker": "old@sha256:3",
                },
            },
            "history": [],
            "failed_releases": {},
        }
        Path(root, "state.json").write_text(json.dumps(state))

    def deployer(self, root, operations):
        return ReleaseDeployer(
            state_root=Path(root),
            compatibility=self.compatibility(),
            operations=operations,
        )

    def test_recovery_requires_exact_zero_migration_contract(self):
        for compatibility, error in (
            (Compatibility(95, 96, 96, "none", 95, 96), "not_exact_schema"),
            (Compatibility(96, 96, 96, "expand-only", 96, 96), "requires_migration"),
        ):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as root:
                operations = FakeOperations(schema=96)
                deployer = ReleaseDeployer(
                    state_root=Path(root), compatibility=compatibility,
                    operations=operations,
                )
                with self.assertRaisesRegex(RuntimeError, error):
                    deployer.recover_current_schema(SHA)
                self.assertEqual(operations.calls, [])

    def test_recovery_establishes_active_and_inactive_schema96_targets(self):
        with tempfile.TemporaryDirectory() as root:
            self.seed(root)
            operations = FakeOperations(schema=96)
            result = self.deployer(root, operations).recover_current_schema(SHA)
            state = json.loads(Path(root, "state.json").read_text())
        self.assertEqual(result["status"], "known_good")
        self.assertEqual(state["active_slot"], "green")
        self.assertEqual(state["known_good_release"]["schema"], 96)
        self.assertTrue(state["known_good_release"]["schema_recovery"])
        self.assertEqual(
            state["known_good_release"]["migration_result"], "not_requested"
        )
        self.assertEqual(state["compatible_fallback_release"]["slot"], "blue")
        self.assertEqual(state["compatible_fallback_release"]["sha"], SHA)
        self.assertTrue(state["compatible_fallback_release"]["schema_recovery"])
        self.assertEqual(operations.traffic, "green")
        self.assertEqual(
            [call for call in operations.calls if call[0] == "switch_traffic"],
            [("switch_traffic", "green")],
        )

    def test_schema_change_aborts_before_switch(self):
        class ChangingSchema(FakeOperations):
            def validate_recovery_backup(self, schema):
                result = super().validate_recovery_backup(schema)
                if sum(call[0] == "validate_recovery_backup" for call in self.calls) == 2:
                    self.schema = 97
                return result

        with tempfile.TemporaryDirectory() as root:
            self.seed(root)
            operations = ChangingSchema(schema=96)
            with self.assertRaisesRegex(RuntimeError, "pre_switch_state_changed"):
                self.deployer(root, operations).recover_current_schema(SHA)
            state = json.loads(Path(root, "state.json").read_text())
        self.assertEqual(operations.traffic, "blue")
        self.assertNotIn("in_progress_release", state)

    def test_candidate_failure_never_switches(self):
        with tempfile.TemporaryDirectory() as root:
            self.seed(root)
            operations = FakeOperations(fail_at="validate_candidate", schema=96)
            with self.assertRaisesRegex(RuntimeError, "injected_validate_candidate_failure"):
                self.deployer(root, operations).recover_current_schema(SHA)
        self.assertEqual(operations.traffic, "blue")

    def test_partial_retained_worker_stop_failure_restores_before_abort(self):
        with tempfile.TemporaryDirectory() as root:
            self.seed(root)
            operations = FakeOperations(fail_at="deactivate_workers", schema=96)
            with self.assertRaisesRegex(
                RuntimeError, "injected_deactivate_workers_failure"
            ):
                self.deployer(root, operations).recover_current_schema(SHA)
        self.assertEqual(operations.traffic, "blue")
        self.assertIn(("restore_workers", "blue"), operations.calls)
        self.assertFalse(any(call[0] == "switch_traffic" for call in operations.calls))

    def test_missing_or_stale_backup_rejects_before_source_or_build(self):
        with tempfile.TemporaryDirectory() as root:
            self.seed(root)
            operations = FakeOperations(
                fail_at="validate_recovery_backup", schema=96
            )
            with self.assertRaisesRegex(
                RuntimeError, "injected_validate_recovery_backup_failure"
            ):
                self.deployer(root, operations).recover_current_schema(SHA)
        self.assertFalse(any(call[0] == "verify_source" for call in operations.calls))
        self.assertFalse(any(call[0] == "build" for call in operations.calls))
        self.assertEqual(operations.traffic, "blue")

    def test_post_switch_failure_never_returns_to_incompatible_release(self):
        with tempfile.TemporaryDirectory() as root:
            self.seed(root)
            operations = FakeOperations(fail_at="observe", schema=96)
            with self.assertRaisesRegex(
                RuntimeError, "recovery_post_switch_forward_repair_required"
            ):
                self.deployer(root, operations).recover_current_schema(SHA)
            state = json.loads(Path(root, "state.json").read_text())
        self.assertEqual(operations.traffic, "green")
        self.assertEqual(state["in_progress_release"]["candidate_slot"], "green")
        self.assertFalse(
            any(call == ("switch_traffic", "blue") for call in operations.calls)
        )

    def test_interrupted_post_switch_recovery_resumes_forward(self):
        with tempfile.TemporaryDirectory() as root:
            self.seed(root)
            first = FakeOperations(fail_at="observe", schema=96)
            with self.assertRaises(RuntimeError):
                self.deployer(root, first).recover_current_schema(SHA)
            resumed = FakeOperations(schema=96)
            resumed.traffic = "green"
            result = self.deployer(root, resumed).recover_current_schema(SHA)
        self.assertEqual(result["status"], "known_good")
        self.assertEqual(resumed.traffic, "green")
        self.assertFalse(any(call[0] == "switch_traffic" for call in resumed.calls))

    def test_completed_recovery_rerun_is_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            self.seed(root)
            first = FakeOperations(schema=96)
            self.deployer(root, first).recover_current_schema(SHA)
            before = Path(root, "state.json").read_bytes()
            second = FakeOperations(schema=96)
            second.traffic = "green"
            result = self.deployer(root, second).recover_current_schema(SHA)
            after = Path(root, "state.json").read_bytes()
        self.assertEqual(result["status"], "already_recovered")
        self.assertEqual(before, after)
        self.assertFalse(any(call[0] == "switch_traffic" for call in second.calls))

    def test_interrupted_pre_switch_recovery_cleans_candidate_then_retries(self):
        class InterruptBeforeSwitch(FakeOperations):
            def validate_candidate(self, sha, slot):
                self._call("validate_candidate", sha, slot)
                raise KeyboardInterrupt()

        with tempfile.TemporaryDirectory() as root:
            self.seed(root)
            interrupted = InterruptBeforeSwitch(schema=96)
            with self.assertRaises(KeyboardInterrupt):
                self.deployer(root, interrupted).recover_current_schema(SHA)
            self.assertEqual(interrupted.traffic, "blue")
            resumed = FakeOperations(schema=96)
            result = self.deployer(root, resumed).recover_current_schema(SHA)
            state = json.loads(Path(root, "state.json").read_text())
        self.assertEqual(result["status"], "known_good")
        self.assertIn(("stop_candidate", "green"), resumed.calls)
        self.assertIn(("restore_workers", "blue"), resumed.calls)
        self.assertNotIn("in_progress_release", state)

    def test_interrupted_post_switch_recovery_resumes_without_old_traffic(self):
        class InterruptAfterSwitch(FakeOperations):
            def observe(self, sha, slot):
                self._call("observe", sha, slot)
                raise KeyboardInterrupt()

        with tempfile.TemporaryDirectory() as root:
            self.seed(root)
            interrupted = InterruptAfterSwitch(schema=96)
            with self.assertRaises(KeyboardInterrupt):
                self.deployer(root, interrupted).recover_current_schema(SHA)
            self.assertEqual(interrupted.traffic, "green")
            resumed = FakeOperations(schema=96)
            resumed.traffic = "green"
            result = self.deployer(root, resumed).recover_current_schema(SHA)
        self.assertEqual(result["status"], "known_good")
        self.assertFalse(any(call == ("switch_traffic", "blue") for call in resumed.calls))

    def test_lost_switch_ack_reconciles_serving_candidate(self):
        class LostAck(FakeOperations):
            def switch_traffic(self, slot):
                self.calls.append(("switch_traffic", slot))
                self.traffic = slot
                raise RuntimeError("lost acknowledgement")

        with tempfile.TemporaryDirectory() as root:
            self.seed(root)
            operations = LostAck(schema=96)
            result = self.deployer(root, operations).recover_current_schema(SHA)
        self.assertEqual(result["status"], "known_good")
        self.assertEqual(operations.traffic, "green")
        self.assertFalse(any(call == ("stop_candidate", "green") for call in operations.calls))

    def test_ambiguous_switch_preserves_both_targets_and_checkpoint(self):
        class Ambiguous(FakeOperations):
            def switch_traffic(self, slot):
                self.calls.append(("switch_traffic", slot))
                raise RuntimeError("unknown switch outcome")
            def resolve_serving_slot(self, expected):
                self.calls.append(("resolve_serving_slot", tuple(sorted(expected.items()))))
                return None

        with tempfile.TemporaryDirectory() as root:
            self.seed(root)
            operations = Ambiguous(schema=96)
            with self.assertRaisesRegex(RuntimeError, "recovery_traffic_state_ambiguous"):
                self.deployer(root, operations).recover_current_schema(SHA)
            state = json.loads(Path(root, "state.json").read_text())
        self.assertIn("in_progress_release", state)
        self.assertFalse(any(call[0] == "stop_candidate" for call in operations.calls))
        self.assertFalse(any(call[0] == "restore_workers" for call in operations.calls))

    def test_normal_release_is_accepted_after_schema96_recovery(self):
        next_sha = "b" * 40

        class Schema96Operations(FakeOperations):
            def validate_rollback_target(self, release, schema):
                self._call("validate_rollback_target", release["sha"], release["slot"], schema)
                return {"compatible_min": 96, "compatible_max": 96}

        with tempfile.TemporaryDirectory() as root:
            self.seed(root)
            recovered = Schema96Operations(schema=96)
            self.deployer(root, recovered).recover_current_schema(SHA)
            normal = Schema96Operations(schema=96)
            normal.traffic = "green"
            deployer = ReleaseDeployer(
                state_root=Path(root),
                compatibility=Compatibility(96, 99, 99, "expand-only", 96, 99),
                operations=normal,
            )
            result = deployer.deploy(next_sha)
        self.assertEqual(result["status"], "known_good")
        self.assertIn(("validate_rollback_target", SHA, "green", 96), normal.calls)


if __name__ == "__main__":
    unittest.main()
