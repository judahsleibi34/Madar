"""Adversarial recovery trust, worker inhibition and bootstrap regressions."""
import copy
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

WEB_ROOT = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB_ROOT))
from deployment.lib.provider_recovery import reject_ordinary_operation
from deployment.lib.provider_recovery_runtime import ProductionRecoveryOperations, RecoveryPaths, digest, protected
from deployment.lib.provider_recovery_bootstrap import TrustedRecoveryBootstrap
import test_provider_recovery_controller as fixtures


class InfrastructureTests(unittest.TestCase):
    def setUp(self):
        fixtures.RecoveryControllerTests.setUp(self)
    def test_controller_transition_does_not_waive_other_provenance(self):
        evidence = copy.deepcopy(self.origin)
        evidence["installed_sha"] = self.contract.sha
        evidence["production_fingerprints"]["controller"] = "9"*64
        receipt = {"contract_digest": digest(self.contract.__dict__),
                   "old_sha": self.contract.installed_sha, "new_sha": self.contract.sha,
                   "old_controller_digest": self.contract.production_fingerprints["controller"],
                   "new_controller_digest": "9"*64}
        evidence["controller_transition"] = receipt
        self.contract.validate_origin(evidence)
        for name in receipt:
            damaged = copy.deepcopy(evidence)
            damaged["controller_transition"][name] = "0"*64
            with self.subTest(receipt=name), self.assertRaises(RuntimeError):
                self.contract.validate_origin(damaged)
        for name in ("environment", "state", "upstream", "worker_authority"):
            damaged = copy.deepcopy(evidence)
            damaged["production_fingerprints"][name] = "0"*64
            with self.subTest(provenance=name), self.assertRaises(RuntimeError):
                self.contract.validate_origin(damaged)

    def test_dangling_recovery_interlock_still_blocks_normal_deployment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "provider-recovery.json").symlink_to(root / "missing")
            with self.assertRaises(RuntimeError):
                reject_ordinary_operation(root)

    def test_both_slot_worker_sets_have_restart_disabled_before_stop(self):
        ops = ProductionRecoveryOperations.__new__(ProductionRecoveryOperations)
        ops.paths = replace(RecoveryPaths(), production_prefix="fixture-only", prefix="fixture-recovery")
        ops.trace = []
        records = {name: {"State": {"Running": True}, "HostConfig": {"RestartPolicy": {"Name": "unless-stopped"}}}
                   for name in ops.worker_names()}
        calls = []
        def command(args, **kwargs):
            calls.append(args)
            if args[1] == "update": records[args[-1]]["HostConfig"]["RestartPolicy"]["Name"] = "no"
            elif args[1] == "stop": records[args[-1]]["State"]["Running"] = False
            elif args[1] == "ps": return "\n".join(records)
            return ""
        ops.inspect = lambda name: records[name]
        ops.command = command
        ops.inhibit_all_workers()
        self.assertEqual(len(records), 6)
        for name in records:
            self.assertLess(calls.index(["docker", "update", "--restart=no", name]),
                            calls.index(["docker", "stop", name]))
        records[next(iter(records))]["State"]["Running"] = True
        with self.assertRaises(RuntimeError): ops.require_all_workers_off()

    def test_bootstrap_cannot_quiesce_or_install_before_all_guards_pass(self):
        from contextlib import nullcontext
        test = self
        class Operations:
            def __init__(self): self.calls = []
            def upgrade_lock(self): return nullcontext()
            def deploy_lock(self): return nullcontext()
            def verify_trusted_bootstrap(self): self.calls.append("trusted")
            def origin_evidence(self): return test.origin
            def target_evidence(self): return test.target
            def stage_candidate(self, sha): self.calls.append("stage"); return Path("candidate"),Path("backup")
            def static_preflight(self, path): self.calls.append("preflight")
            def installer_dry_run(self, path, backup): self.calls.append("dry_run")
            def require_fresh_installation(self): self.calls.append("fresh")
            def record_installation(self, contract): self.calls.append("installed_witness")
            def issue_authorization(self, contract): self.calls.append("authorization")
            def begin_installation(self, contract): self.calls.append("install-interlock")
            def quiesce_normal_automation(self): self.calls.append("quiesce")
            def installer_apply(self, *args): self.calls.append("install")
            def verify_installed_controller(self, sha): self.calls.append("verify_installed")
            def record_controller_transition(self, contract): self.calls.append("receipt")
        ops = Operations()
        bootstrap = TrustedRecoveryBootstrap(ops)
        with self.assertRaises(RuntimeError): bootstrap.install(self.contract, self.metadata, "0"*64)
        self.assertEqual(ops.calls, [])
        bad = copy.deepcopy(self.target)
        bad["checks"]["checkpoint_valid"] = False
        with patch.object(ops, "target_evidence", return_value=bad), self.assertRaises(RuntimeError):
            bootstrap.install(self.contract, self.metadata, digest(self.contract.__dict__))
        self.assertNotIn("quiesce", ops.calls)
        ops.calls.clear()
        with patch("deployment.lib.provider_recovery_phases.require_preparation_evidence"), patch("deployment.lib.provider_recovery_bootstrap.os.geteuid", return_value=0):
            result = bootstrap.install(self.contract, self.metadata, digest(self.contract.__dict__))
        self.assertEqual(ops.calls, ["trusted", "stage", "preflight", "dry_run", "fresh", "install-interlock", "quiesce", "install", "verify_installed", "receipt", "installed_witness", "authorization"])
        self.assertFalse(result["activated"])

    def test_unprotected_or_symlinked_checkpoint_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "checkpoint.json"
            path.write_text("{}")
            alias = root / "alias.json"
            alias.symlink_to(path)
            with self.assertRaises(RuntimeError): protected(alias)
            with self.assertRaises(RuntimeError): protected(path, private=True)

    def test_private_runtime_endpoint_requires_an_internal_bridge(self):
        ops=ProductionRecoveryOperations.__new__(ProductionRecoveryOperations)
        ops.paths=replace(RecoveryPaths(),prefix="fixture-recovery")
        ops.ports={"blue":(29101,39101)}
        ops.inspect=lambda name:{"NetworkSettings":{"Networks":{"fixture-recovery-blue-runtime":{"IPAddress":"172.30.1.2"}}}}
        ops.command=lambda args:json.dumps([{"Internal":True,"Driver":"bridge"}])
        self.assertEqual(ops.runtime_endpoint("blue","backend"),"http://172.30.1.2:8000")
        ops.command=lambda args:json.dumps([{"Internal":False,"Driver":"bridge"}])
        with self.assertRaises(RuntimeError):ops.runtime_endpoint("blue","backend")


class ReassignedRuntimeEndpointTests(unittest.TestCase):
    def test_fallback_endpoints_follow_container_roles_after_address_reassignment(self):
        ops = ProductionRecoveryOperations.__new__(ProductionRecoveryOperations)
        ops.paths = replace(RecoveryPaths(), prefix="fixture-recovery")
        ops.ports = {"local-fallback": (29401, 39401)}
        addresses = {"backend": "10.254.202.4", "frontend": "10.254.202.5"}
        def inspect(name):
            kind = name.rsplit("-", 1)[1]
            return {"NetworkSettings": {"Networks": {
                "fixture-recovery-local-fallback-runtime": {"IPAddress": addresses[kind]}}}}
        ops.inspect = inspect
        ops.command = lambda args: json.dumps([{"Internal": True, "Driver": "bridge"}])
        self.assertEqual(ops.runtime_endpoint("local-fallback", "backend"), "http://10.254.202.4:8000")
        addresses.update(backend="10.254.202.5", frontend="10.254.202.4")
        self.assertEqual(ops.runtime_endpoint("local-fallback", "backend"), "http://10.254.202.5:8000")
        self.assertEqual(ops.runtime_endpoint("local-fallback", "frontend"), "http://10.254.202.4:8080")
