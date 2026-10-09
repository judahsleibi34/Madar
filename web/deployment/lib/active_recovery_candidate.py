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


def verify_lifecycle_networks(row, networks, primary, alias=None, *, created_worker=False):
    """A CREATED declaration is not a running endpoint; both bind exact objects."""
    attached=row['NetworkSettings']['Networks']
    if set(attached)!=set(networks):raise RuntimeError('network_attachment_changed')
    if created_worker:
        if row['State'].get('Status')!='created' or row['State']['Running']:
            raise RuntimeError('network_created_worker_phase_changed')
        if row['HostConfig'].get('NetworkMode')!=primary:
            raise RuntimeError('network_primary_changed')
        for name,value in attached.items():
            if value.get('NetworkID') not in ('',networks[name]) or value.get('EndpointID') or value.get('IPAddress'):
                raise RuntimeError('network_created_endpoint_changed')
    elif any(attached[name].get('NetworkID')!=networks[name] for name in networks):
        raise RuntimeError('network_attachment_changed')
    if alias is not None:
        if set(attached[primary].get('Aliases') or [])!={alias}:
            raise RuntimeError('network_role_changed')
        if any(attached[name].get('Aliases') for name in networks if name!=primary):
            raise RuntimeError('network_secondary_alias_changed')


def worker_spec_matches(row, expected, *, started_worker=False):
    """Docker first start changes only OomKillDisable false to null.

    Retain the original receipt hash. This is not a general spec normalization:
    only a governed business-worker lifecycle may compare the observed null to
    the originally recorded false; true and every other alteration still fail.
    """
    if spec(row)==expected:return True
    if not started_worker or row['HostConfig'].get('OomKillDisable',False) is not None:return False
    previous=dict(row,HostConfig=dict(row['HostConfig'],OomKillDisable=False))
    return spec(previous)==expected


def inspect_previous_candidate(plan, runtime=None):
    """Bind a pre-publication failed candidate as data, never reused authority."""
    binding=(plan.candidate_destination or {}).get('previous_candidate')
    if binding is None:return None
    runtime=runtime or Runtime();root=ROOT/binding['plan_sha256']
    names=('authorization.json','plan.json','events.jsonl','candidate-contract.json','candidate-identities.json')
    paths={name:protected(root/name,private=True) for name in names}
    paths['write-authority/authority.json']=protected(root/'write-authority/authority.json',private=False)
    hashes={name:file_digest(path) for name,path in paths.items()}
    if hashes['plan.json']!=binding['plan_sha256'] or digest(hashes)!=binding['evidence_sha256']:
        raise RuntimeError('previous_candidate_evidence_changed')
    from deployment.lib.active_recovery_resumption import ResumptionPlan
    previous=ResumptionPlan(**json.loads(paths['plan.json'].read_text()));previous.validate()
    receipt=json.loads(paths['authorization.json'].read_text())
    events=[json.loads(line) for line in paths['events.jsonl'].read_text().splitlines()]
    if (previous.digest!=binding['plan_sha256'] or previous.digest==plan.digest
            or receipt.get('operation')!='active-local-rollback-resumption'
            or receipt.get('plan_sha256')!=previous.digest
            or receipt.get('source_bundle_sha256')!=previous.source_bundle_sha256
            or previous.retained_inputs!=plan.retained_inputs or previous.fallback!=plan.fallback
            or [row.get('phase') for row in events]!=['authorized','detached_candidate_pending','detached_candidate_failed']
            or any(row.get('plan_sha256')!=previous.digest for row in events)
            or any((root/name).exists() for name in ('installed-controller.json','worker-owner.json','boot-installation.json','upstream-preimage.conf'))):
        raise RuntimeError('previous_candidate_not_prepublication_failure')
    value=DetachedRecoveryCandidate.from_saved_runtime(previous,root,lambda:None)
    value.verify_recorded_runtime();value.require_write_authority(value.contract,'READ_ONLY')
    rows={kind:value.inspect(value.name(kind)) for kind in ('backend','frontend','parser',*KINDS)}
    for kind,row in rows.items():
        if (row['Image']!=previous.candidate_images['frontend' if kind=='frontend' else 'backend']
                or row['HostConfig']['RestartPolicy']['Name']!='no'
                or (kind in KINDS and (row['State'].get('Status')!='created' or row['State']['Running']))
                or (kind not in KINDS and row['State'].get('Status') not in ('running','exited'))):
            raise RuntimeError('previous_candidate_lifecycle_changed')
        if kind in ('backend','frontend'):
            port={'backend':value.backend_port,'frontend':value.frontend_port}[kind]
            container_port={'backend':'8000/tcp','frontend':'8080/tcp'}[kind]
            if row['HostConfig'].get('PortBindings')!={container_port:[{'HostIp':'127.0.0.1','HostPort':str(port)}]}:
                raise RuntimeError('previous_candidate_port_changed')
            if row['State']['Running']:
                _,version=value.health_json(value.endpoint(kind)+('/api' if kind=='frontend' else '')+'/health/version')
                _,fence=value.health_json(value.endpoint(kind)+('/api' if kind=='frontend' else '')+'/health/recovery')
                if version.get('release_sha')!=previous.source_sha or fence!={'restricted':True,'business_writes_enabled':False}:
                    raise RuntimeError('previous_candidate_endpoint_changed')
    return {'root':root,'candidate':value,'rows':rows,'binding':binding}


def require_unreserved_ports(runtime, ports, retired=None, planned=None):
    """Check host sockets AND stopped Docker reservations without displacing any."""
    planned=planned or {}
    planned_ports={str(b['HostPort']) for row in planned.values() if row['State']['Running'] for values in (row['HostConfig'].get('PortBindings') or {}).values() for b in values or []}
    for port in ports:
        if str(port) in planned_ports:continue
        with socket.socket() as listener:
            # Match Docker's listener semantics: TIME_WAIT is not a live owner.
            # No SO_REUSEPORT; bind+listen still rejects a competing listener.
            listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            try:
                listener.bind(('127.0.0.1',port))
                listener.listen(1)
            except OSError as error:
                raise RuntimeError('detached_port_unavailable_'+str(port)+'_errno_'+str(error.errno)) from None
    retired=retired or {}
    ids=runtime.command(['docker','ps','-aq']).splitlines()
    for row in json.loads(runtime.command(['docker','inspect',*ids])) if ids else []:
        for bindings in (row['HostConfig'].get('PortBindings') or {}).values():
            if any(str(b.get('HostPort')) in {str(p) for p in ports} for b in bindings or []):
                binding=retired.get(row.get('Name','').lstrip('/'))
                if (binding is None or row['Id']!=binding['container_id'] or row['Image']!=binding['image_id']
                        or spec(row)!=binding['spec_sha256'] or (row['State']['Running'] and row['Id'] not in planned)
                        or row['HostConfig']['RestartPolicy']['Name']!='no'):
                    raise RuntimeError('detached_port_already_reserved')


def resolve_candidate_destination(plan, runtime=None):
    """Observe current ownership/identities; never use historical origin_slot as allocation."""
    from deployment.lib.active_recovery_inputs import INPUTS,observe_runtime_dependencies
    from deployment.lib.provider_recovery_runtime import readonly_configuration
    runtime=runtime or Runtime()
    compensated=(plan.candidate_destination or {}).get('post_compensation')
    if compensated:
        from deployment.lib.active_recovery_compensated import resolve_compensated_destination
        return resolve_compensated_destination(compensated,runtime)
    packet,binding=observe_runtime_dependencies(runtime)
    if binding!=plan.retained_inputs['runtime_dependencies']:
        raise RuntimeError('detached_destination_runtime_changed')
    values={}
    for key in ('worker_authority','release_state','traffic','recovery_transaction','local_transaction'):
        path=INPUTS[key]
        reader=protected if key=='local_transaction' else readonly_configuration
        if file_digest(reader(path,private=True))!=plan.retained_inputs[key]:
            raise RuntimeError('detached_destination_ownership_changed')
        values[key]=json.loads(path.read_text())
    owner=values['worker_authority'];traffic=values['traffic'];recovery=values['recovery_transaction'];local=values['local_transaction']
    retained=owner.get('candidate',{}).get('slot')
    recovery_sha=traffic.get('sha')
    if (owner.get('owner')!='RECOVERY' or retained not in {'blue','green'}
            or owner.get('candidate',{}).get('sha')!=recovery_sha
            or recovery.get('slot')!=retained or recovery.get('sha')!=recovery_sha
            or local.get('sha')!=recovery_sha
            or any(v.get('phase')!='local_rollback_active' for v in (recovery,local))
            or traffic.get('slot')!='local-fallback' or traffic.get('provider')!='local'
            or traffic.get('schema')!=115 or traffic.get('database_restore') is not False):
        raise RuntimeError('detached_destination_recovery_ownership_invalid')
    known=values['release_state'].get('known_good_release',{})
    if known.get('schema')!=115 or known.get('slot')!=owner.get('old',{}).get('slot') or known.get('sha')!=owner.get('old',{}).get('sha'):
        raise RuntimeError('detached_destination_release_identity_invalid')
    slot='green' if retained=='blue' else 'blue'
    names=[f'madar-{slot}-{kind}' for kind in ('backend','frontend',*(k+'-worker' for k in KINDS))]
    rows=runtime.inspect(names+[f'madar-{retained}-backend',f'madar-{retained}-frontend'])
    for name,row in rows.items():
        bound=packet['runtimes'][name]
        if row['Id']!=bound['container_id'] or row['Image']!=bound['image_id'] or spec(row)!=bound['spec_sha256']:
            raise RuntimeError('detached_destination_runtime_changed')
    for name in names:
        row=rows[name]
        if (row['State']['Running'] or row['HostConfig']['RestartPolicy']['Name']!='no'
                or row['Config'].get('Labels',{}).get('org.opencontainers.image.revision')!=recovery_sha):
            raise RuntimeError('detached_destination_retained_slot_invalid')
    sources={rows[f'madar-{retained}-{role}']['Config'].get('Labels',{}).get('org.opencontainers.image.revision') for role in ('backend','frontend')}
    if len(sources)!=1 or not next(iter(sources)):
        raise RuntimeError('detached_destination_retained_writer_invalid')
    _,_,fallback,_=identities(runtime.input_bytes())
    prefix=fallback['backend'].removesuffix('-local-fallback-backend')
    redis_name=prefix+'-redis';network=prefix+'-'+retained+'-runtime'
    redis=runtime.inspect([redis_name])[redis_name];net=runtime.network(network)
    if (not redis['State']['Running'] or network not in redis['NetworkSettings']['Networks']
            or redis['Config'].get('Labels',{}).get('com.madar.recovery.profile')!='provider402-signin'
            or not any(m['Type']=='volume' and m['Destination']=='/data' for m in redis['Mounts'])
            or net['Name']!=network or net['Id']!=packet['networks'][network]['Id']
            or net['Driver']!='bridge' or net['Internal'] is not True
            or network not in packet['runtimes'][f'madar-{slot}-backend']['networks']):
        raise RuntimeError('detached_destination_redis_network_invalid')
    ports={'blue':(8101,3100),'green':(8201,3200)}[slot]
    # Previous governed normal-local preparation already retired these exact
    # known-good containers. Their stopped declarations are not live listeners.
    # No other stopped reservation is permitted; none is modified or started.
    retired={};all_names=runtime.command(['docker','ps','-a','--format','{{.Names}}']).splitlines()
    suffix=local.get('contract_digest','')[:12]
    for role,port in zip(('backend','frontend'),ports):
        name=f'madar-{slot}-{role}-legacy-'+suffix
        if name not in all_names:continue
        old_contract=protected(INPUTS['local_contract'],private=True)
        if file_digest(old_contract)!=plan.retained_inputs['local_contract'] or digest(json.loads(old_contract.read_text()))!=local.get('contract_digest'):
            raise RuntimeError('detached_retirement_contract_changed')
        row=runtime.inspect([name])[name]
        container_port={'backend':'8000/tcp','frontend':'8080/tcp'}[role]
        expected_ports={container_port:[{'HostIp':'127.0.0.1','HostPort':str(port)}]}
        image=known.get('images',{}).get(role,'').split('@')[-1]
        if (known.get('slot')!=slot or row['Image']!=image
                or row['Config'].get('Labels',{}).get('org.opencontainers.image.revision')!=known['sha']
                or row['State']['Running'] or row['HostConfig']['RestartPolicy']['Name']!='no'
                or row['HostConfig'].get('PortBindings')!=expected_ports):
            raise RuntimeError('detached_retired_port_declaration_invalid')
        retired[name]={'container_id':row['Id'],'image_id':row['Image'],'spec_sha256':spec(row)}
    previous=inspect_previous_candidate(plan,runtime)
    planned={}
    if previous:
        if previous['candidate'].slot!=slot:raise RuntimeError('previous_candidate_slot_changed')
        for role in ('backend','frontend'):
            row=previous['rows'][role];planned[row['Id']]=row
            retired[row['Name'].lstrip('/')]={'container_id':row['Id'],'image_id':row['Image'],'spec_sha256':spec(row)}
    require_unreserved_ports(runtime,ports,retired,planned)
    probe=DetachedRecoveryCandidate.__new__(DetachedRecoveryCandidate);probe.command=runtime.command
    destination={'slot':slot,'backend_port':ports[0],'frontend_port':ports[1],
        'retained_slot':retained,'retained_source_sha':next(iter(sources)),
        'redis_name':redis_name,'redis_network':network,'redis_network_id':net['Id'],'subnet':probe.free_subnet(),'retired_port_declarations':retired}
    if previous:destination['previous_candidate']=previous['binding']
    return destination


class DetachedRecoveryCandidate(ProductionLocalTransitionOperations):
    def __init__(self, plan, contract, root):
        plan.validate()
        self.plan, self.contract, self.root = plan, contract, Path(root)
        self.require_fresh_stage()
        self._configure(plan,contract,root)

    def _configure(self,plan,contract,root):
        if (contract.sha != plan.source_sha or contract.images != plan.candidate_images
                or contract.checkpoint_digest != plan.checkpoint_manifest_sha256
                or contract.reconciliation_digest != plan.reconciliation_execution_sha256
                or contract.evidence_digest != plan.acceptance_execution_sha256):
            raise RuntimeError('detached_candidate_contract_changed')
        # Runtime identity, rather than historical PASS claims, determines the
        # registered fallback and its private configuration namespace.
        runtime = Runtime()
        compensated=(plan.candidate_destination or {}).get('post_compensation')
        if compensated:
            from deployment.lib.active_recovery_compensated import verify_compensated_binding, inspect_history
            from deployment.lib.active_recovery_fallback import CurrentDataFallback
            from deployment.lib.active_recovery_inputs import registered_fallback_names
            verify_compensated_binding(compensated,runtime)
            previous,previous_root,_,_=inspect_history(compensated['baseline']['previous_plan_sha256'])
            CurrentDataFallback(previous,previous_root,runtime=runtime).verify(backup_preparation='pre_grant_backup' in compensated)
        else:verify(runtime)
        inputs = runtime.input_bytes()
        old = RecoveryContract(**json.loads(inputs['recovery_contract']))
        if contract.recovery_context != digest(asdict(old)):
            raise RuntimeError('detached_recovery_context_changed')
        names=registered_fallback_names(runtime) if compensated else identities(inputs)[2]
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
        destination=resolve_candidate_destination(plan,runtime)
        if destination!=plan.candidate_destination:raise RuntimeError('detached_destination_plan_changed')
        self.slot=destination['slot'];self.redis_name=destination['redis_name'];self.redis_network=destination['redis_network']
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
        destination=plan.candidate_destination
        if destination is None:raise RuntimeError('saved_candidate_destination_missing')
        slot=destination['slot']
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
        value.state=value.recovery.paths.state;value.redis_name=destination['redis_name'];value.redis_network=destination['redis_network']
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
        archives={f'madar-{self.slot}-'+(kind+'-worker' if kind in KINDS else kind)+'-retired-'+self.plan.digest[:12] for kind in ('backend','frontend',*KINDS)}
        if archives.intersection(names) or any(self.name(kind) in names for kind in ('backend','frontend','parser',*KINDS)):
            raise RuntimeError('detached_resource_already_exists')
        networks = self.command(['docker','network','ls','--format','{{.Name}}']).splitlines()
        if self.network_name in networks:
            raise RuntimeError('detached_resource_already_exists')
        previous=inspect_previous_candidate(self.plan)
        planned={row['Id']:row for kind,row in previous['rows'].items() if kind in ('backend','frontend')} if previous else {}
        require_unreserved_ports(self,(self.backend_port,self.frontend_port),(self.plan.candidate_destination or {}).get('retired_port_declarations',{}),planned)

    @classmethod
    def read_only_feasibility(cls,plan,contract,root):
        value=cls.__new__(cls);value.plan=plan;value.contract=contract;value.root=Path(root)
        value._configure(plan,contract,root)
        value.require_feasible();value.verify_image_source();value.verify_retained_inputs()
        return dict(plan.candidate_destination)

    def require_feasible(self):
        self.require_free_destinations()
        if resolve_candidate_destination(self.plan)!=self.plan.candidate_destination:
            raise RuntimeError('detached_destination_plan_changed')
        if (self.slot!=self.plan.candidate_destination['slot']
                or self.backend_port!=self.plan.candidate_destination['backend_port']
                or self.frontend_port!=self.plan.candidate_destination['frontend_port']):
            raise RuntimeError('detached_destination_object_changed')

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
        compensated=(self.plan.candidate_destination or {}).get('post_compensation')
        if compensated:
            from deployment.lib.active_recovery_compensated import verify_compensated_binding
            saved=self.root/'candidate-identities.json'
            verify_compensated_binding(compensated,runtime,staged_plan=self.plan if saved.exists() else None)
        else:
            observation, _ = verify(runtime)
            _, _, names, _ = identities(runtime.input_bytes())
            for role, name in names.items():
                row = observation['runtimes'][name]
                if self.plan.fallback[role] != {'container_id':row['id'],'image_id':row['image'],'spec_sha256':row['spec_sha256']}:
                    raise RuntimeError('detached_registered_fallback_changed')
        if observe_retained_inputs(post_compensation=bool(compensated)) != self.plan.retained_inputs:
            raise RuntimeError('detached_retained_input_changed')

    def staging_check(self, operation, callback, *args, **kwargs):
        """Attach a source-defined operation name; never store command/secret text."""
        try:return callback(*args,**kwargs)
        except Exception as error:
            if not hasattr(error,'madar_staging_operation'):error.madar_staging_operation=operation
            raise

    def retire_previous_candidate(self):
        """Fresh approval may stop only exact unpublished READ_ONLY services."""
        self.require_authorization(self.contract)
        previous=self.staging_check('retirement-identities',inspect_previous_candidate,self.plan)
        if previous is None:return
        from deployment.lib.emergency_routing_repair import exclusive,encoded
        selected={kind:previous['rows'][kind]['Id'] for kind in ('frontend','backend','parser')}
        exclusive(self.root/'previous-candidate-retirement.json',encoded({'plan_sha256':self.plan.digest,
            'previous_candidate':previous['binding'],'stopped_ids':selected}))
        for kind,identity in selected.items():
            # Never update configuration, remove resources or touch the three
            # CREATED business workers. Stop only the freshly bound exact IDs.
            self.require_authorization(self.contract)
            self.staging_check('retirement-identities',inspect_previous_candidate,self.plan)
            self.staging_check('retirement-stop-'+kind,self.command,['docker','stop',identity])
            if self.inspect(identity)['State']['Running']:raise RuntimeError('previous_candidate_stop_failed')
        self.staging_check('post-retirement-identities',inspect_previous_candidate,self.plan)
        self.staging_check('post-retirement-ports',require_unreserved_ports,self,(self.backend_port,self.frontend_port),self.plan.candidate_destination['retired_port_declarations'])

    def stage(self):
        self.require_authorization(self.contract)
        self.staging_check('candidate-feasibility',self.require_feasible)
        self.staging_check('candidate-images',self.verify_image_source)
        # Verify pinned provider/fallback/fences once more immediately before
        # effects. No container rename, old authority or public route change.
        self.staging_check('retained-inputs',self.verify_retained_inputs)
        self.staging_check('previous-candidate-retirement',self.retire_previous_candidate)
        redis = self.inspect(self.redis_name)
        net = json.loads(self.command(['docker','network','inspect',self.redis_network]))[0]
        if (not redis['State']['Running'] or self.redis_network not in redis['NetworkSettings']['Networks']
                or redis['Config'].get('Labels',{}).get('com.madar.recovery.profile') != 'provider402-signin'
                or not net['Internal'] or net['Driver'] != 'bridge'
                or not any(m['Type']=='volume' and m['Destination']=='/data' for m in redis['Mounts'])):
            raise RuntimeError('detached_recovery_redis_unavailable')
        subnet = self.plan.candidate_destination['subnet']
        from deployment.lib.emergency_routing_repair import exclusive,encoded
        exclusive(self.root/'candidate-contract.json',encoded({'version':1,'plan_sha256':self.plan.digest,'contract':asdict(self.contract)}))
        self.set_write_authority(self.contract,'READ_ONLY')
        self.staging_check('candidate-network-create',self.command,['docker','network','create','--driver','bridge','--subnet',subnet,self.network_name])
        self.staging_check('candidate-parser-create',self.command,['docker','run','--pull','never','-d','--name',self.name('parser'),'--network',self.network_name,
            '--network-alias','parser','--restart','no','--log-driver','none',
            '--env','PARSER_WORKER_HEALTH_HOST=0.0.0.0','--env','PARSER_WORKER_PORT=8000',
            '--env','DATA_UPLOAD_DIR=/tmp/local-parser',self.contract.images['backend'],'python','-m','workers.parser_worker'])
        self.staging_check('candidate-backend-create',self._create_application,self.contract,self.name('backend'),'backend',network=self.network_name,loopback_port=self.backend_port)
        self.staging_check('candidate-backend-start',self.command,['docker','start',self.name('backend')])
        cfg={'MADAR_CSP_CONNECT_SRC':"'self' https://api.madarportal.com",'MADAR_PUBLIC_SITE_DOMAIN':'madarportal.com','MADAR_HSTS':'max-age=31536000'}
        args=['docker','run','--pull','never','-d','--name',self.name('frontend'),'--network',self.network_name,
            '--restart','no','--log-driver','none','--publish',f'127.0.0.1:{self.frontend_port}:8080']
        for key in cfg:args += ['--env',key]
        self.staging_check('candidate-frontend-create',self.command,args+[self.contract.images['frontend']],env={**cfg,'PATH':'/usr/bin:/bin'})
        for kind in KINDS:
            self.staging_check('candidate-'+kind+'-create',self._create_application,self.contract,self.name(kind),kind+'-worker',worker=kind,network=self.network_name)
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
            verify_lifecycle_networks(row,{name:record['networks'][name] for name in expected},self.network_name,
                ('backend' if kind=='backend' else kind+'-worker') if kind in {'backend',*KINDS} else None,
                created_worker=kind in KINDS)

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
