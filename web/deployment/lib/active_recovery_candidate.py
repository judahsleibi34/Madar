"""Detached READ_ONLY candidate for a fresh active-rollback continuation.

Reuses the existing strict normal-local configuration and container factory.
This component cannot install a controller, publish routing, start business
consumers or grant NORMAL. It is not a complete production cutover entrypoint.
Only the fresh root-private continuation receipt authorizes candidate creation.
Historical preparation/activation PASS records and /run credentials are unused.
"""
from dataclasses import asdict, replace
import ipaddress
import json
import os
from pathlib import Path
import socket

from deployment.lib.active_recovery_resumption import ROOT
from deployment.lib.active_recovery_inputs import observe_retained_inputs
from deployment.lib.emergency_routing_repair import Runtime, AvailabilityFailure, identities, spec, verify
from deployment.lib.provider_local_transition_runtime import ProductionLocalTransitionOperations
from deployment.lib.provider_recovery import RecoveryContract
from deployment.lib.provider_local_transition import LocalTransitionContract
from deployment.lib.provider_recovery_phases import preparation_binding, sha256
from deployment.lib.provider_recovery_runtime import ProductionRecoveryOperations, RecoveryPaths, digest, file_digest, protected
from deployment.lib.release_deployer import atomic_json

LOCAL = Path('/var/lib/madar-control-plane/local-provider-transition')
RECOVERY = Path('/var/lib/madar-control-plane/provider402')
KINDS = ('notification', 'calendar-sync', 'data-deletion')


class DetachedRecoveryCandidate(ProductionLocalTransitionOperations):
    def __init__(self, plan, contract, root):
        plan.validate()
        self.plan, self.contract, self.root = plan, contract, Path(root)
        self.require_fresh_stage()
        if (contract.sha != plan.source_sha or contract.images != plan.candidate_images
                or contract.checkpoint_digest != plan.checkpoint_manifest_sha256
                or contract.reconciliation_digest != plan.reconciliation_execution_sha256
                or contract.evidence_digest != plan.acceptance_execution_sha256):
            raise RuntimeError('detached_candidate_contract_changed')
        # Runtime identity, rather than historical PASS claims, determines the
        # registered fallback and its private configuration namespace.
        runtime = Runtime()
        verify(runtime)
        inputs = runtime.input_bytes()
        old = RecoveryContract(**json.loads(inputs['recovery_contract']))
        if contract.recovery_context != digest(asdict(old)):
            raise RuntimeError('detached_recovery_context_changed')
        _, _, names, _ = identities(inputs)
        rows = runtime.inspect(list(names.values()))
        for role, name in names.items():
            if plan.fallback[role] != {'container_id': rows[name]['Id'],
                    'image_id': rows[name]['Image'], 'spec_sha256': spec(rows[name])}:
                raise RuntimeError('detached_registered_fallback_changed')
        # Deriving a directory name is not acceptance or reuse of its receipts.
        metadata = json.loads(inputs['schema_contract'])
        old.validate(metadata)
        contract.validate(metadata)
        names_for_fingerprints={'environment':'production_configuration','state':'release_state','upstream':'upstream',
            'worker_authority':'worker_authority','controller':'controller','recovery':'recovery_transaction','traffic':'traffic'}
        if contract.production_fingerprints!={key:plan.retained_inputs[value] for key,value in names_for_fingerprints.items()}:
            raise RuntimeError('detached_prior_fingerprints_changed')
        binding = sha256(preparation_binding(old, metadata))
        prefix = 'madar-provider402-rehearsal-' + binding[:12] + '-candidate'
        if names != {role: prefix + '-local-fallback-' + role for role in ('backend','frontend')}:
            raise RuntimeError('detached_registered_namespace_changed')
        configuration = LOCAL / 'configuration.env'
        if file_digest(protected(configuration, private=True)) != plan.retained_inputs['local_configuration']:
            raise RuntimeError('detached_local_configuration_changed')
        paths = replace(RecoveryPaths(), target_env=RECOVERY/'rehearsals'/binding/'configuration.env', prefix=prefix)
        # Explicitly derived paths load strict configuration but do not consume
        # legacy preparation authorization. The fresh receipt remains mandatory.
        self.recovery = ProductionRecoveryOperations(paths, old)
        self.state = self.recovery.paths.state
        self.slot = 'green' if old.origin_slot == 'blue' else 'blue'
        self.redis_name = prefix + '-redis'
        recovery_slot = 'green' if old.origin_slot == 'blue' else 'blue'
        self.redis_network = prefix + '-' + recovery_slot + '-runtime'
        self._load_configuration(configuration)
        self.prefix = 'madar-normal-' + plan.digest[:12]
        self.network_name = self.prefix + '-runtime'
        self.backend_port = {'blue':8101, 'green':8201}[self.slot]
        self.frontend_port = {'blue':3100, 'green':3200}[self.slot]

    @classmethod
    def from_saved_runtime(cls,plan,root,source_guard):
        """Read durable current-source bindings without reusing stage authority.

        Used by governed boot/revocation checks, not an authorization entrypoint.
        It never invokes old emergency verification after controller handoff.
        """
        if not callable(source_guard):raise RuntimeError('saved_candidate_source_guard_required')
        source_guard();plan.validate();root=Path(root)
        if os.geteuid()!=0 or root!=ROOT/plan.digest:raise RuntimeError('saved_candidate_root_required')
        receipt=json.loads(protected(root/'authorization.json',private=True).read_text())
        if (receipt.get('operation')!='active-local-rollback-resumption' or receipt.get('plan_sha256')!=plan.digest
                or receipt.get('source_bundle_sha256')!=plan.source_bundle_sha256):
            raise RuntimeError('saved_candidate_authorization_changed')
        saved=json.loads(protected(root/'candidate-contract.json',private=True).read_text())
        contract=LocalTransitionContract(**saved['contract'])
        old_path=protected(RECOVERY/'contract.json',private=True)
        metadata_path=protected(RECOVERY/'schema-contract.json',private=True)
        if file_digest(old_path)!=plan.retained_inputs['recovery_contract'] or file_digest(metadata_path)!=plan.retained_inputs['schema_contract']:
            raise RuntimeError('saved_candidate_recovery_inputs_changed')
        old=RecoveryContract(**json.loads(old_path.read_text()))
        slot='green' if old.origin_slot=='blue' else 'blue'
        value=cls.__new__(cls)
        value.plan,value.contract,value.root=plan,contract,root
        value.slot=slot;value.prefix='madar-normal-'+plan.digest[:12];value.network_name=value.prefix+'-runtime'
        metadata=json.loads(metadata_path.read_text())
        old.validate(metadata);contract.validate(metadata)
        binding=sha256(preparation_binding(old,metadata));prefix='madar-provider402-rehearsal-'+binding[:12]+'-candidate'
        if (saved.get('version')!=1 or type(saved.get('version')) is not int or saved.get('plan_sha256')!=plan.digest
                or contract.sha!=plan.source_sha or contract.images!=plan.candidate_images
                or contract.recovery_context!=digest(asdict(old))
                or contract.checkpoint_digest!=plan.checkpoint_manifest_sha256
                or contract.reconciliation_digest!=plan.reconciliation_execution_sha256
                or contract.evidence_digest!=plan.acceptance_execution_sha256):
            raise RuntimeError('saved_candidate_contract_changed')
        names={'environment':'production_configuration','state':'release_state','upstream':'upstream',
            'worker_authority':'worker_authority','controller':'controller','recovery':'recovery_transaction','traffic':'traffic'}
        if contract.production_fingerprints!={key:plan.retained_inputs[value] for key,value in names.items()}:
            raise RuntimeError('saved_candidate_prior_fingerprints_changed')
        # Fixed canonical recovery paths remain measured inputs, not permission
        # to consume historical acceptance or reconstruct expired credentials.
        paths=replace(RecoveryPaths(),target_env=RECOVERY/'rehearsals'/binding/'configuration.env',prefix=prefix)
        value.recovery=ProductionRecoveryOperations(paths,old)
        value.state=value.recovery.paths.state;value.redis_name=prefix+'-redis';value.redis_network=prefix+'-'+slot+'-runtime'
        value.backend_port={'blue':8101,'green':8201}[slot];value.frontend_port={'blue':3100,'green':3200}[slot]
        if file_digest(protected(LOCAL/'configuration.env',private=True))!=plan.retained_inputs['local_configuration']:
            raise RuntimeError('saved_candidate_configuration_changed')
        value._load_configuration(LOCAL/'configuration.env');source_guard()
        return value

    def require_fresh_stage(self):
        if os.geteuid() != 0 or self.root != ROOT/self.plan.digest:
            raise RuntimeError('detached_fresh_root_namespace_required')
        if (not self.root.is_dir() or self.root.is_symlink() or self.root.stat().st_uid != 0
                or self.root.stat().st_mode & 0o077):
            raise RuntimeError("detached_fresh_root_namespace_required")
        for parent in self.root.parents:
            st = parent.lstat()
            if parent.is_symlink() or st.st_uid != 0 or st.st_mode & 0o022:
                raise RuntimeError("detached_fresh_root_namespace_required")
        receipt = json.loads(protected(self.root/'authorization.json', private=True).read_text())
        if (receipt.get('operation') != 'active-local-rollback-resumption'
                or receipt.get('plan_sha256') != self.plan.digest
                or receipt.get('source_bundle_sha256') != self.plan.source_bundle_sha256):
            raise RuntimeError('detached_fresh_authorization_required')
        events = [json.loads(line) for line in protected(self.root/'events.jsonl', private=True).read_text().splitlines()]
        if (len(events) != 2 or [event.get('phase') for event in events] != ['authorized','detached_candidate_pending']
                or any(event.get('plan_sha256') != self.plan.digest for event in events)):
            raise RuntimeError('detached_stage_not_authorized')

    def _env(self, contract, *, worker=False):
        config=super()._env(contract,worker=worker)
        # The preparation marker has disputed provenance and is a different
        # snapshot. Never use it as the normal candidate's freshness proof.
        config['BACKUP_FRESHNESS_MARKER']='/run/madar/backup-state/latest.json'
        return config

    def _backup_marker_mount(self, cfg):
        from deployment.lib.provider_recovery_runtime import readonly_configuration
        source=Path('/var/lib/madar/backup-state/latest.json')
        if cfg['BACKUP_FRESHNESS_MARKER']!='/run/madar/backup-state/latest.json':
            raise RuntimeError('detached_backup_marker_destination_changed')
        readonly_configuration(source,private=False)
        marker=json.loads(source.read_text())
        if (marker.get('format') != 2 or marker.get('verified') is not True
                or marker.get('scope') != 'complete-coordinated-checkpoint' or marker.get('schema') != 115
                or marker.get('manifest_sha256') != self.plan.checkpoint_manifest_sha256
                or marker.get('execution_sha256') != self.plan.checkpoint_execution_sha256):
            raise RuntimeError('detached_backup_marker_proof_changed')
        if not source.parent.is_dir() or source.parent.is_symlink():
            raise RuntimeError('detached_backup_marker_directory_invalid')
        # Scheduled verification atomically replaces latest.json. A directory
        # bind follows those new inodes; a file bind would retain stale proof.
        return 'type=bind,src=/var/lib/madar/backup-state,dst=/run/madar/backup-state,readonly'

    def name(self, kind):
        # Do not change the emergency relay's pinned business-consumer inventory.
        if kind not in {'backend','frontend','parser', *KINDS}:
            raise RuntimeError('detached_kind_invalid')
        return self.prefix + '-' + (kind+'-standby' if kind in KINDS else kind)

    def require_authorization(self, contract):
        self.require_fresh_stage()
        if contract != self.contract:
            raise RuntimeError('detached_contract_changed')

    def set_write_authority(self, contract, mode):
        self.require_authorization(contract)
        if mode != 'READ_ONLY':
            raise RuntimeError('detached_normal_grant_forbidden')
        directory = self.root/'write-authority'
        directory.mkdir(mode=0o755)
        directory.chmod(0o755)
        atomic_json(directory/'authority.json', {'version':1,'schema':115,'release_sha':contract.sha,
            'contract_digest':digest(asdict(contract)),'mode':'READ_ONLY'})
        (directory/'authority.json').chmod(0o444)

    def require_free_destinations(self):
        names = self.command(['docker','ps','-a','--format','{{.Names}}']).splitlines()
        if any(self.name(kind) in names for kind in ('backend','frontend','parser',*KINDS)):
            raise RuntimeError('detached_resource_already_exists')
        networks = self.command(['docker','network','ls','--format','{{.Name}}']).splitlines()
        if self.network_name in networks:
            raise RuntimeError('detached_resource_already_exists')
        for port in (self.backend_port,self.frontend_port):
            with socket.socket() as listener:
                try:listener.bind(('127.0.0.1',port))
                except OSError:raise RuntimeError('detached_port_in_use') from None
        ids = self.command(['docker','ps','-aq']).splitlines()
        for row in json.loads(self.command(['docker','inspect',*ids])) if ids else []:
            for bindings in (row['HostConfig'].get('PortBindings') or {}).values():
                if any(str(binding.get('HostPort')) in {str(self.backend_port),str(self.frontend_port)} for binding in bindings or []):
                    raise RuntimeError('detached_port_already_reserved')

    def free_subnet(self):
        ids = self.command(['docker','network','ls','-q']).splitlines()
        rows = json.loads(self.command(['docker','network','inspect',*ids])) if ids else []
        occupied = [ipaddress.ip_network(item['Subnet']) for row in rows
            for item in row.get('IPAM',{}).get('Config') or [] if item.get('Subnet')]
        occupied += [ipaddress.ip_network(row['dst'], strict=False)
            for row in json.loads(self.command(['ip','-j','route'])) if row.get('dst') not in {None,'default'}]
        for subnet in ipaddress.ip_network('10.253.0.0/16').subnets(new_prefix=24):
            if not any(subnet.overlaps(other) for other in occupied if other.version == 4):return str(subnet)
        raise RuntimeError('detached_network_capacity_unavailable')

    def verify_image_source(self):
        for role,image in self.contract.images.items():
            row = json.loads(self.command(['docker','image','inspect',image]))[0]
            if (row['Id'] != image or row['Config'].get('Labels',{}).get('org.opencontainers.image.revision') != self.contract.sha):
                raise RuntimeError('detached_image_source_changed')

    def verify_retained_inputs(self):
        runtime = Runtime()
        observation, _ = verify(runtime)
        if observe_retained_inputs() != self.plan.retained_inputs:
            raise RuntimeError('detached_retained_input_changed')
        _, _, names, _ = identities(runtime.input_bytes())
        for role, name in names.items():
            row = observation['runtimes'][name]
            if self.plan.fallback[role] != {'container_id':row['id'],'image_id':row['image'],'spec_sha256':row['spec_sha256']}:
                raise RuntimeError('detached_registered_fallback_changed')

    def stage(self):
        self.require_authorization(self.contract)
        self.require_free_destinations()
        self.verify_image_source()
        # Verify pinned provider/fallback/fences once more immediately before
        # effects. No container rename, old authority or public route change.
        self.verify_retained_inputs()
        redis = self.inspect(self.redis_name)
        net = json.loads(self.command(['docker','network','inspect',self.redis_network]))[0]
        if (not redis['State']['Running'] or self.redis_network not in redis['NetworkSettings']['Networks']
                or redis['Config'].get('Labels',{}).get('com.madar.recovery.profile') != 'provider402-signin'
                or not net['Internal'] or net['Driver'] != 'bridge'
                or not any(m['Type']=='volume' and m['Destination']=='/data' for m in redis['Mounts'])):
            raise RuntimeError('detached_recovery_redis_unavailable')
        subnet = self.free_subnet()
        from deployment.lib.emergency_routing_repair import exclusive,encoded
        exclusive(self.root/'candidate-contract.json',encoded({'version':1,'plan_sha256':self.plan.digest,'contract':asdict(self.contract)}))
        self.set_write_authority(self.contract,'READ_ONLY')
        self.command(['docker','network','create','--driver','bridge','--subnet',subnet,self.network_name])
        self.command(['docker','run','--pull','never','-d','--name',self.name('parser'),'--network',self.network_name,
            '--network-alias','parser','--restart','no','--log-driver','none',
            '--env','PARSER_WORKER_HEALTH_HOST=0.0.0.0','--env','PARSER_WORKER_PORT=8000',
            '--env','DATA_UPLOAD_DIR=/tmp/local-parser',self.contract.images['backend'],'python','-m','workers.parser_worker'])
        self._create_application(self.contract,self.name('backend'),'backend',network=self.network_name,loopback_port=self.backend_port)
        self.command(['docker','start',self.name('backend')])
        cfg={'MADAR_CSP_CONNECT_SRC':"'self' https://api.madarportal.com",'MADAR_PUBLIC_SITE_DOMAIN':'madarportal.com','MADAR_HSTS':'max-age=31536000'}
        args=['docker','run','--pull','never','-d','--name',self.name('frontend'),'--network',self.network_name,
            '--restart','no','--log-driver','none','--publish',f'127.0.0.1:{self.frontend_port}:8080']
        for key in cfg:args += ['--env',key]
        self.command(args+[self.contract.images['frontend']],env={**cfg,'PATH':'/usr/bin:/bin'})
        for kind in KINDS:
            self._create_application(self.contract,self.name(kind),kind+'-worker',worker=kind,network=self.network_name)
        self.verify_identities()
        self.require_write_authority(self.contract,'READ_ONLY')
        rows = {kind:self.inspect(self.name(kind)) for kind in ("backend","frontend","parser",*KINDS)}
        record = {"version":1,"plan_sha256":self.plan.digest,"source_sha":self.contract.sha,
            "runtimes":{kind:{"id":row["Id"],"image":row["Image"],"spec_sha256":spec(row)} for kind,row in rows.items()},
            "loopback_ports":{"backend":self.backend_port,"frontend":self.frontend_port},
            "networks":{name:json.loads(self.command(["docker","network","inspect",name]))[0]["Id"]
                for name in (self.network_name,"madar-supabase-client",self.redis_network)},"mode":"READ_ONLY"}
        with (self.root/"candidate-identities.json").open("x") as output:
            os.fchmod(output.fileno(),0o600)
            json.dump(record,output,sort_keys=True);output.write("\n");output.flush();os.fsync(output.fileno())

    def verify_identities(self):
        for kind in ('backend','frontend','parser',*KINDS):
            row = self.inspect(self.name(kind))
            image = self.contract.images['frontend' if kind=='frontend' else 'backend']
            bindings = row['HostConfig'].get('PortBindings') or {}
            expected = ({'8000/tcp':[{'HostIp':'127.0.0.1','HostPort':str(self.backend_port)}]} if kind=='backend' else
                {'8080/tcp':[{'HostIp':'127.0.0.1','HostPort':str(self.frontend_port)}]} if kind=='frontend' else {})
            if (row['Image'] != image or row['HostConfig']['RestartPolicy']['Name'] != 'no'
                    or bindings != expected or row['State']['Running'] != (kind not in KINDS)):
                raise RuntimeError('detached_candidate_identity_changed')
            if kind in {'backend',*KINDS}:
                cfg = dict(item.split('=',1) for item in row['Config']['Env'])
                if (cfg.get('MADAR_RELEASE_SHA') != self.contract.sha
                        or cfg.get('MADAR_BUSINESS_WRITE_CONTRACT') != digest(asdict(self.contract))
                        or not any(m['Source']==str(self.root/'write-authority') and m['Destination']=='/run/madar/business-write-authority'
                            and not m['RW'] for m in row['Mounts'])):
                    raise RuntimeError('detached_candidate_authority_changed')

    def verify_recorded_runtime(self):
        record = json.loads(protected(self.root/'candidate-identities.json',private=True).read_text())
        if (record.get('version') != 1 or record.get('plan_sha256') != self.plan.digest
                or record.get('source_sha') != self.contract.sha or record.get('mode') != 'READ_ONLY'
                or record.get('loopback_ports') != {'backend':self.backend_port,'frontend':self.frontend_port}
                or set(record.get('runtimes',{})) != {'backend','frontend','parser',*KINDS}
                or set(record.get('networks',{})) != {self.network_name,'madar-supabase-client',self.redis_network}):
            raise RuntimeError('detached_identity_receipt_changed')
        for network,identifier in record['networks'].items():
            actual=json.loads(self.command(['docker','network','inspect',network]))[0]
            if actual['Id'] != identifier or actual['Driver'] != 'bridge':
                raise RuntimeError('detached_network_identity_changed')
        for kind,binding in record['runtimes'].items():
            row = self.inspect(self.name(kind))
            if binding != {'id':row['Id'],'image':row['Image'],'spec_sha256':spec(row)}:
                raise RuntimeError('detached_runtime_receipt_changed')
            expected = {self.network_name,'madar-supabase-client',self.redis_network} if kind in {'backend',*KINDS} else {self.network_name}
            attached=row['NetworkSettings']['Networks']
            if set(attached) != expected or any(attached[name]['NetworkID'] != record['networks'][name] for name in expected):
                raise RuntimeError('detached_network_attachment_changed')
            if kind in {'backend',*KINDS} and (('backend' if kind=='backend' else kind+'-worker') not in (attached[self.network_name].get('Aliases') or [])):
                raise RuntimeError('detached_network_role_changed')

    def endpoint(self, kind):
        if kind not in {'backend','frontend'}:raise RuntimeError('detached_endpoint_invalid')
        return 'http://127.0.0.1:'+str(self.backend_port if kind=='backend' else self.frontend_port)

    def health_json(self,url,*,allow_503=False):
        status,data=Runtime().fetch(url)
        if status in {502,504} or (status==503 and not allow_503):
            raise AvailabilityFailure('detached_http_pending')
        if status not in ({200,503} if allow_503 else {200}):
            raise RuntimeError('detached_http_status_invalid')
        value=json.loads(data)
        if not isinstance(value,dict):raise RuntimeError('detached_http_json_invalid')
        return status,value

    def verify_read_only(self):
        self.verify_recorded_runtime()
        self.verify_identities()
        self.require_write_authority(self.contract,'READ_ONLY')
        _, version = self.health_json(self.endpoint('backend')+'/health/version')
        _, ready = self.health_json(self.endpoint('backend')+'/health/ready',allow_503=True)
        _, fence = self.health_json(self.endpoint('backend')+'/health/recovery')
        if (version.get('release_sha') != self.contract.sha or version.get('release_slot') != self.slot
                or version.get('schema_compatible_min') != 115 or version.get('schema_compatible_max') != 115
                or fence != {'restricted':True,'business_writes_enabled':False}):
            raise RuntimeError('detached_read_only_binding_changed')
        pending = {'notification_worker','calendar_sync_worker','calendar_sync_queue','data_deletion_worker'}
        components = ready.get('components',{})
        if (not {'database','auth','schema','storage'}.issubset(components)
                or any(components[key] != 'ok' for key in ('database','auth','schema','storage'))
                or any(value not in {'ok','disabled','configured','not_required','development'} and key not in pending
                    for key,value in components.items())):
            raise RuntimeError('detached_read_only_unready')
        runtime = Runtime()
        runtime.denied(self.endpoint('backend'))
        runtime.http_status(self.endpoint('frontend')+'/')
        _, front_version = self.health_json(self.endpoint('frontend')+'/api/health/version')
        if front_version != version:raise RuntimeError('detached_frontend_backend_mismatch')
        runtime.denied(self.endpoint('frontend')+'/api')
        self.verify_identities()
        self.require_write_authority(self.contract,'READ_ONLY')
        self.verify_recorded_runtime()
