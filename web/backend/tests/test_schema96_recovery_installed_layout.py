"""Disposable installed-layout rehearsal for the schema-96 recovery state machine."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


WEB_ROOT = Path(
    os.getenv("MADAR_TEST_REPOSITORY_ROOT")
    or Path(__file__).resolve().parents[2]
).resolve()


class InstalledLayoutRecoveryTests(unittest.TestCase):
    def test_installed_layout_interruption_resume_and_next_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = root / "control"
            shutil.copytree(WEB_ROOT / "deployment", control / "deployment")
            shutil.copytree(WEB_ROOT / "scripts", control / "deployment/scripts")
            runtime = root / "runtime"
            candidate = os.getenv("MADAR_REHEARSAL_CANDIDATE_SHA", "a" * 40)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--installed-harness",
                    str(control),
                    str(runtime),
                    candidate,
                ],
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["schema"], 96)
        self.assertEqual(result["recovery_status"], "known_good")
        self.assertEqual(result["active_slot"], "green")
        self.assertEqual(result["fallback_slot"], "blue")
        self.assertEqual(result["fallback_sha"], candidate)
        self.assertEqual(result["next_release_status"], "known_good")
        self.assertTrue(result["installed_helpers"])
        self.assertTrue(result["interruption_resumed"])
        self.assertFalse(result["worker_overlap"])


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    os.replace(temporary, path)


def _run_installed_harness(control: Path, runtime: Path, candidate: str) -> int:
    sys.path.insert(0, str(control))
    from deployment.lib.release_deployer import Compatibility, ReleaseDeployer

    cli_path = control / "deployment/bin/madar-release-deploy"
    loader = importlib.machinery.SourceFileLoader("installed_release_cli", str(cli_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    cli = importlib.util.module_from_spec(spec)
    loader.exec_module(cli)
    helper_root = cli.DockerGitOperations.recovery_helper_root()
    installed_helpers = all(
        (helper_root / name).is_file()
        for name in ("backup_support.py", "replicate_latest_node1.py")
    )

    runtime.mkdir()
    state_root = runtime / "release-state"
    state_root.mkdir()
    old_sha = "1" * 40
    _atomic_json(state_root / "state.json", {
        "active_slot": "blue",
        "known_good_release": {
            "sha": old_sha,
            "slot": "blue",
            "schema": 93,
            "images": {
                "backend": "old@sha256:" + "1" * 64,
                "frontend": "old@sha256:" + "2" * 64,
                "worker": "old@sha256:" + "3" * 64,
            },
        },
        "history": [],
        "failed_releases": {},
    })
    _atomic_json(runtime / "actual.json", {
        "schema": 96,
        "traffic": "blue",
        "slots": {"blue": old_sha},
        "workers": {"blue": True, "green": False},
        "worker_overlap": False,
    })
    (runtime / "backup-receipt.json").write_text(json.dumps({
        "backup_id": "madar-20260914T021837Z",
        "schema": 96,
        "local_verified": True,
        "node1_verified": True,
    }), encoding="utf-8")

    class Operations:
        def __init__(self, *, interrupt=False):
            self.interrupt = interrupt

        def actual(self):
            return json.loads((runtime / "actual.json").read_text(encoding="utf-8"))

        def save(self, value):
            value["worker_overlap"] = value["worker_overlap"] or all(
                value["workers"].values()
            )
            _atomic_json(runtime / "actual.json", value)

        def verify_source(self, sha):
            if sha not in {candidate, "b" * 40}:
                raise RuntimeError("candidate_identity_mismatch")

        def build(self, sha, _slot):
            return {
                "backend": f"backend@sha256:{'4' * 64}",
                "frontend": f"frontend@sha256:{'5' * 64}",
                "worker": f"worker@sha256:{'6' * 64}",
                "build_timestamp": "2026-09-14T00:00:00Z",
            }

        def schema_version(self): return int(self.actual()["schema"])
        def preflight(self, _sha, _slot, _images, schema):
            if schema != 96: raise RuntimeError("schema_drift")
        def start_candidate(self, sha, slot, _images):
            value = self.actual(); value["slots"][slot] = sha; value["workers"][slot] = False; self.save(value)
        def validate_candidate(self, sha, slot):
            if self.actual()["slots"].get(slot) != sha: raise RuntimeError("candidate_invalid")
        def validate_rollback_target(self, release, schema):
            minimum = int(release.get("schema_compatible_min", schema))
            maximum = int(release.get("schema_compatible_max", schema))
            if not minimum <= schema <= maximum: raise RuntimeError("fallback_incompatible")
            return {"compatible_min": minimum, "compatible_max": maximum}
        def activate_workers(self, _sha, slot, _images):
            value = self.actual()
            if any(active for other, active in value["workers"].items() if other != slot):
                raise RuntimeError("consumer_overlap")
            value["workers"][slot] = True; self.save(value)
        def deactivate_workers(self, release):
            value = self.actual(); value["workers"][release["slot"]] = False; self.save(value)
        def restore_workers(self, release):
            value = self.actual()
            slot = release["slot"]
            if any(active for other, active in value["workers"].items() if other != slot):
                raise RuntimeError("consumer_overlap")
            value["workers"][slot] = True; self.save(value)
        def worker_ownership(self, retained, candidate):
            value = self.actual()
            old = bool(value["workers"].get(retained["slot"]))
            new = bool(value["workers"].get(candidate["slot"]))
            if old and new: return "overlap"
            if old: return "old"
            if new: return "candidate"
            return "none"
        def switch_traffic(self, slot):
            value = self.actual(); value["traffic"] = slot; self.save(value)
        def observe(self, _sha, _slot):
            if self.interrupt:
                self.interrupt = False
                raise KeyboardInterrupt()
        def stop_candidate(self, slot, *, expected_serving=None):
            value = self.actual()
            if expected_serving is not None and (
                value["traffic"] == slot
                or expected_serving.get(value["traffic"])
                != value["slots"].get(value["traffic"])
            ):
                raise RuntimeError("cannot_stop_unverified_or_serving_slot")
            if value["traffic"] == slot: raise RuntimeError("cannot_stop_serving_slot")
            value["slots"].pop(slot, None); value["workers"][slot] = False; self.save(value)
        def current_traffic_slot(self): return str(self.actual()["traffic"])
        def resolve_serving_slot(self, expected):
            value = self.actual(); slot = value["traffic"]
            return slot if expected.get(slot) == value["slots"].get(slot) else None
        def validate_recovery_backup(self, schema):
            receipt = json.loads((runtime / "backup-receipt.json").read_text())
            if not (receipt["local_verified"] and receipt["node1_verified"] and receipt["schema"] == schema):
                raise RuntimeError("backup_gate_failed")
            return {
                "backup_id": receipt["backup_id"], "schema": schema,
                "manifest_sha256": "7" * 64,
                "node1_sha256sums_sha256": "8" * 64,
            }

    recovery = Compatibility(96, 96, 96, "none", 96, 96)
    first = ReleaseDeployer(state_root=state_root, compatibility=recovery, operations=Operations(interrupt=True))
    try:
        first.recover_current_schema(candidate)
    except KeyboardInterrupt:
        pass
    else:
        raise RuntimeError("meaningful_interruption_not_injected")
    resumed = ReleaseDeployer(state_root=state_root, compatibility=recovery, operations=Operations())
    result = resumed.recover_current_schema(candidate)
    state = json.loads((state_root / "state.json").read_text())
    actual = json.loads((runtime / "actual.json").read_text())
    normal = ReleaseDeployer(
        state_root=state_root,
        compatibility=Compatibility(96, 99, 99, "expand-only", 96, 99),
        operations=Operations(),
    ).deploy("b" * 40)
    print(json.dumps({
        "schema": actual["schema"],
        "recovery_status": result["status"],
        "active_slot": state["active_slot"],
        "fallback_slot": state["compatible_fallback_release"]["slot"],
        "fallback_sha": state["compatible_fallback_release"]["sha"],
        "next_release_status": normal["status"],
        "installed_helpers": installed_helpers,
        "interruption_resumed": True,
        "worker_overlap": actual["worker_overlap"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--installed-harness":
        raise SystemExit(_run_installed_harness(
            Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
        ))
    unittest.main()
