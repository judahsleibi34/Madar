"""Owned F04 orchestration through real installed CLI and existing fault adapter.

This supplies neither approval signatures nor SQL. Fresh test operator AAL2 and
the independently enrolled version3 issuer are mandatory. Secrets stay private.
"""
import hashlib
import json
import subprocess
import threading
import time
from pathlib import Path

from canonical_acceptance_window import bounded_child,execute_protected_child,REMOTE_REQUEST_TIMEOUT,FAULT_RECOVERY_SECONDS


def execute_and_recover(*,base,arguments,operation,review,scope,system,token,started,session,smoke):
    from deployment.lib import exceptional_release_approval as approval
    from deployment.lib.completed_normal_maintenance_recovery import ACTION
    from deployment.lib.migration_executor import atomic_json
    from deployment.lib.migration_inventory import digest
    p,_=approval.policy(system)
    if p['version']!=3 or p['recovery_actions']!=[ACTION]:
        raise RuntimeError('fault_rehearsal_recovery_not_enrolled')
    value=scope['request']['admission'];package=Path(value['source_package'])
    root=Path('/var/lib/madar-control-plane/upgrades/completed-normal-admissions')/value['context_sha256']
    output=Path('/opt/madar-test/origin146');cancel=threading.Event();result={}
    adapter=package/'source/web/staging/integration/canonical_fault_adapter.py'
    helper=adapter.with_name('canonical_fault_matrix.py')
    deadline=time.monotonic()+max(0,REMOTE_REQUEST_TIMEOUT-(time.monotonic()-started)-60)

    def watch():
        try:
            while not cancel.wait(.2):
                if time.monotonic()>=deadline:raise RuntimeError('fault_rehearsal_boundary_timeout')
                events=root/'boot-events.jsonl'
                if not events.exists():continue
                lines=events.read_text().splitlines()
                if not lines:continue
                try:phase=json.loads(lines[-1])['phase']
                except (ValueError,KeyError):continue  # An append may still be in progress.
                if phase not in {'accepted_workers_and_ingress_pending','service_adopt_completed'}:continue
                from deployment.lib.schema160_release import isolated_registration
                registration=isolated_registration(value['contract'])
                now=int(time.time());expires=min(now+900,value['expires_at'],registration['expires_at'])
                if expires<=now+60:raise RuntimeError('fault_rehearsal_window_insufficient')
                plan={'version':1,'boundary':'ingress_finalization','request_id':review['request_id'],
                    'request_sha256':review['request_sha256'],'context_sha256':value['context_sha256'],
                    'controller_sha':value['controller_sha'],'guest_uuid':registration['guest_uuid'],
                    'operation_id':value['operation_id'],'expires_at':expires,
                    'adapter_sha256':hashlib.sha256(adapter.read_bytes()).hexdigest(),
                    'helper_sha256':hashlib.sha256(helper.read_bytes()).hexdigest()}
                plan_path=output/'fault-plan.json';atomic_json(plan_path,plan,exclusive=True);plan_path.chmod(0o400)
                fault=bounded_child(['/usr/bin/python3','-I','-B',str(adapter),'--plan',str(plan_path)],
                    timeout=expires-time.time(),log=output/'canonical-fault.log')
                if fault.returncode:raise RuntimeError('fault_rehearsal_injection_refused')
                result['fault']=json.loads(fault.stdout)
                return
        except Exception as error:result['error']=type(error).__name__+':'+str(error)

    watcher=threading.Thread(target=watch,daemon=True);watcher.start()
    try:
        interrupted=execute_protected_child(base+['approved-execute',*operation],input=token.encode(),
            started=started,expires_at=value['expires_at'],log=output/'canonical-approved-execution.log')
    finally:
        cancel.set();watcher.join(timeout=10)
    if watcher.is_alive() or 'error' in result or result.get('fault',{}).get('fault_injected') is not True:
        raise RuntimeError('fault_rehearsal_no_verified_interruption')
    if interrupted.returncode==0:raise RuntimeError('fault_rehearsal_unexpected_deployment_completion')
    parent=approval.inspect(system,review['request_id'])
    if parent['state']!='RECOVERY_REQUIRED' or not parent['consumed'] or (root/'normal-completion.json').exists():
        raise RuntimeError('fault_rehearsal_parent_not_recoverable')
    parent_consumption=approval.root()/review['request_id']/'approval-consumed.json'
    original_consumption=hashlib.sha256(parent_consumption.read_bytes()).hexdigest()
    from deployment.lib.schema160_release import isolated_registration
    recovery_expiry=isolated_registration(value['contract'])['expires_at']

    def invoke(mode,extra=(),secret=None,minimum=30):
        remaining=int(min(REMOTE_REQUEST_TIMEOUT+FAULT_RECOVERY_SECONDS-(time.monotonic()-started)-60,
                          recovery_expiry-time.time()-30))
        if remaining<minimum:raise RuntimeError('fault_rehearsal_recovery_window_insufficient')
        response=bounded_child(base+[mode,*arguments,*extra],timeout=remaining,
            input=secret.encode() if secret else None,log=output/('canonical-'+mode+'.log'))
        if response.returncode:raise RuntimeError('fault_rehearsal_recovery_cli_refused')
        envelope=json.loads(response.stdout)
        if envelope['operation']!=mode:raise RuntimeError('fault_rehearsal_cli_identity_changed')
        return envelope['result']

    requested=invoke('recovery-prepare',['--request-id',review['request_id']])
    if requested['state']!='AWAITING_ADMIN_APPROVAL':raise RuntimeError('fault_rehearsal_request_not_pending')
    recovery_expiry=approval.inspect(system,requested['request_id'])['request']['admission']['expires_at']
    consent=['--request-id',requested['request_id'],'--confirm-request-digest',requested['request_sha256']]
    # Actual independent test provider, not a signed test packet or a mock AAL2.
    login,_=smoke.http('POST','/token?grant_type=password',body={'email':session['email'],'password':session['password']})
    challenge,_=smoke.http('POST','/factors/'+session['factor_id']+'/challenge',token=login['access_token'],body={})
    step=int(time.time())//30
    while int(time.time())//30==step:time.sleep(.2)
    elevated,_=smoke.http('POST','/factors/'+session['factor_id']+'/verify',token=login['access_token'],
        body={'challenge_id':challenge['id'],'code':smoke.totp(session['totp_secret'])})
    identity=system.authenticate_operator(elevated['access_token'])
    approved=invoke('approval-approve',consent,elevated['access_token'])
    if approved['state']!='APPROVED':raise RuntimeError('fault_rehearsal_approval_not_issued')
    challenge,_=smoke.http('POST','/factors/'+session['factor_id']+'/challenge',token=elevated['access_token'],body={})
    step=int(time.time())//30
    while int(time.time())//30==step:time.sleep(.2)
    fresh,_=smoke.http('POST','/factors/'+session['factor_id']+'/verify',token=elevated['access_token'],
        body={'challenge_id':challenge['id'],'code':smoke.totp(session['totp_secret'])})
    actual=system.authenticate_operator(fresh['access_token'])
    if any(actual[k]!=identity[k] for k in ('operator_auth_id','policy_sha256','session_id_sha256')):
        raise RuntimeError('fault_rehearsal_operator_session_changed')
    recovered=invoke('recovery-execute',consent,fresh['access_token'],minimum=300)
    status=approval.inspect(system,requested['request_id'])
    if (status['state']!='COMPLETED' or not status['consumed'] or recovered['migration_sql_executed'] is not False
            or hashlib.sha256(parent_consumption.read_bytes()).hexdigest()!=original_consumption):
        raise RuntimeError('fault_rehearsal_recovery_not_completed')
    evidence={'boundary':'ingress_finalization','parent_request_id':review['request_id'],
        'parent_consumption_sha256':original_consumption,'recovery_request_id':requested['request_id'],
        'recovery_request_sha256':requested['request_sha256'],'fault':result['fault'],
        'recovered':recovered,'original_approval_reused':False,'operator':identity}
    atomic_json(output/'canonical-actual-fault-recovery.json',evidence,exclusive=True)
    return evidence
