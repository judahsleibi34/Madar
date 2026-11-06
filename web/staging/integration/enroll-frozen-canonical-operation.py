from automatic_rpc import ROOT,EVIDENCE,GUEST,MANIFEST,call
from remote_template import render
from pathlib import Path
import json,base64,sys,subprocess
sys.path.insert(0,'/opt/madar-development/repository/web')
from deployment.lib.migration_inventory import canonical
fault=MANIFEST.get('fault_boundary')
if fault not in (None,'ingress_finalization'):raise RuntimeError('canonical_fault_scope_unsupported')
result=json.loads((ROOT/'canonical-package-result.json').read_bytes())
script=render("""from pathlib import Path
import sys,time,hashlib
sys.path.insert(0,'/opt/madar/control-plane')
from deployment.lib.control_plane_upgrade import SystemOperations
from deployment.lib.isolated_release_environment import observe
from deployment.lib.migration_executor import atomic_json
from deployment.lib.migration_inventory import digest as compact_digest
from deployment.lib.completed_normal_admission import digest
from deployment.lib.schema160_release import ISOLATED_REGISTRATION,isolated_registration
from deployment.lib import exceptional_release_approval as approval
result=RESULT;package=Path(result['package']);document=json.loads((package/'plan.json').read_bytes());contract={**document['admission_contract'],'plan_sha256':digest(document)}
sys.path.insert(0,str(package/'source/web/staging/integration'))
from canonical_acceptance_window import REMOTE_REQUEST_TIMEOUT
assert digest(contract)==result['context_sha256'] and digest(document)==result['plan_sha256']
system=SystemOperations();host=observe();now=int(time.time());origin=json.loads(Path('/etc/madar/historical-origin-policy.json').read_bytes())
trust=json.loads((Path('/etc/madar/independent-test-recovery')/(document['independent_recovery']['receipt_sha256']+'.json')).read_bytes())
registration={'version':1,'kind':'isolated-canonical-controller-acceptance','environment_id':'isolated-'+host['realm_id'],**{k:host[k] for k in ('guest_uuid','machine_id','root_filesystem_uuid')},'operation':contract['operation'],'context_sha256':digest(contract),'plan_sha256':digest(document),'controller_sha':system.installed_sha(),'application_sha':contract['candidate']['source_sha'],'database_system_identifier':host['database_system_identifier'],'origin_schema':146,'target_schema':160,'created_at':now,'expires_at':min(now+10800,origin['expires_at'],trust['expires_at'])}
atomic_json(ISOLATED_REGISTRATION,registration,exclusive=True);ISOLATED_REGISTRATION.chmod(0o444);isolated_registration(contract)
scope={'context_sha256':digest(contract),'plan_sha256':digest(document),'source_bundle_sha256':document['source_bundle_sha256'],'enrollment_sha256':contract['source_roles']['enrollment_sha256'],'candidate_source_sha':contract['candidate']['source_sha'],'operation_id':document['operation_id'],'attempt_id':document['attempt_id']};approval.validate_canonical_scope(scope)
p={'version':2,'policy_id':'isolated-exact-canonical146-160-'+document['attempt_id'],'environment_id':registration['environment_id'],'database_system_identifier':registration['database_system_identifier'],'controller_sha':system.installed_sha(),'enabled':True,'contracts':[approval.CANONICAL],'approval_key_sha256':hashlib.sha256(approval.KEY.read_bytes()).hexdigest(),'max_approval_seconds':300,'max_request_seconds':600,'require_physical_restore':True,'physical_recovery_receipt_sha256':trust['receipt_sha256'],'canonical_scope':scope,'execution_max_seconds':REMOTE_REQUEST_TIMEOUT}
if FAULT is not None:
 p.update(version=3,recovery_actions=['finalize-target160-v1'])
atomic_json(approval.POLICY,p,exclusive=True);approval.policy(system)
print(json.dumps({'registration':registration,'exact_approval_policy':p,'package':str(package),'plan_sha256':digest(document),'context_sha256':digest(contract),'operation_id':document['operation_id'],'attempt_id':document['attempt_id'],'production_authorization':False,'approval_issued':False,'sql_migration_executed':False}))
""",RESULT=result,FAULT=fault)
v=json.loads(call(script,name='independent-frozen-canonical-operation-registration',timeout=120));(ROOT/'canonical-operation-registration.json').write_bytes(canonical(v));(EVIDENCE/'independent-frozen-canonical-operation-registration.json').write_bytes(canonical(v))
# Pin the same exact plan and stage scopes at the independently protected receiver.
receiver=json.loads((ROOT/'maintenance-receiver.json').read_bytes());policy=receiver['policy'];base=receiver['receiver']['base']
from deployment.lib.completed_normal_admission import digest as context_digest
scope=v['context_sha256'];enrollment={'version':1,'kind':'independently-enrolled-maintenance-replica','policy':policy,'policy_sha256':receiver['policy_sha256'],'machine_id':receiver['receiver']['machine_id'],'context_sha256':scope,'plan_sha256':v['plan_sha256'],'stage_scopes':{stage:context_digest({'operation':'completed-normal-schema146-160-coordinated-release','context_sha256':scope,'backup_stage':stage}) for stage in ('pre-migration','post-migration')}}
node=['ssh','-o','BatchMode=yes','-o','ForwardAgent=no','-o','ClearAllForwardings=yes','-o','StrictHostKeyChecking=yes','-o','UpdateHostKeys=no','-o','ConnectTimeout=10','madar-node1-lan','sudo -n python3 -B -']
s=render("""from pathlib import Path
import sys,json,hashlib
root=Path(BASE);ownership=json.loads((root/'ownership.json').read_bytes());assert ownership['receiver_id']==ENROLLMENT['policy']['receiver_id'] and ownership['source_guest_uuid']==ENROLLMENT['policy']['guest_uuid']
sys.path.insert(0,str(root/'source/web'))
from deployment.lib.migration_executor import atomic_json
from deployment.lib.isolated_backup_replica import validate_policy
import time
validate_policy(ENROLLMENT['policy'],now=int(time.time()));atomic_json(root/'maintenance-enrollment.json',ENROLLMENT,exclusive=True)
print(json.dumps({'receiver_id':ownership['receiver_id'],'context_sha256':ENROLLMENT['context_sha256'],'plan_sha256':ENROLLMENT['plan_sha256'],'stage_scopes':ENROLLMENT['stage_scopes'],'authority_issued':False}))
""",BASE=base,ENROLLMENT=enrollment)
p=subprocess.run(node,input=s.encode(),capture_output=True,timeout=60);(EVIDENCE/'private-independent-maintenance-exact-plan-enrollment.log').write_bytes(p.stdout+p.stderr);assert p.returncode==0
(ROOT/'maintenance-exact-enrollment.json').write_bytes(canonical(enrollment));print(json.dumps({'operation_id':v['operation_id'],'attempt_id':v['attempt_id'],'registered_exact_scope':True,'independent_maintenance_receiver_enrolled':True,'approval_issued':False}),flush=True)
