"""Routine admission adapter to the existing ReleaseDeployer/Docker operations.

No replacement deployment state machine, SQL executor, issuer or traffic driver.
Root owns exact authority. Source-owned checks execute without Docker, network,
credentials or writable host mounts. Production operation is not enabled here.
"""
from __future__ import annotations
import json,os,re,subprocess,sys,time
from pathlib import Path
from .migration_inventory import canonical,digest,strict_json
from . import automatic_release_admission as admission
from .provider_recovery_runtime import protected,readonly_configuration
from .control_plane_upgrade import acquire_lock,require_root_directory
from .release_deployer import Compatibility,ReleaseDeployer
from .migration_executor import atomic_json

ROLES=('backend','frontend','redis','parser-worker','remote-ingestion-worker',
       'notification-worker','calendar-sync-worker','data-deletion-worker')
LIMITS_MIB={'backend':1280,'frontend':128,'redis':128,'parser-worker':768,
    'remote-ingestion-worker':256,'notification-worker':256,'calendar-sync-worker':256,'data-deletion-worker':256}


def validate_candidate_model(model,value,source_root):
    """Reject elevated Compose inputs before Docker creates any candidate."""
    if not isinstance(model,dict) or set(model.get('services',{}))!=set(ROLES):
        raise RuntimeError('automatic_candidate_roles_changed')
    data=Path('/var/lib/madar/storage');authority=grant_directory(value)
    for role,row in model['services'].items():
        host=row.get('network_mode','');image=row.get('image','')
        if (row.get('container_name')!='madar-'+value['candidate']['slot']+'-'+role
                or row.get('privileged') or host or row.get('pid') or row.get('ipc')=='host'
                or row.get('cap_add') or row.get('devices') or row.get('device_requests')
                or row.get('cap_drop')!=['ALL'] or row.get('security_opt')!=['no-new-privileges:true']
                or row.get('read_only') is not True or row.get('restart')!='no'
                or str(row.get('mem_limit'))!=str(LIMITS_MIB[role]*1024**2)
                or not 0<float(row.get('cpus',0))<=2 or row.get('pids_limit')!=128):
            raise RuntimeError('automatic_candidate_privilege_or_budget_invalid')
        expected=value['candidate']['images']['frontend' if role=='frontend' else 'backend'].split('@',1)[1]
        if role=='redis':
            if not re.fullmatch(r'[^\s]+@sha256:[a-f0-9]{64}',image):raise RuntimeError('automatic_redis_not_pinned')
        elif image!=expected:raise RuntimeError('automatic_candidate_image_not_admitted')
        for port in row.get('ports',[]):
            if port.get('host_ip')!='127.0.0.1':raise RuntimeError('automatic_candidate_public_port_refused')
        for mount in row.get('volumes',[]):
            path=Path(mount.get('source',''))
            if mount.get('type')!='bind' or not path.is_absolute() or '..' in path.parts:
                raise RuntimeError('automatic_candidate_volume_not_admitted')
            if path.is_relative_to(data) and path!=data:
                if mount.get('target') not in {'/app/uploads','/app/avatar_uploads','/app/private_uploads','/app/private_generated_charts'}:
                    raise RuntimeError('automatic_candidate_data_destination_changed')
            elif ((path.is_relative_to(source_root) and path!=source_root)
                    or path==authority or path==Path('/var/lib/madar/backup-state')):
                if mount.get('read_only') is not True:raise RuntimeError('automatic_candidate_control_mount_writable')
            else:raise RuntimeError('automatic_candidate_host_mount_not_admitted')


def runtime_context(value):
    return digest({k:value[k] for k in ('attempt_id','source_sha','controller_sha')}|{
        'database_system_identifier':value['database']['system_identifier']})


def grant_directory(value):
    return admission.ROOT/'runtime'/value['attempt_id']/'write-authority'


def publish_candidate_grant(value,mode):
    """Exact root file, not an application-readable bearer credential."""
    if mode=='READ_ONLY':
        admission.sealed(value,allow_expired=True);admission.require_reserved(value,allow_completed=True)
    else:admission.require_reserved(value)
    if mode not in {'READ_ONLY','NORMAL'}:raise RuntimeError('automatic_grant_mode_invalid')
    runtime=admission.ROOT/'runtime';require_root_directory(runtime,create=True)
    require_root_directory(runtime/value['attempt_id'],create=True)
    path=grant_directory(value);require_root_directory(path,mode=0o755,create=True)
    candidate=value['candidate'];plan=value['plan']
    record={'version':4,'operation':admission.OPERATION,'operation_id':value['operation_id'],
        'attempt_id':value['attempt_id'],'schema':value['database']['target_schema'],
        'target_schema':value['database']['target_schema'],'release_sha':value['source_sha'],
        'contract_digest':runtime_context(value),'mode':mode,'controller_sha':value['controller_sha'],
        'database_system_identifier':value['database']['system_identifier'],'plan_sha256':digest(plan),
        'compatible_min':candidate['compatible_min'],'compatible_max':candidate['compatible_max']}
    atomic_json(path/'authority.json',record);(path/'authority.json').chmod(0o444)
    return record


def operations_adapter(base,system,value):
    """Adapt immutable inputs/authority only; reuse real lifecycle operations."""
    class AuthorizedOperations(base):
        def __init__(self):
            candidate=value['candidate'];plan=value['plan']
            compatibility=Compatibility(candidate['compatible_min'],candidate['compatible_max'],
                plan['target_schema'],'none' if not plan['migrations'] else 'expand-only',
                value['origin']['compatible_min'],value['origin']['compatible_max'])
            super().__init__(system.repo,system.state_root,Path('/etc/madar/production.env'),compatibility)
            self.automatic_release_admission=value;self._issuer=system;self._credential_root=None
            self._origin_fenced=[];self._model=None;self._candidate_rows=None;self._expected_route=value['origin']['slot']
            self._initial_scope=strict_json(protected(Path('/etc/madar/isolated-release-test.json'),private=True).read_bytes())['runtime_scope']

        def verify_actor_scope(self):
            from .isolated_release_environment import verify_runtime_scope
            from .completed_normal_resources import measured_spec_matches
            import copy,hashlib
            ids=self.run(['/usr/bin/docker','ps','-aq','--no-trunc'],capture=True).split()
            rows=json.loads(self.run(['/usr/bin/docker','inspect',*ids],capture=True))
            candidate=self._candidate_rows or {}
            if set(ids)!=set(self._initial_scope)|set(candidate):raise RuntimeError('automatic_unexpected_runtime_actor')
            expected=copy.deepcopy(self._initial_scope)
            if self._expected_route!=value['origin']['slot']:
                # The existing traffic driver changes exactly this nonsecret
                # file. Never ignore an entire proxy directory's drift.
                proxy=next(r for r in rows if r['Name']=='/madar-release-proxy')
                binding=expected[proxy['Id']]['binds']['/etc/nginx/madar']
                path=Path(binding['source'])
                if path!=Path('/var/lib/madar/proxy') or sorted(p.name for p in path.iterdir())!=['active-upstreams.conf']:
                    raise RuntimeError('automatic_proxy_input_inventory_changed')
                ports={'blue':(8101,3100),'green':(8201,3200)}[self._expected_route]
                body=('upstream madar_backend_active { server 127.0.0.1:'+str(ports[0])+'; }\n'
                    'upstream madar_frontend_active { server 127.0.0.1:'+str(ports[1])+'; }\n').encode()
                if (path/'active-upstreams.conf').read_bytes()!=body:raise RuntimeError('automatic_proxy_route_changed')
                binding['contents_sha256']=digest({'active-upstreams.conf':{'sha256':hashlib.sha256(body).hexdigest(),'uid':1000,'mode':0o644}})
            verify_runtime_scope(expected,[r for r in rows if r['Id'] in self._initial_scope])
            for row in rows:
                if row['Id'] not in candidate:continue
                old=candidate[row['Id']]
                if row['Name']!=old['Name'] or row['Image']!=old['Image'] or not measured_spec_matches(row,old['spec_sha256'],started_worker=True):
                    raise RuntimeError('automatic_candidate_runtime_substituted')
            return rows

        def state_published(self):
            import pwd
            user=pwd.getpwnam('madar')
            for name in ('state.json','worker-ownership.json'):
                path=self.state_root/name
                if path.exists():
                    if path.is_symlink():raise RuntimeError('automatic_state_symlink_refused')
                    os.chown(path,user.pw_uid,user.pw_gid);path.chmod(0o600)

        def schema_version(self):
            with admission.connect_database() as db:
                identifier,schema=db.execute("SELECT system_identifier::text,schema_version FROM pg_catalog.pg_control_system(),public.application_schema_state WHERE contract_key='core'").fetchone()
                if identifier!=value['database']['system_identifier']:raise RuntimeError('automatic_execution_database_substituted')
                return schema

        def guard(self):
            admission.sealed(value);admission.require_reserved(value)
            from .control_plane_upgrade_authorization import require_upgrade_authorization
            require_upgrade_authorization(value['source_sha'],required_operation=admission.OPERATION,
                required_schema=value['database']['origin_schema'],required_context_digest=digest(value))
            with admission.connect_database() as db:
                observed=db.execute("SELECT system_identifier::text,schema_version FROM pg_catalog.pg_control_system(),public.application_schema_state WHERE contract_key='core'").fetchone()
                if observed!=(value['database']['system_identifier'],value['database']['target_schema']):
                    raise RuntimeError('automatic_live_execution_database_changed')

        def admit_deployment(self,sha,state,descriptor):
            if sha!=value['source_sha']:raise RuntimeError('automatic_execution_source_changed')
            system.deploy_lock_descriptor=descriptor # borrowed, owned by ReleaseDeployer
            admission.reserve(value,system)
            system.arm_interlock(sha)
            system.write_authorization(sha,automatic_release_admission=value)
            credential_root=system.runtime_root/('automatic-'+value['attempt_id'])
            require_root_directory(credential_root,mode=0o711,create=True)
            target=credential_root/'madar-control-plane-upgrade'
            fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'wb') as stream:
                stream.write(protected(system.authorization_file,private=True).read_bytes());stream.flush();os.fsync(stream.fileno())
            import pwd
            user=pwd.getpwnam('madar');os.chown(target,user.pw_uid,user.pw_gid);target.chmod(0o400)
            self._credential_root=credential_root;os.environ['CREDENTIALS_DIRECTORY']=str(credential_root)
            self.guard();publish_candidate_grant(value,'READ_ONLY')
            receipt=admission.ROOT/'attempts'/value['attempt_id']/'authorization.json'
            atomic_json(receipt,{'admission_sha256':digest(value),'plan_sha256':digest(value['plan']),
                'environment':value['environment'],'source_sha':sha,'database':value['database'],
                'operation_id':value['operation_id'],'attempt_id':value['attempt_id'],
                'authorized_at':int(time.time()),'expires_at':value['expires_at']},exclusive=True)

        def run(self,command,*,cwd=None,env=None,capture=False):
            # The generic parent owns the only issuer. Candidate scripts never
            # inherit its root privileges, Docker socket or operational env.
            if command and str(command[0]) in {sys.executable,'python','python3','/usr/bin/python3'} and len(command)>1 and '/web/scripts/' in str(command[1]):
                script=Path(command[1]);relative=script.relative_to(self.release_root).as_posix()
                if relative not in {'web/scripts/check_migrations.py','web/scripts/check_migration_transitions.py','web/scripts/check_secret_hygiene.py'}:
                    raise RuntimeError('automatic_unreviewed_source_command')
                # Independently enrolled locked tools, not the candidate image.
                tool=protected(Path('/etc/madar/automatic-check-image'),private=True).read_text().strip()
                if not re.fullmatch('sha256:[a-f0-9]{64}',tool):raise RuntimeError('automatic_check_image_unpinned')
                command=['/usr/bin/docker','run','--rm','--network','none','--read-only','--user','65534:65534',
                    '--cap-drop','ALL','--security-opt','no-new-privileges:true','--memory','256m','--cpus','.5','--pids-limit','64',
                    '--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777','--volume',str(self.release_root)+':/source:ro',
                    '--entrypoint','python',tool,'-B','/source/'+relative]
                cwd=None;env={'PATH':os.defpath,'HOME':'/nonexistent'}
            elif command and command[0]=='git':
                location=Path(cwd or self.repo).resolve()
                if location not in {self.repo.resolve(),(self.state_root/'releases'/value['source_sha']).resolve()}:
                    raise RuntimeError('automatic_git_location_not_admitted')
                command=['/usr/bin/git','-c','safe.directory='+str(location),'-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false',*command[1:]]
                env=dict(env or os.environ,GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null',GIT_NO_REPLACE_OBJECTS='1')
            if command and command[0]==os.getenv('MADAR_TRAFFIC_SWITCH_COMMAND'):
                # Preserve the installed traffic driver's canonical mutation UID.
                command=['/usr/sbin/runuser','-u','madar','--',*command]
            if 'compose' in command and 'config' in command and '--format' in command:
                result=super().run(command,cwd=cwd,env=env,capture=True)
                self._model=strict_json(result);return result
            return super().run(command,cwd=cwd,env=env,capture=capture)

        def build(self,sha,slot):
            self.guard()
            if sha!=value['source_sha'] or slot!=value['candidate']['slot']:raise RuntimeError('automatic_candidate_scope_changed')
            images=value['candidate']['images']
            for role in ('backend','frontend','worker'):
                if self._digest(images[role].split('@')[0])!=images[role]:raise RuntimeError('automatic_immutable_artifact_changed')
            return dict(images,artifact_reused=True)

        def release_metadata_path(self):
            path=admission.directory(value)/'runtime-compatibility.json'
            if not path.exists():
                metadata={'schema':{'compatible_min':self.compatibility.schema_min,'compatible_max':self.compatibility.schema_max,
                    'target':self.compatibility.target_schema,'migration_class':self.compatibility.migration_class,
                    'rollback_compatible_min':self.compatibility.rollback_schema_min,'rollback_compatible_max':self.compatibility.rollback_schema_max}}
                atomic_json(path,metadata,exclusive=True);path.chmod(0o400)
            return protected(path,private=True)

        def _environment(self,sha,slot,images,*,workers_active=False):
            env=super()._environment(sha,slot,images,workers_active=workers_active)
            if sha!=value['source_sha'] or slot!=value['candidate']['slot']:return env
            # Release receipts use tag@local-image-ID. On Docker's classic
            # image store that ID is a config digest, not a registry manifest.
            # Execute the inspected local ID directly; never ask a registry to
            # resolve an invalid tag@config-digest or fall back to its tag.
            env.update(MADAR_BACKEND_IMAGE=images['backend'].split('@',1)[1],
                MADAR_FRONTEND_IMAGE=images['frontend'].split('@',1)[1],
                MADAR_BUSINESS_WRITE_AUTHORITY='/run/madar/business-write-authority/authority.json',
                MADAR_BUSINESS_WRITE_CONTRACT=runtime_context(value),MADAR_BUSINESS_WRITE_AUTHORITY_ROOT=str(grant_directory(value)),
                MADAR_RELEASE_CONTROLLER_SHA=value['controller_sha'],MADAR_RELEASE_DATABASE_SYSTEM_IDENTIFIER=value['database']['system_identifier'])
            return env

        def additional_compose_files(self):
            # Same compose implementation, with the existing authority RO mount.
            if os.environ.get('MADAR_COMPOSE_OVERRIDE'):
                raise RuntimeError('automatic_ambient_compose_override_refused')
            require_root_directory(admission.ROOT,create=True)
            prepared=admission.directory(value);require_root_directory(prepared,create=True)
            override=prepared/'authority-compose.json'
            if not override.exists():
                # Only authority fields; candidate cannot supply host paths.
                fields={'environment':{'MADAR_BUSINESS_WRITE_AUTHORITY':'${MADAR_BUSINESS_WRITE_AUTHORITY}',
                    'MADAR_BUSINESS_WRITE_CONTRACT':'${MADAR_BUSINESS_WRITE_CONTRACT}',
                    'MADAR_RELEASE_CONTROLLER_SHA':'${MADAR_RELEASE_CONTROLLER_SHA}',
                    'MADAR_RELEASE_DATABASE_SYSTEM_IDENTIFIER':'${MADAR_RELEASE_DATABASE_SYSTEM_IDENTIFIER}'},
                    'volumes':[{'type':'bind','source':str(grant_directory(value)),'target':'/run/madar/business-write-authority','read_only':True}]}
                realm=strict_json(protected(Path('/etc/madar/isolated-release-test.json'),private=True).read_bytes())['realm_id']
                services={r:{'restart':'no','mem_limit':LIMITS_MIB[r]*1024**2,'pids_limit':128,
                    'labels':{'com.madar.test.realm':realm}} for r in ROLES}
                for role in ('backend','parser-worker','remote-ingestion-worker','notification-worker','calendar-sync-worker','data-deletion-worker'):
                    services[role].update(fields)
                atomic_json(override,{'services':services,'networks':{name:{'labels':{'com.madar.test.realm':realm}}
                    for name in ('default','parser_internal','remote_ingestion_internal','remote_ingestion_egress')}},exclusive=True)
                override.chmod(0o400)
            return (protected(override,private=True),)

        def _compose(self,sha,slot,images,*args,workers_active=False):
            # Seal the final requirements once; inactive consumers remain
            # CREATED, rather than changing the backend's requirements later.
            workers_active=True
            super()._compose(sha,slot,images,'config','--format','json',workers_active=workers_active)
            validate_candidate_model(self._model,value,self.release_root)
            if digest(self._model)!=value['candidate']['configuration_sha256']:
                raise RuntimeError('automatic_candidate_configuration_substituted')
            if args!=('config','--format','json'):
                return super()._compose(sha,slot,images,*args,workers_active=workers_active)

        def start_candidate(self,sha,slot,images):
            from .runtime_authority import runtime_mutation_lock
            from .completed_normal_resources import measured_spec
            self.guard()
            with runtime_mutation_lock(self.state_root):
                self.verify_actor_scope()
                if self._loaded_serving_slot()==slot:raise RuntimeError('runtime_mutation_target_is_serving')
                self._inhibit_worker_slot(slot)
                self._compose(sha,slot,images,'create','--no-build','--no-recreate',*ROLES,workers_active=True)
                rows=json.loads(self.run(['/usr/bin/docker','inspect',*['madar-'+slot+'-'+role for role in ROLES]],capture=True))
                if len(rows)!=8 or any(r['State']['Running'] or r['State']['Status']!='created' for r in rows):
                    raise RuntimeError('automatic_candidate_not_newly_created')
                self._candidate_rows={r['Id']:{'Name':r['Name'],'Image':r['Image'],'spec_sha256':measured_spec(r)} for r in rows}
                atomic_json(admission.ROOT/'attempts'/value['attempt_id']/'candidate-runtime.json',self._candidate_rows,exclusive=True)
                self.verify_actor_scope()
                self._compose(sha,slot,images,'up','-d','--no-build','--no-recreate','--wait','--wait-timeout','180',
                    'redis','parser-worker','remote-ingestion-worker','backend','frontend',workers_active=True)
                self.verify_actor_scope()

        def preflight(self,sha,slot,images,schema):
            self.guard();self._compose(sha,slot,images,'config','--format','json',workers_active=True)
            if self._model is None or digest(self._model)!=value['candidate']['configuration_sha256']:
                raise RuntimeError('automatic_candidate_configuration_substituted')
            super().preflight(sha,slot,images,schema)

        def deactivate_workers(self,release):
            super().deactivate_workers(release)
            if release.get('slot')==value['origin']['slot']:
                # An ungoverned bootstrap cannot acquire a fake old grant. Fence
                # its real backend and slot-local writers before target NORMAL.
                # Compatible governed origins can later use their preserved RO
                # grant without restarting the serving backend.
                names=['madar-'+release['slot']+'-'+r for r in ('backend','parser-worker','remote-ingestion-worker')]
                rows=json.loads(self.run(['/usr/bin/docker','inspect',*names],capture=True))
                if any(not r['State']['Running'] for r in rows):raise RuntimeError('automatic_origin_fence_preimage_changed')
                self._origin_fenced=[r['Id'] for r in rows]
                self.run(['/usr/bin/docker','update','--restart=no',*self._origin_fenced])
                self.run(['/usr/bin/docker','stop','--time','15',*self._origin_fenced])
                if any(r['State']['Running'] for r in json.loads(self.run(['/usr/bin/docker','inspect',*self._origin_fenced],capture=True))):
                    raise RuntimeError('automatic_origin_writer_fence_incomplete')
            elif release.get('slot')==value['candidate']['slot']:
                publish_candidate_grant(value,'READ_ONLY')

        def activate_workers(self,sha,slot,images):
            self.guard()
            if not self._origin_fenced:raise RuntimeError('automatic_origin_writers_not_fenced')
            self.verify_actor_scope()
            publish_candidate_grant(value,'NORMAL')
            from .runtime_authority import runtime_mutation_lock
            with runtime_mutation_lock(self.state_root):
                self._require_worker_authority(sha,slot);self._require_other_worker_slot_inactive(slot)
                ids=[identity for identity,row in self._candidate_rows.items() if row['Name'].rsplit('-',1)[0] in
                    {'/madar-'+slot+'-notification','/madar-'+slot+'-calendar-sync','/madar-'+slot+'-data-deletion'}]
                if len(ids)!=3:raise RuntimeError('automatic_candidate_worker_inventory_invalid')
                self.run(['/usr/bin/docker','start',*ids]);self.verify_actor_scope()

        def switch_traffic(self,slot):
            self.guard()
            if slot==value['candidate']['slot']:self.verify_actor_scope()
            result=super().switch_traffic(slot)
            self._expected_route=slot
            self.verify_actor_scope()
            return result

        def accept_runtime_inventory(self):
            """Advance only measured test inventory after durable known-good.

            Policy permissions, issuer keys, identity and expiry cannot change.
            The existing positive observer must accept the resulting inventory.
            This is lifecycle enrollment, never authority for another release.
            """
            from .isolated_release_environment import POLICY,measure_bind_source,observe
            from .completed_normal_resources import measured_spec
            rows=self.verify_actor_scope()
            policy=strict_json(protected(POLICY,private=True).read_bytes())
            if policy['runtime_scope']!=self._initial_scope:raise RuntimeError('automatic_environment_inventory_changed')
            scope={}
            for row in rows:
                binds={m['Destination']:measure_bind_source(m['Source'],mutable=m['RW']) for m in row['Mounts'] if m['Type']=='bind'}
                scope[row['Id']]={'name':row['Name'],'image':row['Image'],'spec_sha256':measured_spec(row),'binds':binds}
            atomic_json(POLICY,dict(policy,runtime_scope=scope))
            observe()

        def restore_workers(self,release):
            publish_candidate_grant(value,'READ_ONLY')
            self.guard()
            if self._origin_fenced:self.run(['/usr/bin/docker','start',*self._origin_fenced])
            return super().restore_workers(release)
    return AuthorizedOperations()


def execute(system,value,base_operations,*,manual_retry=False):
    """One exact routine cycle through the EXISTING deployment state machine."""
    if os.geteuid()!=0:raise RuntimeError('automatic_execution_root_required')
    admission.sealed(value)
    lock=acquire_lock(system.upgrade_root/'upgrade.lock',create=True)
    system.automatic_upgrade_lock=lock
    previous=os.environ.get('CREDENTIALS_DIRECTORY');adapter=None;result=None;completed=False
    try:
        adapter=operations_adapter(base_operations,system,value)
        deployer=ReleaseDeployer(state_root=system.state_root,compatibility=adapter.compatibility,operations=adapter)
        result=deployer.deploy(value['source_sha'],manual_retry=manual_retry)
        if result.get('status')!='known_good':raise RuntimeError('automatic_deployment_not_accepted')
        receipt={'operation':admission.OPERATION,'admission_sha256':digest(value),'attempt_id':value['attempt_id'],
            'source_sha':value['source_sha'],'database':value['database'],'release':result,
            'manual_retry_requested':manual_retry,'completed_at':int(time.time())}
        adapter.accept_runtime_inventory()
        atomic_json(admission.ROOT/'attempts'/value['attempt_id']/'completion.json',receipt,exclusive=True)
        completed=True
        return receipt
    finally:
        # Independently observe a just-written completion if interrupted after
        # publication. Expiry/audit failure must never prevent RO revocation.
        path=admission.ROOT/'attempts'/value['attempt_id']/'completion.json'
        if not completed and path.exists():
            try:
                record=strict_json(protected(path,private=True).read_bytes())
                completed=(record.get('admission_sha256')==digest(value) and record.get('attempt_id')==value['attempt_id']
                    and record.get('source_sha')==value['source_sha'] and record.get('release',{}).get('status')=='known_good')
            except Exception:completed=False
        try:
            if adapter is not None and not completed and adapter._credential_root is not None:
                publish_candidate_grant(value,'READ_ONLY')
        finally:
            try:
                system.clear_authorization()
                if completed:system.clear_interlock()
            finally:
                try:
                    if adapter is not None and adapter._credential_root is not None:
                        (adapter._credential_root/'madar-control-plane-upgrade').unlink(missing_ok=True)
                        adapter._credential_root.rmdir()
                finally:
                    if previous is None:os.environ.pop('CREDENTIALS_DIRECTORY',None)
                    else:os.environ['CREDENTIALS_DIRECTORY']=previous
                    system.deploy_lock_descriptor=None
                    os.close(lock);system.automatic_upgrade_lock=None
