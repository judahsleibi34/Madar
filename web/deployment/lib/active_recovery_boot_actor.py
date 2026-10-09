"""Exact-plan boot actor using the durable continuation, never lost /run data.

This actor cannot create an authorization or replay an incomplete positive grant.
Interrupted publication uses current-data fencing and compensation. Completed
NORMAL requires the retained source-bound completion and post-cutover execution.
"""
import json
from pathlib import Path
from deployment.lib.active_recovery_resumption import ActiveRecoveryResumption, ROOT, PHASES
from deployment.lib.active_recovery_source import FrozenContinuationSource
from deployment.lib.active_recovery_candidate import DetachedRecoveryCandidate
from deployment.lib.active_recovery_workers import ActiveRecoveryWorkerHandoff
from deployment.lib.active_recovery_runtime import ActiveRecoveryRuntime
from deployment.lib.active_recovery_boot import ActiveRecoveryNormalBoot
from deployment.lib.active_recovery_inputs import INPUTS, observe_retained_inputs, verify_native_continuation_dependencies
from deployment.lib.active_recovery_fallback import CurrentDataFallback, CompensationPublication, FALLBACK_ROUTE
from deployment.lib.emergency_routing_repair import Runtime, UPSTREAM, MAINTENANCE, verify, spec
from deployment.lib.provider_recovery_runtime import protected, readonly_configuration, file_digest

EARLY_PHASES=frozenset({'authorized','detached_candidate_pending','detached_candidate_failed',
    'detached_candidate_ready','compensation_preparation_failed'})

class ActiveRecoveryBootActor:
    def __init__(self,plan,root,package):
        self.plan,self.root,self.package=plan,Path(root),Path(package)
        self.source=FrozenContinuationSource(plan,self.package)
        self.runtime=Runtime();self.runtime.expected_nginx_sha256=plan.retained_inputs['proxy_configuration']
        self.fallback=CurrentDataFallback(plan,self.root,runtime=self.runtime)
        self.compensation=CompensationPublication(self.fallback,self.root,runtime=self.runtime)
        self.candidate=None;self.workers=None;self.kernel=None
    def phase(self):
        self.source.verify()
        receipt=json.loads(protected(self.root/'authorization.json',private=True).read_text())
        plan_path=protected(self.root/'plan.json',private=True)
        if file_digest(plan_path)!=self.plan.digest:raise RuntimeError('boot_actor_plan_bytes_changed')
        saved=json.loads(plan_path.read_text())
        from dataclasses import asdict
        if (self.root!=ROOT/self.plan.digest or saved!=asdict(self.plan)
                or receipt.get('operation')!='active-local-rollback-resumption'
                or receipt.get('plan_sha256')!=self.plan.digest
                or receipt.get('source_bundle_sha256')!=self.plan.source_bundle_sha256):
            raise RuntimeError('boot_actor_fresh_authorization_changed')
        events=[json.loads(line) for line in protected(self.root/'events.jsonl',private=True).read_text().splitlines()]
        if not events or any(row.get('plan_sha256')!=self.plan.digest or row.get('phase') not in PHASES
                or type(row.get('version')) is not int or row['version']!=1 for row in events):
            raise RuntimeError('boot_actor_journal_changed')
        return events[-1]['phase']
    def assemble(self):
        self.candidate=DetachedRecoveryCandidate.from_saved_runtime(self.plan,self.root,self.source.verify)
        self.workers=ActiveRecoveryWorkerHandoff(self.plan,self.candidate,self.root,self.source.verify)
        self.kernel=ActiveRecoveryRuntime(self.plan,self.candidate,self.root,self.source.verify,self.workers,runtime=self.runtime)
    def completed_evidence(self):
        # This NEW completion must be written by the independently executing
        # final adapter after actual normal acceptance and post-cutover backup.
        # It cannot be substituted with an older recovery PASS receipt.
        self.source.verify()
        completion=json.loads(protected(self.root/'normal-completion.json',private=True).read_text())
        if (completion.get('operation')!='completed-normal-local-continuation'
                or completion.get('plan_sha256')!=self.plan.digest
                or completion.get('source_sha')!=self.plan.source_sha
                or completion.get('source_bundle_sha256')!=self.plan.source_bundle_sha256
                or completion.get('images')!=self.plan.candidate_images
                or completion.get('schema')!=115 or completion.get('database_restore_performed') is not False):
            raise RuntimeError('boot_actor_completion_binding_changed')
        bound=completion.get('retained_execution_files',{})
        required={'normal-acceptance.json','post-cutover-backup.json','installed-controller.json','worker-owner.json','normal-publication.json'}
        if set(bound)!=required:raise RuntimeError('boot_actor_complete_execution_required')
        for name,expected in bound.items():
            if file_digest(protected(self.root/name,private=True))!=expected:
                raise RuntimeError('boot_actor_completed_execution_changed')
        # Installed source must still be the approved source, not just a retained
        # historical successful installer transcript.
        if protected(INPUTS['controller']).read_text().strip()!=self.plan.source_sha:
            raise RuntimeError('boot_actor_installed_source_changed')
        manifest=self.source.verify()
        for relative,expected in manifest['files'].items():
            # The installer is a frozen source tool executed from the governed
            # stage, not an installed runtime entrypoint. Its package bytes were
            # already measured above; all installed controller bytes still match.
            if relative=='web/deployment/bin/madar-install-control-plane':continue
            if relative.startswith('web/deployment/'):
                actual=INPUTS['controller'].parent/relative.removeprefix('web/deployment/')
                if file_digest(protected(actual))!=expected:
                    raise RuntimeError('boot_actor_installed_code_changed')
        publication=json.loads(protected(self.root/'normal-publication.json',private=True).read_text())
        outputs=publication.get('published_sha256',{})
        if set(outputs)!={'production_configuration','backup_configuration','release_state','traffic'}:
            raise RuntimeError('boot_actor_normal_configuration_incomplete')
        for key,expected in outputs.items():
            if file_digest(readonly_configuration(INPUTS[key],private=True))!=expected:
                raise RuntimeError('boot_actor_normal_configuration_changed')
    def native(self):return verify_native_continuation_dependencies(self.plan,self.root,self.runtime)
    def fallback_public_round(self,route):
        if UPSTREAM.read_bytes()!=route:raise RuntimeError('boot_actor_fallback_route_changed')
        endpoints=self.fallback.verify()
        source=self.runtime.json_http('http://%s:%d/health/version'%endpoints['backend'])
        for base in ('http://127.0.0.1:8001','http://127.0.0.1:3000/api'):
            if (self.runtime.json_http(base+'/health/version')!=source
                    or self.runtime.json_http(base+'/health/recovery')!={'restricted':True,'business_writes_enabled':False}):
                raise RuntimeError('boot_actor_public_fallback_binding_changed')
            self.runtime.denied(base)
        self.runtime.http_status('http://127.0.0.1:3000/')
    def stop_bound_runtimes_for_failed_compensation(self):
        self.source.verify()
        receipt=json.loads(protected(self.root/'authorization.json',private=True).read_text())
        if (receipt.get('operation')!='active-local-rollback-resumption'
                or receipt.get('plan_sha256')!=self.plan.digest
                or receipt.get('source_bundle_sha256')!=self.plan.source_bundle_sha256):
            raise RuntimeError('boot_actor_stop_authorization_changed')
        bindings=json.loads(protected(self.root/'candidate-identities.json',private=True).read_text())
        if bindings.get('plan_sha256')!=self.plan.digest:raise RuntimeError('boot_actor_stop_binding_changed')
        failures=[]
        for kind in ('notification','calendar-sync','data-deletion','backend'):
            try:
                expected=bindings['runtimes'][kind]
                rows=self.runtime.inspect([expected['id']])
                row=next(value for value in rows.values() if value['Id']==expected['id'])
                if row['Image']!=expected['image'] or spec(row)!=expected['spec_sha256']:
                    raise RuntimeError('boot_actor_compensation_identity_changed')
                self.runtime.command(['docker','update','--restart=no',row['Id']])
                self.runtime.command(['docker','stop',row['Id']])
            except Exception as error:failures.append(type(error).__name__)
        if failures:raise RuntimeError('boot_actor_compensation_stop_incomplete')

    def compensate(self):
        self.source.verify()
        # Journal failure cannot prevent revocation. No stale controller,
        # configuration, ownership, checkpoint or customer data is restored.
        transaction=ActiveRecoveryResumption(self.plan,None)
        try:transaction.event('compensation_pending',exception_type='InterruptedContinuation')
        except OSError:pass
        try:
            self.candidate._publish_write_authority(self.candidate.contract,'READ_ONLY')
            self.candidate.require_write_authority(self.candidate.contract,'READ_ONLY')
            self.workers.stop_consumers()
            self.compensation.publish(self.fallback_public_round)
            transaction.event('restricted_fallback')
        except Exception:
            # If an authority cannot be revoked, stop the exact bound application
            # as well as the proxy. Never start an unverified fallback or worker.
            try:
                self.stop_bound_runtimes_for_failed_compensation()
            finally:
                self.compensation.maintenance_or_stop_proxy()
                try:transaction.event('compensation_failed',exception_type='CompensationFailure')
                except OSError:pass
            raise
    def resume(self):
        phase=self.phase()
        if phase in EARLY_PHASES:
            # No public handoff occurred. Preserve the exact functioning original
            # route/helper rather than activating an unnecessary replacement.
            if observe_retained_inputs()!=self.plan.retained_inputs:
                raise RuntimeError('boot_actor_early_recovery_changed')
            verify(self.runtime)
            return {'phase':phase,'mode':'ORIGINAL_RESTRICTED_RECOVERY'}
        self.assemble()
        if phase=='normal':
            try:self.candidate.require_write_authority(self.candidate.contract,'NORMAL')
            except RuntimeError:
                self.compensate()
                return {'phase':'restricted_fallback','mode':'READ_ONLY'}
            return ActiveRecoveryNormalBoot(self.plan,self.root,self.candidate,self.kernel,self.source.verify,
                self.completed_evidence,self.native,self.compensate,runtime=self.runtime).execute()
        if phase=='restricted_fallback':
            self.fallback.verify()
            if UPSTREAM.read_bytes()!=FALLBACK_ROUTE:raise RuntimeError('boot_actor_restricted_route_changed')
            return {'phase':phase,'mode':'READ_ONLY'}
        if phase=='compensation_failed':raise RuntimeError('boot_actor_compensation_requires_operator')
        self.compensate()
        return {'phase':'restricted_fallback','mode':'READ_ONLY'}
    def proxy_gate(self):
        phase=self.phase()
        if phase in EARLY_PHASES:
            if observe_retained_inputs()!=self.plan.retained_inputs:raise RuntimeError('boot_actor_early_recovery_changed')
            verify(self.runtime);return
        self.assemble()
        if phase=='normal':
            self.completed_evidence();self.native();self.kernel.normal(require_public=False)
            route=(f'upstream madar_backend_active {{ server 127.0.0.1:{self.candidate.backend_port}; }}\n'
                f'upstream madar_frontend_active {{ server 127.0.0.1:{self.candidate.frontend_port}; }}\n').encode()
        elif phase=='restricted_fallback':self.fallback.verify();route=FALLBACK_ROUTE
        else:raise RuntimeError('boot_actor_proxy_gate_denied')
        if UPSTREAM.read_bytes()!=route:raise RuntimeError('boot_actor_proxy_route_changed')
