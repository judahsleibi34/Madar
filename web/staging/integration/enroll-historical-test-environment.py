from automatic_rpc import call,EVIDENCE,MANIFEST
import json
from canonical_acceptance_window import fresh_historical_enrollment_expiry
import time
enrollment_deadline=fresh_historical_enrollment_expiry(MANIFEST,now=int(time.time()))
script="""from pathlib import Path
import sys,os,time,hashlib,secrets
from datetime import datetime,timezone
ENROLLMENT_DEADLINE="""+repr(enrollment_deadline)+"""
assert int(time.time())<ENROLLMENT_DEADLINE<=int(time.time())+10800
sys.path.insert(0,'/opt/madar/control-plane')
assert not Path('/etc/madar/release-approval.key').exists(), 'historical_test_enrollment_already_prepared'
from deployment.lib.isolated_release_environment import observe_effect_fence,required_rules,TABLE,measure_bind_source,observe
from deployment.lib.completed_normal_resources import measured_spec
from deployment.lib.migration_inventory import canonical,digest
from deployment.lib.migration_executor import atomic_json
from deployment.lib.control_plane_upgrade import SystemOperations
from deployment.lib.active_recovery_inputs import controller_tree_digest
state=json.loads(Path('/opt/madar-test/origin146/private.json').read_bytes());realm=state['realm_id'];system=SystemOperations();now=int(time.time())
try:
 nic=observe_effect_fence(execution=True);already_strict=True
except RuntimeError:
 nic=observe_effect_fence(execution=False);already_strict=False
batch=[{'delete':{'table':{'family':'inet','name':TABLE}}},{'add':{'table':{'family':'inet','name':TABLE}}}]
for chain,rules in required_rules(nic,execution=True).items():
 batch.append({'add':{'chain':{'family':'inet','table':TABLE,'name':chain,'type':'filter','hook':chain,'prio':200,'policy':'accept'}}})
 for rule in rules:batch.append({'add':{'rule':{'family':'inet','table':TABLE,'chain':chain,'expr':rule}}})
if not already_strict:subprocess.run(['nft','--json','-f','-'],input=json.dumps({'nftables':batch}).encode(),check=True,capture_output=True)
assert observe_effect_fence(execution=True)==nic
model_path=Path('/opt/madar-test/origin146/application.json');model=json.loads(model_path.read_bytes())
for role,item in model['services'].items():
 row=json.loads(subprocess.check_output(['docker','inspect','madar-green-'+role]))[0]
 assert row['Config']['Labels']['com.madar.test.realm']==realm
 if row['HostConfig'].get('PidsLimit') is None:
  subprocess.run(['docker','update','--pids-limit','128',row['Id']],check=True,capture_output=True);item['pids_limit']=128
model_path.write_text(json.dumps(model));os.chown(model_path,1000,1000);model_path.chmod(0o600)
ids=subprocess.check_output(['docker','ps','-aq','--no-trunc']).decode().split();rows=json.loads(subprocess.check_output(['docker','inspect',*ids]));scope={}
for row in rows:
 assert row['Config']['Labels']['com.madar.test.realm']==realm
 scope[row['Id']]={'name':row['Name'],'image':row['Image'],'spec_sha256':measured_spec(row),'binds':{m['Destination']:measure_bind_source(m['Source'],mutable=m['RW']) for m in row['Mounts'] if m['Type']=='bind'}}
db=next(r for r in rows if r['Name']=='/supabase-db')
environment={'version':2,'realm_id':realm,'guest_uuid':Path('/sys/class/dmi/id/product_uuid').read_text().strip().lower(),'machine_id':Path('/etc/machine-id').read_text().strip(),'root_filesystem_uuid':subprocess.check_output(['findmnt','-n','-o','UUID','/']).decode().strip(),'expires_at':datetime.fromtimestamp(ENROLLMENT_DEADLINE,timezone.utc).isoformat(),'database_container_id':db['Id'],'database_system_identifier':state['database_system_identifier'],'denied_database_identifiers':['7693515850808332323','7699838575921704994'],'runtime_scope':scope}
atomic_json(Path('/etc/madar/isolated-release-test.json'),environment);observed=observe();assert observed['version']==2
execution={'version':2,'enabled':True,'environment':'isolated-test','environment_id':'isolated-'+realm,'controller_sha':system.installed_sha(),'controller_tree_sha256':controller_tree_digest(),'test_public_key_sha256':hashlib.sha256(b'no release evidence key enrolled by bootstrap').hexdigest(),'test_runner_sha256':hashlib.sha256(b'parent-controlled historical origin native observers only').hexdigest(),'test_commands_sha256':digest(['bootstrap enrollment; no CI or staging release receipt issued']),'evidence_max_age_seconds':600,'operation_max_seconds':900,'recovery_max_age_seconds':86400,'physical_recovery_max_age_seconds':3600,'denied_database_identifiers':environment['denied_database_identifiers']}
# No routine release dispatch is enabled or given authenticated release evidence.
atomic_json(Path('/etc/madar/automatic-release-execution.json'),execution)
from deployment.lib.automatic_release_admission import EXECUTION_POLICY
if EXECUTION_POLICY!=Path('/etc/madar/automatic-release-execution.json'):
 Path('/etc/madar/automatic-release-execution.json').unlink();atomic_json(EXECUTION_POLICY,execution)
routine={'version':1,'policy_id':'isolated-historical-identity-only','environment_id':'isolated-'+realm,'database_system_identifier':state['database_system_identifier'],'controller_sha':system.installed_sha(),'repository':'judahsleibi34/Madar','branch':'refs/heads/main','enabled':False,'expires_at':now+3600,'max_migrations':1,'risk_classes':['A'],'automation_inputs_sha256':hashlib.sha256(b'no release dispatch selected').hexdigest()}
atomic_json(Path('/etc/madar/migration-policy.json'),routine)
p=Path('/etc/madar/automatic-database.dsn');p.write_text('host=127.0.0.1 port=25432 dbname=postgres user=supabase_admin password='+state['database_password']+' sslmode=disable');p.chmod(0o600)
raw=json.loads(Path('/opt/madar-test/origin146/original-provider-probes.json').read_bytes());by_name={r['Name']:r for r in rows};endpoints={}
for name,port in [('auth',9999),('rest',3000),('storage',5000)]:
 ip=by_name['/supabase-'+name]['NetworkSettings']['Networks']['madar-local-supabase_default']['IPAddress'];endpoints[name]='http://'+ip+':'+str(port)
bindings={}
for component in ('auth','rest','storage'):
 row=by_name['/supabase-'+component];bindings[component]={'id':row['Id'],'image':row['Image'],'spec_sha256':measured_spec(row),'network_id':row['NetworkSettings']['Networks']['madar-local-supabase_default']['NetworkID']}
material={'version':2,'subjects':raw['subjects'],'provider_bindings':bindings,'anon_key':state['anon_key']}
from deployment.lib.historical_origin import provider_probe_endpoints
assert provider_probe_endpoints(material,{r['Name'].lstrip('/'):r for r in rows},environment)==endpoints
atomic_json(Path('/etc/madar/historical-origin-probes.json'),material)
p=Path('/etc/madar/release-approval.key');assert not p.exists();p.write_bytes(secrets.token_bytes(64));p.chmod(0o600)
print(json.dumps({'environment_id':execution['environment_id'],'guest_uuid':environment['guest_uuid'],'database_system_identifier':state['database_system_identifier'],'controller_sha':system.installed_sha(),'actors':len(rows),'strict_effect_fence':True,'routine_policy_enabled':False,'release_evidence_or_migration_authority_issued':False}))
"""
value=json.loads(call(script,name='independent-historical-test-environment-enrollment',timeout=180));(EVIDENCE/'independent-historical-test-environment-enrollment.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value),flush=True)
print(call("subprocess.run(['python3','-B','/opt/madar-test/controller/web/staging/integration/exceptional_operator_fixture.py','PREPARE'],check=True)",name='independent-native-operator-construction',timeout=180).decode()[-1200:],flush=True)
