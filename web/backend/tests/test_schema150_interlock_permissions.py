"""Real file bytes/modes; root ownership and temporary ancestry are modeled."""
import json
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch, Mock
from deployment.lib import schema150_provider_adapter as adapter


class InterlockPermissionTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.interlock=self.root/'in-progress.json';self.private=self.root/'provider-inventory.json'
        self.value={'status':'authorized_cycle','rehearsal_sha256':'a'*64}
        for path in (self.interlock,self.private):path.write_text(json.dumps(self.value));path.chmod(0o600)
        self.enterContext(patch.object(adapter,'UPGRADE_INTERLOCK',self.interlock))
        original=Path.stat;self.bad_owner=None
        def root_metadata(path,*args,**kwargs):
            result=original(path,*args,**kwargs)
            if path.is_relative_to(self.root) or path in self.root.parents:
                values=list(result);values[4]=12345 if path==self.bad_owner else 0
                # Temporary test ancestry is not an operational root path.
                # Leaf modes/types remain the actual filesystem observation.
                if path in self.root.parents:values[0]=stat.S_IFMT(result.st_mode)|0o755
                return os.stat_result(values)
            return result
        self.enterContext(patch.object(Path,'stat',root_metadata))

    def test_exact_public_root_interlock_accepts_issuer_mode_without_credential_material(self):
        self.interlock.chmod(0o644)
        self.assertEqual(adapter.private_json(self.interlock),self.value)
        self.assertNotIn('token',adapter.private_json(self.interlock))

    def test_all_other_inputs_remain_private_even_with_interlock_basename(self):
        for path in (self.private,self.root/'other'/'in-progress.json'):
            path.parent.mkdir(exist_ok=True);path.write_text('{}');path.chmod(0o644)
            with self.subTest(path=path),self.assertRaisesRegex(RuntimeError,'file_not_private'):
                adapter.private_json(path)
            path.chmod(0o600);self.assertEqual(adapter.private_json(path),{})

    def test_wrong_owner_or_writable_public_interlock_refuses(self):
        self.interlock.chmod(0o644);self.bad_owner=self.interlock
        with self.assertRaisesRegex(RuntimeError,'untrusted'):adapter.private_json(self.interlock)
        self.bad_owner=None
        for mode in (0o664,0o646,0o666):
            self.interlock.chmod(mode)
            with self.subTest(mode=mode),self.assertRaisesRegex(RuntimeError,'untrusted'):
                adapter.private_json(self.interlock)

    def test_symlink_and_oversized_public_interlock_refuse(self):
        self.interlock.unlink();self.interlock.symlink_to(self.private)
        with self.assertRaisesRegex(RuntimeError,'untrusted'):adapter.private_json(self.interlock)
        self.interlock.unlink();self.interlock.write_bytes(b'x'*(2*1024**2+1));self.interlock.chmod(0o644)
        with self.assertRaisesRegex(RuntimeError,'private_input_limit'):adapter.private_json(self.interlock)

    def test_public_interlock_cannot_replace_missing_or_forged_private_credential(self):
        from deployment.lib import control_plane_upgrade_authorization as authorization
        from test_completed_normal_model import reconciled_contract
        actor=adapter.Schema150ProviderAdapter.__new__(adapter.Schema150ProviderAdapter)
        actor.contract=reconciled_contract()
        actor.binding={'controller_sha':actor.contract['candidate']['controller_sha'],'context_sha256':'a'*64}
        actor.source_guard=Mock();actor._database_identity=Mock()
        self.interlock.write_text(json.dumps({'status':'authorized_cycle','approved_sha':actor.binding['controller_sha'],
            'operation':actor.contract['operation'],'schema':146,'context_sha256':'a'*64,
            'rehearsal_sha256':actor.contract['rehearsal_sha256'],
            'authorization_sha256':hashlib.sha256(b'correct-synthetic-token').hexdigest()}));self.interlock.chmod(0o644)
        credentials=self.root/'credentials';credentials.mkdir()
        def verify(sha,**kwargs):
            return authorization.require_upgrade_authorization(sha,interlock=self.interlock,**kwargs)
        with patch.object(adapter.os,'geteuid',return_value=0),patch.object(adapter,'require_upgrade_authorization',verify),\
                patch.dict(os.environ,{'CREDENTIALS_DIRECTORY':str(credentials)}),\
                patch.object(adapter,'private_json') as read:
            for kind in ('missing','forged'):
                if kind=='forged':
                    path=credentials/'madar-control-plane-upgrade'
                    path.write_text(json.dumps({'approved_sha':actor.binding['controller_sha'],'token':'wrong-synthetic-token'}));path.chmod(0o600)
                with self.subTest(kind=kind),self.assertRaisesRegex(RuntimeError,'exclusive_interlock'):
                    actor.require_authority(actor.binding,purpose='prepare')
            read.assert_not_called();actor._database_identity.assert_not_called()


if __name__=='__main__':unittest.main()
