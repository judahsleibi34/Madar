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
    def switch_traffic(self, slot): self._call("switch_traffic", slot)
    def observe(self, sha, slot): self._call("observe", sha, slot)
    def stop_candidate(self, slot): self._call("stop_candidate", slot)


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


if __name__ == "__main__":
    unittest.main()
