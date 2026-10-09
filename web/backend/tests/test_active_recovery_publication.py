"""Guarded publication fixtures, with only temporary files and fake runtime."""
from dataclasses import dataclass,asdict
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_publication import ActiveRecoveryNormalPublication

@dataclass
class Contract:
    sha:str
    images:dict

class NormalPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);base=Path(self.temp.name)
        self.paths={key:base/(key+'.json') for key in ('production_configuration','backup_configuration','release_state','traffic','native_configuration')}
        for path in self.paths.values():
            path.write_text('{}');path.chmod(0o600)
        self.paths['native_configuration'].write_text('POSTGRES_PASSWORD=synthetic-fixture-placeholder\nPOOLER_TENANT_ID=fixture\n')
        self.paths['production_configuration'].write_text('PRESERVED=original-fixture\n')
        self.paths['release_state'].write_text('{"historical_context":"unchanged"}')
        self.plan=SimpleNamespace(digest='a'*64,source_sha='b'*40,source_bundle_sha256='c'*64,
            retained_inputs={key:hashlib.sha256(path.read_bytes()).hexdigest() for key,path in self.paths.items()})
        self.root=base/self.plan.digest;self.root.mkdir();self.state=base/'state';self.state.mkdir()
        self.auth={'operation':'active-local-rollback-resumption','plan_sha256':self.plan.digest,'source_bundle_sha256':self.plan.source_bundle_sha256}
        (self.root/'authorization.json').write_text(json.dumps(self.auth))
        self.phase='write_grant_pending';self.save_phase()
        self.c=SimpleNamespace(config={'SUPABASE_URL':'http://madar-supabase:8000','FIXTURE_VALUE':'literal value'},slot='green',state=self.state,
            contract=Contract(self.plan.source_sha,{'backend':'sha256:'+'d'*64,'frontend':'sha256:'+'e'*64}),require_write_authority=lambda *args:None)
        self.calls=[];runtime=SimpleNamespace(read_only=lambda **kw:self.calls.append('read_only'))
        self.pub=ActiveRecoveryNormalPublication(self.plan,self.c,self.root,lambda:None,runtime)
        for module in ('active_recovery_publication','provider_local_backup_configuration'):
            for name,value in [('protected',lambda path,**kw:path),('readonly_configuration',lambda path,**kw:path)]:
                q=patch('deployment.lib.'+module+'.'+name,value);q.start();self.addCleanup(q.stop)
        for name,value in [('ROOT',base),('INPUTS',self.paths)]:
            q=patch('deployment.lib.active_recovery_publication.'+name,value);q.start();self.addCleanup(q.stop)
        q=patch('deployment.lib.provider_local_backup_configuration.BACKUP_ENV',self.paths['backup_configuration']);q.start();self.addCleanup(q.stop)
        q=patch('deployment.lib.active_recovery_publication.os.geteuid',return_value=0);q.start();self.addCleanup(q.stop)
        q=patch('deployment.lib.active_recovery_publication.pwd.getpwnam',return_value=SimpleNamespace(pw_uid=os.getuid(),pw_gid=os.getgid()));q.start();self.addCleanup(q.stop)
    def save_phase(self):
        (self.root/'events.jsonl').write_text(json.dumps({'phase':self.phase,'plan_sha256':self.plan.digest,'normal_writes_may_have_occurred':True})+'\n')
    def test_exact_preimages_and_historical_context_are_preserved(self):
        old={key:self.paths[key].read_bytes() for key in ('production_configuration','release_state','traffic')}
        self.pub.publish()
        for key,body in old.items():self.assertEqual((self.root/('pre-normal-'+key)).read_bytes(),body)
        state=json.loads(self.paths['release_state'].read_text());self.assertEqual(state['historical_context'],'unchanged')
        self.assertEqual(state['known_good_release']['schema'],115);self.assertEqual(state['known_good_release']['migration_policy'],'none')
        receipt=json.loads((self.root/'normal-publication.json').read_text());self.assertFalse(receipt['business_write_authority_published'])
        self.assertFalse(receipt['database_restore'])
    def test_changed_input_blocks_any_archive_or_publication(self):
        self.paths['production_configuration'].write_text('changed')
        with self.assertRaisesRegex(RuntimeError,'input_changed'):self.pub.publish()
        self.assertFalse((self.root/'normal-publication-begin.json').exists())
    def test_wrong_phase_and_multiline_configuration_fail_closed(self):
        self.phase='standby_ready';self.save_phase()
        with self.assertRaisesRegex(RuntimeError,'phase_denied'):self.pub.publish()
        self.phase='write_grant_pending';self.save_phase();self.c.config['FIXTURE_VALUE']='line1\nline2'
        with self.assertRaisesRegex(RuntimeError,'environment_invalid'):self.pub.publish()
        self.assertFalse((self.root/'normal-publication-begin.json').exists())
    def test_existing_preimage_is_never_silently_replaced(self):
        path=self.root/'pre-normal-production_configuration';path.write_bytes(b'prior')
        with self.assertRaises(FileExistsError):self.pub.publish()
        self.assertEqual(path.read_bytes(),b'prior')
    def test_shell_value_is_quoted_without_execution(self):
        self.c.config['FIXTURE_VALUE']='$(literal) `literal`'
        self.pub.publish();self.assertIn("FIXTURE_VALUE='$(literal) `literal`'",self.paths['production_configuration'].read_text())
