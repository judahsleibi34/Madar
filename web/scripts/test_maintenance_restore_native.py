"""Native v1/v2 maintenance restore and privilege/data refusal regression.

Only newly owned networkless tmpfs PostgreSQL clusters are used. No port,
existing database, migration engine, issuer or application authority is used.
"""
from pathlib import Path
import datetime,hashlib,json,os,re,shutil,subprocess,sys,time,uuid

import signal,tempfile
repo=Path(__file__).resolve().parents[2]
source_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
worktree_clean=not subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=repo).strip()
root=Path(tempfile.mkdtemp(prefix='madar-maintenance-restore-native-'));root.chmod(0o700)
sys.path.insert(0,str(repo/'web'))
from scripts import backup_support
from scripts.rehearse_backup import rehearse
from deployment.lib.maintenance_backup import seal_capture
from deployment.lib.schema150_actor_inventory import REQUIRED_OBJECT_ROOTS
from deployment.lib.schema150_object_inventory import measure_roots

nonce=str(uuid.uuid4());work=root/'owned-fixture';work.mkdir(mode=0o700)
print(json.dumps({'native_fixture_owner':nonce,'work_root':str(root),'source_sha':source_sha,'worktree_clean':worktree_clean}),flush=True)
signal.signal(signal.SIGTERM,lambda signum,frame:sys.exit(128+signum))
image='postgres@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73'
image_id=None;label='com.madar.native.restore.preflight='+nonce
source='madar-native-restore-source-'+nonce[:12]
tools=work/'tools';tools.mkdir(mode=0o700)
# Label every new container, including the existing rehearsal helper's target.
# This changes no restore behavior or authority; it adds exact cleanup scope.
wrapper=tools/'docker';wrapper.write_text('#!/usr/bin/python3\nimport os,sys\na=sys.argv[1:]\nif a and a[0]=="run":a[1:1]=["--label",'+repr(label)+']\nos.execv("/usr/bin/docker",["/usr/bin/docker",*a])\n');wrapper.chmod(0o700)
# A CI host may have an older PostgreSQL client. Inspect each owned dump with
# the exact source-image client, not an arbitrary host pg_restore installation.
toc=tools/'pg_restore'
toc.write_text('''#!/usr/bin/python3
import os,sys,uuid
from pathlib import Path
assert len(sys.argv)==3 and sys.argv[1]=='--list'
p=Path(sys.argv[2]);assert not p.is_symlink() and p.resolve().is_relative_to(Path(WORK)) and p.is_file() and p.stat().st_nlink==1
assert ',' not in str(p)
args=['/usr/bin/docker','run','--rm','--pull=never','--name','madar-native-toc-'+uuid.uuid4().hex[:12],
 '--label',LABEL,'--network','none','--user',str(os.getuid())+':'+str(os.getgid()),'--read-only',
 '--cap-drop','ALL','--security-opt','no-new-privileges','--memory','256m','--cpus','1','--pids-limit','32',
 '--mount','type=bind,src='+str(p.resolve())+',dst=/backup.dump,readonly','--entrypoint','pg_restore',IMAGE,'--list','/backup.dump']
os.execv(args[0],args)
'''.replace('WORK',repr(str(work))).replace('LABEL',repr(label)).replace('IMAGE',repr(image)))
toc.chmod(0o700)
os.environ['PATH']=str(tools)+':'+os.environ['PATH']

def command(args,*,input=None,timeout=90):
    return subprocess.check_output(args,input=input,text=True,stderr=subprocess.PIPE,timeout=timeout)
def query(sql):
    return command(['docker','exec','-i',source,'psql','-XqAt','-h','/tmp','-U','supabase_admin','-d','postgres','-v','ON_ERROR_STOP=1'],input=sql)
def readonly(sql):
    return query("BEGIN READ ONLY; SET LOCAL search_path=pg_catalog; SET LOCAL TIME ZONE 'UTC'; SET LOCAL statement_timeout='30s';\n"+sql+'\nCOMMIT;')

report={'kind':'native-synthetic-maintenance-restore-regression','source_sha':source_sha,
        'image':image,'run_id':nonce,'status':'FAIL','production_authority':False,
        'canonical_migration_sql_executed':False,'source_application_acceptance_claimed':False}
removed=[]
try:
    # A registry manifest digest and its platform-specific config image ID are
    # different identities. Resolve the pinned reference, then bind every owned
    # container to both its exact requested reference and that actual ID.
    pinned=json.loads(command(['/usr/bin/docker','image','inspect',image]))
    assert len(pinned)==1 and image in pinned[0]['RepoDigests']
    image_id=pinned[0]['Id'];assert re.fullmatch('sha256:[a-f0-9]{64}',image_id)
    report['database_image_id']=image_id
    command(['docker','run','--detach','--pull=never','--name',source,'--network','none',
        '--user','65534:65534','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--memory','2g','--cpus','2','--pids-limit','128',
        '--tmpfs','/tmp:rw,nosuid,nodev,size=64m,mode=1777',
        '--tmpfs','/restore-data:rw,nosuid,nodev,size=1g,mode=1777','--entrypoint','sh',image,'-ec',
        "initdb -D /restore-data/pgdata -U supabase_admin --auth=trust >/dev/null; exec postgres -D /restore-data/pgdata -k /tmp -c listen_addresses='' -c shared_preload_libraries=pg_stat_statements"])
    deadline=time.monotonic()+45
    while True:
        p=subprocess.run(['docker','exec',source,'pg_isready','-h','/tmp','-U','supabase_admin'],capture_output=True)
        if p.returncode==0:break
        if time.monotonic()>deadline:raise RuntimeError('synthetic_source_start_timeout')
        time.sleep(.5)
    query("""CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN;
CREATE ROLE supabase_auth_admin NOLOGIN;
CREATE ROLE synthetic_writer LOGIN;
GRANT authenticated TO synthetic_writer;
CREATE EXTENSION pg_stat_statements;
CREATE EXTENSION pgcrypto;
CREATE EXTENSION btree_gist;
CREATE EXTENSION "uuid-ossp";
CREATE SCHEMA auth;
CREATE SCHEMA storage;
CREATE TABLE public.application_schema_state(contract_key text PRIMARY KEY,schema_version integer NOT NULL);
INSERT INTO public.application_schema_state VALUES('core',146);
CREATE TABLE auth.users(id uuid PRIMARY KEY,fixture text NOT NULL);
INSERT INTO auth.users VALUES('00000000-0000-0000-0000-000000000001','synthetic-original');
ALTER TABLE auth.users OWNER TO supabase_auth_admin;
CREATE TABLE storage.objects(id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,fixture text NOT NULL);
INSERT INTO storage.objects(fixture) VALUES('synthetic-private-object');
CREATE TABLE public.native_restore_records(id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,tenant text NOT NULL,body text NOT NULL);
INSERT INTO public.native_restore_records(tenant,body) VALUES('tenant-a','preserve-a'),('tenant-b','preserve-b');
ALTER TABLE public.native_restore_records ENABLE ROW LEVEL SECURITY;
CREATE POLICY fixture_tenant ON public.native_restore_records TO authenticated USING(tenant='tenant-a');
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT SELECT ON public.native_restore_records TO authenticated;
CREATE TABLE public.owner_only(id integer PRIMARY KEY);
ALTER TABLE public.owner_only OWNER TO synthetic_writer;
GRANT ALL ON public.owner_only TO synthetic_writer;
CREATE FUNCTION public.native_restore_identity() RETURNS integer LANGUAGE sql IMMUTABLE AS 'SELECT 1';
SELECT setval(pg_get_serial_sequence('public.native_restore_records','id'),42,true);
""")
    raw_fingerprint=backup_support.database_fingerprint(readonly)
    fingerprint=backup_support.database_fingerprint(readonly,acl_semantics=True)
    roles=query('SELECT rolname FROM pg_authid WHERE oid=10;').strip();assert roles=='supabase_admin'
    role_sql=command(['docker','exec',source,'pg_dumpall','-h','/tmp','-U',roles,'--roles-only']).encode()
    snapshot=json.loads(readonly(backup_support.ROLE_SNAPSHOT_SQL))
    backup=work/'backup';backup.mkdir(mode=0o700)
    for name in backup_support.FILE_SETS:(backup/'files'/name).mkdir(parents=True)
    (backup/'files/private-uploads/original.txt').write_bytes(b'original synthetic bytes')
    for name,body in {'backup.env':'MADAR_BACKUP_FORMAT=3\n','BACKUP_COMPLETE':'complete\n',
                      'MANIFEST.txt':'synthetic native preapproval fixture\n','CONFIGURATION-INVENTORY.txt':'no credentials\n'}.items():
        (backup/name).write_text(body)
    with (backup/'database.dump').open('xb') as output:
        subprocess.run(['docker','exec',source,'pg_dump','-h','/tmp','-U',roles,'-d','postgres','--format=custom','--create'],stdout=output,stderr=subprocess.PIPE,check=True,timeout=90)
    timestamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    outer={'format_version':3,'status':'complete','backup_id':'madar-'+timestamp,'created_at':timestamp,
           'release':{'git_sha':source_sha},'database':{'dump':'database.dump','schema_version':'146'},
           'checksums':'SHA256SUMS','configuration':{'values_included':False},'file_sets':list(backup_support.FILE_SETS),
           'recovery':{'provider_objects_required':False}}
    (backup/'manifest.json').write_text(json.dumps(outer))
    sums=backup_support.inventory(backup);(backup/'SHA256SUMS').write_text(''.join(v+'  '+k+'\n' for k,v in sorted(sums.items())))
    forest={}
    for name in sorted(REQUIRED_OBJECT_ROOTS):
        directory=work/name;directory.mkdir(mode=0o700)
        forest[name]={'type':'bind','source':str(directory),'content_sha256':'e'*64}
        if name!='database':(directory/'original').write_bytes(('synthetic-'+name).encode())
    binding={'operation':'completed-normal-schema146-160-coordinated-release','context_sha256':'a'*64,
             'source_sha':source_sha,'controller_sha':source_sha,
             'inventory_sha256':'d'*64,'system_identifier':readonly('SELECT system_identifier FROM pg_control_system();').strip(),
             'source_schema':146,'target_schema':160}
    recovery={'origin_source_sha':source_sha,
              'origin_images':{'backend':'sha256:'+'1'*64,'frontend':'sha256:'+'2'*64},
              'candidate_images':{'backend':'sha256:'+'3'*64,'frontend':'sha256:'+'4'*64},
              'database_image':image_id,'migration_manifest_sha256':'6'*64,'controller_tree_sha256':'7'*64,
              'configuration_sha256':{'synthetic':'8'*64},'configuration_escrow_required':True}
    # Independently seal two new synthetic archives. Existing version1 input
    # keeps its original interpretation and is never retroactively rewritten.
    modern=work/'backup-v2';shutil.copytree(backup,modern)
    legacy_digest=seal_capture(backup,binding=binding,stage='pre-migration',original_roles=role_sql,
        roles_snapshot=snapshot,bootstrap_role=roles,roots=forest,previous=measure_roots(forest,phase='fenced'),
        database_fingerprint=raw_fingerprint,recovery=recovery)
    try:rehearse(backup,image,postgres_preload=('pg_stat_statements',),maintenance_manifest_sha256=legacy_digest)
    except RuntimeError as error:
        assert str(error)=='maintenance_database_fingerprint_mismatch'
    else:raise AssertionError('legacy representation mismatch was not reproduced')
    digest=seal_capture(modern,binding=binding,stage='pre-migration',original_roles=role_sql,
        roles_snapshot=snapshot,bootstrap_role=roles,roots=forest,previous=measure_roots(forest,phase='fenced'),
        database_fingerprint=fingerprint,recovery=recovery,database_fingerprint_version=2)
    result=rehearse(modern,image,postgres_preload=('pg_stat_statements',),maintenance_manifest_sha256=digest)
    assert result['status']=='logical_database_and_file_restore_passed'
    assert all(result[k] is True for k in ('role_attributes_restored','ownership_and_acls_restored',
        'database_fingerprint_verified','native_object_bytes_restored','disposable_target_removed'))
    negative={}
    real_fingerprint=backup_support.database_fingerprint
    mutations={
        'lost_grant':'REVOKE SELECT ON public.native_restore_records FROM authenticated;',
        'extra_public_grant':'GRANT SELECT ON public.native_restore_records TO PUBLIC;',
        'grant_option':'GRANT SELECT ON public.native_restore_records TO authenticated WITH GRANT OPTION;',
        'wrong_owner':'ALTER TABLE public.owner_only OWNER TO supabase_admin;',
        'rls_disabled':'ALTER TABLE public.native_restore_records DISABLE ROW LEVEL SECURITY;',
        'sequence_drift':"SELECT setval(pg_get_serial_sequence('public.native_restore_records','id'),99,true);",
        'changed_data':"UPDATE public.native_restore_records SET body='changed' WHERE tenant='tenant-a';",
        'changed_function':"CREATE OR REPLACE FUNCTION public.native_restore_identity() RETURNS integer LANGUAGE sql IMMUTABLE AS 'SELECT 2';",
    }
    for case,sql in mutations.items():
        injected=[]
        def altered_target(query,**options):
            ids=command(['/usr/bin/docker','ps','-aq','--filter','label='+label]).split()
            rows=json.loads(command(['/usr/bin/docker','inspect',*ids]))
            selected=[r for r in rows if re.fullmatch('/madar-restore-rehearsal-[a-f0-9]{12}',r['Name'])]
            assert len(selected)==1 and selected[0]['Image']==image_id and selected[0]['Config']['Image']==image
            target=selected[0];assert target['Config']['Labels']['com.madar.native.restore.preflight']==nonce
            command(['/usr/bin/docker','exec','-i',target['Id'],'psql','-XqAt','-h','/tmp','-U',roles,'-d','postgres','-v','ON_ERROR_STOP=1'],input=sql)
            injected.append(target['Id'])
            return real_fingerprint(query,**options)
        backup_support.database_fingerprint=altered_target
        try:
            try:rehearse(modern,image,postgres_preload=('pg_stat_statements',),maintenance_manifest_sha256=digest)
            except RuntimeError as error:
                assert str(error)=='maintenance_database_fingerprint_mismatch',case
            else:raise AssertionError('unsafe restored state accepted:'+case)
        finally:backup_support.database_fingerprint=real_fingerprint
        assert len(injected)==1 and subprocess.run(['/usr/bin/docker','inspect',injected[0]],capture_output=True).returncode!=0
        negative[case]='REFUSED_REAL_RESTORED_TARGET'
    assert backup_support.database_fingerprint(readonly,acl_semantics=True)==fingerprint
    assert backup_support.database_fingerprint(readonly)==raw_fingerprint
    report.update(status='PASS',actual_restore=result,source_database_unchanged=True,
        version1_representation_refusal_preserved=True,version2_restore_passed=True,
        native_negative_refusals=negative,worktree_clean=worktree_clean,
        source_file_hashes={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (Path(__file__).resolve(),repo/'web/scripts/backup_support.py',repo/'web/scripts/rehearse_backup.py',repo/'web/deployment/lib/maintenance_backup.py')})
except BaseException as error:
    report.update(exception_type=type(error).__name__,error_code=str(error) if isinstance(error,RuntimeError) else 'native_preapproval_fixture_failed')
    raise
finally:
    ids=command(['/usr/bin/docker','ps','-aq','--filter','label='+label]).split()
    for cid in ids:
        row=json.loads(command(['/usr/bin/docker','inspect',cid]))[0]
        assert (row['Config']['Labels']['com.madar.native.restore.preflight']==nonce
                and row['Image']==image_id and row['Config']['Image']==image)
        assert row['Name']=='/'+source or re.fullmatch('/madar-(restore-rehearsal|native-toc)-[a-f0-9]{12}',row['Name'])
        command(['/usr/bin/docker','rm','--force',cid]);removed.append(cid)
    assert not command(['/usr/bin/docker','ps','-aq','--filter','label='+label]).strip()
    report['owned_containers_removed']=True;report['remaining_owned_containers']=0
    report['logical_bytes_removed']=sum(p.stat().st_size for p in work.rglob('*') if p.is_file())
    assert all(not p.is_symlink() and p.stat().st_uid==os.getuid() for p in work.rglob('*'))
    shutil.rmtree(work);report['scratch_removed']=not work.exists()
    root.rmdir()
    print(json.dumps(report),flush=True)
