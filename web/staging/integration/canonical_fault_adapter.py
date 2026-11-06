"""Root-only, disposable-only fault adapter for the existing canonical controller.

Uses the signed consumption owner to select a process, never a name/PID guess.
Run only after fresh normal approval consumption. No issuer or recovery effects.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import importlib.util

PLAN = Path('/opt/madar-test/origin146/fault-plan.json')


def main():
    if os.geteuid() != 0:
        raise RuntimeError('canonical_fault_root_required')
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    args = parser.parse_args()
    if Path(args.plan) != PLAN:
        raise RuntimeError('canonical_fault_plan_location_invalid')
    # Authority observations come from the installed controller, not test code.
    sys.path.insert(0, '/opt/madar/control-plane')
    from deployment.lib.provider_recovery_runtime import protected
    from deployment.lib.migration_inventory import digest
    from deployment.lib.migration_executor import atomic_json
    from deployment.lib.control_plane_upgrade import SystemOperations
    from deployment.lib import exceptional_release_approval as approval
    from deployment.lib.schema160_release import isolated_registration
    from deployment.lib.completed_normal_admission import ADMISSIONS
    import subprocess
    path = protected(PLAN, private=True)
    if path.stat().st_mode & 0o222 or not 0 < path.stat().st_size <= 8192:
        raise RuntimeError('canonical_fault_plan_not_frozen')
    raw = path.read_bytes(); plan = json.loads(raw)
    fields = {'version','boundary','request_id','request_sha256','context_sha256',
              'controller_sha','guest_uuid','operation_id','expires_at',
              'adapter_sha256','helper_sha256'}
    if (set(plan) != fields or plan['version'] != 1
            or type(plan['expires_at']) is not int or not time.time() < plan['expires_at'] <= time.time()+900):
        raise RuntimeError('canonical_fault_plan_scope_invalid')
    # Isolated Python omits the script directory from sys.path. Load only the
    # exact root-protected helper independently pinned in this frozen plan.
    adapter = protected(Path(__file__), private=False)
    helper = protected(adapter.with_name('canonical_fault_matrix.py'), private=False)
    if (hashlib.sha256(adapter.read_bytes()).hexdigest() != plan['adapter_sha256']
            or hashlib.sha256(helper.read_bytes()).hexdigest() != plan['helper_sha256']):
        raise RuntimeError('canonical_fault_runner_changed')
    spec = importlib.util.spec_from_file_location('canonical_fault_matrix', helper)
    fault = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fault)
    if plan['boundary'] not in fault.BOUNDARIES:
        raise RuntimeError('canonical_fault_plan_scope_invalid')
    system = SystemOperations()
    _, key = approval.audit_policy(system)
    journal = approval.root()/approval.identifier(plan['request_id'])
    request = approval.verified(journal/'request.json', key)
    value = request['admission']; approval.canonical_admission_scope(value)
    contract = value['contract']
    registration = isolated_registration(contract)
    if (digest(request) != plan['request_sha256'] or value['context_sha256'] != plan['context_sha256']
            or value['operation_id'] != plan['operation_id'] or value['controller_sha'] != plan['controller_sha']
            or registration['guest_uuid'] != plan['guest_uuid'] or value['environment'] != 'isolated-test'
            or plan['expires_at'] > min(registration['expires_at'], value['expires_at'])):
        raise RuntimeError('canonical_fault_independent_scope_changed')
    owner = approval.verified(journal/'approval-consumed.json', key)
    consent = approval.verified(journal/'approval.json', key)
    if owner['admission_sha256'] != digest(value) or owner['approval_sha256'] != digest(consent):
        raise RuntimeError('canonical_fault_consumption_changed')
    pid = owner['pid']
    package = Path(value['source_package'])
    argv = ['/usr/bin/python3','-I','-B',str(package/'source/web/scripts/continue_completed_normal_upgrade.py'),
            'approved-execute','--source-package',str(package),'--approved-source',value['source_bundle_sha256'],
            '--approved-plan',value['plan_sha256'],'--request-id',plan['request_id'],
            '--confirm-request-digest',plan['request_sha256']]
    expected = (int(owner['process_start']), b'\0'.join(x.encode() for x in argv)+b'\0', pid)
    root = ADMISSIONS/plan['context_sha256']
    output = PLAN.parent/('fault-'+plan['boundary'])
    # Exclusive directory means a second invocation cannot repeat the fault.
    output.mkdir(mode=0o700)

    def guard():
        if (protected(PLAN, private=True).read_bytes() != raw
                or system.installed_sha() != plan['controller_sha']
                or time.time() >= plan['expires_at']
                or Path('/proc/sys/kernel/random/boot_id').read_text().strip() != owner['boot_id']
                or Path('/proc',str(pid)).stat().st_uid != 0
                or approval.verified(journal/'approval-consumed.json',key) != owner
                or isolated_registration(contract) != registration):
            raise RuntimeError('canonical_fault_live_scope_changed')
        entries = approval.history(journal,key)
        if not entries or entries[-1]['state'] not in {'EXECUTING','VERIFYING'}:
            raise RuntimeError('canonical_fault_operation_not_executing')

    def observe():
        events = protected(root/'boot-events.jsonl', private=True).read_text().splitlines()
        phase = json.loads(events[-1])['phase'] if events else None
        db = contract['database']
        sql = ('BEGIN READ ONLY; SELECT json_build_array((SELECT system_identifier::text FROM pg_control_system()),'
               "(SELECT schema_version FROM public.application_schema_state WHERE contract_key='core')); COMMIT;")
        actual = json.loads(subprocess.check_output(['docker','exec',db['container_id'],'psql','-XqAt',
            '-v','ON_ERROR_STOP=1','-U','supabase_admin','-d','postgres','-c',sql],timeout=15))
        if actual[0] != db['system_identifier']:
            raise RuntimeError('canonical_fault_database_changed')
        execution = system.state_root/'migrations'/value['source_sha']/'execution.json'
        record = json.loads(execution.read_bytes()) if execution.exists() else {}
        manifest = json.loads(protected(package/'source/web/deployment/releases/migrations-147-160-coordinated.json').read_bytes())
        if hashlib.sha256((package/'source/web/deployment/releases/migrations-147-160-coordinated.json').read_bytes()).hexdigest() != contract['migration_manifest_sha256']:
            raise RuntimeError('canonical_fault_manifest_changed')
        checksums = {m['number']:m['sha256'] for m in manifest['migrations']}
        committed = []
        for row in record.get('migrations',[]):
            if row.get('status') == 'applied':
                if checksums.get(row['number']) != row.get('checksum'):
                    raise RuntimeError('canonical_fault_migration_checksum_changed')
                committed.append(row['number'])
        return {'phase':phase,'schema':actual[1],'database_system_identifier':actual[0],
                'committed':committed,'executor_status':record.get('status'),
                'migration_intent':(root/'migration-intent.json').exists(),
                'normal_completion':(root/'normal-completion.json').exists(),'approval_consumed':True,
                'normal_acceptance':(root/'normal-acceptance.json').exists(),
                'worker_owner_sha256':hashlib.sha256((system.state_root/'worker-ownership.json').read_bytes()).hexdigest(),
                'route_sha256':hashlib.sha256(Path('/var/lib/madar/proxy/active-upstreams.conf').read_bytes()).hexdigest()}

    def record(name, value):
        atomic_json(output/(name+'.json'), {'plan_sha256':hashlib.sha256(raw).hexdigest(),
            'context_sha256':plan['context_sha256'],'operation_id':plan['operation_id'],
            'at':int(time.time()),'observation':value}, exclusive=True)
    try:
        result = fault.interrupt_exact_process(pid, expected, boundary=plan['boundary'], observe=observe,
            guard=guard, record=record, timeout=min(900,plan['expires_at']-time.time()))
        print(json.dumps({'fault_injected':True,'boundary':plan['boundary'],'observation':result,
                          'recovery_authority_issued':False,'completion_claimed':False}))
    except Exception as error:
        record('refused', {'error_type':type(error).__name__})
        raise


if __name__ == '__main__':
    main()
