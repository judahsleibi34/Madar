"""Durable boot dispatch for one approved completed-NORMAL upgrade.

Original115 recovery is permitted only before handoff at native115. Once an
accepted candidate owns workers, reboot selects that exact compatible runtime
or maintenance. It never starts the historical115-only fallback after SQL.
"""
import json
import os
import re
from pathlib import Path
import sys
from types import SimpleNamespace

from deployment.lib.completed_normal_admission import ADMISSIONS,OPERATION,digest,encoded,validate_contract,verify_history,require_candidate_authority
from deployment.lib.completed_normal_boot_installation import CompletedNormalBootInstallation
from deployment.lib.completed_normal_database import observe_native,require_normal_migration_boundary
from deployment.lib.completed_normal_write_handoff import atomic_public_authority
from deployment.lib.compatible_normal_boot import CompatibleNormalBoot,WORKERS
from deployment.lib.control_plane_upgrade import SystemOperations
from deployment.lib.active_recovery_inputs import INPUTS,controller_tree_digest
from deployment.lib.emergency_routing_repair import Runtime,MAINTENANCE,verification_window,AvailabilityFailure
from deployment.lib.provider_recovery_runtime import protected,readonly_configuration
from deployment.lib.runtime_authority import runtime_mutation_lock,load_worker_authority
from deployment.lib.completed_normal_profile import profile, LEGACY, MANUAL, APPLICATION, expected_origin_grant

CONFIGURATIONS={key:(INPUTS[key],key in {'production_configuration','backup_configuration','native_configuration'})
    for key in ('production_configuration','backup_configuration','native_configuration','native_compose','native_override',
                'gateway_bootstrap','gateway_cds','gateway_lds')}
CONFIGURATIONS['node1_configuration']=(Path('/etc/madar/node1-backup.env'),True)
HISTORICAL_CONFIGURATIONS={key:CONFIGURATIONS[key] for key in
    ('production_configuration','backup_configuration','node1_configuration')}
HISTORICAL_CONFIGURATIONS['database_transport']=(Path('/etc/madar/automatic-database.dsn'),True)


def configuration_names(document):
    """Input shape only; authentic observations are required below."""
    contract=document.get('admission_contract',{})
    if not isinstance(contract,dict) or not isinstance(contract.get('source_roles',{}),dict):
        raise RuntimeError('completed_upgrade_configuration_contract_invalid')
    if contract.get('source_roles',{}).get('origin_kind')=='independently-enrolled-historical-bootstrap-origin':
        return {*HISTORICAL_CONFIGURATIONS,'original_provider_configurations'}
    return set(CONFIGURATIONS)

def verify_live_configuration(document):
    """Hash independently measured configuration, never record its contents."""
    from deployment.lib.provider_recovery_runtime import file_digest
    expected=document.get('live_configuration_sha256')
    if (not isinstance(expected,dict) or set(expected)!=configuration_names(document)
            or any(not re.fullmatch('[0-9a-f]{64}',str(h)) for h in expected.values())):
        raise RuntimeError('completed_upgrade_configuration_contract_invalid')
    selected=CONFIGURATIONS
    if 'original_provider_configurations' in expected:
        from deployment.lib.historical_origin import recorded_observation,verify_provider_configurations
        from deployment.lib.completed_normal_admission import validate_provider_preparation
        from deployment.lib.completed_normal_profile import RECONCILED
        contract=document['admission_contract']
        if validate_provider_preparation(dict(contract,plan_sha256=contract.get('plan_sha256','0'*64))) is not RECONCILED:
            raise RuntimeError('completed_upgrade_historical_configuration_profile_invalid')
        binding=contract['source_roles'];original=recorded_observation(binding)
        for key,name in (('production_configuration','application'),('backup_configuration','backup'),('database_transport','database_transport')):
            if expected[key]!=original['configuration_sha256'][name]:
                raise RuntimeError('completed_upgrade_historical_configuration_changed')
        if verify_provider_configurations(binding)!=expected['original_provider_configurations']:
            raise RuntimeError('completed_upgrade_historical_configuration_changed')
        selected=HISTORICAL_CONFIGURATIONS
    for key,(path,private) in selected.items():
        if file_digest(readonly_configuration(path,private=private))!=expected[key]:
            raise RuntimeError('completed_upgrade_configuration_changed')

class CompletedNormalBootActor:
    def __init__(self,document,package,measure, *, runtime=None,operations=None):
        if not callable(measure):raise RuntimeError('completed_upgrade_boot_measurement_required')
        if 'plan_sha256' in document['admission_contract']:
            raise RuntimeError('completed_upgrade_boot_circular_contract_invalid')
        self.document,self.package,self.measure=document,Path(package),measure
        self.contract=dict(document['admission_contract'],plan_sha256=digest(document));validate_contract(self.contract)
        self.profile=profile(self.contract)
        if self.contract['candidate']['controller_sha']!=document['controller_source_sha']:
            raise RuntimeError('completed_upgrade_boot_controller_role_changed')
        self.root=ADMISSIONS/digest(self.contract)
        self.runtime=runtime or Runtime();self.ops=operations or SystemOperations()
        self.runtime.expected_nginx_sha256=document['proxy_nginx_sha256']
        self.installation=CompletedNormalBootInstallation(self.contract,document,self.package,self.source,self.ops)
    def source(self):
        measured,source=self.measure()
        if measured!=self.document or os.geteuid()!=0:
            raise RuntimeError('completed_upgrade_boot_source_binding_changed')
        verify_live_configuration(self.document)
        locations={str(p) for p in source.rglob('*.py')}
        bare_helpers={p.stem for p in (source/'web/deployment/lib').glob('*.py')}
        for name,module in list(sys.modules.items()):
            if name in {'deployment','scripts'} or name in bare_helpers or name.startswith(('deployment.','scripts.')):
                location=getattr(module,'__file__',None)
                if location is not None and str(Path(location).absolute()) not in locations:
                    raise RuntimeError('completed_upgrade_boot_foreign_import')
        authorization=json.loads(protected(self.root/'operator-authorization.json',private=True).read_text())
        expected={'operation':self.profile.operation,'context_sha256':digest(self.contract),'plan_sha256':digest(self.document),
            'source_bundle_sha256':self.document['source_bundle_sha256'],
            'controller_sha':self.contract['candidate']['controller_sha'],'application_sha':self.contract['candidate']['source_sha']}
        if authorization!=expected:raise RuntimeError('completed_upgrade_boot_durable_authorization_changed')
        current=protected(INPUTS['controller']).read_text().strip();tree=controller_tree_digest()
        candidate=self.contract['candidate'];origin=self.contract['source_roles']
        if current==candidate['controller_sha']:
            same_origin=current==origin['controller_sha']
            if (tree!=candidate['controller_tree_sha256']
                    or same_origin and tree!=self.document['installed_controller_tree_sha256']):
                raise RuntimeError('completed_upgrade_boot_installed_tree_changed')
            intent_path=self.root/'controller-installation-intent.json'
            intent_present=intent_path.exists() or intent_path.is_symlink()
            advanced=any((self.root/name).exists() or (self.root/name).is_symlink()
                for name in ('candidate-runtime.json','migration-intent.json'))
            # The same independently measured controller may already be the
            # target before boot supersession. Its future installation intent
            # cannot be required here or synthesized as historical evidence.
            if not same_origin or intent_present or advanced:
                if not intent_present:raise RuntimeError('completed_upgrade_boot_controller_installation_changed')
                intent=json.loads(protected(intent_path,private=True).read_text())
                if intent!={'operation':self.profile.operation,'context_sha256':digest(self.contract),
                    'from_controller':origin['controller_sha'],'to_controller':candidate['controller_sha'],
                    'old_tree_sha256':self.document['installed_controller_tree_sha256'],
                    'new_tree_sha256':candidate['controller_tree_sha256']}:
                    raise RuntimeError('completed_upgrade_boot_controller_installation_changed')
        elif (current!=origin['controller_sha'] or tree!=self.document['installed_controller_tree_sha256']
                or (self.root/'candidate-runtime.json').exists() or (self.root/'migration-intent.json').exists()):
            raise RuntimeError('completed_upgrade_boot_controller_identity_changed')
        if self.ops.repository_head()!=current:
            raise RuntimeError('completed_upgrade_boot_checkout_role_changed')
    def guard(self):
        self.source();verify_history(self.contract)
        admission=json.loads(protected(self.root/'admission.json').read_text())
        if admission.get('operation')!=self.profile.operation or admission.get('contract')!=self.contract:
            raise RuntimeError('completed_upgrade_boot_admission_changed')
        self.installation.installed()
    def event(self,phase,**fields):
        # Fixed caller fields only; exception messages, configs and HTTP bodies
        # are never placed in the protected audit. Original audit is untouched.
        if set(fields)-{'exception_type','mode','schema'}:
            raise RuntimeError('completed_upgrade_boot_audit_fields_invalid')
        path=self.root/'boot-events.jsonl'
        if path.exists():protected(path,private=True)
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(encoded({'operation':self.profile.operation,'context_sha256':digest(self.contract),'phase':phase,**fields}).replace(b'\n',b'')+b'\n')
            stream.flush();os.fsync(stream.fileno())
    def native(self):return observe_native(self.contract,self.runtime,allow_pending=True)
    def candidate(self, *, compensation_leaf=False):
        return CompatibleNormalBoot(self.contract,source_guard=self.guard,native_verifier=self.native,
            publish_authority=self.publish,compensate_current_data=self.maintenance if compensation_leaf else self.compensate,runtime=self.runtime,
            publication_name='normal-publication.json' if (self.root/'normal-publication.json').exists() else 'candidate-runtime.json')
    def publish(self,mode):
        self.guard()
        value=require_candidate_authority(self.contract)
        atomic_public_authority(self.root/'write-authority/authority.json',dict(value,mode=mode))
        require_candidate_authority(self.contract,mode=mode)
    def origin(self):
        if self.profile is not LEGACY:
            # A separately authorized maintenance transition never delegates
            # to the historical136 actor after installing its replacement.
            raise RuntimeError('completed_upgrade_manual_origin_restart_forbidden')
        # New measured code executes; the old frozen package is historical DATA.
        from deployment.lib.active_recovery_resumption import load_saved_resumption_plan
        from deployment.lib.completed_normal_baseline import historical_source,bind_origin_specification_verifiers
        from deployment.lib.active_recovery_boot_actor import ActiveRecoveryBootActor
        from deployment.lib.active_recovery_boot import ActiveRecoveryNormalBoot
        roles=self.contract['source_roles'];old_root=Path(roles['completion_root'])
        plan=load_saved_resumption_plan(old_root)
        def source():
            self.guard()
            return historical_source(plan)
        actor=ActiveRecoveryBootActor(plan,old_root,
            Path('/var/lib/madar-control-plane/normal-local-preparation')/('normal-source-'+plan.source_bundle_sha256),
            source=SimpleNamespace(verify=source),audit=lambda stage,**kw:self.event('origin_'+stage,
                **{key:value for key,value in kw.items() if key in {'exception_type','mode','schema'}}))
        actor.assemble()
        bind_origin_specification_verifiers(actor)
        def completion():
            self.guard()
            if (self.root/'candidate-runtime.json').exists() or (self.root/'migration-intent.json').exists():
                raise RuntimeError('completed_upgrade_boot_origin_schema_boundary_invalid')
            owner=load_worker_authority(Path('/var/lib/madar/releases'))
            if (owner is None or owner['generation']!=self.contract['origin']['worker_generation']
                    or owner['owner']!='CANDIDATE' or owner['candidate']!={'sha':roles['application_sha'],'slot':self.contract['origin']['slot']}):
                raise RuntimeError('completed_upgrade_boot_origin_worker_owner_changed')
        def native():
            completion()
            if self.native()!=115:raise RuntimeError('completed_upgrade_boot_origin_schema_boundary_invalid')
        actor.completed_evidence=completion
        actor.native=native
        return actor,ActiveRecoveryNormalBoot(plan,old_root,actor.candidate,actor.kernel,self.guard,
            completion,native,self.compensate,runtime=self.runtime,audit=actor.audit)
    def compensate(self):
        # Revocation precedes readiness/audit; current customer data is retained.
        failures=[]
        try:
            value=require_candidate_authority(self.contract)
            atomic_public_authority(self.root/'write-authority/authority.json',dict(value,mode='READ_ONLY'))
        except Exception as error:failures.append(type(error).__name__)
        try:
            if self.contract['source_roles'].get('origin_kind')!='independently-enrolled-historical-bootstrap-origin':
                root=Path(self.contract['source_roles']['completion_root'])
                value=json.loads(protected(root/'write-authority/authority.json').read_text())
                expected=expected_origin_grant(self.contract,'READ_ONLY');expected.pop('mode')
                if {k:v for k,v in value.items() if k!='mode'}!=expected or value.get('mode') not in {'READ_ONLY','NORMAL'}:
                    raise RuntimeError('completed_upgrade_boot_origin_authority_changed')
                atomic_public_authority(root/'write-authority/authority.json',dict(value,mode='READ_ONLY'))
        except Exception as error:failures.append(type(error).__name__)
        try:
            self.event('compensation_pending')
        except OSError:pass
        # A verified READ_ONLY bridge is the forward-repair target. It may stay
        # available without ever regranting writes or restarting the origin.
        from deployment.lib.completed_normal_profile import DELETION, RECONCILED
        if self.profile not in (DELETION, RECONCILED) and not failures and (self.root/'candidate-runtime.json').exists():
            try:
                self.candidate(compensation_leaf=True).execute_read_only()
                self.publish_restricted_bridge()
                self.event('restricted_bridge_verified',mode='READ_ONLY',schema=self.native())
                return
            except Exception as error:failures.append(type(error).__name__)
        self.maintenance()
    def proxy_identity(self):
        from deployment.lib.completed_normal_resources import measured_spec_matches
        expected=self.document.get('proxy_runtime')
        if (not isinstance(expected,dict) or set(expected)!={'id','image','spec_sha256'}
                or not re.fullmatch('[a-f0-9]{64}',str(expected.get('id')))
                or not re.fullmatch('sha256:[a-f0-9]{64}',str(expected.get('image')))
                or not re.fullmatch('[a-f0-9]{64}',str(expected.get('spec_sha256')))):
            raise RuntimeError('completed_upgrade_boot_proxy_binding_missing_or_invalid')
        rows=self.runtime.inspect([expected['id']])
        row=next(iter(rows.values())) if len(rows)==1 else None
        if (row is None or row['Id']!=expected['id'] or row['Image']!=expected['image']
                or not measured_spec_matches(row,expected['spec_sha256'])):
            raise RuntimeError('completed_upgrade_boot_proxy_identity_changed')
        return row
    def publish_restricted_bridge(self):
        import time
        from deployment.lib.emergency_routing_repair import UPSTREAM
        self.guard();self.proxy_identity()
        slot=self.contract['candidate']['slot']
        route=(f'upstream madar_backend_active {{ server 127.0.0.1:{8101 if slot=="blue" else 8201}; }}\n'
            f'upstream madar_frontend_active {{ server 127.0.0.1:{3100 if slot=="blue" else 3200}; }}\n').encode()
        with verification_window(self.runtime,180):
            with runtime_mutation_lock(Path('/var/lib/madar/releases')):
                # Preserve the real route as new audit data; no rollback to an
                # old115 route is permitted once the database advances.
                import uuid
                from deployment.lib.emergency_routing_repair import exclusive
                previous=readonly_configuration(UPSTREAM,private=False).read_bytes()
                exclusive(self.root/('compensation-route-preimage-'+uuid.uuid4().hex+'.conf'),previous)
                self.runtime.nginx_preflight(route,self.root)
                self.runtime.publish(route);self.runtime.reload()
                first=None;successes=0
                while True:
                    self.runtime.budget(1)
                    try:
                        self.candidate().round(normal=False)
                        for base in ('http://127.0.0.1:8001','http://127.0.0.1:3000/api'):
                            version=self.runtime.json_http(base+'/health/version')
                            if (version.get('release_sha')!=self.contract['candidate']['source_sha']
                                    or version.get('release_slot')!=slot
                                    or self.runtime.json_http(base+'/health/recovery')!={'restricted':True,'business_writes_enabled':False}):
                                # The prior Nginx worker may still be draining.
                                raise AvailabilityFailure('compatible_boot_route_activation_pending')
                            self.runtime.denied(base)
                        self.runtime.http_status('http://127.0.0.1:3000/')
                        if UPSTREAM.read_bytes()!=route:raise RuntimeError('completed_upgrade_boot_route_changed')
                        self.proxy_identity()
                    except AvailabilityFailure:first=None;successes=0
                    else:
                        successes+=1
                        if first is None:first=time.monotonic()
                        if successes>=3 and time.monotonic()-first>=5:break
                    time.sleep(self.runtime.budget(1))
    def maintenance(self):
        # Leaf compensation never calls another recovering kernel. Stop only
        # independently bound processes; preserved data is never restored.
        failures=[]
        with verification_window(self.runtime,60):
            with runtime_mutation_lock(Path('/var/lib/madar/releases')):
                from deployment.lib.completed_normal_profile import DELETION, RECONCILED
                candidates=(self.root/'candidate-runtime.json',)
                if self.profile in (DELETION, RECONCILED):candidates+=(self.root/'candidate-staged-runtime.json',)
                historical=self.contract['source_roles'].get('origin_kind')=='independently-enrolled-historical-bootstrap-origin'
                original=() if historical else (Path(self.contract['source_roles']['completion_root'])/
                    ('candidate-runtime.json' if self.profile is not LEGACY else 'candidate-identities.json'),)
                if historical:
                    try:
                        from deployment.lib.completed_normal_admission import origin_runtime
                        record=origin_runtime(self.contract)
                        # Same exact actor stop loop below; no restart or grant.
                        for identity in record['runtimes'].values():
                            rows=self.runtime.inspect([identity['id']]);row=next(iter(rows.values())) if len(rows)==1 else None
                            from deployment.lib.completed_normal_resources import measured_spec_matches
                            if row is None or row['Image']!=identity['image'] or not measured_spec_matches(row,identity['spec_sha256'],started_worker=True):
                                raise RuntimeError('historical_origin_compensation_actor_changed')
                            if row['State']['Running']:self.runtime.command(['docker','stop',identity['id']])
                    except Exception as error:failures.append(type(error).__name__)
                for path in (*candidates,*original):
                    if not path.exists():continue
                    try:record=json.loads(protected(path,private=True).read_text())
                    except Exception as error:
                        failures.append(type(error).__name__)
                        continue
                    kinds=(*WORKERS,'backend') if path.parent==self.root or self.profile is not LEGACY else ('notification','calendar-sync','data-deletion','backend')
                    for kind in kinds:
                        try:
                            expected=record['runtimes'][kind]
                            rows=self.runtime.inspect([expected['id']])
                            row=next(iter(rows.values())) if len(rows)==1 else None
                            if row is None or row['Id']!=expected['id'] or row['Image']!=expected['image']:
                                raise RuntimeError('completed_upgrade_boot_compensation_identity_changed')
                            if row['State']['Running']:self.runtime.command(['docker','stop',row['Id']])
                        except Exception as error:
                            # A failed worker stop must never skip the traffic
                            # fence. Do not touch an unbound replacement.
                            failures.append(type(error).__name__)
                try:
                    if failures:raise RuntimeError('completed_upgrade_boot_worker_stop_failed')
                    self.proxy_identity()
                    self.runtime.nginx_preflight(MAINTENANCE,self.root)
                    self.runtime.publish(MAINTENANCE);self.runtime.reload();self.runtime.verify_maintenance()
                except Exception:
                    # Resolve only the approved immutable proxy ID/image. A
                    # name-only stop could hit an unrelated replacement.
                    expected=self.document['proxy_runtime']
                    rows=self.runtime.inspect([expected['id']])
                    row=next(iter(rows.values())) if len(rows)==1 else None
                    if row is None or row['Id']!=expected['id'] or row['Image']!=expected['image']:
                        raise RuntimeError('completed_upgrade_boot_safe_proxy_stop_unavailable') from None
                    if row['State']['Running']:self.runtime.command(['docker','stop',expected['id']])
        self.event('maintenance',mode='READ_ONLY')
        if failures:raise RuntimeError('completed_upgrade_boot_compensation_worker_stop_failed') from None
    def completed_provider_rows(self):
        """Cold-start identities from the admitted original inventory, not names.

        This is limited to the independently enrolled canonical origin. It
        never changes that inventory or treats it as a modern completion.
        """
        from deployment.lib.schema150_actor_inventory import validate_inventory
        from deployment.lib.completed_normal_resources import measured_spec_matches,verify_runtime_binding
        binding={'operation':self.contract['operation'],'context_sha256':digest(self.contract),
            'source_sha':self.contract['candidate']['source_sha'],'controller_sha':self.contract['candidate']['controller_sha'],
            'inventory_sha256':self.contract['writer_inventory_sha256'],'system_identifier':self.contract['database']['system_identifier'],
            'source_schema':self.profile.source,'target_schema':self.profile.target}
        inventory=validate_inventory(json.loads(protected(self.root/'provider-inventory.json',private=True).read_bytes()),binding)
        publication=json.loads(protected(self.root/'normal-publication.json',private=True).read_bytes())
        verify_runtime_binding(self.contract,publication,self.runtime,Path('/var/lib/madar/releases'))
        ids=self.runtime.command(['docker','ps','-aq','--no-trunc']).split()
        expected={v['id'] for v in inventory['containers'].values()}|set(inventory['exclusions'])|{
            v['id'] for v in publication['runtimes'].values()}
        if len(ids)!=len(set(ids)) or set(ids)!=expected:
            raise RuntimeError('completed_boot_provider_inventory_changed')
        rows=self.runtime.inspect(ids)
        rows={v['Id']:v for v in rows.values()}
        if set(rows)!=expected:raise RuntimeError('completed_boot_provider_inventory_changed')
        native_ids={record['id'] for role,record in inventory['containers'].items() if role.startswith('native:')}
        proxy=rows[inventory['containers']['proxy']['id']]
        if any(not rows[identity]['State']['Running'] for identity in native_ids) and proxy['State']['Running']:
            raise RuntimeError('completed_boot_provider_ingress_not_fenced')
        if not rows[inventory['containers']['native:db']['id']]['State']['Running'] and any(
                rows[record['id']]['State']['Running'] for record in publication['runtimes'].values()):
            raise RuntimeError('completed_boot_provider_writers_not_fenced')
        selected={}
        for role,record in inventory['containers'].items():
            row=rows[record['id']]
            if (row.get('Name')!='/'+record['name'] or row.get('Image')!=record['image']
                    or not measured_spec_matches(row,record['spec_sha256'],started_worker=True)
                    or row['HostConfig']['RestartPolicy']['Name']!='no' or row['State'].get('Restarting')
                    or role.startswith('origin:') and row['State']['Running']):
                raise RuntimeError('completed_boot_provider_actor_changed')
            attached=row['NetworkSettings']['Networks']
            if set(attached)!=set(record['networks']):
                raise RuntimeError('completed_boot_provider_network_changed')
            for name,identity in record['networks'].items():
                endpoint=attached[name]
                if endpoint.get('NetworkID')!=identity and (row['State']['Running']
                        or endpoint.get('NetworkID')!='' or endpoint.get('EndpointID') or endpoint.get('IPAddress')
                        or row['State'].get('Status') not in {'created','exited'}):
                    raise RuntimeError('completed_boot_provider_network_changed')
                objects=json.loads(self.runtime.command(['docker','network','inspect',name]))
                if len(objects)!=1 or objects[0]['Id']!=identity:
                    raise RuntimeError('completed_boot_provider_network_changed')
            if role.startswith('native:'):selected[role]=row
        for identity,record in inventory['exclusions'].items():
            row=rows[identity]
            if row['Image']!=record['image'] or not measured_spec_matches(row,record['spec_sha256']):
                raise RuntimeError('completed_boot_excluded_actor_changed')
        if set(selected)!={'native:db','native:auth','native:rest','native:storage','native:gateway'}:
            raise RuntimeError('completed_boot_provider_roles_invalid')
        return selected

    def resume_completed_providers(self):
        from deployment.lib.completed_normal_profile import RECONCILED
        if self.profile is not RECONCILED or self.contract['source_roles'].get('origin_kind')!='independently-enrolled-historical-bootstrap-origin':
            return
        from deployment.lib.completed_normal_database import require_manual_normal_completion
        # An incomplete operation is fenced; this method cannot continue SQL,
        # restore roles, clear maintenance or issue a fresh deployment grant.
        self.guard();require_manual_normal_completion(self.contract,self.root)
        require_candidate_authority(self.contract,mode='NORMAL')
        with verification_window(self.runtime,60):
            with runtime_mutation_lock(Path('/var/lib/madar/releases')):
                for role in ('native:db','native:auth','native:rest','native:storage','native:gateway'):
                    self.guard();rows=self.completed_provider_rows();row=rows[role]
                    if not row['State']['Running']:
                        self.runtime.command(['docker','start',row['Id']])
                    while True:
                        self.runtime.budget(1)
                        current=self.completed_provider_rows()[role]
                        if current['State']['Running'] and current['State'].get('Health',{}).get('Status')=='healthy':break
                        __import__('time').sleep(self.runtime.budget(1))
                    if role=='native:db':
                        schema=self.native()
                        require_normal_migration_boundary(self.contract,schema,self.root,Path('/var/lib/madar/releases'))
                        if schema!=self.profile.target:raise RuntimeError('completed_boot_provider_schema_changed')
                        from deployment.lib.completed_normal_profile import maintenance_role
                        from deployment.lib.schema160_release import require_target_protocols
                        query=('BEGIN READ ONLY; SELECT json_build_array(public.notification_delivery_protocol(),'
                            'public.notification_outbox_protocol(),public.data_deletion_ownership_protocol()); COMMIT;')
                        protocols=json.loads(self.runtime.command(['docker','exec',row['Id'],'psql','-XqAt',
                            '-v','ON_ERROR_STOP=1','-U',maintenance_role(self.contract),'-d','postgres','-c',query]))
                        if not isinstance(protocols,list) or len(protocols)!=3:
                            raise RuntimeError('completed_boot_provider_protocol_observation_invalid')
                        require_target_protocols(schema,*protocols)
        self.event('completed_native_providers_ready',schema=self.profile.target)

    def resume(self):
        self.guard();self.proxy_identity();self.event('begin')
        if self.profile is not LEGACY and not (self.root/'candidate-runtime.json').exists():
            self.compensate()
            raise RuntimeError('completed_upgrade_manual_handoff_not_published')
        if not (self.root/'candidate-runtime.json').exists() and (self.root/'candidate-staged-runtime.json').exists():
            # The root independently sealed exact CREATED identities before
            # owner transfer. An interruption may follow that transfer but
            # precede the final running-runtime publication. Recover only
            # already exclusive ownership, never infer it from live names.
            stage=json.loads(protected(self.root/'candidate-staged-runtime.json',private=True).read_text())
            owner=load_worker_authority(Path('/var/lib/madar/releases'))
            original={'sha':self.contract['source_roles']['application_sha'],'slot':self.contract['origin']['slot']}
            if owner is not None and owner['candidate']!=original:
                from deployment.lib.completed_normal_resources import verify_runtime_binding
                from deployment.lib.emergency_routing_repair import exclusive
                try:
                    require_candidate_authority(self.contract,mode='READ_ONLY')
                    with runtime_mutation_lock(Path('/var/lib/madar/releases')):
                        self.guard()
                        verify_runtime_binding(self.contract,stage,self.runtime,Path('/var/lib/madar/releases'))
                        exclusive(self.root/'candidate-runtime.json',encoded(stage))
                    self.event('interrupted_handoff_runtime_recovered',mode='READ_ONLY')
                except Exception:
                    self.compensate()
                    raise
        if not (self.root/'candidate-runtime.json').exists():
            actor,kernel=self.origin()
            actor.candidate.require_write_authority(actor.candidate.contract,'NORMAL')
            return kernel.execute()
        self.resume_completed_providers()
        kernel=self.candidate();grant=require_candidate_authority(self.contract)
        if grant['mode']=='NORMAL':
            # Native PostgreSQL may still be warming up after Docker/host
            # startup. The kernel owns the single bounded readiness window
            # and checks migration intent before any positive write effect.
            try:return kernel.execute()
            except RuntimeError as error:
                if str(error) not in {'compatible_boot_migration_forward_repair_required','compatible_boot_normal_completion_pending'}:raise
                self.publish('READ_ONLY')
                return kernel.execute_read_only()
        return kernel.execute_read_only()
    def proxy_gate(self):
        self.guard();self.proxy_identity()
        if self.profile is not LEGACY and not (self.root/'candidate-runtime.json').exists():
            raise RuntimeError('completed_upgrade_manual_handoff_not_published')
        if not (self.root/'candidate-runtime.json').exists():
            actor,_=self.origin();actor.completed_evidence();actor.native();actor.kernel.normal(require_public=False)
            slot=self.contract['origin']['slot']
        else:
            kernel=self.candidate();grant=require_candidate_authority(self.contract)
            if grant['mode']=='NORMAL':require_normal_migration_boundary(self.contract,self.native(),self.root,Path('/var/lib/madar/releases'))
            kernel.round(normal=grant['mode']=='NORMAL');slot=self.contract['candidate']['slot']
        route=(f'upstream madar_backend_active {{ server 127.0.0.1:{8101 if slot=="blue" else 8201}; }}\n'
            f'upstream madar_frontend_active {{ server 127.0.0.1:{3100 if slot=="blue" else 3200}; }}\n').encode()
        actual=readonly_configuration(Path('/var/lib/madar/proxy/active-upstreams.conf'),private=False).read_bytes()
        if self.profile.maintenance and grant['mode']=='READ_ONLY':
            from deployment.lib.completed_normal_execution import manual_maintenance_route
            if actual==manual_maintenance_route(self.contract):
                return {'schema':self.native(),'mode':'READ_ONLY','maintenance':True}
        if actual!=route:
            raise RuntimeError('completed_upgrade_boot_proxy_route_changed')
        return {'schema':self.native(),'mode':'NORMAL' if not (self.root/'candidate-runtime.json').exists() else grant['mode']}
