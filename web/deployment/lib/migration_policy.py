"""Read-only eligibility assessment; never an authorization issuer or executor.

Production dispatch is deliberately unavailable until the protected controller's
maintenance/candidate/handoff/recovery integration is complete. A routine-policy
match prepares an operation; it cannot mint authority or activate deployment.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import stat
import time
from .migration_inventory import strict_json

POLICY_PATH=Path('/etc/madar/migration-policy.json')
FIELDS={'version','policy_id','environment_id','database_system_identifier','controller_sha',
        'repository','branch','enabled','expires_at','max_migrations','risk_classes','automation_inputs_sha256'}
B_OPERATIONS={'add_nullable_column','create_btree_index'}
B_FIELDS={'operations','max_table_bytes','max_table_rows','max_lock_wait_ms','max_statement_ms','measurement_max_age_seconds'}


def validate_policy(value):
    if (not isinstance(value,dict) or type(value.get('version')) is not int or value['version'] not in {1,2}
            or set(value)!=FIELDS|({'class_b'} if value['version']==2 else set())
            or value['repository']!='judahsleibi34/Madar' or value['branch']!='refs/heads/main'
            or type(value['enabled']) is not bool or type(value['expires_at']) is not int
            or type(value['max_migrations']) is not int or not 0<value['max_migrations']<=100
            or value['risk_classes'] not in ([['A']] if value['version']==1 else [['A'],['A','B']])):
        raise RuntimeError('migration_policy_invalid')
    if value['version']==2:
        b=value['class_b']
        if (not isinstance(b,dict) or set(b)!=B_FIELDS or not isinstance(b['operations'],list)
                or any(not isinstance(x,str) or x not in B_OPERATIONS for x in b['operations'])
                or len(set(b['operations']))!=len(b['operations'])
                or ('B' in value['risk_classes'] and not b['operations'])
                or any(type(b[k]) is not int or not 0<b[k]<=limit for k,limit in
                    (('max_table_bytes',2**40),('max_table_rows',10**9),('max_lock_wait_ms',5000),
                     ('max_statement_ms',30000),('measurement_max_age_seconds',300)))):
            raise RuntimeError('migration_policy_class_b_invalid')
        if b['max_lock_wait_ms']>b['max_statement_ms']:raise RuntimeError('migration_policy_class_b_invalid')
    import re
    if (not all(isinstance(value[k],str) and re.fullmatch('[a-zA-Z0-9_-]{1,128}',value[k])
                for k in ('policy_id','environment_id','database_system_identifier'))
            or not isinstance(value['controller_sha'],str) or not re.fullmatch('[a-f0-9]{40}',value['controller_sha'])):
        raise RuntimeError('migration_policy_identity_invalid')
    if not isinstance(value['automation_inputs_sha256'],str) or not re.fullmatch('[a-f0-9]{64}',value['automation_inputs_sha256']):
        raise RuntimeError('migration_policy_automation_identity_invalid')
    return value


def load_policy():
    # Fixed root-protected policy, no CLI/repository-controlled alternate path.
    if os.geteuid()!=0: raise RuntimeError('migration_policy_root_reader_required')
    for path in (Path('/'),Path('/etc'),Path('/etc/madar')):
        value=path.lstat()
        if not stat.S_ISDIR(value.st_mode) or value.st_uid!=0 or value.st_mode&0o022:
            raise RuntimeError('migration_policy_parent_unprotected')
    fd=os.open(POLICY_PATH,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        metadata=os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid!=0 or metadata.st_mode&0o077 or metadata.st_size>32768:
            raise RuntimeError('migration_policy_file_unprotected')
        raw=stream.read(32769)
    if len(raw)>32768: raise RuntimeError('migration_policy_size_limit')
    return validate_policy(strict_json(raw))


def assess(plan, policy, observation, *, now=None):
    """Observations must be authenticated independently by the real controller.

    No supplied boolean or policy match is authority. The return value always
    records production_execution_allowed=False until that integration exists.
    """
    validate_policy(policy); value=plan.document(); now=int(time.time()) if now is None else now
    if not isinstance(observation,dict) or not isinstance(observation.get('gates'),dict):
        return {'version':1,'policy_match':False,'decision':'BLOCKED','reasons':['observation_invalid'],
                'plan_sha256':plan.sha256,'authority_issued':False,'production_execution_allowed':False,
                'protected_dispatch':'BLOCKED_INTEGRATION_INCOMPLETE'}
    reasons=[]
    def require(condition,reason):
        if not condition: reasons.append(reason)
    require(not value['automation_inputs']['missing'],'automation_inputs_incomplete')
    require(value['automation_inputs']['sha256']==policy['automation_inputs_sha256'],'automation_trust_root_changed')
    require(policy['enabled'] and policy['expires_at']>now,'policy_disabled_or_expired')
    require(value['risk_class'] in policy['risk_classes'],'risk_requires_independent_review')
    if value['risk_class']=='B':
        reasons.extend(class_b_reasons(plan,policy,observation,now=now))
    require(value['compatibility_covers_path'],'compatibility_intent_missing_or_incomplete')
    require(bool(value['compatibility_intent'] and value['compatibility_intent']['rolling_compatible']),'rolling_compatibility_not_declared')
    require(not value['protected_control_plane_changed'],'protected_control_plane_upgrade_required')
    require(len(value['migrations'])<=policy['max_migrations'],'policy_migration_count_exceeded')
    for key in ('environment_id','database_system_identifier','controller_sha','repository','branch'):
        require(observation.get(key)==policy[key],key+'_mismatch')
    for key in ('source_sha','origin_schema','target_schema','operation_id'):
        require(type(observation.get(key)) is type(value[key]) and observation.get(key)==value[key],key+'_mismatch')
    require(observation.get('plan_sha256')==plan.sha256,'plan_digest_mismatch')
    require(type(observation.get('evidence_expires_at')) is int and observation['evidence_expires_at']>now,'evidence_expired')
    for gate in value['required_gates']:
        if gate=='fresh_independent_authority': continue
        require(observation.get('gates',{}).get(gate) is True,gate+'_not_verified')
    require(observation.get('operation_consumed') is False,'operation_consumed_or_unknown')
    return {'version':1,'policy_match':not reasons,'decision':'PREPARATION_ELIGIBLE' if not reasons else 'BLOCKED',
            'reasons':sorted(set(reasons)),'plan_sha256':plan.sha256,'authority_issued':False,
            'production_execution_allowed':False,'protected_dispatch':'BLOCKED_INTEGRATION_INCOMPLETE'}


def class_b_reasons(plan,policy,observation,*,now):
    """Validate measured scope only; caller packets still issue no authority."""
    from .migration_inventory import digest
    value=plan.document();limits=policy.get('class_b');packet=observation.get('class_b_measurements')
    if policy['version']!=2 or not isinstance(limits,dict):return ['class_b_policy_not_approved']
    operations=[]
    for row in value['migrations']:
        if row['risk']['class']=='A':continue
        if row['risk']['class']!='B' or not row.get('measurable_operations'):return ['class_b_operation_not_supported']
        for op in row['measurable_operations']:
            if op.get('kind') not in limits['operations']:return ['class_b_operation_not_approved']
            operations.append((row['number'],digest(op)))
    keys={'version','source_sha','plan_sha256','system_identifier','origin_schema','structure_sha256','observed_at','operations','read_only'}
    if (not isinstance(packet,dict) or set(packet)!=keys or type(packet['version']) is not int or packet['version']!=1
            or packet['source_sha']!=value['source_sha'] or packet['plan_sha256']!=plan.sha256
            or packet['system_identifier']!=policy['database_system_identifier']
            or type(packet['origin_schema']) is not int or packet['origin_schema']!=value['origin_schema']
            or packet['structure_sha256']!=observation.get('structure_sha256')
            or not isinstance(packet['structure_sha256'],str) or not __import__('re').fullmatch('[a-f0-9]{64}',packet['structure_sha256'])
            or packet['read_only'] is not True or type(packet['observed_at']) is not int
            or not 0<=now-packet['observed_at']<=limits['measurement_max_age_seconds']
            or not isinstance(packet['operations'],list) or len(packet['operations'])!=len(operations)):
        return ['class_b_measurements_invalid_or_stale']
    reasons=[]
    for row,(number,expected) in zip(packet['operations'],operations):
        if (not isinstance(row,dict) or set(row)!={'migration','operation_sha256','table_bytes','table_rows','conflicting_locks'}
                or type(row['migration']) is not int or row['migration']!=number or row['operation_sha256']!=expected
                or any(type(row[k]) is not int or row[k]<0 for k in ('table_bytes','table_rows','conflicting_locks'))):
            return ['class_b_measurements_invalid_or_stale']
        if row['table_bytes']>limits['max_table_bytes']:reasons.append('class_b_table_bytes_exceeded')
        if row['table_rows']>limits['max_table_rows']:reasons.append('class_b_table_rows_exceeded')
        if row['conflicting_locks']:reasons.append('class_b_lock_contention')
    return reasons


def apply_class_b_limits(cursor,policy,*,expected_schema):
    """Execution budgets on the SAME locked executor session, not admission.

    The caller must separately authenticate source, authority, observations and
    root policy. PostgreSQL17's transaction deadline bounds the total lock hold
    as well as individual statements; a lost reply still requires observation,
    never an automatic retry. No candidate SQL may override these settings.
    """
    validate_policy(policy)
    if policy['version']!=2 or 'B' not in policy['risk_classes']:
        raise RuntimeError('migration_policy_class_b_not_approved')
    if type(expected_schema) is not int or not 0<expected_schema<10**9:
        raise RuntimeError('migration_policy_execution_origin_invalid')
    cursor.execute("SELECT system_identifier::text,schema_version FROM pg_catalog.pg_control_system(),public.application_schema_state WHERE contract_key='core'")
    if cursor.fetchone()!=(policy['database_system_identifier'],expected_schema):
        raise RuntimeError('migration_policy_execution_database_changed')
    cursor.execute("SELECT current_setting('server_version_num')::int")
    version=cursor.fetchone()[0]
    if type(version) is not int or not 170000<=version<180000:
        raise RuntimeError('migration_policy_execution_database_version_unsupported')
    cursor.execute("SELECT count(*) FROM pg_catalog.pg_event_trigger WHERE evtenabled<>'D'")
    if cursor.fetchone()!=(0,):raise RuntimeError('migration_policy_execution_ddl_hooks_unsupported')
    limits=policy['class_b']
    for key,value in (('lock_timeout',limits['max_lock_wait_ms']),
                      ('statement_timeout',limits['max_statement_ms']),
                      ('transaction_timeout',limits['max_statement_ms'])):
        cursor.execute('SELECT pg_catalog.set_config(%s,%s,false)',(key,str(value)+'ms'))
