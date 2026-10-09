"""Synthetic restore evidence validation inputs, never real recovery proof."""
import copy
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.checkpoint_execution_proof import verify_supervised_native_restore,sha256,SEALED_COMPONENTS

class NativeProofTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'checkpoint-20261008T224529Z';self.root.mkdir()
        self.evidence=self.root/'evidence';self.evidence.mkdir()
        self.images={name:{'image':'sha256:'+str(i+1)*64} for i,name in enumerate(('supabase-db','supabase-auth','supabase-rest','supabase-storage'))}
        inventory={};entries=[]
        for name,kind in SEALED_COMPONENTS.items():
            (self.root/name).write_text(json.dumps(self.images) if name=='images.json' else 'non-customer fixture')
            inventory[name]=sha256(self.root/name);entries.append({'path':name,'kind':kind,'sha256':inventory[name],'size':(self.root/name).stat().st_size})
        (self.root/'manifest.json').write_text(json.dumps({'version':1,'schema':115,'sealed':True,'migrations_executed':False,'created_at':'2026-10-08T22:49:30+00:00','files':entries}))
        manifest=sha256(self.root/'manifest.json');self.sources={}
        self.web=self.root/'frozen/web'
        for name in ('record_native_restore_execution.py','verify_restored_native_platform.py','restore_coordinated_checkpoint.py'):
            path=self.web/'scripts'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'synthetic runner bytes');path.chmod(0o500)
            self.sources['scripts/'+name]=sha256(path)
        self.record={'version':1,'operation':'supervised-private-native-core-restore','scope':'native-core','exit_code':0,
            'original_evidence_modified':False,'source_application_acceptance_claimed':False,'checkpoint_manifest_sha256':manifest,
            'started_at':'2026-10-09T02:10:17+00:00','finished_at':'2026-10-09T02:10:38+00:00',
            'argv':['/usr/bin/python3','-I','-B',str(self.web/'scripts/verify_restored_native_platform.py')]}
        self.replica={'node':'madar-node1-lan','exit_code':0,'successful_files':14,'files':{**inventory,'manifest.json':manifest},
            'object_id':'/srv/data2/madar-backups/normal-local-preparation/'+self.root.name}
        self.archives={name:{'files':1,'bytes':10} for name in inventory if name.endswith('.tar.gz')}
        self.result={'operation':'actual-offhost-private-native-core-restore','checkpoint_manifest_sha256':manifest,'restored_files':inventory,'schema':115,
            'database_network_during_restore':'none','runtime_network':'isolated-internal','production_modified':False,'original_checkpoint_modified':False,
            'application_migrations_executed':False,'business_consumers_started':False,'application_acceptance_proven':False,'tenant_isolation_proven':False,
            'full_eleven_service_platform_proven':False,'owners_and_acls_restored':True,'role_attributes_password_verifiers_and_grantors_verified':True,
            'mime_cache_verified':True,'native_login_and_aal2_verified':True,'synthetic_identity_removed':True,
            'database_integrity':{'database_owner':'postgres','invalid_indexes':'0','identities':'18','factors':'2'},'storage_objects':235,'range_checks':235,
            'runtimes':{name.replace('supabase','fixture'):{'id':str(i+1)*64,'image':row['image']} for i,(name,row) in enumerate(self.images.items())}}
    def save(self):
        data={'source_files':('source-files.json',json.dumps(self.sources)),'replica_check':('replica-check.json',json.dumps(self.replica)),
            'archive_verification':('archive-verification.json',json.dumps(self.archives)),
            'stdout':('stdout.jsonl',json.dumps(self.result)+'\n'),'stderr':('stderr.txt','')}
        for key,(name,content) in data.items():
            path=self.evidence/name;path.write_text(content);self.record[key+'_sha256']=sha256(path)
        path=self.evidence/'execution.json';path.write_text(json.dumps(self.record));return path
    def verify(self):
        path=self.save();return verify_supervised_native_restore(self.root,path,approved_execution_digest=sha256(path),
            protected_file=lambda path,**kw:path,now=datetime(2026,10,9,3,tzinfo=timezone.utc))
    def test_exact_fixture_preserves_scope(self):
        report=self.verify();self.assertEqual(report['coordinated_components_verified'],13)
        self.assertFalse(report['normal_application_acceptance']);self.assertFalse(report['full_eleven_service_platform_acceptance'])
    def test_summary_and_bad_exit_do_not_pass(self):
        self.record['exit_code']=True
        with self.assertRaisesRegex(RuntimeError,'scope_invalid'):self.verify()
    def test_changed_source_or_missing_archive_rejected(self):
        path=self.web/'scripts/restore_coordinated_checkpoint.py';path.chmod(0o700);path.write_bytes(b'changed');path.chmod(0o500)
        with self.assertRaisesRegex(RuntimeError,'source_changed'):self.verify()
    def test_wrong_replica_and_dataset_rejected(self):
        self.replica['successful_files']=13
        with self.assertRaisesRegex(RuntimeError,'replica_invalid'):self.verify()
        self.replica['successful_files']=14;self.result['storage_objects']=234
        with self.assertRaisesRegex(RuntimeError,'dataset_invalid'):self.verify()
    def test_incompatible_runtime_image_rejected(self):
        self.result['runtimes']['fixture-db']['image']='sha256:'+'e'*64
        with self.assertRaisesRegex(RuntimeError,'images_changed'):self.verify()
    def test_cannot_relabel_native_scope_as_normal_acceptance(self):
        self.result['application_acceptance_proven']=True
        with self.assertRaisesRegex(RuntimeError,'scope_invalid'):self.verify()
