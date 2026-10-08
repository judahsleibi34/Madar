"""Bounded publication of host-side local backup connectivity.

Database credentials remain in the existing private backup-service environment,
never in application/worker environments. Publication does not run a backup,
alter a freshness attestation, start a timer or restore any database.
"""
from dataclasses import asdict
import os
from pathlib import Path
import re
import shlex

from deployment.lib.provider_recovery_runtime import digest, file_digest, readonly_configuration, protected
from deployment.lib.release_deployer import atomic_json

BACKUP_ENV = Path('/etc/madar/backup.env')
PG_KEYS = frozenset({'PGHOST', 'PGPORT', 'PGUSER', 'PGPASSWORD', 'PGDATABASE', 'PGSSLMODE'})


def native_backup_changes(native):
    password = native.get('POSTGRES_PASSWORD')
    tenant = native.get('POOLER_TENANT_ID')
    if (not password or not isinstance(password, str) or '\n' in password or '\r' in password
            or not isinstance(tenant, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', tenant)):
        raise RuntimeError('local_backup_native_configuration_invalid')
    return {'PGHOST': 'supabase-db', 'PGPORT': '5432', 'PGUSER': 'postgres',
            'PGPASSWORD': password, 'PGDATABASE': 'postgres', 'PGSSLMODE': 'disable'}


def replace_backup_fields(original, changes):
    if set(changes) != PG_KEYS:
        raise RuntimeError('local_backup_field_set_invalid')
    lines = original.splitlines(keepends=True)
    kept = []
    for line in lines:
        match = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=', line)
        if not match or match[1] not in PG_KEYS:
            kept.append(line)
    body = ''.join(kept)
    if body and not body.endswith('\n'):
        body += '\n'
    return body + ''.join(key + '=' + shlex.quote(changes[key]) + '\n' for key in sorted(PG_KEYS))


def verify_backup_input(root, reconciliation, contract, phase):
    expected = reconciliation.get('backup_configuration_before_digest', '')
    if not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise RuntimeError('local_backup_configuration_binding_missing')
    observed = file_digest(readonly_configuration(BACKUP_ENV, private=True))
    receipt_path = root / 'backup-configuration.json'
    if not receipt_path.exists() and not receipt_path.is_symlink():
        if observed == expected:
            return
        raise RuntimeError('local_backup_configuration_changed')
    if phase not in {'resume_pending', 'normal', 'rollback_pending', 'local_rollback_active'}:
        raise RuntimeError('local_backup_configuration_changed')
    import json
    receipt = json.loads(protected(receipt_path, private=True).read_text())
    if receipt != {'version': 1, 'contract_digest': digest(asdict(contract)),
                   'before': expected, 'after': observed}:
        raise RuntimeError('local_backup_configuration_changed')


def publish_backup_configuration(root, reconciliation, contract, native):
    if os.geteuid() != 0:
        raise RuntimeError('local_backup_root_required')
    verify_backup_input(root, reconciliation, contract, 'resume_pending')
    receipt_path = root / 'backup-configuration.json'
    if receipt_path.exists() or receipt_path.is_symlink():
        raise RuntimeError('local_backup_configuration_already_published')
    old = readonly_configuration(BACKUP_ENV, private=True)
    st = old.stat()
    original = old.read_bytes()
    archive = root / 'retired-backup.env'
    with archive.open('xb') as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(original)
        handle.flush(); os.fsync(handle.fileno())
    body = replace_backup_fields(original.decode(), native_backup_changes(native))
    temporary = old.with_name('.normal-local-backup.env')
    with temporary.open('x') as handle:
        os.fchmod(handle.fileno(), 0o600)
        os.fchown(handle.fileno(), st.st_uid, st.st_gid)
        handle.write(body)
        handle.flush(); os.fsync(handle.fileno())
    # The receipt binds this one permitted publication before the new inode is
    # visible. A crash retains the protected archive and a fail-closed packet.
    atomic_json(receipt_path, {'version': 1, 'contract_digest': digest(asdict(contract)),
        'before': reconciliation['backup_configuration_before_digest'], 'after': file_digest(temporary)})
    os.chmod(receipt_path, 0o600)
    os.replace(temporary, old)
    descriptor = os.open(old.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
