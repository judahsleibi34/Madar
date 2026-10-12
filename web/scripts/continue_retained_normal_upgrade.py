#!/usr/bin/env python3
"""One freshly authorized continuation of the retained136..144 bridge.

Reuses the installed controller, systemd credentials, worker authority, locked
migration executor, grants, backup/restore/replication and existing boot actor.
Historical admission/authorization/failure are preserved as DATA, not permission.
"""
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import traceback

BASE=Path('/var/lib/madar-control-plane/normal-local-preparation')
ROUTING_SOURCE='8b0ab68f77a81bc6480b49d0fed9ef8b2ca8b5257887add7a50d75b5008a9bfd'
ROUTING_PLAN='bde5730d072d21d322423b645f49ad93e7b3f6e9e188a5c7f94da55844eb9fa2'
ROUTING_RESULT='19350f64c7b30a80a50a02cc6a0864a76e087763a8fdc4bbdb39e3b72a2aa91f'
OPERATION='retained-normal-schema136-144-continuation'
PREVIOUS_PLAN='6c489dcddea6bf7a6e72689833e3883f63fa11cb6bf69f4d667748b2e2fde86b'
PREVIOUS_SOURCE='ad4d9ce099863e002db2a895a197a3b8098d74e0fd54492b33bba2132b03db32'


def encoded(value):return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
def digest(value):return hashlib.sha256(encoded(value)).hexdigest()
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def secure(path):
    for p in (path,*path.parents):
        s=p.lstat()
        if p.is_symlink() or s.st_uid!=0 or s.st_mode&0o022:raise RuntimeError('continuation_untrusted_source_or_record')
    return path
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


class Continuation:
    def __init__(self,source_hash):
        if not re.fullmatch('[0-9a-f]{64}',source_hash):raise RuntimeError('continuation_source_hash_invalid')
        self.package=BASE/('retained-continuation-source-'+source_hash);self.source_hash=source_hash
        raw=secure(self.package/'source-bundle.json').read_bytes();self.manifest=json.loads(raw)
        if (hashlib.sha256(raw).hexdigest()!=source_hash or raw!=encoded(self.manifest)
                or set(self.manifest['files'])!={'driver.py','child.py','write-probe.py','migration.py'}
                or not re.fullmatch('[0-9a-f]{40}',str(self.manifest.get('source_git')))
                or Path(__file__)!=self.package/'driver.py'):
            raise RuntimeError('continuation_source_package_changed')
        for name,h in self.manifest['files'].items():
            if sha(secure(self.package/name))!=h:raise RuntimeError('continuation_executable_changed')
        prior=BASE/('read-only-bridge-source-'+ROUTING_SOURCE)
        manifest=secure(prior/'source-bundle.json').read_bytes()
        if hashlib.sha256(manifest).hexdigest()!=ROUTING_SOURCE:raise RuntimeError('continuation_routing_source_changed')
        for name,h in json.loads(manifest)['files'].items():
            if sha(secure(prior/name))!=h:raise RuntimeError('continuation_routing_executable_changed')
        self.recovery=load('continuation_measured_routing_dependency',prior/'driver.py')
        self.actor,self.validator,_=self.recovery.assemble(ROUTING_SOURCE)
        self.contract=self.actor.contract;self.controller=self.contract['candidate']['controller_sha']
        self.plan=None;self.scope=None;self.phase='preflight';self.active=False

    def evidence(self):
        from deployment.lib.completed_normal_evidence import verify_application_evidence,verify_complete_rehearsal
        return verify_application_evidence(self.actor),verify_complete_rehearsal(self.actor)

    def execution_ci(self):
        git=self.manifest['source_git'];repo='judahsleibi34/Madar'
        rows=json.loads(self.actor.ops.command('continuation_ci',[
            '/usr/sbin/runuser','-u','madar','--','/usr/bin/gh','run','list','--repo',repo,'--commit',git,
            '--limit','30','--json','databaseId,headSha,status,conclusion,workflowName,url']).stdout)
        accepted={}
        for name in ('Backend Check','Frontend Check'):
            matches=[r for r in rows if r.get('workflowName')==name and r.get('headSha')==git]
            if not matches:raise RuntimeError('continuation_exact_source_ci_missing')
            record=max(matches,key=lambda r:r['databaseId'])
            if (record['status']!='completed' or record['conclusion']!='success'
                    or record['url']!='https://github.com/'+repo+'/actions/runs/'+str(record['databaseId'])):
                raise RuntimeError('continuation_exact_source_ci_incomplete')
            accepted[name]=record
        return accepted

    def measurement(self):
        if (self.actor.root/'migration-intent.json').exists():return self.resume_measurement()
        actor=self.actor
        result=Path('/var/lib/madar-control-plane/emergency-retained-bridge-routing')/ROUTING_PLAN/'result.json'
        if sha(secure(result))!=ROUTING_RESULT:raise RuntimeError('continuation_routing_completion_changed')
        bindings=self.recovery.measure_live(actor,self.validator,published=True)
        from deployment.lib.completed_normal_admission import prepared_path
        from deployment.lib.provider_recovery_runtime import readonly_configuration
        prepared=readonly_configuration(prepared_path(self.contract,actor.ops.state_root),private=True)
        record=json.loads(prepared.read_text())
        state=readonly_configuration(actor.ops.state_root/'state.json',private=True)
        value=json.loads(state.read_text());known=value.get('known_good_release') or {}
        if (record.get('status')!='candidate_validated_workers_inactive' or record.get('schema')!=136
                or record.get('release_sha')!=self.contract['candidate']['source_sha'] or record.get('candidate_slot')!='blue'
                or value.get('active_slot')!='green' or known.get('sha')!=self.contract['source_roles']['application_sha']
                or known.get('schema')!=136 or value.get('in_progress_release') or value.get('rollback_failure')):
            raise RuntimeError('continuation_prepared_state_changed')
        absent=('candidate-staged-runtime.json','candidate-runtime.json','migration-intent.json','migration-inputs.json',
                'pre-migration-backup.json','post-migration-backup.json','normal-completion.json')
        if any((actor.root/name).exists() for name in absent):raise RuntimeError('continuation_parent_progress_changed')
        if (actor.ops.state_root/'migrations'/record['release_sha']/'execution.json').exists():
            raise RuntimeError('continuation_migration_attempt_exists')
        self.evidence()
        from deployment.lib.completed_normal_resources import measured_spec
        gateway=actor.runtime.inspect(['supabase-envoy'])['supabase-envoy']
        if (gateway['Config'].get('Labels',{}).get('com.docker.compose.service')!='api-gw'
                or gateway['Config'].get('Labels',{}).get('com.docker.compose.project')!='madar-local-supabase'
                or not gateway['State']['Running']):
            raise RuntimeError('continuation_native_auth_gateway_changed')
        from deployment.lib.active_recovery_backup import verify_backup_execution_context
        verify_backup_execution_context(actor.package,expected_schema=136)
        from deployment.lib.completed_normal_database import migration_customer_snapshot
        current=migration_customer_snapshot(self.contract,actor.runtime)
        from deployment.lib.control_plane_upgrade import BACKUP_TIMERS
        timers={name:actor.ops.systemctl_state(name) for name in BACKUP_TIMERS}
        if actor.ops.interlock_backup_states(self.controller)!=actor.document['backup_timer_states']:
            raise RuntimeError('continuation_backup_restore_state_changed')
        if any(v['active']!='inactive' for v in timers.values()):raise RuntimeError('continuation_backup_timer_changed')
        if any(actor.ops.systemctl_state(n.replace('.timer','.service'))['active'] not in {'inactive','failed'} for n in BACKUP_TIMERS):
            raise RuntimeError('continuation_backup_service_running')
        if os.statvfs('/').f_bavail*os.statvfs('/').f_frsize<4*1024**3:raise RuntimeError('continuation_storage_insufficient')
        return {'bindings':bindings,'execution_ci':self.execution_ci(),'routing_result_sha256':ROUTING_RESULT,'prepared_sha256':sha(prepared),
                'state_sha256':sha(state),'customer_snapshot_sha256':digest(current),'timers':timers,
                'auth_gateway':{'id':gateway['Id'],'image':gateway['Image'],'spec_sha256':measured_spec(gateway)},
                'timer_restore':actor.document['backup_timer_states'],
                'worker_generation':hashlib.sha256(f"bootstrap:{record['release_sha']}:blue:{record['prepared_at']}".encode()).hexdigest()}

    def resume_measurement(self):
        """Exact consumed attempt, sealed READ_ONLY runtime, no executor/SQL."""
        from deployment.lib.provider_recovery_runtime import protected,readonly_configuration
        from deployment.lib.runtime_authority import load_worker_authority
        from deployment.lib.completed_normal_migration import intent_document
        from deployment.lib.completed_normal_database import migration_customer_snapshot
        from deployment.lib.completed_normal_resources import measured_spec
        from deployment.lib.control_plane_upgrade import BACKUP_TIMERS
        actor=self.actor;actor.guard();kernel=actor.candidate();kernel.verify_mode(normal=False)
        if actor.native()!=136:raise RuntimeError('continuation_resume_source_schema_changed')
        previous=actor.root/'continuations'/PREVIOUS_PLAN
        failure=json.loads(protected(previous/'failure.json',private=True).read_text())
        previous_plan=json.loads(protected(previous/'plan.json',private=True).read_text())
        previous_authorization=json.loads(protected(previous/'operator-authorization.json',private=True).read_text())
        if (digest(previous_plan)!=PREVIOUS_PLAN or failure.get('operation')!=OPERATION
                or failure.get('phase')!='service_migrate_pending' or failure.get('database_restored') is not False
                or 'compensation_exception_type' in failure or (previous/'completion.json').exists()
                or json.loads(protected(actor.root/'migration-intent.json',private=True).read_text())!=intent_document(self.contract)):
            raise RuntimeError('continuation_resume_previous_attempt_changed')
        if previous_authorization!={'operation':OPERATION,'plan_sha256':PREVIOUS_PLAN,'source_sha256':PREVIOUS_SOURCE,
                'parent_context_sha256':actor.root.name,'historical_authorization_reused':False}:
            raise RuntimeError('continuation_resume_previous_authorization_changed')
        if any((actor.root/n).exists() for n in ('migration-completion.json','normal-completion.json','post-migration-backup.json','normal-publication.json')):
            raise RuntimeError('continuation_resume_progress_changed')
        candidate=self.contract['candidate'];state_path=readonly_configuration(actor.ops.state_root/'state.json',private=True)
        state=json.loads(state_path.read_text());known=state.get('known_good_release') or {}
        owner=load_worker_authority(actor.ops.state_root)
        if (state.get('active_slot')!='blue' or known.get('sha')!=candidate['source_sha'] or known.get('slot')!='blue'
                or known.get('schema')!=136 or state.get('in_progress_release') or state.get('rollback_failure')
                or owner is None or owner['owner']!='CANDIDATE' or owner['candidate']!={'sha':candidate['source_sha'],'slot':'blue'}
                or owner['generation']!=previous_plan['initial']['worker_generation']
                or (actor.ops.state_root/'migrations'/candidate['source_sha']/'execution.json').exists()):
            raise RuntimeError('continuation_resume_no_sql_state_changed')
        before=json.loads(protected(actor.root/'pre-migration-customer-snapshot.json',private=True).read_text())
        current=migration_customer_snapshot(self.contract,actor.runtime,columns=before['columns'])
        if before!=current:raise RuntimeError('continuation_resume_customer_snapshot_changed')
        from deployment.lib.completed_normal_migration import verify_migration_backup
        from deployment.lib.active_recovery_backup import verify_backup_execution_context
        inputs=json.loads(protected(actor.root/'migration-inputs.json',private=True).read_text())
        receipt=json.loads(protected(actor.root/'pre-migration-backup.json',private=True).read_text())
        if (receipt['schema']!=136 or receipt['source_sha']!=candidate['source_sha'] or receipt['images']!=candidate['images']
                or receipt['restore']['status']!='logical_database_and_file_restore_passed'
                or receipt['node1']['checksum_exit_code']!=0 or receipt['local_path']!=inputs['backup']):
            raise RuntimeError('continuation_resume_backup_evidence_changed')
        from types import SimpleNamespace
        verify_migration_backup(Path(inputs['backup']),inputs,candidate['source_sha'],
            SimpleNamespace(recovery_helper_root=lambda:actor.package/'source/web/scripts'),expected_schema=136)
        verify_backup_execution_context(actor.package,expected_schema=136);self.evidence()
        timers={n:actor.ops.systemctl_state(n) for n in BACKUP_TIMERS}
        if any(v['active']!='inactive' for v in timers.values()) or actor.ops.interlock_backup_states(self.controller)!=actor.document['backup_timer_states']:
            raise RuntimeError('continuation_resume_backup_timer_changed')
        if any(actor.ops.systemctl_state(n.replace('.timer','.service'))['active'] not in {'inactive','failed'} for n in BACKUP_TIMERS):
            raise RuntimeError('continuation_resume_backup_service_running')
        gateway=actor.runtime.inspect(['supabase-envoy'])['supabase-envoy'];actor.proxy_identity()
        from deployment.lib.emergency_routing_repair import UPSTREAM
        if UPSTREAM.read_bytes()!=self.recovery.ROUTE:raise RuntimeError('continuation_resume_public_route_changed')
        fixed=[actor.root/n for n in ('admission.json','operator-authorization.json','failure.json','controller-installation.json',
            'controller-installation-intent.json','boot-installation.json','candidate-staged-runtime.json','candidate-runtime.json',
            'migration-intent.json','migration-inputs.json','pre-migration-backup.json','pre-migration-customer-snapshot.json')]
        fixed += [previous/n for n in ('plan.json','operator-authorization.json','failure.json')]
        fixed += [actor.root/'write-authority/authority.json',Path(self.contract['source_roles']['completion_root'])/'write-authority/authority.json',
            actor.ops.interlock_file]
        records={str(p):sha(protected(p)) for p in fixed}
        owner_path=readonly_configuration(actor.ops.state_root/'worker-ownership.json',private=True);records[str(owner_path)]=sha(owner_path)
        if os.statvfs('/').f_bavail*os.statvfs('/').f_frsize<4*1024**3:raise RuntimeError('continuation_storage_insufficient')
        return {'entry':'sealed-pre-sql','previous_plan_sha256':PREVIOUS_PLAN,'bindings':{'records':records},
            'state_sha256':sha(state_path),'customer_snapshot_sha256':digest(current),'execution_ci':self.execution_ci(),
            'timers':timers,'timer_restore':actor.document['backup_timer_states'],'worker_generation':owner['generation'],
            'auth_gateway':{'id':gateway['Id'],'image':gateway['Image'],'spec_sha256':measured_spec(gateway)}}

    def preflight(self):
        if self.plan['initial']!=self.measurement():raise RuntimeError('continuation_live_bindings_changed')
        if self.scope.exists() or self.scope.is_symlink():raise RuntimeError('continuation_authorization_consumed')
        return {'preflight':'PASS','production_modified':False,'authorization_consumed':False}

    def guard(self):
        raw=secure(self.package/'source-bundle.json').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=self.source_hash:raise RuntimeError('continuation_source_changed')
        for name,h in self.manifest['files'].items():
            if sha(secure(self.package/name))!=h:raise RuntimeError('continuation_executable_changed')
        self.actor.guard()
        fixed=self.plan['initial']['bindings']['records']
        for path,h in fixed.items():
            if any(path.endswith('/'+name) for name in ('worker-ownership.json','in-progress.json','latest.json','LATEST','boot-events.jsonl')):
                continue
            if path==str(self.actor.root/'write-authority/authority.json'):continue
            if sha(secure(Path(path)))!=h:raise RuntimeError('continuation_historical_binding_changed')
        if self.active:
            expected={'operation':OPERATION,'plan_sha256':digest(self.plan),'source_sha256':self.source_hash,
                      'parent_context_sha256':self.actor.root.name,'historical_authorization_reused':False}
            if json.loads(secure(self.scope/'operator-authorization.json').read_text())!=expected:
                raise RuntimeError('continuation_fresh_authorization_changed')
            if (self.scope/'completion.json').exists() or (self.scope/'failure.json').exists():
                raise RuntimeError('continuation_authorization_consumed')

    def witness(self):
        self.guard()
        if not self.active:raise RuntimeError('continuation_fresh_authorization_required')
        from deployment.lib.completed_normal_profile import expected_origin_grant
        return {'operation':OPERATION,'plan_sha256':digest(self.plan),'source_sha256':self.source_hash,
                'parent_context_sha256':self.actor.root.name,'application_sha':self.contract['candidate']['source_sha'],
                'child_sha256':self.manifest['files']['child.py'],'worker_generation':self.plan['initial']['worker_generation'],
                'migration_sha256':self.manifest['files']['migration.py'],
                'worker_owner_sha256':self.plan['initial']['bindings']['records'][str(self.actor.ops.state_root/'worker-ownership.json')],
                'origin_grant':expected_origin_grant(self.contract,'READ_ONLY')}

    def event(self,phase):
        self.phase=phase
        from deployment.lib.emergency_routing_repair import exclusive
        exclusive(self.scope/(phase+'.json'),encoded({'phase':phase,'operation':OPERATION,'plan_sha256':digest(self.plan)}))

    @contextmanager
    def credential(self):
        from deployment.lib.completed_normal_execution import CompletedNormalUpgrade
        with CompletedNormalUpgrade.root_credential(self):yield

    def child(self,mode):
        if mode not in {'activate','migrate'}:raise RuntimeError('continuation_child_stage_invalid')
        self.event('service_'+mode+'_pending');self.guard()
        self.ops.write_authorization(self.controller,completed_normal_contract=self.contract)
        unit='madar-control-plane-upgrade-continuation-'+str(os.getpid())+'-'+mode
        try:
            result=self.ops.command('continuation_'+mode,[
                '/usr/bin/systemd-run','--quiet','--wait','--collect','--service-type=oneshot','--unit='+unit,
                '--uid=madar','--gid=madar','--working-directory='+str(self.ops.repo),
                '--property=UMask=0077','--property=NoNewPrivileges=yes','--property=TimeoutStartSec=45min',
                '--property=EnvironmentFile=/etc/madar/backup.env','--property=EnvironmentFile=/etc/madar/node1-backup.env',
                '--property=EnvironmentFile='+str(self.ops.contract_path),
                '--property=Environment=MADAR_TRAFFIC_SWITCH_DRIVER=docker-nginx',
                '--property=Environment=MADAR_PROXY_CONTAINER=madar-release-proxy',
                '--property=LoadCredential=madar-control-plane-upgrade:'+str(self.ops.authorization_file),
                '--property=LoadCredential=completed-continuation-executor:'+str(self.package/'child.py'),
                '--property=LoadCredential=completed-continuation-migration:'+str(self.package/'migration.py'),
                '/usr/bin/python3','-I','-B','/run/credentials/'+unit+'.service/completed-continuation-executor',mode],
                timeout=3000,check=False)
            if result.returncode:raise RuntimeError('continuation_child_'+mode+'_failed')
        finally:self.ops.clear_authorization()
        self.event('service_'+mode+'_completed')

    def execute(self):
        from deployment.lib.control_plane_upgrade import SystemOperations,acquire_lock,atomic_json,BACKUP_TIMERS
        from deployment.lib.completed_normal_execution import protected_creation_mode,enter_manual_maintenance,verify_serving
        from deployment.lib.completed_normal_write_handoff import CompletedNormalWriteHandoff
        from deployment.lib.completed_normal_backup import CompletedNormalBackupContext
        from deployment.lib.completed_normal_migration import seal_intent,seal_completion
        from deployment.lib.completed_normal_database import migration_customer_snapshot,verify_migration_customer_preservation
        from deployment.lib.emergency_routing_repair import exclusive
        driver=self
        class FreshOperations(SystemOperations):
            def write_authorization(ops,*args,**kwargs):
                lease=driver.witness()
                super().write_authorization(*args,**kwargs)
                document=json.loads(ops.authorization_file.read_text());document['completed_continuation']=lease
                atomic_json(ops.authorization_file,document);ops.authorization_file.chmod(0o600)
                interlock=json.loads(ops.interlock_file.read_text());interlock['completed_continuation_sha256']=digest(lease)
                atomic_json(ops.interlock_file,interlock);ops.interlock_file.chmod(0o644)
        self.preflight();self.ops=FreshOperations();self.actor.ops=self.ops
        self.ops.backup_timer_sha=self.controller
        lock=acquire_lock(self.ops.upgrade_root/'upgrade.lock',create=False)
        try:
            with protected_creation_mode():
                self.preflight();self.scope.parent.mkdir(mode=0o700,exist_ok=True);secure(self.scope.parent);self.scope.mkdir(mode=0o700)
                exclusive(self.scope/'plan.json',encoded(self.plan),mode=0o400)
                exclusive(self.scope/'operator-authorization.json',encoded({'operation':OPERATION,'plan_sha256':digest(self.plan),
                    'source_sha256':self.source_hash,'parent_context_sha256':self.actor.root.name,'historical_authorization_reused':False}))
                exclusive(self.scope/'previous-interlock.json',secure(self.ops.interlock_file).read_bytes())
                self.active=True;self.guard()
                if self.plan['initial'].get('entry')=='sealed-pre-sql':
                    with self.credential():
                        self.event('sealed_pre_sql_resume_verified')
                        kernel=self.actor.candidate();kernel.verify_mode(normal=False)
                        before=json.loads(secure(self.actor.root/'pre-migration-customer-snapshot.json').read_text())
                        from deployment.lib.emergency_routing_repair import UPSTREAM,MAINTENANCE,verification_window
                        self.event('migration_maintenance_pending')
                        exclusive(self.scope/'migration-maintenance-preimage.conf',UPSTREAM.read_bytes())
                        with verification_window(self.actor.runtime,180):
                            self.actor.proxy_identity();self.actor.runtime.nginx_preflight(MAINTENANCE,self.scope)
                            self.actor.runtime.publish(MAINTENANCE);self.actor.runtime.reload()
                else:
                    with self.credential():
                        self.event('candidate_stage_seal_pending')
                        self.validator.seal_candidate_stage(self.contract,source_guard=self.guard,
                            model_loader=lambda:self.recovery.staged_model(self.actor),runtime=self.actor.runtime,state_root=self.ops.state_root)
                    self.child('activate')
                    with self.credential():
                        self.event('candidate_runtime_seal_pending')
                        self.validator.seal_candidate_runtime(self.contract,source_guard=self.guard,
                            model_loader=lambda:self.recovery.staged_model(self.actor),runtime=self.actor.runtime,state_root=self.ops.state_root)
                        kernel=self.actor.candidate();kernel.verify_mode(normal=False)
                    self.event('ordinary_read_only_adoption_pending')
                    self.ops.run_deploy_service('continuation_adopt',self.controller,completed_normal_contract=self.contract,completed_normal_mode='adopt')
                    with self.credential():
                        self.event('migration_maintenance_pending');enter_manual_maintenance(self.actor)
                        backup=CompletedNormalBackupContext(self.contract,self.actor.document,self.actor.package,kernel,
                            stage='pre-migration',source_guard=self.guard,artifact_guard=lambda:self.evidence()[0])
                        self.event('pre_migration_backup_pending');receipt=backup.capture();backup.seal_migration_inputs(receipt)
                        before=migration_customer_snapshot(self.contract,self.actor.runtime)
                        exclusive(self.actor.root/'pre-migration-customer-snapshot.json',encoded(before))
                        seal_intent(self.contract,source_guard=self.guard,runtime_guard=self.actor.native,backup_guard=backup.guard)
                self.child('migrate')
                with self.credential():
                    self.event('migration_preservation_pending')
                    after=migration_customer_snapshot(self.contract,self.actor.runtime,columns=before['columns'])
                    exclusive(self.actor.root/'post-migration-customer-snapshot.json',encoded(after))
                    exclusive(self.actor.root/'migration-customer-preservation.json',encoded(verify_migration_customer_preservation(before,after,contract=self.contract)))
                    seal_completion(self.contract,self.ops.state_root/'releases'/self.contract['candidate']['source_sha'],self.ops.state_root,
                        source_guard=self.guard,runtime_guard=self.actor.native)
                    self.actor.publish_restricted_bridge()
                self.ops.run_deploy_service('continuation_refresh',self.controller,completed_normal_contract=self.contract,completed_normal_mode='refresh')
                with self.credential():
                    self.event('normal_grant_pending')
                    handoff=CompletedNormalWriteHandoff(self.contract,kernel,source_guard=self.guard,
                        boot_guard=self.actor.installation.installed,artifact_guard=lambda:self.evidence()[0])
                    handoff.grant(schema=144);verify_serving(self.actor,schema=144,normal=True)
                    self.event('authenticated_live_write_pending')
                    write_result=load('continuation_measured_live_write',self.package/'write-probe.py').run(
                        self.actor,self.scope,digest(self.plan),self.plan['initial']['auth_gateway'])
                    exclusive(self.scope/'live-write-verification.json',encoded(write_result))
                    self.event('post_migration_backup_pending')
                    backup=CompletedNormalBackupContext(self.contract,self.actor.document,self.actor.package,kernel,
                        stage='post-migration',source_guard=self.guard,artifact_guard=lambda:self.evidence()[0]);receipt=backup.capture()
                    self.event('backup_timer_restore_pending');self.ops.restore_backup_timers()
                    result={'operation':self.contract['operation'],'context_sha256':self.actor.root.name,'schema':144,'mode':'NORMAL',
                        'application_sha':self.contract['candidate']['source_sha'],'controller_sha':self.controller,
                        'images':self.contract['candidate']['images'],'backup':receipt,
                        'backup_timers':{n:self.ops.systemctl_state(n) for n in BACKUP_TIMERS},'customer_database_restored':False,
                        'live_authenticated_write':write_result,
                        'continuation':{'operation':OPERATION,'plan_sha256':digest(self.plan),'source_sha256':self.source_hash,'source_git':self.manifest['source_git']}}
                    self.guard();verify_serving(self.actor,schema=144,normal=True)
                    exclusive(self.actor.root/'normal-completion.json',encoded(result))
                    from deployment.lib.completed_normal_baseline import seal_compatible_release
                    seal_compatible_release(self.contract,self.actor.root,self.ops.state_root)
                    exclusive(self.scope/'completion.json',encoded(result))
                self.ops.clear_interlock();return result
        except Exception as error:
            if self.active:
                failure={'operation':OPERATION,'phase':self.phase,'exception_type':type(error).__name__,'database_restored':False,
                    'frames':[{'file':Path(f.filename).name,'function':f.name,'line':f.lineno} for f in traceback.extract_tb(error.__traceback__)[-16:]]}
                try:
                    # Interrupted startup may precede the final runtime seal.
                    # Stop only the independently sealed new worker IDs then;
                    # never depend on a missing final receipt to fence them.
                    stage=self.actor.root/'candidate-staged-runtime.json'
                    if stage.exists() and not (self.actor.root/'candidate-runtime.json').exists():
                        from deployment.lib.completed_normal_resources import verify_runtime_resources
                        rows=verify_runtime_resources(self.contract,json.loads(secure(stage).read_text()),self.actor.runtime)
                        for kind in self.validator.BUSINESS:
                            if rows[kind]['State']['Running']:self.actor.runtime.command(['docker','stop',rows[kind]['Id']])
                    self.actor.compensate();self.ops.requiesce_backup_timers_for_failure()
                except Exception as compensation:failure['compensation_exception_type']=type(compensation).__name__
                exclusive(self.scope/'failure.json',encoded(failure))
            raise
        finally:
            self.active=False
            if hasattr(self,'ops'):self.ops.clear_authorization();self.ops.close_locks()
            os.close(lock)


def main():
    if os.geteuid()!=0 or not sys.flags.isolated or not sys.flags.dont_write_bytecode:raise RuntimeError('continuation_isolated_root_required')
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('prepare','preflight','execute'))
    parser.add_argument('--approved-source',required=True);parser.add_argument('--approved-plan');args=parser.parse_args()
    driver=Continuation(args.approved_source)
    if args.mode=='prepare':
        initial=driver.measurement();plan={'operation':OPERATION,'source_sha256':args.approved_source,'source_git':driver.manifest['source_git'],
            'parent_context_sha256':driver.actor.root.name,'initial':initial,'migrations':[137,138,139,140,141,143,144],
            'target_schema':144,'restore_old_customer_database':False,'automatic_retry':False,'live_synthetic_account_verification':True}
        from deployment.lib.emergency_routing_repair import exclusive
        exclusive(driver.package/'plan.json',encoded(plan),mode=0o400)
        print(json.dumps({'preflight':'PASS','production_modified':False,'source_sha256':args.approved_source,'plan_sha256':digest(plan)}));return
    raw=secure(driver.package/'plan.json').read_bytes();driver.plan=json.loads(raw)
    if (hashlib.sha256(raw).hexdigest()!=args.approved_plan or raw!=encoded(driver.plan)
            or driver.plan['operation']!=OPERATION or driver.plan['source_sha256']!=args.approved_source
            or driver.plan['migrations']!=[137,138,139,140,141,143,144] or driver.plan['target_schema']!=144
            or driver.plan.get('live_synthetic_account_verification') is not True
            or driver.plan['restore_old_customer_database'] is not False or driver.plan['automatic_retry'] is not False):
        raise RuntimeError('continuation_approved_plan_changed')
    driver.scope=driver.actor.root/'continuations'/digest(driver.plan)
    print(json.dumps(driver.preflight() if args.mode=='preflight' else driver.execute(),sort_keys=True))


if __name__=='__main__':
    try:main()
    except Exception as error:
        code=str(error);print(json.dumps({'status':'failed','exception_type':type(error).__name__,
            'failure_code':code if isinstance(error,RuntimeError) and re.fullmatch('[a-z][a-z0-9_]{1,100}',code) else 'sanitized_exception'}));raise SystemExit(1)
