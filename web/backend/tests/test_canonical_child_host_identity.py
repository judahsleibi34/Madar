"""Host observation transport uses existing issuer/witness trust, no authority."""
import copy
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import Mock,patch
import unittest

from deployment.lib import schema160_release as release
from deployment.lib import completed_normal_admission as admission
from deployment.lib import control_plane_upgrade as upgrade
from deployment.lib.completed_normal_profile import RECONCILED
import test_historical_origin as fixtures


class CanonicalChildHostIdentityTests(unittest.TestCase):
    def setUp(self):
        # The unit image intentionally has no host machine-id. Model that one
        # file here; native guest acceptance reobserves the actual kernel/host.
        self.machine='1'*32
        read=Path.read_text
        def machine_file(path,*a,**kw):
            return self.machine if str(path)=='/etc/machine-id' else read(path,*a,**kw)
        self.enterContext(patch.object(Path,'read_text',machine_file))
        self.boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        self.registration={'context_sha256':'a'*64,'guest_uuid':'00000000-0000-4000-8000-000000000001',
            'machine_id':self.machine,'root_filesystem_uuid':'00000000-0000-4000-8000-000000000002'}
        self.witness={'version':1,'kind':'root-observed-canonical-child-host',**self.registration,'boot_id':self.boot}
        def run(args):
            if args==['/usr/bin/systemd-detect-virt']:return b'kvm\n'
            if args==['/usr/bin/findmnt','-n','-o','UUID','/']:return (self.registration['root_filesystem_uuid']+'\n').encode()
            raise AssertionError('unexpected host observation')
        self.run=self.enterContext(patch('deployment.lib.isolated_release_environment.run',side_effect=run))

    def test_unprivileged_verification_never_reads_root_only_dmi(self):
        read=Path.read_text
        def guarded(path,*a,**kw):
            if str(path).endswith('/dmi/id/product_uuid'):raise PermissionError('native root-only DMI')
            return read(path,*a,**kw)
        with patch.object(Path,'read_text',guarded),patch.object(os,'geteuid',return_value=1000):
            self.assertIsNone(release.verify_child_host_identity(self.registration,self.witness))
        self.assertEqual(self.run.call_count,2)

    def test_changed_projection_context_guest_machine_filesystem_or_boot_refuses(self):
        for key in ('context_sha256','guest_uuid','machine_id','root_filesystem_uuid','boot_id','kind','version'):
            changed=dict(self.witness,**{key:False if key=='version' else 'changed'})
            with self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'host_changed'):
                release.verify_child_host_identity(self.registration,changed)
        with self.assertRaisesRegex(RuntimeError,'host_changed'):
            release.verify_child_host_identity(self.registration,None)

    def test_actual_boot_and_machine_are_reobserved_not_taken_from_projection(self):
        read=Path.read_text
        for path in ('/etc/machine-id','/proc/sys/kernel/random/boot_id'):
            def changed(p,*a,**kw):return 'changed' if str(p)==path else read(p,*a,**kw)
            with self.subTest(path=path),patch.object(Path,'read_text',changed):
                with self.assertRaisesRegex(RuntimeError,'host_changed'):
                    release.verify_child_host_identity(self.registration,self.witness)
        for returned in (b'docker\n',b'wrong-filesystem\n'):
            with patch('deployment.lib.isolated_release_environment.run',return_value=returned):
                with self.assertRaisesRegex(RuntimeError,'host_changed'):
                    release.verify_child_host_identity(self.registration,self.witness)

    def test_root_projection_requires_full_existing_host_and_effect_fence_verifier(self):
        with patch.object(os,'geteuid',return_value=1000),patch.object(release,'isolated_registration') as observe:
            with self.assertRaisesRegex(RuntimeError,'root_required'):release.root_child_host_identity({})
            observe.assert_not_called()
        for error in ('schema160_isolated_registration_host_changed','isolation_tampered'):
            with patch.object(os,'geteuid',return_value=0),patch.object(release,'isolated_registration',side_effect=RuntimeError(error)):
                with self.assertRaisesRegex(RuntimeError,error):release.root_child_host_identity({})
        with patch.object(os,'geteuid',return_value=0),patch.object(release,'isolated_registration',return_value=self.registration) as observe:
            self.assertEqual(release.root_child_host_identity({'model':'contract'}),self.witness)
            observe.assert_called_once_with({'model':'contract'})

    def test_actual_issuer_binds_root_projection_in_existing_credential_and_interlock(self):
        contract=fixtures.HistoricalPreparationBindingTests().contract()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);admissions=root/'admissions';current=admissions/admission.digest(contract);current.mkdir(parents=True)
            (current/'admission.json').write_text(json.dumps({'operation':RECONCILED.operation,'contract':contract}))
            ops=upgrade.SystemOperations.__new__(upgrade.SystemOperations)
            ops.runtime_root=root/'runtime';ops.runtime_root.mkdir();ops.authorization_file=ops.runtime_root/'credential'
            ops.interlock_file=root/'interlock';ops.state_root=root/'state';ops.interlock_document=Mock(return_value={})
            history={'original_runtime':{'source_sha':contract['source_roles']['application_sha'],
                'images':contract['origin']['images'],'worker_generation':contract['origin']['worker_generation']}}
            with patch.object(admission,'ADMISSIONS',admissions),patch.object(admission,'validate_contract'),\
                 patch.object(admission,'verify_history'),patch.object(admission,'require_candidate_authority',return_value={'mode':'READ_ONLY'}),\
                 patch.object(admission,'measure_provider_record',return_value={'model':'existing provider metadata'}),\
                 patch('deployment.lib.completed_normal_profile.profile',return_value=RECONCILED),\
                 patch('deployment.lib.exceptional_release_approval.require_canonical_execution',return_value={'model':'already authenticated parent lease'}),\
                 patch('deployment.lib.historical_origin.history_witness',return_value=history),\
                 patch.object(release,'root_child_host_identity',return_value=self.witness) as observed,\
                 patch('deployment.lib.provider_recovery_runtime.protected',side_effect=lambda p,**kw:Path(p)),\
                 patch.object(upgrade,'require_root_directory'):
                ops.write_authorization(contract['candidate']['controller_sha'],completed_normal_contract=contract,completed_normal_mode='prepare')
            observed.assert_called_once_with(contract)
            credential=json.loads(ops.authorization_file.read_bytes());interlock=json.loads(ops.interlock_file.read_bytes())
            self.assertEqual(credential['canonical_host_identity'],self.witness)
            self.assertEqual(interlock['canonical_host_identity_sha256'],admission.digest(self.witness))
            self.assertNotIn('migration_database',credential)
            self.assertEqual(ops.authorization_file.stat().st_mode&0o777,0o600)
            self.assertEqual(ops.interlock_file.stat().st_mode&0o777,0o644)


if __name__=='__main__':unittest.main()
