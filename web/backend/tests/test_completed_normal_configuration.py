"""Critical input bytes remain bound across every privileged boot phase."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_completed_normal_admission import fixture_contract
from deployment.lib import completed_normal_boot_actor as m

class ConfigurationTests(unittest.TestCase):
    def test_exact_inputs_and_nonsecret_mode_are_explicit(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);inputs={};hashes={};calls=[]
            for key,(_,private) in m.CONFIGURATIONS.items():
                p=root/key;p.write_text('fixture-only-input-'+key)
                inputs[key]=(p,private);hashes[key]=hashlib.sha256(p.read_bytes()).hexdigest()
            def read(path,*,private):calls.append((path.name,private));return path
            with patch.object(m,'CONFIGURATIONS',inputs),patch.object(m,'readonly_configuration',side_effect=read):
                m.verify_live_configuration({'live_configuration_sha256':hashes})
                self.assertIn(('gateway_bootstrap',False),calls)
                self.assertIn(('production_configuration',True),calls)
                self.assertIn(('backup_configuration',True),calls)
                self.assertIn(('node1_configuration',True),calls)
                inputs['production_configuration'][0].write_text('changed-private-value')
                with self.assertRaisesRegex(RuntimeError,'configuration_changed') as failure:
                    m.verify_live_configuration({'live_configuration_sha256':hashes})
                self.assertNotIn('changed-private-value',str(failure.exception))
    def test_missing_extra_or_invalid_binding_rejects_before_file_access(self):
        hashes={key:'1'*64 for key in m.CONFIGURATIONS}
        for value in ({},dict(hashes,unexpected='2'*64),dict(hashes,backup_configuration='not-a-hash')):
            with patch.object(m,'readonly_configuration') as read:
                with self.assertRaisesRegex(RuntimeError,'contract_invalid'):
                    m.verify_live_configuration({'live_configuration_sha256':value})
                read.assert_not_called()

if __name__=='__main__':unittest.main()
