"""Fixed-path privileged operations for normal local-provider graduation.

All data work must already have verified evidence. This adapter performs no SQL
writes, schema change, checkpoint restore or hosted-provider traffic operation.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import json
import ipaddress
import os
from pathlib import Path
import pwd
import time
from urllib.parse import urlsplit

from deployment.lib.environment_file import load_environment_file
from deployment.lib.provider_recovery import RecoveryContract
from deployment.lib.provider_recovery_runtime import (
    ProductionRecoveryOperations, RecoveryPaths, SERVICES, digest, file_digest, http, protected,
)
from deployment.lib.release_deployer import atomic_json
from deployment.lib.runtime_authority import load_worker_authority, runtime_mutation_lock, write_worker_authority

ROOT = Path("/var/lib/madar-control-plane/local-provider-transition")


class ProductionLocalTransitionOperations:
    def __init__(self):
        recovery = RecoveryContract(**json.loads(protected(
            Path("/var/lib/madar-control-plane/provider402/contract.json"), private=True).read_text()))
        self.recovery = ProductionRecoveryOperations(RecoveryPaths(), recovery)
        self.root = ROOT
        self.transaction_path = self.root / "transaction.json"
        self.state = self.recovery.paths.state
        self.slot = recovery.origin_slot
        self.redis_name = self.recovery.paths.prefix + "-redis"
        recovery_slot = "blue" if recovery.origin_slot == "green" else "green"
        self.redis_network = self.recovery.paths.prefix + "-" + recovery_slot + "-runtime"
        self._load_configuration(self.root / "configuration.env")

    def _load_configuration(self, configuration):
        """Shared strict local/session configuration; this grants no authority."""
        self.config = {}
        load_environment_file(protected(configuration, private=True), environ=self.config)
        if (self.config.get("SUPABASE_URL") != "http://madar-supabase:8000"
                or self.config.get("MADAR_SUPABASE_CLIENT_NETWORK") != "madar-supabase-client"
                or not all(self.config.get(key) for key in ("SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY", "CSRF_SECRET"))
                or any(".supabase.co" in value for value in self.config.values())
                or self.config.get("EMAIL_CHANNEL_ENABLED", "false") != "false"
                or self.config.get("MADAR_RECOVERY_PROFILE", "")
                or any(key.startswith(("LD_", "PYTHON", "DOCKER_", "COMPOSE_", "GIT_"))
                    or key in {"PATH", "HOME", "SHELL", "BASH_ENV", "ENV", "IFS", "CDPATH"}
                    for key in self.config)):
            raise RuntimeError("local_transition_configuration_invalid")
        for key in ("SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY", "CSRF_SECRET", "SESSION_ACTIVITY_SECRET", "PENDING_VERIFICATION_SECRET"):
            if self.config.get(key) != self.recovery.config.get(key):
                raise RuntimeError("local_transition_session_configuration_changed")
        from deployment.lib.provider_recovery_runtime import readonly_configuration
        legacy = {}
        load_environment_file(readonly_configuration(self.recovery.paths.production_env), environ=legacy)
        for key in ("CALENDAR_CREDENTIALS_SECRET", "COMMERCIAL_ENTITLEMENTS_ENFORCED"):
            if self.config.get(key) != legacy.get(key):
                raise RuntimeError("local_transition_existing_application_configuration_changed")
        self.command = self.recovery.command
        self.inspect = self.recovery.inspect

    def evidence(self):
        report = json.loads(protected(self.root / "evidence.json", private=True).read_text())
        from deployment.lib.provider_recovery_phases import ACTIVATION_REHEARSAL, ACTIVATION_RECEIPT, auth_acceptance_digest
        completed = json.loads(protected(ACTIVATION_REHEARSAL, private=True).read_text())
        if report.get("acceptance_mode", "human") != completed.get("acceptance_mode", "human"):
            raise RuntimeError("local_transition_acceptance_mode_changed")
        if report.get("acceptance_mode", "human") != "human" and report.get("auth_acceptance_digest") != auth_acceptance_digest(self.recovery.contract, self.recovery.metadata(), completed, authorized_at=json.loads(protected(ACTIVATION_RECEIPT, private=True).read_text())["authorized_at"]):
            raise RuntimeError("local_transition_acceptance_digest_changed")
        return report

    def fingerprints(self):
        result = self.recovery.fingerprints()
        for key, name in (("recovery", "provider-recovery.json"), ("traffic", "provider-recovery-traffic.json")):
            result[key] = file_digest(self.state / name)
        return result

    def require_authorization(self, contract):
        self.recovery.authorize(self.recovery.contract)
        receipt = json.loads(protected(self.root / "authorization.json", private=True).read_text())
        if receipt != {"version": 1, "operation": "normal-local-provider", "schema": 115,
                "contract_digest": digest(asdict(contract)), "evidence_digest": contract.evidence_digest}:
            raise RuntimeError("local_transition_authorization_invalid")

    def require_phase(self, contract, phases):
        self.require_authorization(contract)
        state = json.loads(protected(self.transaction_path, private=True).read_text())
        if state.get("contract_digest") != digest(asdict(contract)) or state.get("phase") not in phases:
            raise RuntimeError("local_transition_operation_phase_invalid")
        if state["phase"] in {"rollback_pending", "normal"}:
            self.verify_runtime_rollback_inputs(contract)
        else:
            self.verify_immutable_inputs(contract)
        permitted = {"handoff_pending": {"worker_authority"}, "switch_pending": {"upstream", "traffic"},
                     "resume_pending": {"environment", "state"},
                     "rollback_pending": {"worker_authority", "upstream", "recovery", "traffic"}}.get(state["phase"], set())
        current = self.fingerprints()
        if {key for key in current if current[key] != state["fingerprints"][key]} - permitted:
            raise RuntimeError("local_transition_production_changed")
        return state

    def verify_immutable_inputs(self, contract):
        self.verify_runtime_rollback_inputs(contract)
        manifest = json.loads(protected(self.root / "checkpoint" / "manifest.json", private=True).read_text())
        created = datetime.fromisoformat(manifest["created_at"])
        if created.tzinfo is None or not 0 <= (datetime.now(timezone.utc)-created).total_seconds() <= 129600:
            raise RuntimeError("local_transition_checkpoint_not_fresh")
        # Historical PASS summaries and restore_verified flags cannot prove a
        # later supplemented manifest. The execution packet's digest must be
        # independently included in a fresh authorization, never inferred from
        # the aggregate gate report. Runtime-only rollback does not restore this
        # snapshot and deliberately retains its existing integrity-only path.
        report = self.evidence()
        if digest(report) != contract.evidence_digest:
            raise RuntimeError("local_transition_evidence_binding_invalid")
        from deployment.lib.checkpoint_execution_proof import verify_checkpoint_execution
        verify_checkpoint_execution(self.root / "checkpoint", self.root / "restore-execution.json",
            approved_execution_digest=report.get("restore_execution_digest"),
            protected_file=protected, now=datetime.now(timezone.utc))

    def verify_runtime_rollback_inputs(self, contract):
        # Runtime-only rollback preserves current DB/Auth/Storage and never
        # restores this archive. Its integrity remains mandatory; its age must
        # not strand serving traffic after normal writes have been accepted.
        if (contract.sha != self.recovery.contract.sha or contract.images != self.recovery.contract.images
                or contract.recovery_context != digest(asdict(self.recovery.contract))
                or self.command(["git", "-C", str(self.recovery.paths.repository), "rev-parse", "origin/main"]) != contract.sha
                or protected(self.recovery.paths.controller / "CONTROL_PLANE_SOURCE_SHA").read_text().strip() != contract.sha):
            raise RuntimeError("local_transition_canonical_source_changed")
        for image in contract.images.values():
            labels = json.loads(self.command(["docker", "image", "inspect", image]))[0]["Config"].get("Labels", {})
            if labels.get("org.opencontainers.image.revision") != contract.sha:
                raise RuntimeError("local_transition_image_revision_changed")
        schema = self.recovery.target_sql("SELECT schema_version FROM public.application_schema_state WHERE contract_key='core';")
        if [line for line in schema.splitlines() if line not in {"BEGIN", "ROLLBACK"}] != ["115"]:
            raise RuntimeError("local_transition_schema_changed")
        network = json.loads(self.command(["docker", "network", "inspect", "madar-supabase-client"]))[0]
        if not network["Internal"] or network["Driver"] != "bridge":
            raise RuntimeError("local_transition_network_not_internal")
        for name in SERVICES:
            row = self.inspect(name)
            if not row["State"]["Running"] or row["State"].get("Health", {}).get("Status") != "healthy":
                raise RuntimeError("local_transition_native_service_unhealthy")
            if any(item["HostIp"] != "127.0.0.1" for bindings in row["NetworkSettings"]["Ports"].values() for item in bindings or []):
                raise RuntimeError("local_transition_native_public_port")
        manifest_path = protected(self.root / "checkpoint" / "manifest.json", private=True)
        if file_digest(manifest_path) != contract.checkpoint_digest:
            raise RuntimeError("local_transition_checkpoint_changed")
        manifest = json.loads(manifest_path.read_text())
        created = datetime.fromisoformat(manifest["created_at"])
        sealed = type(manifest.get("version")) is int and manifest.get("version") == 1 and manifest.get("sealed") is True
        if (created.tzinfo is None or created > datetime.now(timezone.utc)
                or manifest.get("schema") != 115
                or (not sealed and manifest.get("restore_verified") is not True)):
            raise RuntimeError("local_transition_checkpoint_unverified")
        # Sealed checkpoints never inherit a restore_verified marker. Their
        # separately retained actual restore execution is checked by the
        # forward-operation gate; runtime rollback never restores this data.
        required = {"database", "roles", "storage", "auth_metadata", "application_storage", "native_config", "production_config", "images", "controller", "schema", "ledgers"}
        if not required.issubset({item["kind"] for item in manifest["files"]}):
            raise RuntimeError("local_transition_checkpoint_incomplete")
        seen = set()
        for item in manifest["files"]:
            path = Path(item["path"])
            if path.is_absolute() or ".." in path.parts or path in seen:
                raise RuntimeError("local_transition_checkpoint_path_invalid")
            seen.add(path)
            file = protected(manifest_path.parent / path, private=True)
            if file.stat().st_size != item["size"] or file_digest(file) != item["sha256"]:
                raise RuntimeError("local_transition_checkpoint_integrity_failed")
        reconciliation = json.loads(protected(self.root / "reconciliation.json", private=True).read_text())
        if digest(reconciliation) != contract.reconciliation_digest:
            raise RuntimeError("local_transition_reconciliation_changed")
        # Existing native configuration belongs to the operator, not the root
        # controller. Its protected reconciliation attestation pins the exact
        # three inputs consumed by Compose; it is never trusted as executable
        # controller code or an authorization receipt.
        from deployment.lib.provider_recovery_runtime import readonly_configuration
        native = reconciliation.get("native_configuration_fingerprints", {})
        if set(native) != {".env", "docker-compose.yml", "docker-compose.madar-local.yml"}:
            raise RuntimeError("local_transition_native_configuration_binding_missing")
        for name, expected in native.items():
            path = readonly_configuration(Path("/opt/madar/local-supabase") / name, private=name == ".env")
            if file_digest(path) != expected:
                raise RuntimeError("local_transition_native_configuration_changed")
        from deployment.lib.provider_local_backup_configuration import verify_backup_input
        phase = None
        if self.transaction_path.exists():
            phase = json.loads(protected(self.transaction_path, private=True).read_text()).get("phase")
        verify_backup_input(self.root, reconciliation, contract, phase)

    def require_recovery_active(self, context):
        # Runtime-owned release files are untrusted until bound to the protected
        # packet and independently observed serving identity.
        state = json.loads((self.state / "provider-recovery.json").read_text())
        if state.get("context_digest") != context or state.get("phase") != "active":
            raise RuntimeError("local_transition_recovery_not_active")
        self.recovery.smoke_recovery(self.recovery.contract, state["slot"])

    def verify_local_fallback(self):
        self.recovery.validate_runtime("local-fallback")
        if json.loads((self.state / "provider-recovery-fallback.json").read_text()) != self.recovery.descriptor():
            raise RuntimeError("local_transition_fallback_changed")

    def names(self):
        return [f"madar-{slot}-{kind}-worker" for slot in ("blue", "green")
                for kind in ("notification", "calendar-sync", "data-deletion")]

    def require_all_workers_off(self):
        self.recovery.require_all_workers_off()

    def inhibit_all_workers(self):
        self.recovery.inhibit_all_workers()

    def set_write_authority(self, contract, mode):
        if mode not in {"READ_ONLY", "NORMAL"}:
            raise RuntimeError("local_transition_write_mode_invalid")
        phases = {"prepare_pending", "prepared", "handoff_pending", "workers_ready", "switch_pending",
            "serving_read_only", "rollback_required", "resume_pending", "normal", "rollback_pending"}
        state = self.require_phase(contract, {"resume_pending"} if mode == "NORMAL" else phases)
        if mode == "NORMAL":
            smoke = json.loads(protected(self.root / "final-smoke.json", private=True).read_text())
            from deployment.lib.provider_local_transition import SMOKE_GATES
            gates = smoke.get("gates", {})
            if (set(gates) != SMOKE_GATES or any(value != "PASS" for value in gates.values())
                    or state.get("final_smoke_digest") != digest(gates)
                    or smoke.get("contract_digest") != digest(asdict(contract))
                    or smoke.get("production_fingerprints") != state.get("pre_resume_fingerprints")
                    or state.get("normal_writes_ever_enabled") is not True):
                raise RuntimeError("local_transition_write_grant_smoke_invalid")
            self.require_single_owner(contract)
            self.verify_private_candidate(contract, workers_required=True)
        self._publish_write_authority(contract, mode)

    def _publish_write_authority(self, contract, mode):
        """Effect helper; callers must prove their governed grant/revocation.

        Shared permissions implement the reviewed umask correction. This is not
        an authorization entrypoint and does not consume historical PASS data.
        """
        if os.geteuid() != 0 or mode not in {"READ_ONLY", "NORMAL"}:
            raise RuntimeError("local_transition_write_publication_denied")
        directory = self.root / "write-authority"
        directory.mkdir(mode=0o755, exist_ok=True)
        if directory.is_symlink() or directory.stat().st_uid != 0 or directory.stat().st_mode & 0o022:
            raise RuntimeError("local_transition_write_directory_untrusted")
        # The root launcher deliberately uses umask 077. This non-secret,
        # read-only-mounted directory must remain traversable by the backend
        # UID; mkdir(mode=0755) alone would silently create mode 0700.
        os.chmod(directory, 0o755)
        atomic_json(directory / "authority.json", {"version": 1, "schema": 115,
            "release_sha": contract.sha, "contract_digest": digest(asdict(contract)), "mode": mode})
        os.chmod(directory / "authority.json", 0o444)

    def require_write_authority(self, contract, mode):
        value = json.loads(protected(self.root / "write-authority" / "authority.json").read_text())
        if value != {"version": 1, "schema": 115, "release_sha": contract.sha,
                "contract_digest": digest(asdict(contract)), "mode": mode}:
            raise RuntimeError("local_transition_write_authority_changed")

    def _env(self, contract, *, worker=False):
        config = dict(self.config)
        config.update({"APP_ENV": "production", "MADAR_ENV_FILE": "/tmp/no-env",
            "MADAR_ENV_OVERRIDE": "false", "MADAR_RELEASE_SHA": contract.sha,
            "MADAR_RELEASE_SLOT": self.slot, "SCHEMA_COMPATIBLE_MIN": "115", "SCHEMA_COMPATIBLE_MAX": "115",
            "SUPABASE_URL": "http://madar-supabase:8000", "MADAR_SUPABASE_CLIENT_NETWORK": "madar-supabase-client",
            "REDIS_URL": f"redis://{self.redis_name}:6379/0", "COOKIE_SECURE": "true",
            "ADMIN_MFA_LOGIN_ENFORCEMENT": "true", "RATE_LIMIT_FAIL_OPEN": "false", "RATE_LIMIT_ENABLED": "true",
            "NOTIFICATION_WORKER_ENABLED": "true", "CALENDAR_SYNC_WORKER_ENABLED": "true",
            "DATA_DELETION_WORKER_ENABLED": "true", "NOTIFICATION_WORKER_REQUIRED": "true",
            "DATA_DELETION_WORKER_REQUIRED": "true", "CALENDAR_SYNC_REQUIRED": "true",
            "NOTIFICATION_WORKER_HEALTH_HOST": "0.0.0.0", "CALENDAR_SYNC_WORKER_HEALTH_HOST": "0.0.0.0",
            "DATA_DELETION_WORKER_HEALTH_HOST": "0.0.0.0", "EMAIL_CHANNEL_ENABLED": "false",
            "NOTIFICATION_WORKER_HEALTH_URL": "http://notification-worker:8090/health",
            "CALENDAR_SYNC_WORKER_HEALTH_URL": "http://calendar-sync-worker:8091/health",
            "DATA_DELETION_WORKER_HEALTH_URL": "http://data-deletion-worker:8094/health",
            "PARSER_ISOLATED_WORKER_ENABLED": "true", "PARSER_WORKER_URL": "http://parser:8000",
            "PARSER_WORKER_HEALTH_URL": "http://parser:8000/health",
            "REMOTE_INGESTION_ENABLED": "false", "ALLOW_REMOTE_DATASET_URLS": "false", "AI_ALLOW_LOCAL_EXEC": "false",
            "PUBLIC_UPLOADS_DIR": "/app/public/uploads", "DATA_UPLOAD_DIR": "/app/private_uploads",
            "PRIVATE_CHARTS_DIR": "/app/private_generated_charts", "BACKUP_FRESHNESS_REQUIRED": "true"})
        for key in ("MADAR_RECOVERY_PROFILE", "MADAR_BUSINESS_WRITE_AUTHORITY", "MADAR_BUSINESS_WRITE_CONTRACT"):
            config.pop(key, None)
        config.update({"MADAR_BUSINESS_WRITE_AUTHORITY": "/run/madar/business-write-authority/authority.json",
            "MADAR_BUSINESS_WRITE_CONTRACT": digest(asdict(contract))})
        return config

    def _create_application(self, contract, name, alias, *, worker=None, network=None, loopback_port=None):
        network = network or f"madar-{self.slot}-local-transition"
        if loopback_port is not None and (worker is not None or loopback_port != {"blue": 8101, "green": 8201}[self.slot]):
            raise RuntimeError("local_transition_backend_port_invalid")
        cfg = self._env(contract, worker=worker is not None)
        args = ["docker", "create", "--name", name, "--network", network, "--network-alias", alias,
                "--restart", "no", "--log-driver", "none", "--label", "com.madar.local-transition="+digest(asdict(contract))]
        if loopback_port is not None:
            args += ["--publish", f"127.0.0.1:{loopback_port}:8000"]
        args += ["--mount", f"type=bind,src={self.root}/write-authority,dst=/run/madar/business-write-authority,readonly"]
        if worker is not None:
            port = {"notification": 8090, "calendar-sync": 8091, "data-deletion": 8094}[worker]
            args += ["--health-cmd", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:"+str(port)+"/health',timeout=3)\"",
                     "--health-interval", "10s", "--health-timeout", "5s", "--health-retries", "3"]
        for relative, destination in (("uploads", "/app/public/uploads"), ("private_uploads", "/app/private_uploads"),
                                      ("private_generated_charts", "/app/private_generated_charts")):
            source = Path("/var/lib/madar/storage") / relative
            if source.is_symlink() or not source.is_dir():
                raise RuntimeError("local_transition_application_storage_missing")
            args += ["--mount", f"type=bind,src={source},dst={destination}"]
        args += ["--mount", self._backup_marker_mount(cfg)]
        for key in cfg:
            args += ["--env", key]
        args += [contract.images["backend"]]
        if worker:
            args += ["python", "-m", "workers."+worker.replace("-", "_")+"_worker"]
        self.command(args, env={**cfg, "PATH": "/usr/bin:/bin"})
        self.command(["docker", "network", "connect", "madar-supabase-client", name])
        # Attach only the newly created, exact-source application process.
        # Existing recovery Redis/fallback topology is never changed here.
        self.command(["docker", "network", "connect", self.redis_network, name])

    def _backup_marker_mount(self, cfg):
        marker = protected(Path(cfg["BACKUP_FRESHNESS_MARKER"]))
        return f"type=bind,src={marker},dst={marker},readonly"

    def require_emergency_routing_handoff_complete(self):
        upstream = protected(self.recovery.paths.upstream).read_text()
        if any(f"127.0.0.1:{port}" in upstream for port in (29401, 39401, 39402)):
            raise RuntimeError("local_transition_emergency_handoff_required")

    def prepare_normal_candidate(self, contract):
        self.require_phase(contract, {"prepare_pending"})
        # The legacy slot is not serving: recovery traffic must remain on the
        # separate, privately rehearsed runtime. Preserve old containers/images
        # instead of deleting them, and durably inhibit every archived consumer.
        self.require_recovery_active(contract.recovery_context)
        self.require_all_workers_off()
        redis = self.inspect(self.redis_name)
        redis_network = json.loads(self.command(["docker", "network", "inspect", self.redis_network]))[0]
        if (not redis["State"]["Running"] or redis["Config"].get("Labels", {}).get("com.madar.recovery.profile") != "provider402-signin"
                or self.redis_network not in redis["NetworkSettings"]["Networks"]
                or not redis_network["Internal"] or redis_network["Driver"] != "bridge"
                or not any(item["Type"] == "volume" and item["Destination"] == "/data" for item in redis["Mounts"])):
            raise RuntimeError("local_transition_recovery_redis_unavailable")
        suffix = digest(asdict(contract))[:12]
        for kind in ("backend", "frontend", "redis", "notification-worker", "calendar-sync-worker", "data-deletion-worker"):
            name = f"madar-{self.slot}-{kind}"
            self.command(["docker", "update", "--restart=no", name])
            self.command(["docker", "stop", name])
            self.command(["docker", "rename", name, name+"-legacy-"+suffix])
        network = f"madar-{self.slot}-local-transition"
        # Normal workers need outbound HTTPS. No host port is published and
        # the separate Supabase client bridge remains internal and unchanged.
        ids = self.command(["docker", "network", "ls", "-q"]).splitlines()
        existing = json.loads(self.command(["docker", "network", "inspect", *ids]))
        occupied = [ipaddress.ip_network(item["Subnet"]) for row in existing
                    for item in row.get("IPAM", {}).get("Config") or [] if item.get("Subnet")]
        routes = json.loads(self.command(["ip", "-j", "route"]))
        occupied += [ipaddress.ip_network(row["dst"], strict=False) for row in routes
                     if row.get("dst") not in {None, "default"}]
        choices = [subnet for subnet in ipaddress.ip_network("10.253.0.0/16").subnets(new_prefix=24)
                   if not any(subnet.overlaps(other) for other in occupied if other.version == 4)]
        if not choices:
            raise RuntimeError("local_transition_private_network_capacity_unavailable")
        self.command(["docker", "network", "create", "--driver", "bridge", "--subnet", str(choices[0]), network])
        # Legacy Redis is retained intact (including its writable layer). The
        # normal candidate uses the tested recovery Redis without clearing,
        # importing or replaying keys, sessions or historical queue entries.
        self.command(["docker", "run", "-d", "--name", f"madar-{self.slot}-local-parser", "--network", network,
            "--network-alias", "parser", "--restart", "no", "--log-driver", "none",
            "--env", "PARSER_WORKER_HEALTH_HOST=0.0.0.0", "--env", "PARSER_WORKER_PORT=8000",
            "--env", "DATA_UPLOAD_DIR=/tmp/local-parser", contract.images["backend"], "python", "-m", "workers.parser_worker"])
        self._create_application(contract, f"madar-{self.slot}-backend", "backend")
        self.command(["docker", "start", f"madar-{self.slot}-backend"])
        cfg = {"MADAR_CSP_CONNECT_SRC": "'self' https://api.madarportal.com", "MADAR_PUBLIC_SITE_DOMAIN": "madarportal.com",
               "MADAR_HSTS": "max-age=31536000"}
        args = ["docker", "run", "-d", "--name", f"madar-{self.slot}-frontend", "--network", network,
                "--restart", "no", "--log-driver", "none"]
        for key in cfg:
            args += ["--env", key]
        self.command(args+[contract.images["frontend"]], env={**cfg, "PATH": "/usr/bin:/bin"})
        for kind in ("notification", "calendar-sync", "data-deletion"):
            self._create_application(contract, f"madar-{self.slot}-{kind}-worker", kind+"-worker", worker=kind)

    def endpoint(self, kind):
        row = self.inspect(f"madar-{self.slot}-{kind}")
        network = f"madar-{self.slot}-local-transition"
        return "http://"+row["NetworkSettings"]["Networks"][network]["IPAddress"]+(":8000" if kind == "backend" else ":8080")

    def verify_private_candidate(self, contract, *, workers_required):
        for attempt in range(60):
            try:
                for kind, image in contract.images.items():
                    row = self.inspect(f"madar-{self.slot}-{kind}")
                    if row["Image"] != image or not row["State"]["Running"] or any(row["NetworkSettings"]["Ports"].values()):
                        raise RuntimeError("local_transition_candidate_identity_invalid")
                _, version = http(self.endpoint("backend")+"/health/version")
                _, ready = http(self.endpoint("backend")+"/health/ready", allow_503=not workers_required)
                _, fence = http(self.endpoint("backend")+"/health/recovery")
                if version["release_sha"] != contract.sha or version["release_slot"] != self.slot or fence != {"restricted": True, "business_writes_enabled": False}:
                    raise RuntimeError("local_transition_candidate_binding_invalid")
                allowed = {"notification_worker", "calendar_sync_worker", "calendar_sync_queue", "data_deletion_worker"} if not workers_required else set()
                if any(value not in {"ok", "disabled", "configured", "not_required", "development"} and name not in allowed
                       for name, value in ready["components"].items()):
                    raise RuntimeError("local_transition_candidate_unready")
                if workers_required and ready.get("ready") is not True:
                    raise RuntimeError("local_transition_candidate_workers_unready")
                import urllib.request
                with urllib.request.urlopen(self.endpoint("frontend"), timeout=5) as response:
                    if response.status != 200:
                        raise RuntimeError("local_transition_frontend_unready")
                return
            except (RuntimeError, OSError):
                if attempt == 59:
                    raise
                time.sleep(1)

    def designate_single_normal_owner(self, contract):
        self.require_phase(contract, {"handoff_pending"})
        with runtime_mutation_lock(self.state):
            self.require_all_workers_off()
            write_worker_authority(self.state, generation=digest(asdict(contract)), owner="CANDIDATE",
                old={"sha": contract.sha, "slot": "blue" if self.slot == "green" else "green"},
                candidate={"sha": contract.sha, "slot": self.slot})

    def require_single_owner(self, contract):
        authority = load_worker_authority(self.state)
        if authority is None or authority["owner"] != "CANDIDATE" or authority["generation"] != digest(asdict(contract)) or authority["candidate"] != {"sha": contract.sha, "slot": self.slot}:
            raise RuntimeError("local_transition_worker_owner_invalid")
        other = "blue" if self.slot == "green" else "green"
        for kind in ("notification", "calendar-sync", "data-deletion"):
            row = self.inspect(f"madar-{other}-{kind}-worker")
            if row["State"]["Running"] or row["HostConfig"]["RestartPolicy"]["Name"] != "no":
                raise RuntimeError("local_transition_duplicate_consumer")
        self.recovery.require_recovery_consumers_off()
        # Renamed hosted workers are retained evidence, never spare consumers.
        for name in self.command(["docker", "ps", "-a", "--format", "{{.Names}}"]).splitlines():
            if name.startswith(("madar-blue-", "madar-green-")) and "-worker-legacy-" in name:
                row = self.inspect(name)
                if row["State"]["Running"] or row["HostConfig"]["RestartPolicy"]["Name"] != "no":
                    raise RuntimeError("local_transition_archived_consumer_uninhibited")

    def start_and_verify_worker(self, contract, kind):
        self.require_phase(contract, {"handoff_pending"})
        self._start_exact_worker(contract, kind)

    def restart_existing_worker(self, contract, kind):
        self.require_phase(contract, {"normal"})
        self.require_write_authority(contract, "NORMAL")
        self._start_exact_worker(contract, kind)

    def _start_exact_worker(self, contract, kind):
        if kind not in {"notification", "calendar-sync", "data-deletion"}:
            raise RuntimeError("local_transition_worker_kind_invalid")
        self.require_single_owner(contract)
        name = f"madar-{self.slot}-{kind}-worker"
        row = self.inspect(name)
        env = dict(item.split("=", 1) for item in row["Config"].get("Env", []))
        if (row["Image"] != contract.images["backend"]
                or row["Config"].get("Labels", {}).get("com.madar.local-transition") != digest(asdict(contract))
                or env.get("SUPABASE_URL") != "http://madar-supabase:8000"
                or env.get("EMAIL_CHANNEL_ENABLED") != "false"
                or row["HostConfig"]["RestartPolicy"]["Name"] != "no"):
            raise RuntimeError("local_transition_worker_image_invalid")
        self.command(["docker", "start", name])
        port = {"notification": 8090, "calendar-sync": 8091, "data-deletion": 8094}[kind]
        for attempt in range(60):
            row = self.inspect(name)
            address = row["NetworkSettings"]["Networks"][f"madar-{self.slot}-local-transition"]["IPAddress"]
            try:
                http(f"http://{address}:{port}/health")
                return
            except RuntimeError:
                if attempt == 59:
                    raise
                time.sleep(1)

    def switch_normal_traffic(self, contract):
        self.require_phase(contract, {"switch_pending"})
        self.require_single_owner(contract)
        self.require_write_authority(contract, "READ_ONLY")
        self.verify_private_candidate(contract, workers_required=True)
        self.verify_local_fallback()
        phase = json.loads(protected(self.transaction_path, private=True).read_text())
        if phase.get("phase") != "switch_pending" or phase.get("contract_digest") != digest(asdict(contract)):
            raise RuntimeError("local_transition_traffic_phase_invalid")
        with runtime_mutation_lock(self.state):
            backend = urlsplit(self.endpoint("backend")).netloc
            frontend = urlsplit(self.endpoint("frontend")).netloc
            path = self.recovery.paths.upstream
            temporary = path.with_name(".normal-local-provider-upstreams")
            with temporary.open("x") as handle:
                handle.write(f"upstream madar_backend_active {{ server {backend}; }}\nupstream madar_frontend_active {{ server {frontend}; }}\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o644)
            os.replace(temporary, path)
            self.command(["docker", "exec", self.recovery.paths.proxy, "nginx", "-t"])
            self.command(["docker", "exec", self.recovery.paths.proxy, "nginx", "-s", "reload"])
            atomic_json(self.state / "provider-recovery-traffic.json", {"sha": contract.sha, "slot": self.slot,
                "schema": 115, "provider": "local", "database_restore": False, "normal_transition": True})

    def verify_serving_candidate(self, contract):
        _, version = http(f"http://127.0.0.1:{self.recovery.paths.stable_backend}/health/version")
        _, ready = http(f"http://127.0.0.1:{self.recovery.paths.stable_backend}/health/ready")
        if version.get("release_sha") != contract.sha or version.get("release_slot") != self.slot or not ready.get("ready"):
            raise RuntimeError("local_transition_serving_identity_invalid")

    def final_smoke(self, contract):
        report = json.loads(protected(self.root / "final-smoke.json", private=True).read_text())
        if report.get("contract_digest") != digest(asdict(contract)) or report.get("production_fingerprints") != self.fingerprints():
            raise RuntimeError("local_transition_final_smoke_binding_invalid")
        return report.get("gates", {})

    def retire_hosted_writers(self, contract):
        self.require_phase(contract, {"resume_pending"})
        for name in self.command(["docker", "ps", "-a", "--format", "{{.Names}}"]).splitlines():
            if not name.startswith(("madar-blue-", "madar-green-")):
                continue
            row = self.inspect(name)
            config = dict(item.split("=", 1) for item in row["Config"].get("Env", []))
            if ".supabase.co" in config.get("SUPABASE_URL", ""):
                self.command(["docker", "update", "--restart=no", name])
                self.command(["docker", "stop", name])
        self.require_single_owner(contract)

    def commit_normal_release_state(self, contract):
        self.require_phase(contract, {"resume_pending"})
        from deployment.lib.provider_local_backup_configuration import publish_backup_configuration
        from deployment.lib.provider_recovery_runtime import readonly_configuration
        native = {}
        load_environment_file(readonly_configuration(Path("/opt/madar/local-supabase/.env"), private=True), environ=native)
        reconciliation = json.loads(protected(self.root / "reconciliation.json", private=True).read_text())
        publish_backup_configuration(self.root, reconciliation, contract, native)
        # Configuration publication is a reviewed transaction output, not a
        # manual env edit. Preserve the old protected input and recovery state.
        old = self.recovery.paths.production_env
        archive = self.root / "retired-production.env"
        with archive.open("xb") as handle:
            handle.write(old.read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(archive, 0o600)
        temporary = old.with_name(".normal-local-production.env")
        with temporary.open("x") as handle:
            for key, value in self.config.items():
                if "\n" in value or "\r" in value:
                    raise RuntimeError("local_transition_environment_multiline_rejected")
                import shlex
                handle.write(key+"="+shlex.quote(value)+"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, old)
        state_path = self.state / "state.json"
        state = json.loads(state_path.read_text())
        state["active_slot"] = self.slot
        state["known_good_release"] = {"sha": contract.sha, "slot": self.slot, "images": contract.images,
            "schema": 115, "schema_compatible_min": 115, "schema_compatible_max": 115, "provider": "local",
            "worker_generation": digest(asdict(contract)),
            "migration_policy": "none", "runtime_only_rollback": True}
        state["provider_local_transition"] = digest(asdict(contract))
        atomic_json(state_path, state)
        # Keep recovery interlocks until a separately attested automation exit;
        # ordinary deployment cannot accidentally replace this new authority.
        identity = pwd.getpwnam("madar")
        for path in (old, state_path, self.state / "worker-ownership.json"):
            os.chown(path, identity.pw_uid, identity.pw_gid)
        # Consumer restart policies remain 'no'. Restarts require this protected
        # controller and the durable single-owner checks, not Docker automation.

    def switch_current_data_local_fallback(self, contract):
        self.require_phase(contract, {"rollback_pending"})
        with runtime_mutation_lock(self.state):
            recovery = self.recovery.contract
            write_worker_authority(self.state, generation=digest(asdict(recovery)), owner="RECOVERY",
                old={"sha": recovery.origin_sha, "slot": recovery.origin_slot},
                candidate={"sha": recovery.sha, "slot": "blue" if recovery.origin_slot == "green" else "green"})
            state = json.loads((self.state / "provider-recovery.json").read_text())
            state["phase"] = "rollback_pending"
            atomic_json(self.state / "provider-recovery.json", state)
        self.recovery.switch_local_rollback(self.recovery.contract)
        state["phase"] = "local_rollback_active"
        atomic_json(self.state / "provider-recovery.json", state)

    def verify_local_fallback_serving(self):
        self.recovery.verify_local_rollback(self.recovery.contract)
