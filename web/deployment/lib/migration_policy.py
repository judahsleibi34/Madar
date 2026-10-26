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


def validate_policy(value):
    if (not isinstance(value,dict) or set(value)!=FIELDS or type(value['version']) is not int or value['version']!=1
            or value['repository']!='judahsleibi34/Madar' or value['branch']!='refs/heads/main'
            or type(value['enabled']) is not bool or type(value['expires_at']) is not int
            or type(value['max_migrations']) is not int or not 0<value['max_migrations']<=100
            or value['risk_classes']!=['A']): raise RuntimeError('migration_policy_invalid')
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
    require(value['risk_class']=='A','risk_requires_independent_review')
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
