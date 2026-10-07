"""Concrete Docker/native-provider adapter for the protected recovery transaction.

Only the bootstrap selects canonical paths. Fixture overrides are constructor
arguments; the production CLI accepts no environment/path/driver overrides.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit, unquote

from deployment.lib.environment_file import load_environment_file
from deployment.lib.provider_recovery import PROFILE, RecoveryContract, require_provider_recovery_authorization
from deployment.lib.release_deployer import atomic_json
from deployment.lib.runtime_authority import load_worker_authority, runtime_mutation_lock

SERVICES = ("supabase-db", "supabase-auth", "supabase-rest", "supabase-storage",
    "realtime-dev.supabase-realtime", "supabase-pooler", "supabase-meta", "supabase-envoy",
    "supabase-studio", "supabase-edge-functions", "supabase-imgproxy")
ORIGIN_PORTS = {"blue": 8101, "green": 8201}
PORTS = {"blue": (29101, 39101), "green": (29201, 39201), "local-fallback": (29401, 39401)}


def file_digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def protected(path: Path, *, private=False) -> Path:
    path = Path(path)
    if not path.is_absolute() or not path.is_file():
        raise RuntimeError("recovery_protected_file_missing")
    for item in (path, *path.parents):
        stat = item.lstat()
        if item.is_symlink() or stat.st_uid != 0 or stat.st_mode & 0o022:
            raise RuntimeError("recovery_protected_path_untrusted")
    if private and path.stat().st_mode & 0o077:
        raise RuntimeError("recovery_protected_file_not_private")
    return path


def readonly_configuration(path: Path, *, private=True) -> Path:
    """Existing operator-owned private configuration is read-only input.

    This trust rule never applies to authorization, executable code, or receipts.
    Canonical configuration files may be owned by the existing madar operator;
    parent directories must reject writes by unrelated users.
    """
    import pwd
    path = Path(path)
    operator = pwd.getpwnam("madar").pw_uid
    if not path.is_absolute() or not path.is_file():
        raise RuntimeError("recovery_readonly_configuration_missing")
    for item in (path, *path.parents):
        stat = item.lstat()
        if item.is_symlink() or stat.st_uid not in {0, operator} or stat.st_mode & 0o002:
            raise RuntimeError("recovery_readonly_configuration_untrusted")
        if stat.st_mode & 0o020 and stat.st_uid != operator:
            raise RuntimeError("recovery_readonly_configuration_untrusted")
    if private and path.stat().st_mode & 0o077:
        raise RuntimeError("recovery_readonly_configuration_not_private")
    return path


def read_json(path: Path):
    return json.loads(protected(path).read_text())


def http(url, *, headers=None, allow_402=False, allow_503=False):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args): return None
    try:
        with urllib.request.build_opener(NoRedirect).open(
                urllib.request.Request(url, headers=headers or {}), timeout=10) as response:
            body = response.read()
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        if error.code == 402 and allow_402: return 402, None
        if error.code == 503 and allow_503: return 503, json.loads(error.read())
        raise RuntimeError("recovery_http_check_failed") from None
    except (ValueError, OSError):
        raise RuntimeError("recovery_http_check_failed") from None


@dataclass(frozen=True)
class RecoveryPaths:
    repository: Path = Path("/srv/madar/production")
    state: Path = Path("/var/lib/madar/releases")
    production_env: Path = Path("/etc/madar/production.env")
    target_env: Path = Path("/etc/madar/provider402-recovery.env")
    upstream: Path = Path("/var/lib/madar/proxy/active-upstreams.conf")
    controller: Path = Path("/opt/madar/control-plane/deployment")
    checkpoint: Path = Path("/var/lib/madar-control-plane/provider402/checkpoint/manifest.json")
    rehearsal: Path = Path("/var/lib/madar-control-plane/provider402/rehearsal.json")
    source_env: Path = Path("/var/lib/madar/recovery-stale/legacy-checkout-storage.20260828T043706Z/production-checkout.env")
    proxy: str = "madar-release-proxy"
    prefix: str = "madar-provider402"
    production_prefix: str = "madar"
    controller_transition: Path = Path("/var/lib/madar-control-plane/provider402/controller-transition.json")
    stable_backend: int = 8001
    stable_frontend: int = 3000


class ProductionRecoveryOperations:
    def __init__(self, paths: RecoveryPaths, contract: RecoveryContract, *, ports=None):
        self.paths, self.contract = paths, contract
        if paths == RecoveryPaths():
            # Production adopts only the exact private runtimes whose human and
            # rollback evidence was authorized, rather than rebuilding different
            # configuration after the operator has tested them.
            from deployment.lib.provider_recovery_phases import require_completed_evidence, preparation_binding, sha256
            metadata = json.loads(protected(Path("/var/lib/madar-control-plane/provider402/schema-contract.json"), private=True).read_text())
            require_completed_evidence(contract, metadata)
            binding = sha256(preparation_binding(contract, metadata))
            directory = Path("/var/lib/madar-control-plane/provider402/rehearsals") / binding
            paths = replace(paths, target_env=directory/"configuration.env",
                            prefix="madar-provider402-rehearsal-"+binding[:12]+"-candidate")
            self.paths = paths
        self.ports = ports or PORTS
        self.config = {}
        load_environment_file(protected(paths.target_env, private=True), environ=self.config)
        self.production = {}
        load_environment_file(readonly_configuration(paths.production_env), environ=self.production)
        # Do not admit arbitrary Docker/runtime or process-loader overrides.
        self.config = {key: value for key, value in self.config.items() if key in {
            "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY", "CSRF_SECRET",
            "SESSION_ACTIVITY_SECRET", "PENDING_VERIFICATION_SECRET", "FRONTEND_URLS",
            "FRONTEND_URL", "FRONTEND_PRIMARY_URL", "PUBLIC_API_URL", "PUBLIC_SITE_DOMAIN",
            "TRUSTED_PROXY_IPS", "BACKUP_FRESHNESS_MARKER", "BACKUP_MAX_AGE_SECONDS",
        }}
        if (self.config.get("SUPABASE_URL") != "http://madar-supabase:8000"
                or not all(self.config.get(k) for k in ("SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY", "CSRF_SECRET", "FRONTEND_URLS"))):
            raise RuntimeError("recovery_local_configuration_invalid")
        self.trace = []

    def command(self, args, *, input=None, env=None):
        if args[0] == "git":
            # The canonical checkout is operator-owned. Root's clean launcher
            # must not depend on that operator's HOME/global Git configuration.
            # Trust only this exact adapter-bound repository, never '*', and
            # never honor replacement objects during provenance checks.
            if args[1:3] != ["-C", str(self.paths.repository)]:
                raise RuntimeError("recovery_git_repository_escape")
            args = ["git", "--no-replace-objects", "-c",
                    "safe.directory="+str(self.paths.repository), *args[1:]]
        result = subprocess.run(args, input=input, env=env, capture_output=True, text=True, timeout=240)
        if result.returncode:
            # Never include stderr: Docker/libpq/provider messages may contain secrets.
            raise RuntimeError("recovery_command_failed")
        return result.stdout.strip()

    def inspect(self, name):
        return json.loads(self.command(["docker", "inspect", name]))[0]

    def fingerprints(self):
        files = {"environment": self.paths.production_env, "state": self.paths.state/"state.json",
            "upstream": self.paths.upstream, "worker_authority": self.paths.state/"worker-ownership.json"}
        result = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key,path in files.items()}
        entries = []
        for path in sorted(self.paths.controller.rglob("*")):
            if path.is_symlink(): raise RuntimeError("recovery_controller_symlink")
            if path.is_file(): entries.append((str(path.relative_to(self.paths.controller)), hashlib.sha256(path.read_bytes()).hexdigest()))
        result["controller"] = digest(entries)
        return result

    def authorize(self, contract):
        from deployment.lib.provider_recovery_phases import require_activation_evidence
        require_activation_evidence(contract, self.metadata())
        require_provider_recovery_authorization(contract)
        if contract != self.contract: raise RuntimeError("recovery_contract_changed")
        self.trace.append("authorize")

    def checkpoint(self):
        manifest = read_json(self.paths.checkpoint)
        if hashlib.sha256(self.paths.checkpoint.read_bytes()).hexdigest() != self.contract.checkpoint_digest:
            raise RuntimeError("recovery_checkpoint_changed")
        created = datetime.fromisoformat(manifest["created_at"])
        if created.tzinfo is None:
            raise RuntimeError("recovery_checkpoint_timestamp_invalid")
        age = (datetime.now(timezone.utc)-created).total_seconds()
        if not 0 <= age <= 129600 or manifest.get("schema") != 115 or manifest.get("restore_verified") is not True:
            raise RuntimeError("recovery_checkpoint_unverified_or_stale")
        entries = manifest.get("files", [])
        required = {"database", "storage", "auth_metadata", "production_config", "images", "controller", "schema"}
        if {entry.get("kind") for entry in entries} != required:
            raise RuntimeError("recovery_checkpoint_incomplete")
        seen = set()
        for entry in entries:
            relative = Path(entry["path"])
            if relative.is_absolute() or ".." in relative.parts or relative in seen:
                raise RuntimeError("recovery_checkpoint_path_invalid")
            seen.add(relative)
            file = protected(self.paths.checkpoint.parent/relative, private=True)
            if file.stat().st_size != entry["size"] or file_digest(file) != entry["sha256"]:
                raise RuntimeError("recovery_checkpoint_integrity_failed")
        self.trace.append("checkpoint")
        return True

    def metadata(self):
        return json.loads(protected(Path("/var/lib/madar-control-plane/provider402/schema-contract.json"), private=True).read_text())

    def rehearsal(self):
        from deployment.lib.provider_recovery_phases import require_completed_evidence
        require_completed_evidence(self.contract, self.metadata())
        return True

    def target_sql(self, sql):
        return self.command(["docker","exec","-i","supabase-db","psql","-X","-U","postgres","-d","postgres","-v","ON_ERROR_STOP=1","-At"], input="BEGIN READ ONLY;\n"+sql+"\nROLLBACK;\n")

    def source_schema(self):
        # Only the explicitly approved variable is read from the protected file.
        values = []
        with readonly_configuration(self.paths.source_env).open() as handle:
            for line in handle:
                match = re.match(r"^\s*(?:export\s+)?SUPABASE_DB_URL=(.*)$", line)
                if match:
                    parsed = shlex.split(match.group(1), comments=True)
                    if len(parsed) != 1:
                        raise RuntimeError("recovery_source_database_configuration_invalid")
                    values.append(parsed[0])
        if len(values) != 1:
            raise RuntimeError("recovery_source_database_configuration_invalid")
        url = urlsplit(values[0])
        if url.scheme not in {"postgres", "postgresql"} or not url.hostname:
            raise RuntimeError("recovery_source_database_unavailable")
        env = {"PATH":"/usr/bin:/bin", "PGHOST":url.hostname, "PGPORT":str(url.port or 5432),
            "PGUSER":unquote(url.username or ""), "PGPASSWORD":unquote(url.password or ""),
            "PGDATABASE":unquote(url.path.lstrip("/")), "PGCONNECT_TIMEOUT":"10", "PGSSLMODE":"require"}
        text = self.command(["psql","-X","-At","-v","ON_ERROR_STOP=1"], env=env,
            input="BEGIN READ ONLY; SELECT schema_version FROM public.application_schema_state WHERE contract_key='core'; ROLLBACK;")
        return "115" in text.splitlines()

    def origin_evidence(self):
        state=json.loads((self.paths.state/"state.json").read_text())
        known=state.get("known_good_release", {})
        components={}
        for name,port in (("stable",self.paths.stable_backend),("active",ORIGIN_PORTS[self.contract.origin_slot])):
            _, ready=http(f"http://127.0.0.1:{port}/health/ready",allow_503=True)
            _, identity=http(f"http://127.0.0.1:{port}/health/version")
            if identity.get("release_sha") != self.contract.origin_sha:
                raise RuntimeError("recovery_serving_identity_changed")
            components[name]=ready.get("components")
        provider={}
        headers={"apikey":self.production["SUPABASE_SERVICE_KEY"],"Authorization":"Bearer "+self.production["SUPABASE_SERVICE_KEY"]}
        for name,path in (("auth","/auth/v1/health"),("rest","/rest/v1/users?select=id&limit=1")):
            provider[name]=http(self.production["SUPABASE_URL"].rstrip("/")+path,headers=headers,allow_402=True)[0]
        remote=self.command(["git","-C",str(self.paths.repository),"remote","get-url","origin"])
        head=self.command(["git","-C",str(self.paths.repository),"rev-parse","HEAD"])
        dirty=self.command(["git","-C",str(self.paths.repository),"status","--porcelain"])
        from deployment.lib.control_plane_upgrade import EXPECTED_CONTRACT
        result={"provider_http":provider,"sha":head,"slot":state.get("active_slot"),
            "installed_sha":(self.paths.controller/"CONTROL_PLANE_SOURCE_SHA").read_text().strip(),
            "schema":known.get("schema"),"production_fingerprints":self.fingerprints(),
            "readiness":components,"canonical_repository":remote==EXPECTED_CONTRACT["MADAR_CANONICAL_GIT_REMOTE"],
            "clean_repository":not dirty,"controller_provenance_valid":False,
            "traffic_identity_valid":known.get("sha")==head and known.get("slot")==state.get("active_slot"),
            "no_pending_release_or_migration":not any(state.get(k) for k in ("in_progress_release","rollback_failure","pending_migration")),
            "source_schema115":self.source_schema(),"local_checkpoint_valid":self.checkpoint()}
        # Compare every installed file listed in the existing installed manifest
        # against its recorded immutable Git source, not just a marker string.
        marker=result["installed_sha"]
        installer=self.command(["git","-C",str(self.paths.repository),"show",marker+":web/deployment/bin/madar-install-control-plane"])
        match=re.search(r"declare -a tracked_files=\((.*?)\n\)",installer,re.S)
        if not match:
            raise RuntimeError("recovery_installed_manifest_unavailable")
        relatives=shlex.split(match.group(1))
        for relative in relatives:
            entry=Path(relative)
            if entry.is_absolute() or ".." in entry.parts:
                raise RuntimeError("recovery_installed_manifest_invalid")
            installed=protected(self.paths.controller/entry)
            result_bytes=subprocess.run(["git","--no-replace-objects","-c","safe.directory="+str(self.paths.repository),"-C",str(self.paths.repository),"show",marker+":web/deployment/"+relative],capture_output=True,timeout=20)
            if result_bytes.returncode or installed.read_bytes()!=result_bytes.stdout:
                raise RuntimeError("recovery_controller_provenance_changed")
        if self.paths.controller_transition.exists():
            result["controller_transition"] = read_json(self.paths.controller_transition)
        result["controller_provenance_valid"]=True
        self.trace.append("origin402")
        return result

    def descriptor(self):
        return {"version":1,"sha":self.contract.sha,"schema":115,"images":self.contract.images,
            "profile":PROFILE,"supabase_url":"http://madar-supabase:8000","network":"madar-supabase-client",
            "configuration_sha256":hashlib.sha256(self.paths.target_env.read_bytes()).hexdigest(),
            "ports":list(self.ports["local-fallback"]),"database_restore":False}

    def register_fallback(self):
        descriptor=self.descriptor()
        if digest(descriptor)!=self.contract.rollback_runtime_digest:
            raise RuntimeError("recovery_fallback_contract_invalid")
        self.start_runtime("local-fallback")
        self.validate_runtime("local-fallback")
        path=self.paths.state/"provider-recovery-fallback.json"
        if path.exists() and json.loads(path.read_text())!=descriptor:
            raise RuntimeError("recovery_fallback_registration_changed")
        atomic_json(path,descriptor)
        self.trace.append("fallback_registered")

    def target_evidence(self):
        self.checkpoint();self.rehearsal()
        network=json.loads(self.command(["docker","network","inspect","madar-supabase-client"]))[0]
        native=[]
        for name in SERVICES:
            row=self.inspect(name)
            native.append(row["State"]["Status"]=="running" and row["State"].get("Health",{}).get("Status")=="healthy" and all(
                port["HostIp"]=="127.0.0.1" for ps in (row["NetworkSettings"]["Ports"] or {}).values() for port in ps or []))
        headers={"apikey":self.config["SUPABASE_SERVICE_KEY"],"Authorization":"Bearer "+self.config["SUPABASE_SERVICE_KEY"]}
        auth=http("http://127.0.0.1:18000/auth/v1/health",headers=headers)[0]==200
        rest,rows=http("http://127.0.0.1:18000/rest/v1/application_schema_state?contract_key=eq.core&select=schema_version",headers=headers)
        storage=http("http://127.0.0.1:18000/storage/v1/status",headers=headers)[0]==200
        sql=self.target_sql("SELECT count(*) FROM public.users p LEFT JOIN auth.users a ON p.auth_id=a.id WHERE p.auth_id IS NOT NULL AND a.id IS NULL;")
        orphan_free="0" in sql.splitlines()
        mfa_sql=self.target_sql("SELECT count(*)=2 AND bool_and(u.id IS NOT NULL AND f.status::text IN ('verified','unverified') AND f.factor_type::text='totp') FROM auth.mfa_factors f LEFT JOIN auth.users u ON u.id=f.user_id;")
        mfa_structural="t" in mfa_sql.splitlines()
        fallback_path=self.paths.state/"provider-recovery-fallback.json"
        if not fallback_path.exists():
            # Read-only pre-activation validation consumes the Phase-1 passive
            # registration; production registration occurs only in Phase 3.
            from deployment.lib.provider_recovery_phases import preparation_binding, sha256
            binding=sha256(preparation_binding(self.contract,self.metadata()))
            fallback_path=Path("/var/lib/madar-control-plane/provider402/rehearsals")/binding/"state/provider-recovery-fallback.json"
        # Existing release-state directories belong to the runtime operator.
        # Their descriptor is untrusted input until it exactly matches the
        # root-authorized contract and the live pinned runtime checks below.
        fallback=json.loads(fallback_path.read_text())
        if fallback!=self.descriptor(): raise RuntimeError("recovery_fallback_registration_invalid")
        self.validate_runtime("local-fallback")
        image_provenance=True
        for image in self.contract.images.values():
            row=self.inspect(image)
            image_provenance &= row["Id"]==image and row["Config"].get("Labels",{}).get("org.opencontainers.image.revision")==self.contract.sha
        return {"sha":self.contract.sha,"images":self.contract.images,"schema":115 if rows==[{"schema_version":115}] else 0,
            "migrations_executed":False,"supabase_url":self.config["SUPABASE_URL"],"network":"madar-supabase-client",
            "checkpoint_digest":self.contract.checkpoint_digest,"rollback_runtime_digest":digest(fallback),
            "checks":{"auth":auth,"rest":rest==200,"storage":storage,"schema":rows==[{"schema_version":115}],
                "all_supabase_services":all(native),"internal_network":network["Internal"] is True and network["Driver"]=="bridge",
                "loopback_ports":all(native),"auth_linkage":orphan_free,"mfa_aal2":mfa_structural and self.rehearsal(),"tenant_isolation":self.rehearsal(),
                "business_write_fence":self.rehearsal(),"no_consumers":self.require_recovery_consumers_off(),"checkpoint_valid":True,
                "rollback_live_local_compatible":True,"image_provenance":image_provenance}}

    def runtime_name(self,slot,kind): return f"{self.paths.prefix}-{slot}-{kind}"

    def start_runtime(self,slot):
        network=self.paths.prefix+"-"+slot+"-runtime"
        exists=subprocess.run(["docker","network","inspect",network],capture_output=True).returncode==0
        if not exists: self.command(["docker","network","create","--internal",network])
        redis=self.paths.prefix+"-redis"
        if subprocess.run(["docker","inspect",redis],capture_output=True).returncode:
            image=self.inspect(self.paths.production_prefix+"-"+self.contract.origin_slot+"-redis")["Image"]
            self.command(["docker","run","-d","--name",redis,"--network",network,"--restart","unless-stopped",
                "--log-driver","none","--label","com.madar.recovery.profile="+PROFILE,
                "--mount","type=volume,src="+self.paths.prefix+"-redis,dst=/data",image,"redis-server","--appendonly","yes"])
        redis_row=self.inspect(redis)
        if network not in redis_row["NetworkSettings"]["Networks"]:
            self.command(["docker","network","connect",network,redis])
        parser=self.runtime_name(slot,"parser")
        if subprocess.run(["docker","inspect",parser],capture_output=True).returncode:
            self.command(["docker","run","-d","--name",parser,"--network",network,
                "--network-alias","parser","--restart","unless-stopped","--log-driver","none","--env","PARSER_WORKER_PORT=8000",
                "--env","PARSER_WORKER_HEALTH_HOST=0.0.0.0","--env","DATA_UPLOAD_DIR=/tmp/recovery/private",
                self.contract.images["backend"],"python","-m","workers.parser_worker"])
        for kind,image in self.contract.images.items():
            name=self.runtime_name(slot,kind)
            if subprocess.run(["docker","inspect",name],capture_output=True).returncode==0:
                row=self.inspect(name)
                if row["Image"]!=image or row["Config"].get("Labels",{}).get("com.madar.recovery.profile")!=PROFILE:
                    raise RuntimeError("recovery_existing_runtime_identity_changed")
                continue
            cfg={}
            if kind=="backend":
                cfg={**self.config,"APP_ENV":"production","MADAR_RELEASE_SHA":self.contract.sha,
                    "MADAR_RELEASE_SLOT":slot,"MADAR_ENV_FILE":"/tmp/no-env","MADAR_ENV_OVERRIDE":"false",
                    "MADAR_RECOVERY_PROFILE":PROFILE,"MADAR_SUPABASE_CLIENT_NETWORK":"madar-supabase-client",
                    "SCHEMA_COMPATIBLE_MIN":"115","SCHEMA_COMPATIBLE_MAX":"115","COOKIE_SECURE":"true",
                    "ADMIN_MFA_LOGIN_ENFORCEMENT":"true","RATE_LIMIT_ENABLED":"true","RATE_LIMIT_FAIL_OPEN":"false",
                    "REDIS_URL":"redis://"+redis+":6379/0","NOTIFICATION_WORKER_ENABLED":"false",
                    "CALENDAR_SYNC_WORKER_ENABLED":"false","DATA_DELETION_WORKER_ENABLED":"false",
                    "NOTIFICATION_WORKER_REQUIRED":"false","DATA_DELETION_WORKER_REQUIRED":"false",
                    "CALENDAR_FEATURE_ENABLED":"false","CALENDAR_SYNC_REQUIRED":"false","EMAIL_CHANNEL_ENABLED":"false",
                    "WEB_PUSH_ENABLED":"false","ALLOW_REMOTE_DATASET_URLS":"false","AI_ALLOW_LOCAL_EXEC":"false",
                    "PARSER_ISOLATED_WORKER_ENABLED":"true",
                    "PARSER_WORKER_URL":"http://parser:8000",
                    "PARSER_WORKER_HEALTH_URL":"http://parser:8000/health","COMMERCIAL_ENTITLEMENTS_ENFORCED":"false",
                    "PUBLIC_UPLOADS_DIR":"/tmp/recovery/uploads","DATA_UPLOAD_DIR":"/tmp/recovery/private",
                    "PRIVATE_CHARTS_DIR":"/tmp/recovery/charts","BACKUP_FRESHNESS_REQUIRED":"true"}
            else:
                cfg={"MADAR_CSP_CONNECT_SRC":"'self'","MADAR_PUBLIC_SITE_DOMAIN":"madarportal.com","MADAR_HSTS":"max-age=31536000"}
            port=self.ports[slot][0 if kind=="backend" else 1]
            cmd=["docker","create","--name",name,"--network",network,"--network-alias", "backend" if kind=="backend" else "frontend",
                "--log-driver","none","--restart","unless-stopped","--label","com.madar.recovery.profile="+PROFILE,
                ]
            if kind=="backend" and self.config.get("BACKUP_FRESHNESS_MARKER"):
                marker=protected(Path(self.config["BACKUP_FRESHNESS_MARKER"]))
                cmd += ["--mount",f"type=bind,src={marker},dst={marker},readonly"]
            for key in cfg: cmd += ["--env",key]
            self.command(cmd+[image],env={"PATH":os.environ.get("PATH","/usr/bin:/bin"),**cfg})
            if kind=="backend": self.command(["docker","network","connect","madar-supabase-client",name])
            self.command(["docker","start",name])
        self.trace.append("runtime_prepared:"+slot)

    def runtime_endpoint(self,slot,kind):
        # Internal bridges deliberately have no public or published container
        # ports. The host-network governed proxy reaches private bridge IPs.
        import ipaddress
        if slot not in self.ports or kind not in {"backend","frontend"}:
            raise RuntimeError("recovery_runtime_endpoint_invalid")
        row=self.inspect(self.runtime_name(slot,kind))
        network=self.paths.prefix+"-"+slot+"-runtime"
        attachment=row["NetworkSettings"]["Networks"].get(network)
        if not attachment or not ipaddress.ip_address(attachment["IPAddress"]).is_private:
            raise RuntimeError("recovery_runtime_private_address_invalid")
        info=json.loads(self.command(["docker","network","inspect",network]))[0]
        if info.get("Internal") is not True or info.get("Driver")!="bridge":
            raise RuntimeError("recovery_runtime_network_not_private")
        return "http://"+attachment["IPAddress"]+(":8000" if kind=="backend" else ":8080")

    def validate_runtime(self,slot):
        backend=self.runtime_endpoint(slot,"backend")
        frontend=self.runtime_endpoint(slot,"frontend")
        for attempt in range(30):
            try:
                _,ready=http(backend+"/health/ready")
                _,version=http(backend+"/health/version")
                _,profile=http(backend+"/health/recovery")
                if ready.get("ready") is not True or version.get("release_sha")!=self.contract.sha or version.get("release_slot")!=slot:
                    raise RuntimeError("recovery_runtime_identity_or_readiness_invalid")
                if profile!={"restricted":True,"business_writes_enabled":False}:
                    raise RuntimeError("recovery_runtime_unfenced")
                if str(version.get("schema_compatible_min"))!="115" or str(version.get("schema_compatible_max"))!="115":
                    raise RuntimeError("recovery_runtime_schema_invalid")
                # Validate actual config, images and host bindings, not health alone.
                for kind,image in self.contract.images.items():
                    row=self.inspect(self.runtime_name(slot,kind))
                    if row["Image"]!=image or not row["State"]["Running"]:
                        raise RuntimeError("recovery_runtime_image_invalid")
                    if any(b["HostIp"]!="127.0.0.1" for ps in row["NetworkSettings"]["Ports"].values() for b in ps or []):
                        raise RuntimeError("recovery_runtime_public_exposure")
                    if kind=="backend":
                        env=dict(v.split("=",1) for v in row["Config"]["Env"])
                        if any(env.get(key)!=value for key,value in self.config.items()):
                            raise RuntimeError("recovery_runtime_configuration_changed")
                        if any(env.get(key)!="true" for key in ("ADMIN_MFA_LOGIN_ENFORCEMENT","RATE_LIMIT_ENABLED","COOKIE_SECURE","BACKUP_FRESHNESS_REQUIRED")) or env.get("RATE_LIMIT_FAIL_OPEN")!="false":
                            raise RuntimeError("recovery_runtime_security_policy_changed")
                        if env.get("SUPABASE_URL")!="http://madar-supabase:8000" or env.get("MADAR_RECOVERY_PROFILE")!=PROFILE:
                            raise RuntimeError("recovery_runtime_provider_invalid")
                        if any(env.get(k)!="false" for k in ("NOTIFICATION_WORKER_ENABLED","CALENDAR_SYNC_WORKER_ENABLED","DATA_DELETION_WORKER_ENABLED")):
                            raise RuntimeError("recovery_runtime_consumers_enabled")
                with urllib.request.urlopen(frontend+"/",timeout=5) as response:
                    if response.status!=200: raise RuntimeError("recovery_frontend_unavailable")
                return True
            except (RuntimeError,OSError):
                if attempt==29: raise
                time.sleep(1)

    def worker_names(self):
        return [f"{self.paths.production_prefix}-{slot}-{kind}-worker" for slot in ("blue","green") for kind in ("notification","calendar-sync","data-deletion")]

    def require_recovery_consumers_off(self):
        # No recovery worker container may exist, including a retained instance.
        names=self.command(["docker","ps","-a","--format","{{.Names}}"]).splitlines()
        if any(name.startswith(self.paths.prefix+"-") and name.endswith(("notification-worker","calendar-sync-worker","data-deletion-worker")) for name in names):
            raise RuntimeError("recovery_consumer_container_present")
        return True

    def capture_pre_switch_state(self):
        self.authorize(self.contract)
        workers={}
        for name in self.worker_names():
            row=self.inspect(name)
            workers[name]={"id":row["Id"],"running":row["State"]["Running"],
                "restart":row["HostConfig"]["RestartPolicy"]}
        files={name:(self.paths.state/name).read_bytes() if (self.paths.state/name).exists() else None
               for name in ("worker-ownership.json","provider-recovery-fallback.json")}
        return {"workers":workers,"files":files,"fingerprints":self.fingerprints()}

    def restore_pre_switch_state(self,snapshot):
        self.authorize(self.contract)
        state=json.loads((self.paths.state/"provider-recovery.json").read_text())
        if state.get("phase")!="pre_switch_compensation_pending":
            raise RuntimeError("recovery_pre_switch_compensation_not_allowed")
        if set(snapshot["workers"])!=set(self.worker_names()):
            raise RuntimeError("recovery_pre_switch_snapshot_invalid")
        # Verify all identities before attempting any compensation. A replaced
        # worker or changed production configuration requires operator review.
        for name,old in snapshot["workers"].items():
            if self.inspect(name)["Id"]!=old["id"]:
                raise RuntimeError("recovery_pre_switch_worker_identity_changed")
        current=self.fingerprints()
        if any(current[k]!=snapshot["fingerprints"][k] for k in current if k!="worker_authority"):
            raise RuntimeError("recovery_pre_switch_production_changed")
        with runtime_mutation_lock(self.paths.state):
            for name,content in snapshot["files"].items():
                path=self.paths.state/name
                if content is None:
                    if path.exists():path.unlink()
                else:
                    temp=path.with_name(".provider402-restore-"+name)
                    with temp.open("xb") as handle:
                        handle.write(content);handle.flush();os.fsync(handle.fileno())
                    os.chmod(temp,0o600);os.replace(temp,path)
            for name,old in snapshot["workers"].items():
                policy=old["restart"]["Name"]
                if policy=="on-failure" and old["restart"].get("MaximumRetryCount"):
                    policy += ":"+str(old["restart"]["MaximumRetryCount"])
                self.command(["docker","update","--restart="+policy,name])
                row=self.inspect(name)
                if old["running"] and not row["State"]["Running"]:
                    self.command(["docker","start",name])
                elif not old["running"] and row["State"]["Running"]:
                    self.command(["docker","stop",name])
            for name,old in snapshot["workers"].items():
                row=self.inspect(name)
                if row["State"]["Running"]!=old["running"] or row["HostConfig"]["RestartPolicy"]!=old["restart"]:
                    raise RuntimeError("recovery_pre_switch_compensation_incomplete")
        if self.fingerprints()!=snapshot["fingerprints"]:
            raise RuntimeError("recovery_pre_switch_compensation_incomplete")

    def inhibit_all_workers(self):
        for name in self.worker_names():
            row=self.inspect(name)
            self.command(["docker","update","--restart=no",name])
            if row["State"]["Running"]: self.command(["docker","stop",name])
        self.require_all_workers_off();self.trace.append("workers_inhibited")

    def require_all_workers_off(self):
        for name in self.worker_names():
            row=self.inspect(name)
            if row["State"]["Running"] or row["HostConfig"]["RestartPolicy"]["Name"]!="no":
                raise RuntimeError("recovery_workers_not_durably_inhibited")
        self.require_recovery_consumers_off()

    def prepare_candidate(self,contract,slot):
        self.start_runtime(slot);self.validate_runtime(slot)

    def switch_recovery_traffic(self,contract,slot):
        self.switch(slot)

    def switch_local_rollback(self,contract):
        self.switch("local-fallback")

    def verify_local_rollback(self,contract):
        self.validate_runtime("local-fallback");self.smoke_recovery(contract,"local-fallback")

    def smoke_recovery(self,contract,slot):
        self.validate_runtime(slot)
        _,profile=http(f"http://127.0.0.1:{self.paths.stable_backend}/health/recovery")
        _,version=http(f"http://127.0.0.1:{self.paths.stable_backend}/health/version")
        if profile!={"restricted":True,"business_writes_enabled":False} or version.get("release_slot")!=slot or version.get("release_sha")!=contract.sha:
            raise RuntimeError("recovery_stable_runtime_mismatch")
        self.trace.append("smoke:"+slot)

    def switch(self,slot):
        self.authorize(self.contract)
        with runtime_mutation_lock(self.paths.state):
            authority=load_worker_authority(self.paths.state)
            state=json.loads((self.paths.state/"provider-recovery.json").read_text())
            context=digest(self.contract.__dict__)
            if (authority is None or authority["owner"]!="RECOVERY"
                    or authority["candidate"]["sha"]!=self.contract.sha
                    or authority["generation"]!=context
                    or state.get("context_digest")!=context):
                raise RuntimeError("recovery_traffic_authority_invalid")
            if state.get("phase") not in {"switch_pending","active","rollback_pending","local_rollback_active"}:
                raise RuntimeError("recovery_traffic_phase_invalid")
            if slot not in {authority["candidate"]["slot"],"local-fallback"}:
                raise RuntimeError("recovery_traffic_target_invalid")
            self.require_all_workers_off();self.validate_runtime(slot)
            if slot=="local-fallback" and json.loads((self.paths.state/"provider-recovery-fallback.json").read_text())!=self.descriptor():
                raise RuntimeError("recovery_fallback_not_registered")
            backend=urlsplit(self.runtime_endpoint(slot,"backend")).netloc
            frontend=urlsplit(self.runtime_endpoint(slot,"frontend")).netloc
            content=f"upstream madar_backend_active {{ server {backend}; }}\nupstream madar_frontend_active {{ server {frontend}; }}\n"
            from deployment.lib.release_deployer import atomic_json
            # Traffic state is a separate explicit recovery authority. The
            # ordinary release state's known-good hosted slot is never forged.
            path=self.paths.upstream
            temporary=path.with_name(".provider402-upstreams")
            if temporary.exists(): raise RuntimeError("recovery_traffic_temporary_exists")
            with temporary.open("x") as handle:
                handle.write(content);handle.flush();os.fsync(handle.fileno())
            os.chmod(temporary,0o644);os.replace(temporary,path)
            descriptor=os.open(path.parent,os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(descriptor)
            finally: os.close(descriptor)
            self.command(["docker","exec",self.paths.proxy,"nginx","-t"])
            self.command(["docker","exec",self.paths.proxy,"nginx","-s","reload"])
            self.smoke_recovery(self.contract,slot)
            atomic_json(self.paths.state/"provider-recovery-traffic.json",{"sha":self.contract.sha,"slot":slot,"schema":115,"provider":"local","database_restore":False})
            self.trace.append("traffic:"+slot)
