"""Additive boot-gate preparation for a freshly approved normal continuation.

Old emergency files/units remain intact. The new boot actor must support both
completed NORMAL and interrupted current-data restricted recovery. No actor is
started here; daemon reload does not publish routing or grant writes.
"""
import json
import os
from pathlib import Path
import re
from deployment.lib.active_recovery_resumption import ROOT
from deployment.lib.active_recovery_source import FrozenContinuationSource
from deployment.lib.provider_recovery_runtime import protected,file_digest
from deployment.lib.emergency_routing_repair import exclusive,encoded
from deployment.lib.control_plane_upgrade import SystemOperations

UNITS=Path('/etc/systemd/system')
DROPIN=UNITS/'madar-release-proxy.service.d/92-normal-local-continuation.conf'

class ActiveRecoveryBootInstallation:
    def __init__(self,plan,root,package,*,operations=None):
        self.plan,self.root,self.package=plan,Path(root),Path(package)
        self.source=FrozenContinuationSource(plan,self.package);self.ops=operations or SystemOperations()
        self.name='madar-normal-local-boot-'+plan.digest[:12]+'.service'
    def guard(self):
        self.source.verify()
        if os.geteuid()!=0 or self.root!=ROOT/self.plan.digest:raise RuntimeError('boot_installation_fresh_root_required')
        receipt=json.loads(protected(self.root/'authorization.json',private=True).read_text())
        events=[json.loads(line) for line in protected(self.root/'events.jsonl',private=True).read_text().splitlines()]
        if (receipt.get('operation')!='active-local-rollback-resumption' or receipt.get('plan_sha256')!=self.plan.digest
                or receipt.get('source_bundle_sha256')!=self.plan.source_bundle_sha256
                or not events or events[-1].get('phase')!='detached_candidate_ready'
                or any(row.get('plan_sha256')!=self.plan.digest for row in events)):
            raise RuntimeError('boot_installation_phase_denied')
        listeners=json.loads(protected(self.root/'fallback-listener-installation.json',private=True).read_text())
        compensated=(getattr(self.plan,'candidate_destination',None) or {}).get('post_compensation')
        expected_service='madar-normal-local-fallback-'+self.plan.digest[:12]+'.service'
        if compensated:
            prior=compensated['baseline']['previous_plan_sha256']
            if listeners.get('reused_from_plan')!=prior:raise RuntimeError('boot_installation_reused_listener_not_bound')
            expected_service='madar-normal-local-fallback-'+prior[:12]+'.service'
            expected_hash=compensated['baseline']['startup']['files'].get(str(UNITS/expected_service))
            if listeners.get('unit_sha256')!=expected_hash:raise RuntimeError('boot_installation_reused_listener_changed')
        if (listeners.get('plan_sha256')!=self.plan.digest or listeners.get('source_bundle_sha256')!=self.plan.source_bundle_sha256
                or listeners.get('service')!=expected_service):
            raise RuntimeError('boot_installation_listener_binding_changed')
        unit=protected(UNITS/listeners['service'])
        if file_digest(unit)!=listeners.get('unit_sha256') or self.ops.systemctl_state(listeners['service'])!={'enabled':'enabled','active':'active'}:
            raise RuntimeError('boot_installation_listener_service_changed')
        return listeners['service']
    def command(self,mode):
        if mode not in {'resume-boot','check-proxy-gate'}:raise RuntimeError('boot_installation_mode_invalid')
        for path in (self.root,self.package):
            if not path.is_absolute() or not re.fullmatch(r'/[A-Za-z0-9._/-]+',str(path)):
                raise RuntimeError('boot_installation_path_invalid')
        entry=self.package/'source/web/scripts/boot_active_recovery.py'
        protected(entry,private=True)
        return f'/usr/bin/python3 -I -B {entry} {mode} --plan-root {self.root} --source-package {self.package} --approved-plan {self.plan.digest} --approved-source {self.plan.source_bundle_sha256}'
    def install(self):
        listener=self.guard();unit=UNITS/self.name
        compensated=(getattr(self.plan,'candidate_destination',None) or {}).get('post_compensation')
        if unit.exists() or unit.is_symlink() or (not compensated and (DROPIN.exists() or DROPIN.is_symlink())):
            raise FileExistsError('boot_installation_namespace_used')
        previous_boot=None
        if compensated:
            previous_boot='madar-normal-local-boot-'+compensated['baseline']['previous_plan_sha256'][:12]+'.service'
            expected=compensated['baseline']['startup']['files'].get(str(DROPIN))
            if file_digest(protected(DROPIN))!=expected or self.ops.systemctl_state(previous_boot)!={'enabled':'enabled','active':'inactive'}:
                raise RuntimeError('boot_supersession_preimage_changed')
            exclusive(self.root/'proxy-boot-dropin-preimage.conf',DROPIN.read_bytes())
        # Preserve the actual previous effective proxy unit as DATA, not a
        # substitute installation witness or authorization for the new source.
        old=self.ops.command('continuation_proxy_unit_observe',['/usr/bin/systemctl','cat','madar-release-proxy.service']).stdout
        exclusive(self.root/'proxy-unit-preimage.txt',old.encode())
        body=('[Unit]\nDescription=Madar exact-plan boot reconciliation\n'
            f'Requires=docker.service {listener}\nAfter=docker.service {listener}\n'
            '[Service]\nType=oneshot\nRemainAfterExit=yes\nUser=root\nGroup=root\nUMask=0077\n'
            'Environment=PATH=/usr/sbin:/usr/bin:/sbin:/bin\nEnvironment=HOME=/root\nEnvironment=LANG=C.UTF-8\n'
            f'ExecStart={self.command("resume-boot")}\nTimeoutStartSec=300\nNoNewPrivileges=yes\n'
            '[Install]\nWantedBy=multi-user.target\n').encode()
        dropin=('[Unit]\n'+f'Requires={self.name}\nAfter={self.name}\n'
            '[Service]\nExecStartPre=\n'+f'ExecStartPre={self.command("check-proxy-gate")}\n').encode()
        exclusive(self.root/self.name,body)
        exclusive(self.root/'proxy-normal-boot-dropin.conf',dropin)
        self.ops.command('continuation_boot_unit_validate',['/usr/bin/systemd-analyze','verify',str(self.root/self.name)])
        if compensated:
            exclusive(self.root/'boot-supersession-intent.json',encoded({'version':1,'plan_sha256':self.plan.digest,
                'previous_boot':previous_boot,'previous_enabled':'enabled','preimage_sha256':expected,
                'replacement_sha256':__import__('hashlib').sha256(dropin).hexdigest(),
                'unit_sha256':__import__('hashlib').sha256(body).hexdigest(),'database_restore':False}))
        self.guard();exclusive(unit,body);unit.chmod(0o644)
        if not DROPIN.parent.is_dir():raise RuntimeError('boot_installation_proxy_dropin_directory_missing')
        if compensated:
            # Replace ONLY this attested continuation-owned drop-in. Keeping a
            # second Requires drop-in would run the consumed boot actor as well.
            if file_digest(protected(DROPIN))!=expected:raise RuntimeError('boot_supersession_preimage_changed')
            temporary=DROPIN.with_name('.'+self.plan.digest+'.conf')
            exclusive(temporary,dropin);temporary.chmod(0o644)
            os.replace(temporary,DROPIN)
            descriptor=os.open(DROPIN.parent,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(descriptor)
            finally:os.close(descriptor)
            self.ops.command('continuation_boot_disable_consumed',['/usr/bin/systemctl','disable',previous_boot])
        else:
            exclusive(DROPIN,dropin);DROPIN.chmod(0o644)
        self.ops.command('continuation_boot_daemon_reload',['/usr/bin/systemctl','daemon-reload'])
        self.ops.command('continuation_boot_enable',['/usr/bin/systemctl','enable',self.name])
        # Never --now: preparing the future boot actor must not switch the
        # currently serving restricted recovery to compensation during staging.
        exclusive(self.root/'boot-installation.json',encoded({'version':1,'plan_sha256':self.plan.digest,
            'source_bundle_sha256':self.plan.source_bundle_sha256,'service':self.name,
            'unit_sha256':file_digest(unit),'dropin_sha256':file_digest(DROPIN),
            'historical_files_modified':bool(compensated),'historical_receipts_modified':False,'routing_published':False,
            'superseded_boot':previous_boot,'previous_dropin_preserved':bool(compensated)}))


def verify_post_compensation_boot(plan,root,runtime):
    """Re-attest controlled 92 supersession before public handoff/early reboot."""
    compensated=(plan.candidate_destination or {}).get('post_compensation')
    if not compensated:raise RuntimeError('boot_supersession_contract_required')
    root=Path(root);baseline=compensated['baseline']['startup'];previous=compensated['baseline']['previous_plan_sha256']
    receipt=json.loads(protected(root/'boot-installation.json',private=True).read_text())
    intent=json.loads(protected(root/'boot-supersession-intent.json',private=True).read_text())
    name='madar-normal-local-boot-'+plan.digest[:12]+'.service'
    old='madar-normal-local-boot-'+previous[:12]+'.service'
    if (receipt.get('plan_sha256')!=plan.digest or receipt.get('source_bundle_sha256')!=plan.source_bundle_sha256
            or receipt.get('service')!=name or receipt.get('superseded_boot')!=old
            or intent.get('plan_sha256')!=plan.digest or intent.get('previous_boot')!=old
            or intent.get('preimage_sha256')!=baseline['files'][str(DROPIN)]
            or file_digest(protected(root/'proxy-boot-dropin-preimage.conf',private=True))!=intent['preimage_sha256']
            or file_digest(protected(DROPIN))!=intent['replacement_sha256']
            or receipt.get('dropin_sha256')!=intent['replacement_sha256']
            or file_digest(protected(UNITS/name))!=intent['unit_sha256']
            or receipt.get('unit_sha256')!=intent['unit_sha256']):
        raise RuntimeError('boot_supersession_attestation_changed')
    for filename,expected in baseline['files'].items():
        if filename!=str(DROPIN) and file_digest(protected(Path(filename)))!=expected:
            raise RuntimeError('boot_supersession_retained_controls_changed')
    expected_dropins=sorted(filename for filename in baseline['files'] if '/madar-release-proxy.service.d/' in filename)
    physical=sorted(str(p) for p in DROPIN.parent.iterdir())
    if physical!=expected_dropins:raise RuntimeError('boot_supersession_unexpected_dropin')
    new_state=dict(line.split('=',1) for line in runtime.command(['systemctl','show',name,
        '--property=UnitFileState','--no-pager']).splitlines() if '=' in line)
    if new_state!={'UnitFileState':'enabled'}:raise RuntimeError('boot_supersession_new_actor_not_enabled')
    props=dict(line.split('=',1) for line in runtime.command(['systemctl','show','madar-release-proxy.service',
        '--property=FragmentPath,DropInPaths,Requires,ExecStartPre','--no-pager']).splitlines() if '=' in line)
    if (props.get('FragmentPath')!=str(UNITS/'madar-release-proxy.service')
            or props.get('DropInPaths','').split()!=expected_dropins
            or old in props.get('Requires','').split() or name not in props.get('Requires','').split()):
        raise RuntimeError('boot_supersession_effective_controls_changed')
    states=dict(line.split('=',1) for line in runtime.command(['systemctl','show',old,
        '--property=ActiveState,UnitFileState','--no-pager']).splitlines() if '=' in line)
    if states!={'ActiveState':'inactive','UnitFileState':'disabled'}:
        raise RuntimeError('boot_supersession_consumed_actor_not_disabled')
    return receipt
