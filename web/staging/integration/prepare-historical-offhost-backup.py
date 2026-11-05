"""Independent parent captures only its fenced synthetic guest, never production."""
import base64,hashlib,json,os,subprocess,sys,time,uuid
from pathlib import Path
from automatic_rpc import ROOT,EVIDENCE,GUEST,SSH,MANIFEST,call
from canonical_acceptance_window import fresh_recovery_expiry
from datetime import datetime
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption
sys.path.insert(0,'/opt/madar-development/repository/web')
from deployment.lib.migration_inventory import canonical,digest
operation=str(uuid.uuid4());receiver=str(uuid.uuid4())
known=json.loads(call("""import sys
sys.path.insert(0,'/opt/madar/control-plane')
from deployment.lib.control_plane_upgrade import SystemOperations
from deployment.lib import historical_origin as origin
system=SystemOperations();s=json.loads((system.state_root/'state.json').read_bytes())
binding=origin.attest(system,s)
consumed=json.loads((pathlib.Path(binding['enrollment_root'])/'bootstrap-origin-consumed.json').read_bytes())
print(json.dumps({'source':s['known_good_release']['sha'],'slot':s['active_slot'],'origin_expires_at':consumed['payload']['expires_at']}))
""",name='offhost-source-known-good',timeout=120))
# Only NEW evidence can use this planned lifetime. Existing signed packets are
# never edited; insufficient remaining owner lifetime refuses before fencing.
if (ROOT/'offhost-prepared.json').exists() or (ROOT/'offhost-backup').exists():
 raise RuntimeError('canonical_fresh_recovery_existing_material_refused')
if type(MANIFEST['max_lifetime_seconds']) is not int or not 0<MANIFEST['max_lifetime_seconds']<=10800:
 raise RuntimeError('canonical_fresh_recovery_supervisor_scope_invalid')
expires=fresh_recovery_expiry(now=int(time.time()),origin_deadline=known['origin_expires_at'],
 supervisor_deadline=int(datetime.fromisoformat(MANIFEST['created_at']).timestamp())+MANIFEST['max_lifetime_seconds'],
 fault_boundary=MANIFEST.get('fault_boundary'))
expected_stop={'operation_id':operation,'source_guest_uuid':GUEST['guest_uuid'],'source_sha':known['source'],'qemu_exited':True}
request={'operation_id':operation,'receiver_id':receiver,'source_poweroff_sha256':digest(expected_stop)}
script='''import sys,base64,hashlib,tarfile,io,time
from pathlib import Path
sys.path.insert(0,'/opt/madar/control-plane')
from deployment.lib.control_plane_upgrade import SystemOperations
from deployment.lib import historical_origin as origin
from deployment.lib.isolated_release_environment import verify_runtime_scope
from deployment.lib.migration_inventory import canonical,digest
from deployment.lib.completed_normal_database import STRUCTURE_SQL
request=json.loads(base64.b64decode(REQUEST));root=Path('/opt/madar-test/offhost')
if root.exists():
 assert not root.is_symlink() and root.stat().st_uid==0
 root.rename(root.with_name('offhost-failed-'+request['operation_id']))
root.mkdir(mode=0o700)
system=SystemOperations();state=json.loads(Path('/var/lib/madar/releases/state.json').read_bytes());binding=origin.attest(system,state);original=origin.recorded_observation(binding);policy,key,environment=origin.policy(system);evidence_root=Path(binding['enrollment_root']);context={'kind':origin.KIND,'source_binding':binding,'request_record':json.loads((evidence_root/'bootstrap-origin-request.json').read_bytes()),'enrollment_record':json.loads((evidence_root/'bootstrap-origin-consumed.json').read_bytes()),'history':original['database']}
m={'source_sha':binding['application_sha'],'history':original['database'],'environment':environment,'actors':{}}
from deployment.lib.automatic_release_recovery import ROOT as recovery_root
from deployment.lib.migration_executor import atomic_json
atomic_json(recovery_root/'independent-restore-in-progress.json',{'version':1,'kind':'independent-restoration-source-preparing','operation_id':request['operation_id'],'receiver_id':request['receiver_id'],'source_guest_uuid':environment['guest_uuid'],'source_binding':binding},exclusive=True)
rows=json.loads(subprocess.check_output(['docker','inspect',*subprocess.check_output(['docker','ps','-aq']).decode().split()]))
verify_runtime_scope(m['environment']['runtime_scope'],rows);m['actors']={r['Name'].lstrip('/'):r['Id'] for r in rows}
ids=m['actors'];redis_id=ids['madar-'+state['active_slot']+'-redis'];all_ids=[r['Id'] for r in rows if r['Id'] not in {ids['supabase-db'],redis_id}]
subprocess.run(['docker','stop','--time','15',*all_ids],check=True,stdout=subprocess.DEVNULL,timeout=180)
subprocess.run(['docker','exec',redis_id,'redis-cli','--rdb','/data/recovery.rdb'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=30)
redis_snapshot=subprocess.check_output(['docker','exec',redis_id,'cat','/data/recovery.rdb'],timeout=15)
(root/'redis.rdb').write_bytes(redis_snapshot);(root/'redis.rdb').chmod(0o600)
if len(redis_snapshot)>8*1024**2:raise RuntimeError('offhost_source_redis_budget')
subprocess.run(['docker','stop','--time','15',redis_id],check=True,stdout=subprocess.DEVNULL,timeout=30)
all_ids.append(redis_id)
assert all(not r['State']['Running'] for r in json.loads(subprocess.check_output(['docker','inspect',*all_ids])))
def sql(query):return subprocess.check_output(['docker','exec','-i',ids['supabase-db'],'psql','-XqAt','-v','ON_ERROR_STOP=1','-U','supabase_admin','-d','postgres'],input=query.encode(),timeout=45).decode().strip()
assert sql('SELECT system_identifier::text FROM pg_control_system()')==m['history']['system_identifier']
role_names={'database':'supabase-db','auth':'supabase-auth','rest':'supabase-rest','storage':'supabase-storage','gateway':'supabase-envoy','proxy':'madar-release-proxy'}
role_names.update({r:'madar-'+state['active_slot']+'-'+r for r in ('backend','frontend','redis','parser-worker','remote-ingestion-worker','notification-worker','calendar-sync-worker','data-deletion-worker')})
byname={r['Name'].lstrip('/'):r for r in rows};selected={k:byname[v] for k,v in role_names.items()};binds={};total=0
for role,row in selected.items():
 for mount in row['Mounts']:
  if mount['Type']=='tmpfs' or role=='database' or role=='storage' and mount['Destination']=='/var/lib/storage':continue
  if mount['Type']!='bind':raise RuntimeError('offhost_source_unrecognized_mount')
  source=Path(mount['Source']);key=hashlib.sha256(str(source).encode()).hexdigest();files={}
  for path in sorted(source.rglob('*')) if source.is_dir() else [source]:
   if path.is_symlink():raise RuntimeError('offhost_source_symlink')
   if path.is_dir():continue
   if not path.is_file() or path.stat().st_size>16*1024**2:raise RuntimeError('offhost_source_file_not_bounded')
   body=path.read_bytes();total+=len(body)
   if total>32*1024**2:raise RuntimeError('offhost_source_bind_budget')
   relative=path.relative_to(source).as_posix() if source.is_dir() else path.name
   mode=path.stat().st_mode&0o777;mode=mode if mode in {0o400,0o444,0o600,0o644,0o755} else 0o644
   files[relative]={'body':base64.b64encode(body).decode(),'mode':mode}
  binds[key]={'files':files,'mutable':mount['RW']};mount['recovery_bind_key']=key
  if source.is_file():mount['recovery_file']=source.name
fingerprints={}
def fingerprint(label,query):fingerprints[label]={'query':query,'sha256':hashlib.sha256(sql(query).encode()).hexdigest()}
fingerprint('roles',"SELECT jsonb_agg(to_jsonb(r)-'oid' ORDER BY rolname)::text FROM pg_authid r")
fingerprint('catalog_roles_rls_acl',STRUCTURE_SQL)
tables=json.loads(sql("SELECT json_agg(json_build_array(n.nspname,c.relname,c.relkind) ORDER BY n.nspname,c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('public','auth','storage') AND c.relkind IN ('r','p','S')"))
for schema,table,kind in tables:
 quoted='"'+schema.replace('"','""')+'"."'+table.replace('"','""')+'"'
 query=('SELECT json_build_array(last_value,is_called)::text FROM '+quoted) if kind=='S' else ('SELECT jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text FROM '+quoted+' t')
 fingerprint(schema+'.'+table,query)
objects=json.loads(sql("SELECT json_agg(json_build_object('bucket',bucket_id,'name',name,'version',version,'metadata',metadata) ORDER BY bucket_id,name) FROM storage.objects"))
backup='/tmp/madar-'+request['operation_id']
subprocess.run(['docker','exec','--user','postgres',ids['supabase-db'],'pg_basebackup','-U','supabase_admin','-D',backup,'-X','stream','--checkpoint=fast'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=180)
def archive(container,source,target):
 process=subprocess.Popen(['docker','cp',container+':'+source+'/.','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 count=0;size=0
 with tarfile.open(fileobj=process.stdout,mode='r|') as original,tarfile.open(target,mode='w:gz') as out:
  for member in original:
   name=member.name
   while name.startswith('./'):name=name[2:]
   if name in ('','.'):continue
   if name.startswith('/') or '..' in Path(name).parts or not (member.isfile() or member.isdir()) or member.sparse:raise RuntimeError('offhost_source_archive_member')
   count+=1;size+=member.size
   if count>100000 or size>1024**3:raise RuntimeError('offhost_source_archive_budget')
   member.name=name;member.uid=member.gid=0;member.uname=member.gname='';out.addfile(member,original.extractfile(member) if member.isfile() else None)
 if process.wait(timeout=30):raise RuntimeError('offhost_source_archive_command_failed')
 target.chmod(0o600)
archive(ids['supabase-db'],backup,root/'postgres.tar.gz');archive(ids['supabase-storage'],'/var/lib/storage',root/'objects.tar.gz')
app={'version':1,'source_sha':m['source_sha'],'database_system_identifier':m['history']['system_identifier'],'schema':m['history']['schema'],'slot':state['active_slot'],
 'redis_snapshot':{'body':base64.b64encode(redis_snapshot).decode(),'sha256':hashlib.sha256(redis_snapshot).hexdigest()},'release_context':context,'containers':selected,'binds':binds,'fingerprints':fingerprints,'storage_objects':objects,'original_fixture':json.loads(Path('/opt/madar-test/origin146/original-provider-probes.json').read_bytes()),'source_poweroff_sha256':request['source_poweroff_sha256']}
app['original_fixture']['business']=json.loads(Path('/opt/madar-test/origin146/business-fixture.json').read_bytes())
app['original_fixture']['members']=[json.loads(Path('/opt/madar-test/origin146/member-'+str(subject['tenant_id'])+'.json').read_bytes()) for subject in app['original_fixture']['subjects']]
(root/'application.json').write_bytes(canonical(app));(root/'application.json').chmod(0o600)
files={name:{'size':(root/name).stat().st_size,'sha256':hashlib.sha256((root/name).read_bytes()).hexdigest()} for name in ('postgres.tar.gz','objects.tar.gz','application.json')}
print(json.dumps({'source_sha':m['source_sha'],'schema':m['history']['schema'],'database_system_identifier':m['history']['system_identifier'],'files':files,'fingerprints':len(fingerprints),'images':sorted({r['Image'] for r in selected.values()}),'writers_fenced':True,'authority_issued':False,'source_origin_kind':origin.KIND,'source_origin_sha256':digest(context),'origin_expires_at':context['enrollment_record']['payload']['expires_at']}))
'''.replace('REQUEST',repr(base64.b64encode(canonical(request)).decode()))
observed=json.loads(call(script,name='actual-fenced-physical-backup',timeout=480))
folder=ROOT/'offhost-backup';folder.mkdir(mode=0o700)
for name,record in observed['files'].items():
 path=folder/name
 with path.open('xb') as out:
  os.fchmod(out.fileno(),0o600)
  subprocess.run(SSH+['sudo -n cat /opt/madar-test/offhost/'+name],stdout=out,check=True,timeout=120)
 assert path.stat().st_size==record['size'] and hashlib.sha256(path.read_bytes()).hexdigest()==record['sha256']
assert expires<=observed['origin_expires_at'] and int(time.time())<expires
key=Ed25519PrivateKey.generate();private=key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption());p=ROOT/'offhost-source.key';p.write_bytes(private);p.chmod(0o600)
value={'operation':'independent-synthetic-application-restoration','operation_id':operation,'receiver_id':receiver,'source_sha':observed['source_sha'],'source_guest_uuid':GUEST['guest_uuid'],'source_database_system_identifier':observed['database_system_identifier'],
 'backup_format':'postgres-physical-and-application-v1','expires_at':expires,'files':observed['files'],'source_origin_kind':observed['source_origin_kind'],'source_origin_sha256':observed['source_origin_sha256']}
record={'value':value,'packet':{'payload':value,'signature':base64.b64encode(key.sign(canonical(value))).decode()},'public_key':base64.b64encode(key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode(),'expected_poweroff_observation':expected_stop,'observed_backup':observed}
p=ROOT/'offhost-prepared.json';p.write_bytes(canonical(record));p.chmod(0o600)
proof={k:observed[k] for k in ('source_sha','schema','database_system_identifier','files','fingerprints','writers_fenced','authority_issued')};proof.update(operation_id=operation,receiver_id=receiver,manifest_sha256=digest(value),source_guest_uuid=GUEST['guest_uuid'],restoration_completed=False)
p=EVIDENCE/'offhost-backup-created.json';p.write_bytes(canonical(proof));p.chmod(0o600)
print(json.dumps(proof),flush=True)
