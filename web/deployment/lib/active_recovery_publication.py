"""Normal-local configuration/state outputs under a fresh write-boundary plan.

Does not grant writes, alter historical recovery transactions, restore customer
rows or enable timers. Exact prior configuration/state are retained root-private.
A failure is compensated with CURRENT-data restrictions, not stale state/data.
"""
from dataclasses import asdict
import json
import os
from pathlib import Path
import pwd
import shlex
from deployment.lib.active_recovery_resumption import ROOT
from deployment.lib.active_recovery_inputs import INPUTS
from deployment.lib.emergency_routing_repair import exclusive,encoded
from deployment.lib.provider_recovery_runtime import readonly_configuration,protected,file_digest,digest
from deployment.lib.provider_local_backup_configuration import publish_backup_configuration
from deployment.lib.release_deployer import atomic_json
from deployment.lib.runtime_authority import runtime_mutation_lock
from deployment.lib.environment_file import load_environment_file

class ActiveRecoveryNormalPublication:
    def __init__(self,plan,candidate,root,source_guard,runtime_verifier):
        if not callable(source_guard):raise RuntimeError('normal_publication_source_guard_required')
        self.plan,self.candidate,self.root=plan,candidate,Path(root)
        self.source_guard,self.runtime_verifier=source_guard,runtime_verifier
    def guard(self):
        self.source_guard()
        if os.geteuid()!=0 or self.root!=ROOT/self.plan.digest:raise RuntimeError('normal_publication_fresh_root_required')
        receipt=json.loads(protected(self.root/'authorization.json',private=True).read_text())
        events=[json.loads(line) for line in protected(self.root/'events.jsonl',private=True).read_text().splitlines()]
        if (receipt.get('operation')!='active-local-rollback-resumption' or receipt.get('plan_sha256')!=self.plan.digest
                or receipt.get('source_bundle_sha256')!=self.plan.source_bundle_sha256
                or not events or events[-1].get('phase')!='write_grant_pending'
                or events[-1].get('normal_writes_may_have_occurred') is not True
                or any(row.get('plan_sha256')!=self.plan.digest for row in events)):
            raise RuntimeError('normal_publication_phase_denied')
        self.runtime_verifier.read_only(workers_started=True)
        for key in ('production_configuration','backup_configuration','release_state','traffic'):
            if file_digest(readonly_configuration(INPUTS[key],private=True))!=self.plan.retained_inputs[key]:
                raise RuntimeError('normal_publication_input_changed')
        self.source_guard()
    def publish(self):
        self.guard()
        configuration=dict(self.candidate.config)
        if (configuration.get('SUPABASE_URL')!='http://madar-supabase:8000'
                or any(not isinstance(value,str) or '\n' in value or '\r' in value for value in configuration.values())):
            raise RuntimeError('normal_publication_environment_invalid')
        native={}
        load_environment_file(readonly_configuration(INPUTS['native_configuration'],private=True),environ=native)
        state=json.loads(readonly_configuration(INPUTS['release_state'],private=True).read_text())
        contract=self.candidate.contract
        state['active_slot']=self.candidate.slot
        state['known_good_release']={'sha':contract.sha,'slot':self.candidate.slot,'images':dict(contract.images),
            'schema':115,'schema_compatible_min':115,'schema_compatible_max':115,'provider':'local',
            'worker_generation':digest(asdict(contract)),'migration_policy':'none','runtime_only_rollback':True}
        # Keep the historical context; this NEW continuation is the normal overlay.
        state['normal_local_resumption']=self.plan.digest
        traffic={'sha':contract.sha,'slot':self.candidate.slot,'schema':115,'provider':'local',
            'database_restore':False,'normal_transition':True,'normal_local_resumption':self.plan.digest}
        identity=pwd.getpwnam('madar')
        with runtime_mutation_lock(self.candidate.state):
            self.guard()
            for key in ('production_configuration','release_state','traffic'):
                exclusive(self.root/('pre-normal-'+key),readonly_configuration(INPUTS[key],private=True).read_bytes())
            exclusive(self.root/'normal-publication-begin.json',encoded({'version':1,'plan_sha256':self.plan.digest,
                'source_sha':self.plan.source_sha,'database_restore':False,'historical_transactions_modified':False}))
            publish_backup_configuration(self.root,{'backup_configuration_before_digest':self.plan.retained_inputs['backup_configuration']},contract,native)
            production=INPUTS['production_configuration'];temporary=production.with_name('.continuation-'+self.plan.digest[:12]+'.env')
            with temporary.open('x') as stream:
                os.fchmod(stream.fileno(),0o600);os.fchown(stream.fileno(),identity.pw_uid,identity.pw_gid)
                for key,value in sorted(configuration.items()):stream.write(key+'='+shlex.quote(value)+'\n')
                stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,production)
            descriptor=os.open(production.parent,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(descriptor)
            finally:os.close(descriptor)
            for key,payload in [('release_state',state),('traffic',traffic)]:
                atomic_json(INPUTS[key],payload);os.chown(INPUTS[key],identity.pw_uid,identity.pw_gid)
            exclusive(self.root/'normal-publication.json',encoded({'version':1,'plan_sha256':self.plan.digest,
                'source_sha':self.plan.source_sha,'published_sha256':{key:file_digest(INPUTS[key]) for key in
                    ('production_configuration','backup_configuration','release_state','traffic')},
                'business_write_authority_published':False,'database_restore':False}))
        self.candidate.require_write_authority(contract,'READ_ONLY')
        self.source_guard()
