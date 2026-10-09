"""Read-only identity and health checks across canonical worker handoff.

Container names and IPs may change; the approved IDs, images, specifications and
network IDs cannot. This component issues no authorization and changes nothing.
"""
import json
from pathlib import Path
from deployment.lib.active_recovery_candidate import KINDS,verify_lifecycle_networks,worker_spec_matches
from deployment.lib.emergency_routing_repair import Runtime, spec
from deployment.lib.provider_recovery_runtime import protected

ROLES = frozenset({'backend', 'frontend', 'parser', *KINDS})
CORE = frozenset({'database', 'auth', 'schema', 'storage'})
PENDING = frozenset({'notification_worker', 'calendar_sync_worker', 'calendar_sync_queue', 'data_deletion_worker'})

class ActiveRecoveryRuntime:
    def __init__(self, plan, candidate, root, source_guard, worker_handoff, *, runtime=None):
        if not callable(source_guard):
            raise RuntimeError('active_runtime_source_guard_required')
        self.plan, self.candidate, self.root = plan, candidate, Path(root)
        self.source_guard, self.workers = source_guard, worker_handoff
        self.runtime = runtime or Runtime()

    def identities(self, *, workers_started, require_running=True):
        self.source_guard()
        binding = json.loads(protected(self.root/'candidate-identities.json', private=True).read_text())
        if (type(binding.get('version')) is not int or binding['version'] != 1
                or binding.get('plan_sha256') != self.plan.digest
                or binding.get('source_sha') != self.plan.source_sha
                or binding.get('mode') != 'READ_ONLY'
                or set(binding.get('runtimes', {})) != ROLES
                or binding.get('loopback_ports') != {'backend':self.candidate.backend_port, 'frontend':self.candidate.frontend_port}
                or set(binding.get('networks', {})) != {self.candidate.network_name, 'madar-supabase-client', self.candidate.redis_network}):
            raise RuntimeError('active_runtime_receipt_changed')
        for name, identity in binding['networks'].items():
            actual = json.loads(self.candidate.command(['docker', 'network', 'inspect', name]))[0]
            if actual['Id'] != identity or actual['Driver'] != 'bridge':
                raise RuntimeError('active_runtime_network_changed')
        result = {}
        for kind, expected in binding['runtimes'].items():
            row = self.candidate.inspect(expected['id'])
            image = self.plan.candidate_images['frontend' if kind == 'frontend' else 'backend']
            if (expected['id']!=row['Id'] or expected['image']!=row['Image']
                    or not worker_spec_matches(row,expected['spec_sha256'],started_worker=workers_started and kind in KINDS)
                    or row['Image'] != image or row['HostConfig']['RestartPolicy']['Name'] != 'no'
                    or (require_running and row['State']['Running'] is not (workers_started or kind not in KINDS))):
                raise RuntimeError('active_runtime_identity_changed')
            attached = row['NetworkSettings']['Networks']
            wanted = {self.candidate.network_name, 'madar-supabase-client', self.candidate.redis_network} if kind in {'backend', *KINDS} else {self.candidate.network_name}
            verify_lifecycle_networks(row,{name:binding['networks'][name] for name in wanted},self.candidate.network_name,
                ('backend' if kind=='backend' else kind+'-worker') if kind in {'backend',*KINDS} else None,
                created_worker=kind in KINDS and not workers_started)
            result[kind] = row
        if workers_started:
            owner = self.workers.verify_owner()
            if any(owner['active'][kind] != result[kind]['Id'] for kind in ('backend', 'frontend', *KINDS)):
                raise RuntimeError('active_runtime_owner_changed')
        self.source_guard()
        return result

    def read_only(self, *, workers_started, require_public=True):
        self.identities(workers_started=workers_started)
        self.candidate.require_write_authority(self.candidate.contract, 'READ_ONLY')
        versions = []
        bases=(self.candidate.endpoint('backend'), self.candidate.endpoint('frontend')+'/api')
        if require_public:bases+=('http://127.0.0.1:8001', 'http://127.0.0.1:3000/api')
        for base in bases:
            _, version = self.candidate.health_json(base+'/health/version')
            _, fence = self.candidate.health_json(base+'/health/recovery')
            if (version.get('release_sha') != self.plan.source_sha or version.get('release_slot') != self.candidate.slot
                    or version.get('schema_compatible_min') != 115 or version.get('schema_compatible_max') != 115
                    or fence != {'restricted':True, 'business_writes_enabled':False}):
                raise RuntimeError('active_runtime_read_only_changed')
            self.runtime.denied(base)
            versions.append(version)
        if any(version != versions[0] for version in versions):
            raise RuntimeError('active_runtime_serving_roles_changed')
        _, ready = self.candidate.health_json(self.candidate.endpoint('backend')+'/health/ready', allow_503=True)
        components = ready.get('components', {})
        if (not CORE.issubset(components) or any(components[key] != 'ok' for key in CORE)
                or any(value not in {'ok','disabled','configured','not_required','development'} and key not in PENDING
                       for key, value in components.items())):
            raise RuntimeError('active_runtime_core_unready')
        if workers_started:
            self.workers.verify_standbys()
        frontends=(self.candidate.endpoint('frontend'),)
        if require_public:frontends+=('http://127.0.0.1:3000',)
        for base in frontends:
            self.runtime.http_status(base+'/')
        self.identities(workers_started=workers_started)
        self.candidate.require_write_authority(self.candidate.contract, 'READ_ONLY')
        return {'source_sha':self.plan.source_sha, 'schema':115, 'business_writes_enabled':False,
                'workers_started':workers_started}


    def normal(self, *, require_public=True):
        self.identities(workers_started=True)
        self.candidate.require_write_authority(self.candidate.contract,'NORMAL')
        bases=(self.candidate.endpoint('backend'),self.candidate.endpoint('frontend')+'/api')
        if require_public:bases+=('http://127.0.0.1:8001','http://127.0.0.1:3000/api')
        versions=[]
        for base in bases:
            _,version=self.candidate.health_json(base+'/health/version')
            _,fence=self.candidate.health_json(base+'/health/recovery')
            _,ready=self.candidate.health_json(base+'/health/ready')
            if (version.get('release_sha')!=self.plan.source_sha or version.get('release_slot')!=self.candidate.slot
                    or version.get('schema_compatible_min')!=115 or version.get('schema_compatible_max')!=115
                    or fence!={'restricted':False,'business_writes_enabled':True}
                    or ready.get('ready') is not True
                    or any(ready.get('components',{}).get(key)!='ok' for key in CORE)):
                raise RuntimeError('active_runtime_normal_unready')
            versions.append(version)
        if any(version!=versions[0] for version in versions):raise RuntimeError('active_runtime_serving_roles_changed')
        owner=self.workers.verify_owner()
        for kind in KINDS:
            row=self.candidate.inspect(owner['active'][kind])
            address=row['NetworkSettings']['Networks'][self.candidate.network_name]['IPAddress']
            port={'notification':8090,'calendar-sync':8091,'data-deletion':8094}[kind]
            _,health=self.candidate.health_json(f'http://{address}:{port}/health')
            healthy=health.get('healthy') is True if kind=='calendar-sync' else health.get('status')=='ok'
            if not healthy:raise RuntimeError('active_runtime_normal_worker_unhealthy')
            if health.get('consuming') is not True:
                from deployment.lib.emergency_routing_repair import AvailabilityFailure
                raise AvailabilityFailure('active_runtime_normal_worker_activation_pending')
        frontends=(self.candidate.endpoint('frontend'),)
        if require_public:frontends+=('http://127.0.0.1:3000',)
        for base in frontends:self.runtime.http_status(base+'/')
        self.identities(workers_started=True)
        self.candidate.require_write_authority(self.candidate.contract,'NORMAL')
        return {'source_sha':self.plan.source_sha,'schema':115,'business_writes_enabled':True}
