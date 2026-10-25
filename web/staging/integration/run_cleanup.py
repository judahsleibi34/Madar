"""Explicit fresh-staging teardown, never a production/backup garbage collector.

Only new attempts with a private lifecycle record are eligible. An accepted
review stack is retained; legacy stacks have no record and are never adopted.
Dry-run is the default. Shared images and private evidence are not deleted.
"""
from datetime import datetime
import json
import os
from pathlib import Path
import re
import secrets
import stat
import time

import manage

POLICY = 'disposable-run.json'
OWNER = 'com.madar.staging.owner'
PROJECT = 'com.docker.compose.project'
PROTECTED = 'com.madar.staging.protected'


def _read(runtime):
    for path, directory in ((runtime, True), (runtime / POLICY, False)):
        info = path.lstat()
        expected_type = stat.S_ISDIR if directory else stat.S_ISREG
        if (not expected_type(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or (not directory and (info.st_nlink != 1 or info.st_size > 8192))):
            raise RuntimeError('staging_cleanup_private_record_required')
    value = json.loads((runtime / POLICY).read_bytes())
    if (value.get('version') != 1 or value.get('purpose') != 'fresh-synthetic-application'
            or value.get('runtime') != str(runtime) or value.get('project') != manage.PROJECT
            or value.get('owner') != manage.OWNER or manage.OWNER != manage.PROJECT
            or not re.fullmatch('[0-9a-f]{40}', str(value.get('source_sha')))
            or manage.PROJECT != 'madar-full-provider-' + value['source_sha'][:12]
            or not re.fullmatch('madar-full-provider-[0-9a-f]{12}', manage.PROJECT)
            or not re.fullmatch('[0-9a-f]{32}', str(value.get('run_id')))
            or type(value.get('created')) not in (int, float)
            or type(value.get('retain')) is not bool):
        raise RuntimeError('staging_cleanup_scope_changed')
    return value


def reserve(runtime, *, source, retain=False):
    """Call after fresh configuration reservation, before creating resources."""
    manage.require_staging_host()
    if (runtime != manage.RUNTIME or runtime.is_symlink()
            or manage.PROJECT != 'madar-full-provider-' + source[:12]
            or not re.fullmatch('[0-9a-f]{40}', source)):
        raise RuntimeError('staging_cleanup_reservation_scope_invalid')
    value = {'version': 1, 'purpose': 'fresh-synthetic-application',
        'project': manage.PROJECT, 'owner': manage.OWNER, 'runtime': str(runtime),
        'source_sha': source, 'run_id': secrets.token_hex(16), 'created': time.time(),
        'retain': bool(retain), 'retention_reason': 'accepted-review-stack' if retain else None}
    path = runtime / POLICY
    with path.open('xb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write((json.dumps(value, sort_keys=True) + '\n').encode())
        stream.flush(); os.fsync(stream.fileno())
    return value


def _json(*args):
    return json.loads(manage.docker(*args))


def _labels(row, *, container=False):
    return (row.get('Config', {}).get('Labels') if container else row.get('Labels')) or {}


def preview(runtime, *, services):
    """Validate the entire deletion set before any mutation, including users."""
    manage.require_staging_host()
    if runtime != manage.RUNTIME:
        raise RuntimeError('staging_cleanup_runtime_changed')
    policy = _read(runtime)
    if policy['retain']:
        raise RuntimeError('staging_cleanup_explicitly_retained')
    ids = manage.docker('ps', '-aq', '--no-trunc').decode().split()
    if len(ids) > 2048 or len(ids) != len(set(ids)):
        raise RuntimeError('staging_cleanup_unbounded_inventory')
    rows = _json('inspect', *ids) if ids else []
    if {r['Id'] for r in rows} != set(ids):
        raise RuntimeError('staging_cleanup_incomplete_inventory')
    selected = [r for r in rows if _labels(r, container=True).get(PROJECT) == manage.PROJECT]
    for row in selected:
        labels = _labels(row, container=True)
        if (labels.get(OWNER) != manage.OWNER or labels.get(PROTECTED)
                or labels.get('com.docker.compose.service') not in services
                or row['State'].get('Running') or row['State'].get('Restarting')):
            raise RuntimeError('staging_cleanup_foreign_protected_or_active_container')
        created = datetime.fromisoformat(row['Created'].replace('Z', '+00:00')).timestamp()
        if created < policy['created']:
            raise RuntimeError('staging_cleanup_resource_predates_run')
    owned = {r['Id'] for r in selected}
    resources = {'containers': sorted(owned), 'networks': [], 'volumes': []}
    for kind, suffixes in (('network', ('isolated', 'ingress')), ('volume', ('database', 'objects'))):
        names = manage.docker(kind, 'ls', '--filter', 'label=' + PROJECT + '=' + manage.PROJECT,
            '--format', '{{.Name}}').decode().split()
        expected = {manage.PROJECT + '_' + name for name in suffixes}
        if len(names) != len(set(names)) or not set(names) <= expected:
            raise RuntimeError('staging_cleanup_unexpected_resource')
        for name in names:
            row = _json(kind, 'inspect', name)[0]
            labels = _labels(row)
            if labels.get(OWNER) != manage.OWNER or labels.get(PROJECT) != manage.PROJECT or labels.get(PROTECTED):
                raise RuntimeError('staging_cleanup_foreign_or_protected_resource')
            created = datetime.fromisoformat(row.get('CreatedAt', row.get('Created', '')).replace('Z', '+00:00')).timestamp()
            if created < policy['created']:
                raise RuntimeError('staging_cleanup_resource_predates_run')
            # A mount or endpoint held by ANY other container blocks the whole
            # deletion plan, including stopped containers and other projects.
            for container in rows:
                if container['Id'] in owned:
                    continue
                if kind == 'volume':
                    used = any(m.get('Type') == 'volume' and m.get('Name') == name for m in container.get('Mounts', []))
                else:
                    used = name in container.get('NetworkSettings', {}).get('Networks', {})
                if used:
                    raise RuntimeError('staging_cleanup_external_reference')
            if kind == 'network' and set(row.get('Containers') or {}) - owned:
                raise RuntimeError('staging_cleanup_unknown_endpoint')
            if kind == 'volume' and (row.get('Options') or row.get('Driver') != 'local'):
                raise RuntimeError('staging_cleanup_nonlocal_volume')
            resources[kind + 's'].append(name)
    return {'run_id': policy['run_id'], 'resources': resources, 'dry_run': True,
        'images_removed': [], 'private_evidence_removed': False}


def teardown(runtime, *, services, apply=False):
    report = preview(runtime, services=services)
    if not apply:
        return report
    # Recheck the complete set immediately before removal. Docker rm (without
    # force) and volume/network rm independently refuse live/new references.
    if preview(runtime, services=services) != report:
        raise RuntimeError('staging_cleanup_inventory_changed')
    removed = []
    try:
        for kind in ('container', 'network', 'volume'):
            for identity in report['resources'][kind + 's']:
                args = ('rm', identity) if kind == 'container' else (kind, 'rm', identity)
                manage.docker(*args)
                removed.append({'kind': kind, 'identity': identity})
                manage.private_write('cleanup-result.json', json.dumps({'removed': removed, 'complete': False}) + '\n')
        remaining = preview(runtime, services=services)
        if any(remaining['resources'].values()):
            raise RuntimeError('staging_cleanup_leak_observed')
    except Exception as error:
        manage.private_write('cleanup-result.json', json.dumps({'removed': removed,
            'complete': False, 'exception_type': type(error).__name__}, sort_keys=True) + '\n')
        raise
    manage.private_write('cleanup-result.json', json.dumps({'removed': removed, 'complete': True}, sort_keys=True) + '\n')
    report.update(dry_run=False, removed=removed)
    return report


def stop_and_teardown(runtime, *, services):
    """Caller owns the staging lease; only a new disposable attempt may stop."""
    manage.require_staging_host()
    policy = _read(runtime)
    if policy['retain']:
        raise RuntimeError('staging_cleanup_explicitly_retained')
    manage.attest_resources()
    manage.compose('stop', '--timeout', '15')
    return teardown(runtime, services=services, apply=True)
