"""Real files, no value disclosure or test-directory bypass."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

WEB=Path(os.environ.get('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
spec=importlib.util.spec_from_file_location('secret_hygiene',WEB/'scripts/check_secret_hygiene.py')
scanner=importlib.util.module_from_spec(spec);spec.loader.exec_module(scanner)


class SecretHygieneContentTests(unittest.TestCase):
    def test_credentials_in_documents_and_tests_fail_without_disclosing_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);token='ghp_'+'Z'*36
            for name in ('report.md','test_fixture.py'):
                (root/name).write_text('first line\n'+token+'\n')
                findings=scanner.inspect(root,[name])
                self.assertEqual(findings,[{'path':name,'line':2,'kind':'github_token'}])
                self.assertNotIn(token,json.dumps(findings))

    def test_real_key_header_is_refused_but_code_header_constant_is_not_a_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'key.txt';header='-----BEGIN '+'OPENSSH PRIVATE KEY-----'
            p.write_text(header+'\nsynthetic-material\n')
            self.assertEqual(scanner.inspect(root,[p.name])[0]['kind'],'private_key')
            p.write_text('HEADER = b"'+header+'"\n')
            self.assertEqual(scanner.inspect(root,[p.name]),[])

    def test_chunk_boundary_cannot_hide_token_and_symlinks_are_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'boundary.txt';token='github_pat_'+'Z'*50
            p.write_text('x'*65530+'\n'+token+'\n')
            self.assertEqual(scanner.inspect(root,[p.name]),[{'path':p.name,'line':2,'kind':'github_token'}])
            (root/'link.txt').symlink_to(p)
            self.assertEqual(scanner.inspect(root,['link.txt']),[])
            (root/'.env').write_text('SYNTHETIC=placeholder')
            self.assertEqual(scanner.inspect(root,['.env'])[0]['kind'],'forbidden_environment_file')
