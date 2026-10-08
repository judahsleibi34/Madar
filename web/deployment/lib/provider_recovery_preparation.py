"""Phase-1 capabilities restricted to root-protected private rehearsal resources.

This adapter cannot operate the production proxy, release state or worker sets.
Production activation uses ProductionRecoveryOperations and the mandatory
Phase-2 receipt; this class is never an activation authorization mechanism.
"""
from dataclasses import replace
import json
import os
from pathlib import Path
import re
import subprocess

from deployment.lib.provider_recovery import PROFILE
from deployment.lib.provider_recovery_phases import PRECONDITIONS, preparation_binding, sha256
from deployment.lib.provider_recovery_runtime import ProductionRecoveryOperations, RecoveryPaths, protected, http
from deployment.lib.release_deployer import atomic_json
from deployment.lib.runtime_authority import runtime_mutation_lock, write_worker_authority

ROOT = Path('/var/lib/madar-control-plane/provider402/rehearsals')
PRIVATE_PORTS = {'blue': (29101, 39101), 'green': (29201, 39201), 'local-fallback': (29401, 39401)}


class PrivatePreparationOperations(ProductionRecoveryOperations):
    def __init__(self, contract, metadata, directory):
        self.binding = sha256(preparation_binding(contract, metadata))
        expected = ROOT / self.binding
        if Path(directory) != expected:
            raise RuntimeError('recovery_private_scope_invalid')
        self.directory = expected
        self.scope_prefix = 'madar-provider402-rehearsal-' + self.binding[:12]
        paths = RecoveryPaths(repository=expected/'source', state=expected/'state',
            production_env=expected/'configuration.env', target_env=expected/'configuration.env',
            upstream=expected/'proxy'/'active-upstreams.conf', controller=expected/'source'/'web/deployment',
            checkpoint=expected/'checkpoint'/'manifest.json', rehearsal=expected/'rehearsal.json',
            proxy=self.scope_prefix+'-proxy', prefix=self.scope_prefix+'-candidate',
            production_prefix=self.scope_prefix+'-origin', controller_transition=expected/'transition.json',
            stable_backend=28001, stable_frontend=38001)
        self.require_isolated_paths(paths)
        super().__init__(paths, contract, ports=PRIVATE_PORTS)
        self.schema_metadata = metadata

    def require_isolated_paths(self, paths):
        if os.geteuid() != 0:
            raise RuntimeError('recovery_private_root_required')
        for path in (paths.repository, paths.state, paths.production_env, paths.target_env,
                     paths.upstream, paths.controller, paths.checkpoint, paths.rehearsal):
            if not path.is_relative_to(self.directory):
                raise RuntimeError('recovery_private_path_escape')
            if path.exists() and not path.resolve().is_relative_to(self.directory):
                raise RuntimeError('recovery_private_path_escape')
        for name in (paths.prefix, paths.production_prefix, paths.proxy):
            if not name.startswith(self.scope_prefix+'-'):
                raise RuntimeError('recovery_private_resource_escape')
        for path in (self.directory, *self.directory.parents):
            stat = path.lstat()
            if path.is_symlink() or stat.st_uid != 0 or stat.st_mode & 0o022:
                raise RuntimeError('recovery_private_root_untrusted')

    def require_isolated(self):
        self.require_isolated_paths(self.paths)
        if self.ports != PRIVATE_PORTS or (self.paths.stable_backend, self.paths.stable_frontend) != (28001, 38001):
            raise RuntimeError('recovery_private_port_escape')
        return True

    def command(self, args, *, input=None, env=None):
        self.require_isolated()
        # Every Docker mutation has a structurally checked resource capability.
        # Read-only inspect/list do not grant a mutation capability.
        if args[0] == 'docker':
            operation = args[1]
            if operation in {'create', 'run'}:
                if '--name' not in args or not args[args.index('--name')+1].startswith(self.scope_prefix+'-'):
                    raise RuntimeError('recovery_private_container_escape')
                if any(flag in args for flag in ('--privileged', '--pid', '--volumes-from', '-v', '--volume')):
                    raise RuntimeError('recovery_private_unsafe_container')
                for index, arg in enumerate(args):
                    if arg == '--mount':
                        mount = args[index+1]
                        source = re.search(r'(?:^|,)src=([^,]+)', mount)
                        if not source or not ((source[1].startswith(str(self.directory)+'/') and Path(source[1]).resolve().is_relative_to(self.directory)) or re.fullmatch(re.escape(self.scope_prefix)+r'-[a-zA-Z0-9-]+',source[1]) or source[1] == '/var/lib/madar-control-plane/provider402/preparation-backup-verification.json'):
                            raise RuntimeError('recovery_private_mount_escape')
                    if arg == '-p' and not args[index+1].startswith('127.0.0.1:'):
                        raise RuntimeError('recovery_private_public_port')
                if '--network' in args and args[args.index('--network')+1] == 'host':
                    # Only the private proxy, whose root-protected configuration
                    # binds loopback fixture endpoints, may use host networking.
                    if args[args.index('--name')+1] != self.paths.proxy:
                        raise RuntimeError('recovery_private_host_network_denied')
            elif operation in {'start', 'stop', 'update', 'rm'}:
                if not args[-1].startswith(self.scope_prefix+'-'):
                    raise RuntimeError('recovery_private_container_escape')
            elif operation == 'network':
                action = args[2]
                if action == 'connect':
                    if not args[-1].startswith(self.scope_prefix+'-') or not (args[-2].startswith(self.scope_prefix+'-') or args[-2]=='madar-supabase-client'):
                        raise RuntimeError('recovery_private_network_escape')
                elif action == 'create':
                    if not args[-1].startswith(self.scope_prefix+'-') or '--internal' not in args:
                        raise RuntimeError('recovery_private_network_escape')
                elif action != 'inspect':
                    raise RuntimeError('recovery_private_network_operation_denied')
            elif operation == 'exec':
                if args[2:5] == ['-i', 'supabase-db', 'psql']:
                    if not input or not re.fullmatch(r'BEGIN READ ONLY;\nSELECT[^;]+;\nROLLBACK;\n',input,re.S):
                        raise RuntimeError('recovery_private_database_mutation_denied')
                elif args[2] == self.paths.proxy and args[3:] in (['nginx','-t'], ['nginx','-s','reload']):
                    pass
                else:
                    raise RuntimeError('recovery_private_exec_denied')
            elif operation not in {'inspect', 'ps'}:
                raise RuntimeError('recovery_private_docker_operation_denied')
        elif args[0] != 'git' or args[1:3] != ['-C',str(self.paths.repository)] or args[3] not in {'show','rev-parse','status'}:
            raise RuntimeError('recovery_private_command_denied')
        return super().command(args, input=input, env=env)

    def metadata(self):
        return self.schema_metadata

    def authorize(self, contract):
        # Private traffic rehearsal authorization is not production authorization.
        self.require_isolated()
        if contract != self.contract:
            raise RuntimeError('recovery_private_contract_changed')
        protected(self.directory/'contract.json', private=True)
        if json.loads((self.directory/'contract.json').read_text()) != contract.__dict__:
            raise RuntimeError('recovery_private_contract_changed')

    def collect_preconditions(self, contract, metadata):
        self.authorize(contract)
        contract.validate(metadata)
        self.checkpoint()
        observer = ProductionRecoveryOperations(replace(RecoveryPaths(),
            target_env=self.paths.target_env, checkpoint=self.paths.checkpoint), contract)
        origin = observer.origin_evidence()
        contract.validate_origin(origin)
        for kind, image in contract.images.items():
            row = self.inspect(image)
            if row['Id'] != image or row['Config'].get('Labels',{}).get('org.opencontainers.image.revision') != contract.sha:
                raise RuntimeError('recovery_private_image_provenance_invalid')
        if self.command(['git','-C',str(self.paths.repository),'rev-parse','HEAD']) != contract.sha or self.command(['git','-C',str(self.paths.repository),'status','--porcelain']):
            raise RuntimeError('recovery_private_source_changed')
        proof=json.loads(protected(self.directory/'source-validation.json',private=True).read_text())
        if proof.get('sha') != contract.sha or proof.get('write_fence_source_validation') != 'PASS':
            raise RuntimeError('recovery_private_source_validation_missing')
        from deployment.lib.provider_recovery_runtime import SERVICES
        for name in SERVICES:
            row=self.inspect(name)
            if row['State'].get('Health',{}).get('Status')!='healthy' or any(p['HostIp']!='127.0.0.1' for ps in (row['NetworkSettings']['Ports'] or {}).values() for p in ps or []):
                raise RuntimeError('recovery_private_target_unhealthy')
        headers={'apikey':self.config['SUPABASE_SERVICE_KEY'], 'Authorization':'Bearer '+self.config['SUPABASE_SERVICE_KEY']}
        for path in ('/auth/v1/health','/rest/v1/application_schema_state?contract_key=eq.core&select=schema_version','/storage/v1/status'):
            status, body=http('http://127.0.0.1:18000'+path,headers=headers)
            if status!=200 or ('application_schema_state' in path and body!=[{'schema_version':115}]):
                raise RuntimeError('recovery_private_target_invalid')
        network=json.loads(self.command(['docker','network','inspect','madar-supabase-client']))[0]
        if not network.get('Internal'):
            raise RuntimeError('recovery_private_target_network_not_internal')
        return {name:'PASS' for name in PRECONDITIONS},origin

    def prepare_isolated_candidate_and_fallback(self, contract):
        # The six fixture worker containers exist before this call. These are
        # the only worker resources this capability can inhibit.
        self.inhibit_all_workers()
        self.register_fallback()
        slot='blue' if contract.origin_slot=='green' else 'green'
        self.prepare_candidate(contract,slot)
        with runtime_mutation_lock(self.paths.state):
            write_worker_authority(self.paths.state, generation=sha256(contract.__dict__), owner='RECOVERY',
                old={'sha':contract.origin_sha,'slot':contract.origin_slot}, candidate={'sha':contract.sha,'slot':slot})
        atomic_json(self.paths.state/'provider-recovery.json',{'phase':'switch_pending','context_digest':sha256(contract.__dict__),
            'sha':contract.sha,'slot':slot,'schema':115,'restore_database_on_rollback':False})
        self.require_all_workers_off()

    def prepare_proxy_publication(self):
        # This capability has only private scoped paths/resources and cannot
        # restart the production service. Its proxy discards Docker logs;
        # production always uses the canonical publication implementation.
        self.require_isolated()
        if self.inspect(self.paths.proxy)['HostConfig'].get('LogConfig', {}).get('Type') != 'none':
            raise RuntimeError('recovery_private_proxy_logging_enabled')

    def save_preparation_report(self, report):
        self.require_isolated()
        path=self.paths.rehearsal
        if path.exists():
            raise RuntimeError('recovery_preparation_report_already_present')
        atomic_json(path, report)
        os.chmod(path,0o600)
