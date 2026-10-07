"""State-machine unit tests; concrete installer/runtime acceptance is separate."""
import copy
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

WEB_ROOT = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB_ROOT))
from deployment.lib.provider_local_transition import (
    GATES, SMOKE_GATES, LocalProviderTransition, LocalTransitionContract, validate_evidence,
)
from deployment.lib.provider_recovery_runtime import digest
from deployment.lib.provider_local_auth_configuration import (
    CALLBACKS, SMTP_KEYS, configuration_changes, validate_preparation_evidence,
)


class Operations:
    def __init__(self, report, fingerprints):
        self.report = report
        self.fp = dict(fingerprints)
        self.calls = []
        self.mode = "READ_ONLY"
        self.authorized = True
        self.smoke = {key: "PASS" for key in SMOKE_GATES}

    def require_authorization(self, _):
        if not self.authorized:
            raise RuntimeError("authorization")

    def evidence(self):
        return self.report

    def fingerprints(self):
        return dict(self.fp)

    def set_write_authority(self, _, mode):
        self.calls.append("write:"+mode)
        self.mode = mode

    def require_write_authority(self, _, mode):
        if self.mode != mode:
            raise RuntimeError("wrong_write_authority")

    def final_smoke(self, _):
        return self.smoke

    def __getattr__(self, name):
        def operation(*args, **kwargs):
            self.calls.append(name)
            if name == "designate_single_normal_owner":
                self.fp["worker_authority"] = "b" * 64
            if name == "switch_normal_traffic":
                self.fp["upstream"] = "c" * 64
                self.fp["traffic"] = "c" * 64
            if name == "switch_current_data_local_fallback":
                self.fp["upstream"] = "d" * 64
                self.fp["traffic"] = "d" * 64
                self.fp["worker_authority"] = "d" * 64
        return operation


class LocalTransitionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.metadata = json.loads((WEB_ROOT / "deployment/releases/release.json").read_text())
        fp = {key: "a" * 64 for key in ("environment", "state", "upstream", "worker_authority", "controller", "recovery", "traffic")}
        self.report = {"schema": 115, "source_sha": "a" * 40,
            "images": {"backend": "sha256:"+"a"*64, "frontend": "sha256:"+"b"*64},
            "checkpoint_digest": "c" * 64, "reconciliation_digest": "d" * 64,
            "recovery_context": "e" * 64, "migrations_executed": False,
            "unexplained_differences": 0, "database_restore_on_runtime_rollback": False,
            "gates": {key: "PASS" for key in GATES}}
        self.contract = LocalTransitionContract(self.report["source_sha"], self.report["images"],
            self.report["recovery_context"], self.report["checkpoint_digest"],
            self.report["reconciliation_digest"], digest(self.report), fp)
        self.ops = Operations(self.report, fp)
        self.ops.transaction_path = self.root / "transaction.json"
        self.tx = LocalProviderTransition(self.root, self.ops)
        for item in (patch("deployment.lib.provider_local_transition.os.geteuid", return_value=0),
                     patch("deployment.lib.provider_local_transition.protected", side_effect=lambda p, **kw: p)):
            item.start()
            self.addCleanup(item.stop)

    def prepared(self):
        return self.tx.prepare(self.contract, self.metadata)

    def switched(self):
        self.prepared()
        self.tx.handoff(self.contract, self.metadata)
        self.tx.switch(self.contract, self.metadata)

    def test_business_writes_stay_off_until_every_smoke_gate_passes(self):
        self.switched()
        self.assertEqual(self.ops.mode, "READ_ONLY")
        for gate in SMOKE_GATES:
            with self.subTest(gate=gate):
                self.ops.smoke[gate] = "FAIL"
                with self.assertRaisesRegex(RuntimeError, "smoke_incomplete"):
                    self.tx.finalize(self.contract, self.metadata)
                self.assertEqual(self.ops.mode, "READ_ONLY")
                self.ops.smoke[gate] = "PASS"
        state = self.tx.finalize(self.contract, self.metadata)
        self.assertEqual(state["phase"], "normal")
        self.assertTrue(state["normal_writes_ever_enabled"])
        self.assertEqual(self.ops.calls[-3:], ["retire_hosted_writers", "commit_normal_release_state", "write:NORMAL"])

    def test_all_migration_data_backup_smtp_and_security_gates_are_required(self):
        for gate in GATES:
            report = copy.deepcopy(self.report)
            report["gates"][gate] = "FAIL"
            contract = replace(self.contract, evidence_digest=digest(report))
            with self.subTest(gate=gate), self.assertRaises(RuntimeError):
                validate_evidence(contract, report)

    def test_contract_changes_require_new_bound_evidence(self):
        for field, value in (("sha", "f" * 40), ("images", {**self.contract.images, "backend": "sha256:"+"f"*64}),
                ("checkpoint_digest", "f"*64), ("reconciliation_digest", "f"*64), ("recovery_context", "f"*64)):
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                validate_evidence(replace(self.contract, **{field: value}), self.report)
        for key, value in (("migration_manifest", None), ("migration_policy", "automatic")):
            metadata = copy.deepcopy(self.metadata)
            metadata[key] = value
            with self.assertRaises(RuntimeError):
                self.contract.validate(metadata)

    def test_unexpected_production_fingerprint_stops_before_mutation(self):
        self.ops.fp["environment"] = "f" * 64
        with self.assertRaisesRegex(RuntimeError, "production_changed"):
            self.prepared()
        self.assertEqual(self.ops.calls, ["verify_immutable_inputs"])

    def test_authorization_is_required_for_every_operation(self):
        self.ops.authorized = False
        for operation in ("prepare", "handoff", "switch", "finalize", "rollback"):
            with self.subTest(operation=operation), self.assertRaisesRegex(RuntimeError, "authorization"):
                getattr(self.tx, operation)(self.contract, self.metadata)

    def test_handoff_precedes_switch_and_requires_all_other_workers_off(self):
        self.prepared()
        with self.assertRaisesRegex(RuntimeError, "phase_or_binding"):
            self.tx.switch(self.contract, self.metadata)
        self.tx.handoff(self.contract, self.metadata)
        starts = [x for x in self.ops.calls if x == "start_and_verify_worker"]
        self.assertEqual(len(starts), 3)
        self.tx.switch(self.contract, self.metadata)
        self.assertLess(self.ops.calls.index("designate_single_normal_owner"), self.ops.calls.index("switch_normal_traffic"))

    def test_failed_worker_activation_stops_consumers_and_retains_fence(self):
        self.prepared()
        with patch.object(self.ops, "start_and_verify_worker", side_effect=RuntimeError("unhealthy")):
            with self.assertRaisesRegex(RuntimeError, "unhealthy"):
                self.tx.handoff(self.contract, self.metadata)
        self.assertEqual(self.ops.mode, "READ_ONLY")
        self.assertIn("inhibit_all_workers", self.ops.calls)
        self.assertEqual(json.loads(self.tx.path.read_text())["phase"], "rollback_required")

    def test_interrupted_traffic_switch_uses_local_runtime_only_rollback(self):
        self.prepared()
        self.tx.handoff(self.contract, self.metadata)
        with patch.object(self.ops, "switch_normal_traffic", side_effect=RuntimeError("interrupted")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                self.tx.switch(self.contract, self.metadata)
        self.tx.rollback(self.contract, self.metadata)
        self.assertEqual(self.ops.mode, "READ_ONLY")
        self.assertIn("switch_current_data_local_fallback", self.ops.calls)
        self.assertFalse(any("restore" in call for call in self.ops.calls))

    def test_after_writes_rollback_fences_and_preserves_current_database(self):
        self.switched()
        self.tx.finalize(self.contract, self.metadata)
        state = self.tx.rollback(self.contract, self.metadata)
        self.assertTrue(state["normal_writes_ever_enabled"])
        self.assertEqual(self.ops.mode, "READ_ONLY")
        self.assertEqual(state["phase"], "local_rollback_active")
        self.assertFalse(any("restore" in call for call in self.ops.calls))

    def test_runtime_rollback_does_not_depend_on_deployment_checkpoint_freshness(self):
        self.switched()
        self.tx.finalize(self.contract, self.metadata)
        with patch.object(self.ops, "verify_immutable_inputs", side_effect=RuntimeError("expired")):
            self.tx.rollback(self.contract, self.metadata)
        self.assertIn("verify_runtime_rollback_inputs", self.ops.calls)
        self.assertEqual(self.ops.mode, "READ_ONLY")

    def test_smtp_preparation_cannot_authorize_normal_activation(self):
        report = copy.deepcopy(self.report)
        report["gates"]["auth_smtp"] = "PENDING"
        contract = replace(self.contract, evidence_digest=digest(report))
        validate_preparation_evidence(contract, report)
        with self.assertRaisesRegex(RuntimeError, "mandatory_gate_incomplete"):
            validate_evidence(contract, report)
        for gate in GATES - {"auth_smtp"}:
            altered = copy.deepcopy(report)
            altered["gates"][gate] = "FAIL"
            with self.subTest(gate=gate), self.assertRaises(RuntimeError):
                validate_preparation_evidence(replace(contract, evidence_digest=digest(altered)), altered)
        with self.assertRaisesRegex(RuntimeError, "evidence_changed"):
            validate_preparation_evidence(replace(contract, evidence_digest="f" * 64), report)

    def test_auth_mail_configuration_is_gmail_starttls_and_exact_public_callbacks_only(self):
        values = {key: "synthetic-fixture" for key in SMTP_KEYS}
        values.update(SMTP_HOST="smtp.gmail.com", SMTP_PORT="587", SMTP_USER="fixture@example.invalid",
                      SMTP_ADMIN_EMAIL="fixture@example.invalid")
        result = configuration_changes(values)
        self.assertEqual(result["API_EXTERNAL_URL"], "https://api.madarportal.com")
        self.assertEqual({key: result[key] for key in CALLBACKS}, CALLBACKS)
        for key, bad in (("SMTP_PORT", "465"), ("SMTP_HOST", "other.example.invalid"),
                         ("SMTP_PASS", ""), ("SMTP_ADMIN_EMAIL", "other@example.invalid"),
                         ("SMTP_SENDER_NAME", "invalid\nvalue")):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                configuration_changes({**values, key: bad})

    def test_worker_repair_cannot_start_consumers_during_recovery_or_preparation(self):
        self.prepared()
        with self.assertRaisesRegex(RuntimeError, "phase_or_binding"):
            self.tx.restart_worker(self.contract, self.metadata, "notification")
        self.assertNotIn("restart_existing_worker", self.ops.calls)

    def test_normal_worker_repair_is_authorized_exact_owner_only_without_promotion(self):
        self.switched()
        self.tx.finalize(self.contract, self.metadata)
        before = dict(self.ops.fp)
        self.tx.restart_worker(self.contract, self.metadata, "notification")
        self.assertIn("restart_existing_worker", self.ops.calls)
        self.assertEqual(self.ops.fp, before)
        self.ops.authorized = False
        with self.assertRaisesRegex(RuntimeError, "authorization"):
            self.tx.restart_worker(self.contract, self.metadata, "calendar-sync")
        with self.assertRaisesRegex(RuntimeError, "worker_kind"):
            self.tx.restart_worker(self.contract, self.metadata, "unknown")
