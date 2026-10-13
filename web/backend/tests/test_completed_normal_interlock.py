"""Exact failed-attempt reconciliation; private files, no production effects."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_completed_normal_manual_profile import manual_contract
from deployment.lib import completed_normal_execution as m
from deployment.lib import completed_normal_admission as admission


class FailedBootInterlockTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.admissions=self.base/'admissions';self.admissions.mkdir()
        self.sources=self.base/'sources';self.sources.mkdir();self.units=self.base/'units';self.units.mkdir()
        self.proc=self.base/'proc';self.proc.mkdir();self.runtime=self.base/'runtime';self.runtime.mkdir()
        self.upgrades=self.base/'upgrades';self.upgrades.mkdir()
        for p in (patch.object(m,'ADMISSIONS',self.admissions),patch.object(admission,'ADMISSIONS',self.admissions),
                patch.object(m,'SOURCE_PACKAGES',self.sources),patch.object(m,'BOOT_UNITS',self.units),
                patch.object(m,'PROC_ROOT',self.proc),patch.object(m,'protected',lambda p,**kw:Path(p)),
                patch.object(m,'require_root_directory',self.directory)):
            p.start();self.addCleanup(p.stop)
        self.contract=manual_contract();self.old=copy.deepcopy(self.contract)
        self.old['candidate']['controller_sha']='e'*40
        self.context=admission.digest(self.old);self.old_root=self.admissions/self.context;self.old_root.mkdir()
        original=self.units/'old-proxy.conf';original.write_bytes(b'original gate\n');original.chmod(0o644)
        generated=self.units/'failed-new.service';generated_body=b'rolled back\n'
        retained=self.old_root/'retained-failed-new.service';retained.write_bytes(generated_body)
        self.boot={'files':{str(original):{'sha256':m.file_digest(original),'uid':original.stat().st_uid,'mode':0o644}},
            'unit_states':{'old.service':{'active':'active','enabled':'enabled'}}}
        self.timers={'native':{'active':'active','enabled':'enabled'}}
        self.document={'operation':m.MANUAL.operation,'source_bundle_sha256':'f'*64,
            'boot_resources':self.boot,'backup_timer_states':self.timers}
        auth={'operation':m.MANUAL.operation,'context_sha256':self.context,'controller_sha':'e'*40,
            'plan_sha256':self.old['plan_sha256'],'source_bundle_sha256':'b'*64,
            'application_sha':self.old['candidate']['source_sha']}
        receipt={'operation':m.MANUAL.operation,'contract':self.old}
        resources={str(generated):hashlib.sha256(generated_body).hexdigest()}
        self.records={'operator-authorization.json':auth,'admission.json':receipt,
            'failure.json':{'operation':m.MANUAL.operation,'context_sha256':self.context,
                'phase':'boot_supersession_pending','exception_type':'RuntimeError','customer_database_restored':False,
                'frames':[{'source':'completed_normal_boot_installation.py','function':'installed'}]},
            'boot-preimages.json':self.boot,'boot-installation.json':{'historical_units_deleted':False,'resources':resources},
            'boot-installation-failed.json':{'operation':m.MANUAL.operation,'context_sha256':self.context,
                'phase':'boot_resource_installation','database_restored':False,'retained_generated_resources':resources},
            'backup-timer-preimages.json':self.timers,'events.jsonl':{'phase':'admitted'},
            'boot-events.jsonl':{'phase':'boot_supersession_pending'}}
        for name,value in self.records.items():(self.old_root/name).write_bytes(admission.encoded(value))
        self.interlock={'version':2,'status':'authorized_cycle','operation':m.MANUAL.operation,'schema':136,
            'approved_sha':'e'*40,'context_sha256':self.context,'admission_sha256':admission.digest(receipt),
            'backup_timer_states':self.timers}
        path=self.runtime/'in-progress.json';path.write_bytes(admission.encoded(self.interlock))
        wrapper_body=b'private fixture wrapper';wh=hashlib.sha256(wrapper_body).hexdigest()
        (self.sources/('normal-invocation-'+wh+'.py')).write_bytes(wrapper_body)
        self.binding={'interlock_sha256':m.file_digest(path),'context_sha256':self.context,'controller_sha':'e'*40,
            'plan_sha256':self.old['plan_sha256'],'source_bundle_sha256':'b'*64,'invocation_wrapper_sha256':wh,
            'records':{n:m.file_digest(self.old_root/n) for n in m.FAILED_BOOT_RECORDS}}
        self.document['failed_boot_interlock']=self.binding
        self.commands=[];self.stops=[];self.active=''
        self.ops=SimpleNamespace(interlock_file=path,authorization_file=self.runtime/'authorization.json',
            upgrade_root=self.upgrades,deploy_lock_descriptor=2,
            command=self.command,systemctl_state=lambda n:dict(self.boot['unit_states'][n]),
            clear_interlock=lambda:(self.stops.append('clear_interlock'),path.unlink()))
        self.actor=SimpleNamespace(contract=self.contract,document=self.document,ops=self.ops,
            root=self.admissions/'new',package=self.sources/'new')
        self.driver=m.CompletedNormalUpgrade(self.actor,artifact_guard=lambda:None,model_loader=lambda:{},
            acceptance_guard=lambda **kw:None,rehearsal_guard=lambda:None)
        self.driver.preparation_source=lambda:None;self.driver.lock=1

    @staticmethod
    def directory(path,*,create=False,**kw):
        if create:path.mkdir(mode=0o700,exist_ok=True)
        if not path.is_dir():raise RuntimeError('fixture_directory_missing')

    def command(self,label,args):
        self.commands.append((label,args));return SimpleNamespace(stdout=self.active)

    def verify(self):return m.verify_failed_boot_interlock(self.document,self.contract,self.ops)

    def revise_record(self,name):
        (self.old_root/name).write_bytes(admission.encoded(self.records[name]))
        self.binding['records'][name]=m.file_digest(self.old_root/name)

    def test_read_only_verification_preserves_interlock_and_all_records(self):
        before={p:p.read_bytes() for p in self.old_root.iterdir()}
        body=self.ops.interlock_file.read_bytes();self.assertEqual(self.verify(),body)
        self.assertEqual(self.ops.interlock_file.read_bytes(),body);self.assertEqual(self.stops,[])
        self.assertEqual(before,{p:p.read_bytes() for p in self.old_root.iterdir()})

    def test_exact_transaction_archives_before_retirement_and_prevents_replay(self):
        body=self.ops.interlock_file.read_bytes();self.driver.reconcile_failed_interlock()
        root=self.driver.reconciliation_root()
        self.assertEqual((root/'previous-interlock.json').read_bytes(),body)
        self.assertTrue((root/'intent.json').is_file());self.assertTrue((root/'completion.json').is_file())
        self.assertFalse(self.ops.interlock_file.exists());self.assertEqual(self.stops,['clear_interlock'])
        self.ops.interlock_file.write_bytes(body)
        with self.assertRaisesRegex(RuntimeError,'already_consumed'):self.driver.reconcile_failed_interlock()
        self.assertEqual(self.stops,['clear_interlock'])

    def test_changed_or_missing_interlock_rejects_without_retirement(self):
        self.ops.interlock_file.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'interlock_changed'):self.verify()
        self.ops.interlock_file.unlink()
        with self.assertRaisesRegex(RuntimeError,'binding_invalid'):self.verify()
        self.assertEqual(self.stops,[])

    def test_unknown_interlock_without_explicit_plan_binding_rejects(self):
        self.document.pop('failed_boot_interlock')
        with self.assertRaisesRegex(RuntimeError,'existing_interlock_requires_reconciliation'):self.verify()

    def test_altered_historical_record_rejects(self):
        (self.old_root/'failure.json').write_bytes(b'altered')
        with self.assertRaisesRegex(RuntimeError,'evidence_changed'):self.verify()

    def test_unfinished_or_later_failure_is_not_reconciliable(self):
        self.records['failure.json']['phase']='service_migrate_pending';self.revise_record('failure.json')
        with self.assertRaisesRegex(RuntimeError,'not_reconciliable'):self.verify()

    def test_advanced_attempt_rejects(self):
        (self.old_root/'controller-installation-intent.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'attempt_advanced'):self.verify()

    def test_incomplete_compensation_rejects(self):
        (self.units/'old-proxy.conf').write_bytes(b'changed original')
        with self.assertRaisesRegex(RuntimeError,'compensation_incomplete'):self.verify()

    def test_residual_generated_resource_rejects(self):
        (self.units/'failed-new.service').write_bytes(b'still installed')
        with self.assertRaisesRegex(RuntimeError,'compensation_incomplete'):self.verify()

    def test_changed_current_origin_rejects(self):
        self.contract['origin']['worker_generation']='9'*64
        with self.assertRaisesRegex(RuntimeError,'not_reconciliable'):self.verify()

    def test_active_old_process_service_or_credential_rejects(self):
        proc=self.proc/'123';proc.mkdir()
        entry=self.sources/('normal-source-'+'b'*64)/'source/web/scripts/continue_completed_normal_upgrade.py'
        (proc/'cmdline').write_bytes(b'python3\0'+str(entry).encode()+b'\0execute\0')
        with self.assertRaisesRegex(RuntimeError,'still_running'):self.verify()
        (proc/'cmdline').unlink();proc.rmdir();self.active='old-upgrade.service active running'
        with self.assertRaisesRegex(RuntimeError,'still_running'):self.verify()
        self.active='';self.ops.authorization_file.write_text('private fixture')
        with self.assertRaisesRegex(RuntimeError,'authorization_active'):self.verify()

    def test_locks_are_required_before_any_reconciliation_effect(self):
        self.driver.lock=None
        with self.assertRaisesRegex(RuntimeError,'locks_required'):self.driver.reconcile_failed_interlock()
        self.assertEqual(self.stops,[]);self.assertFalse(self.driver.reconciliation_root().exists())

    def test_archive_failure_preserves_original_interlock(self):
        with patch.object(m,'exclusive',side_effect=OSError('fixture_full')):
            with self.assertRaises(OSError):self.driver.reconcile_failed_interlock()
        self.assertTrue(self.ops.interlock_file.exists());self.assertEqual(self.stops,[])

    def test_change_between_verified_archive_and_retirement_rejects(self):
        original=m.exclusive
        def changed(path,body):
            original(path,body)
            if path.name=='intent.json':self.ops.interlock_file.write_bytes(b'foreign changed lock')
        with patch.object(m,'exclusive',changed):
            with self.assertRaisesRegex(RuntimeError,'interlock_changed'):self.driver.reconcile_failed_interlock()
        self.assertEqual(self.ops.interlock_file.read_bytes(),b'foreign changed lock')
        self.assertEqual(self.stops,[])

    def test_reconciliation_is_not_available_to_historical_operation(self):
        self.contract['version']=1
        with self.assertRaises(RuntimeError):self.verify()
        self.assertEqual(self.stops,[])


if __name__=='__main__':unittest.main()
