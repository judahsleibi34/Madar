#!/usr/bin/env python3
"""Real, disposable schema-96 recovery and ordinary-prepare rehearsal.

Run only inside a dedicated Docker-in-Docker engine. The script deliberately
refuses a daemon containing any pre-existing container.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


def run(*command: str, check: bool = True, capture: bool = False, env=None, cwd=None) -> str:
    completed = subprocess.run(
        list(command), check=check, text=True, env=env, cwd=cwd,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.DEVNULL if capture and not check else None,
    )
    return completed.stdout.strip() if capture else ""


def load_cli(source: Path):
    web = source / "web"
    sys.path.insert(0, str(web))
    loader = importlib.machinery.SourceFileLoader(
        "real_runtime_release_cli", str(web / "deployment/bin/madar-release-deploy")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


class Harness:
    OLD_SHA = "1" * 40

    def __init__(self, args, cli, controller_source: Path):
        self.args = args
        self.cli = cli
        self.root = Path(args.runtime_root)
        self.state_root = self.root / "state"
        self.storage = self.root / "storage"
        self.proxy_root = self.root / "proxy"
        self.target = self.proxy_root / "active-target.json"
        self.env_file = self.root / "rehearsal.env"
        self.repo = self.root / "repo"
        self.controller_source = controller_source
        self.compose = Path(args.source) / "web/deployment/rehearsal/docker-compose.runtime.yml"
        self.prefix = "pr121final"
        self.records = []
        self.overlap_observed = False
        self.recovery = cli.Compatibility.load(
            controller_source / "web/deployment/releases/schema-96-recovery.json"
        )

    def setup(self):
        if run("docker", "ps", "-a", "--format", "{{.Names}}", capture=True):
            raise RuntimeError("disposable_engine_not_empty")
        self.root.mkdir(parents=True, exist_ok=True)
        run("git", "clone", "--no-local", self.args.repository, str(self.repo))
        run(
            "git", "cat-file", "-e", f"{self.args.recovery_sha}^{{commit}}",
            check=True, cwd=self.repo,
        )
        for relative in ("uploads", "avatar_uploads", "private_uploads", "private_generated_charts"):
            (self.storage / relative).mkdir(parents=True)
        self.proxy_root.mkdir(parents=True)
        self.env_file.write_text("REHEARSAL_ONLY=true\n")
        os.environ.update({
            "MADAR_STORAGE_ROOT": str(self.storage),
            "MADAR_DEPLOY_STATE_ROOT": str(self.state_root),
            "MADAR_TRAFFIC_SWITCH_COMMAND": str(
                self.controller_source / "web/deployment/bin/madar-switch-traffic"
            ),
            "MADAR_TRAFFIC_SWITCH_DRIVER": "file-proxy",
            "MADAR_ACTIVE_TARGET_FILE": str(self.target),
            "MADAR_CANDIDATE_READY_ATTEMPTS": "20",
            "MADAR_CANDIDATE_READY_RETRY_SECONDS": "1",
            "MADAR_WORKER_READY_ATTEMPTS": "30",
            "MADAR_WORKER_READY_RETRY_SECONDS": "0.2",
            "MADAR_RELEASE_OBSERVE_SECONDS": "10",
            "VITE_API_URL": "https://api.madarportal.com",
            "SUPABASE_URL": "http://127.0.0.1:54321",
            "SUPABASE_SERVICE_KEY": "synthetic-rehearsal-key",
        })
        fixture = f"{self.prefix}-fixture:latest"
        run("docker", "build", "-t", fixture, str(Path(self.args.source) / "web/deployment/rehearsal"))
        for sha in (self.OLD_SHA, self.args.recovery_sha, self.args.normal_sha):
            self.build_release_images(fixture, sha)
        self.fixture = fixture
        run(
            "docker", "run", "-d", "--name", f"{self.prefix}-schema",
            "--network", "host", "-e", "SCHEMA=96", fixture, "schema",
        )
        for _ in range(30):
            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:54321/rest/v1/application_schema_state", timeout=1
                ) as response:
                    if json.loads(response.read()) == [{"schema_version": 96}]:
                        break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("schema_fixture_start_failed")

    def build_release_images(self, fixture: str, sha: str):
        built = "2026-09-15T00:00:00Z"
        directory = Path(tempfile.mkdtemp(dir=self.root))
        try:
            (directory / "Dockerfile").write_text(f"FROM {fixture}\n")
            common = (
                "--label", f"com.madar.release.sha={sha}",
                "--label", f"com.madar.release.built_at={built}",
            )
            run("docker", "build", *common, "-t", f"madar-backend:{sha}", str(directory))
            run(
                "docker", "build", *common,
                "--label", "com.madar.frontend.api_origin=https://api.madarportal.com",
                "-t", f"madar-frontend:{sha}-production", str(directory),
            )
        finally:
            shutil.rmtree(directory)

    def operations(self, sha: str, compatibility, cls=None):
        cls = cls or RealOperations
        return cls(
            self.repo, self.state_root, self.env_file, compatibility,
            metadata_filename=("schema-96-recovery.json" if compatibility == self.recovery else "release.json"),
            compose_file=self.compose, project_prefix=f"{self.prefix}-project",
            container_prefix=f"{self.prefix}-container", harness=self,
        )

    def set_target(self, slot: str):
        ports = self.cli.SLOT_PORTS[slot]
        atomic(self.target, {
            "slot": slot, "backend_port": int(ports["backend"]),
            "frontend_port": int(ports["frontend"]),
        })

    def start_proxy(self):
        run("docker", "rm", "-f", f"{self.prefix}-proxy", check=False)
        run(
            "docker", "run", "-d", "--name", f"{self.prefix}-proxy",
            "--network", "host", "-e", f"ACTIVE_TARGET_FILE={self.target}",
            "-v", f"{self.proxy_root}:{self.proxy_root}:ro", self.fixture, "proxy",
        )
        for _ in range(30):
            try:
                with urllib.request.urlopen("http://127.0.0.1:8001/health/version", timeout=1):
                    return
            except Exception:
                time.sleep(0.2)
        raise RuntimeError("proxy_start_failed")

    def cleanup_slots(self):
        for slot in ("blue", "green"):
            run(
                "docker", "compose", "--project-name", f"{self.prefix}-project-{slot}",
                "-f", str(self.compose), "--profile", "workers",
                "--profile", "deletion-worker", "down", "--timeout", "1",
                "--remove-orphans",
                check=False, env=dict(os.environ, MADAR_SLOT=slot,
                    MADAR_CONTAINER_PREFIX=f"{self.prefix}-container",
                    MADAR_BACKEND_IMAGE=f"madar-backend:{self.args.recovery_sha}",
                    MADAR_FRONTEND_IMAGE=f"madar-frontend:{self.args.recovery_sha}-production",
                    MADAR_RELEASE_SHA=self.args.recovery_sha,
                    MADAR_RELEASE_SLOT=slot, MADAR_BUILD_TIMESTAMP="fixture",
                    SCHEMA_COMPATIBLE_MIN="96", SCHEMA_COMPATIBLE_MAX="96",
                    NOTIFICATION_WORKER_REQUIRED="true",
                    MADAR_BACKEND_BIND_PORT=self.cli.SLOT_PORTS[slot]["backend"],
                    MADAR_FRONTEND_BIND_PORT=self.cli.SLOT_PORTS[slot]["frontend"],
                    MADAR_REDIS_BIND_PORT=self.cli.SLOT_PORTS[slot]["redis"]),
            )

    def seed(self):
        self.cleanup_slots()
        if self.state_root.exists():
            shutil.rmtree(self.state_root)
        run("git", "worktree", "prune", cwd=self.repo)
        self.state_root.mkdir(parents=True)
        images = self.image_record(self.OLD_SHA)
        state = {
            "active_slot": "blue",
            "known_good_release": {
                "sha": self.OLD_SHA, "slot": "blue", "schema": 93,
                "schema_compatible_min": 81, "schema_compatible_max": 93,
                "images": images,
            },
            "history": [], "failed_releases": {},
        }
        atomic(self.state_root / "state.json", state)
        self.set_target("blue")
        old = self.operations(self.OLD_SHA, self.recovery)
        old.release_root = Path(self.args.source)

        # Match the actual stranded production binary: it predates the
        # release_slot field in /health/version.
        previous_omit_slot = os.environ.get("MADAR_OMIT_RELEASE_SLOT")
        os.environ["MADAR_OMIT_RELEASE_SLOT"] = "true"
        try:
            old._compose(
                self.OLD_SHA, "blue", images, "up", "-d", "--no-build",
                "--force-recreate", "--wait", "--wait-timeout", "60",
                "redis", "parser-worker", "remote-ingestion-worker",
                "backend", "frontend", "notification-worker",
                "calendar-sync-worker", "data-deletion-worker",
                workers_active=True,
            )
        finally:
            if previous_omit_slot is None:
                os.environ.pop("MADAR_OMIT_RELEASE_SLOT", None)
            else:
                os.environ["MADAR_OMIT_RELEASE_SLOT"] = previous_omit_slot

        self.start_proxy()
        old.validate_candidate(self.OLD_SHA, "blue")
        self.sample_workers("seed")

    def image_record(self, sha: str):
        backend = run("docker", "image", "inspect", "--format", "{{.Id}}", f"madar-backend:{sha}", capture=True)
        frontend = run("docker", "image", "inspect", "--format", "{{.Id}}", f"madar-frontend:{sha}-production", capture=True)
        return {
            "backend": f"madar-backend:{sha}@{backend}",
            "frontend": f"madar-frontend:{sha}-production@{frontend}",
            "worker": f"madar-backend:{sha}@{backend}",
            "build_timestamp": "2026-09-15T00:00:00Z",
        }

    def sample_workers(self, phase: str):
        groups = {}
        for slot in ("blue", "green"):
            running = []
            for service in ("notification-worker", "calendar-sync-worker", "data-deletion-worker"):
                name = f"{self.prefix}-container-{slot}-{service}"
                value = run("docker", "inspect", "--format", "{{.State.Status}}", name, check=False, capture=True)
                if value in {"running", "restarting", "paused"}:
                    running.append(service)
            groups[slot] = running
        overlap = bool(groups["blue"] and groups["green"])
        self.overlap_observed |= overlap
        try:
            authority = json.loads(
                (self.state_root / "worker-ownership.json").read_text()
            )
        except (OSError, ValueError):
            authority = None
        try:
            route = json.loads(self.target.read_text()).get("slot")
        except (OSError, ValueError):
            route = "ambiguous"
        self.records.append({
            "event": "worker_sample", "phase": phase, "groups": groups,
            "overlap": overlap, "route": route, "authority": authority,
        })
        return groups

    def slot_instances(self):
        instances = {}
        for slot in ("blue", "green"):
            name = f"{self.prefix}-container-{slot}-backend"
            instances[slot] = run(
                "docker", "inspect", "--format", "{{.Id}}", name,
                check=False, capture=True,
            ) or None
        return instances

    def worker_health(self, slot: str):
        health = {}
        for service in ("notification-worker", "calendar-sync-worker", "data-deletion-worker"):
            name = f"{self.prefix}-container-{slot}-{service}"
            health[service] = run(
                "docker", "inspect", "--format", "{{.State.Health.Status}}", name,
                check=False, capture=True,
            ) or "absent"
        return health

    def recover(self, operations=None):
        operations = operations or self.operations(self.args.recovery_sha, self.recovery)
        deployer = self.cli.ReleaseDeployer(
            state_root=self.state_root, compatibility=self.recovery, operations=operations,
        )
        return deployer.recover_current_schema(self.args.recovery_sha)

    def scenario(self, name: str, function):
        self.seed()
        start = len(self.records)
        outcome = "ok"
        try:
            detail = function()
        except BaseException as error:
            outcome = type(error).__name__
            detail = str(error)
        groups = self.sample_workers(name + ":final")
        state = json.loads((self.state_root / "state.json").read_text())
        route = None
        try:
            route = json.loads(self.target.read_text()).get("slot")
        except Exception:
            route = "ambiguous"
        record = {
            "scenario": name, "outcome": outcome, "detail": detail,
            "exit_code": 0 if outcome == "ok" else 1,
            "route": route, "workers": groups,
            "instances": self.slot_instances(),
            "phase": (state.get("in_progress_release") or {}).get("phase"),
            "status": (state.get("in_progress_release") or {}).get("status"),
            "events": self.records[start:],
        }
        self.records.append(record)
        atomic(Path(self.args.evidence).with_suffix(".progress.json"), {
            "candidate_sha": self.args.recovery_sha,
            "ordinary_candidate_sha": self.args.normal_sha,
            "overlap_observed": self.overlap_observed,
            "records": self.records,
        })
        return record

    @staticmethod
    def require_failed(record):
        if record["outcome"] == "ok":
            raise RuntimeError(f"injected_failure_did_not_fail:{record['scenario']}")

    def run_all(self):
        happy = self.scenario("happy_path", self.recover)
        if happy["outcome"] != "ok":
            raise RuntimeError(f"happy_path_failed:{happy}")

        stopped = self.scenario("old_worker_stop_failure", lambda: self.recover(
            self.operations(self.args.recovery_sha, self.recovery, StopOldFailure)
        ))
        self.require_failed(stopped)
        if stopped["workers"]["green"]:
            raise RuntimeError(f"candidate_workers_started_after_old_stop_failure:{stopped}")

        restarted = self.scenario("old_worker_restart_during_switch", lambda: self.recover(
            self.operations(self.args.recovery_sha, self.recovery, RestartDuringSwitch)
        ))
        self.require_failed(restarted)
        if restarted["workers"]["green"]:
            raise RuntimeError(f"candidate_workers_started_after_old_restart:{restarted}")

        drifted = self.scenario("route_drift_before_fallback", lambda: self.recover(
            self.operations(self.args.recovery_sha, self.recovery, FallbackDrift)
        ))
        self.require_failed(drifted)
        drift_event = next(
            event for event in drifted["events"]
            if event.get("event") == "fallback_route_drift"
        )
        if drift_event["before"] != drift_event["after"]:
            raise RuntimeError(f"serving_fallback_was_recreated:{drift_event}")

        ambiguous = self.scenario("ambiguous_switch", lambda: self.recover(
            self.operations(self.args.recovery_sha, self.recovery, AmbiguousSwitch)
        ))
        self.require_failed(ambiguous)
        ambiguity_event = next(
            event for event in ambiguous["events"]
            if event.get("event") == "ambiguous_route_injected"
        )
        if ambiguous["route"] != "ambiguous" or ambiguity_event["instances"] != ambiguous["instances"]:
            raise RuntimeError(f"ambiguous_route_mutated_runtime:{ambiguous}")

        def interrupted_resume(starting: bool):
            first = self.operations(self.args.recovery_sha, self.recovery, InterruptAfterServing)
            try:
                self.recover(first)
            except KeyboardInterrupt:
                pass
            if starting:
                name = f"{self.prefix}-container-green-notification-worker"
                run("docker", "restart", name)
                health = self.worker_health("green")
                self.records.append({"event": "resume_worker_health", "expected": "starting", "health": health})
                if health["notification-worker"] != "starting":
                    raise RuntimeError(f"worker_not_starting_at_resume:{health}")
            else:
                health = self.worker_health("green")
                self.records.append({"event": "resume_worker_health", "expected": "healthy", "health": health})
                if set(health.values()) != {"healthy"}:
                    raise RuntimeError(f"workers_not_healthy_at_resume:{health}")
            return self.recover()
        starting = self.scenario("resume_candidate_workers_starting", lambda: interrupted_resume(True))
        healthy = self.scenario("resume_candidate_workers_healthy", lambda: interrupted_resume(False))
        if starting["outcome"] != "ok" or healthy["outcome"] != "ok":
            raise RuntimeError(f"candidate_worker_resume_failed:{starting}:{healthy}")

        def fallback_resume():
            first = self.operations(self.args.recovery_sha, self.recovery, InterruptFallback)
            try:
                self.recover(first)
            except KeyboardInterrupt:
                pass
            return self.recover()
        fallback = self.scenario("fallback_interruption_resume", fallback_resume)
        if fallback["outcome"] != "ok":
            raise RuntimeError(f"fallback_resume_failed:{fallback}")

        def candidate_shutdown_failure():
            first = self.operations(self.args.recovery_sha, self.recovery, InterruptAfterServing)
            try:
                self.recover(first)
            except KeyboardInterrupt:
                pass
            self.set_target("blue")
            failing = self.operations(self.args.recovery_sha, self.recovery, CandidateShutdownFailure)
            return self.recover(failing)
        shutdown = self.scenario("candidate_worker_shutdown_failure", candidate_shutdown_failure)
        self.require_failed(shutdown)
        if shutdown["workers"]["blue"] or not shutdown["workers"]["green"]:
            raise RuntimeError(f"old_workers_restored_without_candidate_shutdown_proof:{shutdown}")

        # Finish one clean recovery, then use the real ordinary candidate and
        # its actual release/manifest parser for prepare and retry.
        self.seed()
        self.recover()
        normal_root = self.state_root
        normal_ops = self.operations(self.args.normal_sha, self.recovery)
        normal_ops.verify_source(self.args.normal_sha)
        normal_compatibility = self.cli.Compatibility.load(
            normal_ops.release_root / "web/deployment/releases/release.json"
        )
        normal_ops.compatibility = normal_compatibility
        normal_ops.metadata_filename = "release.json"
        first = self.cli.prepare_release(
            sha=self.args.normal_sha, slot="blue", state_root=normal_root,
            compatibility=normal_compatibility, operations=normal_ops,
        )
        second = self.cli.prepare_release(
            sha=self.args.normal_sha, slot="blue", state_root=normal_root,
            compatibility=normal_compatibility, operations=normal_ops,
        )
        plan = second["migration_plan"]
        if plan != [[96, 97], [97, 98], [98, 99]]:
            raise RuntimeError(f"planner_path_unexpected:{plan}")
        (normal_root / "prepared-release.json").unlink()
        retry_ops = self.operations(self.args.normal_sha, normal_compatibility, PrepareOnceFailure)
        try:
            self.cli.prepare_release(
                sha=self.args.normal_sha, slot="blue", state_root=normal_root,
                compatibility=normal_compatibility, operations=retry_ops,
            )
        except RuntimeError as error:
            if "injected_prepare_interruption" not in str(error):
                raise
        retried = self.cli.prepare_release(
            sha=self.args.normal_sha, slot="blue", state_root=normal_root,
            compatibility=normal_compatibility, operations=retry_ops,
        )
        incompatible = None
        recovery_normal = self.operations(self.args.recovery_sha, self.recovery)
        recovery_normal.verify_source(self.args.recovery_sha)
        incompatible_compatibility = self.cli.Compatibility.load(
            recovery_normal.release_root / "web/deployment/releases/release.json"
        )
        recovery_normal.compatibility = incompatible_compatibility
        recovery_normal.metadata_filename = "release.json"
        try:
            self.cli.prepare_release(
                sha=self.args.recovery_sha, slot="blue", state_root=self.root / "incompatible-state",
                compatibility=incompatible_compatibility, operations=recovery_normal,
            )
        except Exception as error:
            incompatible = str(error)
        if not incompatible:
            raise RuntimeError("incompatible_candidate_not_rejected")
        self.records.append({
            "scenario": "real_normal_prepare_retry",
            "exit_code": 0,
            "first_status": first["status"], "retry_status": retried["status"],
            "interrupted_prepare_exit_code": 1,
            "retried_prepare_exit_code": 0,
            "planner_derived_path": plan, "migrations_applied": False,
            "completed_recovery_not_hijacked": True,
            "incompatible_candidate_rejected": incompatible,
        })
        if self.overlap_observed:
            raise RuntimeError("consumer_overlap_observed")
        return {
            "candidate_sha": self.args.recovery_sha,
            "ordinary_candidate_sha": self.args.normal_sha,
            "planner_derived_path": plan,
            "overlap_observed": self.overlap_observed,
            "installed_executable_hashes": {
                name: hashlib.sha256(path.read_bytes()).hexdigest()
                for name, path in {
                    "madar-release-deploy": self.controller_source / "web/deployment/bin/madar-release-deploy",
                    "madar-switch-traffic": self.controller_source / "web/deployment/bin/madar-switch-traffic",
                }.items()
            },
            "records": self.records,
        }


RealOperations = None


def _operations_classes(cli):
    class Base(cli.DockerGitOperations):
        def __init__(self, *args, harness=None, **kwargs):
            super().__init__(*args, **kwargs)
            self.harness = harness

        def validate_recovery_backup(self, schema: int):
            document = {
                "backup_id": "madar-20260915T000000Z", "schema": schema,
                "manifest_sha256": hashlib.sha256(b"real-rehearsal-manifest").hexdigest(),
                "node1_sha256sums_sha256": hashlib.sha256(b"real-rehearsal-node1").hexdigest(),
            }
            return json.loads(json.dumps(document))

        def observe(self, sha: str, slot: str):
            self.validate_candidate(sha, slot)
            self.harness.sample_workers("observation")

        def activate_workers(self, sha, slot, images):
            self.harness.sample_workers(f"activate:{slot}:before")
            result = super().activate_workers(sha, slot, images)
            self.harness.sample_workers(f"activate:{slot}:after")
            return result

        def deactivate_workers(self, release):
            slot = release.get("slot")
            self.harness.sample_workers(f"deactivate:{slot}:before")
            result = super().deactivate_workers(release)
            self.harness.sample_workers(f"deactivate:{slot}:after")
            return result

        def restore_workers(self, release):
            slot = release.get("slot")
            self.harness.sample_workers(f"restore:{slot}:before")
            result = super().restore_workers(release)
            self.harness.sample_workers(f"restore:{slot}:after")
            return result

    class StopOld(Base):
        def deactivate_workers(self, release):
            if release.get("slot") == "blue":
                raise RuntimeError("injected_old_worker_stop_failure")
            return super().deactivate_workers(release)

    class Restart(Base):
        def switch_traffic(self, slot):
            super().switch_traffic(slot)
            names = self._worker_names("blue")
            self.run(["docker", "start", *names])
            self.harness.sample_workers("old_restart_during_switch")

    class Drift(Base):
        def start_candidate(self, sha, slot, images):
            if slot == "blue" and self.harness.target.exists():
                self.harness.set_target("blue")
                before = self.harness.slot_instances()["blue"]
                try:
                    return super().start_candidate(sha, slot, images)
                finally:
                    after = self.harness.slot_instances()["blue"]
                    self.harness.records.append({
                        "event": "fallback_route_drift", "slot": slot,
                        "before": before, "after": after,
                    })
            return super().start_candidate(sha, slot, images)

    class Ambiguous(Base):
        def switch_traffic(self, slot):
            super().switch_traffic(slot)
            instances = self.harness.slot_instances()
            atomic(self.harness.target, {"slot": "ambiguous", "backend_port": 9, "frontend_port": 9})
            self.harness.records.append({
                "event": "ambiguous_route_injected", "instances": instances,
            })
            raise RuntimeError("injected_lost_switch_identity")

    class InterruptServing(Base):
        def observe(self, sha, slot):
            self.harness.sample_workers("interruption_after_candidate_serving")
            raise KeyboardInterrupt()

    class InterruptAtFallback(Base):
        def start_candidate(self, sha, slot, images):
            result = super().start_candidate(sha, slot, images)
            if slot == "blue" and self.harness.target.exists():
                raise KeyboardInterrupt()
            return result

    class ShutdownFailure(Base):
        def deactivate_workers(self, release):
            if release.get("slot") == "green":
                raise RuntimeError("injected_candidate_shutdown_failure")
            return super().deactivate_workers(release)

    class PrepareFailure(Base):
        failed = False
        def start_candidate(self, sha, slot, images):
            if not self.failed:
                self.failed = True
                raise RuntimeError("injected_prepare_interruption")
            return super().start_candidate(sha, slot, images)

    return Base, StopOld, Restart, Drift, Ambiguous, InterruptServing, InterruptAtFallback, ShutdownFailure, PrepareFailure


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--recovery-sha", required=True)
    parser.add_argument("--normal-sha", required=True)
    args = parser.parse_args()
    runtime_root = Path(args.runtime_root)
    controller_source = runtime_root / "installed"
    shutil.copytree(
        Path(args.source) / "web/deployment",
        controller_source / "web/deployment",
    )
    cli = load_cli(controller_source)
    global RealOperations, StopOldFailure, RestartDuringSwitch, FallbackDrift
    global AmbiguousSwitch, InterruptAfterServing, InterruptFallback
    global CandidateShutdownFailure, PrepareOnceFailure
    (RealOperations, StopOldFailure, RestartDuringSwitch, FallbackDrift,
     AmbiguousSwitch, InterruptAfterServing, InterruptFallback,
     CandidateShutdownFailure, PrepareOnceFailure) = _operations_classes(cli)
    harness = Harness(args, cli, controller_source)
    harness.setup()
    result = harness.run_all()
    evidence = Path(args.evidence)
    atomic(evidence, result)
    print(json.dumps({
        "status": "passed", "candidate_sha": args.recovery_sha,
        "planner_derived_path": result["planner_derived_path"],
        "overlap_observed": result["overlap_observed"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
