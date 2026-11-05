"""Explicit independently controlled isolated test administrator action.

Uses actual fresh operator AAL2 and exact CLI consent. It never signs approval,
writes SQL, supplies caller PASS fields, or issues production authority.
"""
from automatic_rpc import ROOT,EVIDENCE,MANIFEST,call
from remote_template import render
from pathlib import Path
import json,sys
from canonical_acceptance_window import REMOTE_REQUEST_TIMEOUT,FAULT_RECOVERY_SECONDS
def canonical(value):
 return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
# Extra native acceptance gate before any new one-time approval. This is a
# synthetic restore test, never authority or replacement recovery evidence.
native=EVIDENCE/'actual-preapproval-native-maintenance-restore.json'
if not native.exists():raise RuntimeError('preapproval_native_restore_acceptance_missing')
proof=json.loads(native.read_bytes())
assert proof['status']=='PASS' and proof['source_sha']==MANIFEST['source_current']
assert proof['owned_containers_removed'] is True and proof['scratch_removed'] is True
fault=MANIFEST.get('fault_boundary')
if fault not in (None,'ingress_finalization'):raise RuntimeError('canonical_fault_scope_unsupported')
result=json.loads((ROOT/'canonical-package-result.json').read_bytes())
script=render("""from pathlib import Path
import sys,time,hashlib
remote_started=time.monotonic()
sys.path[:0]=['/opt/madar/control-plane','/opt/madar-test/controller/web/staging/integration']
from deployment.lib.migration_executor import atomic_json
from deployment.lib.control_plane_upgrade import SystemOperations
result=RESULT;package=Path(result['package']);document=json.loads((package/'plan.json').read_bytes());system=SystemOperations()
assert system.installed_sha()==document['controller_source_sha']==CONTROLLER
sys.path.insert(0,str(package/'source/web/staging/integration'))
from canonical_acceptance_window import execute_protected_child
entry=package/'source/web/scripts/continue_completed_normal_upgrade.py'
base=['/usr/bin/python3','-I','-B',str(entry)]
arguments=['--source-package',str(package),'--approved-source',result['source_bundle_sha256'],'--approved-plan',result['plan_sha256']]
log=Path('/opt/madar-test/origin146/canonical-approval-prepare.log')
if log.exists():
 envelope=json.loads(log.read_bytes());assert envelope['operation']=='approval-prepare'
 review=envelope['result']
 inspected=subprocess.run(base+['approval-inspect',*arguments,'--request-id',review['request_id']],capture_output=True,timeout=60)
 assert inspected.returncode==0
 status=json.loads(inspected.stdout);assert status['operation']=='approval-inspect' and status['result']['state']=='AWAITING_ADMIN_APPROVAL' and status['result']['request_sha256']==review['request_sha256'] and not status['result']['consumed']
else:
 prepared=subprocess.run(base+['approval-prepare',*arguments],capture_output=True,timeout=480)
 log.write_bytes(prepared.stdout+prepared.stderr);log.chmod(0o600)
 if prepared.returncode:raise RuntimeError('actual_canonical_approval_prepare_refused')
 envelope=json.loads(prepared.stdout);assert envelope['operation']=='approval-prepare';review=envelope['result']
assert review['state']=='AWAITING_ADMIN_APPROVAL'
view=review['review'];assert view['source_sha']==document['admission_contract']['candidate']['source_sha'] and view['controller_sha']==system.installed_sha()
assert view['origin_schema']==146 and view['target_schema']==160 and view['database_system_identifier']==document['admission_contract']['database']['system_identifier']
assert view['manifest_sha256']=='7633a15a9f531874409577fb9696e472631d3bbde63ae2603be0a4d23ef7c08f'
assert [row['number'] for row in view['sql']]==list(range(147,161))
atomic_json(Path('/opt/madar-test/origin146/canonical-approval-review.json'),review,exclusive=True)
operation=arguments+['--request-id',review['request_id'],'--confirm-request-digest',review['request_sha256']]
missing=subprocess.run(base+['approved-execute',*operation],input=b'',capture_output=True,timeout=90)
assert missing.returncode and json.loads(missing.stdout)['failure_code']=='exceptional_canonical_explicit_approved_request_required'
print(json.dumps({'actual_missing_approval_refused':True,'request_id':review['request_id'],'request_sha256':review['request_sha256'],'review':view}),flush=True)
sessionfile=Path('/opt/madar-test/operator-fixture/private-session.json');session=json.loads(sessionfile.read_bytes());facts=json.loads(Path('/opt/madar-test/operator-fixture/facts.json').read_bytes())
import smoke
smoke.PROVIDER=facts['auth_user_url'].removesuffix('/user');smoke.APPLICATION='http://127.0.0.1:8001/api'
login,_=smoke.http('POST','/token?grant_type=password',body={'email':session['email'],'password':session['password']})
challenge,_=smoke.http('POST','/factors/'+session['factor_id']+'/challenge',token=login['access_token'],body={})
step=int(time.time())//30
while int(time.time())//30==step:time.sleep(.2)
elevated,_=smoke.http('POST','/factors/'+session['factor_id']+'/verify',token=login['access_token'],body={'challenge_id':challenge['id'],'code':smoke.totp(session['totp_secret'])})
identity=system.authenticate_operator(elevated['access_token']);assert identity['aal']=='aal2' and identity['operator_auth_id']==facts['operator_auth_id']
approved=subprocess.run(base+['approval-approve',*operation],input=elevated['access_token'].encode(),capture_output=True,timeout=480)
log=Path('/opt/madar-test/origin146/canonical-approval-issue.log');log.write_bytes(approved.stdout+approved.stderr);log.chmod(0o600)
if approved.returncode:raise RuntimeError('actual_canonical_exact_approval_refused')
approval_envelope=json.loads(approved.stdout);assert approval_envelope['operation']=='approval-approve';approval=approval_envelope['result'];atomic_json(Path('/opt/madar-test/origin146/canonical-genuine-approval.json'),approval,exclusive=True)
print(json.dumps({'genuine_exact_operator_approval':True,'operator':identity,'approval':approval}),flush=True)
# Explicit fresh MFA for execution in the SAME approved operator session.
challenge,_=smoke.http('POST','/factors/'+session['factor_id']+'/challenge',token=elevated['access_token'],body={})
step=int(time.time())//30
while int(time.time())//30==step:time.sleep(.2)
renewed,_=smoke.http('POST','/factors/'+session['factor_id']+'/verify',token=elevated['access_token'],body={'challenge_id':challenge['id'],'code':smoke.totp(session['totp_secret'])})
execution_identity=system.authenticate_operator(renewed['access_token'])
assert all(execution_identity[k]==identity[k] for k in ('operator_auth_id','policy_sha256','session_id_sha256'))
elevated=renewed
print(json.dumps({'execution_mfa_fresh':True,'same_approved_operator_session':True}),flush=True)
# Actual installed/frozen protected controller owns every SQL and runtime effect.
from deployment.lib import exceptional_release_approval as approval_api
scope=approval_api.inspect(system,review['request_id'])
assert scope['state']=='APPROVED' and not scope['consumed']
log=Path('/opt/madar-test/origin146/canonical-approved-execution.log')
fault_recovery=None
if FAULT is None:
 executed=execute_protected_child(base+['approved-execute',*operation],input=elevated['access_token'].encode(),started=remote_started,expires_at=scope['request']['admission']['expires_at'],log=log)
 if executed.returncode:raise RuntimeError('actual_canonical_protected_execution_failed')
 completion_envelope=json.loads(executed.stdout);assert completion_envelope['operation']=='approved-execute';completion=completion_envelope['result']
 completed_request_id=review['request_id'];completed_request_sha256=review['request_sha256']
else:
 from canonical_finalization_rehearsal import execute_and_recover
 fault_recovery=execute_and_recover(base=base,arguments=arguments,operation=operation,review=review,scope=scope,system=system,token=elevated['access_token'],started=remote_started,session=session,smoke=smoke)
 completion=fault_recovery['recovered']['completion']
 completed_request_id=fault_recovery['recovery_request_id'];completed_request_sha256=fault_recovery['recovery_request_sha256']
assert completion['schema']==160 and completion['mode']=='NORMAL'
root=Path('/var/lib/madar-control-plane/upgrades/completed-normal-admissions')/result['context_sha256']
receipts={}
for name in ('normal-completion.json','normal-acceptance.json','migration-execution.json','operator-authorization.json','worker-owner.json','boot-installation.json','pre-migration-backup.json','post-migration-backup.json'):
 path=root/name
 if path.exists():receipts[name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'record':json.loads(path.read_bytes())}
assert receipts['normal-completion.json']['record']==completion
state=json.loads((system.state_root/'state.json').read_bytes());assert state['known_good_release']['schema']==160 and not state.get('in_progress_release')
report={'controller_sha':system.installed_sha(),'source_sha':completion['application_sha'],'database_system_identifier':view['database_system_identifier'],'origin_schema':146,'target_schema':160,'operation_id':document['operation_id'],'attempt_id':document['attempt_id'],'approval_request_id':completed_request_id,'request_sha256':completed_request_sha256,'fault_recovery':fault_recovery,'completion':completion,'receipts':receipts,'release_state':state,'production_modified':False}
atomic_json(Path('/opt/madar-test/origin146/canonical-actual-completed-report.json'),report,exclusive=True)
print(json.dumps(report),flush=True)
""",RESULT=result,CONTROLLER=MANIFEST['source_current'],FAULT=fault)
try:
 raw=call(script,name='actual-protected-canonical-approval-and-execution',timeout=REMOTE_REQUEST_TIMEOUT+(FAULT_RECOVERY_SECONDS if fault is not None else 0))
finally:
 # Capture the existing authentic root journals regardless of the operation's
 # result. This witness grants no authority and never changes source state.
 import subprocess
 captured=subprocess.run([sys.executable,'-B',str(ROOT/'capture-authenticated-controller-journals.py')],capture_output=True,timeout=100)
 path=EVIDENCE/'private-finally-controller-journal-capture.log';path.write_bytes(captured.stdout+captured.stderr);path.chmod(0o600)
records=[json.loads(line) for line in raw.splitlines() if line.startswith(b'{')];assert records[-1]['target_schema']==160
(EVIDENCE/'actual-protected-canonical-approval-and-execution.json').write_bytes(canonical(records[-1]));(ROOT/'canonical-completed.json').write_bytes(canonical(records[-1]));print(json.dumps(records[-1]),flush=True)
