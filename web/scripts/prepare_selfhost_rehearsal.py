#!/usr/bin/env python3
"""Prepare (never start) the pinned synthetic-only self-host rehearsal.

Does not load production settings or change release state. Run as madar, with
an exact official sparse checkout and a new selfhost-rehearsal directory.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

UPSTREAM_SHA = "241bb11c0627f2981746d37033f57dbfa81d29b0"
NODE_IMAGE = "node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32"
SERVICES = frozenset({"db", "auth", "rest", "storage", "imgproxy", "api-gw", "studio", "meta", "supavisor"})
DOCKER = ["docker", "--host", "unix:///var/run/docker.sock"]


def clean_environment():
    # Compose process variables override .env; never inherit provider credentials.
    return {k: os.environ[k] for k in ("PATH", "HOME", "USER", "LOGNAME") if k in os.environ}


def validate_target(target: Path):
    if not target.is_absolute() or target.name != "selfhost-rehearsal":
        raise ValueError("target_must_be_absolute_selfhost_rehearsal_directory")
    if ".." in target.parts or not any(target.is_relative_to(root) for root in (Path("/home/madar"), Path("/tmp"))):
        raise ValueError("target_outside_rehearsal_roots")
    if target.exists() or target.is_symlink() or any(p.is_symlink() for p in target.parents):
        raise ValueError("existing_or_symlink_target_refused")


def isolated_compose(original: dict, lock: dict) -> dict:
    if lock.get("commit") != UPSTREAM_SHA:
        raise ValueError("incorrect_upstream_lock")
    digests = {row["image"]: row["digest"] for row in lock["images"] if row.get("status") == "resolved"}
    config = copy.deepcopy(original)
    if not SERVICES.issubset(config.get("services", {})):
        raise ValueError("required_service_missing")
    config["name"] = "madar-selfhost-rehearsal"
    config["services"] = {k: v for k, v in config["services"].items() if k in SERVICES}
    for name, service in config["services"].items():
        digest = digests.get(service["image"], "")
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
            raise ValueError("unresolved_image_digest")
        service["image"] += "@" + digest
        service["container_name"] = "madar-selfhost-rehearsal-" + name
        service["restart"] = "no"
        service.pop("ports", None)
        service["mem_limit"] = "1536m" if name == "db" else "1024m" if name == "studio" else "768m"
        service["cpus"] = "1.0"
        if service.get("network_mode") or service.get("privileged") or service.get("devices"):
            raise ValueError("unsafe_service_privileges")
        for mount in service.get("volumes", []):
            if not isinstance(mount, str):
                raise ValueError("unexpected_mount_format")
            source = mount.split(":", 1)[0]
            if (not source.startswith("./volumes/") and source != "db-config") or ".." in Path(source).parts:
                raise ValueError("unsafe_mount")
        if "depends_on" in service:
            service["depends_on"] = {k: v for k, v in service["depends_on"].items() if k in SERVICES}
    for name, ports in {"api-gw": ["127.0.0.1:55431:8000"], "supavisor": ["127.0.0.1:55432:5432", "127.0.0.1:55433:6543"], "db": ["127.0.0.1:55434:5432"]}.items():
        config["services"][name]["ports"] = ports
    config["services"]["auth"]["environment"]["GOTRUE_JWT_KEYS"] = "${JWT_KEYS}"
    config["services"]["storage"]["environment"]["JWT_JWKS"] = "${JWT_JWKS}"
    config["services"]["storage"]["environment"]["ENABLE_IMAGE_TRANSFORMATION"] = "false"
    config["volumes"] = {"db-config": None}
    return config


def prepare(source: Path, target: Path, lock_path: Path):
    import yaml  # Operator tooling dependency; not added to the application image.
    validate_target(target)
    env = clean_environment()
    sha = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], env=env, text=True).strip()
    if sha != UPSTREAM_SHA:
        raise ValueError("upstream_identity_mismatch")
    lock = json.loads(lock_path.read_text())
    # Read tracked blobs from the exact commit, excluding ignored .env/data files
    # and refusing symlinks. No untracked source content can enter the rehearsal.
    listing = subprocess.check_output(["git", "-C", str(source), "ls-tree", "-r", "HEAD", "docker"], env=env, text=True)
    files = []
    for entry in listing.splitlines():
        metadata, filename = entry.split("\t", 1)
        mode, kind, oid = metadata.split()
        path = Path(filename)
        if mode not in {"100644", "100755"} or kind != "blob" or ".." in path.parts or path.parts[0] != "docker":
            raise ValueError("unsafe_upstream_entry")
        files.append((path.relative_to("docker"), oid, mode))
    if not files:
        raise ValueError("upstream_docker_snapshot_missing")
    original = yaml.safe_load(subprocess.check_output(["git", "-C", str(source), "show", "HEAD:docker/docker-compose.yml"], env=env))
    config = isolated_compose(original, lock)
    os.umask(0o077)
    target.mkdir(parents=True, mode=0o700)
    for path, oid, mode in files:
        output = target / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(subprocess.check_output(["git", "-C", str(source), "cat-file", "blob", oid], env=env))
        output.chmod(0o700 if mode == "100755" else 0o600)
    (target / ".env").write_bytes((target / ".env.example").read_bytes())
    key_script = target / "utils/add-new-auth-keys.sh"
    key_script.write_text(key_script.read_text().replace("node:22-alpine", NODE_IMAGE))
    for name in ("generate-keys.sh", "add-new-auth-keys.sh"):
        result = subprocess.run(["sh", str(target / "utils" / name), "--update-env"], cwd=target, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode:
            raise ValueError("synthetic_key_generation_failed")
    replacements = {"API_EXTERNAL_URL": "http://127.0.0.1:55431", "SUPABASE_PUBLIC_URL": "http://127.0.0.1:55431", "SITE_URL": "http://127.0.0.1:55430", "ADDITIONAL_REDIRECT_URLS": "http://127.0.0.1:55430", "ENABLE_EMAIL_AUTOCONFIRM": "true", "DISABLE_SIGNUP": "false", "POSTGRES_PORT": "5432", "POSTGRES_HOST": "db", "POOLER_TENANT_ID": "madar-rehearsal", "POOLER_DEFAULT_POOL_SIZE": "5", "POOLER_MAX_CLIENT_CONN": "30", "POOLER_DB_POOL_SIZE": "5"}
    text = (target / ".env").read_text()
    for key, value in replacements.items():
        pattern = r"^" + key + r"=.*$"
        text = re.sub(pattern, key + "=" + value, text, flags=re.M) if re.search(pattern, text, re.M) else text + "\n" + key + "=" + value + "\n"
    (target / ".env").write_text(text)
    (target / "docker-compose.yml").write_text(yaml.safe_dump(config, sort_keys=False))
    result = subprocess.run(DOCKER + ["compose", "config", "--quiet"], cwd=target, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode:
        raise ValueError("isolated_compose_validation_failed")
    report = {"status": "prepared_not_started", "upstream_sha": sha, "services": sorted(SERVICES), "compose_sha256": hashlib.sha256((target / "docker-compose.yml").read_bytes()).hexdigest(), "production_configuration_read": False, "full_migration_ready": False}
    (target / "rehearsal-identity.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--lock", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.upstream, args.output, args.lock), indent=2))
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        # Never print arbitrary provider/subprocess exception text.
        print(json.dumps({"status": "failed", "error_type": type(error).__name__}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
