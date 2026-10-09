"""Additive, exact-source installation of NEW compensation listeners.

Never replaces the emergency helper, service, credentials or audit records.
Loopback listeners are fail-closed until fresh compensation authority exists.
This component does not change proxy routing or grant normal production.
"""
import json
import os
from pathlib import Path
import re
import socket
from deployment.lib.active_recovery_resumption import ROOT
from deployment.lib.active_recovery_source import FrozenContinuationSource
from deployment.lib.active_recovery_fallback import FALLBACK_PORTS
from deployment.lib.emergency_routing_repair import exclusive,encoded
from deployment.lib.provider_recovery_runtime import protected,file_digest
from deployment.lib.control_plane_upgrade import SystemOperations

UNITS=Path('/etc/systemd/system')

class ActiveRecoveryFallbackInstallation:
    def __init__(self,plan,root,package,*,operations=None):
        self.plan,self.root,self.package=plan,Path(root),Path(package)
        self.source=FrozenContinuationSource(plan,self.package)
        self.ops=operations or SystemOperations()
        self.name='madar-normal-local-fallback-'+plan.digest[:12]+'.service'
    def guard(self):
        self.source.verify()
        if os.geteuid()!=0 or self.root!=ROOT/self.plan.digest:raise RuntimeError('fallback_installation_fresh_root_required')
        receipt=json.loads(protected(self.root/'authorization.json',private=True).read_text())
        events=[json.loads(line) for line in protected(self.root/'events.jsonl',private=True).read_text().splitlines()]
        if (receipt.get('operation')!='active-local-rollback-resumption' or receipt.get('plan_sha256')!=self.plan.digest
                or receipt.get('source_bundle_sha256')!=self.plan.source_bundle_sha256
                or not events or events[-1].get('phase')!='detached_candidate_ready'
                or any(row.get('plan_sha256')!=self.plan.digest for row in events)):
            raise RuntimeError('fallback_installation_phase_denied')
    def content(self):
        for path in (self.package,self.root):
            if not path.is_absolute() or not re.fullmatch(r'/[A-Za-z0-9._/-]+',str(path)):
                raise RuntimeError('fallback_installation_path_invalid')
        entry=self.package/'source/web/scripts/serve_active_recovery_fallback.py'
        protected(entry,private=True)
        command=f'/usr/bin/python3 -I -B {entry} --plan-root {self.root} --source-package {self.package} --approved-plan {self.plan.digest} --approved-source {self.plan.source_bundle_sha256}'
        return ('[Unit]\nDescription=Madar exact-plan restricted compensation listener\nRequires=docker.service\nAfter=docker.service\n'
            '[Service]\nType=simple\nUser=root\nGroup=root\nUMask=0077\n'
            'Environment=PATH=/usr/sbin:/usr/bin:/sbin:/bin\nEnvironment=HOME=/root\nEnvironment=LANG=C.UTF-8\n'
            f'ExecStart={command}\nRestart=on-failure\nRestartSec=5\nTimeoutStopSec=45\n'
            'NoNewPrivileges=yes\nPrivateTmp=yes\nProtectSystem=strict\nProtectHome=yes\n'
            'RestrictAddressFamilies=AF_INET AF_UNIX\nLimitNOFILE=256\nTasksMax=64\nMemoryMax=256M\n'
            '[Install]\nWantedBy=multi-user.target\n').encode()
    def install(self):
        self.guard();unit=UNITS/self.name
        if unit.exists() or unit.is_symlink() or (self.root/'fallback-listener-installation.json').exists():
            raise FileExistsError('fallback_installation_namespace_used')
        for port in FALLBACK_PORTS.values():
            with socket.socket() as test:test.bind(('127.0.0.1',port))
        body=self.content()
        exclusive(self.root/self.name,body)
        self.ops.command('continuation_listener_validate',['/usr/bin/systemd-analyze','verify',str(self.root/self.name)])
        self.guard()
        # Exclusive root publication; old emergency units/drop-ins are untouched.
        exclusive(unit,body);unit.chmod(0o644)
        self.ops.command('continuation_listener_reload',['/usr/bin/systemctl','daemon-reload'])
        self.ops.command('continuation_listener_enable',['/usr/bin/systemctl','enable','--now',self.name])
        if self.ops.systemctl_state(self.name)!={'enabled':'enabled','active':'active'}:
            raise RuntimeError('fallback_installation_service_not_active')
        exclusive(self.root/'fallback-listener-installation.json',encoded({'version':1,'plan_sha256':self.plan.digest,
            'source_bundle_sha256':self.plan.source_bundle_sha256,'service':self.name,'unit_sha256':file_digest(unit),
            'loopback_ports':FALLBACK_PORTS,'historical_installation_modified':False}))
        return self.name
