"""Fresh exact-plan recovery backup before normal authorization; no write grant.

Uses the ordinary current-data pipeline. A private network-only version proxy
identifies the retained installed release, not a fabricated normal release.
Historical checkpoints, timestamps, transactions and authorization stay intact.
"""
import hashlib,ipaddress,json,os,pwd,re,shutil,subprocess,tempfile,time
from pathlib import Path
from types import SimpleNamespace
from deployment.lib.active_recovery_resumption import ROOT
from deployment.lib.active_recovery_inputs import INPUTS
from deployment.lib.provider_recovery_runtime import protected,readonly_configuration,file_digest,digest
from deployment.lib.emergency_routing_repair import Runtime,exclusive,encoded,spec,verification_window,AvailabilityFailure
from deployment.lib.active_recovery_backup import capture_and_replicate,checked,ENVIRONMENT

BASE=Path('/var/lib/madar-control-plane/normal-local-recovery-backup')
MARKER=Path('/var/lib/madar/backup-state/latest.json')
LATEST=Path('/var/lib/madar/backups/LATEST')
EXECUTABLES_BASE=Path('/run')

def declaration(plan):
    return ((getattr(plan,'candidate_destination',None) or {}).get('post_compensation') or {}).get('pre_grant_backup')

def require_publication(plan,package,runtime=None):
    if declaration(plan) is None:return
    runtime=runtime or Runtime();root=BASE/plan.digest
    auth=json.loads(protected(root/'authorization.json',private=True).read_text())
    record=json.loads(protected(root/'publication.json',private=True).read_text())
    if (auth.get('operation')!='current-data-recovery-backup-before-normal' or auth.get('plan_sha256')!=plan.digest
            or auth.get('source_bundle_sha256')!=plan.source_bundle_sha256
            or record.get('plan_sha256')!=plan.digest or record.get('source_bundle_sha256')!=plan.source_bundle_sha256
            or record.get('marker_sha256')!=file_digest(readonly_configuration(MARKER,private=False))
            or record.get('latest_sha256')!=file_digest(readonly_configuration(LATEST,private=False))
            or record.get('backup_receipt_sha256')!=file_digest(protected(root/'verified-recovery-backup.json',private=True))):
        raise RuntimeError('recovery_backup_publication_not_bound')
    from scripts import backup_support
    receipt=json.loads(protected(root/'verified-recovery-backup.json',private=True).read_text())
    backup_id=record.get('backup_id')
    if (not isinstance(backup_id,str) or not re.fullmatch(r'madar-[0-9]{8}T[0-9]{6}Z',backup_id)
            or Path(receipt['local_path'])!=Path('/var/lib/madar/backups')/backup_id):
        raise RuntimeError('recovery_backup_publication_path_invalid')
    manifest=backup_support.verify(Path(receipt['local_path']))
    if file_digest(Path(receipt['local_path'])/'SHA256SUMS')!=receipt.get('sha256sums_sha256'):
        raise RuntimeError('recovery_backup_published_checksums_changed')
    scope=digest({'plan_sha256':plan.digest,'operation':'current-data-recovery-backup-before-normal'})
    if (receipt.get('operation')!='actual-pre-normal-current-data-backup-restore-replica'
            or receipt.get('plan_sha256')!=plan.digest or receipt.get('source_sha')!=plan.source_sha
            or receipt.get('images')!=plan.candidate_images or receipt.get('schema')!=115
            or receipt.get('restore',{}).get('status')!='logical_database_and_file_restore_passed'
            or receipt.get('node1',{}).get('plan_sha256')!=scope
            or type(receipt['node1'].get('checksum_exit_code')) is not int or receipt['node1']['checksum_exit_code']!=0
            or receipt['node1'].get('sha256sums_sha256')!=receipt.get('sha256sums_sha256')
            or receipt.get('captured_release_sha')!=manifest['release']['git_sha']
            or manifest['backup_id']!=record.get('backup_id')):
        raise RuntimeError('recovery_backup_restore_replica_not_proven')
    from deployment.lib.active_recovery_compensated import inspect_history
    from deployment.lib.active_recovery_fallback import CurrentDataFallback
    previous,previous_root,_,_=inspect_history(plan.candidate_destination['post_compensation']['baseline']['previous_plan_sha256'])
    with verification_window(runtime,180):
        first=None;count=0
        while True:
            runtime.budget(1)
            try:
                CurrentDataFallback(previous,previous_root,runtime=runtime).verify()
                for url in ('https://madarportal.com/','https://api.madarportal.com/'):runtime.http_status(url)
                proxy=runtime.inspect(['madar-release-proxy'])['madar-release-proxy']
                if proxy['State'].get('Health',{}).get('Status')!='healthy':raise AvailabilityFailure('proxy_health_pending')
            except AvailabilityFailure:first=None;count=0
            else:
                first=time.monotonic() if first is None else first;count+=1
                if count>=3 and time.monotonic()-first>=5:return record
            time.sleep(runtime.budget(1))

class RecoveryBackupContext:
    def __init__(self,plan,root,package,operations):
        self.plan,self.root,self.package,self.ops=plan,Path(root),Path(package),operations
        self.runtime=operations.runtime;self.container=None
        state=json.loads(readonly_configuration(INPUTS['release_state'],private=True).read_text())
        release=state['known_good_release'];self.release_sha=release['sha']
        previous=plan.candidate_destination['post_compensation']['baseline']['previous_plan_sha256']
        from deployment.lib.active_recovery_compensated import inspect_history
        prior,_,_,_=inspect_history(previous)
        if release.get('provider')!='local' or release.get('schema')!=115 or self.release_sha!=prior.source_sha or release['images']!=prior.candidate_images:
            raise RuntimeError('recovery_backup_retained_release_changed')
        self.release=release
        self.replica_plan=SimpleNamespace(digest=digest({'plan_sha256':plan.digest,'operation':'current-data-recovery-backup-before-normal'}))
    def read_only_feasibility(self):
        expected=declaration(self.plan)
        if (not expected or file_digest(readonly_configuration(MARKER,private=False))!=expected['marker_sha256']
                or file_digest(readonly_configuration(LATEST,private=False))!=expected['latest_sha256']):
            raise RuntimeError('recovery_backup_preimages_changed')
        name='madar-recovery-backup-'+self.plan.digest[:12]
        executable=EXECUTABLES_BASE/('madar-normal-recovery-backup-'+self.plan.digest[:12])
        scope=Path('/var/lib/madar/backups')/('recovery-before-normal-'+self.plan.digest)
        if name in self.runtime.names() or executable.exists() or executable.is_symlink() or scope.exists() or scope.is_symlink():
            raise RuntimeError('recovery_backup_exclusive_resource_changed')
        backend=self.runtime.inspect(['madar-green-backend'])['madar-green-backend']
        bound=self.plan.candidate_destination['post_compensation']['baseline']['resources']['madar-green-backend']
        if (backend['Id']!=bound['container_id'] or backend['Image']!=self.release['images']['backend']
                or spec(backend)!=bound['spec_sha256'] or not backend['State']['Running']):
            raise RuntimeError('recovery_backup_retained_backend_changed')
        return {'capture_release_sha':self.release_sha,'database_read_only':True,'host_ports':False}
    def guard(self):
        self.ops.verify_frozen_source(self.plan)
        from deployment.lib.active_recovery_compensated import verify_compensated_binding
        verify_compensated_binding(self.plan.candidate_destination["post_compensation"],self.runtime,
            recovery_backup=(self.plan,self.resource) if self.container is not None else None)
        self.ops.require_no_normal_write_authority();self.ops.require_all_consumers_stopped()
        auth=json.loads(protected(self.root/'authorization.json',private=True).read_text())
        if self.root!=BASE/self.plan.digest or auth.get('operation')!='current-data-recovery-backup-before-normal' or auth.get('plan_sha256')!=self.plan.digest or auth.get('source_bundle_sha256')!=self.plan.source_bundle_sha256:
            raise RuntimeError('recovery_backup_fresh_authorization_required')
        expected=declaration(self.plan)
        if (file_digest(readonly_configuration(MARKER,private=False))!=expected['marker_sha256']
                or file_digest(readonly_configuration(LATEST,private=False))!=expected['latest_sha256']):
            raise RuntimeError('recovery_backup_preimages_changed')
    def prepare(self):
        self.read_only_feasibility();self.guard()
        self.helpers=EXECUTABLES_BASE/('madar-normal-recovery-backup-'+self.plan.digest[:12])
        self.helpers.mkdir(mode=0o755)
        for name in ('backup_support.py','backup_madar.sh','verify_backup.sh'):
            source=protected(self.package/'source/web/scripts'/name,private=True);out=self.helpers/name
            out.write_bytes(source.read_bytes());out.chmod(0o444)
            if file_digest(out)!=file_digest(source):raise RuntimeError('recovery_backup_helper_changed')
        self.helpers.chmod(0o555)
        rows=self.runtime.inspect(['supabase-db','supabase-envoy','madar-green-backend'])
        backend=rows['madar-green-backend'];envoy=rows['supabase-envoy'];db=rows['supabase-db']
        expected=self.plan.candidate_destination['post_compensation']['baseline']['resources']['madar-green-backend']
        if backend['Id']!=expected['container_id'] or backend['Image']!=self.release['images']['backend'] or spec(backend)!=expected['spec_sha256']:
            raise RuntimeError('recovery_backup_retained_backend_changed')
        native=next(iter(db['NetworkSettings']['Networks']));gateway=envoy['NetworkSettings']['Networks'][native]['IPAddress']
        network=next(k for k in backend['NetworkSettings']['Networks'] if k.startswith('madar-normal-'))
        address=backend['NetworkSettings']['Networks'][network]['IPAddress']
        for value in (address,gateway):
            ip=ipaddress.ip_address(value)
            if ip.version!=4 or not ip.is_private:raise RuntimeError('recovery_backup_destination_invalid')
        config=self.helpers/'proxy.conf'
        # Directory becomes writable only to root while this new nonsecret file is sealed.
        self.helpers.chmod(0o755)
        config.write_text(f'pid /tmp/recovery-backup.pid; error_log stderr notice; events {{}} http {{ access_log off; server {{ listen 127.0.0.1:8001; location / {{ proxy_pass http://{address}:8000; }} }} server {{ listen 127.0.0.1:18000; location / {{ proxy_pass http://{gateway}:8000; }} }} }}')
        config.chmod(0o444);self.helpers.chmod(0o555)
        name='madar-recovery-backup-'+self.plan.digest[:12]
        self.container=checked(['docker','create','--name',name,'--user','nginx','--network',native,'--restart','no','--read-only',
            '--security-opt','no-new-privileges','--cap-drop','ALL','--tmpfs','/tmp:rw,nosuid,nodev','--tmpfs','/var/cache/nginx:rw,nosuid,nodev,mode=1777',
            '--mount','type=bind,src='+str(config)+',dst=/proxy.conf,readonly','--entrypoint','nginx',self.release['images']['frontend'],
            '-c','/proxy.conf','-g','daemon off;']).strip()
        checked(['docker','network','connect',network,self.container]);checked(['docker','start',self.container])
        row=next(iter(self.runtime.inspect([self.container]).values()))
        if row['HostConfig']['PortBindings'] or not row['State']['Running']:raise RuntimeError('recovery_backup_proxy_not_private')
        self.pid=row['State']['Pid'];self.proxy_spec=spec(row);self.attachments=row['NetworkSettings']['Networks']
        self.resource={'container_id':row['Id'],'image_id':row['Image'],'spec_sha256':self.proxy_spec,
            'running':row['State']['Running'],'status':row['State']['Status'],'restart':row['HostConfig']['RestartPolicy']['Name'],
            'networks':{k:v['NetworkID'] for k,v in self.attachments.items()}}
        # Docker start is asynchronous. Require the actual retained version
        # through this private namespace before starting the restricted child.
        deadline=time.monotonic()+30
        probe="import json,urllib.request;print(json.dumps(json.load(urllib.request.urlopen('http://127.0.0.1:8001/health/version',timeout=2))))"
        while True:
            check=subprocess.run(['nsenter','--target',str(self.pid),'--net','/usr/bin/python3','-I','-B','-c',probe],
                env=ENVIRONMENT,capture_output=True,text=True,timeout=5)
            if check.returncode==0:
                version=json.loads(check.stdout)
                if version.get('release_sha')!=self.release_sha or version.get('release_slot')!='green':
                    raise RuntimeError('recovery_backup_version_identity_changed')
                break
            if time.monotonic()>=deadline:raise RuntimeError('recovery_backup_proxy_activation_deadline')
            time.sleep(min(.2,deadline-time.monotonic()))
        exclusive(self.root/'capture-context.json',encoded({'plan_sha256':self.plan.digest,'approved_source_sha':self.plan.source_sha,
            'captured_release':self.release,'container_id':self.container,'image_id':row['Image'],'spec_sha256':self.proxy_spec,
            'native_database_id':db['Id'],'resource':self.resource,'database_read_only':True,'consumers_started':False}))
    def capture(self,env,descriptor,identity):
        row=next(iter(self.runtime.inspect([self.container]).values()))
        if row['State']['Pid']!=self.pid or spec(row)!=self.proxy_spec or row['NetworkSettings']['Networks']!=self.attachments:raise RuntimeError('recovery_backup_proxy_changed')
        prefix=['nsenter','--target',str(self.pid),'--net','setpriv','--reuid='+str(identity.pw_uid),'--regid='+str(identity.pw_gid),'--clear-groups','--no-new-privs']
        probe="import os,pathlib,subprocess;assert subprocess.run(['docker','inspect','supabase-db'],capture_output=True).returncode!=0;assert not os.getgroups();assert next(x.split(':')[1].strip() for x in pathlib.Path('/proc/self/status').read_text().splitlines() if x.startswith('NoNewPrivs:'))=='1'"
        checked([*prefix,'/usr/bin/python3','-I','-B','-c',probe],env=env,pass_fds=(descriptor,))
        checked([*prefix,'/usr/bin/python3','-I','-B',str(self.helpers/'backup_support.py'),'scheduled',str(self.helpers/'backup_madar.sh')],env=env,pass_fds=(descriptor,))
    def close_and_guard(self):
        row=next(iter(self.runtime.inspect([self.container]).values()))
        if row['Id']!=self.container or spec(row)!=self.proxy_spec or row['NetworkSettings']['Networks']!=self.attachments:raise RuntimeError('recovery_backup_proxy_changed')
        checked(['docker','rm','-f',self.container]);self.container=None
        self.guard()
    def record_publication(self,backup,sums):
        exclusive(self.root/'publication.json',encoded({'operation':'actual-verified-recovery-backup-freshness-publication',
            'plan_sha256':self.plan.digest,'source_bundle_sha256':self.plan.source_bundle_sha256,'backup_id':backup.name,
            'captured_release_sha':self.release_sha,'marker_sha256':file_digest(readonly_configuration(MARKER,private=False)),
            'latest_sha256':file_digest(readonly_configuration(LATEST,private=False)),
            'backup_receipt_sha256':file_digest(protected(self.root/'verified-recovery-backup.json',private=True)),
            'customer_database_restored':False,'normal_writes_granted':False}))

def execute_recovery_backup(plan,package,operations):
    if not declaration(plan):raise RuntimeError('recovery_backup_not_declared')
    operations.verify_frozen_source(plan);operations.verify_active_rollback_inputs(plan)
    root=BASE/plan.digest
    if root.exists() or root.is_symlink():raise RuntimeError('recovery_backup_attempt_already_used')
    for parent in (BASE.parent,*BASE.parent.parents):
        st=parent.lstat()
        if parent.is_symlink() or st.st_uid!=0 or st.st_mode&0o022:raise RuntimeError('recovery_backup_namespace_untrusted')
    BASE.mkdir(mode=0o700,exist_ok=True)
    if BASE.is_symlink() or BASE.stat().st_uid!=0 or BASE.stat().st_mode&0o077:raise RuntimeError('recovery_backup_namespace_untrusted')
    root.mkdir(mode=0o700)
    exclusive(root/'authorization.json',encoded({'operation':'current-data-recovery-backup-before-normal','plan_sha256':plan.digest,
        'source_bundle_sha256':plan.source_bundle_sha256,'normal_authorization_issued':False}))
    context=RecoveryBackupContext(plan,root,package,operations)
    try:
        context.prepare()
        capture_and_replicate(plan,root,Path(package),operations.source.verify,operations,recovery_context=context)
        return require_publication(plan,package,operations.runtime)
    except Exception as error:
        import traceback
        frames=[{'file':Path(f.filename).name,'function':f.name,'line':f.lineno} for f in traceback.extract_tb(error.__traceback__)[-16:]]
        exclusive(root/'failure.json',encoded({'operation':'current-data-recovery-backup-before-normal','plan_sha256':plan.digest,
            'exception_type':type(error).__name__,'traceback':frames,'messages_redacted':True,
            'customer_database_restored':False,'normal_authorization_issued':False}))
        raise
