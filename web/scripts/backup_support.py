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
import fcntl
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import time
import urllib.request
import tarfile
import base64
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
                or type(manifest.get('configuration', {}).get('values_included')) is not bool
                or set(manifest.get('file_sets', [])) != set(FILE_SETS)
                or manifest.get('created_at') != manifest.get('backup_id', '')[6:]):
            raise BackupError('backup_manifest_invalid')
        datetime.strptime(manifest['created_at'], '%Y%m%dT%H%M%SZ')
        coordinated = manifest.get('coordinated_checkpoint')
        if manifest['configuration']['values_included'] is True:
            if coordinated != 'coordinated/manifest.json':
                raise BackupError('coordinated_checkpoint_required')
            verify_coordinated_checkpoint(root)
        elif coordinated is not None:
            raise BackupError('coordinated_checkpoint_configuration_undeclared')
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
        maintenance = manifest.get('maintenance_backup')
        if maintenance is not None:
            if maintenance != 'maintenance/manifest.json' or recovery.get('provider_objects_required') is not False:
                raise BackupError('maintenance_backup_contract_invalid')
            verify_maintenance(root)
        elif (root / 'maintenance').exists():
            raise BackupError('undeclared_maintenance_backup')
    if dump:
        result = subprocess.run(['pg_restore', '--list', str(root / 'database.dump')],
                                capture_output=True, timeout=180)
        if result.returncode:
            raise BackupError('database_dump_unreadable')
    return manifest


def verify_maintenance(root: Path, *, expected_sha256: str | None = None) -> dict:
    """Verify maintenance recovery material, never authorize its use.

    A protected consumer must independently pin the inner manifest digest. The
    ordinary sender, receiver and isolated restore share this byte contract.
    No saved SQL is executed and no original host path is opened here.
    """
    directory = root/'maintenance'
    real_path(directory)
    path = directory/'manifest.json'
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(descriptor,'rb') as source:
        metadata=os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size>256*1024:
            raise BackupError('maintenance_manifest_changed')
        body=source.read(256*1024+1)
    # Hash and parse the same bounded descriptor capture. Published backups may
    # be runtime-owned; checking a pathname and reopening it is not custody.
    if len(body)>256*1024 or expected_sha256 is not None and hashlib.sha256(body).hexdigest()!=expected_sha256:
        raise BackupError('maintenance_manifest_changed')
    value = json.loads(body)
    keys = {'version','binding','stage','schema','bootstrap_role','roles_sha256','roles_snapshot_sha256',
            'objects_sha256','objects_measurement','database_fingerprint','recovery','authority_issued'}
    if (not isinstance(value,dict) or set(value)!=keys or type(value['version']) is not int or value['version']!=1
            or value['authority_issued'] is not False or value['stage'] not in {'pre-migration','post-migration'}
            or type(value['schema']) is not int or value['schema']<=0
            or not re.fullmatch('[a-zA-Z_][a-zA-Z0-9_]*',str(value['bootstrap_role']))
            or any(not re.fullmatch('[0-9a-f]{64}',str(value[k])) for k in
                   ('roles_sha256','roles_snapshot_sha256','objects_sha256','database_fingerprint'))):
        raise BackupError('maintenance_manifest_invalid')
    binding=value['binding']
    if (not isinstance(binding,dict) or set(binding)!={'operation','context_sha256','source_sha','controller_sha',
            'inventory_sha256','system_identifier','source_schema','target_schema'}
            or not isinstance(binding['operation'],str) or not re.fullmatch('[a-z0-9-]{1,160}',binding['operation'])
            or any(not re.fullmatch('[0-9a-f]{64}',str(binding[k])) for k in ('context_sha256','inventory_sha256'))
            or any(not re.fullmatch('[0-9a-f]{40}',str(binding[k])) for k in ('source_sha','controller_sha'))
            or not re.fullmatch('[1-9][0-9]{0,19}',str(binding['system_identifier']))
            or any(type(binding[k]) is not int or binding[k]<=0 for k in ('source_schema','target_schema'))
            or binding['source_schema']>=binding['target_schema']
            or value['schema']!=binding['source_schema' if value['stage']=='pre-migration' else 'target_schema']):
        raise BackupError('maintenance_binding_invalid')
    recovery=value['recovery']
    if (not isinstance(recovery,dict) or set(recovery)!={'origin_source_sha','origin_images','candidate_images',
            'database_image','migration_manifest_sha256','controller_tree_sha256','configuration_sha256','configuration_escrow_required'}
            or recovery['configuration_escrow_required'] is not True
            or not re.fullmatch('[0-9a-f]{40}',str(recovery['origin_source_sha']))
            or any(not re.fullmatch('[0-9a-f]{64}',str(recovery[k])) for k in ('migration_manifest_sha256','controller_tree_sha256'))
            or not re.fullmatch('sha256:[0-9a-f]{64}',str(recovery['database_image']))
            or not isinstance(recovery['configuration_sha256'],dict) or not recovery['configuration_sha256']
            or len(recovery['configuration_sha256'])>64
            or any(not isinstance(k,str) or not re.fullmatch('[0-9a-f]{64}',str(v)) for k,v in recovery['configuration_sha256'].items())):
        raise BackupError('maintenance_recovery_context_invalid')
    for key in ('origin_images','candidate_images'):
        images=recovery[key]
        if (not isinstance(images,dict) or set(images)!={'backend','frontend'}
                or any(not re.fullmatch('sha256:[0-9a-f]{64}',str(v)) for v in images.values())):
            raise BackupError('maintenance_recovery_images_invalid')
    expected={'manifest.json','roles.sql','roles-snapshot.json','objects.tar.gz'}
    if {p.name for p in directory.iterdir()}!=expected:
        raise BackupError('maintenance_inventory_invalid')
    for name,key,limit in (('roles.sql','roles_sha256',4*1024**2),
                           ('roles-snapshot.json','roles_snapshot_sha256',4*1024**2),
                           ('objects.tar.gz','objects_sha256',2*1024**3)):
        target=directory/name
        if (target.is_symlink() or not target.is_file() or not 0<target.stat().st_size<=limit
                or digest(target)!=value[key]):
            raise BackupError('maintenance_member_changed')
    snapshot=json.loads((directory/'roles-snapshot.json').read_bytes())
    if not isinstance(snapshot,dict) or set(snapshot)!={'roles','memberships','settings'}:
        raise BackupError('maintenance_roles_snapshot_invalid')
    saved=(directory/'roles.sql').read_text()
    create='CREATE ROLE '+value['bootstrap_role']+';'
    if (saved.splitlines().count(create)!=1 or not re.search(
            '^ALTER ROLE '+re.escape(value['bootstrap_role'])+r' WITH SUPERUSER\b',saved,re.M)):
        raise BackupError('maintenance_bootstrap_invalid')
    measurement=value['objects_measurement']
    allowed={'provider_storage','builder_assets','private_uploads','generated_artifacts','avatars','datasets'}
    if (not isinstance(measurement,dict) or set(measurement)!={'version','phase','roots'}
            or measurement['version']!=1 or measurement['phase']!='fenced'
            or not isinstance(measurement['roots'],dict)
            or not allowed-{'datasets'} <= set(measurement['roots'])-{'database'} <= allowed):
        raise BackupError('maintenance_object_measurement_invalid')
    records={name:[] for name in measurement['roots'] if name!='database'}; seen=set(); total=0
    with tarfile.open(directory/'objects.tar.gz',mode='r|gz') as archive:
        for index,member in enumerate(archive):
            parts=PurePosixPath(member.name).parts
            if (index>=131072 or not parts or parts[0] not in records
                    or member.name!=PurePosixPath(member.name).as_posix() or '..' in parts
                    or member.name in seen or member.sparse or not (member.isfile() or member.isdir())
                    or member.size<0 or member.size>128*1024**2):
                raise BackupError('maintenance_object_archive_invalid')
            seen.add(member.name);total+=member.size
            if total>1536*1024**2:raise BackupError('maintenance_object_archive_limit')
            attributes=json.loads(member.pax_headers.get('madar.xattrs.base64','{}'))
            if not isinstance(attributes,dict) or len(json.dumps(attributes))>65536:
                raise BackupError('maintenance_object_xattr_invalid')
            for name,raw in attributes.items():
                if not isinstance(name,str) or '\0' in name or not isinstance(raw,str):
                    raise BackupError('maintenance_object_xattr_invalid')
                try:base64.b64decode(raw,validate=True)
                except ValueError:raise BackupError('maintenance_object_xattr_invalid') from None
            if len(parts)==1:
                identity=measurement['roots'][parts[0]]['identity']
                if not member.isdir() or (member.mode,member.uid,member.gid)!=(identity['mode'],identity['uid'],identity['gid']):
                    raise BackupError('maintenance_object_root_metadata_changed')
                continue
            relative='/'.join(parts[1:]); row=[relative,'directory' if member.isdir() else 'file',member.mode,member.uid,member.gid]
            if member.isfile():
                with archive.extractfile(member) as stream: checksum=hashlib.file_digest(stream,'sha256').hexdigest()
                row.extend([member.size,checksum])
            records[parts[0]].append(row)
    for name,rows in records.items():
        rows.sort(key=lambda row:tuple(PurePosixPath(row[0]).parts))
        checksum=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
        content=measurement['roots'][name]['content']
        actual={'sha256':checksum,'entries':len(rows),'files':sum(r[1]=='file' for r in rows),
                'bytes':sum(r[5] for r in rows if r[1]=='file')}
        if actual!=content:raise BackupError('maintenance_object_capture_mismatch')
    return value


ROLE_SNAPSHOT_SQL = """SELECT json_build_object(
 'roles',(SELECT coalesce(json_object_agg(rolname,to_jsonb(r)-'oid'),'{}'::json) FROM pg_authid r),
 'memberships',(SELECT coalesce(json_agg(json_build_object('role',roleid::regrole::text,
 'member',member::regrole::text,'grantor',grantor::regrole::text,'admin_option',admin_option,
 'inherit_option',inherit_option,'set_option',set_option) ORDER BY roleid::regrole::text,member::regrole::text),'[]'::json)
 FROM pg_auth_members),
 'settings',(SELECT coalesce(json_agg(json_build_object('role',setrole::regrole::text,
 'database',coalesce(d.datname,''),'settings',setconfig) ORDER BY setrole::regrole::text,coalesce(d.datname,'')),
 '[]'::json) FROM pg_db_role_setting s LEFT JOIN pg_database d ON d.oid=s.setdatabase));"""


def database_snapshot(query) -> list:
    """Measure data, sequences and role-based ownership/ACLs, with no raw rows.

    query is a fixed code-owned read-only transport, never serialized evidence.
    Callers must retain quiescence; bounded server timeouts fail on large data
    instead of claiming a partial recovery. Restore cluster OIDs may differ.
    """
    rows=json.loads(query("SELECT coalesce(json_agg(json_build_object('schema',n.nspname,'name',c.relname,"
        "'kind',c.relkind) ORDER BY n.nspname,c.relname),'[]'::json) FROM pg_class c JOIN pg_namespace n "
        "ON n.oid=c.relnamespace WHERE n.nspname IN ('public','auth','storage') AND c.relkind IN ('r','p','S');"))
    if not isinstance(rows,list) or not 0<len(rows)<=4096:raise BackupError('maintenance_relation_inventory_invalid')
    def identifier(value):
        if not isinstance(value,str) or not value or len(value.encode())>63 or '\0' in value:
            raise BackupError('maintenance_relation_inventory_invalid')
        return '"'+value.replace('"','""')+'"'
    statements=[]
    for row in rows:
        table=identifier(row['schema'])+'.'+identifier(row['name'])
        name=json.dumps([row['schema'],row['name']],separators=(',',':')).replace("'","''")
        if row['kind']=='S':
            statements.append("SELECT json_build_array('"+name+"',last_value,is_called)::text FROM "+table+';')
        else:
            statements.append("SELECT json_build_array('"+name+"',count(*),encode(sha256(convert_to(coalesce("
                "string_agg(h,'' ORDER BY h COLLATE \"C\"),''),'UTF8')),'hex'))::text FROM "
                "(SELECT encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') h FROM "+table+' t) rows;')
    statements.append("SELECT json_build_object('database',(SELECT json_build_array(datname,datdba::regrole::text,datacl) "
        "FROM pg_database WHERE datname=current_database()),'relations',(SELECT json_agg(json_build_array(n.nspname,"
        "c.relname,c.relkind,c.relowner::regrole::text,c.relacl,c.relrowsecurity,c.relforcerowsecurity) "
        "ORDER BY n.nspname,c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname IN ('public','auth','storage')),'schemas',(SELECT json_agg(json_build_array(nspname,"
        "nspowner::regrole::text,nspacl) ORDER BY nspname) FROM pg_namespace WHERE nspname IN ('public','auth','storage')),"
        "'functions',(SELECT json_agg(json_build_array(n.nspname,p.proname,pg_get_function_identity_arguments(p.oid),"
        "p.proowner::regrole::text,p.proacl,p.prosecdef,p.proconfig,pg_get_functiondef(p.oid)) ORDER BY "
        "n.nspname,p.proname,pg_get_function_identity_arguments(p.oid)) FROM pg_proc p JOIN pg_namespace n "
        "ON n.oid=p.pronamespace WHERE n.nspname IN ('public','auth','storage') AND p.prokind IN ('f','p')))::text;")
    raw=query('\n'.join(statements))
    packet=[json.loads(line) for line in raw.splitlines() if line.strip()]
    if len(packet)!=len(rows)+1:raise BackupError('maintenance_database_fingerprint_incomplete')
    # pg_restore may emit semantically identical ACL items in a different array
    # order. Keep every privilege/grantee/grantor token (including duplicates),
    # and distinguish NULL/default ACLs from an explicitly empty ACL.
    metadata=packet[-1]
    grants=[(metadata['database'],2)]
    for key,index in (('relations',4),('schemas',2),('functions',4)):
        grants.extend((row,index) for row in metadata[key] or [])
    for row,index in grants:
        if row[index] is not None:
            if not isinstance(row[index],list) or any(not isinstance(item,str) for item in row[index]):
                raise BackupError('maintenance_acl_snapshot_invalid')
            row[index]=sorted(row[index])
    return packet


def database_fingerprint(query) -> str:
    packet=database_snapshot(query)
    return hashlib.sha256(json.dumps(packet,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()


def verify_coordinated_checkpoint(root: Path) -> None:
    """Verify opt-in native recovery escrow without relaxing ordinary backups."""
    directory = real_path(root / 'coordinated')
    manifest_path = real_path(directory / 'manifest.json', directory=False)
    if directory.stat().st_mode & 0o077 or manifest_path.stat().st_mode & 0o077:
        raise BackupError('coordinated_checkpoint_integrity_failed')
    checkpoint = json.loads(manifest_path.read_text())
    if checkpoint.get('schema') != 115 or checkpoint.get('restore_verified') is not True:
        raise BackupError('coordinated_checkpoint_restore_unverified')
    purposes = {'database_dump', 'roles', 'native_storage', 'native_configuration',
                'function_cache', 'managed_storage', 'production_configuration',
                'controller_state', 'images', 'schema_ledgers', 'auth_metadata',
                'independent_restore'}
    entries = checkpoint.get('files', [])
    if (len(entries) != len(purposes)
            or {entry.get('purpose') for entry in entries} != purposes):
        raise BackupError('coordinated_checkpoint_incomplete')
    seen = set()
    for entry in entries:
        relative = PurePosixPath(entry['path'])
        if relative.is_absolute() or '..' in relative.parts or str(relative) in seen:
            raise BackupError('coordinated_checkpoint_path_invalid')
        seen.add(str(relative))
        file = real_path(directory / relative, directory=False)
        if (not file.is_file() or file.is_symlink() or file.stat().st_mode & 0o077
                or file.stat().st_size != entry['size'] or digest(file) != entry['sha256']):
            raise BackupError('coordinated_checkpoint_integrity_failed')
    proof_entry = next(entry for entry in entries if entry['purpose'] == 'independent_restore')
    proof = json.loads((root / 'coordinated' / proof_entry['path']).read_text())
    required = {'schema115', 'all_public_tables', 'auth', 'mfa', 'foreign_keys',
                'storage_metadata', 'storage_bytes', 'storage_xattrs', 'asset_delivery',
                'tenant_isolation', 'runtime_readiness', 'no_migrations', 'no_workers',
                'no_email', 'private_topology'}
    if (set(proof.get('checks', {})) != required
            or any(value is not True for value in proof['checks'].values())
            or proof.get('database_dump_sha256') != next(
                entry['sha256'] for entry in entries if entry['purpose'] == 'database_dump')):
        raise BackupError('coordinated_checkpoint_restore_proof_invalid')


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


# A governed root caller can pass a sealed, anonymous, nonsecret address lease
# to a child with NO supplementary groups. No Docker socket or IP environment
# override is trusted. The fd survives bash and its Python provider subprocess.
LOCAL_DATABASE_FD = 'MADAR_LOCAL_DATABASE_BINDING_FD'
DATABASE_SEALS = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL


def sealed_local_database_binding() -> int:
    if os.geteuid() != 0 or LOCAL_DATABASE_FD in os.environ:
        raise BackupError('local_backup_binding_root_required')
    address = direct_local_database_address()
    fd = os.memfd_create('madar-native-backup-address', os.MFD_ALLOW_SEALING)
    try:
        # fd 9 belongs to backup_madar.sh's existing backup lock.
        inherited = fcntl.fcntl(fd, fcntl.F_DUPFD_CLOEXEC, 64)
        os.close(fd)
        fd = inherited
        os.fchmod(fd, 0o400)
        payload = json.dumps({'version': 1, 'address': address,
                              'expires': time.monotonic() + 7200}).encode()
        os.write(fd, payload)
        fcntl.fcntl(fd, fcntl.F_ADD_SEALS, DATABASE_SEALS)
        return fd
    except BaseException:
        os.close(fd)
        raise


def leased_local_database_address() -> str:
    try:
        raw = os.environ[LOCAL_DATABASE_FD]
        if not re.fullmatch(r'[0-9]{1,6}', raw):
            raise ValueError('descriptor')
        fd = int(raw)
        metadata = os.fstat(fd)
        if (fd < 64 or metadata.st_uid != 0 or not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) != 0o400 or metadata.st_size > 4096
                or fcntl.fcntl(fd, fcntl.F_GET_SEALS) != DATABASE_SEALS):
            raise ValueError('authority')
        value = json.loads(os.pread(fd, 4096, 0))
        remaining = value['expires'] - time.monotonic()
        address = ipaddress.ip_address(value['address'])
        if (set(value) != {'version', 'address', 'expires'} or value['version'] != 1
                or not 0 < remaining <= 7200 or address.version != 4
                or not address.is_private or address.is_loopback or address.is_link_local
                or address.is_unspecified or address.is_multicast):
            raise ValueError('lease')
        return str(address)
    except (OSError, ValueError, KeyError, TypeError):
        raise BackupError('local_backup_binding_invalid') from None


def direct_local_database_address() -> str:
    """Resolve only the healthy native DB; never persist a Docker bridge address."""
    if LOCAL_DATABASE_FD in os.environ:
        return leased_local_database_address()
    shape = ('{"running":{{json .State.Running}},"health":{{json .State.Health.Status}},'
             '"service":{{json (index .Config.Labels "com.docker.compose.service")}},'
             '"directory":{{json (index .Config.Labels "com.docker.compose.project.working_dir")}},'
             '"publications":{{json .HostConfig.PortBindings}},'
             '"networks":{{json .NetworkSettings.Networks}}}')
    try:
        result = subprocess.run(['docker', 'inspect', '--format', shape, 'supabase-db'],
                                capture_output=True, text=True, timeout=10, check=True)
        value = json.loads(result.stdout)
        networks = value['networks']
        if (value['running'] is not True or value['health'] != 'healthy'
                or value['service'] != 'db' or value['directory'] != '/opt/madar/local-supabase'
                or value['publications'] or len(networks) != 1):
            raise ValueError('identity')
        address = ipaddress.ip_address(next(iter(networks.values()))['IPAddress'])
        if (address.version != 4 or not address.is_private or address.is_loopback
                or address.is_link_local or address.is_unspecified or address.is_multicast):
            raise ValueError('address')
        return str(address)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError, StopIteration):
        raise BackupError('local_backup_direct_database_unavailable') from None


def direct_local_database_shape() -> bool:
    return all(os.environ.get(key) == value for key, value in {
        'PGHOST': 'supabase-db', 'PGPORT': '5432', 'PGUSER': 'postgres',
        'PGDATABASE': 'postgres', 'PGSSLMODE': 'disable'}.items())


def provider_snapshot(root: Path, backup_id: str) -> None:
    base = os.environ.get('SUPABASE_URL', '').rstrip('/')
    parsed = urlsplit(base)
    key = os.environ.get('SUPABASE_SERVICE_KEY', '')
    local = (base == 'http://127.0.0.1:18000'
             and os.environ.get('PGHOST') == '127.0.0.1'
             and os.environ.get('PGPORT') == '15432'
             and os.environ.get('PGDATABASE') == 'postgres'
             and os.environ.get('PGSSLMODE') == 'disable'
             and re.fullmatch(r'postgres\.[A-Za-z0-9_-]{1,128}', os.environ.get('PGUSER', '')))
    if (base == 'http://127.0.0.1:18000' and direct_local_database_shape()
            and os.environ.get('PGHOSTADDR') == direct_local_database_address()):
        local = True
    if ((parsed.scheme != 'https' and not local) or not parsed.hostname or parsed.username or parsed.password
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
    # The internal application alias deliberately does not resolve from host
    # backup services. Only this exact local topology maps to its loopback API.
    # Keys still come from the protected production credential; hosted and
    # other provider endpoints are never rewritten.
    if found['SUPABASE_URL'] == 'http://madar-supabase:8000':
        found['SUPABASE_URL'] = 'http://127.0.0.1:18000'
        if not direct_local_database_shape():
            raise BackupError('local_backup_database_configuration_mismatch')
        found['PGHOSTADDR'] = direct_local_database_address()
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
            if args.extra is not None:
                if not re.fullmatch('[0-9a-f]{64}',args.extra):
                    raise BackupError('maintenance_expected_digest_invalid')
                verify_maintenance(args.path,expected_sha256=args.extra)
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
