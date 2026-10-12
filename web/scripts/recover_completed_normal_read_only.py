#!/usr/bin/env python3
"""One exact-approved routing repair of the retained, fenced schema144 bridge.

Reuses the existing frozen controller's source/boot/database guards, Compose
renderer and proxy publication. Never installs code, grants writes, starts
workers, executes migrations, clears interlocks or restores customer data.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback

BASE = Path('/var/lib/madar-control-plane/normal-local-preparation')
PARENT_SOURCE = '3e67189068de9f60c5da59799f6f35220cdf681a83b99be113ed9b1344167cf1'
PARENT_PLAN = '62e8801d47b5b8fe85a33ff90f3e2ba933c8c140081739b1da449b5a9329caad'
CONTEXT = '795df6dc0143f9445846b477b4b4e1626f915a4961987189399fca85ffb119c8'
OPERATION = 'retained-schema144-bridge-read-only-routing'
ATTEMPTS = Path('/var/lib/madar-control-plane/emergency-retained-bridge-routing')
ROUTE = (b'upstream madar_backend_active { server 127.0.0.1:8101; }\n'
         b'upstream madar_frontend_active { server 127.0.0.1:3100; }\n')


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def secure(path):
    for item in (path, *path.parents):
        st = item.lstat()
        if item.is_symlink() or st.st_uid != 0 or st.st_mode & 0o022:
            raise RuntimeError('recovery_source_or_record_untrusted')
    return path


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assemble(source_hash):
    if not re.fullmatch('[0-9a-f]{64}', source_hash):
        raise RuntimeError('recovery_source_hash_invalid')
    package = BASE / ('read-only-bridge-source-' + source_hash)
    manifest = secure(package / 'source-bundle.json').read_bytes()
    inventory = json.loads(manifest)
    if (sha(manifest) != source_hash or manifest != encoded(inventory)
            or set(inventory) != {'source_git', 'files'}
            or set(inventory['files']) != {'driver.py', 'validator.py'}
            or Path(__file__) != package / 'driver.py'):
        raise RuntimeError('recovery_source_package_changed')
    for name, expected in inventory['files'].items():
        if sha(secure(package / name).read_bytes()) != expected:
            raise RuntimeError('recovery_executable_changed')
    parent = BASE / ('normal-source-' + PARENT_SOURCE)
    parent_manifest = secure(parent / 'source-bundle.json').read_bytes()
    entry_path = secure(parent / 'source/web/scripts/continue_completed_normal_upgrade.py')
    if (sha(parent_manifest) != PARENT_SOURCE or sha(entry_path.read_bytes()) !=
            json.loads(parent_manifest)['files']['web/scripts/continue_completed_normal_upgrade.py']):
        raise RuntimeError('recovery_parent_entry_changed')
    entry = load('recovery_parent_entry', entry_path)
    measure = lambda: entry.measure(parent, PARENT_SOURCE, PARENT_PLAN)
    document, source = measure()
    sys.path.insert(0, str(source / 'web'))
    from deployment.lib.completed_normal_boot_actor import CompletedNormalBootActor
    actor = CompletedNormalBootActor(document, parent, measure)
    if actor.root.name != CONTEXT:
        raise RuntimeError('recovery_parent_context_changed')
    validator = load('recovery_measured_validator', secure(package / 'validator.py'))
    return actor, validator, inventory


def staged_model(actor):
    from deployment.lib.completed_normal_model import render_candidate_model, accepted_compose_blobs
    model = render_candidate_model(actor, read_only=True)
    release = actor.ops.state_root / 'releases' / actor.contract['candidate']['source_sha']
    # Read-only rendering uses package-relative mounts. Resolve those relative
    # application mounts to the actual canonical staged worktree, after proving
    # its accepted Git identity and clean tracked bytes. Authority/storage
    # mounts are absolute and are never remapped.
    args = ['runuser', '-u', 'madar', '--', 'git', '--no-optional-locks', '-C', str(release)]
    for command, expected in ((['rev-parse', 'HEAD'], actor.contract['candidate']['source_sha']),
                              (['status', '--porcelain', '--untracked-files=no'], '')):
        result = subprocess.run([*args, *command], capture_output=True, text=True, timeout=actor.runtime.budget(15))
        if result.returncode or result.stdout.strip() != expected:
            raise RuntimeError('recovery_staged_application_changed')
    blobs = accepted_compose_blobs(actor.contract['candidate']['source_sha'], actor.document['application_source_objects'])
    for relative, oid in blobs.items():
        data = (release / relative).read_bytes()
        if hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() != oid:
            raise RuntimeError('recovery_staged_compose_changed')
    frozen = actor.package / 'source'
    for service in model['services'].values():
        for volume in service.get('volumes', []):
            path = Path(volume['source'])
            if path.is_relative_to(frozen):
                volume['source'] = str(release / path.relative_to(frozen))
    return model


def verify_core(actor):
    runtime = actor.runtime
    pending = {'notification_worker', 'calendar_sync_worker', 'data_deletion_worker'}
    status, data = runtime.fetch('http://127.0.0.1:8101/health/ready')
    ready = json.loads(data)
    components = ready.get('components', {})
    if (status not in {200, 503} or not components
            or any(components.get(key) != 'ok' for key in
                   ('environment', 'database', 'auth', 'storage', 'schema', 'redis',
                    'admin_mfa_policy', 'parser_isolation', 'backup_freshness'))
            or any(value not in {'ok', 'disabled', 'configured', 'not_required', 'development'}
                   and not (key in pending and value == 'unavailable') for key, value in components.items())):
        raise RuntimeError('recovery_read_only_core_unready')
    for base in ('http://127.0.0.1:8101', 'http://127.0.0.1:3100/api'):
        verify_endpoint(actor, base)
    runtime.http_status('http://127.0.0.1:3100/')


def verify_endpoint(actor, base):
    value = actor.runtime.json_http(base + '/health/version')
    if (value.get('release_sha') != actor.contract['candidate']['source_sha']
            or value.get('release_slot') != 'blue'
            or value.get('schema_compatible_min') != 136
            or value.get('schema_compatible_max') != 144
            or value.get('schema_excluded_versions') != [142]):
        raise RuntimeError('recovery_endpoint_identity_changed')
    if actor.runtime.json_http(base + '/health/recovery') != {'restricted': True, 'business_writes_enabled': False}:
        raise RuntimeError('recovery_write_fence_changed')
    actor.runtime.denied(base)


def measure_live(actor, validator, *, published=False):
    from deployment.lib.completed_normal_admission import require_candidate_authority, digest
    from deployment.lib.completed_normal_profile import expected_origin_grant
    from deployment.lib.provider_recovery_runtime import protected, readonly_configuration
    from deployment.lib.completed_normal_resources import measured_spec, measured_spec_matches
    from deployment.lib.emergency_routing_repair import UPSTREAM, MAINTENANCE
    actor.guard()
    if actor.native() != 136:
        raise RuntimeError('recovery_native_schema_changed')
    if any((actor.root / name).exists() for name in
           ('candidate-staged-runtime.json', 'candidate-runtime.json', 'migration-intent.json', 'normal-completion.json')):
        raise RuntimeError('recovery_execution_progress_changed')
    failure = json.loads(protected(actor.root / 'failure.json', private=True).read_text())
    if (failure.get('phase') != 'service_prepare_completed' or failure.get('exception_type') != 'RuntimeError'
            or failure.get('customer_database_restored') is not False or 'compensation_exception_type' in failure
            or failure.get('context_sha256') != CONTEXT
            or not any(frame.get('function') == 'validate_model' for frame in failure.get('frames', []))):
        raise RuntimeError('recovery_previous_failure_changed')
    require_candidate_authority(actor.contract, mode='READ_ONLY')
    from deployment.lib.runtime_authority import load_worker_authority
    owner_path = readonly_configuration(actor.ops.state_root / 'worker-ownership.json', private=True)
    owner = load_worker_authority(actor.ops.state_root)
    if (owner is None or owner['owner'] != 'CANDIDATE'
            or owner['generation'] != actor.contract['origin']['worker_generation']
            or owner['candidate'] != {'sha': actor.contract['source_roles']['application_sha'],
                                      'slot': actor.contract['origin']['slot']}):
        raise RuntimeError('recovery_worker_ownership_changed')
    origin = Path(actor.contract['source_roles']['completion_root'])
    authority = json.loads(protected(origin / 'write-authority/authority.json').read_text())
    if authority != expected_origin_grant(actor.contract, 'READ_ONLY'):
        raise RuntimeError('recovery_origin_write_fence_changed')
    original = json.loads(protected(origin / 'candidate-runtime.json', private=True).read_text())
    old_workers = [original['runtimes'][kind]['id'] for kind in validator.BUSINESS]
    old_rows = actor.runtime.inspect(old_workers)
    if len(old_rows) != 3 or any(row['State']['Running'] for row in old_rows.values()):
        raise RuntimeError('recovery_origin_consumers_running')
    for kind in validator.BUSINESS:
        expected = original['runtimes'][kind]
        row = next(row for row in old_rows.values() if row['Id'] == expected['id'])
        if row['Image'] != expected['image'] or not measured_spec_matches(row, expected['spec_sha256']):
            raise RuntimeError('recovery_origin_worker_identity_changed')
    runtimes, networks = validator.validate_model(actor.contract, staged_model(actor), actor.runtime, phase='staged')
    # Reject another consuming production generation, including retained
    # canonical BLUE resources. Demo resources are outside this transaction.
    for name in actor.runtime.names():
        if name.startswith('madar-') and 'demo' not in name and any(name.endswith('-' + k) for k in validator.BUSINESS):
            row = next(iter(actor.runtime.inspect([name]).values()))
            if row['State']['Running']:
                raise RuntimeError('recovery_competing_business_consumer')
    proxy = actor.proxy_identity()
    route = readonly_configuration(UPSTREAM, private=False).read_bytes()
    if route != (ROUTE if published else MAINTENANCE):
        raise RuntimeError('recovery_route_preimage_changed')
    verify_core(actor)
    fixed = [actor.root / name for name in
             ('failure.json', 'admission.json', 'operator-authorization.json', 'controller-installation.json',
              'controller-installation-intent.json', 'boot-installation.json', 'boot-preimages.json', 'boot-events.jsonl')]
    fixed += [actor.root / 'write-authority/authority.json', origin / 'write-authority/authority.json',
              Path('/run/madar/control-plane-upgrade/in-progress.json')]
    records = {str(p): sha(secure(p).read_bytes()) for p in fixed}
    # These existing deployment/backup data files are owned by madar. Apply
    # their existing configuration trust policy; never extend it to root
    # executable code, authorization or protected completion receipts.
    for path, private in ((owner_path, True), (Path('/var/lib/madar/backup-state/latest.json'), False),
                          (Path('/var/lib/madar/backups/LATEST'), True)):
        records[str(path)] = sha(readonly_configuration(path, private=private).read_bytes())
    return {'records': records,
            'runtimes': runtimes, 'networks': networks,
            'origin_workers': {row['Id']: measured_spec(row) for row in old_rows.values()},
            'proxy_id': proxy['Id'], 'proxy_image': proxy['Image'], 'proxy_spec': measured_spec(proxy),
            'database': actor.contract['database'], 'parent_source': PARENT_SOURCE, 'parent_plan': PARENT_PLAN,
            'route_sha256': sha(ROUTE), 'schema': 136, 'mode': 'READ_ONLY'}


def public_round(actor):
    from deployment.lib.emergency_routing_repair import AvailabilityFailure
    for url in ('http://127.0.0.1:3000/', 'https://madarportal.com/', 'https://api.madarportal.com/'):
        actor.runtime.http_status(url)
    for base in ('http://127.0.0.1:8001', 'http://127.0.0.1:3000/api',
                 'https://api.madarportal.com', 'https://madarportal.com/api'):
        verify_endpoint(actor, base)
    if actor.proxy_identity()['State'].get('Health', {}).get('Status') != 'healthy':
        raise AvailabilityFailure('recovery_proxy_health_pending')


def main():
    if os.geteuid() != 0 or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        raise RuntimeError('recovery_isolated_root_required')
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('prepare', 'preflight', 'execute'))
    parser.add_argument('--approved-source', required=True)
    parser.add_argument('--approved-plan')
    args = parser.parse_args()
    if args.mode != 'prepare' and not re.fullmatch('[0-9a-f]{64}', str(args.approved_plan)):
        raise RuntimeError('recovery_plan_hash_invalid')
    actor, validator, inventory = assemble(args.approved_source)
    package = Path(__file__).parent
    current = measure_live(actor, validator)
    if args.mode == 'prepare':
        plan = {'operation': OPERATION, 'source_sha256': args.approved_source,
                'source_git': inventory['source_git'], 'bindings': current,
                'verification_seconds': 180, 'compensation_seconds': 60,
                'writes_granted': False, 'workers_started': False, 'database_restored': False}
        body = encoded(plan);target = package / 'plan.json'
        from deployment.lib.emergency_routing_repair import exclusive
        exclusive(target, body, mode=0o400)
        print(json.dumps({'source_sha256': args.approved_source, 'plan_sha256': sha(body),
                          'preflight': 'PASS', 'production_modified': False}));return
    body = secure(package / 'plan.json').read_bytes();plan = json.loads(body)
    if (sha(body) != args.approved_plan or body != encoded(plan) or plan['operation'] != OPERATION
            or plan['source_sha256'] != args.approved_source or plan['bindings'] != current
            or any(plan[k] is not False for k in ('writes_granted', 'workers_started', 'database_restored'))
            or (plan['verification_seconds'], plan['compensation_seconds']) != (180, 60)):
        raise RuntimeError('recovery_approved_bindings_changed')
    root = ATTEMPTS / args.approved_plan
    if root.exists() or root.is_symlink():raise RuntimeError('recovery_authorization_consumed')
    if args.mode == 'preflight':
        print(json.dumps({'preflight': 'PASS', 'production_modified': False, 'authorization_consumed': False}));return
    from deployment.lib.provider_recovery_bootstrap import exclusive_lock
    from deployment.lib.emergency_routing_repair import exclusive, UPSTREAM, verification_window, AvailabilityFailure
    with exclusive_lock(actor.ops.upgrade_root / 'upgrade.lock'), exclusive_lock(actor.ops.state_root / 'deploy.lock'):
        if measure_live(actor, validator) != plan['bindings']:
            raise RuntimeError('recovery_locked_bindings_changed')
        ATTEMPTS.mkdir(mode=0o700, exist_ok=True);secure(ATTEMPTS);root.mkdir(mode=0o700)
        exclusive(root / 'authorization.json', encoded({'operation': OPERATION, 'source_sha256': args.approved_source,
                  'plan_sha256': args.approved_plan, 'parent_authorization_reused': False}))
        before = UPSTREAM.read_bytes();exclusive(root / 'routing-preimage.conf', before)
        effect = False;phase = 'nginx_configuration_validation'
        try:
            with verification_window(actor.runtime, 180):
                actor.runtime.nginx_preflight(ROUTE, root)
                if measure_live(actor, validator) != plan['bindings']:raise RuntimeError('recovery_prepublication_changed')
                phase = 'route_publication';effect = True;actor.runtime.publish(ROUTE);actor.runtime.reload()
                phase = 'activation_convergence';first = None;count = 0
                while True:
                    actor.runtime.budget(1)
                    if measure_live(actor, validator, published=True) != plan['bindings']:
                        raise RuntimeError('recovery_postpublication_changed')
                    try:public_round(actor)
                    except AvailabilityFailure:first = None;count = 0
                    else:
                        count += 1;first = time.monotonic() if first is None else first
                        if count >= 3 and time.monotonic() - first >= 5:break
                    time.sleep(actor.runtime.budget(1))
            exclusive(root / 'result.json', encoded({'operation': OPERATION, 'status': 'RECOVERY_ONLY',
                      'frontend': 200, 'api': 200, 'schema': 136, 'business_writes_enabled': False,
                      'business_workers_started': False, 'normal_claimed': False}))
            print((root / 'result.json').read_text())
        except Exception as error:
            failure = {'phase': phase, 'exception_type': type(error).__name__,
                       'frames': [{'file': Path(f.filename).name, 'function': f.name, 'line': f.lineno}
                                  for f in traceback.extract_tb(error.__traceback__)[-16:]], 'database_restored': False}
            if effect:
                try:
                    with verification_window(actor.runtime, 60):
                        actor.proxy_identity();actor.runtime.nginx_preflight(before, root)
                        actor.runtime.publish(before);actor.runtime.reload();actor.runtime.verify_maintenance()
                    failure['compensation'] = 'prior_maintenance_restored'
                except Exception:
                    try:
                        proxy = actor.proxy_identity()
                        actor.runtime.command(['docker', 'stop', proxy['Id']])
                        failure['compensation'] = 'bound_proxy_stopped'
                    except Exception as compensation:
                        failure['compensation'] = 'failed_closed_action_unavailable'
                        failure['compensation_exception_type'] = type(compensation).__name__
            exclusive(root / 'failure.json', encoded(failure));raise


if __name__ == '__main__':
    try:main()
    except Exception as error:
        code = str(error)
        print(json.dumps({'status': 'failed', 'exception_type': type(error).__name__,
                          'failure_code': code if isinstance(error, RuntimeError) and code.replace('_', '').isalnum()
                          else 'sanitized_exception'}));raise SystemExit(1)
