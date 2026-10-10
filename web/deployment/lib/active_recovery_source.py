"""Exact root-private source fence for a freshly approved continuation.

No stage, installation, credential reconstruction or repository mutation.
The caller must freeze reviewed bytes before importing any root-executed code.
This check cannot convert mutable development imports into trusted execution.
"""
import json
import os
from pathlib import Path
import re
import sys
from deployment.lib.provider_recovery_runtime import protected,digest,file_digest

REQUIRED=frozenset({'web/deployment/lib/active_recovery_retained_fallback.py','web/deployment/lib/active_recovery_backup_freshness.py','web/scripts/finish_compensated_normal.py','web/scripts/verify_final_application_artifacts.py','web/scripts/backup_support.py','web/scripts/backup_madar.sh','web/scripts/verify_backup.sh','web/scripts/rehearse_backup.py','web/scripts/normal_backup_replica.py','web/scripts/resume_active_recovery.py','web/deployment/lib/active_recovery_operations.py','web/deployment/lib/active_recovery_artifact_evidence.py','web/deployment/lib/active_recovery_backup.py','web/deployment/lib/active_recovery_boot_actor.py','web/deployment/lib/active_recovery_execution.py','web/scripts/boot_active_recovery.py','web/deployment/lib/active_recovery_resumption.py',
    'web/deployment/lib/active_recovery_source.py','web/deployment/lib/active_recovery_runtime.py','web/deployment/lib/active_recovery_boot_installation.py','web/deployment/lib/active_recovery_proxy.py','web/deployment/lib/active_recovery_boot.py','web/deployment/lib/active_recovery_listener.py','web/scripts/serve_active_recovery_fallback.py','web/deployment/lib/active_recovery_reconciliation.py','web/deployment/lib/active_recovery_publication.py','web/deployment/lib/active_recovery_write_authority.py','web/deployment/lib/active_recovery_workers.py','web/deployment/lib/active_recovery_controller.py','web/deployment/lib/active_recovery_compensated.py','web/deployment/lib/active_recovery_inputs.py',
    'web/deployment/lib/active_recovery_candidate.py','web/deployment/lib/active_recovery_handoff.py',
    'web/deployment/lib/active_recovery_fallback.py','web/deployment/lib/checkpoint_execution_proof.py',
    'web/deployment/lib/provider_local_transition_runtime.py','web/deployment/lib/control_plane_upgrade.py',
    'web/deployment/bin/madar-install-control-plane'})

class FrozenContinuationSource:
    def __init__(self,plan,root):self.plan=plan;self.root=Path(root)
    def verify(self):
        if os.geteuid()!=0 or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
            raise RuntimeError('continuation_isolated_frozen_entry_required')
        manifest_path=protected(self.root/'source-bundle.json',private=True)
        if file_digest(manifest_path)!=self.plan.source_bundle_sha256:
            raise RuntimeError('continuation_source_manifest_bytes_changed')
        manifest=json.loads(manifest_path.read_text())
        from deployment.lib.active_recovery_resumption import controller_revision
        if digest(manifest)!=self.plan.source_bundle_sha256 or type(manifest.get('version')) is not int or manifest.get('version')!=1 or manifest.get('source_sha')!=controller_revision(self.plan):
            raise RuntimeError('continuation_source_manifest_changed')
        files=manifest.get('files',{})
        if not isinstance(files,dict) or not REQUIRED.issubset(files):
            raise RuntimeError('continuation_source_inventory_incomplete')
        source=self.root/'source'
        actual={path.relative_to(source).as_posix() for path in source.rglob('*') if path.is_file() or path.is_symlink()}
        if actual!=set(files):raise RuntimeError('continuation_source_inventory_changed')
        for relative,expected in files.items():
            path=Path(relative)
            if path.is_absolute() or '..' in path.parts or path.as_posix()!=relative or not re.fullmatch(r'[0-9a-f]{64}',str(expected)):
                raise RuntimeError('continuation_source_path_invalid')
            target=protected(source/path,private=True)
            if target.stat().st_mode&0o200 or target.suffix in {'.pyc','.pyo'} or file_digest(target)!=expected:
                raise RuntimeError('continuation_frozen_source_changed')
        # Every imported deployment module must come from the measured snapshot;
        # installed/mutable development modules and site imports are forbidden.
        locations={str(source/relative) for relative in files}
        bare_helpers={Path(relative).stem for relative in files if relative.startswith('web/deployment/lib/') and relative.endswith('.py')}
        for name,module in list(sys.modules.items()):
            if name in {'deployment','scripts'} or name in bare_helpers or name.startswith(('deployment.','scripts.')):
                location=getattr(module,'__file__',None)
                if location is not None and Path(location).absolute().as_posix() not in locations:
                    raise RuntimeError('continuation_foreign_privileged_import')
        return manifest
