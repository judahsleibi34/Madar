"""Bind the existing ordinary backup pipeline to the fresh compatible upgrade.

This adapter changes neither the backup format nor the historical recovery
records. Each source/target backup gets a new append-only local/Node1 scope.
No test artifact is published as a production backup by this module.
"""
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace

from deployment.lib.completed_normal_admission import ADMISSIONS,OPERATION,digest,encoded,require_fresh_authorization
from deployment.lib.provider_recovery_runtime import protected,readonly_configuration,file_digest


class CompletedNormalBackupContext:
    def __init__(self,contract,document,package,kernel,*,stage,source_guard,artifact_guard):
        if stage not in {'pre-migration','post-migration'} or not all(callable(f) for f in (source_guard,artifact_guard)):
            raise RuntimeError('completed_backup_independent_guards_required')
        self.contract,self.document,self.package,self.kernel=contract,document,Path(package),kernel
        self.context=digest(contract);self.root=ADMISSIONS/self.context
        self.stage=stage;self.schema=115 if stage=='pre-migration' else 136
        self.source_guard,self.artifact_guard=source_guard,artifact_guard
        self.receipt_name=stage+'-backup.json'
        self.scope=digest({'operation':OPERATION,'context_sha256':self.context,'backup_stage':stage})
        self.plan=SimpleNamespace(digest=self.scope,source_sha=contract['candidate']['source_sha'],
            candidate_images=contract['candidate']['images'])
        if (kernel.contract!=contract or kernel.root!=self.root or document.get('source_bundle_sha256') is None
                or digest(document)!=contract['plan_sha256']):
            raise RuntimeError('completed_backup_runtime_binding_invalid')

    def validate(self,plan,root,package):
        if os.geteuid()!=0:raise RuntimeError('completed_backup_root_required')
        self.source_guard();require_fresh_authorization(self.contract)
        if (Path(root)!=self.root or Path(package)!=self.package or plan.digest!=self.scope
                or plan.source_sha!=self.plan.source_sha or plan.candidate_images!=self.plan.candidate_images
                or file_digest(protected(self.package/'source-bundle.json',private=True))!=self.document['source_bundle_sha256']):
            raise RuntimeError('completed_backup_fresh_binding_invalid')
        receipt=json.loads(protected(self.root/'operator-authorization.json',private=True).read_text())
        if receipt!={'operation':OPERATION,'context_sha256':self.context,'plan_sha256':self.contract['plan_sha256'],
                'source_bundle_sha256':self.document['source_bundle_sha256'],
                'controller_sha':self.contract['candidate']['controller_sha'],'application_sha':self.plan.source_sha}:
            raise RuntimeError('completed_backup_operator_binding_changed')
        admission=json.loads(protected(self.root/'admission.json').read_text())
        if admission.get('operation')!=OPERATION or admission.get('contract')!=self.contract:
            raise RuntimeError('completed_backup_admission_changed')
        if (self.root/self.receipt_name).exists():raise RuntimeError('completed_backup_stage_already_consumed')

    def artifacts(self):
        report=self.artifact_guard()
        replica=report.get('node1_replica',{}) if isinstance(report,dict) else {}
        if (set(replica)!={'host','filesystem_uuid','configuration_sha256'}
                or replica['host']!='madar-node1-lan'
                or not re.fullmatch('[0-9a-f-]{36}',str(replica['filesystem_uuid']))
                or replica['configuration_sha256']!=self.document['live_configuration_sha256']['node1_configuration']):
            raise RuntimeError('completed_backup_replica_binding_invalid')
        return report

    def guard(self):
        self.source_guard();require_fresh_authorization(self.contract)
        if self.kernel.native_verifier()!=self.schema:raise RuntimeError('completed_backup_schema_changed')
        self.kernel.round(normal=self.stage=='post-migration')

    def role_names(self):
        # Read role NAMES from the current native database. Passwords,
        # attributes and memberships are never copied into this inventory.
        self.guard()
        raw=self.kernel.runtime.command(['docker','exec',self.contract['database']['container_id'],
            'psql','-XqAt','-v','ON_ERROR_STOP=1','-U','postgres','-d','postgres','-c',
            "BEGIN READ ONLY; SELECT json_agg(rolname ORDER BY rolname)::text FROM pg_roles; COMMIT;"])
        names=json.loads(raw)
        if (not isinstance(names,list) or not names or len(names)!=len(set(names))
                or any(not re.fullmatch('[a-zA-Z_][a-zA-Z0-9_]*',str(n)) for n in names)):
            raise RuntimeError('completed_backup_role_inventory_invalid')
        return tuple(names)

    def capture(self):
        from deployment.lib.active_recovery_backup import capture_and_replicate
        return capture_and_replicate(self.plan,self.root,self.package,self.source_guard,self.kernel,completed_context=self)

    def seal_migration_inputs(self,receipt):
        """Issue only actual verified source115 backup/restore/replica evidence."""
        from deployment.lib.completed_normal_migration import intent_document
        from deployment.lib.emergency_routing_repair import exclusive
        self.guard()
        actual=json.loads(protected(self.root/self.receipt_name,private=True).read_text())
        if (self.stage!='pre-migration' or receipt!=actual or actual.get('schema')!=115
                or actual.get('context_sha256')!=self.context or actual.get('plan_sha256')!=self.scope
                or actual.get('source_sha')!=self.plan.source_sha or actual.get('images')!=self.plan.candidate_images
                or actual.get('restore',{}).get('status')!='logical_database_and_file_restore_passed'
                or actual.get('restore',{}).get('backup_schema')!=115
                or actual.get('node1',{}).get('checksum_exit_code')!=0):
            raise RuntimeError('completed_backup_migration_evidence_invalid')
        from scripts import backup_support
        backup=Path(actual['local_path']);manifest=backup_support.verify(backup)
        if manifest['release']['git_sha']!=self.plan.source_sha or int(manifest['database']['schema_version'])!=115:
            raise RuntimeError('completed_backup_migration_release_changed')
        inputs={'intent':intent_document(self.contract),'backup':str(backup),
            'backup_manifest_sha256':file_digest(readonly_configuration(backup/'manifest.json',private=False)),
            'backup_checksums_sha256':file_digest(readonly_configuration(backup/'SHA256SUMS',private=False)),
            'restore_execution_sha256':digest(actual['restore']),'replica_execution_sha256':digest(actual['node1'])}
        exclusive(self.root/'migration-inputs.json',encoded(inputs))
        return inputs
