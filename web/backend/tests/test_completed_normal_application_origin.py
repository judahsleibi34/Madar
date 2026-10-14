"""No-SQL origin admission keeps all ancestor SQL provenance immutable."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_completed_normal_application_release import application_contract
from deployment.lib import completed_normal_admission as m
from deployment.lib.completed_normal_profile import APPLICATION,MANUAL
from deployment.lib.provider_recovery_runtime import file_digest

class ApplicationOriginHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.admissions=Path(self.tmp.name)/'admissions';self.admissions.mkdir()
        p=patch.object(m,'ADMISSIONS',self.admissions);p.start();self.addCleanup(p.stop)
        p=patch('deployment.lib.provider_recovery_runtime.protected',lambda path,**kw:Path(path));p.start();self.addCleanup(p.stop)
        ancestor=self.admissions/('a'*64);ancestor.mkdir()
        previous=application_contract();previous['source_roles']['completion_root']=str(ancestor)
        for name in m.COMPATIBLE_HISTORICAL_NAMES:(ancestor/name).write_bytes(m.encoded({'fixture':name}))
        previous['historical_files']={str(ancestor/name):file_digest(ancestor/name) for name in m.COMPATIBLE_HISTORICAL_NAMES}
        self.previous=previous;self.ancestor=ancestor
        self.root=self.admissions/m.digest(previous);self.root.mkdir()
        self.completion={'operation':APPLICATION.operation,'context_sha256':self.root.name,'mode':'NORMAL','schema':previous['database']['schema'],
          'application_sha':previous['candidate']['source_sha'],'controller_sha':previous['candidate']['controller_sha'],
          'images':previous['candidate']['images'],'customer_database_restored':False,'sql_executed':False}
        for name in m.APPLICATION_HISTORICAL_NAMES:(self.root/name).write_bytes(m.encoded({'fixture':name}))
        (self.root/'admission.json').write_bytes(m.encoded({'operation':APPLICATION.operation,'contract':previous}))
        self.contract=application_contract()
        self.contract['source_roles'].update(completion_root=str(self.root),application_sha=previous['candidate']['source_sha'],controller_sha=previous['candidate']['controller_sha'])
        self.contract['origin']['images']=previous['candidate']['images']
        self.update_completion()
    def update_completion(self):
        (self.root/'normal-completion.json').write_bytes(m.encoded(self.completion))
        self.contract['source_roles']['completion_sha256']=file_digest(self.root/'normal-completion.json')
        self.contract['historical_files']={str(self.root/name):file_digest(self.root/name) for name in m.APPLICATION_HISTORICAL_NAMES}
    def test_completed_application_origin_accepts_without_fake_sql(self):
        m.validate_contract(self.contract);m.verify_history(self.contract)
        self.assertFalse((self.root/'migration-intent.json').exists())
    def test_migration_origins_cannot_omit_sql_evidence(self):
        c=copy.deepcopy(self.contract);c.update(operation=MANUAL.operation,version=MANUAL.version)
        c['source_roles']['schema']=MANUAL.source;c['database']['schema']=MANUAL.source
        with self.assertRaisesRegex(RuntimeError,'history_invalid'):m.validate_contract(c)
    def test_ancestor_sql_changes_remain_rejected(self):
        (self.ancestor/'migration-intent.json').write_bytes(b'altered')
        with self.assertRaisesRegex(RuntimeError,'historical_evidence_changed'):m.verify_history(self.contract)
    def test_application_completion_cannot_be_readonly_restored_or_sql(self):
        original=copy.deepcopy(self.completion)
        for changes in ({'mode':'READ_ONLY'},{'sql_executed':True},{'sql_executed':None},
                        {'customer_database_restored':True},{'application_sha':'e'*40},{'controller_sha':'f'*40},{'schema':145}):
            self.completion=dict(original,**changes);self.update_completion()
            with self.subTest(changes=changes),self.assertRaisesRegex(RuntimeError,'application_origin_history_invalid'):m.verify_history(self.contract)
    def test_wrong_profile_admission_rejected(self):
        (self.root/'admission.json').write_bytes(m.encoded({'operation':MANUAL.operation,'contract':self.previous}))
        self.update_completion()
        with self.assertRaisesRegex(RuntimeError,'application_origin_history_invalid'):m.verify_history(self.contract)
    def test_changed_origin_image_rejected(self):
        self.contract['origin']['images']=dict(self.contract['origin']['images'],backend='sha256:'+'f'*64)
        with self.assertRaisesRegex(RuntimeError,'application_origin_history_invalid'):m.verify_history(self.contract)
    def test_cycle_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'application_history_cycle'):m.verify_history(self.contract,_visited={self.root})
    def test_partial_receipt_set_rejected(self):
        self.contract['historical_files'].pop(str(self.root/'boot-installation.json'))
        with self.assertRaisesRegex(RuntimeError,'history_invalid'):m.validate_contract(self.contract)
