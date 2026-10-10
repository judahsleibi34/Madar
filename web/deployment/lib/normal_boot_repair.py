"""Freshly authorized boot-resource supersession for completed NORMAL only.

Reuses the existing boot runtime/fence/ownership/readiness implementation.
The original completed contract identifies resources; a NEW exact-package
authorization permits this operation. Original frozen bytes/receipts stay intact.
"""
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import time
import re

from deployment.lib.active_recovery_boot_actor import ActiveRecoveryBootActor
from deployment.lib.active_recovery_resumption import ROOT,load_saved_resumption_plan
from deployment.lib.active_recovery_inputs import INPUTS,OPERATOR_CONFIGURATION,controller_tree_digest
from deployment.lib.active_recovery_fallback import CompensationPublication
from deployment.lib.completed_normal_baseline import attest_split,historical_source,BASE
from deployment.lib.control_plane_upgrade import SystemOperations,acquire_lock
from deployment.lib.emergency_routing_repair import encoded,exclusive,AvailabilityFailure,verification_window
from deployment.lib.provider_recovery_runtime import protected,readonly_configuration,file_digest

UNITS=Path('/etc/systemd/system')
DROPIN=UNITS/'madar-release-proxy.service.d/92-normal-local-continuation.conf'
OPERATION='repair-completed-normal-boot'

def unit_bytes(name,command,listener):
    return ('[Unit]\nDescription=Madar completed NORMAL boot repair\n'
        f'Requires=docker.service {listener}\nAfter=docker.service {listener}\nPartOf=docker.service\n'
        '[Service]\nType=oneshot\nRemainAfterExit=yes\nUser=root\nGroup=root\nUMask=0077\n'
        'Environment=PATH=/usr/sbin:/usr/bin:/sbin:/bin\nEnvironment=HOME=/root\nEnvironment=LANG=C.UTF-8\n'
        f'ExecStart={command}\nTimeoutStartSec=300\nNoNewPrivileges=yes\n'
        '[Install]\nWantedBy=multi-user.target docker.service\n').encode()

def dropin_bytes(name,command):
    return ('[Unit]\n'+f'Requires={name}\nAfter={name}\n[Service]\nExecStartPre=\nExecStartPre={command}\n').encode()

class RepairActor(ActiveRecoveryBootActor):
    """Compensation is new-audit maintenance; historical phase stays untouched."""
    def compensate(self):
        try:self.audit('compensation_pending')
        except OSError:pass
        failures=[]
        try:
            self.candidate._publish_write_authority(self.candidate.contract,'READ_ONLY')
            self.candidate.require_write_authority(self.candidate.contract,'READ_ONLY')
        except Exception as error:failures.append(type(error).__name__)
        try:self.workers.stop_consumers()
        except Exception as error:failures.append(type(error).__name__)
        if failures:
            try:self.stop_bound_runtimes_for_failed_compensation()
            except Exception as error:failures.append(type(error).__name__)
        # No unavailable GREEN/fallback is started, no historical journal is
        # appended, and no old customer snapshot/configuration is restored.
        CompensationPublication(self.fallback,self.repair_root,runtime=self.runtime).maintenance_or_stop_proxy()
        self.audit('compensated',failures=failures,database_restore=False)
        if failures:raise RuntimeError('boot_repair_compensation_incomplete')

class NormalBootRepair:
    def __init__(self,document,package,*,operations=None,authorized=False):
        if not re.fullmatch('[0-9a-f]{64}',document.get('original_plan_sha256','')):
            raise RuntimeError('boot_repair_original_plan_invalid')
        self.document,self.package=document,Path(package)
        self.digest=hashlib.sha256(encoded(document)).hexdigest()
        self.root=ROOT/self.digest
        self.old_root=ROOT/document['original_plan_sha256']
        self.plan=load_saved_resumption_plan(self.old_root)
        self.ops=operations or SystemOperations()
        self.authorized=authorized
        self.name='madar-normal-local-boot-'+self.digest[:12]+'.service'
        self.old_name='madar-normal-local-boot-'+self.plan.digest[:12]+'.service'
        self.actor=RepairActor(self.plan,self.old_root,BASE/('normal-source-'+self.plan.source_bundle_sha256),source=self,audit=self.event)
        self.actor.repair_root=self.root
    def verify(self):
        from scripts.resume_active_recovery import measure
        saved,source=measure(self.package,self.document['source_bundle_sha256'],self.digest)
        if saved!=self.document or self.document.get('operation')!=OPERATION or self.document.get('schema')!=115:
            raise RuntimeError('boot_repair_plan_changed')
        manifest=json.loads((self.package/'source-bundle.json').read_text())
        locations={str(source/name) for name in manifest['files']}
        helpers={Path(name).stem for name in manifest['files'] if name.startswith('web/deployment/lib/') and name.endswith('.py')}
        for name,module in list(sys.modules.items()):
            if name in {'deployment','scripts'} or name in helpers or name.startswith(('deployment.','scripts.')):
                location=getattr(module,'__file__',None)
                if location is not None and str(Path(location).absolute()) not in locations:
                    raise RuntimeError('boot_repair_foreign_privileged_import')
        if self.authorized:
            receipt=json.loads(protected(self.root/'authorization.json',private=True).read_text())
            if receipt!={'operation':OPERATION,'plan_sha256':self.digest,'source_bundle_sha256':self.document['source_bundle_sha256']}:
                raise RuntimeError('boot_repair_fresh_authorization_changed')
        if controller_tree_digest()!=self.document['installed_controller_tree_sha256']:
            raise RuntimeError('boot_repair_installed_tree_changed')
        return historical_source(self.plan)
    def event(self,stage,**fields):
        if not self.authorized:raise RuntimeError('boot_repair_event_requires_fresh_approval')
        path=self.root/'events.jsonl'
        if path.exists():protected(path,private=True)
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,'a') as stream:
            json.dump({'operation':OPERATION,'plan_sha256':self.digest,'source_bundle_sha256':self.document['source_bundle_sha256'],
                'stage':stage,'observed_at':datetime.now(timezone.utc).isoformat(),**fields},stream,sort_keys=True)
            stream.write('\n');stream.flush();os.fsync(stream.fileno())
    def command(self,mode):
        entry=self.package/'source/web/scripts/repair_completed_normal_boot.py'
        return f'/usr/bin/python3 -I -B {entry} {mode} --source-package {self.package} --approved-source {self.document["source_bundle_sha256"]} --approved-plan {self.digest}'
    def baseline(self,*,installed=False):
        for name,expected in self.document['baseline_files'].items():
            if installed and name==str(DROPIN):continue
            reader=readonly_configuration if Path(name) in {INPUTS[key] for key in OPERATOR_CONFIGURATION} else protected
            path=reader(Path(name),private=False)
            state=path.stat()
            if {'sha256':file_digest(path),'uid':state.st_uid,'mode':state.st_mode&0o7777}!=expected:
                raise RuntimeError('boot_repair_baseline_changed')
    def resources(self):
        self.verify()
        self.baseline()
        state=json.loads(readonly_configuration(INPUTS['release_state'],private=True).read_text())
        split=attest_split(state,self.old_root,self.ops.repository_head(),self.ops.installed_sha())
        if split!=self.document['source_roles']:raise RuntimeError('boot_repair_source_roles_changed')
        if self.ops.repository_origin()!=self.document['repository_origin']:raise RuntimeError('boot_repair_repository_origin_changed')
        self.ops.require_clean_repository()
        if self.actor.phase()!='normal':raise RuntimeError('boot_repair_completed_normal_required')
        self.actor.assemble();self.actor.completed_evidence();self.actor.native()
        rows=self.actor.kernel.identities(workers_started=True,require_running=False)
        return rows
    def preflight(self):
        rows=self.resources()
        for name,expected in self.document['initial_systemd_states'].items():
            if self.ops.systemctl_state(name)!=expected:
                raise RuntimeError('boot_repair_initial_systemd_state_changed')
        self.actor.candidate.require_write_authority(self.actor.candidate.contract,'NORMAL')
        if any(row['State']['Running'] for row in rows.values()):raise RuntimeError('boot_repair_initial_stopped_state_changed')
        for port in (self.actor.candidate.backend_port,self.actor.candidate.frontend_port):
            with socket.socket() as probe:probe.bind(('127.0.0.1',port))
        if self.ops.systemctl_state(self.old_name)!={'enabled':'enabled','active':'inactive'}:
            raise RuntimeError('boot_repair_original_unit_state_changed')
        if set(str(p) for p in DROPIN.parent.iterdir())!=set(self.document['proxy_dropins']):
            raise RuntimeError('boot_repair_dropin_inventory_changed')
        if (UNITS/self.name).exists() or self.root.exists():raise RuntimeError('boot_repair_namespace_already_consumed')
        from deployment.lib.active_recovery_backup import verify_backup_execution_context
        from deployment.lib.active_recovery_artifact_evidence import verify_artifact_acceptance
        verify_artifact_acceptance(self.plan)
        for name in ('backup_support.py','backup_madar.sh','verify_backup.sh'):
            if file_digest(protected(Path('/usr/local/lib/madar')/name))!=file_digest(protected(self.package/'source/web/scripts'/name,private=True)):
                raise RuntimeError('normal_backup_installed_helper_changed')
        backup_context=verify_backup_execution_context(self.package)
        with tempfile.TemporaryDirectory(prefix='boot-repair-unit-',dir='/opt/madar-development/repository/.incident-response') as temporary:
            candidate=Path(temporary)/self.name
            candidate.write_bytes(unit_bytes(self.name,self.command('resume-boot'),self.document['listener']))
            self.ops.command('boot_repair_candidate_unit_check',['systemd-analyze','verify',str(candidate)])
        return {'production_modified':False,'schema':115,'source_roles':self.document['source_roles'],
            'containers':{kind:row['Id'] for kind,row in rows.items()},'plan_sha256':self.digest,
            'backup_execution_context':backup_context}
    def verify_public_normal(self):
        self.actor.assemble()
        with verification_window(self.actor.runtime,180):
            first=None;successes=0
            while True:
                self.actor.runtime.budget(1)
                try:
                    self.installed();self.actor.completed_evidence();self.actor.native();self.actor.kernel.normal()
                    for base in ('https://api.madarportal.com','https://madarportal.com/api'):
                        if base.startswith('https://api.'):
                            self.actor.runtime.http_status(base+'/')
                        version=self.actor.runtime.json_http(base+'/health/version')
                        ready=self.actor.runtime.json_http(base+'/health/ready')
                        fence=self.actor.runtime.json_http(base+'/health/recovery')
                        if (version.get('release_sha')!=self.plan.source_sha or version.get('release_slot')!=self.actor.candidate.slot
                                or version.get('schema_compatible_min')!=115 or version.get('schema_compatible_max')!=115
                                or ready.get('ready') is not True or fence!={'restricted':False,'business_writes_enabled':True}):
                            raise RuntimeError('boot_repair_public_normal_binding_changed')
                    self.actor.runtime.http_status('https://madarportal.com/')
                    proxy=self.actor.runtime.inspect(['madar-release-proxy'])['madar-release-proxy']
                    if proxy['State'].get('Health',{}).get('Status')!='healthy':raise AvailabilityFailure('boot_repair_proxy_activation_pending')
                except AvailabilityFailure:first=None;successes=0
                else:
                    successes+=1
                    if first is None:first=time.monotonic()
                    if successes>=3 and time.monotonic()-first>=5:return
                time.sleep(self.actor.runtime.budget(1))
    @contextmanager
    def locks(self):
        descriptors=[]
        try:
            for path in (self.ops.upgrade_root/'upgrade.lock',self.ops.state_root/'deploy.lock'):
                descriptors.append(acquire_lock(path,create=False))
            yield
        finally:
            for descriptor in reversed(descriptors):os.close(descriptor)
    def installed(self):
        self.verify()
        record=json.loads(protected(self.root/'installation.json',private=True).read_text())
        if (record.get('plan_sha256')!=self.digest or record.get('service')!=self.name
                or file_digest(protected(UNITS/self.name))!=record.get('unit_sha256')
                or file_digest(protected(DROPIN))!=record.get('dropin_sha256')):
            raise RuntimeError('boot_repair_installation_changed')
        self.baseline(installed=True)
        if self.ops.systemctl_state(self.old_name)['enabled']!='disabled':raise RuntimeError('boot_repair_old_actor_not_superseded')
        if self.ops.systemctl_state(self.name)['enabled']!='enabled':raise RuntimeError('boot_repair_new_actor_not_enabled')
        props=self.ops.command('boot_repair_effective_unit',['systemctl','show','madar-release-proxy.service','--property=Requires,ExecStartPre,DropInPaths','--no-pager']).stdout
        values=dict(line.split('=',1) for line in props.splitlines() if '=' in line)
        if (self.old_name in values.get('Requires','').split() or self.name not in values.get('Requires','').split()
                or self.command('check-proxy-gate') not in values.get('ExecStartPre','')
                or set(values.get('DropInPaths','').split())!=set(self.document['proxy_dropins'])):
            raise RuntimeError('boot_repair_effective_controls_changed')
    def install(self):
        with self.locks():
            self.preflight()
            self.root.mkdir(mode=0o700)
            exclusive(self.root/'authorization.json',encoded({'operation':OPERATION,'plan_sha256':self.digest,'source_bundle_sha256':self.document['source_bundle_sha256']}))
            self.authorized=True;self.verify()
            exclusive(self.root/'proxy-dropin-preimage.conf',DROPIN.read_bytes())
            body=unit_bytes(self.name,self.command('resume-boot'),self.document['listener'])
            dropin=dropin_bytes(self.name,self.command('check-proxy-gate'))
            exclusive(self.root/self.name,body)
            self.ops.command('boot_repair_unit_validate',['systemd-analyze','verify',str(self.root/self.name)])
            try:
                exclusive(UNITS/self.name,body);(UNITS/self.name).chmod(0o644)
                temporary=DROPIN.with_name('.'+self.digest+'.conf')
                exclusive(temporary,dropin);temporary.chmod(0o644);os.replace(temporary,DROPIN)
                descriptor=os.open(DROPIN.parent,os.O_RDONLY|os.O_DIRECTORY)
                try:os.fsync(descriptor)
                finally:os.close(descriptor)
                self.ops.command('boot_repair_disable_old',['systemctl','disable',self.old_name])
                self.ops.command('boot_repair_reload_units',['systemctl','daemon-reload'])
                self.ops.command('boot_repair_enable_new',['systemctl','enable',self.name])
                exclusive(self.root/'installation.json',encoded({'plan_sha256':self.digest,'service':self.name,
                    'unit_sha256':hashlib.sha256(body).hexdigest(),'dropin_sha256':hashlib.sha256(dropin).hexdigest(),
                    'installed_controller_unchanged':True,'original_unit_retained':self.old_name}))
                self.installed();self.event('installed')
            except Exception:
                # No startup/write change has happened; restore only the exact
                # owned boot drop-in preimage, retain new failed resources/audit.
                preimage=protected(self.root/'proxy-dropin-preimage.conf',private=True).read_bytes()
                current=DROPIN.read_bytes()
                if current not in (preimage,dropin):raise RuntimeError('boot_repair_install_rollback_preimage_changed')
                temp=DROPIN.with_name('.'+self.digest+'.rollback.conf');exclusive(temp,preimage);temp.chmod(0o644);os.replace(temp,DROPIN)
                self.ops.command('boot_repair_disable_failed',['systemctl','disable',self.name],check=False)
                self.ops.command('boot_repair_reenable_original',['systemctl','enable',self.old_name])
                self.ops.command('boot_repair_rollback_reload',['systemctl','daemon-reload'])
                self.event('installation_failed');raise
        # The service acquires the same locks itself. Never start it while the
        # coordinator holds them, and never invoke the consumed cutover.
        try:
            self.ops.command('boot_repair_initial_resume',['systemctl','start',self.name],timeout=300)
            self.verify_public_normal();self.event('public_normal_verified')
        except Exception as error:
            self.event('failed',exception_type=type(error).__name__)
            self.actor.compensate();raise
        # Reuse the already tested ordinary backup/restore/append-only replica
        # implementation in a NEW authorization namespace. Never touch old scopes.
        from deployment.lib.active_recovery_backup import capture_and_replicate
        descriptor=acquire_lock(Path('/var/lib/madar/backups/.backup.lock'),create=False)
        try:
            capture_and_replicate(self.plan,self.root,self.package,self.verify,self.actor.kernel,
                authorizing_context={'plan_sha256':self.digest,'source_bundle_sha256':self.document['source_bundle_sha256']})
        except Exception as error:
            # Backup errors cannot pretend to be success. Preserve healthy
            # original NORMAL and existing valid backup while reporting failure;
            # no unrelated timer, customer data or original receipt is reverted.
            self.event('post_boot_backup_failed',exception_type=type(error).__name__);raise
        finally:os.close(descriptor)
        try:self.verify_public_normal()
        except Exception as error:
            self.event('failed',exception_type=type(error).__name__)
            self.actor.compensate();raise
        self.event('complete')
        return {'mode':'NORMAL','schema':115,'plan_sha256':self.digest,'backup_restored_and_replicated':True}
    def resume(self):
        self.authorized=True
        with self.locks():
            self.installed()
            events=[json.loads(line) for line in protected(self.root/'events.jsonl',private=True).read_text().splitlines()]
            if any(row['stage'] in {'installation_failed','failed','compensation_pending','compensated'} for row in events):
                raise RuntimeError('boot_repair_failed_attempt_not_replayable')
            self.actor.assemble()
            if events[-1]['stage']=='installed':
                rows=self.actor.kernel.identities(workers_started=True,require_running=False)
                if any(row['State']['Running'] for row in rows.values()):
                    raise RuntimeError('boot_repair_initial_stopped_state_changed')
                for port in (self.actor.candidate.backend_port,self.actor.candidate.frontend_port):
                    with socket.socket() as probe:probe.bind(('127.0.0.1',port))
            # Original completion grants no new authorization. This NEW source
            # fence/receipt is checked by every reused runtime operation.
            return self.actor.resume()
    def proxy_gate(self):
        self.authorized=True;self.installed();return self.actor.proxy_gate()
