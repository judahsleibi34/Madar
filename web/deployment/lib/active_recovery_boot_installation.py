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
        if (listeners.get('plan_sha256')!=self.plan.digest or listeners.get('source_bundle_sha256')!=self.plan.source_bundle_sha256
                or listeners.get('service')!='madar-normal-local-fallback-'+self.plan.digest[:12]+'.service'):
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
        if unit.exists() or unit.is_symlink() or DROPIN.exists() or DROPIN.is_symlink():
            raise FileExistsError('boot_installation_namespace_used')
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
        self.guard();exclusive(unit,body);unit.chmod(0o644)
        if not DROPIN.parent.is_dir():raise RuntimeError('boot_installation_proxy_dropin_directory_missing')
        exclusive(DROPIN,dropin);DROPIN.chmod(0o644)
        self.ops.command('continuation_boot_daemon_reload',['/usr/bin/systemctl','daemon-reload'])
        self.ops.command('continuation_boot_enable',['/usr/bin/systemctl','enable',self.name])
        # Never --now: preparing the future boot actor must not switch the
        # currently serving restricted recovery to compensation during staging.
        exclusive(self.root/'boot-installation.json',encoded({'version':1,'plan_sha256':self.plan.digest,
            'source_bundle_sha256':self.plan.source_bundle_sha256,'service':self.name,
            'unit_sha256':file_digest(unit),'dropin_sha256':file_digest(DROPIN),
            'historical_files_modified':False,'routing_published':False}))
