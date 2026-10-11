"""Actual durable boot gate; private files never become production evidence."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB))
from deployment.lib import completed_normal_database as m
from deployment.lib.completed_normal_admission import digest,encoded
from test_completed_normal_admission import fixture_contract

class MigrationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.contract=fixture_contract()
        self.manifest=WEB/'deployment/releases/migrations-116-136.json'
        self.contract['migration_manifest_sha256']=hashlib.sha256(self.manifest.read_bytes()).hexdigest()
        self.intent={'operation':self.contract['operation'],'context_sha256':digest(self.contract),
            'source_sha':self.contract['candidate']['source_sha'],'manifest_sha256':self.contract['migration_manifest_sha256'],
            'source_schema':115,'target_schema':136,'database_restored':False}
        p=patch('deployment.lib.provider_recovery_runtime.protected',lambda path,**kw:Path(path))
        p.start();self.addCleanup(p.stop)
    def check(self,schema):m.require_normal_migration_boundary(self.contract,schema,self.root,self.root/'operator-state')
    def start(self):
        (self.root/'migration-intent.json').write_bytes(encoded(self.intent))
    def complete(self):
        self.start();(self.root/'migration-manifest.json').write_bytes(self.manifest.read_bytes())
        self.execution={'release_sha':self.contract['candidate']['source_sha'],'status':'completed','phase':'complete',
            'observed_schema':136,'backup':{'verified':True},'migrations':[
                {'number':r['number'],'checksum':r['sha256'],'status':'applied'}
                for r in json.loads(self.manifest.read_text())['migrations']]}
        self.seal()
    def seal(self):
        body=encoded(self.execution);(self.root/'migration-execution.json').write_bytes(body)
        (self.root/'migration-completion.json').write_bytes(encoded(dict(self.intent,
            execution_sha256=hashlib.sha256(body).hexdigest(),observed_schema=136)))
    def test_pre_sql_boot_only_accepts_schema115(self):
        self.check(115)
        for schema in (116,120,136):
            with self.assertRaisesRegex(RuntimeError,'unattested_schema_advancement'):self.check(schema)
    def test_intent_before_first_transaction_blocks_old_positive_grant(self):
        self.start()
        for schema in (115,116,119,136):
            with self.assertRaisesRegex(RuntimeError,'forward_repair_required'):self.check(schema)
    def test_exact_completed_chain_allows_normal_at136_only(self):
        self.complete();self.check(136)
        for schema in (115,119,135):
            with self.assertRaisesRegex(RuntimeError,'completion_changed'):self.check(schema)
    def test_execution_and_manifest_changes_fail_closed(self):
        self.complete();p=self.root/'migration-execution.json';body=p.read_bytes();p.write_bytes(body+b' ')
        with self.assertRaisesRegex(RuntimeError,'completion_changed'):self.check(136)
        p.write_bytes(body);(self.root/'migration-manifest.json').write_bytes(b'{}')
        with self.assertRaisesRegex(RuntimeError,'manifest_changed'):self.check(136)
    def test_completed_marker_cannot_mask_missing_failed_or_reordered_sql(self):
        self.complete();original=copy.deepcopy(self.execution)
        for mutation in (lambda e:e.update(status='failed'),lambda e:e['migrations'].pop(),
                lambda e:e['migrations'].reverse(),lambda e:e['migrations'][0].update(status='applying'),
                lambda e:e['backup'].update(verified=False),lambda e:e.update(release_sha='e'*40)):
            self.execution=copy.deepcopy(original);mutation(self.execution);self.seal()
            with self.assertRaisesRegex(RuntimeError,'execution_invalid'):self.check(136)
    def test_resume_history_already_applied_is_verified_by_checksum(self):
        self.complete()
        for r in self.execution['migrations'][:4]:r['status']='already_applied'
        self.seal();self.check(136)
    def test_native_pending_is_bounded_availability_not_identity_exception(self):
        class Runtime:
            def inspect(_,names):return {'supabase-db':row}
            def command(_,args):return json.dumps([{'Id':db['network_id']}])
        db=self.contract['database'];row={'Id':db['container_id'],'Name':'/supabase-db','Image':db['image'],
            'State':{'Running':False,'Status':'exited'},'Config':{},'HostConfig':{},'Mounts':[],
            'NetworkSettings':{'Networks':{db['network_name']:{'NetworkID':db['network_id']}}}}
        from deployment.lib.emergency_routing_repair import spec
        self.contract['database']['spec_sha256']=spec(row)
        from deployment.lib.emergency_routing_repair import AvailabilityFailure
        with self.assertRaises(AvailabilityFailure):m.observe_native(self.contract,Runtime(),allow_pending=True)
        row['Image']='sha256:'+'0'*64
        with self.assertRaisesRegex(RuntimeError,'identity_changed'):m.observe_native(self.contract,Runtime(),allow_pending=True)

if __name__=='__main__':unittest.main()
