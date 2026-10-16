#!/usr/bin/env python3
"""Dedicated-VM-only native provider rehearsal; never consumes operator env files."""

import argparse
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import time
import urllib.error
import urllib.request

OWNER = "architecture-hardening-20261016"
PROJECT = "madar-hardening-20261016"
MARKER = "madar-hardening-synthetic-146"
HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
RUNTIME = Path.home() / PROJECT
DOCKER = ["sudo", "-n", "docker", "--host", "unix:///var/run/docker.sock"]


def require_staging_host():
    if socket.gethostname() != "madar-staging":
        raise RuntimeError("This harness runs only on the dedicated madar-staging VM")
    if RUNTIME.is_symlink() or RUNTIME.parent.resolve() != Path.home().resolve():
        raise RuntimeError("Unsafe staging runtime root")


def docker(*args, data=None, timeout=180):
    require_staging_host()
    # In particular, never inherit DOCKER_HOST, Compose overrides or credentials.
    environment = {"PATH": os.defpath, "HOME": str(Path.home())}
    if args and args[0] == "build":
        # BuildKit attempts remote tag resolution even with --network=none.
        # The VM is deliberately offline; the legacy builder uses local images.
        environment["DOCKER_BUILDKIT"] = "0"
    result = subprocess.run(DOCKER + list(args), input=data, capture_output=True,
                            timeout=timeout, env=environment)
    if args and args[0] == "build":
        private_write("application-build.log", (result.stdout + result.stderr).decode(errors="replace"))
    if result.returncode:
        # Database URLs and passwords can occur in provider/Compose errors.
        # Preserve output privately for diagnosis, never echo it into reports.
        RUNTIME.mkdir(mode=0o700, exist_ok=True)
        private_write("last-command-error.log", result.stderr.decode(errors="replace"))
        raise RuntimeError("Staging Docker command failed; inspect private last-command-error.log")
    return result.stdout


def private_write(name, value, *, mounted=False):
    path = RUNTIME / name
    if path.is_symlink():
        raise RuntimeError("Refusing symlinked staging configuration")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(value)
    path.chmod(0o444 if mounted else 0o600)


def jwt(secret, role):
    def encode(value):
        return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode().rstrip("=")
    now = int(time.time())
    unsigned = encode({"alg": "HS256", "typ": "JWT"}) + "." + encode(
        {"role": role, "iss": "madar-isolated-staging", "iat": now, "exp": now + 86400 * 7})
    signature = hmac.new(secret.encode(), unsigned.encode(), hashlib.sha256).digest()
    return unsigned + "." + base64.urlsafe_b64encode(signature).decode().rstrip("=")


def prepare(source_sha):
    require_staging_host()
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha or ""):
        raise RuntimeError("An explicit committed source SHA is required")
    if RUNTIME.exists():
        raise RuntimeError("Runtime root already exists; preserve it or use its existing configuration")
    RUNTIME.mkdir(mode=0o700)
    password, signing = secrets.token_hex(32), secrets.token_hex(32)
    anon, service = jwt(signing, "anon"), jwt(signing, "service_role")
    state = {"owner": OWNER, "project": PROJECT, "source_sha": source_sha,
             "database": "madar_hardening", "marker": MARKER}
    private_write("owner.json", json.dumps(state, indent=2) + "\n")
    values = {"HARDENING_ROOT": str(RUNTIME), "SOURCE_SHA": source_sha,
              "DATABASE_PASSWORD": password, "JWT_SECRET": signing, "ANON_KEY": anon, "SERVICE_KEY": service}
    private_write("compose.env", "".join(f"{key}={value}\n" for key, value in values.items()))
    app = {
        "APP_ENV": "staging", "MADAR_ENV_OVERRIDE": "false", "MADAR_ENV_FILE": "/tmp/no-env-file",
        "SUPABASE_URL": "http://gateway:8081", "SUPABASE_ANON_KEY": anon, "SUPABASE_SERVICE_KEY": service,
        "CSRF_SECRET": secrets.token_hex(32), "COOKIE_SECURE": "true", "COOKIE_SAMESITE": "lax",
        "CSRF_ORIGIN_CHECK_ENABLED": "true", "CSRF_ALLOW_MISSING_ORIGIN": "false",
        "FRONTEND_URLS": "http://127.0.0.1:18080", "PUBLIC_SITE_DOMAIN": "hardening.test",
        "REDIS_URL": "redis://redis:6379/0", "RATE_LIMIT_ENABLED": "true", "RATE_LIMIT_FAIL_OPEN": "false",
        "ADMIN_MFA_LOGIN_ENFORCEMENT": "true", "COMMERCIAL_ENTITLEMENTS_ENFORCED": "true",
        "MADAR_RELEASE_SHA": source_sha, "MADAR_BUILD_TIMESTAMP": "staging-source-overlay",
        "SCHEMA_COMPATIBLE_MIN": "144", "SCHEMA_COMPATIBLE_MAX": "146",
        "PUBLIC_UPLOADS_DIR": "/tmp/public/uploads", "DATA_UPLOAD_DIR": "/tmp/private/uploads",
        "PRIVATE_CHARTS_DIR": "/tmp/private/charts", "MADAR_UPLOAD_WORKSPACE_DIR": "/tmp/parser",
        "MPLCONFIGDIR": "/tmp/matplotlib", "XDG_CACHE_HOME": "/tmp/cache",
        "PYGWALKER_TELEMETRY_ENABLED": "false", "AI_ALLOW_LOCAL_EXEC": "false",
        "ALLOW_REMOTE_DATASET_URLS": "false", "CALENDAR_FEATURE_ENABLED": "false",
        "EMAIL_CHANNEL_ENABLED": "false", "WEB_PUSH_ENABLED": "false",
        "NOTIFICATION_WORKER_ENABLED": "true", "NOTIFICATION_WORKER_REQUIRED": "true",
        "NOTIFICATION_WORKER_HEALTH_HOST": "0.0.0.0",
        "NOTIFICATION_WORKER_HEALTH_URL": "http://notification-worker:8090/health",
        "NOTIFICATION_WORKER_CONCURRENCY": "1", "NOTIFICATION_WORKER_BATCH_SIZE": "5",
        "NOTIFICATION_WORKER_POLL_SECONDS": "1", "STORAGE_DISK_FREE_FLOOR_BYTES": "16777216",
        "METRICS_TOKEN": secrets.token_hex(32), "BACKUP_FRESHNESS_REQUIRED": "false",
    }
    private_write("application.env", "".join(f"{key}={value}\n" for key, value in app.items()))
    # Only generated hex strings enter SQL literals. These credentials are
    # scoped to this unpublished, disposable database and never leave the VM.
    private_write("bootstrap.sql", f"""
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create role authenticator login noinherit password '{password}';
grant anon, authenticated, service_role to authenticator;
create role supabase_auth_admin login noinherit password '{password}';
create role supabase_storage_admin login noinherit password '{password}';
grant anon, authenticated, service_role to supabase_storage_admin;
create schema auth authorization supabase_auth_admin;
create schema storage authorization supabase_storage_admin;
create schema extensions;
create extension pgcrypto schema extensions;
create extension "uuid-ossp" schema extensions;
grant usage on schema public, extensions to anon, authenticated, service_role, supabase_auth_admin, supabase_storage_admin;
grant create on schema public to supabase_auth_admin, supabase_storage_admin;
alter role supabase_auth_admin set search_path to auth, public, extensions;
alter role supabase_storage_admin set search_path to storage, public, extensions;
create function auth.uid() returns uuid language sql stable as $$
  select coalesce(nullif(current_setting('request.jwt.claim.sub',true),''),
    nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'sub')::uuid $$;
create function auth.role() returns text language sql stable as $$
  select coalesce(nullif(current_setting('request.jwt.claim.role',true),''),
    nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role') $$;
create function auth.jwt() returns jsonb language sql stable as $$
  select coalesce(nullif(current_setting('request.jwt.claims',true),'')::jsonb,'{{}}'::jsonb) $$;
grant usage on schema auth to anon, authenticated, service_role;
comment on database madar_hardening is '{MARKER}';
""", mounted=True)
    private_write("nginx.conf", """pid /tmp/nginx.pid;
error_log /dev/stderr warn;
events { worker_connections 128; }
http {
  access_log off;
  client_body_temp_path /tmp/client;
  proxy_temp_path /tmp/proxy;
  client_max_body_size 6m;
  server {
    listen 8081;
    location /auth/v1/ { proxy_pass http://auth:9999/; proxy_set_header Host $http_host; }
    location /rest/v1/ { proxy_pass http://rest:3000/; proxy_set_header Host $http_host; }
    location /storage/v1/ { proxy_pass http://storage:5000/; proxy_set_header Host $http_host; }
    location / { return 404; }
  }
}
""", mounted=True)
    print("Prepared private synthetic staging configuration; no external credentials used")


def state():
    require_staging_host()
    owner = RUNTIME / "owner.json"
    if owner.is_symlink() or not owner.is_file():
        raise RuntimeError("Missing owned staging runtime")
    value = json.loads(owner.read_text())
    if value.get("owner") != OWNER or value.get("project") != PROJECT or value.get("marker") != MARKER:
        raise RuntimeError("Staging ownership mismatch")
    return value


def compose(*args, timeout=180):
    state()
    return docker("compose", "--project-name", PROJECT, "--env-file", str(RUNTIME / "compose.env"),
                  "--file", str(HERE / "compose.yaml"), *args, timeout=timeout)


def attest_resources():
    state()
    identifiers = docker("ps", "-aq", "--filter", f"label=com.docker.compose.project={PROJECT}").decode().split()
    for identifier in identifiers:
        resource = json.loads(docker("inspect", identifier))[0]
        if resource["Config"]["Labels"].get("com.madar.staging.owner") != OWNER:
            raise RuntimeError("Refusing an unowned staging container")
    for kind, names in (("network", [f"{PROJECT}_isolated"]),
                        ("volume", [f"{PROJECT}_database", f"{PROJECT}_objects"])):
        existing = docker(kind, "ls", "--format", "{{.Name}}").decode().splitlines()
        for name in names:
            if name not in existing:
                continue
            resource = json.loads(docker(kind, "inspect", name))[0]
            if (resource.get("Labels") or {}).get("com.madar.staging.owner") != OWNER:
                raise RuntimeError("Refusing an unowned staging resource")
            if kind == "network" and not resource.get("Internal"):
                raise RuntimeError("Staging network must be internal")


def database_container():
    attest_resources()
    identifier = compose("ps", "-q", "postgres").decode().strip()
    if not identifier:
        raise RuntimeError("Owned staging database is not running")
    return identifier


def sql(statement, *, database="madar_hardening"):
    return docker("exec", "-i", database_container(), "psql", "-X", "-U", "postgres", "-d", database,
                  "-v", "ON_ERROR_STOP=1", "-Atq", data=statement.encode(), timeout=180).decode().strip()


def require_database_marker():
    actual = sql("select current_database() || ':' || shobj_description(oid,'pg_database') "
                 "from pg_database where datname=current_database();")
    if actual != "madar_hardening:" + MARKER:
        raise RuntimeError("Refusing SQL on an unverified disposable database")


def up():
    value = state()
    attest_resources()
    if sql_if_running():
        raise RuntimeError("Database already running; use schema or smoke without recreating it")
    docker("build", "--network=none", "--memory=1536m", "--build-arg", "SOURCE_SHA=" + value["source_sha"],
           "--file", str(HERE / "Dockerfile"), "--tag", "madar-hardening-application:" + value["source_sha"],
           str(REPOSITORY), timeout=240)
    compose("up", "-d", "--wait", "--wait-timeout", "90", "postgres", "auth", "rest", "storage", "gateway", "redis")
    print("Native provider services started on the isolated staging network")


def sql_if_running():
    return bool(compose("ps", "-q", "postgres").strip())


def schema():
    require_database_marker()
    if sql("select to_regclass('public.application_schema_state') is not null;") != "f":
        raise RuntimeError("Schema initialization requires a fresh owned database")
    for path in sorted((REPOSITORY / "web/database/migrations").glob("*.sql")):
        number = int(path.name.split("_", 1)[0])
        if number == 142 or number > 146:
            continue  # The selected learning143 branch explicitly excludes142.
        sql(path.read_text())
    if sql("select schema_version from public.application_schema_state where contract_key='core';") != "146":
        raise RuntimeError("Staging schema target was not reached")
    sql("notify pgrst, 'reload schema';")
    compose("up", "-d", "--wait", "--wait-timeout", "90", "backend", "notification-worker")
    print("Immutable migrations rehearsed to schema146; API and notification worker started")


def down():
    attest_resources()
    # Stop/remove only this explicitly labeled project. Preserve named volumes
    # and private credentials for review and recovery; no broad Docker cleanup.
    compose("down", "--timeout", "15")
    print("Owned integration services stopped; named data/object volumes retained")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "up", "schema", "down", "status"))
    parser.add_argument("--source-sha")
    args = parser.parse_args()
    require_staging_host()
    if args.action == "prepare":
        prepare(args.source_sha)
    elif args.action == "status":
        attest_resources()
        print(compose("ps", "--format", "json").decode())
    else:
        {"up": up, "schema": schema, "down": down}[args.action]()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error)) from None
