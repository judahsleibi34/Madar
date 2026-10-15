#!/usr/bin/env python3
"""One fresh backup-only completion of the verified schema146 runtime.

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
PARENT_SOURCE='ecdc02ef9a2fac59007e0c02be3add85e69bd37db7ea19929b36c91c43143ed6'
PARENT_PLAN='7e27ac761f6571bfd1c2101f7717cdbcbb904aec0ab4914a08e07340bf6588ad'
PARENT_CONTEXT='b3e4084534ff0453acda8c59a3a064cf01691cc19350311036b50c9a0a0a2234'
OPERATION='retained-normal-schema146-backup-completion'
PREVIOUS_PLAN='2305e6f1360c83ce50eee90031cd57a9b14a07ad28287b294f9b4f56f77c2196'
BINDING_FAILURE_PLAN='dc0b3e0c66a5dd0e41eb8aa13fbdd067da302d8dd9a067a151dd210dc050cf50'


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
                or set(self.manifest['files'])!={'driver.py','write-probe.py','backup.py','write-handoff.py','source/web/scripts/normal_backup_replica.py','source/web/scripts/backup_support.py','source/web/scripts/backup_madar.sh','source/web/scripts/verify_backup.sh'}
                or not re.fullmatch('[0-9a-f]{40}',str(self.manifest.get('source_git')))
                or Path(__file__)!=self.package/'driver.py'):
            raise RuntimeError('continuation_source_package_changed')
        for name,h in self.manifest['files'].items():
            if sha(secure(self.package/name))!=h:raise RuntimeError('continuation_executable_changed')
        parent=BASE/('normal-source-'+PARENT_SOURCE)
        entry=parent/'source/web/scripts/continue_completed_normal_upgrade.py'
        measured=load('measured_completed_normal_parent',secure(entry))
        document,source=measured.measure(parent,PARENT_SOURCE,PARENT_PLAN)
        sys.path.insert(0,str(source/'web'))
        from deployment.lib.completed_normal_boot_actor import CompletedNormalBootActor
        self.actor=CompletedNormalBootActor(document,parent,lambda:measured.measure(parent,PARENT_SOURCE,PARENT_PLAN))
        if self.actor.root.name!=PARENT_CONTEXT:raise RuntimeError('continuation_parent_context_changed')
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

    def candidate(self):
        # A repeated positive boundary uses the immutable candidate identity.
        # The earlier NORMAL publication is verified separately as history.
        from deployment.lib.compatible_normal_boot import CompatibleNormalBoot
        return CompatibleNormalBoot(self.contract,source_guard=self.guard,native_verifier=self.actor.native,
            publish_authority=self.actor.publish,compensate_current_data=self.actor.compensate,
            runtime=self.actor.runtime,publication_name='candidate-runtime.json')

    def measurement(self):
        from deployment.lib.provider_recovery_runtime import protected,readonly_configuration
        from deployment.lib.runtime_authority import load_worker_authority
        from deployment.lib.completed_normal_database import migration_customer_snapshot,require_normal_migration_boundary
        from deployment.lib.completed_normal_resources import measured_spec
        from deployment.lib.control_plane_upgrade import BACKUP_TIMERS
        actor=self.actor;actor.guard();kernel=self.candidate();kernel.verify_mode(normal=False)
        if actor.native()!=146:raise RuntimeError('backup_completion_target_schema_changed')
        constructor=load('preflight_measured_write_boundary',self.package/'write-handoff.py')
        constructor.CompletedNormalWriteHandoff(self.contract,kernel,source_guard=self.guard,
            boot_guard=actor.installation.installed,artifact_guard=lambda:self.evidence()[0])
        binding=actor.root/'continuations'/BINDING_FAILURE_PLAN
        rejected=json.loads(protected(binding/'failure.json',private=True).read_text())
        if (rejected.get('operation')!=OPERATION or rejected.get('phase')!='normal_grant_pending'
                or rejected.get('database_restored') is not False or 'compensation_exception_type' in rejected
                or not any(f.get('file')=='write-handoff.py' and f.get('function')=='__init__' for f in rejected.get('frames',[]))
                or any((binding/name).exists() for name in ('completion.json','pre-grant-authority-146.json','write-boundary-146.json'))):
            raise RuntimeError('backup_completion_binding_failure_changed')
        require_normal_migration_boundary(self.contract,146,actor.root,actor.ops.state_root)
        previous=actor.root/'continuations'/PREVIOUS_PLAN
        failure=json.loads(protected(previous/'failure.json',private=True).read_text())
        if (failure.get('operation')!='retained-normal-schema144-146-pre-sql-continuation'
                or failure.get('phase')!='post_migration_backup_pending' or failure.get('database_restored') is not False
                or 'compensation_exception_type' in failure or (previous/'completion.json').exists()):
            raise RuntimeError('backup_completion_previous_attempt_changed')
        write=json.loads(protected(previous/'live-write-verification.json',private=True).read_text())
        if any(write.get(k) is not True for k in ('authenticated_login','http_profile_mutation','fresh_session_readback','native_database_readback')):
            raise RuntimeError('backup_completion_previous_write_not_verified')
        if any((actor.root/n).exists() for n in ('normal-completion.json','post-migration-backup.json')):
            raise RuntimeError('backup_completion_already_completed')
        candidate=self.contract['candidate'];state_path=readonly_configuration(actor.ops.state_root/'state.json',private=True)
        state=json.loads(state_path.read_text());known=state.get('known_good_release') or {};owner=load_worker_authority(actor.ops.state_root)
        publication=json.loads(protected(actor.root/'candidate-runtime.json',private=True).read_text())
        if (state.get('active_slot')!='blue' or known.get('sha')!=candidate['source_sha'] or known.get('slot')!='blue'
                or known.get('schema')!=146 or state.get('in_progress_release') or state.get('rollback_failure')
                or owner is None or owner['owner']!='CANDIDATE' or owner['candidate']!={'sha':candidate['source_sha'],'slot':'blue'}
                or owner['generation']!=publication['worker_generation']):
            raise RuntimeError('backup_completion_runtime_changed')
        before=json.loads(protected(actor.root/'pre-migration-customer-snapshot.json',private=True).read_text())
        current=migration_customer_snapshot(self.contract,actor.runtime,columns=before['columns'])
        self.evidence()
        timers={n:actor.ops.systemctl_state(n) for n in BACKUP_TIMERS}
        if any(v['active']!='inactive' for v in timers.values()) or actor.ops.interlock_backup_states(self.controller)!=actor.document['backup_timer_states']:
            raise RuntimeError('backup_completion_timer_changed')
        if any(actor.ops.systemctl_state(n.replace('.timer','.service'))['active'] not in {'inactive','failed'} for n in BACKUP_TIMERS):
            raise RuntimeError('backup_completion_backup_service_running')
        gateway=actor.runtime.inspect(['supabase-envoy'])['supabase-envoy'];actor.proxy_identity()
        fixed=[actor.root/n for n in ('admission.json','operator-authorization.json','failure.json','controller-installation.json','controller-installation-intent.json','boot-installation.json','candidate-runtime.json','migration-intent.json','migration-inputs.json','pre-migration-backup.json','pre-migration-customer-snapshot.json','migration-completion.json','migration-execution.json','migration-manifest.json','migration-customer-preservation.json')]
        fixed += [previous/n for n in ('plan.json','operator-authorization.json','failure.json','live-write-verification.json')]
        fixed += [binding/n for n in ('plan.json','operator-authorization.json','failure.json')]
        fixed += [actor.root/'write-authority/authority.json',Path(self.contract['source_roles']['completion_root'])/'write-authority/authority.json',actor.ops.interlock_file]
        records={str(p):sha(protected(p)) for p in fixed}
        owner_path=readonly_configuration(actor.ops.state_root/'worker-ownership.json',private=True);records[str(owner_path)]=sha(owner_path)
        if os.statvfs('/').f_bavail*os.statvfs('/').f_frsize<4*1024**3:raise RuntimeError('backup_completion_storage_insufficient')
        return {'entry':'sealed-post-sql','bindings':{'records':records},'state_sha256':sha(state_path),'customer_snapshot_sha256':digest(current),'execution_ci':self.execution_ci(),'timers':timers,'timer_restore':actor.document['backup_timer_states'],'worker_generation':owner['generation'],'auth_gateway':{'id':gateway['Id'],'image':gateway['Image'],'spec_sha256':measured_spec(gateway)}}

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
        if self.plan is None:
            if self.active:raise RuntimeError('continuation_frozen_plan_required')
            return
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
                'backup_sha256':self.manifest['files']['backup.py'],'worker_generation':self.plan['initial']['worker_generation'],
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

    def execute(self):
        from deployment.lib.control_plane_upgrade import SystemOperations,acquire_lock,atomic_json,BACKUP_TIMERS
        from deployment.lib.completed_normal_execution import protected_creation_mode,verify_serving
        from deployment.lib.completed_normal_write_handoff import CompletedNormalWriteHandoff
        from deployment.lib.completed_normal_backup import CompletedNormalBackupContext
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
                with self.credential():
                    self.event('sealed_schema146_runtime_verified')
                    kernel=self.candidate();kernel.verify_mode(normal=False)
                with self.credential():
                    self.event('normal_grant_pending')
                    measured_handoff=load('source_bound_fresh_write_boundary',self.package/'write-handoff.py')
                    handoff=measured_handoff.CompletedNormalWriteHandoff(self.contract,kernel,source_guard=self.guard,
                        boot_guard=self.actor.installation.installed,artifact_guard=lambda:self.evidence()[0])
                    handoff.grant(schema=146,fresh_attempt_root=self.scope);verify_serving(self.actor,schema=146,normal=True)
                    self.event('authenticated_live_write_pending')
                    write_result=load('continuation_measured_live_write',self.package/'write-probe.py').run(
                        self.actor,self.scope,digest(self.plan),self.plan['initial']['auth_gateway'])
                    exclusive(self.scope/'live-write-verification.json',encoded(write_result))
                    self.event('post_migration_backup_pending')
                    corrected=load('source_bound_schema146_backup',self.package/'backup.py')
                    class FreshBackup(CompletedNormalBackupContext):
                        def validate(context,plan,root,package):
                            if Path(package)!=driver.package:raise RuntimeError('backup_completion_payload_changed')
                            driver.guard()
                            super().validate(plan,root,driver.actor.package)
                        def capture(context):
                            return corrected.capture_and_replicate(context.plan,context.root,driver.package,context.source_guard,context.kernel,completed_context=context)
                    backup=FreshBackup(self.contract,self.actor.document,self.actor.package,kernel,
                        stage='post-migration',source_guard=self.guard,artifact_guard=lambda:self.evidence()[0])
                    # A failed scoped backup is immutable evidence, never retried.
                    from types import SimpleNamespace
                    backup.scope=digest({'operation':OPERATION,'plan_sha256':digest(self.plan),'stage':'post-migration'})
                    backup.plan=SimpleNamespace(digest=backup.scope,source_sha=self.contract['candidate']['source_sha'],candidate_images=self.contract['candidate']['images'])
                    receipt=backup.capture()
                    self.event('backup_timer_restore_pending');self.ops.restore_backup_timers()
                    result={'operation':self.contract['operation'],'context_sha256':self.actor.root.name,'schema':146,'mode':'NORMAL',
                        'application_sha':self.contract['candidate']['source_sha'],'controller_sha':self.controller,
                        'images':self.contract['candidate']['images'],'backup':receipt,
                        'backup_timers':{n:self.ops.systemctl_state(n) for n in BACKUP_TIMERS},'customer_database_restored':False,
                        'live_authenticated_write':write_result,
                        'continuation':{'operation':OPERATION,'plan_sha256':digest(self.plan),'source_sha256':self.source_hash,'source_git':self.manifest['source_git']}}
                    self.guard();verify_serving(self.actor,schema=146,normal=True)
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
            'parent_context_sha256':driver.actor.root.name,'initial':initial,'migrations':[],
            'target_schema':146,'restore_old_customer_database':False,'automatic_retry':False,'live_synthetic_account_verification':True}
        from deployment.lib.emergency_routing_repair import exclusive
        exclusive(driver.package/'plan.json',encoded(plan),mode=0o400)
        print(json.dumps({'preflight':'PASS','production_modified':False,'source_sha256':args.approved_source,'plan_sha256':digest(plan)}));return
    raw=secure(driver.package/'plan.json').read_bytes();driver.plan=json.loads(raw)
    if (hashlib.sha256(raw).hexdigest()!=args.approved_plan or raw!=encoded(driver.plan)
            or driver.plan['operation']!=OPERATION or driver.plan['source_sha256']!=args.approved_source
            or driver.plan['migrations']!=[] or driver.plan['target_schema']!=146
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
