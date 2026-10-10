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
        compensated=(getattr(self.plan,'candidate_destination',None) or {}).get('post_compensation')
        from deployment.lib.active_recovery_retained_fallback import declaration,verify_backup,verify_runtime
        retained=declaration(self.plan)
        if compensated and not retained:
            from deployment.lib.active_recovery_compensated import verify_compensated_binding,inspect_history
            verify_compensated_binding(compensated,staged_plan=self.plan)
            previous,previous_root,records,_=inspect_history(compensated['baseline']['previous_plan_sha256'])
            old=records['fallback-listener-installation.json'];old_unit=protected(UNITS/old['service'])
            if file_digest(old_unit)!=old['unit_sha256'] or self.ops.systemctl_state(old['service'])!={'enabled':'enabled','active':'active'}:
                raise RuntimeError('fallback_reuse_installed_identity_changed')
            # A NEW measured reconciliation record, never an old authorization.
            # Old source remains frozen and enforces stopped-consumer READ_ONLY
            # current-data fallback; no source/image approval is transferred.
            exclusive(self.root/'fallback-listener-installation.json',encoded({'version':1,'plan_sha256':self.plan.digest,
                'source_bundle_sha256':self.plan.source_bundle_sha256,'service':old['service'],
                'unit_sha256':old['unit_sha256'],'loopback_ports':FALLBACK_PORTS,
                'historical_installation_modified':False,'reused_from_plan':previous.digest,
                'reused_source_bundle_sha256':previous.source_bundle_sha256}))
            return old['service']
        if unit.exists() or unit.is_symlink() or (self.root/'fallback-listener-installation.json').exists():
            raise FileExistsError('fallback_installation_namespace_used')
        previous=None
        if retained:
            from deployment.lib.active_recovery_compensated import verify_compensated_binding,inspect_history
            verify_compensated_binding(compensated,staged_plan=self.plan)
            verify_backup(self.plan);verify_runtime(self.plan,__import__('deployment.lib.emergency_routing_repair',fromlist=['Runtime']).Runtime())
            old,old_root,records,_=inspect_history(compensated['baseline']['previous_plan_sha256'])
            previous=records['fallback-listener-installation.json']['service']
            old_unit=protected(UNITS/previous)
            if file_digest(old_unit)!=records['fallback-listener-installation.json']['unit_sha256']:
                raise RuntimeError('fallback_supersession_preimage_changed')
            exclusive(self.root/'fallback-unit-preimage.service',old_unit.read_bytes())
        for port in (() if retained else FALLBACK_PORTS.values()):
            with socket.socket() as test:test.bind(('127.0.0.1',port))
        body=self.content()
        exclusive(self.root/self.name,body)
        self.ops.command('continuation_listener_validate',['/usr/bin/systemd-analyze','verify',str(self.root/self.name)])
        self.guard()
        # Exclusive root publication; old emergency units/drop-ins are untouched.
        exclusive(unit,body);unit.chmod(0o644)
        if previous:
            exclusive(self.root/'fallback-supersession-intent.json',encoded({'plan_sha256':self.plan.digest,
                'source_bundle_sha256':self.plan.source_bundle_sha256,'previous_service':previous,
                'previous_unit_sha256':file_digest(protected(UNITS/previous)),
                'replacement_service':self.name,'replacement_unit_sha256':file_digest(unit),
                'historical_unit_modified':False}))
            self.ops.command('continuation_listener_disable_consumed',['/usr/bin/systemctl','disable','--now',previous])
        try:
            self.ops.command('continuation_listener_reload',['/usr/bin/systemctl','daemon-reload'])
            self.ops.command('continuation_listener_enable',['/usr/bin/systemctl','enable','--now',self.name])
            if self.ops.systemctl_state(self.name)!={'enabled':'enabled','active':'active'}:
                raise RuntimeError('fallback_installation_service_not_active')
        except Exception:
            if previous:
                # Own exact new unit only; retain all bytes/records. The previous
                # restricted listener remains fail-closed if its marker is stale.
                if file_digest(protected(unit))!=__import__('hashlib').sha256(body).hexdigest():
                    raise RuntimeError('fallback_supersession_replacement_changed') from None
                self.ops.command('continuation_listener_stop_failed',['/usr/bin/systemctl','disable','--now',self.name])
                self.ops.command('continuation_listener_restore_previous',['/usr/bin/systemctl','enable','--now',previous])
            raise
        exclusive(self.root/'fallback-listener-installation.json',encoded({'version':1,'plan_sha256':self.plan.digest,
            'source_bundle_sha256':self.plan.source_bundle_sha256,'service':self.name,'unit_sha256':file_digest(unit),
            'loopback_ports':FALLBACK_PORTS,'historical_installation_modified':False,
            **({'superseded_listener':previous,'retained_local_fallback':True} if previous else {})}))
        return self.name
