from pathlib import Path
from automatic_rpc import call,EVIDENCE,ROOT,MANIFEST
import json,hashlib,subprocess
key=ROOT/'independent-observer.key';public=ROOT/'independent-observer.pub'
assert key.stat().st_uid==1000 and key.stat().st_mode&0o077==0 and len(public.read_bytes())==32
trust={'public_sha256':hashlib.sha256(public.read_bytes()).hexdigest(),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'commands':['historical_origin.observe(SystemOperations(), pinned_policy, live_isolated_environment)','installed CLI historical-origin prepare/enroll/inspect; never release or migration execution']}
from canonical_acceptance_window import fresh_historical_enrollment_expiry
import time
enrollment_deadline=fresh_historical_enrollment_expiry(MANIFEST,now=int(time.time()))
script="""from pathlib import Path
import sys,hashlib,time
ENROLLMENT_DEADLINE="""+repr(enrollment_deadline)+"""
assert int(time.time())<ENROLLMENT_DEADLINE<=int(time.time())+10800
sys.path.insert(0,'/opt/madar/control-plane')
from deployment.lib.control_plane_upgrade import SystemOperations
from deployment.lib.migration_executor import atomic_json
from deployment.lib.migration_inventory import digest
from deployment.lib.active_recovery_inputs import controller_tree_digest
from deployment.lib.automatic_release_admission import EXECUTION_POLICY
from deployment.lib.isolated_release_environment import observe
from deployment.lib import historical_origin as origin
trust="""+repr(trust)+"""
system=SystemOperations();environment=observe();state=json.loads(Path('/var/lib/madar/releases/state.json').read_bytes());source=state['known_good_release']['sha'];slot=state['active_slot']
assert not (state.get('known_good_release') or {}).get('historical_origin'), 'historical_origin_already_enrolled'
assert not list(Path('/var/lib/madar-control-plane/upgrades/automatic-admissions/historical-origins').glob('*/bootstrap-origin-consumed.json')), 'historical_origin_already_consumed'
execution=json.loads(EXECUTION_POLICY.read_bytes());execution.update(controller_sha=system.installed_sha(),controller_tree_sha256=controller_tree_digest(),test_public_key_sha256=trust['public_sha256'],test_runner_sha256=trust['runner_sha256'],test_commands_sha256=digest(trust['commands']));atomic_json(EXECUTION_POLICY,execution)
routine_path=Path('/etc/madar/migration-policy.json');routine=json.loads(routine_path.read_bytes());assert routine['enabled'] is False;routine.update(controller_sha=system.installed_sha(),expires_at=int(time.time())+3600);atomic_json(routine_path,routine)
redis=json.loads(subprocess.check_output(['docker','inspect','madar-'+slot+'-redis']))[0]['Image']
contract={'version':8,'operation':'completed-normal-schema146-160-coordinated-release','source_roles':{'application_sha':source},'database':{'system_identifier':environment['database_system_identifier']},'candidate':{'source_sha':'e5b48db27d98ddf582108efe9a27cc1dd6b54012','controller_sha':system.installed_sha(),'images':{'backend':'sha256:32ccb92443a7030969dab02720107d66f874132b5c66cf0fb8a1567ba7b1e661','frontend':'sha256:e620a92e4ff312076be4207f936cd86bee837c79d6717425bf8e8d3d8005d174'},'redis_image':redis},'migration_manifest_sha256':'7633a15a9f531874409577fb9696e472631d3bbde63ae2603be0a4d23ef7c08f'}
intent=origin.successor_intent(contract)
images={role:json.loads(subprocess.check_output(['docker','inspect','madar-'+slot+'-'+role]))[0]['Image'] for role in ('backend','frontend')}
p={'version':1,'kind':origin.KIND,'environment_id':execution['environment_id'],'database_system_identifier':environment['database_system_identifier'],'controller_sha':system.installed_sha(),'source_sha':source,'source_tree_sha':subprocess.check_output(['git','-C','/srv/madar/production','rev-parse',source+'^{tree}']).decode().strip(),'images':images,'observation_sha256':'0'*64,'approval_key_sha256':hashlib.sha256(Path('/etc/madar/release-approval.key').read_bytes()).hexdigest(),'successor_intent_sha256':digest(intent),'expires_at':ENROLLMENT_DEADLINE,'max_request_seconds':600}
if origin.POLICY.exists():
 old=json.loads(origin.POLICY.read_bytes());assert old['observation_sha256']=='0'*64
 assert not (state.get('known_good_release') or {}).get('historical_origin')
 assert not list(Path('/var/lib/madar-control-plane/upgrades/automatic-admissions/historical-origins').glob('*/bootstrap-origin-consumed.json'))
 oldpath=Path('/opt/madar-test/origin146/failed-origin-policy-'+digest(old)+'.json')
 if not oldpath.exists():atomic_json(oldpath,old,exclusive=True)
atomic_json(origin.POLICY,p)
p,key,environment=origin.policy(system)
value=origin.observe(system,p,environment)
atomic_json(Path('/opt/madar-test/origin146/independent-parent-observation.json'),value)
p['observation_sha256']=digest(value);atomic_json(origin.POLICY,p)
print(json.dumps({'kind':origin.KIND,'observation':value,'observation_sha256':digest(value),'policy_sha256':digest(p),'successor_intent':intent,'source':source,'installed_controller':system.installed_sha(),'enrollment_issued':False,'migration_authority_issued':False}))
"""
result=json.loads(call(script,name='historical-native-independent-observation',timeout=240))
(EVIDENCE/'historical-native-independent-observation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='observation'}))
