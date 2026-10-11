"""Root write boundary for one credential-bound completed-NORMAL upgrade.

The madar deployment child can stage/start READ_ONLY standbys, but cannot create
or widen a grant. This effect requires actual live runtime checks supplied by
the exact frozen root coordinator, including boot supersession and accepted
artifact verification. Historical acceptance does not authorize this boundary.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time

from deployment.lib.completed_normal_admission import (
    ADMISSIONS, OPERATION, digest, encoded, require_fresh_authorization,
    require_candidate_authority, verify_history,
)
from deployment.lib.emergency_routing_repair import exclusive, verification_window, AvailabilityFailure
from deployment.lib.provider_recovery_runtime import protected
from deployment.lib.runtime_authority import runtime_mutation_lock
from deployment.lib.completed_normal_resources import origin_spec_matches


def atomic_public_authority(path: Path, value: dict) -> None:
    """Publish a nonsecret root grant without a transient unreadable rename."""
    protected(path)
    descriptor, temporary = tempfile.mkstemp(prefix='.grant-',dir=path.parent)
    try:
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(encoded(value));stream.flush();os.fsync(stream.fileno())
        os.chmod(temporary,0o644)
        os.replace(temporary,path)
        directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


class CompletedNormalWriteHandoff:
    def __init__(self,contract,kernel,*,source_guard,boot_guard,artifact_guard,
                 admissions=ADMISSIONS,state_root=Path('/var/lib/madar/releases')):
        if not all(callable(f) for f in (source_guard,boot_guard,artifact_guard)):
            raise RuntimeError('completed_normal_write_independent_guards_required')
        self.contract,self.kernel=contract,kernel
        self.admissions,self.state_root=Path(admissions),Path(state_root)
        self.root=self.admissions/digest(contract)
        self.source_guard,self.boot_guard,self.artifact_guard=source_guard,boot_guard,artifact_guard
        if kernel.publication_name!='candidate-runtime.json' or kernel.root!=self.root or kernel.contract!=contract:
            raise RuntimeError('completed_normal_write_candidate_binding_invalid')

    def authorization(self, *, schema=115):
        if schema not in {115,136}:
            raise RuntimeError('completed_normal_write_target_schema_invalid')
        if os.geteuid()!=0:raise RuntimeError('completed_normal_write_root_required')
        self.source_guard()
        require_fresh_authorization(self.contract)
        receipt=json.loads(protected(self.root/'admission.json').read_text())
        if receipt.get('operation')!=OPERATION or receipt.get('contract')!=self.contract:
            raise RuntimeError('completed_normal_write_fresh_admission_changed')
        verify_history(self.contract)
        self.boot_guard()
        self.artifact_guard()
        if self.kernel.native_verifier()!=schema:
            raise RuntimeError('completed_normal_write_source_schema_changed')
        if schema==136:
            from deployment.lib.completed_normal_database import require_normal_migration_boundary
            require_normal_migration_boundary(self.contract,schema,self.root,self.state_root)

    def guard(self, *, schema=115):
        self.authorization(schema=schema)
        roles=self.contract['source_roles']
        origin=json.loads(protected(Path(roles['completion_root'])/'write-authority/authority.json').read_text())
        if origin!={'version':1,'schema':115,'release_sha':roles['application_sha'],
                'contract_digest':self.contract['origin']['write_contract_digest'],'mode':'READ_ONLY'}:
            raise RuntimeError('completed_normal_write_origin_not_fenced')
        self.kernel.round(normal=False)
        self.source_guard()

    def fence_origin(self):
        """Revoke the verified old grant before the madar worker handoff.

        The original receipt/authorization are never edited. Its live mutable
        grant is independently checked, saved as a NEW exact preimage, then
        revoked by this fresh operation. No customer or Auth rows are modified.
        """
        self.authorization()
        roles=self.contract['source_roles'];old_root=Path(roles['completion_root'])
        path=old_root/'write-authority/authority.json'
        expected={'version':1,'schema':115,'release_sha':roles['application_sha'],
                  'contract_digest':self.contract['origin']['write_contract_digest'],'mode':'NORMAL'}
        if json.loads(protected(path).read_text())!=expected:
            raise RuntimeError('completed_normal_origin_positive_grant_changed')
        binding=json.loads(protected(old_root/'candidate-identities.json',private=True).read_text())
        if (binding.get('plan_sha256')!=roles['original_plan_sha256']
                or binding.get('source_sha')!=roles['application_sha']
                or set(binding.get('runtimes',{}))!={'backend','frontend','parser','notification','calendar-sync','data-deletion'}):
            raise RuntimeError('completed_normal_origin_runtime_binding_changed')
        runtime=self.kernel.runtime
        rows=runtime.inspect([value['id'] for value in binding['runtimes'].values()])
        for kind,identity in binding['runtimes'].items():
            row=next((r for r in rows.values() if r['Id']==identity['id']),None)
            if (row is None or row['Image']!=identity['image'] or not row['State']['Running']
                    or not origin_spec_matches(row,identity['spec_sha256'],started_worker=kind in {'notification','calendar-sync','data-deletion'})):
                raise RuntimeError('completed_normal_origin_runtime_changed')
        port=8101 if self.contract['origin']['slot']=='blue' else 8201
        base=f'http://127.0.0.1:{port}'
        version=runtime.json_http(base+'/health/version')
        if (version.get('release_sha')!=roles['application_sha'] or version.get('release_slot')!=self.contract['origin']['slot']
                or version.get('schema_compatible_min')!=115 or version.get('schema_compatible_max')!=115
                or runtime.json_http(base+'/health/recovery')!={'restricted':False,'business_writes_enabled':True}):
            raise RuntimeError('completed_normal_origin_serving_identity_changed')
        with runtime_mutation_lock(self.state_root):
            self.authorization()
            if json.loads(protected(path).read_text())!=expected:
                raise RuntimeError('completed_normal_origin_positive_grant_changed')
            exclusive(self.root/'origin-grant-preimage.json',protected(path).read_bytes())
            atomic_public_authority(path,dict(expected,mode='READ_ONLY'))
            runtime.denied(base)

    def revoke(self):
        # Revocation cannot depend on a successful audit append or readiness.
        # It cannot restore an origin grant, old worker owner or customer DB.
        value=require_candidate_authority(self.contract,admissions=self.admissions)
        atomic_public_authority(self.root/'write-authority/authority.json',dict(value,mode='READ_ONLY'))
        require_candidate_authority(self.contract,mode='READ_ONLY',admissions=self.admissions)

    def grant(self, *, schema=115):
        self.guard(schema=schema)
        effect_started=False
        try:
            with runtime_mutation_lock(self.state_root):
                self.guard(schema=schema)
                path=self.root/'write-authority/authority.json'
                value=require_candidate_authority(self.contract,mode='READ_ONLY',admissions=self.admissions)
                suffix='' if schema==115 else '-136'
                exclusive(self.root/('pre-grant-authority'+suffix+'.json'),protected(path).read_bytes())
                exclusive(self.root/('write-boundary'+suffix+'.json'),encoded({'operation':OPERATION,'context_sha256':digest(self.contract),
                    'normal_writes_may_have_occurred':True,'restore_customer_database':False}))
                effect_started=True
                # The original115 grant remains historical data. The target
                # grant advances its schema only after root-sealed SQL evidence.
                self.authorization(schema=schema)
                atomic_public_authority(path,dict(value,mode='NORMAL',schema=schema))
                with verification_window(self.kernel.runtime,180):
                    first=None;successes=0
                    while True:
                        self.kernel.runtime.budget(1)
                        try:self.kernel.round(normal=True)
                        except AvailabilityFailure:first=None;successes=0
                        else:
                            successes+=1
                            if first is None:first=time.monotonic()
                            if successes>=3 and time.monotonic()-first>=5:break
                        time.sleep(self.kernel.runtime.budget(1))
                # Seal real runtime publication only after the positive boundary
                # and sustained checks. A READ_ONLY stage is not NORMAL evidence.
                self.authorization(schema=schema)
                actual=protected(self.root/'candidate-runtime.json',private=True).read_bytes()
                if schema==115:
                    exclusive(self.root/'normal-publication.json',actual)
                else:
                    if protected(self.root/'normal-publication.json',private=True).read_bytes()!=actual:
                        raise RuntimeError('completed_normal_write_publication_changed')
                    exclusive(self.root/'target-normal-publication.json',encoded({
                        'operation':OPERATION,'context_sha256':digest(self.contract),'schema':136,
                        'mode':'NORMAL','database_restored':False}))
        except Exception:
            if effect_started:
                try:self.revoke()
                finally:self.kernel.compensate_current_data()
            raise
        return {'operation':OPERATION,'context_sha256':digest(self.contract),'mode':'NORMAL',
                'schema':schema,'customer_database_restored':False}
