#!/usr/bin/env python3
"""Capture a NEW sealed schema115 recovery checkpoint without publishing it.

Read-only database commands and file reads only; no timers, freshness markers,
LATEST pointers, retention, production state or service configuration changes.
The destination must be a new root-private backup preparation directory.
No restore PASS is issued. Run only frozen, independently reviewed source.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deployment.lib.coordinated_checkpoint import seal, digest_file

DESTROOT = Path('/var/lib/madar-control-plane/normal-local-preparation')
RECOVERY = Path('/var/lib/madar/releases')
LOCAL = Path('/var/lib/madar-control-plane/local-provider-transition')
NATIVE = Path('/opt/madar/local-supabase')
SKIP = {'checkpoints', 'checkpoint', 'local-coordinated-backups', 'rehearsals', '__pycache__'}
START = time.monotonic()


def command(args, *, sql=None, output=None):
    remaining = 600 - (time.monotonic() - START)
    if remaining <= 0:
        raise RuntimeError('checkpoint_capture_deadline')
    result = subprocess.run(args, input=sql.encode() if sql else None,
        stdout=output if output else subprocess.PIPE, stderr=subprocess.PIPE, timeout=min(120, remaining))
    if result.returncode:
        raise RuntimeError('checkpoint_capture_command_failed')
    return result.stdout.decode() if output is None else None


def sql(query):
    return command(['docker', 'exec', '-i', 'supabase-db', 'psql', '-X', '-U', 'postgres', '-d', 'postgres', '-At', '-v', 'ON_ERROR_STOP=1'],
                   sql='BEGIN READ ONLY;\n'+query+'\nROLLBACK;\n').splitlines()[1:-1]


def http(path):
    with urlopen('http://127.0.0.1:8001'+path, timeout=5) as response:
        if response.status != 200:
            raise RuntimeError('checkpoint_recovery_unavailable')
        return json.load(response)


def observe():
    recovery = http('/health/recovery')
    if recovery.get('restricted') is not True or recovery.get('business_writes_enabled') is not False:
        raise RuntimeError('checkpoint_business_write_fence_missing')
    if sql("SELECT schema_version FROM public.application_schema_state WHERE contract_key='core';") != ['115']:
        raise RuntimeError('checkpoint_schema_changed')
    facts = {}
    for slot in ('blue', 'green'):
        for kind in ('notification', 'calendar-sync', 'data-deletion'):
            name = f'madar-{slot}-{kind}-worker'
            row = json.loads(command(['docker', 'inspect', name]))[0]
            if row['State']['Running'] or row['HostConfig']['RestartPolicy']['Name'] != 'no':
                raise RuntimeError('checkpoint_consumer_enabled')
            facts[name] = row['Id']
    for label, path in [('local', LOCAL/'transaction.json'), ('recovery', RECOVERY/'provider-recovery.json')]:
        if json.loads(path.read_text()).get('phase') != 'local_rollback_active':
            raise RuntimeError('checkpoint_transaction_changed')
        facts[label] = digest_file(path)
    facts['route'] = digest_file(Path('/var/lib/madar/proxy/active-upstreams.conf'))
    facts['controller'] = digest_file(Path('/opt/madar/control-plane/deployment/CONTROL_PLANE_SOURCE_SHA'))
    facts['authority'] = digest_file(LOCAL/'write-authority/authority.json')
    facts['version'] = http('/health/version')
    return facts


def files(roots):
    selected = []
    for root in roots:
        root = Path(root)
        if not root.exists() or root.is_symlink():
            raise RuntimeError('checkpoint_source_missing_or_symlink')
        for parent in root.parents:
            if parent.is_symlink():
                raise RuntimeError('checkpoint_source_parent_symlink')
        candidates = [root] if root.is_file() else root.rglob('*')
        for path in candidates:
            if any(part in SKIP for part in path.relative_to(root).parts):
                continue
            if path.is_symlink() or not (path.is_file() or path.is_dir()):
                raise RuntimeError('checkpoint_source_special_file')
            if path.is_file():
                selected.append(path)
    return sorted(set(selected))


def archive(destination, roots):
    selected = files(roots)
    if not selected:
        raise RuntimeError('checkpoint_archive_empty')
    before = {str(p): digest_file(p) for p in selected}
    with tarfile.open(destination, 'x:gz') as stream:
        for path in selected:
            stream.add(path, arcname=str(path).lstrip('/'), recursive=False)
    after = {str(p): digest_file(p) for p in files(roots)}
    if before != after:
        raise RuntimeError('checkpoint_source_changed_during_capture')


def capture(destination):
    if os.geteuid() != 0 or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        raise RuntimeError('checkpoint_frozen_root_entry_required')
    if destination.parent != DESTROOT or not destination.name.startswith('checkpoint-') or destination.exists() or destination.is_symlink():
        raise RuntimeError('checkpoint_new_preparation_destination_required')
    os.umask(0o077)
    # This payload contains recovery secrets and customer backup data. Only a
    # fresh root-private namespace is permitted, outside the source checkout.
    for parent in (DESTROOT.parent, *DESTROOT.parent.parents):
        info = parent.lstat()
        if parent.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
            raise RuntimeError('checkpoint_destination_parent_untrusted')
    if not DESTROOT.exists():
        DESTROOT.mkdir(mode=0o700)
    info = DESTROOT.lstat()
    if DESTROOT.is_symlink() or info.st_uid != 0 or info.st_mode & 0o077:
        raise RuntimeError('checkpoint_destination_namespace_untrusted')
    baseline = observe()
    destination.mkdir(mode=0o700)
    binding = {}
    def write(name, kind, value):
        with (destination/name).open('x') as stream:
            json.dump(value, stream, sort_keys=True, indent=2); stream.write('\n')
        binding[name] = kind
    for name, kind, args in [
        ('database.dump', 'database', ['docker', 'exec', '-e', 'PGOPTIONS=-c default_transaction_read_only=on', 'supabase-db', 'pg_dump', '-U', 'postgres', '-d', 'postgres', '--format=custom']),
        ('roles.sql', 'roles', ['docker', 'exec', '-e', 'PGOPTIONS=-c default_transaction_read_only=on', 'supabase-db', 'pg_dumpall', '-U', 'postgres', '--roles-only'])]:
        with (destination/name).open('xb') as output:
            command(args, output=output); output.flush(); os.fsync(output.fileno())
        binding[name] = kind
    roots = [
        ('native-storage.tar.gz', 'storage', [NATIVE/'volumes/storage']),
        ('function-cache.tar.gz', 'native_config', [Path('/var/lib/docker/volumes/madar-local-supabase_deno-cache/_data')]),
        ('native-configuration.tar.gz', 'native_config', [NATIVE/'.env', NATIVE/'docker-compose.yml', NATIVE/'docker-compose.madar-local.yml', NATIVE/'volumes/api', NATIVE/'volumes/db/roles.sql', NATIVE/'volumes/db/jwt.sql', NATIVE/'volumes/db/_supabase.sql', NATIVE/'volumes/functions']),
        ('managed-storage.tar.gz', 'application_storage', [Path('/var/lib/madar/storage')]),
        ('production-configuration.tar.gz', 'production_config', [Path('/etc/madar/production.env'), LOCAL/'configuration.env', Path('/etc/madar/backup.env'), Path('/etc/madar/node1-backup.env')]),
        ('controller-state.tar.gz', 'controller', [Path('/opt/madar/control-plane/deployment'), RECOVERY, Path('/var/lib/madar/proxy'), Path('/var/lib/madar-control-plane/emergency-routing'), LOCAL, Path('/var/lib/madar-control-plane/provider402')])]
    for name, kind, sources in roots:
        archive(destination/name, sources); binding[name] = kind
    containers = command(['docker','ps','-a','--format','{{.Names}}']).splitlines()
    names = [name for name in containers if name.startswith(('supabase-', 'madar-blue-', 'madar-green-', 'madar-provider402-', 'madar-release-proxy'))]
    rows = json.loads(command(['docker','inspect',*names]))
    write('images.json','images', {row['Name'].lstrip('/'): {'id':row['Id'],'image':row['Image']} for row in rows})
    write('auth-metadata.json','auth_metadata', sql("SELECT 'users='||count(*) FROM auth.users UNION ALL SELECT 'identities='||count(*) FROM auth.identities UNION ALL SELECT 'factors='||count(*) FROM auth.mfa_factors;"))
    write('schema.json','schema', sql("SELECT schema_version FROM public.application_schema_state WHERE contract_key='core';"))
    write('ledgers.json','ledgers', sql("SELECT version FROM supabase_migrations.schema_migrations ORDER BY version;"))
    if observe() != baseline:
        raise RuntimeError('checkpoint_runtime_changed_during_capture')
    write('capture-bindings.json','controller', baseline)
    manifest_hash = seal(destination, created_at=datetime.now(timezone.utc).isoformat(), binding=binding)
    return {'operation':'sealed-recovery-checkpoint-capture','manifest_sha256':manifest_hash,
            'destination':str(destination),'files':len(binding),'schema':115,'business_writes_enabled':False,
            'production_modified':False,'migrations_executed':False,'restore_verified':False}

if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('destination',type=Path); args=parser.parse_args()
    try:
        print(json.dumps(capture(args.destination)))
    except Exception as error:
        print(json.dumps({'operation':'sealed-recovery-checkpoint-capture','status':'failed','exception_type':type(error).__name__,
                          'stage':str(error) if type(error) is RuntimeError else 'capture_failed'})); sys.exit(1)
