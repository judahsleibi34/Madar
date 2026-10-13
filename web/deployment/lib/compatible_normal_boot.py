"""Schema-aware boot kernel for an accepted compatible NORMAL release.

This replaces no unit itself. A separately authorized exact-resource installer
must seal its runtime bindings and supersede the old boot dependencies first.
The kernel never runs SQL or selects an old schema115 fallback after advancement.
It uses the existing bounded verification and current-data compensation model.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import time

from deployment.lib.active_recovery_candidate import default_dns_spec_matches
from deployment.lib.completed_normal_admission import OPERATION, ADMISSIONS, digest, validate_contract, require_candidate_authority
from deployment.lib.emergency_routing_repair import Runtime, AvailabilityFailure, verification_window
from deployment.lib.provider_recovery_runtime import protected
from deployment.lib.runtime_authority import runtime_mutation_lock
from deployment.lib.completed_normal_profile import profile

WORKERS = ("notification-worker", "calendar-sync-worker", "data-deletion-worker")
ROLES = ("backend", "frontend", "parser-worker", "remote-ingestion-worker", "redis", *WORKERS)


class CompatibleNormalBoot:
    def __init__(self, contract, *, source_guard, native_verifier, publish_authority,
                 compensate_current_data, runtime=None, admissions=ADMISSIONS, state_root=Path('/var/lib/madar/releases'),
                 publication_name='normal-publication.json', normal_resume_guard=None):
        if not all(callable(f) for f in (source_guard, native_verifier, publish_authority, compensate_current_data)):
            raise RuntimeError('compatible_boot_independent_guards_required')
        validate_contract(contract)
        self.contract = contract
        self.profile = profile(contract)
        self.root = Path(admissions) / digest(contract)
        self.admissions, self.state_root = Path(admissions), Path(state_root)
        self.source_guard, self.native_verifier = source_guard, native_verifier
        self.publish_authority, self.compensate_current_data = publish_authority, compensate_current_data
        self.runtime = runtime or Runtime()
        if publication_name not in {'normal-publication.json','candidate-runtime.json'}:
            raise RuntimeError('compatible_boot_publication_path_invalid')
        self.publication_name = publication_name
        if normal_resume_guard is None:
            from deployment.lib.completed_normal_database import require_normal_migration_boundary,require_manual_normal_completion
            def normal_resume_guard(schema):
                require_normal_migration_boundary(self.contract,schema,self.root,self.state_root)
                require_manual_normal_completion(self.contract,self.root)
        if not callable(normal_resume_guard):
            raise RuntimeError('compatible_boot_normal_resume_guard_required')
        self.normal_resume_guard=normal_resume_guard

    def bindings(self):
        self.source_guard()
        if os.geteuid() != 0:
            raise RuntimeError('compatible_boot_root_required')
        receipt = json.loads(protected(self.root/'admission.json').read_text())
        if receipt.get('operation') != self.profile.operation or receipt.get('contract') != self.contract:
            raise RuntimeError('compatible_boot_fresh_contract_changed')
        publication = json.loads(protected(self.root/self.publication_name, private=True).read_text())
        if (set(publication) != {'operation','context_sha256','source_sha','images','runtimes','networks','worker_generation','origin_workers'}
                or publication['operation'] != self.profile.operation or publication['context_sha256'] != digest(self.contract)
                or publication['source_sha'] != self.contract['candidate']['source_sha']
                or publication['images'] != self.contract['candidate']['images']
                or set(publication['runtimes']) != set(ROLES) or len(publication['origin_workers']) != 3):
            raise RuntimeError('compatible_boot_publication_changed')
        from deployment.lib.completed_normal_resources import verify_runtime_binding
        selected=verify_runtime_binding(self.contract,publication,self.runtime,self.state_root)
        schema = self.native_verifier()
        if not self.profile.supports(schema):
            raise RuntimeError('compatible_boot_native_schema_invalid')
        self.source_guard()
        return selected

    def round(self, *, normal):
        rows = self.bindings()
        grant = require_candidate_authority(self.contract, mode='NORMAL' if normal else 'READ_ONLY', admissions=self.admissions)
        slot = self.contract['candidate']['slot']
        port = 8101 if slot == 'blue' else 8201
        front = 3100 if slot == 'blue' else 3200
        base = f'http://127.0.0.1:{port}'
        for url in (base, f'http://127.0.0.1:{front}/api'):
            version = self.runtime.json_http(url+'/health/version')
            fence = self.runtime.json_http(url+'/health/recovery')
            if (version.get('release_sha') != self.contract['candidate']['source_sha']
                    or version.get('release_slot') != slot or version.get('schema_compatible_min') != self.profile.minimum
                    or version.get('schema_compatible_max') != self.profile.target
                    or tuple(version.get('schema_excluded_versions', [])) != self.profile.excluded
                    or fence != {'restricted':not normal,'business_writes_enabled':normal}):
                raise RuntimeError('compatible_boot_serving_binding_changed')
            if not normal:
                self.runtime.denied(url)
        # READ_ONLY readiness may intentionally omit consuming-worker health.
        status, body = self.runtime.fetch(base+'/health/ready')
        payload = json.loads(body)
        core = {'database','auth','schema','storage','redis','environment','admin_mfa_policy','parser_isolation'}
        components = payload.get('components',{})
        if not core.issubset(components) or any(components[k] != 'ok' for k in core):
            raise AvailabilityFailure('compatible_boot_core_unready')
        permitted = {'notification_worker','calendar_sync_worker','calendar_sync_queue','data_deletion_worker'}
        if any(v not in {'ok','disabled','configured','not_required','development'} and (normal or k not in permitted) for k,v in components.items()):
            raise AvailabilityFailure('compatible_boot_readiness_unready')
        if normal and (status != 200 or payload.get('ready') is not True):
            raise AvailabilityFailure('compatible_boot_normal_unready')
        for kind in WORKERS:
            row = rows[kind]
            if not row['State']['Running'] or row['State'].get('Health',{}).get('Status') != 'healthy':
                raise AvailabilityFailure('compatible_boot_worker_start_pending')
            # Resolve the current endpoint by the measured primary network ID;
            # never persist or trust a Docker IP through daemon restart.
            primary = row['HostConfig']['NetworkMode']
            address = row['NetworkSettings']['Networks'][primary]['IPAddress']
            health_port = {'notification-worker':8090,'calendar-sync-worker':8091,'data-deletion-worker':8094}[kind]
            health = self.runtime.json_http(f'http://{address}:{health_port}/health')
            healthy = health.get('healthy') is True if kind=='calendar-sync-worker' else health.get('status')=='ok'
            if not healthy or health.get('consuming') is not normal:
                raise AvailabilityFailure('compatible_boot_worker_consumption_pending')
        self.runtime.http_status(f'http://127.0.0.1:{front}/')
        self.bindings()
        return grant

    def _converge(self, *, normal):
        first = None
        successes = 0
        while True:
            self.runtime.budget(1)
            try:
                self.round(normal=normal)
            except AvailabilityFailure:
                first = None
                successes = 0
            else:
                successes += 1
                if first is None:
                    first = time.monotonic()
                if successes >= 3 and time.monotonic()-first >= 5:
                    return
            time.sleep(self.runtime.budget(1))

    def _ready_bindings(self):
        # Identity failures remain fatal. Only unchanged, temporarily unhealthy
        # native resources may converge during a cold Docker/host start.
        while True:
            self.runtime.budget(1)
            try:
                return self.bindings()
            except AvailabilityFailure:
                time.sleep(self.runtime.budget(1))

    def verify_mode(self, *, normal):
        """Await observed worker fencing without starting or granting anything.

        Grant publication is synchronous; worker health reflects its next poll.
        Identity/integrity failures stay fatal. Require sustained convergence
        before a backup or SQL boundary can rely on stopped consumption.
        """
        with verification_window(self.runtime,180):
            self._converge(normal=normal)

    def _start(self, rows):
        for kind in ('redis','parser-worker','remote-ingestion-worker','backend','frontend',*WORKERS):
            self.source_guard()
            actual=next(iter(self.runtime.inspect([rows[kind]['Id']]).values()))
            if not actual['State']['Running']:
                self.runtime.command(['docker','start',actual['Id']])

    def execute_read_only(self):
        """Recover only the accepted bridge; never grant writes or restore data.

        An interrupted migration or revoked grant can use this path through the
        separately source-bound boot dispatcher. It has no legacy115 fallback.
        """
        effect_started=False
        try:
            with verification_window(self.runtime,180):
                with runtime_mutation_lock(self.state_root):
                    rows=self._ready_bindings()
                    require_candidate_authority(self.contract,mode='READ_ONLY',admissions=self.admissions)
                    effect_started=True
                    self._start(rows)
                    self._converge(normal=False)
        except Exception:
            if effect_started:
                self.compensate_current_data()
            raise
        return {'operation':self.profile.operation,'schema':self.native_verifier(),'mode':'READ_ONLY','database_restored':False}

    def execute(self):
        if self.publication_name != 'normal-publication.json':
            raise RuntimeError('compatible_boot_positive_publication_required')
        effect_started=False
        try:
            # The deadline includes native startup and lock acquisition, not
            # merely the final HTTP checks. The lock spans fence/start/grant.
            with verification_window(self.runtime,180):
                with runtime_mutation_lock(self.state_root):
                    rows=self._ready_bindings()
                    require_candidate_authority(self.contract,mode='NORMAL',admissions=self.admissions)
                    self.normal_resume_guard(self.native_verifier())
                    effect_started=True
                    self.publish_authority('READ_ONLY')
                    require_candidate_authority(self.contract,mode='READ_ONLY',admissions=self.admissions)
                    self._start(rows)
                    self._converge(normal=False)
                    self.bindings()
                    require_candidate_authority(self.contract,mode='READ_ONLY',admissions=self.admissions)
                    # Migration intent may have been sealed after initial
                    # observation. Recheck immediately before any positive grant.
                    self.normal_resume_guard(self.native_verifier())
                    self.publish_authority('NORMAL')
                    self._converge(normal=True)
        except Exception:
            # Compensation takes its own locks; never invoke it while holding
            # the runtime lock, and never start the old115-only application.
            if effect_started:
                self.compensate_current_data()
            raise
        return {'operation':self.profile.operation,'schema':self.native_verifier(),'mode':'NORMAL','database_restored':False}
