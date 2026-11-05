"""Narrow maintenance finalization through the existing approval/controller path.

An interrupted deployment is immutable history. A separate request, fresh AAL2
approval and consumption authorize finalization only, never SQL or deployment
replay. Earlier maintenance/partial-SQL states are deliberately unsupported here.
"""
import hashlib
import os
from pathlib import Path
import time
import uuid

from . import exceptional_release_approval as approvals
from .migration_inventory import digest, strict_json
from .migration_executor import atomic_json
from .provider_recovery_runtime import protected, readonly_configuration, file_digest

KIND = 'canonical-maintenance-finalization-recovery'
ACTION = 'finalize-target160-v1'


def validate(value):
    fields = {'version','kind','action','request_id','parent_request_id','parent_request_sha256',
              'parent_consumption_sha256','parent_approval_sha256','parent_audit_sha256',
              'context_sha256','operation_id','attempt_id','source_sha','controller_sha',
              'contract','observation','policy_sha256','created_at','expires_at'}
    if (not isinstance(value,dict) or set(value)!=fields or type(value['version']) is not int
            or value['version']!=1 or value['kind']!=KIND or value['action']!=ACTION
            or any(type(value[k]) is not int for k in ('created_at','expires_at'))
            or not value['created_at']<value['expires_at']<=value['created_at']+1800):
        raise RuntimeError('maintenance_recovery_scope_invalid')
    import re
    for k in fields:
        if k.endswith('_sha256') and not re.fullmatch('[a-f0-9]{64}',str(value[k])):
            raise RuntimeError('maintenance_recovery_scope_invalid')
    for k in ('request_id','parent_request_id','operation_id','attempt_id'):
        approvals.identifier(value[k])
    from .completed_normal_admission import digest as context_digest
    contract=value['contract']
    if (value['request_id']==value['parent_request_id'] or value['context_sha256']!=context_digest(contract)
            or value['source_sha']!=contract['candidate']['source_sha']
            or value['controller_sha']!=contract['candidate']['controller_sha']):
        raise RuntimeError('maintenance_recovery_binding_changed')
    return value


def owner_live(owner):
    if owner['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():return False
    try:
        p=Path('/proc')/str(owner['pid'])
        fields=(p/'stat').read_text().rsplit(')',1)[1].split()
        return p.stat().st_uid==0 and fields[19]==owner['process_start'] and fields[0]!='Z'
    except (FileNotFoundError,ProcessLookupError):return False


def policy(system):
    p,key=approvals.policy(system)
    if p['version']!=3 or p['recovery_actions']!=[ACTION]:
        raise RuntimeError('maintenance_recovery_not_independently_enrolled')
    return p,key


def observe(system,parent_id,request_id,*,created_at=None,expires_at=None):
    """Independent read-only measurement; no credential, service or SQL effects."""
    p,key=policy(system);driver=approvals.canonical_driver(system)
    if p['canonical_scope']!=approvals.canonical_scope(driver):
        raise RuntimeError('maintenance_recovery_policy_scope_changed')
    approvals.identifier(parent_id);approvals.identifier(request_id)
    with approvals.journal_lock(parent_id) as parent:
        request=approvals._request(parent,key)
        original=request['admission'];approvals.canonical_admission_scope(original)
        if (original['contract']!=driver.contract or original['policy_sha256']!=digest(p)
                or request['policy_sha256']!=digest(p)
                or original['operation_id']!=driver.document['operation_id']
                or original['attempt_id']!=driver.document['attempt_id']):
            raise RuntimeError('maintenance_recovery_parent_changed')
        consent=approvals.verified(parent/'approval.json',key)
        consumed=approvals.verified(parent/'approval-consumed.json',key)
        if (consent['request_sha256']!=digest(request) or consumed['approval_sha256']!=digest(consent)
                or consumed['admission_sha256']!=digest(original) or owner_live(consumed)):
            raise RuntimeError('maintenance_recovery_parent_not_interrupted')
        entries=approvals.history(parent,key)
        if not entries or entries[-1]['state'] not in {'EXECUTING','VERIFYING','RECOVERY_REQUIRED'}:
            raise RuntimeError('maintenance_recovery_parent_state_invalid')
        snapshot=driver.observe_maintenance_finalization()
        from .schema160_release import isolated_registration
        from .historical_origin import policy as origin_policy
        from .automatic_release_admission import PHYSICAL_RECOVERY
        registration=isolated_registration(driver.contract);origin,_,_=origin_policy(system)
        trust=strict_json(protected(PHYSICAL_RECOVERY/(p['physical_recovery_receipt_sha256']+'.json'),private=True).read_bytes())
        now=int(time.time());start=now if created_at is None else created_at
        cap=min(start+min(1800,p['execution_max_seconds']),registration['expires_at'],origin['expires_at'],trust['expires_at'])
        end=cap if expires_at is None else expires_at
        if not start<=now<end<=cap:raise RuntimeError('maintenance_recovery_expired_or_extended')
        return validate({'version':1,'kind':KIND,'action':ACTION,'request_id':request_id,
            'parent_request_id':parent_id,'parent_request_sha256':digest(request),
            'parent_consumption_sha256':digest(consumed),'parent_approval_sha256':digest(consent),
            'parent_audit_sha256':digest(entries),'context_sha256':original['context_sha256'],
            'operation_id':original['operation_id'],'attempt_id':original['attempt_id'],
            'source_sha':original['source_sha'],'controller_sha':original['controller_sha'],
            'contract':driver.contract,'observation':snapshot,'policy_sha256':digest(p),
            'created_at':start,'expires_at':end})


def create(system,parent_id):
    p,key=policy(system);request_id=str(uuid.uuid4())
    value=observe(system,parent_id,request_id)
    if value['policy_sha256']!=digest(p):raise RuntimeError('exceptional_policy_changed')
    with approvals.journal_lock(request_id) as path:
        approvals.event(path,key,'DISCOVERED',{'parent_request_id':parent_id,'action':ACTION})
        approvals.event(path,key,'CI_PENDING',{'source_sha':value['controller_sha']})
        request={'version':1,'request_id':request_id,'admission':value,'admission_sha256':digest(value),
            'policy_sha256':digest(p),'created_at':int(time.time()),
            'expires_at':min(value['expires_at'],int(time.time())+p['max_request_seconds']),
            'review':{'action':ACTION,'parent_request_id':parent_id,'observation':value['observation'],
                'limitations':'Finalization only. No SQL, child activation, ownership transfer or route replacement. Original approval remains consumed.'}}
        atomic_json(path/'request.json',approvals.sign(request,key),exclusive=True)
        for state in ('CI_ACCEPTED','STAGING_PENDING','STAGING_ACCEPTED','TECHNICAL_REVIEW_REQUIRED','AWAITING_ADMIN_APPROVAL'):
            approvals.event(path,key,state,{'same_immutable_parent_artifacts':value['parent_request_sha256'],
                'fresh_recovery_observation':digest(value['observation']),'new_ci_or_staging_execution':False})
        return {'request_id':request_id,'request_sha256':digest(request),'state':'AWAITING_ADMIN_APPROVAL','review':request['review']}


def verify(system,value,*,consume=False,token=None):
    validate(value)
    from .schema150_provider_adapter import require_owned_lock
    require_owned_lock(system.automatic_upgrade_lock,system.upgrade_root/'upgrade.lock')
    require_owned_lock(system.deploy_lock_descriptor,system.state_root/'deploy.lock')
    p,key=policy(system)
    if (value['policy_sha256']!=digest(p) or value['controller_sha']!=p['controller_sha']
            or value['contract']['database']['system_identifier']!=p['database_system_identifier']):
        raise RuntimeError('maintenance_recovery_policy_scope_changed')
    with approvals.journal_lock(value['request_id']) as path:
        request=approvals._request(path,key);consent=approvals.verified(path/'approval.json',key)
        state=approvals.history(path,key)[-1]['state']
        if (request['admission']!=value or request['policy_sha256']!=digest(p)
                or consent['request_sha256']!=digest(request)
                or consent['admission_sha256']!=digest(value) or consent['policy_sha256']!=digest(p)
                or not consent['issued_at']<consent['expires_at']<=min(
                    request['expires_at'],value['expires_at'],consent['issued_at']+p['max_approval_seconds'])):
            raise RuntimeError('maintenance_recovery_approval_changed')
        if (path/'revoked.json').exists():raise RuntimeError('exceptional_approval_revoked')
        if int(time.time())>=value['expires_at']:raise RuntimeError('maintenance_recovery_execution_expired')
        owner={'admission_sha256':digest(value),'approval_sha256':digest(consent),
            'parent_consumption_sha256':value['parent_consumption_sha256'],'pid':os.getpid(),
            'process_start':Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],
            'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'execution_expires_at':value['expires_at']}
        consumed=path/'approval-consumed.json'
        # The original signed approval and consumed owner are never modified.
        parent=approvals.root()/value['parent_request_id']
        parent_owner=approvals.verified(parent/'approval-consumed.json',key)
        if (digest(parent_owner)!=value['parent_consumption_sha256'] or owner_live(parent_owner)
                or digest(approvals._request(parent,key))!=value['parent_request_sha256']
                or digest(approvals.verified(parent/'approval.json',key))!=value['parent_approval_sha256']
                or digest(approvals.history(parent,key))!=value['parent_audit_sha256']):
            raise RuntimeError('maintenance_recovery_parent_changed')
        if consume:
            if consumed.exists() or state!='APPROVED':raise RuntimeError('exceptional_approval_consumed_or_not_approved')
            if observe(system,value['parent_request_id'],value['request_id'],created_at=value['created_at'],expires_at=value['expires_at'])!=value:
                raise RuntimeError('maintenance_recovery_observation_changed')
            operator=system.authenticate_operator(token)
            if any(operator[k]!=consent['operator'][k] for k in ('operator_auth_id','policy_sha256','session_id_sha256')):
                raise RuntimeError('exceptional_current_operator_changed')
            current,current_key=policy(system)
            if current!=p or current_key!=key:raise RuntimeError('exceptional_policy_changed')
            if int(time.time())>=min(consent['expires_at'],request['expires_at'],value['expires_at']):
                raise RuntimeError('exceptional_approval_expired')
            approvals.event(path,key,'REVALIDATING',{'parent_consumption_sha256':value['parent_consumption_sha256']})
            atomic_json(consumed,approvals.sign(owner,key),exclusive=True)
            approvals.event(path,key,'AUTHORIZED_FOR_EXECUTION',{'consumption_sha256':digest(owner)})
        elif (not consumed.exists() or approvals.verified(consumed,key)!=owner
                or state not in {'AUTHORIZED_FOR_EXECUTION','EXECUTING','VERIFYING'}):
            raise RuntimeError('maintenance_recovery_not_current_owner')
        return consent


def require_lease(system,contract,value):
    if value['contract']!=contract:raise RuntimeError('maintenance_recovery_contract_changed')
    consent=verify(system,value)
    # The root issuer projects this fresh request's identity, not the old lease.
    # Existing hash-bound/live-parent checks are retained in the child verifier.
    return {'version':1,'kind':'canonical-exceptional-operation-lease','request_id':value['request_id'],
        'approval_sha256':digest(consent),'admission_sha256':digest(value),'context_sha256':value['context_sha256'],
        'operation_id':value['operation_id'],'attempt_id':value['attempt_id'],
        'execution_expires_at':value['expires_at'],'pid':os.getpid(),
        'process_start':Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],
        'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
