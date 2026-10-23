"""Pure exact actor inventory validation for delivery/outbox/deletion cutover.

Native observations must come from the protected adapter, not operator claims.
This verifier issues no authority and never stops an unrelated workload.
"""
import re

WORKERS = {'notification','data-deletion','calendar-sync'}
PATTERN = re.compile(r'(?:^|[\s/]|workers[./])(notification_worker|data_deletion_worker|calendar_sync_worker)(?:\.py|\b)')


def verify_actor_inventory(observed, policy):
    if (not isinstance(policy, dict) or set(policy) != {'version','operation','actors'}
            or type(policy['version']) is not int or policy['version'] != 1
            or policy['operation'] != 'delivery-outbox-deletion-exclusive-cutover'
            or not isinstance(policy['actors'], dict) or not policy['actors']
            or set(observed) != set(policy['actors'])):
        raise RuntimeError('schema149_writer_inventory_ambiguous')
    roles = set()
    for identifier, binding in policy['actors'].items():
        if (not re.fullmatch('[0-9a-f]{64}', str(identifier)) or not isinstance(binding, dict)
                or set(binding) != {'role','image','spec_sha256','generation'}
                or binding['role'] not in WORKERS or binding['generation'] not in {'origin','candidate'}
                or not re.fullmatch('sha256:[0-9a-f]{64}', str(binding['image']))
                or not re.fullmatch('[0-9a-f]{64}', str(binding['spec_sha256']))):
            raise RuntimeError('schema149_writer_binding_invalid')
        row = observed[identifier]
        expected = {**binding, 'running':False, 'restarting':False, 'restart':'no'}
        if row != expected:
            raise RuntimeError('schema149_writer_not_fenced')
        roles.add(binding['role'])
    if roles != WORKERS:
        raise RuntimeError('schema149_writer_role_inventory_incomplete')
    return {'actors':len(observed),'roles':sorted(roles),'unknown_actors':0}


def verify_host_processes(runtime, allowed_ids, *, positive_pid):
    """An independently visible backend PID proves the /proc scan isn't empty.

    All matching mutating workers must have been stopped, including manual and
    docker-exec invocations invisible in Config.Cmd. No command strings escape.
    """
    if type(positive_pid) is not int or positive_pid <= 0 or not allowed_ids:
        raise RuntimeError('schema149_process_visibility_unverified')
    visible = False
    for line in runtime.command(['ps','-eo','pid=,args=']).splitlines():
        fields = line.strip().split(None,1)
        if len(fields) != 2 or not fields[0].isdigit():
            continue
        pid = int(fields[0])
        if pid == positive_pid:
            group = runtime.command(['cat','/proc/'+str(pid)+'/cgroup'])
            if set(re.findall('[0-9a-f]{64}',group)) - set(allowed_ids):
                raise RuntimeError('schema149_positive_process_identity_changed')
            if not set(re.findall('[0-9a-f]{64}',group)):
                raise RuntimeError('schema149_process_visibility_unverified')
            visible = True
        if PATTERN.search(fields[1]):
            raise RuntimeError('schema149_live_mutating_worker')
    if not visible:
        raise RuntimeError('schema149_process_visibility_unverified')
    return {'positive_process_visible':True,'mutating_workers':0}
