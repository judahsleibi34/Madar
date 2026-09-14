#!/usr/bin/env python3
"""Restore a verified logical backup into a disposable, networkless database.

This proves logical database/file recovery, not a replacement Supabase platform
or application readiness. Database roles, ACLs, provider keys and configuration
require their separately reviewed recovery procedure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import uuid


class RehearsalError(RuntimeError):
    pass


def regular_source(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise RehearsalError("source_must_be_absolute_regular_file")
    path = path.resolve(strict=True)
    if "," in str(path):
        raise RehearsalError("source_contains_mount_delimiter")
    return path


def readonly_file_mount(value: str, target: str) -> str:
    return f"type=bind,src={regular_source(value)},dst={target},readonly"


def run(command: list[str], *, phase: str, timeout: int = 180, input: str | None = None) -> str:
    try:
        result = subprocess.run(command, input=input, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RehearsalError(f"{phase}:{type(error).__name__}") from None
    if result.returncode:
        # pg_restore errors can contain COPY rows or SQL literals. Never emit
        # raw database output, even into the sanitized evidence report.
        raise RehearsalError(f"{phase}:exit_{result.returncode}")
    return result.stdout


def file_inventory(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RehearsalError("backup_file_symlink_not_supported")
        if path.is_file():
            with path.open("rb") as handle:
                files[str(path.relative_to(root))] = hashlib.file_digest(handle, "sha256").hexdigest()
        elif not path.is_dir():
            raise RehearsalError("backup_special_file_not_supported")
    return files


def rehearse(backup: Path, image: str, migration: Path | None = None) -> dict:
    if not re.fullmatch(r"[a-zA-Z0-9./:_-]+@sha256:[0-9a-f]{64}", image):
        raise RehearsalError("postgres_image_must_be_digest_pinned")
    regular_source(str(backup / "database.dump"))
    migration_mount = readonly_file_mount(str(migration), "/migration.sql") if migration else None
    manifest = json.loads((backup / "manifest.json").read_text())
    verify = Path(__file__).resolve().with_name("verify_backup.sh")
    run(["bash", str(verify), str(backup)], phase="backup_verification")
    with (backup / "database.dump").open("rb") as handle:
        dump_hash = hashlib.file_digest(handle, "sha256").hexdigest()
    name = "madar-restore-rehearsal-" + uuid.uuid4().hex[:12]
    result = {"backup_id": manifest["backup_id"], "backup_timestamp": manifest["created_at"],
              "backup_schema": int(manifest["database"]["schema_version"]),
              "dump_sha256": dump_hash, "image": image, "container": name,
              "network": "none", "platform_recovery_proven": False}
    # A private readable copy decouples backup ownership from the image
    # account database; initdb requires a named non-root UID. The parent stays
    # mode 0700 and only this file is mounted, read-only, into the container.
    scratch_dump = tempfile.TemporaryDirectory(prefix="madar-dump-restore-")
    staged_dump = Path(scratch_dump.name) / "database.dump"
    try:
        shutil.copyfile(backup / "database.dump", staged_dump)
        staged_dump.chmod(0o444)
        dump_mount = readonly_file_mount(str(staged_dump), "/backup.dump")
    except BaseException:
        scratch_dump.cleanup()
        raise
    command = ["docker", "run", "--detach", "--name", name, "--network", "none",
               "--user", "65534:65534",
               "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
               "--memory", "2g", "--cpus", "2", "--pids-limit", "128",
               "--tmpfs", "/tmp:rw,nosuid,nodev,size=64m,mode=1777",
               "--tmpfs", "/restore-data:rw,nosuid,nodev,size=1g,mode=1777",
               "--mount", dump_mount]
    if migration_mount:
        command += ["--mount", migration_mount]
    command += ["--entrypoint", "sh", image, "-ec",
                "initdb -D /restore-data/pgdata -U postgres --auth=trust >/dev/null; "
                "exec postgres -D /restore-data/pgdata -k /tmp -c listen_addresses='' "
                "-c log_statement=none -c log_min_error_statement=panic"]
    created = False
    started = time.monotonic()
    try:
        run(command, phase="database_start")
        created = True
        for _ in range(60):
            ready = subprocess.run(["docker", "exec", name, "pg_isready", "-h", "/tmp", "-U", "postgres"], capture_output=True, timeout=10)
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RehearsalError("database_start_timeout")
        psql = ["docker", "exec", "-i", name, "psql", "-X", "-h", "/tmp", "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-At"]
        # Logical dumps exclude cluster roles. NOLOGIN prerequisites only; this
        # rehearsal must never be mistaken for a live authorization bootstrap.
        run(psql, phase="role_prerequisites", input="CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN; CREATE ROLE service_role NOLOGIN;\n")
        restore_started = time.monotonic()
        run(["docker", "exec", name, "pg_restore", "--exit-on-error", "--single-transaction",
             "--no-owner", "--no-acl", "-h", "/tmp", "-U", "postgres", "-d", "postgres", "/backup.dump"], phase="full_database_restore")
        result["restore_seconds"] = round(time.monotonic() - restore_started, 3)
        schema = int(run(psql, phase="restored_schema", input="SELECT schema_version FROM public.application_schema_state WHERE contract_key='core';"))
        if schema != result["backup_schema"]:
            raise RehearsalError("restored_schema_mismatch")
        result["restored_schema"] = schema
        if migration:
            run(psql + ["--file", "/migration.sql"], phase="isolated_migration")
        rows = run(psql, phase="metadata_validation", input="""
SELECT 'schema='||schema_version FROM public.application_schema_state WHERE contract_key='core';
SELECT 'public_tables='||count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r';
SELECT 'invalid_indexes='||count(*) FROM pg_index WHERE NOT indisvalid;
SELECT 'auth_users='||count(*) FROM auth.users;
""")
        result["metadata"] = dict(line.split("=", 1) for line in rows.splitlines())
        if result["metadata"]["invalid_indexes"] != "0":
            raise RehearsalError("invalid_restored_indexes")
        expected_tables = manifest['database'].get('public_tables')
        if expected_tables is not None and int(result['metadata']['public_tables']) != expected_tables:
            raise RehearsalError('restored_public_table_count_mismatch')
        if schema == 96:
            projection = run(psql, phase="schema96_order_confirmation_projection", input="""
BEGIN;
DO $$
DECLARE v_tenant integer; v_order uuid;
BEGIN
  SELECT tenant_id INTO v_tenant FROM public.tenants ORDER BY tenant_id LIMIT 1;
  IF v_tenant IS NULL THEN RAISE EXCEPTION 'schema96_fixture_tenant_missing'; END IF;
  INSERT INTO public.ecommerce_orders (
    tenant_id,order_number,status,payment_status,payment_method,currency,
    subtotal,discount_total,total,customer_name,customer_email,customer_phone,
    address_line_1,city,country
  ) VALUES (
    v_tenant,'SCHEMA96-RECOVERY-FIXTURE','pending','unpaid','cash_on_delivery','ILS',
    10,0,10,'Synthetic','synthetic@example.invalid','000','fixture','fixture','PS'
  ) RETURNING id INTO v_order;
  INSERT INTO public.ecommerce_order_items (
    tenant_id,order_id,product_id,sku,product_name,quantity,unit_price,line_total,
    product_slug,product_snapshot,list_unit_price,discount_amount,discount_source
  ) VALUES (
    v_tenant,v_order,NULL,'SCHEMA96-FIXTURE','Synthetic item',1,10,10,
    'synthetic-item','{}'::jsonb,10,0,NULL
  );
END $$;
SELECT count(*) FROM public.ecommerce_order_items
WHERE sku='SCHEMA96-FIXTURE' AND product_snapshot='{}'::jsonb
  AND unit_price=10 AND line_total=10;
ROLLBACK;
""").splitlines()
            if projection != ["BEGIN", "DO", "1", "ROLLBACK"]:
                raise RehearsalError("schema96_order_confirmation_projection_failed")
            post96_column = run(psql, phase="schema96_post96_column_absence", input="""
SELECT count(*) FROM information_schema.columns
WHERE table_schema='public' AND table_name='ecommerce_order_items'
  AND column_name='loyalty_entitlement_id';
""").strip()
            if post96_column != "0":
                raise RehearsalError("schema96_unexpected_post96_column")
            result["schema96_order_confirmation_projection"] = "passed"
        file_sets = {}
        with tempfile.TemporaryDirectory(prefix="madar-file-restore-") as scratch:
            for name_set in ("builder-assets", "private-uploads", "generated-artifacts", "avatars"):
                source = backup / "files" / name_set
                if not source.is_dir() or source.is_symlink():
                    raise RehearsalError("backup_file_set_missing")
                before = file_inventory(source)
                target = Path(scratch) / name_set
                shutil.copytree(source, target, symlinks=True)
                if file_inventory(target) != before:
                    raise RehearsalError("file_restore_checksum_mismatch")
                file_sets[name_set] = {"files": len(before), "checksums_match": True}
        result["file_sets"] = file_sets
        if manifest.get('recovery', {}).get('provider_objects_required'):
            source = backup / 'provider'
            before = file_inventory(source)
            with tempfile.TemporaryDirectory(prefix='madar-provider-restore-') as scratch:
                target = Path(scratch) / 'provider'
                shutil.copytree(source, target, symlinks=True)
                if file_inventory(target) != before:
                    raise RehearsalError('provider_restore_checksum_mismatch')
                provider = json.loads((target / 'manifest.json').read_text())
                result['provider_objects'] = {'objects': len(provider['objects']), 'checksums_match': True,
                                              'remote_provider_restore_performed': False}
        result["status"] = "logical_database_and_file_restore_passed"
    finally:
        try:
            if created:
                run(["docker", "rm", "--force", name], phase="disposable_cleanup")
                result["disposable_target_removed"] = True
        finally:
            scratch_dump.cleanup()
    result["total_seconds"] = round(time.monotonic() - started, 3)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    parser.add_argument("--postgres-image", required=True)
    parser.add_argument("--migration", type=Path)
    args = parser.parse_args()
    try:
        report = rehearse(args.backup, args.postgres_image, args.migration)
    except (RehearsalError, OSError, ValueError, KeyError) as error:
        print(json.dumps({"status": "failed", "error": str(error) if isinstance(error, RehearsalError) else type(error).__name__}))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
