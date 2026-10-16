#!/usr/bin/env python3
"""Restore synthetic database + native object bytes, retaining independent copies."""

from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import PurePosixPath
import secrets
import tarfile
import time

import manage


FINGERPRINT_SQL = """
begin;
create temporary table rehearsal_fingerprints(name text, rows bigint, digest text);
do $$ declare relation record; amount bigint; digest text; begin
  for relation in select schemaname,tablename from pg_catalog.pg_tables
    where schemaname in ('public','auth','storage') order by schemaname,tablename
  loop
    execute format('select count(*),md5(coalesce(jsonb_agg(to_jsonb(t) order by to_jsonb(t)::text)::text,''[]'')) from %I.%I t',
      relation.schemaname,relation.tablename) into amount,digest;
    insert into rehearsal_fingerprints values(relation.schemaname||'.'||relation.tablename,amount,digest);
  end loop;
end $$;
select json_build_object(
  'tables',(select json_object_agg(name,json_build_object('rows',rows,'digest',digest) order by name) from rehearsal_fingerprints),
  'sequences',(select json_object_agg(schemaname||'.'||sequencename,last_value order by schemaname,sequencename)
    from pg_catalog.pg_sequences where schemaname in ('public','auth','storage'))
);
rollback;
"""


def helper(volume, program, *, data=None, writable=False):
    return manage.docker("run", "--rm", "--interactive", "--network=none", "--memory=256m", "--cpus=0.5", "--pids-limit=64",
        "--read-only", "--user=0:0", "--cap-drop=ALL", "--cap-add=DAC_OVERRIDE",
        "--label", "com.madar.staging.owner=" + manage.OWNER,
        "--volume", volume + ":/objects:" + ("rw" if writable else "ro"),
        "--entrypoint", "python", "madar-schema136-preparation-test:working", "-c", program, data=data)


def inventory(volume):
    return json.loads(helper(volume, """
import hashlib,json,pathlib
root=pathlib.Path('/objects')
print(json.dumps({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted(root.rglob('*')) if p.is_file()}))
"""))


def write_binary(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(value)


def main():
    manage.require_database_marker()
    if not (manage.RUNTIME / "smoke-fixture.json").is_file():
        raise RuntimeError("Native MFA/object/worker smoke fixtures must exist before this restore drill")
    schema = int(manage.sql("select schema_version from public.application_schema_state where contract_key='core';"))
    token = secrets.token_hex(8)
    destination = "madar_hardening_restore_" + token
    volume = manage.PROJECT + "_restore_objects_" + token
    evidence = manage.RUNTIME / ("restore-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + token)
    evidence.mkdir(mode=0o700)
    services = ["frontend", "backend", "notification-worker", "gateway", "auth", "storage"]
    # Stop all synthetic writers for one consistent database/object checkpoint.
    # Production services and the pre-existing staging project are unrelated.
    manage.compose("stop", "--timeout", "15", *services)
    started = time.monotonic()
    try:
        before = json.loads(manage.sql(FINGERPRINT_SQL))
        source_volume = manage.PROJECT + "_objects"
        objects_before = inventory(source_volume)
        dump = manage.docker("exec", manage.database_container(), "pg_dump", "-U", "postgres", "-d", "madar_hardening", "-Fc")
        archive = helper(source_volume, "import sys,tarfile; t=tarfile.open(fileobj=sys.stdout.buffer,mode='w|'); t.add('/objects',arcname='.'); t.close()")
        write_binary(evidence / "database.dump", dump)
        write_binary(evidence / "objects.tar", archive)
        manage.docker("exec", "-i", manage.database_container(), "pg_restore", "--list", data=dump)
        # Reject links, devices and path traversal before any extraction.
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            for member in source.getmembers():
                path = PurePosixPath(member.name)
                if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir()):
                    raise RuntimeError("Unsafe synthetic object archive")
        manage.sql(f'create database "{destination}" template template0;')
        manage.sql(f"comment on database \"{destination}\" is '{manage.MARKER}-restore';")
        manage.docker("exec", "-i", manage.database_container(), "pg_restore", "-U", "postgres", "--exit-on-error",
                      "--single-transaction", "-d", destination, data=dump)
        after = json.loads(manage.sql(FINGERPRINT_SQL, database=destination))
        if after != before:
            raise RuntimeError("Restored synthetic database rows or sequence states differ")
        manage.docker("volume", "create", "--label", "com.madar.staging.owner=" + manage.OWNER, volume)
        helper(volume, "import sys,tarfile; t=tarfile.open(fileobj=sys.stdin.buffer,mode='r|'); t.extractall('/objects',filter='data')",
               writable=True, data=archive)
        if inventory(volume) != objects_before:
            raise RuntimeError("Restored synthetic object bytes differ")
        report = {
            "scope": "synthetic logical database and native object byte restore; same PostgreSQL cluster/roles",
            "source_sha": manage.state()["source_sha"], "schema": schema, "restored_database": destination,
            "restored_object_volume": volume, "tables_verified": len(before["tables"]),
            "sequences_verified": len(before["sequences"] or {}), "objects_verified": len(objects_before),
            "mfa_factors_verified": before["tables"]["auth.mfa_factors"]["rows"],
            "database_sha256": hashlib.sha256(dump).hexdigest(), "objects_sha256": hashlib.sha256(archive).hexdigest(),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "limitations": ["not PITR", "not off-host recovery", "not a bare-host role/ACL rebuild",
                            "not full restored-application acceptance or measured production RPO/RTO"],
        }
        (evidence / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        (evidence / "result.json").chmod(0o600)
        print(json.dumps(report, sort_keys=True))
    finally:
        manage.compose("start", "--wait", "--wait-timeout", "90", *services)


if __name__ == "__main__":
    main()
