"""Backup-first authorization/integrity regressions; fixtures are not evidence."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib import active_recovery_backup_freshness as module
from deployment.lib.provider_recovery_runtime import digest

class BackupPublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/('a'*64);self.root.mkdir()
        self.plan=SimpleNamespace(digest='a'*64,source_bundle_sha256='b'*64,source_sha='c'*40,
            candidate_images={'backend':'sha256:'+'d'*64,'frontend':'sha256:'+'e'*64},
            candidate_destination={'post_compensation':{'baseline':{'previous_plan_sha256':'f'*64},'pre_grant_backup':{}}})
        self.auth={'operation':'current-data-recovery-backup-before-normal','plan_sha256':self.plan.digest,'source_bundle_sha256':'b'*64}
        self.publication={'plan_sha256':self.plan.digest,'source_bundle_sha256':'b'*64,'marker_sha256':'1'*64,
            'latest_sha256':'1'*64,'backup_receipt_sha256':'1'*64,'backup_id':'madar-20261010T001122Z'}
        self.receipt={'operation':'actual-pre-normal-current-data-backup-restore-replica','plan_sha256':self.plan.digest,
            'source_sha':self.plan.source_sha,'images':self.plan.candidate_images,'schema':115,'local_path':'/var/lib/madar/backups/madar-20261010T001122Z',
            'captured_release_sha':'8'*40,'restore':{'status':'logical_database_and_file_restore_passed'},
            'sha256sums_sha256':'1'*64,'node1':{'plan_sha256':digest({'plan_sha256':self.plan.digest,'operation':self.auth['operation']}),
                'checksum_exit_code':0,'sha256sums_sha256':'1'*64}}
        self.manifest={'backup_id':'madar-20261010T001122Z','release':{'git_sha':'8'*40}}
        self.runtime=SimpleNamespace(budget=Mock(return_value=0),http_status=Mock(),
            inspect=Mock(return_value={'madar-release-proxy':{'State':{'Health':{'Status':'healthy'}}}}))
        for item in (patch.object(module,'BASE',self.base),patch.object(module,'protected',side_effect=lambda p,**kw:p),
            patch.object(module,'readonly_configuration',side_effect=lambda p,**kw:p),patch.object(module,'file_digest',return_value='1'*64),
            patch('scripts.backup_support.verify',return_value=self.manifest),
            patch('deployment.lib.active_recovery_compensated.inspect_history',return_value=(object(),'/fixture',{},{})),
            patch('deployment.lib.active_recovery_fallback.CurrentDataFallback'),patch.object(module,'verification_window'),
            patch.object(module.time,'sleep')):
            item.start();self.addCleanup(item.stop)
        self.save()
    def save(self):
        for name,data in (('authorization.json',self.auth),('publication.json',self.publication),('verified-recovery-backup.json',self.receipt)):
            (self.root/name).write_text(json.dumps(data))
    def verify(self):return module.require_publication(self.plan,Path('/package'),self.runtime)
    def test_missing_actual_publication_cannot_authorize_normal(self):
        (self.root/'publication.json').unlink()
        with self.assertRaises(FileNotFoundError):self.verify()
        self.runtime.http_status.assert_not_called()
    def test_changed_plan_package_marker_latest_receipt_denied_before_health(self):
        for key in ('plan_sha256','source_bundle_sha256','marker_sha256','latest_sha256','backup_receipt_sha256'):
            old=self.publication[key];self.publication[key]='0'*64;self.save()
            with self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'publication_not_bound'):self.verify()
            self.publication[key]=old
        self.runtime.http_status.assert_not_called()
    def test_invalid_restore_image_source_schema_and_replica_fail_closed(self):
        original=copy.deepcopy(self.receipt)
        for key,value in (('restore',{'status':'PASS'}),('images',{}),('source_sha','0'*40),('schema',116),
             ('captured_release_sha','0'*40),('node1',{'checksum_exit_code':True}),('node1',{'checksum_exit_code':1})):
            self.receipt=copy.deepcopy(original);self.receipt[key]=value;self.save()
            with self.subTest(key=key,value=value),self.assertRaisesRegex(RuntimeError,'not_proven'):self.verify()
        self.runtime.http_status.assert_not_called()
    def test_three_full_rounds_and_five_seconds_required(self):
        with patch.object(module.time,'monotonic',side_effect=[0,1,5]):self.assertEqual(self.verify(),self.publication)
        self.assertEqual(self.runtime.http_status.call_count,8)
    def test_security_failure_is_not_retried(self):
        self.runtime.inspect.side_effect=RuntimeError('changed_identity')
        with self.assertRaisesRegex(RuntimeError,'changed_identity'):self.verify()
        self.assertEqual(self.runtime.inspect.call_count,1)
    def test_overall_deadline_is_enforced(self):
        from deployment.lib.emergency_routing_repair import VerificationDeadline
        self.runtime.budget.side_effect=VerificationDeadline('expired')
        with self.assertRaises(VerificationDeadline):self.verify()
        self.runtime.http_status.assert_not_called()
    def test_original_plans_without_backup_phase_remain_unchanged(self):
        self.plan.candidate_destination=None
        self.assertIsNone(self.verify());self.runtime.http_status.assert_not_called()

class RecoveryBackupRuntimeTests(unittest.TestCase):
    def test_changed_private_proxy_pid_spec_or_attachment_aborts_before_child(self):
        context=object.__new__(module.RecoveryBackupContext);context.container='a'*64;context.pid=42
        context.proxy_spec='b'*64;context.attachments={'native':{'NetworkID':'c'*64}}
        for row in ({'State':{'Pid':43},'NetworkSettings':{'Networks':context.attachments}},
                    {'State':{'Pid':42},'NetworkSettings':{'Networks':context.attachments}},
                    {'State':{'Pid':42},'NetworkSettings':{'Networks':{}}}):
            context.runtime=SimpleNamespace(inspect=Mock(return_value={'fixture':row}))
            expected='0'*64 if row['NetworkSettings']['Networks']==context.attachments and row['State']['Pid']==42 else context.proxy_spec
            with patch.object(module,'spec',return_value=expected),patch.object(module,'checked') as child:
                with self.assertRaisesRegex(RuntimeError,'proxy_changed'):context.capture({},3,SimpleNamespace(pw_uid=1000,pw_gid=1000))
                child.assert_not_called()
    def test_failed_context_validation_never_deletes_unverified_resource(self):
        context=object.__new__(module.RecoveryBackupContext);context.container='a'*64;context.proxy_spec='b'*64
        context.attachments={};context.runtime=SimpleNamespace(inspect=Mock(return_value={'fixture':{'Id':'0'*64}}))
        with patch.object(module,'checked') as command:
            with self.assertRaisesRegex(RuntimeError,'proxy_changed'):context.close_and_guard()
            command.assert_not_called()

class PublishedArtifactBindingTests(BackupPublicationTests):
    def test_changed_published_checksums_rejected(self):
        self.receipt['sha256sums_sha256']='0'*64;self.save()
        with self.assertRaisesRegex(RuntimeError,'checksums_changed'):self.verify()
        self.runtime.http_status.assert_not_called()
    def test_foreign_backup_path_rejected(self):
        self.receipt['local_path']='/tmp/test-backup';self.save()
        with self.assertRaisesRegex(RuntimeError,'publication_path_invalid'):self.verify()
        self.runtime.http_status.assert_not_called()
