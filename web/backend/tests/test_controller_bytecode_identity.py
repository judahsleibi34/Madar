"""Source-only installed-controller identity and pre-activation repair regressions."""
import hashlib
import json
import os
from pathlib import Path
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

WEB = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB))
from deployment.lib.provider_recovery_runtime import ProductionRecoveryOperations, RecoveryPaths, digest
from deployment.lib.provider_recovery_bootstrap import ProductionBootstrapOperations
import test_provider_recovery_controller as fixtures


class ControllerBytecodeIdentityTests(unittest.TestCase):
    def tree(self, root):
        target = root / "web/deployment"
        shutil.copytree(WEB / "deployment/lib", target / "lib",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        return target

    def fingerprint(self, controller, root):
        state = root / "state"; state.mkdir(exist_ok=True)
        for name in ("state.json", "worker-ownership.json"):
            (state / name).write_text("{}")
        env = root / "configuration.env"; env.write_text("test=true")
        upstream = root / "upstream"; upstream.write_text("test")
        ops = object.__new__(ProductionRecoveryOperations)
        ops.paths = RecoveryPaths(controller=controller, state=state,
                                  production_env=env, upstream=upstream)
        return ops.fingerprints()

    def test_direct_execution_and_repeated_imports_keep_all_file_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); controller = self.tree(root)
            before = self.fingerprint(controller, root)
            for _ in range(2):
                for entry in ("provider_recovery_entry.py", "provider_recovery_prepare_entry.py",
                              "provider_local_transition_entry.py"):
                    r = subprocess.run([sys.executable, str(controller / "lib" / entry), "--help"],
                                       capture_output=True, text=True)
                    self.assertEqual(r.returncode, 0, r.stderr)
                code = "import sys;sys.path.insert(0," + repr(str(root / "web")) + ");import deployment.lib.provider_recovery_runtime;import deployment.lib.provider_recovery_bootstrap"
                r = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(self.fingerprint(controller, root), before)
                self.assertFalse(list(controller.rglob("*.pyc")))

    def test_cached_substitute_is_rejected_before_any_deployment_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); controller = self.tree(root); marker = root / "executed"
            evil = root / "evil.py"
            evil.write_text("from pathlib import Path;Path(" + repr(str(marker)) + ").touch()")
            cache = controller / "lib/__pycache__"; cache.mkdir()
            py_compile.compile(str(evil), cfile=str(cache / ("__init__." + sys.implementation.cache_tag + ".pyc")), doraise=True)
            r = subprocess.run([sys.executable, str(controller / "lib/provider_recovery_entry.py"), "--help"], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("protected_controller_bytecode_present", r.stderr)
            self.assertFalse(marker.exists())

    def test_no_file_type_is_excluded_from_controller_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); controller = self.tree(root)
            before = self.fingerprint(controller, root)["controller"]
            for name in ("lib/provider_recovery_runtime.py", "installation-manifest.json", "authorization.json", "configuration.conf", "lib/__pycache__/arbitrary.json", "lib/__pycache__/unverified.pyc"):
                p = controller / name; p.parent.mkdir(exist_ok=True)
                original = p.read_bytes() if p.exists() else None
                p.write_bytes(b"tampered")
                self.assertNotEqual(self.fingerprint(controller, root)["controller"], before)
                if original is None: p.unlink()
                else: p.write_bytes(original)

    def test_repair_requires_exact_prior_context_and_cannot_refresh_normally(self):
        fixtures.RecoveryControllerTests.setUp(self)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                ops = object.__new__(ProductionBootstrapOperations)
                ops.runtime = Path(tmp)
                ops.receipt = Path(tmp) / "transition.json"
                ops.recovery = Mock(contract=self.contract)
                (ops.runtime / "authorized.credential").write_text("{}")
                with self.assertRaisesRegex(RuntimeError, "existing_authorization"):
                    ops.require_fresh_installation()
                ops.recovery.contract = replace(self.contract, repair_context_digest="9"*64)
                with patch.object(ops, "require_unused_installation_repair", side_effect=RuntimeError("prior_rejected")) as check:
                    with self.assertRaisesRegex(RuntimeError, "prior_rejected"):
                        ops.require_fresh_installation()
                    check.assert_called_once()
        finally:
            self.doCleanups()

    def test_repair_does_not_waive_runtime_fallback_or_origin_checks(self):
        fixtures.RecoveryControllerTests.setUp(self)
        try:
            c = replace(self.contract, repair_context_digest="9"*64)
            c.validate(self.metadata)
            c.validate_origin(self.origin)
            changed = dict(self.origin, production_fingerprints=dict(self.origin["production_fingerprints"], controller="0"*64))
            with self.assertRaisesRegex(RuntimeError, "origin_changed"):
                c.validate_origin(changed)
            target = dict(self.target, checks=dict(self.target["checks"], rollback_live_local_compatible=False))
            with self.assertRaises(RuntimeError): c.validate_target(target)
        finally:
            self.doCleanups()
