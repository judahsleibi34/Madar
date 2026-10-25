"""Real bounded ZIP/JSON captures with modeled GitHub; never release authority."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

from deployment.lib import completed_normal_evidence as evidence
from deployment.lib import schema148_artifacts as artifacts
from deployment.lib.completed_normal_profile import profile
from test_schema160_release import reconciled_contract


class CanonicalApplicationEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.archive=self.root/'fresh.zip'
        self.contract=reconciled_contract();self.source=self.contract['candidate']['source_sha']
        self.images=self.contract['candidate']['images']
        repo={'full_name':artifacts.REPOSITORY}
        self.run={'id':100,'head_sha':self.source,'run_attempt':1,'status':'completed','conclusion':'success',
            'path':evidence.FRESH_WORKFLOW,'name':evidence.FRESH_NAME,'repository':repo,'head_repository':repo}
        self.artifact={'id':101,'expired':False,'name':f'full-provider-{self.source}-100-1',
            'workflow_run':{'id':100,'head_sha':self.source}}
        self.image_run=dict(self.run,id=50,path=artifacts.WORKFLOW,name='Schema148 Candidate Artifacts')
        self.image_artifact={'id':51,'expired':False,'name':f'schema148-candidate-{self.source}-50-1',
            'workflow_run':{'id':50,'head_sha':self.source},'digest':'sha256:'+'e'*64}
        self.latest=[self.run];self.receipt={'run_attempt':1,'build_timestamp':'synthetic-time'}
        self.binding={'archive':str(self.archive),'artifact_id':101,'run_id':100}
        self.image_binding={'archive':str(self.root/'images.zip'),'artifact_id':51,'run_id':50}
        rows={}
        for n,name in enumerate(sorted(evidence.FRESH_SERVICES),1):
            role='backend' if name in {'backend','calendar-sync-worker','notification-worker','deletion-worker'} else 'frontend'
            image=self.contract['candidate']['redis_image'] if name=='redis' else self.images[role]
            rows[name]={'id':f'{n:064x}','image':image,'running':True,'health':'healthy'}
        self.report={'version':1,'status':'PASS','source_sha':self.source,'schema':160,'images':self.images,
            'acceptance_kind':'fresh_application','origin_schema':None,'existing_database_upgrade_accepted':False,
            'protected_controller_execution':False,'production_authorized':False,'source_overlay_used':False,
            'native_auth_mfa_refresh_csrf_storage_notifications_readiness':True,'native_tenant_read_write_isolation':True,
            'worker_protocols':{'delivery':2,'outbox':2,'deletion':2},'protected_upgrade_status':'BLOCKED_DEFERRED',
            'artifact_id':51,'run_id':50,'run_attempt':1,'archive_sha256':self.image_artifact['digest'],'runtime':rows}
        self.command=Mock(side_effect=self.api)
        self.actor=SimpleNamespace(contract=self.contract,ops=SimpleNamespace(command=self.command),document={})
        change=patch.object(evidence,'readonly_configuration',side_effect=lambda p,**kw:Path(p));change.start();self.addCleanup(change.stop)
        self.write()

    def write(self, *, body=None, extra=None):
        with zipfile.ZipFile(self.archive,'w',compression=zipfile.ZIP_DEFLATED) as output:
            output.writestr('full-provider-acceptance.json',body if body is not None else json.dumps(self.report))
            if extra:output.writestr(extra,'untrusted')
        self.artifact.update(digest='sha256:'+hashlib.sha256(self.archive.read_bytes()).hexdigest(),size_in_bytes=self.archive.stat().st_size)

    def api(self,label,args,**kwargs):
        self.assertEqual(label,'schema160_fresh_evidence');self.assertEqual(kwargs,{'timeout':30})
        self.assertEqual(args[:6],['/usr/sbin/runuser','-u','madar','--','/usr/bin/gh','api'])
        prefix='repos/'+artifacts.REPOSITORY+'/actions/'
        self.assertTrue(args[-1].startswith(prefix));endpoint=args[-1][len(prefix):]
        values={'artifacts/101':self.artifact,'runs/100':self.run,'artifacts/51':self.image_artifact,
            'runs/50':self.image_run,'workflows/full-provider-staging.yml/runs?head_sha='+self.source+'&per_page=100':{'workflow_runs':self.latest}}
        return SimpleNamespace(stdout=json.dumps(values[endpoint]))

    def verify(self):
        return evidence.verified_fresh_application(self.actor,self.binding,self.image_binding,self.receipt)

    def test_authenticated_fresh_acceptance_is_not_preserved_upgrade_or_authority(self):
        result=self.verify()
        self.assertTrue(result['fresh_application_accepted']);self.assertFalse(result['preserved_upgrade_accepted'])
        self.assertFalse(result['authority_issued']);self.assertEqual(self.command.call_count,10)
        with self.assertRaises(RuntimeError):profile(self.contract)
        with self.assertRaisesRegex(RuntimeError,'protected_rehearsal_acceptance_required'):
            evidence.verify_complete_rehearsal(self.actor)

    def test_caller_pass_packet_cannot_authenticate_itself(self):
        self.archive.write_text('{"status":"PASS"}')
        with self.assertRaises(RuntimeError):self.verify()

    def test_source_scope_protocol_and_preservation_relabelling_reject_even_authenticated_packets(self):
        original=copy.deepcopy(self.report)
        for key,value in [('schema',150),('version',True),('source_sha','f'*40),('production_authorized',True),
                ('existing_database_upgrade_accepted',True),('protected_controller_execution',True),
                ('origin_schema',146),('source_overlay_used',True),('worker_protocols',{'delivery':2,'outbox':1,'deletion':2}),
                ('worker_protocols',{'delivery':2.0,'outbox':2,'deletion':2})]:
            self.report=copy.deepcopy(original);self.report[key]=value;self.write()
            with self.subTest(key=key,value=value),self.assertRaises(RuntimeError):self.verify()

    def test_unknown_wrong_image_and_unhealthy_runtimes_reject(self):
        original=copy.deepcopy(self.report)
        for case in ('extra','missing','image','health','redis'):
            self.report=copy.deepcopy(original)
            if case=='extra':self.report['runtime']['unknown']={}
            elif case=='missing':del self.report['runtime']['auth']
            elif case=='image':self.report['runtime']['backend']['image']='sha256:'+'f'*64
            elif case=='redis':self.report['runtime']['redis']['image']='sha256:'+'f'*64
            else:self.report['runtime']['storage']['health']='unhealthy'
            self.write()
            with self.subTest(case=case),self.assertRaises(RuntimeError):self.verify()

    def test_stale_foreign_failed_expired_and_rerun_metadata_reject(self):
        for target,key,value in [(self.run,'head_sha','f'*40),(self.run,'status','in_progress'),
                (self.run,'conclusion','failure'),(self.run,'run_attempt',2),
                (self.run,'head_repository',{'full_name':'foreign/fork'}),(self.run,'path','.github/workflows/other.yml'),
                (self.artifact,'expired',True),(self.artifact,'id',False),(self.artifact,'id',101.0),(self.artifact,'size_in_bytes',2*1024**2+1),
                (self.image_run,'run_attempt',2),(self.image_run,'conclusion','failure'),(self.image_artifact,'expired',True)]:
            original=copy.deepcopy(target[key]);target[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(RuntimeError):self.verify()
            target[key]=original
        self.latest=[dict(self.run,id=102,status='in_progress')]
        with self.assertRaisesRegex(RuntimeError,'api_identity_changed'):self.verify()

    def test_changed_api_during_capture_refuses(self):
        original=self.command.side_effect
        def changed(label,args,**kw):
            if self.command.call_count>5:self.artifact['expired']=True
            return original(label,args,**kw)
        self.command.side_effect=changed
        with self.assertRaisesRegex(RuntimeError,'api_identity_changed'):self.verify()

    def test_duplicate_json_zip_inventory_and_oversized_members_refuse(self):
        for body,extra in [(('{"version":1,'+json.dumps(self.report)[1:]).encode(),None),
                (None,'unexpected.json'),(b'x'*(512*1024+1),None)]:
            self.write(body=body,extra=extra)
            with self.subTest(extra=extra),self.assertRaises(RuntimeError):self.verify()

    def test_nonregular_and_oversized_local_archives_refuse(self):
        original=self.archive.read_bytes()
        self.archive.unlink();os.mkfifo(self.archive)
        with self.assertRaises(RuntimeError):self.verify()
        self.archive.unlink();self.archive.write_bytes(original)
        other=self.archive.with_name('other.zip');self.archive.rename(other);self.archive.symlink_to(other)
        with self.assertRaises(RuntimeError):self.verify()
        self.archive.unlink();self.archive.write_bytes(original)
        with self.archive.open('wb') as stream:stream.truncate(2*1024**2+1)
        with self.assertRaises(RuntimeError):self.verify()

    def test_archive_replacement_after_authentication_cannot_replace_consumed_report(self):
        original=artifacts.zipfile.ZipFile
        def changed(*args,**kwargs):
            self.archive.write_bytes(b'changed after hashing')
            return original(*args,**kwargs)
        with patch.object(artifacts.zipfile,'ZipFile',side_effect=changed):
            self.assertTrue(self.verify()['fresh_application_accepted'])

    def test_codec_caller_can_only_tighten_the_existing_bound(self):
        for limit in (True,0,-1,6*1024**3+1):
            with self.subTest(limit=limit),self.assertRaisesRegex(RuntimeError,'archive_limit_invalid'):
                with artifacts.authenticated_bytes(self.archive,self.artifact['digest'],max_bytes=limit):pass

    def test_canonical_dispatch_authenticates_image_bytes_before_fresh_report(self):
        replica={'host':'madar-node1-lan','filesystem_uuid':'1'*8+'-'+'2'*4+'-'+'3'*4+'-'+'4'*4+'-'+'5'*12,'configuration_sha256':'a'*64}
        self.actor.package=self.root
        self.actor.document.update(application_evidence={},application_artifacts={'build_timestamp':'synthetic-time'},
            node1_replica=replica,live_configuration_sha256={'node1_configuration':'a'*64})
        for name,value in {'provenance':self.image_binding,'fresh_application':self.binding}.items():
            path=self.root/(name+'.json');path.write_text(json.dumps(value))
            self.actor.document['application_evidence'][name]={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        with patch('deployment.lib.schema160_release.captured_source') as sql,\
                patch.object(artifacts,'verify_provenance',return_value=self.receipt) as images:
            result=evidence.verify_application_evidence(self.actor)
            sql.assert_called_once_with(self.root/'source')
            images.assert_called_once_with(self.actor,self.image_binding)
            self.assertTrue(result['fresh_application']['fresh_application_accepted'])
            self.assertFalse(result['complete_upgrade_rehearsal']);self.assertFalse(result['node1_recovery_accepted'])
        with patch('deployment.lib.schema160_release.captured_source'),\
                patch.object(artifacts,'verify_provenance',side_effect=RuntimeError('image_bytes_changed')):
            self.command.reset_mock()
            with self.assertRaisesRegex(RuntimeError,'image_bytes_changed'):evidence.verify_application_evidence(self.actor)
            self.command.assert_not_called()

    def test_canonical_changed_sql_refuses_before_any_artifact_or_api(self):
        self.actor.package=self.root
        with patch('deployment.lib.schema160_release.captured_source',side_effect=RuntimeError('sql_changed')):
            with self.assertRaisesRegex(RuntimeError,'sql_changed'):evidence.verify_application_evidence(self.actor)
        self.command.assert_not_called()
