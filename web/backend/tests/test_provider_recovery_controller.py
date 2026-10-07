import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

WEB_ROOT = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB_ROOT))
from deployment.lib.provider_recovery import RecoveryContract, ProviderRecoveryTransaction, reject_ordinary_operation
from deployment.lib.runtime_authority import load_worker_authority


class RecoveryControllerTests(unittest.TestCase):
    def setUp(self):
        self.contract = RecoveryContract("a"*40, "b"*40, "c"*40, "green",
            {"backend": "sha256:"+"d"*64, "frontend": "sha256:"+"e"*64},
            {key: "f"*64 for key in ("environment", "state", "upstream", "worker_authority", "controller")},
            "1"*64, "2"*64, "3"*64)
        self.metadata = {"migration_policy": "none", "schema": {
            "compatible_min": 115, "compatible_max": 115, "target": 115,
            "rollback_compatible_min": 115, "rollback_compatible_max": 115, "migration_class": "none"}}
        self.origin = {"provider_http": {"auth": 402, "rest": 402}, "sha": "b"*40,
            "slot": "green", "installed_sha": "c"*40, "schema": 115,
            "production_fingerprints": self.contract.production_fingerprints,
            "readiness": {slot: {"environment": "ok", "redis": "ok", "storage": "ok", "admin_mfa_policy": "ok", "parser_isolation": "ok", "auth": "unavailable", "database": "unavailable", "backup_freshness": "stale"} for slot in ("active", "stable")},
            **{key: True for key in ("canonical_repository", "clean_repository", "controller_provenance_valid", "traffic_identity_valid", "no_pending_release_or_migration", "source_schema115", "local_checkpoint_valid")}}
        self.target = {"sha": "a"*40, "images": self.contract.images, "schema": 115,
            "migrations_executed": False, "supabase_url": "http://madar-supabase:8000", "network": "madar-supabase-client",
            "checkpoint_digest": "1"*64, "rollback_runtime_digest": "2"*64,
            "checks": {key: True for key in ("auth", "rest", "storage", "schema", "all_supabase_services", "internal_network", "loopback_ports", "auth_linkage", "mfa_aal2", "tenant_isolation", "business_write_fence", "no_consumers", "checkpoint_valid", "rollback_live_local_compatible", "image_provenance")}}

    def test_http402_provenance_and_each_critical_check_are_mandatory(self):
        self.contract.validate(self.metadata)
        self.contract.validate_origin(self.origin)
        self.contract.validate_target(self.target)
        for name in self.target["checks"]:
            evidence = copy.deepcopy(self.target)
            evidence["checks"][name] = False
            with self.subTest(check=name), self.assertRaises(RuntimeError):
                self.contract.validate_target(evidence)
        for status in (200, 401, 403, 500, 503, None):
            evidence = copy.deepcopy(self.origin)
            evidence["provider_http"]["auth"] = status
            with self.subTest(status=status), self.assertRaises(RuntimeError):
                self.contract.validate_origin(evidence)
        evidence = copy.deepcopy(self.origin)
        evidence["readiness"]["active"]["redis"] = "unavailable"
        with self.assertRaises(RuntimeError):
            self.contract.validate_origin(evidence)
        evidence = copy.deepcopy(self.origin)
        evidence["local_checkpoint_valid"] = False
        with self.assertRaises(RuntimeError):
            self.contract.validate_origin(evidence)

    def test_non_migrating_exact_schema_contract(self):
        for key, value in (("target", 116), ("compatible_max", 116), ("migration_class", "expand-only")):
            metadata = copy.deepcopy(self.metadata)
            metadata["schema"][key] = value
            with self.assertRaises(RuntimeError):
                self.contract.validate(metadata)
        for key, value in (("migration_policy", "automatic"), ("migration_manifest", None)):
            metadata = copy.deepcopy(self.metadata)
            metadata[key] = value
            with self.assertRaises(RuntimeError):
                self.contract.validate(metadata)

    def test_transaction_never_activates_workers_and_rollback_preserves_database(self):
        test = self
        class Operations:
            def __init__(self): self.calls = []; self.fail = False
            def authorize(self, contract): self.calls.append("authorize")
            def origin_evidence(self): return test.origin
            def target_evidence(self): return test.target
            def prepare_candidate(self, contract, slot): self.calls.append("prepare")
            def inhibit_all_workers(self): self.calls.append("inhibit")
            def require_all_workers_off(self): self.calls.append("workers_off")
            def switch_recovery_traffic(self, contract, slot): self.calls.append("switch")
            def smoke_recovery(self, contract, slot):
                self.calls.append("smoke")
                if self.fail: raise RuntimeError("fixture_failure")
            def switch_local_rollback(self, contract): self.calls.append("local_rollback")
            def verify_local_rollback(self, contract): self.calls.append("verify_rollback")
        for fail in (False, True):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                ops = Operations(); ops.fail = fail
                transaction = ProviderRecoveryTransaction(root, ops)
                if fail:
                    with self.assertRaises(RuntimeError): transaction.activate(self.contract, self.metadata)
                else:
                    self.assertEqual(transaction.activate(self.contract, self.metadata)["phase"], "active")
                self.assertEqual(load_worker_authority(root)["owner"], "RECOVERY")
                self.assertFalse(json.loads((root / "provider-recovery.json").read_text())["restore_database_on_rollback"])
                with self.assertRaises(RuntimeError): reject_ordinary_operation(root)
                self.assertLess(ops.calls.index("inhibit"), ops.calls.index("switch"))
                self.assertNotIn("activate_workers", ops.calls)
                if fail: self.assertIn("local_rollback", ops.calls)

    def test_missing_recovery_authorization_is_rejected(self):
        from deployment.lib.control_plane_upgrade_authorization import require_upgrade_authorization
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(RuntimeError):
                require_upgrade_authorization("a"*40, interlock=Path(temporary)/"absent.json", required_operation="provider402-signin", required_schema=115, require_rehearsal=True)

    def test_pre_switch_failure_keeps_interlock_without_routing_or_worker_restore(self):
        class Operations:
            def authorize(self, contract): pass
            def origin_evidence(inner): return self.origin
            def target_evidence(inner): return self.target
            def prepare_candidate(inner, contract, slot): raise RuntimeError("fixture_prepare_failure")
            def switch_local_rollback(inner, contract): self.fail("pre-switch failure must not change traffic")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(RuntimeError):
                ProviderRecoveryTransaction(root, Operations()).activate(self.contract, self.metadata)
            self.assertEqual(json.loads((root/"provider-recovery.json").read_text())["phase"], "pre_switch_failed_operator_review_required")
