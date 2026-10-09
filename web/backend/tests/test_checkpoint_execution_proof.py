"""Fixture packets are validator unit inputs, never production restore evidence."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

WEB_ROOT = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB_ROOT))
from deployment.lib.checkpoint_execution_proof import verify_checkpoint_execution, sha256, SEALED_COMPONENTS


class CheckpointExecutionProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inventory={}
        files=[]
        for name,kind in SEALED_COMPONENTS.items():
            (self.root/name).write_bytes(b'non-customer unit fixture')
            self.inventory[name]=sha256(self.root/name)
            files.append({'path':name,'kind':kind,'size':(self.root/name).stat().st_size,'sha256':self.inventory[name]})
        manifest={'version':1,'sealed':True,'schema':115,'migrations_executed':False,
            'created_at':'2026-10-08T11:00:00+00:00','files':files,'restore_verified':False}
        (self.root / 'manifest.json').write_text(json.dumps(manifest))
        (self.root / 'transcript.txt').write_text('unit fixture execution only\n')
        (self.root/'runner.py').write_text('# unit-only non-executable fixture\n')
        self.record = {'version': 1, 'operation': 'coordinated-checkpoint-restore',
            'checkpoint_manifest_sha256': sha256(self.root / 'manifest.json'),
            'schema': 115, 'migrations_executed': False, 'production_modified': False,
            'workers_started': False, 'scope': 'complete-coordinated-checkpoint',
            'restored_files': self.inventory,
            'execution': {'started_at': '2026-10-08T11:01:00+00:00',
                'finished_at': '2026-10-08T11:02:00+00:00', 'exit_code': 0,
                'argv': ['unit-fixture-runner'], 'network': 'none', 'customer_endpoints_used': False,
                'runner_path': 'runner.py', 'runner_sha256': sha256(self.root/'runner.py'), 'image_id': 'sha256:'+'b'*64,
                'transcript_path': 'transcript.txt', 'transcript_sha256': sha256(self.root/'transcript.txt')},
            'offhost': {'checkpoint_manifest_sha256': sha256(self.root/'manifest.json'),
                'restored_files': self.inventory, 'independent_restore_exit_code': 0,
                'independent_restore_verified': True, 'source_host_id': 'fixture-a',
                'backup_host_id': 'fixture-b', 'object_id': 'fixture',
                'protection': 'online-ssh-unencrypted', 'object_sha256': 'c'*64}}
        receipt=self.root/'offhost.json'
        receipt.write_text(json.dumps(self.record['offhost']))
        self.record['offhost'].update({'execution_receipt_path':'offhost.json',
                                     'execution_receipt_sha256':sha256(receipt)})

    def verify(self, record=None, approved=None):
        proof = self.root / 'proof.json'
        proof.write_text(json.dumps(record or self.record))
        return verify_checkpoint_execution(self.root, proof,
            approved_execution_digest=approved or sha256(proof),
            protected_file=lambda path, **_: path, now=datetime(2026,10,9,tzinfo=timezone.utc))

    def test_complete_exact_fixture_packet(self):
        self.assertEqual(self.verify()['files'], 13)

    def test_old_pass_summary_and_flag_are_insufficient(self):
        with self.assertRaises(RuntimeError):
            self.verify({'restore_verified': True, 'checks': {'restore': 'PASS'}})
        with self.assertRaises(RuntimeError):
            self.verify(approved='e'*64)

    def test_supplemented_manifest_needs_new_restore(self):
        p=self.root/'manifest.json';record=json.loads(p.read_text())
        record['files'].append({'path':'supplement.json','size':2,'sha256':hashlib.sha256(b'{}').hexdigest()})
        (self.root/'supplement.json').write_bytes(b'{}');p.write_text(json.dumps(record))
        with self.assertRaisesRegex(RuntimeError,'complete_manifest_required'):
            self.verify()

    def test_changed_component_or_transcript_is_rejected(self):
        (self.root/'database.dump').write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'inventory_changed'):
            self.verify()
        (self.root/'database.dump').write_bytes(b'non-customer unit fixture')
        (self.root/'transcript.txt').write_text('changed')
        with self.assertRaisesRegex(RuntimeError,'transcript_changed'):
            self.verify()

    def test_execution_scope_failure_and_unverified_offhost(self):
        cases=[('scope','database-only'),('schema',116),('production_modified',True),
            ('execution.exit_code',1),('execution.customer_endpoints_used',True),
            ('execution.network','host'),('execution.finished_at','2026-10-08T10:59:00+00:00'),
            ('offhost.backup_host_id','fixture-a'),('offhost.independent_restore_verified',False),
            ('offhost.independent_restore_exit_code',False),('offhost.restored_files',{}),
            ('restored_files',{}),('execution.transcript_path','../outside')]
        for key,value in cases:
            record=copy.deepcopy(self.record);target=record
            parts=key.split('.')
            for part in parts[:-1]:target=target[part]
            target[parts[-1]]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):self.verify(record)

    def test_dump_only_manifest_is_not_complete_coordinated_scope(self):
        manifest=json.loads((self.root/'manifest.json').read_text());manifest['files']=manifest['files'][:1]
        (self.root/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(RuntimeError,'complete_manifest_required'):self.verify()

    def test_wrong_component_kind_or_mutable_manifest_rejected(self):
        for variant in ('kind','sealed','version','migrations'):
            path=self.root/'manifest.json';original=path.read_text();manifest=json.loads(original)
            if variant=='kind':manifest['files'][0]['kind']='controller'
            elif variant=='sealed':manifest['sealed']=False
            elif variant=='version':manifest['version']=True
            else:manifest['migrations_executed']=True
            path.write_text(json.dumps(manifest))
            with self.subTest(variant=variant),self.assertRaisesRegex(RuntimeError,'complete_manifest_required'):self.verify()
            path.write_text(original)
