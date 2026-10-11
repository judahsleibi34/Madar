"""Freshly approved SQL-only forward repair of an interrupted admitted upgrade.

The prior attempt and its grant are DATA, never renewed authorization. A new
immutable plan, root receipt and credential witness bind one new executor file.
This operation ends READ_ONLY at136; it never restores data or grants NORMAL.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import secrets
import traceback

from deployment.lib.completed_normal_admission import ADMISSIONS,digest,encoded,require_candidate_authority,credential_witness
from deployment.lib.provider_recovery_runtime import protected,readonly_configuration,file_digest
from deployment.lib.emergency_routing_repair import exclusive

OPERATION='completed-normal-schema115-136-forward-resumption'

def executor_path(state_root,sha,relative):
    if not isinstance(relative,str) or not re.fullmatch(r'execution\.json|resumptions/[0-9a-f]{64}/execution\.json',relative):
        raise RuntimeError('completed_forward_previous_execution_invalid')
    return Path(state_root)/'migrations'/sha/relative

def authorization_record(plan):
    return {'operation':OPERATION,'plan_sha256':digest(plan),
        'parent_context_sha256':plan['parent_context_sha256'],'source_bundle_sha256':plan['source_bundle_sha256'],
        'controller_sha':plan['controller_sha'],'application_sha':plan['application_sha']}

def scope_root(contract,plan):
    return ADMISSIONS/digest(contract)/'forward-resumptions'/digest(plan)

def validate_scope(contract,plan):
    keys={'version','operation','nonce','controller_sha','application_sha','source_bundle_sha256','parent_plan_sha256',
        'parent_context_sha256','observed_schema','database','previous_execution','previous_execution_sha256',
        'parent_failure_sha256','customer_snapshot_sha256','grant_sha256','runtime_sha256','worker_owner_sha256',
        'fixture_only','production_authorization'}
    if (not isinstance(plan,dict) or set(plan)!=keys or type(plan['version']) is not int or plan['version']!=1
            or plan['operation']!=OPERATION or not re.fullmatch('[0-9a-f]{32}',str(plan['nonce']))
            or plan['controller_sha']!=contract['candidate']['controller_sha']
            or plan['application_sha']!=contract['candidate']['source_sha']
            or plan['parent_plan_sha256']!=contract['plan_sha256'] or plan['parent_context_sha256']!=digest(contract)
            or type(plan['observed_schema']) is not int or not 115<=plan['observed_schema']<=136
            or plan['database']!=contract['database'] or type(plan['fixture_only']) is not bool
            or type(plan['production_authorization']) is not bool
            or plan['fixture_only']==plan['production_authorization']):
        raise RuntimeError('completed_forward_scope_invalid')
    for key in keys:
        if key.endswith('_sha256') and not re.fullmatch('[0-9a-f]{64}',str(plan[key])):
            raise RuntimeError('completed_forward_scope_invalid')
    executor_path(Path('/var/lib/madar/releases'),plan['application_sha'],plan['previous_execution'])

def authorize_witness(contract,plan):
    validate_scope(contract,plan)
    receipt=json.loads(protected(scope_root(contract,plan)/'operator-authorization.json',private=True).read_text())
    if receipt!=authorization_record(plan):raise RuntimeError('completed_forward_fresh_authorization_missing')
    return plan

def authorized_executor(contract,state_root):
    """A consumed parent execution can never authorize another executor."""
    plan=credential_witness('migration_resumption','migration_resumption_sha256')
    authorize_witness(contract,plan)
    prior=readonly_configuration(executor_path(state_root,plan['application_sha'],plan['previous_execution']),private=True)
    if file_digest(prior)!=plan['previous_execution_sha256']:
        raise RuntimeError('completed_forward_previous_execution_changed')
    root=ADMISSIONS/digest(contract)
    bindings=((root/'failure.json','parent_failure_sha256'),(root/'candidate-runtime.json','runtime_sha256'),
        (root/'write-authority/authority.json','grant_sha256'))
    if (any(file_digest(protected(path))!=plan[key] for path,key in bindings)
            or file_digest(readonly_configuration(Path(state_root)/'worker-ownership.json',private=True))!=plan['worker_owner_sha256']):
        raise RuntimeError('completed_forward_runtime_witness_changed')
    return plan,executor_path(state_root,plan['application_sha'],'resumptions/'+digest(plan)+'/execution.json')

def measure_plan(actor,*,nonce=None,previous_execution='execution.json'):
    """Read-only candidate/data measurement; no authorization or effects."""
    actor.guard();contract=actor.contract;root=actor.root
    if (root/'migration-completion.json').exists() or not (root/'migration-intent.json').exists():
        raise RuntimeError('completed_forward_incomplete_migration_required')
    failure=protected(root/'failure.json',private=True)
    if json.loads(failure.read_text()).get('phase')!='service_migrate_pending':
        raise RuntimeError('completed_forward_sql_failure_required')
    kernel=actor.candidate();require_candidate_authority(contract,mode='READ_ONLY');kernel.verify_mode(normal=False)
    from deployment.lib.completed_normal_database import migration_customer_snapshot
    original=json.loads(protected(root/'pre-migration-customer-snapshot.json',private=True).read_text())
    current=migration_customer_snapshot(contract,actor.runtime,columns=original['columns'])
    if (original.get('schema')!=115 or current['schema'] not in range(115,137)
            or set(current['roots'])!=set(original['roots'])
            or any(v!=current['roots'][k] for k,v in original['roots'].items() if k!='public.application_schema_state')):
        raise RuntimeError('completed_forward_current_customer_data_changed')
    prior=readonly_configuration(executor_path(actor.ops.state_root,contract['candidate']['source_sha'],previous_execution),private=True)
    record=json.loads(prior.read_text())
    if (record.get('release_sha')!=contract['candidate']['source_sha'] or record.get('status') not in {'running','failed'}
            or record.get('backup',{}).get('verified') is not True):
        raise RuntimeError('completed_forward_previous_execution_invalid')
    # The database controls committed progress. Prior records are bound as
    # historical data, not reused as independent execution or acceptance PASS.
    from deployment.lib.completed_normal_migration import intent_document
    if json.loads(protected(root/'migration-intent.json',private=True).read_text())!=intent_document(contract):
        raise RuntimeError('completed_forward_migration_intent_changed')
    manifest=json.loads(protected(actor.package/'source/web/deployment/releases/migrations-116-136.json').read_text())
    rows=record.get('migrations',[])
    if not isinstance(rows,list) or len(rows)>21:raise RuntimeError('completed_forward_previous_execution_invalid')
    for row,sql in zip(rows,manifest['migrations']):
        if (row.get('number')!=sql['number'] or row.get('checksum')!=sql['sha256']
                or row.get('status') not in {'applied','applying','already_applied'}):
            raise RuntimeError('completed_forward_previous_execution_invalid')
    result={'version':1,'operation':OPERATION,'nonce':nonce or secrets.token_hex(16),
        'controller_sha':contract['candidate']['controller_sha'],'application_sha':contract['candidate']['source_sha'],
        'source_bundle_sha256':actor.document['source_bundle_sha256'],'parent_plan_sha256':contract['plan_sha256'],
        'parent_context_sha256':digest(contract),'observed_schema':current['schema'],'database':contract['database'],
        'previous_execution':previous_execution,'previous_execution_sha256':file_digest(prior),
        'parent_failure_sha256':file_digest(failure),'customer_snapshot_sha256':digest(current),
        'grant_sha256':file_digest(protected(root/'write-authority/authority.json')),
        'runtime_sha256':file_digest(protected(root/'candidate-runtime.json',private=True)),
        'worker_owner_sha256':file_digest(readonly_configuration(actor.ops.state_root/'worker-ownership.json',private=True)),
        'fixture_only':actor.document.get('fixture_only') is True,'production_authorization':actor.document.get('fixture_only') is not True}
    validate_scope(contract,result);actor.guard();return result

class CompletedNormalForwardResumption:
    def __init__(self,actor,plan,*,artifact_guard,rehearsal_guard):
        if not all(callable(x) for x in (artifact_guard,rehearsal_guard)):
            raise RuntimeError('completed_forward_independent_guards_required')
        self.actor,self.plan=actor,plan;self.artifact_guard,self.rehearsal_guard=artifact_guard,rehearsal_guard
        validate_scope(actor.contract,plan);self.root=scope_root(actor.contract,plan);self.phase='preflight'
    def preflight(self):
        self.artifact_guard();self.rehearsal_guard()
        if self.root.parent.exists() or self.root.parent.is_symlink():
            from deployment.lib.control_plane_filesystem import require_root_protected_directory
            require_root_protected_directory(self.root.parent)
        if measure_plan(self.actor,nonce=self.plan['nonce'],previous_execution=self.plan['previous_execution'])!=self.plan:
            raise RuntimeError('completed_forward_live_bindings_changed')
        if self.root.exists() or self.root.is_symlink():raise RuntimeError('completed_forward_attempt_already_consumed')
        return {'schema':self.plan['observed_schema'],'mode':'READ_ONLY','production_modified':False,'authorization_consumed':False}
    @contextmanager
    def credential(self):
        from deployment.lib.completed_normal_execution import CompletedNormalUpgrade
        # Reuse the existing root credential lifecycle; its optional witness
        # binds this fresh operation, not a reconstructed historical token.
        from types import SimpleNamespace
        binding=SimpleNamespace(ops=self.actor.ops,controller=self.plan['controller_sha'],contract=self.actor.contract)
        with CompletedNormalUpgrade.root_credential(binding,migration_resumption=self.plan):yield
    def execute(self):
        from deployment.lib.control_plane_upgrade import acquire_lock
        from deployment.lib.completed_normal_database import migration_customer_snapshot,verify_migration_customer_preservation
        from deployment.lib.completed_normal_migration import seal_completion
        from deployment.lib.completed_normal_execution import protected_creation_mode,verify_serving
        if os.geteuid()!=0:raise RuntimeError('completed_forward_root_required')
        self.preflight();lock=acquire_lock(self.actor.ops.upgrade_root/'upgrade.lock',create=False)
        try:
            with protected_creation_mode():
                self.preflight();self.root.parent.mkdir(mode=0o700,exist_ok=True)
                from deployment.lib.control_plane_filesystem import require_root_protected_directory
                require_root_protected_directory(self.root.parent);self.root.mkdir(mode=0o700)
                exclusive(self.root/'plan.json',encoded(self.plan),mode=0o400)
                exclusive(self.root/'operator-authorization.json',encoded(authorization_record(self.plan)),mode=0o400)
                self.phase='migration_pending'
                self.actor.ops.run_deploy_service('completed_forward_migrate',self.plan['controller_sha'],
                    completed_normal_contract=self.actor.contract,completed_normal_mode='migrate',migration_resumption=self.plan)
                with self.credential():
                    original=json.loads(protected(self.actor.root/'pre-migration-customer-snapshot.json',private=True).read_text())
                    current=migration_customer_snapshot(self.actor.contract,self.actor.runtime,columns=original['columns'])
                    preservation=verify_migration_customer_preservation(original,current)
                    exclusive(self.root/'customer-preservation.json',encoded(preservation))
                    path=executor_path(self.actor.ops.state_root,self.plan['application_sha'],'resumptions/'+digest(self.plan)+'/execution.json')
                    seal_completion(self.actor.contract,self.actor.ops.state_root/'releases'/self.plan['application_sha'],self.actor.ops.state_root,
                        source_guard=self.actor.guard,runtime_guard=self.actor.native,execution_path=path)
                self.phase='read_only_refresh_pending'
                self.actor.ops.run_deploy_service('completed_forward_refresh',self.plan['controller_sha'],
                    completed_normal_contract=self.actor.contract,completed_normal_mode='refresh',migration_resumption=self.plan)
                with self.credential():observed=verify_serving(self.actor,schema=136,normal=False)
                result={'operation':OPERATION,'plan_sha256':digest(self.plan),'schema':136,'mode':'READ_ONLY',
                    'database_restored':False,'normal_grant_issued':False,'separate_normal_completion_required':True,'serving':observed}
                exclusive(self.root/'completion.json',encoded(result));self.actor.ops.clear_interlock();return result
        except Exception as error:
            if self.root.exists():
                try:self.actor.compensate();self.actor.ops.requiesce_backup_timers_for_failure()
                finally:
                    exclusive(self.root/'failure.json',encoded({'phase':self.phase,'exception_type':type(error).__name__,
                        'frames':[{'source':Path(f.filename).name,'line':f.lineno,'function':f.name} for f in traceback.extract_tb(error.__traceback__)[-16:]],
                        'database_restored':False}))
            raise
        finally:self.actor.ops.clear_authorization();self.actor.ops.close_locks();os.close(lock)
