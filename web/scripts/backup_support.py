#!/usr/bin/env python3
"""Private backup integrity, provider snapshots, freshness and retention.

Only aggregate diagnostics leave this module. Provider bytes are logical
recovery material, never proof of a replacement Supabase platform.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import urllib.request
from urllib.parse import quote, urlsplit

BACKUP_ID = re.compile(r"madar-[0-9]{8}T[0-9]{6}Z\Z")
FILE_SETS = ("builder-assets", "private-uploads", "generated-artifacts", "avatars")
MAX_OBJECTS = 100000
MAX_OBJECT_BYTES = 512 * 1024 * 1024


class BackupError(RuntimeError):
    pass


def real_path(path: Path, *, directory: bool = True) -> Path:
    if not path.is_absolute() or '..' in path.parts:
        raise BackupError('path_must_be_absolute_without_traversal')
    for item in (path, *path.parents):
        if item.is_symlink():
            raise BackupError('symlink_path_rejected')
    if directory and not path.is_dir():
        raise BackupError('directory_missing')
    return path


def digest(path: Path) -> str:
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def inventory(root: Path) -> dict[str, str]:
    real_path(root)
    result = {}
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(base) / name
            mode = path.lstat().st_mode
            if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise BackupError('special_or_symlink_backup_member')
            if stat.S_ISREG(mode):
                result[str(path.relative_to(root))] = digest(path)
    return result


def verify(root: Path, *, dump: bool = True) -> dict:
    real_path(root)
    required = ['backup.env', 'database.dump', 'SHA256SUMS']
    for name in FILE_SETS:
        real_path(root / 'files' / name)
    for name in required:
        if not (root / name).is_file():
            raise BackupError('missing_backup_member')
    actual = inventory(root)
    sums = {}
    for line in (root / 'SHA256SUMS').read_text().splitlines():
        # sha256sum escapes backslashes/newlines. Decode only its documented
        # filename escapes; reject traversal, duplicate names and absolute paths.
        escaped = line.startswith('\\')
        if escaped:
            line = line[1:]
        if not re.match(r'^[0-9a-f]{64} [ *]', line):
            raise BackupError('checksum_manifest_invalid')
        name = line[66:]
        if escaped:
            name = re.sub(r'\\([\\n])', lambda m: '\n' if m[1] == 'n' else '\\', name)
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts:
            raise BackupError('checksum_path_invalid')
        name = str(path)
        if name in sums or name == 'SHA256SUMS':
            raise BackupError('checksum_duplicate_or_recursive')
        sums[name] = line[:64]
    actual.pop('SHA256SUMS')
    if sums != actual:
        raise BackupError('checksum_verification_failed')
    formats = [line.split('=', 1)[1] for line in (root / 'backup.env').read_text().splitlines()
               if line.startswith('MADAR_BACKUP_FORMAT=')]
    if len(formats) != 1 or formats[0] not in ('1', '2', '3'):
        raise BackupError('unsupported_backup_format')
    manifest = {}
    if formats[0] in ('2', '3') and not (root / 'BACKUP_COMPLETE').is_file():
        raise BackupError('completion_marker_missing')
    if formats[0] == '3':
        manifest = json.loads((root / 'manifest.json').read_text())
        if (manifest.get('format_version') != 3 or manifest.get('status') != 'complete'
                or not BACKUP_ID.fullmatch(manifest.get('backup_id', ''))
                or manifest.get('database', {}).get('dump') != 'database.dump'
                or manifest.get('checksums') != 'SHA256SUMS'
                or manifest.get('configuration', {}).get('values_included') is not False
                or set(manifest.get('file_sets', [])) != set(FILE_SETS)
                or manifest.get('created_at') != manifest.get('backup_id', '')[6:]):
            raise BackupError('backup_manifest_invalid')
        datetime.strptime(manifest['created_at'], '%Y%m%dT%H%M%SZ')
        for name in ('MANIFEST.txt', 'CONFIGURATION-INVENTORY.txt'):
            if not (root / name).is_file():
                raise BackupError('missing_backup_member')
        recovery = manifest.get('recovery', {})
        if recovery.get('provider_objects_required'):
            provider = json.loads((root / 'provider/manifest.json').read_text())
            if (provider.get('database_backup_id') != manifest['backup_id']
                    or provider.get('status') != 'complete'
                    or provider.get('platform_recovery_proven') is not False):
                raise BackupError('provider_manifest_invalid')
            objects = provider['objects']
            expected = {}
            for row in objects:
                leaf = hashlib.sha256(json.dumps([row['bucket_id'], row['name']], ensure_ascii=False).encode()).hexdigest()
                name = 'objects/' + leaf
                if row['file'] != name or name in expected:
                    raise BackupError('provider_object_identity_invalid')
                target = root / 'provider' / name
                if target.stat().st_size != row['bytes'] or digest(target) != row['sha256']:
                    raise BackupError('provider_object_integrity_failed')
                expected[name] = row['sha256']
            if inventory(root / 'provider/objects') != {k[8:]: v for k, v in expected.items()}:
                raise BackupError('provider_object_inventory_mismatch')
        elif (root / 'provider').exists():
            raise BackupError('undeclared_provider_objects')
    if dump:
        result = subprocess.run(['pg_restore', '--list', str(root / 'database.dump')],
                                capture_output=True, timeout=180)
        if result.returncode:
            raise BackupError('database_dump_unreadable')
    return manifest


def atomic_text(path: Path, text: str, mode: int = 0o600) -> None:
    real_path(path.parent)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise BackupError('marker_target_invalid')
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def latest(marker: Path, root: Path, max_age: int = 129600) -> Path:
    real_path(marker, directory=False)
    real_path(root)
    fields = marker.read_text().strip().split(' ', 1)
    if len(fields) != 2:
        raise BackupError('latest_marker_invalid')
    timestamp, name = fields
    path = Path(name)
    if path.parent != root or not BACKUP_ID.fullmatch(path.name) or path.name != 'madar-' + timestamp:
        raise BackupError('latest_target_outside_backup_root')
    created = datetime.strptime(timestamp, '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - created).total_seconds()
    if max_age <= 0 or not 0 <= age <= max_age:
        raise BackupError('latest_backup_stale')
    verify(path)
    return path


def publish_marker(root: Path, marker: Path, state: Path | None) -> None:
    manifest = verify(root)
    if root.name != manifest['backup_id']:
        raise BackupError('published_backup_identity_mismatch')
    created = manifest['created_at']
    atomic_text(marker, f'{created} {root}\n')
    if state is not None:
        real_path(state)
        # Deliberately omit host paths, provider identifiers and customer names.
        document = {'format': 1, 'backup_id': root.name, 'created_at': created,
                    'verified': True, 'manifest_sha256': digest(root / 'manifest.json')}
        atomic_text(state / 'latest.json', json.dumps(document) + '\n', 0o644)


def retention(root: Path, current: Path, keep: int) -> list[str]:
    real_path(root)
    if current.parent != root or not BACKUP_ID.fullmatch(current.name):
        raise BackupError('retention_current_invalid')
    verify(current, dump=False)
    if keep < 2:
        raise BackupError('retention_minimum_two')
    managed = []
    for path in sorted(root.iterdir(), reverse=True):
        if not BACKUP_ID.fullmatch(path.name) or path.is_symlink() or not path.is_dir():
            continue
        # Only new-contract complete verified backups are managed. Historical
        # backups and unknown entries are never adopted for deletion.
        try:
            manifest = verify(path, dump=False)
            if manifest.get('retention_managed') is True and manifest.get('backup_id') == path.name:
                managed.append(path)
        except (BackupError, OSError, ValueError, KeyError):
            continue
    protected = set(managed[:keep]) | {current}
    removed = []
    for path in managed:
        if path in protected:
            continue
        # Revalidate immediately before fd-safe rmtree; never follow symlinks.
        verify(path, dump=False)
        if not shutil.rmtree.avoids_symlink_attacks:
            raise BackupError('safe_retention_unavailable')
        shutil.rmtree(path)
        removed.append(path.name)
    return removed


def provider_inventory() -> list[dict]:
    env = dict(os.environ, PGCONNECT_TIMEOUT='10',
               PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=30000')
    sql = """select coalesce(json_agg(x order by bucket_id,name),'[]'::json) from
      (select bucket_id,name,updated_at,metadata->>'size' as size
       from storage.objects order by bucket_id,name limit 100001) x;"""
    result = subprocess.run(['psql', '-X', '-At', '-v', 'ON_ERROR_STOP=1', '-c', sql],
                            env=env, capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise BackupError('provider_inventory_failed')
    rows = json.loads(result.stdout)
    if not isinstance(rows, list) or len(rows) > MAX_OBJECTS:
        raise BackupError('provider_inventory_limit')
    return rows


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise BackupError('provider_redirect_rejected')


def provider_snapshot(root: Path, backup_id: str) -> None:
    base = os.environ.get('SUPABASE_URL', '').rstrip('/')
    parsed = urlsplit(base)
    key = os.environ.get('SUPABASE_SERVICE_KEY', '')
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path or not key):
        raise BackupError('provider_configuration_invalid')
    before = json.loads((root / 'provider-inventory.json').read_text())
    destination = root / 'provider'
    destination.mkdir(mode=0o700)
    (destination / 'objects').mkdir(mode=0o700)
    headers = {'apikey': key}
    if not key.startswith('sb_secret_'):
        headers['Authorization'] = 'Bearer ' + key
    opener = urllib.request.build_opener(NoRedirect())
    objects = []
    for row in before:
        bucket, name = row['bucket_id'], row['name']
        # URL path normalization must never redirect an authenticated request.
        if any(p in ('.', '..') for p in name.split('/')) or '/' in bucket:
            raise BackupError('provider_object_path_invalid')
        leaf = hashlib.sha256(json.dumps([bucket, name], ensure_ascii=False).encode()).hexdigest()
        target = destination / 'objects' / leaf
        size = 0
        url = base + '/storage/v1/object/authenticated/' + quote(bucket, safe='') + '/' + quote(name, safe='/')
        try:
            with opener.open(urllib.request.Request(url, headers=headers), timeout=30) as response, target.open('xb') as output:
                if response.status != 200:
                    raise BackupError('provider_download_status')
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_OBJECT_BYTES:
                        raise BackupError('provider_object_too_large')
                    output.write(chunk)
        except Exception:
            raise BackupError('provider_download_failed') from None
        if row.get('size') is not None and size != int(row['size']):
            raise BackupError('provider_object_size_mismatch')
        objects.append({**row, 'file': 'objects/' + leaf, 'bytes': size, 'sha256': digest(target)})
    if before != provider_inventory():
        raise BackupError('provider_inventory_changed_retry_required')
    coverage = registry_coverage(root, objects)
    manifest = {'format': 1, 'status': 'complete', 'database_backup_id': backup_id,
                'builder_registry_coverage': coverage,
                'platform_recovery_proven': False, 'objects': objects}
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (root / 'provider-inventory.json').unlink()


def registry_coverage(root: Path, objects: list[dict]) -> dict:
    sql = """select coalesce(json_agg(x),'[]'::json) from
      (select b.storage_key,b.sha256,b.status,
       (select count(*) from public.builder_asset_references r where r.asset_id=b.id) as references
       from public.builder_assets b where b.status <> 'soft_deleted') x;"""
    env = dict(os.environ, PGCONNECT_TIMEOUT='10',
               PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=30000')
    result = subprocess.run(['psql','-X','-At','-v','ON_ERROR_STOP=1','-c',sql],
                            env=env, capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise BackupError('builder_registry_inventory_failed')
    rows = json.loads(result.stdout)
    provider = {(row['bucket_id'], row['name']): row['sha256'] for row in objects}
    missing_unreferenced = []
    covered = 0
    for row in rows:
        key = PurePosixPath(row['storage_key'])
        if key.is_absolute() or '..' in key.parts:
            raise BackupError('builder_registry_path_invalid')
        local = root / 'files/builder-assets' / str(key)
        local_hash = digest(local) if local.is_file() and not local.is_symlink() else None
        provider_hash = provider.get((os.environ.get('BUILDER_ASSET_BUCKET', 'builder-assets'), str(key)))
        if any(value is not None and value != row['sha256'] for value in (local_hash, provider_hash)):
            raise BackupError('builder_registry_content_hash_mismatch')
        if local_hash is not None or provider_hash is not None:
            covered += 1
        elif row['status'] == 'active' or int(row['references']) > 0:
            raise BackupError('required_builder_asset_missing')
        else:
            # Preserve the existing registry in the DB dump. Do not manufacture
            # bytes or delete historical dangling records to claim recovery.
            missing_unreferenced.append(hashlib.sha256(str(key).encode()).hexdigest())
    return {'registry_rows':len(rows), 'covered':covered, 'required_missing':0,
            'preexisting_unreferenced_missing_key_hashes':sorted(missing_unreferenced)}


def scheduled(script: Path) -> None:
    # systemd hands only this service a private credential copy. The production
    # dotenv file also contains legacy colon assignments: never shell-source it.
    credential = Path(os.environ['CREDENTIALS_DIRECTORY']) / 'production.env'
    found = {}
    for line in credential.read_text().splitlines():
        match = re.match(r'^\s*(SUPABASE_URL|SUPABASE_SERVICE_KEY)\s*[=:]\s*(.*)$', line)
        if not match:
            continue
        value = match[2].strip()
        value = ast.literal_eval(value) if value[:1] in ('"', "'") else re.split(r'\s+#', value, maxsplit=1)[0]
        if not isinstance(value, str) or not value:
            raise BackupError('provider_credential_invalid')
        found[match[1]] = value
    if set(found) != {'SUPABASE_URL', 'SUPABASE_SERVICE_KEY'}:
        raise BackupError('provider_credentials_missing')
    state = json.loads((Path(os.environ['MADAR_DEPLOY_STATE_ROOT']) / 'state.json').read_text())
    release = state['known_good_release']
    with urllib.request.urlopen('http://127.0.0.1:8001/health/version', timeout=10) as response:
        live = json.load(response)
    if live.get('release_sha') != release['sha'] or not re.fullmatch(r'[0-9a-f]{40}', release['sha']):
        raise BackupError('backup_live_release_mismatch')
    env = dict(os.environ, **found, MADAR_RELEASE_SHA=release['sha'],
               MADAR_BUILD_TIMESTAMP=live['build_timestamp'], MADAR_PROVIDER_BACKUP_REQUIRED='true')
    os.execve('/bin/bash', ['bash', str(script)], env)


def main() -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['verify', 'inventory', 'provider-before', 'provider-after', 'publish', 'latest', 'retain', 'scheduled'])
    parser.add_argument('path', type=Path)
    parser.add_argument('extra', nargs='?')
    args = parser.parse_args()
    try:
        if args.operation == 'scheduled':
            scheduled(args.path)
        elif args.operation == 'verify':
            verify(args.path)
        elif args.operation == 'inventory':
            inventory(args.path)
        elif args.operation == 'provider-before':
            (args.path / 'provider-inventory.json').write_text(json.dumps(provider_inventory()))
        elif args.operation == 'provider-after':
            provider_snapshot(args.path, args.extra)
        elif args.operation == 'publish':
            state = os.environ.get('MADAR_BACKUP_STATE_DIR')
            publish_marker(args.path, Path(os.environ['MADAR_BACKUP_FRESHNESS_MARKER']), Path(state) if state else None)
        elif args.operation == 'latest':
            path = latest(args.path, Path(os.environ['MADAR_BACKUP_DIR']), int(os.environ.get('MADAR_BACKUP_MAX_AGE_SECONDS', '129600')))
            print(path)
        elif args.operation == 'retain':
            removed = retention(args.path, Path(args.extra), int(os.environ.get('MADAR_BACKUP_KEEP_COUNT', '30')))
            print(json.dumps({'retention_removed_backup_ids': removed}))
    except Exception as error:
        print('ERROR: ' + (str(error) if isinstance(error, BackupError) else type(error).__name__), file=__import__('sys').stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
