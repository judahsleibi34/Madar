"""Fresh authorization protocol for an already-active local rollback.

This continuation is a NEW transaction. It never edits a historical receipt,
reconstructs /run credentials, or calls the legacy provider402 authorize path.
Privileged effects belong to a separately reviewed, exact-source adapter. This
protocol alone is not an installed or executable production repair capability.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

from deployment.lib.provider_recovery_runtime import digest, protected, file_digest
from deployment.lib.active_recovery_inputs import KEYS

HASH = re.compile(r'[0-9a-f]{64}')
ROOT = Path('/var/lib/madar-control-plane/normal-local-resumption')
PHASES = {'authorized', 'detached_candidate_pending', 'detached_candidate_failed', 'detached_candidate_ready', 'compensation_preparation_failed', 'read_only_handoff_pending',
          'read_only_serving', 'controller_resume_pending', 'controller_resumed',
          'standby_ready', 'write_grant_pending', 'normal', 'compensation_pending',
          'restricted_fallback', 'compensation_failed'}


@dataclass(frozen=True)
class ResumptionPlan:
    source_sha: str
    source_bundle_sha256: str
    candidate_images: dict
    retained_inputs: dict
    fallback: dict
    checkpoint_manifest_sha256: str
    checkpoint_execution_sha256: str
    reconciliation_execution_sha256: str
    acceptance_execution_sha256: str
    emergency_installation_sha256: str
    schema: int = 115
    migration_policy: str = 'none'
    restore_customer_database: bool = False
    convergence_seconds: int = 180
    compensation_seconds: int = 60
    prior_backup_timer_preimage: dict | None = None
    candidate_destination: dict | None = None

    def validate(self):
        if not re.fullmatch(r'[0-9a-f]{40}', self.source_sha):
            raise RuntimeError('resumption_source_invalid')
        for key in ('source_bundle_sha256', 'checkpoint_manifest_sha256', 'checkpoint_execution_sha256',
                    'reconciliation_execution_sha256', 'acceptance_execution_sha256', 'emergency_installation_sha256'):
            if not HASH.fullmatch(getattr(self, key)):
                raise RuntimeError('resumption_evidence_binding_invalid')
        if (type(self.schema) is not int or self.schema != 115 or self.migration_policy != 'none'
                or self.restore_customer_database is not False or self.convergence_seconds != 180
                or self.compensation_seconds != 60):
            raise RuntimeError('resumption_scope_invalid')
        destination=self.candidate_destination
        if destination is not None:
            import ipaddress
            fields={'slot','backend_port','frontend_port','retained_slot','retained_source_sha','redis_name','redis_network','redis_network_id','subnet','retired_port_declarations'}
            optional={'previous_candidate'} if 'previous_candidate' in destination else set()
            if (set(destination)!=fields|optional or destination['slot'] not in {'blue','green'}
                    or destination['retained_slot'] not in {'blue','green'} or destination['slot']==destination['retained_slot']
                    or (destination['backend_port'],destination['frontend_port'])!={'blue':(8101,3100),'green':(8201,3200)}[destination['slot']]
                    or not re.fullmatch('[0-9a-f]{40}',destination['retained_source_sha'])
                    or not HASH.fullmatch(destination['redis_network_id'])
                    or not re.fullmatch('madar-provider402-rehearsal-[0-9a-f]{12}-candidate-redis',destination['redis_name'])
                    or destination['redis_network']!=destination['redis_name'][:-6]+'-'+destination['retained_slot']+'-runtime'
                    or ipaddress.ip_network(destination['subnet']).prefixlen!=24
                    or not ipaddress.ip_network(destination['subnet']).subnet_of(ipaddress.ip_network('10.253.0.0/16'))):
                raise RuntimeError('resumption_candidate_destination_invalid')
            retired=destination['retired_port_declarations']
            previous=destination.get('previous_candidate')
            if previous is not None and (set(previous)!={'plan_sha256','evidence_sha256'} or any(not HASH.fullmatch(str(v)) for v in previous.values())):
                raise RuntimeError('resumption_previous_candidate_invalid')
            if not isinstance(retired,dict) or len(retired)>(4 if previous else 2):raise RuntimeError('resumption_retired_declarations_invalid')
            for name,value in retired.items():
                if (not (re.fullmatch('madar-'+destination['slot']+'-(backend|frontend)-legacy-[0-9a-f]{12}',name) or (previous and re.fullmatch('madar-normal-'+previous['plan_sha256'][:12]+'-(backend|frontend)',name)))
                        or set(value)!={'container_id','image_id','spec_sha256'}
                        or not HASH.fullmatch(value['container_id']) or not HASH.fullmatch(value['spec_sha256'])
                        or not re.fullmatch('sha256:[0-9a-f]{64}',value['image_id'])):
                    raise RuntimeError('resumption_retired_declarations_invalid')
        prior=self.prior_backup_timer_preimage
        if prior is not None and (not isinstance(prior,dict)
                or set(prior)!={'plan_sha256','evidence_sha256','timer_preimage_sha256'}
                or any(not HASH.fullmatch(str(value)) for value in prior.values())):
            raise RuntimeError('resumption_prior_timer_binding_invalid')
        if set(self.candidate_images) != {'backend','frontend'} or any(
                not re.fullmatch(r'sha256:[0-9a-f]{64}', str(value)) for value in self.candidate_images.values()):
            raise RuntimeError('resumption_candidate_images_invalid')
        if set(self.retained_inputs) != KEYS or any(not HASH.fullmatch(str(value)) for value in self.retained_inputs.values()):
            raise RuntimeError('resumption_retained_binding_invalid')
        if set(self.fallback) != {'backend', 'frontend'}:
            raise RuntimeError('resumption_fallback_binding_invalid')
        for role, identity in self.fallback.items():
            if (set(identity) != {'container_id','image_id','spec_sha256'}
                    or not HASH.fullmatch(str(identity['container_id']))
                    or not HASH.fullmatch(str(identity['spec_sha256']))
                    or not re.fullmatch(r'sha256:[0-9a-f]{64}', str(identity['image_id']))):
                raise RuntimeError('resumption_fallback_binding_invalid')

    @property
    def digest(self):
        return digest(asdict(self))


def load_saved_resumption_plan(root):
    """Read the exact approved plan bytes from its protected durable namespace."""
    root=Path(root);path=protected(root/'plan.json',private=True)
    plan=ResumptionPlan(**json.loads(path.read_text()));plan.validate()
    if root!=ROOT/plan.digest or file_digest(path)!=plan.digest:
        raise RuntimeError('resumption_saved_plan_bytes_changed')
    return plan


class ActiveRecoveryResumption:
    """Ordering protocol: read-only public handoff precedes protected mutations.

    Three distinct boundaries: detached READ_ONLY staging, read-only routing
    handoff, and positive write grant. Workers must be healthy non-consuming
    standbys until the final atomic grant. Every failing post-handoff operation
    invokes current-data restricted fallback, never stale checkpoint restoration.
    """
    def __init__(self, plan, operations):
        plan.validate()
        self.plan, self.ops = plan, operations
        self.root = ROOT / plan.digest
        self.authorization = self.root/'authorization.json'
        self.journal = self.root/'events.jsonl'
        self.phase = None

    def event(self, phase, **fields):
        if phase not in PHASES:
            raise RuntimeError('resumption_phase_invalid')
        payload={'version':1,'plan_sha256':self.plan.digest,'phase':phase,
                 'observed_at':datetime.now(timezone.utc).isoformat(),**fields}
        # Append-only records, never replace the prior installation/status.
        if self.journal.exists():
            protected(self.journal,private=True)
        descriptor=os.open(self.journal,os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,'a') as stream:
            json.dump(payload,stream,sort_keys=True);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        self.phase=phase

    def authorize(self, *, approved_plan, approved_source):
        if os.geteuid()!=0 or approved_plan!=self.plan.digest or approved_source!=self.plan.source_bundle_sha256:
            raise RuntimeError('resumption_fresh_explicit_approval_required')
        # All independent observations/evidence must precede ANY runtime effect.
        self.ops.verify_frozen_source(self.plan)
        self.ops.verify_actual_execution_evidence(self.plan)
        self.ops.verify_active_rollback_inputs(self.plan)
        self.ops.verify_emergency_installation(self.plan)
        self.ops.verify_restricted_fallback(self.plan)
        self.ops.require_all_consumers_stopped()
        self.ops.require_no_normal_write_authority()
        dependencies=self.ops.capture_verified_runtime_dependencies(self.plan)
        if not isinstance(dependencies,dict) or digest(dependencies)!=self.plan.retained_inputs['runtime_dependencies']:
            raise RuntimeError('resumption_dependency_capture_changed')
        self.ops.exclusive_private_namespace(self.root)
        with self.authorization.open('x') as stream:
            os.chmod(self.authorization,0o600)
            json.dump({'version':1,'operation':'active-local-rollback-resumption','plan_sha256':self.plan.digest,
                'source_bundle_sha256':self.plan.source_bundle_sha256,
                'authorized_at':datetime.now(timezone.utc).isoformat()},stream,sort_keys=True)
            stream.write('\n');stream.flush();os.fsync(stream.fileno())
        for name,payload in [('plan.json',asdict(self.plan)),('runtime-dependencies.json',dependencies)]:
            with (self.root/name).open('x') as stream:
                os.fchmod(stream.fileno(),0o600)
                json.dump(payload,stream,sort_keys=True)
                if name!='plan.json':stream.write('\n')
                stream.flush();os.fsync(stream.fileno())
        self.event('authorized')

    def require_authorized(self):
        if os.geteuid()!=0:
            raise RuntimeError('resumption_root_entry_required')
        receipt=json.loads(protected(self.authorization,private=True).read_text())
        if (receipt.get('operation')!='active-local-rollback-resumption' or receipt.get('plan_sha256')!=self.plan.digest
                or receipt.get('source_bundle_sha256')!=self.plan.source_bundle_sha256):
            raise RuntimeError('resumption_authorization_changed')
        plan_path=protected(self.root/'plan.json',private=True)
        if file_digest(plan_path)!=self.plan.digest:raise RuntimeError('resumption_sealed_plan_bytes_changed')
        saved=json.loads(plan_path.read_text())
        if saved!=asdict(self.plan):raise RuntimeError('resumption_sealed_plan_changed')
        dependencies=json.loads(protected(self.root/'runtime-dependencies.json',private=True).read_text())
        if digest(dependencies)!=self.plan.retained_inputs['runtime_dependencies']:
            raise RuntimeError('resumption_dependency_capture_changed')
        self.ops.verify_frozen_source(self.plan)
        self.ops.verify_actual_execution_evidence(self.plan)

    def execute(self):
        self.require_authorized()
        with self.ops.upgrade_lock(), self.ops.deploy_lock():
            self.ops.require_unused_attempt(self.root)
            self.ops.verify_active_rollback_inputs(self.plan)
            self.ops.verify_emergency_installation(self.plan)
            self.ops.require_all_consumers_stopped()
            self.ops.require_no_normal_write_authority()
            # Names, authority path and files are separate from the emergency
            # relay's pinned namespace and six-consumer inventory.
            # Claim this approved attempt durably before its first staging
            # effect. An interrupted/failed staging cannot silently retry.
            self.event('detached_candidate_pending')
            try:
                self.ops.quiesce_backup_timers_before_staging(self.plan,self.root)
                self.ops.stage_detached_read_only_candidate(self.plan,self.root)
                self.ops.verify_detached_candidate(self.plan,workers_required=False)
                self.ops.verify_active_rollback_inputs(self.plan)
                self.ops.verify_emergency_installation(self.plan)
            except Exception as error:
                self.event('detached_candidate_failed',exception_type=type(error).__name__)
                raise
            self.event('detached_candidate_ready')
            # Safe compensation must exist before the first public publication.
            try:
                self.ops.prepare_current_data_compensation(self.plan,self.root)
            except Exception as error:
                # Public routing has not been published. Preserve the original
                # serving installation; consume this attempt and retain every
                # partially prepared resource for governed diagnosis.
                self.event('compensation_preparation_failed',exception_type=type(error).__name__)
                raise
            self.event('read_only_handoff_pending')
            try:
                self.ops.publish_read_only_handoff(self.plan,self.root)
                self.ops.require_sustained_read_only_serving(self.plan,deadline_seconds=180,
                    consecutive_rounds=3,minimum_span_seconds=5)
                self.event('read_only_serving')
                self.ops.require_emergency_routing_handoff_complete()
                self.event('controller_resume_pending')
                self.ops.install_and_attest_governed_controller(self.plan,self.root)
                self.ops.establish_source_fence_and_reconcile(self.plan,self.root)
                self.event('controller_resumed')
                self.ops.establish_single_worker_owner(self.plan,self.root)
                self.ops.start_nonconsuming_standbys(self.plan,self.root)
                self.ops.verify_standby_workers(self.plan)
                self.ops.verify_read_only_acceptance(self.plan)
                self.event('standby_ready')
                self.ops.require_exact_source_and_images(self.plan)
                self.ops.verify_restricted_fallback(self.plan)
                self.ops.verify_single_owner_and_standbys(self.plan)
                self.ops.verify_final_write_grant_prerequisites(self.plan)
                # Durable write boundary precedes the atomic authority grant;
                # compensation thereafter may only preserve the CURRENT DB.
                self.event('write_grant_pending',normal_writes_may_have_occurred=True)
                self.ops.commit_normal_release_and_grant_writes(self.plan,self.root)
                self.ops.verify_normal_acceptance(self.plan)
                self.ops.capture_replicate_and_verify_post_cutover_backup(self.plan,self.root)
                self.event('normal')
                self.ops.restore_configured_backup_timers(self.plan,self.root)
            except Exception as error:
                self.compensate(type(error).__name__)
                raise
        return {'plan_sha256':self.plan.digest,'phase':self.phase}

    def compensate(self, exception_type):
        # Failure to retain a report must not prevent compensation.
        try:self.event('compensation_pending',exception_type=exception_type)
        except OSError:pass
        try:
            self.ops.fence_normal_writes_and_stop_consumers(self.plan)
            self.ops.publish_verified_current_data_fallback(self.plan,self.root,deadline_seconds=60)
            self.ops.verify_restricted_fallback_serving(self.plan)
        except Exception as error:
            self.ops.activate_maintenance_or_stop_proxy(self.plan,self.root)
            try:self.event('compensation_failed',exception_type=type(error).__name__)
            except OSError:pass
            raise
        try:self.event('restricted_fallback')
        except OSError:pass
