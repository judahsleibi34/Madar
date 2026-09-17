"""Retained installed-copy failure/resume matrix for schema-96 recovery."""

from __future__ import annotations

import hashlib
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


WEB_ROOT = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT") or Path(__file__).resolve().parents[2])
OLD_SHA = os.getenv("MADAR_MATRIX_OLD_SHA", "1" * 40)
CANDIDATE_SHA = os.getenv("MADAR_MATRIX_CANDIDATE_SHA", "a" * 40)
NORMAL_SHA = os.getenv("MADAR_MATRIX_NORMAL_SHA", "b" * 40)


def atomic(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


class MatrixOperations:
    def __init__(self, actual_path: Path, *, fault: str = ""):
        self.actual_path = actual_path
        self.fault = fault
        self.calls: list[str] = []
        self.validations = 0
        self.starts = 0

    def actual(self) -> dict:
        return json.loads(self.actual_path.read_text(encoding="utf-8"))

    def save(self, value: dict) -> None:
        if value["workers"]["blue"] != "inactive" and value["workers"]["green"] != "inactive":
            value["overlap_observed"] = True
        atomic(self.actual_path, value)

    def verify_source(self, sha):
        self.calls.append("verify_source")
        if sha not in {CANDIDATE_SHA, NORMAL_SHA}: raise RuntimeError("candidate_identity_mismatch")

    def build(self, _sha, _slot):
        self.calls.append("build")
        return {name: f"{name}@sha256:{index * 64}" for name, index in (("backend", "4"), ("frontend", "5"), ("worker", "6"))}

    def schema_version(self): return 96
    def preflight(self, _sha, _slot, _images, schema):
        if schema != 96: raise RuntimeError("schema_drift")

    def start_candidate(self, sha, slot, _images):
        self.calls.append(f"start:{slot}")
        self.starts += 1
        if self.fault == "candidate_start" and self.starts == 1: raise RuntimeError("injected_candidate_start")
        if self.fault == "normal_prepare_once" and sha == NORMAL_SHA and self.starts == 1: raise RuntimeError("injected_normal_prepare")
        if self.fault == "fallback_interrupt" and sha == CANDIDATE_SHA and self.starts == 2:
            self.fault = ""
            raise KeyboardInterrupt()
        value = self.actual(); value["slots"][slot] = sha; self.save(value)

    def validate_candidate(self, sha, slot):
        self.validations += 1
        value = self.actual()
        if self.fault == "traffic_drift" and self.validations == 2:
            value["traffic"] = slot; self.save(value)
        if value["slots"].get(slot) != sha: raise RuntimeError("candidate_invalid")

    def validate_rollback_target(self, _release, _schema): return {"compatible_min": 96, "compatible_max": 96}

    def activate_workers(self, _sha, slot, _images):
        self.calls.append(f"activate:{slot}")
        value = self.actual(); value["workers"][slot] = "active"; self.save(value)

    def deactivate_workers(self, release):
        slot = release["slot"]; self.calls.append(f"deactivate:{slot}")
        if self.fault == "old_stop" and slot == "blue": raise RuntimeError("injected_old_stop")
        if self.fault == "candidate_stop" and slot == "green": raise RuntimeError("injected_candidate_stop")
        value = self.actual(); value["workers"][slot] = "inactive"; self.save(value)

    def restore_workers(self, release):
        slot = release["slot"]; self.calls.append(f"restore:{slot}")
        value = self.actual(); value["workers"][slot] = "active"; self.save(value)

    def worker_ownership(self, retained, candidate):
        value = self.actual(); old = value["workers"][retained["slot"]]; new = value["workers"][candidate["slot"]]
        if old != "inactive" and new != "inactive": return "overlap"
        if old == "active": return "old"
        if old == "starting": return "old_starting"
        if new == "active": return "candidate"
        if new == "starting": return "candidate_starting"
        return "none"

    def switch_traffic(self, slot):
        self.calls.append(f"switch:{slot}")
        value = self.actual()
        if self.fault == "ambiguous_switch":
            value["traffic"] = "unknown"; self.save(value); raise RuntimeError("injected_switch_ack_loss")
        value["traffic"] = slot; self.save(value)

    def observe(self, _sha, _slot):
        if self.fault == "post_switch_interrupt": self.fault = ""; raise KeyboardInterrupt()

    def stop_candidate(self, slot, *, expected_serving=None):
        self.calls.append(f"stop:{slot}")
        value = self.actual()
        if expected_serving is not None:
            serving = self.resolve_serving_slot(expected_serving)
            if serving is None or serving == slot: raise RuntimeError("unsafe_candidate_cleanup")
        value["slots"].pop(slot, None); value["workers"][slot] = "inactive"; self.save(value)

    def current_traffic_slot(self): return self.actual()["traffic"]
    def resolve_serving_slot(self, expected):
        value = self.actual(); slot = value["traffic"]
        return slot if slot in expected and expected[slot] == value["slots"].get(slot) else None
    def validate_recovery_backup(self, schema):
        return {"backup_id": "disposable-schema96", "schema": schema, "manifest_sha256": "7" * 64, "node1_sha256s_sha256": "8" * 64}


def seed(root: Path, *, traffic="blue", workers=None, in_progress=None) -> tuple[Path, Path]:
    state_root = root / "state"; state_root.mkdir(parents=True)
    actual_path = root / "actual.json"
    old = {"sha": OLD_SHA, "slot": "blue", "schema": 93, "images": {}, "schema_compatible_min": 81, "schema_compatible_max": 93}
    state = {"active_slot": "blue", "known_good_release": old, "history": [], "failed_releases": {}}
    if in_progress is not None: state["in_progress_release"] = in_progress
    atomic(state_root / "state.json", state)
    slots = {"blue": OLD_SHA}
    if in_progress is not None:
        slots["green"] = CANDIDATE_SHA
    atomic(actual_path, {"traffic": traffic, "slots": slots, "workers": workers or {"blue": "active", "green": "inactive"}, "overlap_observed": False})
    return state_root, actual_path


def interrupted_state(worker_owner="none") -> dict:
    old = {"sha": OLD_SHA, "slot": "blue", "schema": 93, "images": {}}
    return {"release_sha": CANDIDATE_SHA, "candidate_slot": "green", "previous_traffic_target": "blue", "previous_known_good_release": old, "schema_recovery": True, "schema": 96, "images": {}, "worker_owner": worker_owner, "recovery_id": hashlib.sha256(f"{CANDIDATE_SHA}:96:{OLD_SHA}".encode()).hexdigest(), "status": "running", "phase": "worker_cutover"}


def snapshot(scenario, expected, injected, state_root, actual_path, result, resume=""):
    state = json.loads((state_root / "state.json").read_text()); actual = json.loads(actual_path.read_text())
    progress = state.get("in_progress_release") or {}
    latest = (state.get("history") or [{}])[-1]
    return {"scenario_id": scenario, "initial_state": "schema96_old_runtime", "recovery_id": progress.get("recovery_id") or next((x.get("recovery_id") for x in reversed(state.get("history", [])) if x.get("schema_recovery")), None), "expected_invariant": expected, "injected_failure": injected or "none", "controller_result": result, "actual_routing_state": actual["traffic"], "actual_old_worker_state": actual["workers"]["blue"], "actual_candidate_worker_state": actual["workers"]["green"], "durable_phase": progress.get("phase") or latest.get("phase", "complete"), "durable_status": progress.get("status") or latest.get("status", "unknown"), "resume_command": resume or "not_required", "final_active_slot": state.get("active_slot"), "fallback_slot": (state.get("compatible_fallback_release") or {}).get("slot"), "overlap_observed": actual["overlap_observed"]}


def run_matrix(installed: Path) -> list[dict]:
    sys.path.insert(0, str(installed))
    from deployment.lib.release_deployer import Compatibility, ReleaseDeployer
    loader = importlib.machinery.SourceFileLoader("installed_matrix_cli", str(installed / "deployment/bin/madar-release-deploy"))
    spec = importlib.util.spec_from_loader(loader.name, loader); cli = importlib.util.module_from_spec(spec); loader.exec_module(cli)
    recovery = Compatibility(96, 96, 96, "none", 96, 96)
    records = []

    def execute(identifier, fault="", *, traffic="blue", workers=None, progress=None, resume=False):
        with tempfile.TemporaryDirectory() as directory:
            state_root, actual_path = seed(Path(directory), traffic=traffic, workers=workers, in_progress=progress)
            ops = MatrixOperations(actual_path, fault=fault); outcome = "success"
            try: ReleaseDeployer(state_root=state_root, compatibility=recovery, operations=ops).recover_current_schema(CANDIDATE_SHA)
            except KeyboardInterrupt: outcome = "interrupted"
            except RuntimeError as error: outcome = str(error)
            if resume:
                try: ReleaseDeployer(state_root=state_root, compatibility=recovery, operations=MatrixOperations(actual_path)).recover_current_schema(CANDIDATE_SHA); outcome += ";resume_success"
                except RuntimeError as error: outcome += ";resume:" + str(error)
            records.append(snapshot(identifier, "no_worker_overlap_and_serving_runtime_preserved", fault, state_root, actual_path, outcome, "installed recovery rerun" if resume else ""))
            return state_root, actual_path

    execute("A", resume=False)
    execute("B", "old_stop")
    execute("C", "candidate_start")
    execute("D", "candidate_stop", workers={"blue": "inactive", "green": "active"}, progress=interrupted_state("candidate"))
    execute("E", "traffic_drift")
    execute("F", "ambiguous_switch")
    execute("G", "post_switch_interrupt", resume=True)
    execute("H", "fallback_interrupt", resume=True)
    execute("I", traffic="green", workers={"blue": "inactive", "green": "starting"}, progress=interrupted_state("none"), resume=True)
    execute("J", traffic="green", workers={"blue": "inactive", "green": "active"}, progress=interrupted_state("candidate"), resume=True)
    execute("K", "fallback_interrupt", resume=True)

    for identifier, fault in (("L", ""), ("M", "normal_prepare_once")):
        with tempfile.TemporaryDirectory() as directory:
            state_root, actual_path = seed(Path(directory)); ops = MatrixOperations(actual_path)
            ReleaseDeployer(state_root=state_root, compatibility=recovery, operations=ops).recover_current_schema(CANDIDATE_SHA)
            prepare_ops = MatrixOperations(actual_path, fault=fault); outcome = "prepare_success"
            normal = Compatibility(96, 99, 99, "expand-only", 96, 99)
            try: cli.prepare_release(sha=NORMAL_SHA, slot="blue", state_root=state_root, compatibility=normal, operations=prepare_ops)
            except RuntimeError as error:
                outcome = "interrupted:" + str(error)
                cli.prepare_release(sha=NORMAL_SHA, slot="blue", state_root=state_root, compatibility=normal, operations=MatrixOperations(actual_path))
                outcome += ";retry_success"
            records.append(snapshot(identifier, "ordinary_96_to_99_prepare_is_idempotent_and_applies_no_migrations", fault, state_root, actual_path, outcome, "ordinary prepare retry" if fault else ""))
    digest = hashlib.sha256()
    for relative in (
        "deployment/bin/madar-release-deploy",
        "deployment/lib/release_deployer.py",
        "deployment/lib/control_plane_upgrade.py",
    ):
        digest.update(relative.encode())
        digest.update((installed / relative).read_bytes())
    for record in records:
        record.update(
            candidate_sha=CANDIDATE_SHA,
            installed_controller_digest=digest.hexdigest(),
            migration_plan=[[96, 97], [97, 98], [98, 99]],
            migrations_applied=False,
        )
    return records


class InstalledFailureMatrixTests(unittest.TestCase):
    def test_installed_failure_resume_matrix(self):
        with tempfile.TemporaryDirectory() as directory:
            installed = Path(directory) / "control"
            shutil.copytree(WEB_ROOT / "deployment", installed / "deployment")
            completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--installed-matrix", str(installed)], text=True, capture_output=True, timeout=60, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        records = json.loads(completed.stdout)
        self.assertEqual([record["scenario_id"] for record in records], list("ABCDEFGHIJKLM"))
        self.assertTrue(all(not record["overlap_observed"] for record in records), records)
        by_id = {record["scenario_id"]: record for record in records}
        self.assertEqual(by_id["D"]["actual_old_worker_state"], "inactive")
        self.assertEqual(by_id["D"]["durable_status"], "operator_intervention_required")
        self.assertEqual(by_id["E"]["actual_routing_state"], "green")
        self.assertEqual(by_id["F"]["actual_routing_state"], "unknown")
        self.assertTrue(
            all("resume_success" in by_id[item]["controller_result"] for item in "GHIJK"),
            records,
        )
        self.assertEqual(by_id["L"]["controller_result"], "prepare_success")
        self.assertIn("retry_success", by_id["M"]["controller_result"])


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--installed-matrix":
        payload = json.dumps(run_matrix(Path(sys.argv[2])), indent=2, sort_keys=True)
        evidence = os.getenv("MADAR_MATRIX_EVIDENCE", "").strip()
        if evidence:
            Path(evidence).write_text(payload + "\n", encoding="utf-8")
        print(payload)
    else:
        unittest.main()
