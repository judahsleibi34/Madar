"""Authenticated SQL proof/backup refusal models; native acceptance is separate."""
import copy,hashlib,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from deployment.lib import automatic_release_migration as migration
from deployment.lib.migration_inventory import digest

class MigrationProofTests(unittest.TestCase):
    def setUp(self):
        self.plan={'origin_schema':900160,'target_schema':900161,'migrations':[{'to_schema':900161,'sha256':'a'*64}],
            'compatibility_intent':{'worker_protocols':{'delivery':2,'outbox':2,'deletion':2}}}
        self.value={'plan':self.plan,'source_sha':'b'*40}
        self.record={'plan_sha256':digest(self.plan),'origin_schema':900160,'target_schema':900161,
            'native_exit_codes':[0], 'boundaries':[{'schema':900161,'sql_sha256':'a'*64,'semantic_sha256':'c'*64,'protocols':{'delivery':2,'outbox':2,'deletion':2}}],
            'backup_files':{n:{'sha256':hashlib.sha256(n.encode()).hexdigest(),'bytes':len(n)} for n in ('database.dump','roles.sql','objects.tar')}}
        self.proof={'migration':self.record,'gates':{'recovery':{'backup_sha256':self.record['backup_files']['database.dump']['sha256'],'objects_sha256':self.record['backup_files']['objects.tar']['sha256']}}}
    def test_exact_native_boundaries_and_original_bytes_are_required(self):
        self.assertIs(migration.proof_scope(self.value,self.proof),self.record)
        for mutate in (lambda r:r.update(plan_sha256='f'*64),lambda r:r.update(native_exit_codes=[1]),
            lambda r:r['boundaries'][0].update(sql_sha256='f'*64),lambda r:r['boundaries'][0]['protocols'].update(deletion=0),
            lambda r:r['backup_files']['database.dump'].update(sha256='f'*64)):
            proof=copy.deepcopy(self.proof);mutate(proof['migration'])
            with self.subTest(mutate=mutate),self.assertRaises(RuntimeError):migration.proof_scope(self.value,proof)
    def test_corrupt_or_truncated_backup_cannot_pass_the_signed_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);backup=root/self.value['source_sha'];backup.mkdir()
            for name in self.record['backup_files']:(backup/name).write_bytes(name.encode())
            with patch.object(migration,'BACKUPS',root),patch.object(migration,'protected',side_effect=lambda p,**kw:p):
                self.assertEqual(migration.verify_backup(self.value,self.proof,self.record),backup)
                (backup/'roles.sql').write_bytes(b'X'*len('roles.sql'))
                with self.assertRaisesRegex(RuntimeError,'backup_corrupt'):migration.verify_backup(self.value,self.proof,self.record)
                (backup/'roles.sql').write_bytes(b'')
                with self.assertRaisesRegex(RuntimeError,'backup_size_changed'):migration.verify_backup(self.value,self.proof,self.record)
    def test_expired_independent_policy_refuses_before_evidence_or_execution(self):
        with patch('deployment.lib.migration_policy.load_policy',return_value={'enabled':True,'expires_at':0}),\
                patch.object(migration.admission,'execution_policy',return_value=({},{})),\
                patch.object(migration.admission,'independent_evidence') as evidence:
            with self.assertRaisesRegex(RuntimeError,'policy_disabled_or_expired'):migration.prepared(self.value,None)
            evidence.assert_not_called()
