"""Governed single-owner handoff to non-consuming normal-local standbys.

Only a freshly approved continuation after sustained read-only publication may
use this component. Original slot resources and ownership bytes are retained.
No database, historical transaction, emergency helper or write grant is changed.
"""
from dataclasses import asdict
import json
import os
import pwd
import time
from pathlib import Path
from deployment.lib.active_recovery_resumption import ROOT
from deployment.lib.active_recovery_candidate import KINDS
from deployment.lib.emergency_routing_repair import spec,exclusive,encoded,AvailabilityFailure
from deployment.lib.provider_recovery_runtime import protected,digest
from deployment.lib.runtime_authority import write_worker_authority,load_worker_authority,runtime_mutation_lock

class ActiveRecoveryWorkerHandoff:
    def __init__(self,plan,candidate,root,source_guard):
        if not callable(source_guard):raise RuntimeError('worker_handoff_frozen_source_guard_required')
        self.plan,self.candidate,self.root,self.source_guard=plan,candidate,Path(root),source_guard
        self.state=Path('/var/lib/madar/releases')
    def guard(self,phases):
        self.source_guard()
        if os.geteuid()!=0 or self.root!=ROOT/self.plan.digest:raise RuntimeError('worker_handoff_fresh_root_required')
        receipt=json.loads(protected(self.root/'authorization.json',private=True).read_text())
        if (receipt.get('operation')!='active-local-rollback-resumption' or receipt.get('plan_sha256')!=self.plan.digest
                or receipt.get('source_bundle_sha256')!=self.plan.source_bundle_sha256):raise RuntimeError('worker_handoff_authorization_changed')
        events=[json.loads(line) for line in protected(self.root/'events.jsonl',private=True).read_text().splitlines()]
        if not events or events[-1].get('phase') not in phases or any(row.get('plan_sha256')!=self.plan.digest for row in events):
            raise RuntimeError('worker_handoff_phase_denied')
        self.candidate.require_write_authority(self.candidate.contract,'READ_ONLY')
        return json.loads(protected(self.root/'candidate-identities.json',private=True).read_text())
    def canonical(self,kind):
        if kind not in {'backend','frontend',*KINDS}:raise RuntimeError('worker_handoff_role_invalid')
        return f'madar-{self.candidate.slot}-'+(kind+'-worker' if kind in KINDS else kind)
    def establish_owner(self):
        record=self.guard({'controller_resumed'})
        dependencies=json.loads(protected(self.root/'runtime-dependencies.json',private=True).read_text())
        if digest(dependencies)!=self.plan.retained_inputs['runtime_dependencies']:raise RuntimeError('worker_handoff_dependencies_changed')
        names=set(self.candidate.command(['docker','ps','-a','--format','{{.Names}}']).splitlines())
        selected={};archive_names={}
        for kind in ('backend','frontend',*KINDS):
            name=self.canonical(kind);old=self.candidate.inspect(name);expected=dependencies['runtimes'][name]
            if (old['Id']!=expected['container_id'] or old['Image']!=expected['image_id'] or spec(old)!=expected['spec_sha256']
                    or old['State']['Running'] or old['HostConfig']['RestartPolicy']['Name']!='no'):
                raise RuntimeError('worker_handoff_retained_slot_changed')
            archive=name+'-retired-'+self.plan.digest[:12]
            if archive in names:raise RuntimeError('worker_handoff_archive_collision')
            new=self.candidate.inspect(self.candidate.name(kind));bound=record['runtimes'][kind]
            if new['Id']!=bound['id'] or new['Image']!=bound['image'] or spec(new)!=bound['spec_sha256']:
                raise RuntimeError('worker_handoff_candidate_changed')
            if kind in KINDS and new['State']['Running']:raise RuntimeError('worker_handoff_standby_started_early')
            selected[kind]=new;archive_names[kind]=archive
        # No name collision or changed binding can start a partial rename. Exact
        # original owner bytes are copied to a NEW protected file, never deleted.
        previous=(self.state/'worker-ownership.json').read_bytes()
        exclusive(self.root/'worker-ownership-preimage.json',previous)
        with runtime_mutation_lock(self.state):
            self.guard({'controller_resumed'})
            for kind in ('backend','frontend',*KINDS):
                self.candidate.command(['docker','rename',self.canonical(kind),archive_names[kind]])
                self.candidate.command(['docker','rename',self.candidate.name(kind),self.canonical(kind)])
            contract=self.candidate.contract
            other='blue' if self.candidate.slot=='green' else 'green'
            owner=write_worker_authority(self.state,generation=digest(asdict(contract)),owner='CANDIDATE',
                old={'sha':self.candidate.recovery.contract.origin_sha,'slot':other},candidate={'sha':contract.sha,'slot':self.candidate.slot})
            identity=pwd.getpwnam('madar')
            os.chown(self.state/'worker-ownership.json',identity.pw_uid,identity.pw_gid)
            exclusive(self.root/'worker-owner.json',encoded({'version':1,'plan_sha256':self.plan.digest,'authority':owner,
                'active':{kind:row['Id'] for kind,row in selected.items()},'retained_names':archive_names}))
        self.verify_owner()
    def verify_owner(self):
        self.source_guard()
        record=json.loads(protected(self.root/'worker-owner.json',private=True).read_text())
        if record.get('plan_sha256')!=self.plan.digest or load_worker_authority(self.state)!=record.get('authority'):
            raise RuntimeError('worker_handoff_single_owner_changed')
        for kind,identity in record['active'].items():
            if self.candidate.inspect(self.canonical(kind))['Id']!=identity:raise RuntimeError('worker_handoff_active_identity_changed')
        for name in record['retained_names'].values():
            row=self.candidate.inspect(name)
            if row['State']['Running'] or row['HostConfig']['RestartPolicy']['Name']!='no':raise RuntimeError('worker_handoff_retained_consumer_started')
        binding=json.loads(protected(self.root/'candidate-identities.json',private=True).read_text())
        if set(record['active'])!={'backend','frontend',*KINDS}:raise RuntimeError('worker_handoff_active_inventory_changed')
        for kind,identity in record['active'].items():
            row=self.candidate.inspect(identity);expected=binding['runtimes'][kind]
            if identity!=expected['id'] or row['Image']!=expected['image'] or spec(row)!=expected['spec_sha256']:
                raise RuntimeError('worker_handoff_active_spec_changed')
        active_ids=set(record['active'].values())
        for name in self.candidate.command(['docker','ps','-a','--format','{{.Names}}']).splitlines():
            if name.startswith('madar-') and any(kind+'-worker' in name or name.endswith(kind+'-standby') for kind in KINDS):
                row=self.candidate.inspect(name)
                if row['Id'] not in active_ids and (row['State']['Running'] or row['HostConfig']['RestartPolicy']['Name']!='no'):
                    raise RuntimeError('worker_handoff_duplicate_consumer')
        return record
    def start_standbys(self):
        self.guard({'controller_resumed'});record=self.verify_owner()
        for kind in KINDS:
            self.guard({'controller_resumed'});self.verify_owner()
            self.candidate.command(['docker','start',record['active'][kind]])
        deadline=time.monotonic()+60
        while True:
            try:self.verify_standbys();return
            except AvailabilityFailure:
                if time.monotonic()>=deadline:raise RuntimeError('worker_handoff_standby_deadline')
                time.sleep(min(1,deadline-time.monotonic()))
    def verify_standbys(self):
        self.guard({'controller_resumed','standby_ready','write_grant_pending','normal'})
        owner=self.verify_owner()
        for kind in KINDS:
            row=self.candidate.inspect(owner['active'][kind])
            if not row['State']['Running']:raise RuntimeError('worker_handoff_standby_not_running')
            address=row['NetworkSettings']['Networks'][self.candidate.network_name]['IPAddress']
            port={'notification':8090,'calendar-sync':8091,'data-deletion':8094}[kind]
            _,health=self.candidate.health_json(f'http://{address}:{port}/health')
            healthy=(health.get('healthy') is True if kind=='calendar-sync' else health.get('status')=='ok')
            if not healthy or health.get('consuming') is not False:
                raise RuntimeError('worker_handoff_standby_not_nonconsuming')
        return owner
    def stop_consumers(self):
        # Compensation may start after only a subset of renames/starts. Bound
        # candidate IDs remain stable, so names cannot hide a consuming process.
        # Stopping approved IDs is always a safe revocation under this fresh
        # receipt, including when audit append or authority publication failed.
        # Never require a successful compensation event to stop consumers.
        self.source_guard()
        if os.geteuid()!=0 or self.root!=ROOT/self.plan.digest:raise RuntimeError('worker_handoff_fresh_root_required')
        receipt=json.loads(protected(self.root/'authorization.json',private=True).read_text())
        if receipt.get('plan_sha256')!=self.plan.digest or receipt.get('source_bundle_sha256')!=self.plan.source_bundle_sha256 or receipt.get('operation')!='active-local-rollback-resumption':
            raise RuntimeError('worker_handoff_authorization_changed')
        record=json.loads(protected(self.root/'candidate-identities.json',private=True).read_text())
        failures=[]
        for kind in KINDS:
            try:
                identity=record['runtimes'][kind]['id']
                row=self.candidate.inspect(identity)
                if row['Image']!=self.plan.candidate_images['backend']:raise RuntimeError('worker_handoff_stop_image_changed')
                self.candidate.command(['docker','update','--restart=no',identity])
                self.candidate.command(['docker','stop',identity])
                if self.candidate.inspect(identity)['State']['Running']:raise RuntimeError('worker_handoff_consumer_stop_failed')
            except Exception as error:
                failures.append(type(error).__name__)
        if failures:raise RuntimeError('worker_handoff_consumer_stop_incomplete')
