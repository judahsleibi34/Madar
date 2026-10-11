"""Admission is a new credential-bound operation, never a NORMAL flag bypass."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

WEB = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB))
from deployment.lib import completed_normal_admission as m
from deployment.lib import control_plane_upgrade_authorization as auth
from deployment.lib import active_recovery_inputs as inputs
from deployment.lib.provider_recovery import reject_ordinary_operation
from deployment.lib.active_recovery_resumption import ROOT


def fixture_contract():
    root = ROOT / ("a" * 64)
    return {
        "version": 1, "operation": m.OPERATION,
        "source_roles": {"application_sha": "a" * 40, "controller_sha": "b" * 40,
            "completion_root": str(root), "original_plan_sha256": root.name, "completion_sha256": "1" * 64},
        "origin": {"slot": "blue", "images": {"backend": "sha256:" + "1" * 64, "frontend": "sha256:" + "2" * 64}, "worker_generation": "3" * 64, "write_contract_digest":"3"*64},
        "candidate": {"slot": "green", "source_sha": "c" * 40, "controller_sha": "d" * 40,
            "controller_tree_sha256": "4" * 64, "compatible_min": 115, "compatible_max": 136,
            "redis_image":"sha256:"+"5"*64,
            "images": {"backend": "sha256:" + "5" * 64, "frontend": "sha256:" + "6" * 64}},
        "historical_files": {str(root / name): "7" * 64 for name in m.HISTORICAL_NAMES},
        "database": {"container_id": "8" * 64, "image": "sha256:" + "9" * 64, "system_identifier": "731", "schema": 115, "spec_sha256":"f"*64,
            "network_name":"madar-local-supabase_default","network_id":"1"*64,"backup_configuration_sha256":"2"*64},
        "migration_manifest_sha256": "a" * 64, "rehearsal_sha256": "b" * 64, "plan_sha256": "c" * 64,
        "provider_record_sha256": hashlib.sha256(b'{"phase":"local_rollback_active"}').hexdigest(),
        "customer_table_roots_sha256":"d"*64,"customer_identity_roots_sha256":"e"*64,
        "resources":{slot:{'subnets':dict(zip(('default','parser','remote_internal','remote_egress'),
                ('10.249.'+str(offset+i)+'.0/24' for i in range(4)))),'retired_port_declarations':{}}
            for slot,offset in (('blue',0),('green',4))},
    }


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.contract = fixture_contract()
        self.state = self.root / "state"; self.state.mkdir()
        (self.state / "provider-recovery.json").write_bytes(b'{"phase":"local_rollback_active"}')
        known = {"sha": "a" * 40, "slot": "blue", "schema": 115, "images": self.contract["origin"]["images"]}
        (self.state / "state.json").write_text(json.dumps({"active_slot": "blue", "known_good_release": known}))
        self.admissions = self.root / "admissions"
        saved = self.admissions / m.digest(self.contract); saved.mkdir(parents=True)
        receipt = {"version": 1, "operation": m.OPERATION, "contract": self.contract,
            "provider_record_sha256": self.contract["provider_record_sha256"], "observed_at": "2026-10-11T00:00:00Z",
            "database_restored": False, "historical_authorization_reused": False}
        (saved / "admission.json").write_text(json.dumps(receipt))
        self.receipt=receipt
        self.interlock = self.root / "interlock.json"
        credential_dir = self.root / "credentials"; credential_dir.mkdir()
        self.credential = credential_dir / "madar-control-plane-upgrade"
        token = "fresh-test-token-not-a-production-credential"
        self.authorization = {"approved_sha": "d" * 40, "operation": m.OPERATION, "schema": 115,
            "context_sha256": m.digest(self.contract), "rehearsal_sha256": self.contract["rehearsal_sha256"], "token": token,
            "completed_normal_admission":receipt}
        self.interlock_data = {k: v for k, v in self.authorization.items() if k != "token"}
        self.interlock_data.update(status="authorized_cycle", authorization_sha256=hashlib.sha256(token.encode()).hexdigest())
        self.interlock_data['admission_sha256']=m.digest(receipt)
        self.save_auth()
        self.controller = self.root / "CONTROL_PLANE_SOURCE_SHA"; self.controller.write_text("d" * 40)
        # These fixture readers stand in for canonical protected paths. The
        # credential implementation itself executes, including file UID/mode
        # checks, without accepting a mock PASS packet or mocked authorization.
        patches = [
            patch.object(auth, "UPGRADE_INTERLOCK", self.interlock),
            patch.object(m, "require_upgrade_authorization", lambda sha, **kw: auth.require_upgrade_authorization(sha, interlock=self.interlock, **kw)),
            patch("deployment.lib.provider_recovery_runtime.protected", lambda p, **kw: Path(p)),
            patch("deployment.lib.provider_recovery_runtime.readonly_configuration", lambda p, **kw: Path(p)),
            patch.object(inputs, "INPUTS", {"controller": self.controller}),
            patch.object(inputs, "controller_tree_digest", lambda: "4" * 64),
            patch.dict(os.environ, {"CREDENTIALS_DIRECTORY": str(credential_dir)}),
        ]
        # Owner verification is performed against the fixture UID; tests also
        # run as root in the isolated CI image where that UID is genuinely root.
        if os.geteuid() != 0:
            original_stat = Path.stat
            interlock = self.interlock
            def fixture_stat(path, *args, **kwargs):
                result = original_stat(path, *args, **kwargs)
                if path == interlock:
                    fields = list(result); fields[4] = 0
                    return os.stat_result(fields)
                return result
            patches.append(patch.object(Path, "stat", fixture_stat))
        for p in patches:
            p.start(); self.addCleanup(p.stop)

    def save_auth(self):
        self.interlock.write_text(json.dumps(self.interlock_data)); self.interlock.chmod(0o644)
        self.credential.write_text(json.dumps(self.authorization)); self.credential.chmod(0o600)

    def call(self, sha="c" * 40):
        return m.require_admission(self.state, sha, admissions=self.admissions)

    def test_valid_exact_fresh_scope_preserves_both_source_roles_and_history(self):
        before = (self.state / "provider-recovery.json").read_bytes()
        self.assertEqual(self.call(), self.contract)
        self.assertNotEqual(self.call()["candidate"]["source_sha"], self.call()["candidate"]["controller_sha"])
        self.assertEqual((self.state / "provider-recovery.json").read_bytes(), before)

    def test_no_credential_or_old_completion_is_not_admission(self):
        self.credential.unlink()
        with self.assertRaisesRegex(RuntimeError, "credential_witness_missing"): self.call()

    def test_wrong_token_operation_image_source_and_rehearsal_reject(self):
        for field, value in (("token", "wrong"), ("operation", "release"), ("schema", 136), ("context_sha256", "e" * 64), ("rehearsal_sha256", "f" * 64)):
            with self.subTest(field=field):
                original = dict(self.authorization)
                self.authorization[field] = value; self.save_auth()
                with self.assertRaisesRegex(RuntimeError, "exclusive_interlock"): self.call()
                self.authorization = original; self.save_auth()
        with self.assertRaisesRegex(RuntimeError, "binding_changed"): self.call("e" * 40)

    def test_consumed_status_cannot_reuse_a_valid_token(self):
        self.interlock_data["status"] = "complete"; self.save_auth()
        with self.assertRaisesRegex(RuntimeError, "rehearsal_changed"): self.call()

    def test_edited_provider_and_installed_controller_fail_closed(self):
        (self.state / "provider-recovery.json").write_text('{"phase":"normal"}')
        with self.assertRaisesRegex(RuntimeError, "provider_record_changed"): self.call()
        (self.state / "provider-recovery.json").write_bytes(b'{"phase":"local_rollback_active"}')
        self.controller.write_text("e" * 40)
        with self.assertRaisesRegex(RuntimeError, "installed_controller_changed"): self.call()

    def test_schema_advance_rejects_old115_application_but_admits_bound_bridge(self):
        state = json.loads((self.state / "state.json").read_text()); state["known_good_release"]["schema"] = 116
        (self.state / "state.json").write_text(json.dumps(state))
        with self.assertRaisesRegex(RuntimeError, "release_changed"): self.call()
        state.update(active_slot="green", known_good_release={"sha": "c" * 40, "slot": "green", "schema": 136,
            "images": {k: f"accepted@{v}" for k,v in self.contract["candidate"]["images"].items()}})
        (self.state / "state.json").write_text(json.dumps(state))
        self.assertEqual(self.call(), self.contract)
        state["known_good_release"]["images"]["backend"] = "accepted@sha256:" + "e" * 64
        (self.state / "state.json").write_text(json.dumps(state))
        with self.assertRaisesRegex(RuntimeError, "release_changed"): self.call()

    def test_unknown_pending_generation_rejected(self):
        state = json.loads((self.state / "state.json").read_text()); state["in_progress_release"] = {"release_sha": "e" * 40, "candidate_slot": "green"}
        (self.state / "state.json").write_text(json.dumps(state))
        with self.assertRaisesRegex(RuntimeError, "pending_release_changed"): self.call()

    def test_admission_contract_rejects_unbound_history_and_widened_schema(self):
        for mutation in (lambda v: v["historical_files"].clear(), lambda v: v["candidate"].update(compatible_max=137),
                         lambda v: v["database"].update(schema=136), lambda v: v["source_roles"].update(completion_root="/tmp/agent-pass")):
            value = copy.deepcopy(self.contract); mutation(value)
            with self.assertRaises(RuntimeError): m.validate_contract(value)

    def test_default_guard_still_rejects_without_fresh_interlock(self):
        self.interlock.unlink()
        with self.assertRaisesRegex(RuntimeError, "requires_separate_operator_exit"): reject_ordinary_operation(self.state)

    def test_interlock_permissions_are_enforced_by_actual_validator(self):
        self.interlock.chmod(0o666)
        with self.assertRaisesRegex(RuntimeError, "interlock_invalid"): self.call()

    def test_child_witness_cannot_be_replaced_by_agent_written_metadata(self):
        value=copy.deepcopy(self.authorization['completed_normal_admission'])
        value['observed_at']='invented'
        self.authorization['completed_normal_admission']=value;self.save_auth()
        with self.assertRaisesRegex(RuntimeError,'credential_witness_changed'):self.call()


if __name__ == "__main__": unittest.main()
