#!/usr/bin/env python3
"""Bounded physical receiver adapter for the existing append-only test receiver.

This is a disposable restoration test, never production installation, SQL
migration, release promotion or a new write-authority issuer. Root enrollment
and actual receive receipts are prerequisites. Original grants are preserved
only with their physical database identity while the source guest is OFF.
"""
import hashlib,json,os,re,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from deployment.lib.provider_recovery_runtime import protected
from deployment.lib.migration_inventory import digest,strict_json
from deployment.lib.migration_executor import atomic_json
from deployment.lib.coordinated_archive_restore import restore_archive,verify_restored_archive
from deployment.lib.coordinated_storage_restore import recover_metadata
from deployment.lib.coordinated_checkpoint import digest_file

DIAGNOSTIC_ROOT=None
ROLE_BUDGET={'database':384,'auth':128,'rest':128,'storage':192,'gateway':32,'redis':64,
    'frontend':64,'backend':768,'parser-worker':384,'remote-ingestion-worker':96,
    'notification-worker':128,'calendar-sync-worker':128,'data-deletion-worker':128,'proxy':32}
ROLE_CPU={'database':.35,'auth':.15,'rest':.1,'storage':.1,'gateway':.05,'redis':.1,
    'frontend':.05,'backend':.35,'parser-worker':.2,'remote-ingestion-worker':.1,
    'notification-worker':.1,'calendar-sync-worker':.1,'data-deletion-worker':.1,'proxy':.05}


def command(args,*,data=None,timeout=30):
    result=subprocess.run(args,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':'/root','LANG':'C.UTF-8','DOCKER_HOST':'unix:///var/run/docker.sock','DOCKER_CONFIG':'/nonexistent'})
    if result.returncode:
        if DIAGNOSTIC_ROOT is not None:
            p=DIAGNOSTIC_ROOT/'private-effect-error.log';p.write_bytes((result.stdout+result.stderr)[-65536:]);p.chmod(0o600)
        raise RuntimeError('offhost_test_effect_failed:'+Path(args[0]).name)
    return result.stdout


def root_for(run_id,*,allow_expired=False):
    if os.geteuid()!=0 or not re.fullmatch(r'codex-[0-9]{8}T[0-9]{6}Z-automatic-execution-[a-f0-9]{8}',run_id):raise RuntimeError('offhost_test_root_scope_required')
    root=Path('/opt/madar-recovery-tests')/run_id
    enrollment=strict_json(protected(root/'enrollment.json',private=True).read_bytes())
    if (enrollment['run_id']!=run_id or not allow_expired and enrollment['expires_at']<=time.time()
            or Path('/etc/machine-id').read_text().strip()!=enrollment['machine_id']
            or Path('/sys/class/dmi/id/product_uuid').read_text().strip().lower()!=enrollment['product_uuid']):
        raise RuntimeError('offhost_test_receiver_identity_changed')
    fs=command(['findmnt','-n','-o','FSTYPE,UUID','-T',str(root)]).decode().split()
    if fs!=['ext4',enrollment['filesystem_uuid']]:raise RuntimeError('offhost_test_filesystem_changed')
    return root,enrollment


def restore(run_id):
    global DIAGNOSTIC_ROOT
    root,enrollment=root_for(run_id);DIAGNOSTIC_ROOT=root
    received=strict_json(protected(root/'received.json',private=True).read_bytes())
    if received['manifest_sha256']!=enrollment['manifest_sha256'] or received['receiver_id']!=enrollment['receiver_id']:
        raise RuntimeError('offhost_test_received_scope_changed')
    incoming=root/'incoming'
    for name,sha in received['files'].items():
        if digest_file(protected(incoming/name,private=True))!=sha:raise RuntimeError('offhost_test_received_bytes_changed')
    app=strict_json(protected(incoming/'application.json',private=True).read_bytes())
    required={'version','source_sha','database_system_identifier','schema','slot','containers','binds','fingerprints','storage_objects','original_fixture','source_poweroff_sha256','redis_snapshot'}
    if (set(app)!=required or app['version']!=1 or app['source_sha']!=enrollment['source_sha']
            or app['database_system_identifier']!=enrollment['source_database_system_identifier']
            or set(app['containers'])!=set(ROLE_BUDGET) or app['slot'] not in {'blue','green'}
            or not re.fullmatch('[a-f0-9]{64}',str(app['source_poweroff_sha256']))):
        raise RuntimeError('offhost_test_application_contract_invalid')
    # The independent parent publishes this only after the exact source QEMU
    # process has exited. Candidate code cannot publish a receiver root receipt.
    stopped=strict_json(protected(root/'source-powered-off.json',private=True).read_bytes())
    if (digest(stopped)!=app['source_poweroff_sha256'] or stopped.get('source_guest_uuid')!=enrollment['source_guest_uuid']
            or stopped.get('source_sha')!=app['source_sha'] or stopped.get('qemu_exited') is not True):
        raise RuntimeError('offhost_test_source_not_independently_fenced')
    for row in app['containers'].values():
        if not re.fullmatch('sha256:[a-f0-9]{64}',str(row['Image'])):raise RuntimeError('offhost_test_image_not_immutable')
        inspected=json.loads(command(['docker','image','inspect',row['Image']]))
        if len(inspected)!=1 or inspected[0]['Id']!=row['Image']:raise RuntimeError('offhost_test_image_unavailable')
    if sum(ROLE_BUDGET.values())>2800 or sum(ROLE_CPU.values())>2.01:raise RuntimeError('offhost_test_resource_budget_exceeded')
    memory=int(next(v.split()[1] for v in Path('/proc/meminfo').read_text().splitlines() if v.startswith('MemAvailable:')))*1024
    if memory<(sum(ROLE_BUDGET.values())+768)*1024**2:raise RuntimeError('offhost_test_memory_headroom_insufficient')
    # No published ports, host-network actors or host-addressed gateway.
    # Application acceptance executes inside this exact isolated bridge.
    owner={'run_id':run_id,'receiver_id':enrollment['receiver_id'],'containers':{},'network':None,'volumes':[], 'images_imported':[]}
    atomic_json(root/'restore-owned.json',owner,exclusive=True)
    def checkpoint():atomic_json(root/'restore-owned.json',owner)
    def phase(name,**details):atomic_json(root/('restoration-'+name+'.json'),{'operation':'independent-application-restoration','operation_id':enrollment['backup_operation_id'],'receiver_id':enrollment['receiver_id'],'source_sha':app['source_sha'],'source_database_system_identifier':app['database_system_identifier'],'phase':name,**details})
    try:
        phase('authenticated_backup_received')
        for name in ('postgres','objects'):
            source=incoming/(name+'.tar.gz');target=root/name
            restore_archive(source,target,max_bytes=1024**3,max_members=100000)
            verify_restored_archive(source,target,max_bytes=1024**3,max_members=100000)
        for path in (root/'postgres',*(root/'postgres').rglob('*')):
            os.chown(path,70,70);path.chmod(0o700 if path.is_dir() else 0o600)
        command(['docker','run','--name','madar-recovery-'+enrollment['receiver_id'][:12]+'-verify','--label','com.madar.test.receiver='+enrollment['receiver_id'],'--rm','--network','none','--read-only','--user','70:70','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','384m','--memory-swap','384m','--cpus','.5','--pids-limit','64','--mount','type=bind,src='+str(root/'postgres')+',dst=/restore,readonly','--entrypoint','pg_verifybackup',app['containers']['database']['Image'],'/restore'],timeout=120)
        phase('postgres_physical_backup_independently_verified')
        redis_bytes=__import__('base64').b64decode(app['redis_snapshot']['body'],validate=True)
        if len(redis_bytes)>8*1024**2 or hashlib.sha256(redis_bytes).hexdigest()!=app['redis_snapshot']['sha256']:
            raise RuntimeError('offhost_test_redis_snapshot_changed')
        (root/'redis.rdb').write_bytes(redis_bytes);(root/'redis.rdb').chmod(0o444)
        mounts={}
        for key,record in app['binds'].items():
            if not re.fullmatch('[a-f0-9]{64}',key) or set(record)!={'files','mutable'}:raise RuntimeError('offhost_test_bind_inventory_invalid')
            dest=root/'binds'/key;dest.mkdir(parents=True,mode=0o755)
            for relative,row in record['files'].items():
                parts=Path(relative)
                if parts.is_absolute() or '..' in parts.parts or str(parts)=='.' or set(row)!={'body','mode'}:raise RuntimeError('offhost_test_bind_path_invalid')
                body=base64.b64decode(row['body'],validate=True)
                if len(body)>16*1024**2 or row['mode'] not in {0o400,0o444,0o600,0o644,0o755}:raise RuntimeError('offhost_test_bind_bytes_or_permissions_invalid')
                target=dest/parts;target.parent.mkdir(parents=True,exist_ok=True,mode=0o755);target.write_bytes(body);target.chmod(row['mode'])
            if record['mutable']:
                for path in (dest,*dest.rglob('*')):os.chown(path,65534,65534)
            mounts[key]=dest
        network='madar-recovery-'+enrollment['receiver_id']
        owner['network']=command(['docker','network','create','--internal','--opt','com.docker.network.bridge.gateway_mode_ipv4=isolated','--label','com.madar.test.receiver='+enrollment['receiver_id'],network]).decode().strip();checkpoint()
        measured_network=json.loads(command(['docker','network','inspect',owner['network']]))[0]
        if (measured_network['Driver']!='bridge' or measured_network['Internal'] is not True
                or measured_network.get('EnableIPv6') or measured_network['Options'].get('com.docker.network.bridge.gateway_mode_ipv4')!='isolated'):
            raise RuntimeError('offhost_test_network_isolation_invalid')
        bridge='br-'+owner['network'][:12]
        interfaces=json.loads(command(['ip','-json','address','show','dev',bridge]))
        if len(interfaces)!=1 or any(a.get('family')=='inet' for a in interfaces[0].get('addr_info',[])):
            raise RuntimeError('offhost_test_host_gateway_exposed')
        def sql(query):
            return command(['docker','exec','-i',owner['containers']['database'],'psql','-XqAt','-v','ON_ERROR_STOP=1','-U','supabase_admin','-d','postgres'],data=query.encode(),timeout=45).decode().strip()
        def create(role):
            row=app['containers'][role];name='madar-recovery-'+enrollment['receiver_id'][:12]+'-'+role
            config=row['Config'];host=row['HostConfig']
            args=['docker','create','--name',name,'--label','com.madar.test.receiver='+enrollment['receiver_id'],'--network',network,
                '--restart=no','--dns','127.0.0.1','--memory',str(ROLE_BUDGET[role])+'m','--memory-swap',str(ROLE_BUDGET[role])+'m','--cpus',str(ROLE_CPU[role]),'--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges',
                '--log-opt','max-size=1m','--log-opt','max-file=2']
            aliases={row['Name'].lstrip('/'),role}
            for endpoint in row['NetworkSettings']['Networks'].values():aliases.update(v for v in endpoint.get('Aliases',[]) if v)
            for alias in sorted(aliases):
                if re.fullmatch('[a-zA-Z0-9_.-]{1,128}',alias):args+=['--network-alias',alias]
            for env in config.get('Env',[]):args+=['--env',env]
            if host.get('ReadonlyRootfs'):args+=['--read-only']
            user='70:70' if role=='database' else config.get('User')
            if user:args+=['--user',user]
            for target,options in (host.get('Tmpfs') or {}).items():args+=['--tmpfs',target+':'+options]
            if role=='redis':args+=['--mount','type=bind,src='+str(root/'redis.rdb')+',dst=/data/dump.rdb,readonly']
            for mount in row['Mounts']:
                if mount['Type']=='tmpfs':continue
                destination=mount['Destination']
                if role=='database':
                    if destination!='/var/lib/postgresql/data':continue # no bootstrap SQL on restore
                    source=root/'postgres'
                elif role=='storage' and destination=='/var/lib/storage':source=root/'objects'
                else:
                    source=mounts[mount['recovery_bind_key']]
                    if mount.get('recovery_file'):source=source/mount['recovery_file']
                    if role=='proxy':
                        for f in source.rglob('*') if source.is_dir() else [source]:
                            if f.is_file():
                                text=f.read_text();text=text.replace('listen 127.0.0.1:','listen ')
                                text=text.replace('127.0.0.1:'+str(8101 if app['slot']=='blue' else 8201),'backend:8000')
                                text=text.replace('127.0.0.1:'+str(3100 if app['slot']=='blue' else 3200),'frontend:80');f.write_text(text)
                args+=['--mount','type=bind,src='+str(source)+',dst='+destination+(',readonly' if not mount['RW'] else '')]
            entry=config.get('Entrypoint') or []
            if entry:args+=['--entrypoint',entry[0]]
            args+=[row['Image'],*entry[1:],*(config.get('Cmd') or [])]
            identity=command(args).decode().strip();owner['containers'][role]=identity;checkpoint()
            command(['docker','start',identity]);return identity
        create('database');deadline=time.monotonic()+90
        while True:
            try:
                if sql('SELECT system_identifier::text FROM pg_control_system()')!=app['database_system_identifier']:raise RuntimeError('offhost_test_restored_database_identity_changed')
                break
            except RuntimeError:
                if time.monotonic()>deadline:raise
                time.sleep(1)
        for label,record in app['fingerprints'].items():
            actual=sql(record['query'])
            if hashlib.sha256(actual.encode()).hexdigest()!=record['sha256']:raise RuntimeError('offhost_test_restored_fingerprint_changed:'+label)
        if sql("select schema_version::text||':'||notification_delivery_protocol()||':'||notification_outbox_protocol()||':'||data_deletion_ownership_protocol() from public.application_schema_state where contract_key='core'")!=str(app['schema'])+':2:2:2':raise RuntimeError('offhost_test_schema_protocols_changed')
        phase('database_roles_acls_data_and_history_restored',fingerprints=len(app['fingerprints']),schema=app['schema'])
        recover_metadata(app['storage_objects'],root/'objects')
        for path in (root/'objects',*(root/'objects').rglob('*')):os.chown(path,1000,1000)
        for role in ('auth','rest','storage','gateway','redis','parser-worker','remote-ingestion-worker','backend','frontend','notification-worker','calendar-sync-worker','data-deletion-worker','proxy'):create(role)
        deadline=time.monotonic()+240
        while True:
            try:
                probe=command(['docker','exec','-i',owner['containers']['backend'],'python','-'],data=b"import json;from urllib.request import urlopen;print(json.dumps([json.load(urlopen('http://proxy:8001/health/ready',timeout=5)),json.load(urlopen('http://proxy:8001/health/version',timeout=5))]))",timeout=15)
                ready,identity=json.loads(probe)
                if ready['ready'] is True and identity['release_sha']==app['source_sha']:break
            except (OSError,ValueError,RuntimeError):pass
            if time.monotonic()>deadline:raise RuntimeError('offhost_test_restored_application_unready')
            time.sleep(2)
        phase('application_running',schema=app['schema'],source_database_system_identifier=app['database_system_identifier'])
        return {'operation':'independent-application-restoration','phase':'application_running','source_sha':app['source_sha'],'receiver_id':enrollment['receiver_id'],'operation_id':enrollment['backup_operation_id'],'fingerprints':len(app['fingerprints']),'functional_acceptance_pending':True,'deployment_authority_issued':False,'migration_sql_executed':False}
    except BaseException:
        # Exact owned actors only; preserve bounded inputs for diagnosis. Never
        # silently resume the source while a restored writer could still run.
        for identity in owner['containers'].values():
            try:command(['docker','stop','--time','10',identity],timeout=20)
            except Exception:pass
        phase('fenced_failed_restoration');raise




def cleanup(run_id):
    """Explicit exact-owner teardown, including a partially failed restoration."""
    root,enrollment=root_for(run_id,allow_expired=True)
    owned=root/'restore-owned.json'
    if not owned.exists():return {'containers_removed':[],'networks_removed':[],'volumes_removed':[]}
    owner=strict_json(protected(owned,private=True).read_bytes())
    if owner.get('receiver_id')!=enrollment['receiver_id'] or owner.get('run_id')!=run_id:raise RuntimeError('offhost_cleanup_owner_changed')
    current=command(['docker','ps','-aq','--no-trunc']).decode().split()
    rows=json.loads(command(['docker','inspect',*current])) if current else []
    expected=set(owner['containers'].values());present={r['Id']:r for r in rows}
    verifier='madar-recovery-'+enrollment['receiver_id'][:12]+'-verify'
    for row in rows:
        if row['Name']=='/'+verifier and row['Config'].get('Labels',{}).get('com.madar.test.receiver')==enrollment['receiver_id']:expected.add(row['Id'])
    if (root/'cleanup.json').exists():
        if expected & set(present):raise RuntimeError('offhost_cleanup_actor_reappeared')
        return strict_json(protected(root/'cleanup.json',private=True).read_bytes())
    if any(present[i]['Config'].get('Labels',{}).get('com.madar.test.receiver')!=enrollment['receiver_id'] for i in expected & set(present)):
        raise RuntimeError('offhost_cleanup_foreign_actor')
    if any(r['Id'] not in expected and any(m.get('Source','').startswith(str(root)+'/') for m in r.get('Mounts',[])) for r in rows):
        raise RuntimeError('offhost_cleanup_foreign_reference')
    removed=[]
    for identity in sorted(expected & set(present)):
        command(['docker','stop','--time','10',identity],timeout=20);command(['docker','rm',identity]);removed.append(identity)
    networks=[]
    if owner['network']:
        rows=json.loads(command(['docker','network','inspect',owner['network']]))
        if len(rows)!=1 or rows[0]['Labels'].get('com.madar.test.receiver')!=enrollment['receiver_id'] or rows[0]['Containers']:
            raise RuntimeError('offhost_cleanup_network_in_use_or_foreign')
        command(['docker','network','rm',owner['network']]);networks=[owner['network']]
    result={'containers_removed':removed,'networks_removed':networks,'volumes_removed':[],'protected_resources_modified':False}
    atomic_json(root/'cleanup.json',result,exclusive=True);return result


if __name__=='__main__':
    try:print(json.dumps(cleanup(sys.argv[2]) if len(sys.argv)==3 and sys.argv[1]=='--cleanup' else restore(sys.argv[1]),sort_keys=True))
    except Exception as error:
        print(json.dumps({'operation':'independent-application-restoration','status':'failed','error_type':type(error).__name__,'error_code':str(error) if isinstance(error,RuntimeError) else 'bounded_restore_effect_failed'}));raise SystemExit(1)
