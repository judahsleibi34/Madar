"""Adversarial provenance parsing; synthetic API/ZIP fixtures grant no authority."""
import copy
import io
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import tarfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import zipfile
sys.path.insert(0,os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib.schema148_artifacts import archive_runtime_identity,verify_archive,verify_required_ci,INPUTS,WORKFLOW,capture_candidate_archive
from deployment.lib import schema148_artifacts as artifacts

class ArtifactTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.path=Path(temporary.name)/'artifact.zip'
        self.sha='a'*40;self.images={'backend':'sha256:'+'b'*64,'frontend':'sha256:'+'c'*64}
        self.inputs={name:'d'*64 for name in INPUTS}
        self.run={'id':11,'run_attempt':1,'head_sha':self.sha,'repository':{'full_name':'judahsleibi34/Madar'},
            'head_repository':{'full_name':'judahsleibi34/Madar'},'path':WORKFLOW,'name':'Schema148 Candidate Artifacts','status':'completed','conclusion':'success'}
        self.artifact={'id':22,'expired':False,'name':f'schema148-candidate-{self.sha}-11-1','workflow_run':{'id':11,'head_sha':self.sha}}
        self.receipt={'version':1,'repository':'judahsleibi34/Madar','source_sha':self.sha,'build_mode':'fresh-locked-ci','images':self.images,
            'build_host_image_ids':self.images,'runtime_identity':'single-OCI-manifest-containerd',
            'inputs_sha256':self.inputs,'run_id':11,'run_attempt':1,'production_authorized':False,
            'archives':{role:{'file':role+'.tar.gz','sha256':hashlib.sha256(role.encode()).hexdigest(),'bytes':len(role)} for role in self.images}}
        self.write()
    def write(self,extra=None,payloads=None):
        with zipfile.ZipFile(self.path,'w') as archive:
            archive.writestr('receipt.json',json.dumps(self.receipt))
            for role in self.images:archive.writestr(role+'.tar.gz',(payloads or {}).get(role,role.encode()))
            if extra:archive.writestr(extra,'untrusted')
        self.artifact['digest']='sha256:'+hashlib.sha256(self.path.read_bytes()).hexdigest()
    def verify(self):return verify_archive(self.path,self.artifact,self.run,source_sha=self.sha,images=self.images,expected_inputs=self.inputs)
    def test_authenticated_exact_source_archive_parses_without_loading_images(self):
        self.assertEqual(self.verify()['images'],self.images)
        self.assertFalse(self.verify()['production_authorized'])
    def test_tampered_archive_digest_refuses(self):
        self.path.write_bytes(self.path.read_bytes()+b'changed')
        with self.assertRaises(RuntimeError):self.verify()
    def test_path_replacement_after_authentication_cannot_substitute_parsed_receipt(self):
        original=self.path.read_bytes()
        payload=b'substituted image archive'
        self.receipt['archives']['backend'].update(bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest())
        self.write(payloads={'backend':payload})
        replacement=self.path.with_name('replacement.zip');self.path.rename(replacement)
        self.path.write_bytes(original)
        self.artifact['digest']='sha256:'+hashlib.sha256(original).hexdigest()
        original_open=zipfile.ZipFile
        def replace_then_open(*args,**kwargs):
            replacement.replace(self.path)
            return original_open(*args,**kwargs)
        with patch('deployment.lib.schema148_artifacts.zipfile.ZipFile',side_effect=replace_then_open):
            self.assertEqual(self.verify()['archives']['backend']['sha256'],hashlib.sha256(b'backend').hexdigest())
        self.assertNotEqual('sha256:'+hashlib.sha256(self.path.read_bytes()).hexdigest(),self.artifact['digest'])
    def test_same_inode_mutation_after_authentication_cannot_change_consumed_bytes(self):
        original=self.path.read_bytes()
        payload=b'substituted image archive'
        self.receipt['archives']['backend'].update(bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest())
        self.write(payloads={'backend':payload})
        replacement=self.path.read_bytes();self.path.write_bytes(original)
        self.artifact['digest']='sha256:'+hashlib.sha256(original).hexdigest()
        original_open=zipfile.ZipFile
        def overwrite_then_open(*args,**kwargs):
            self.path.write_bytes(replacement)
            return original_open(*args,**kwargs)
        with patch('deployment.lib.schema148_artifacts.zipfile.ZipFile',side_effect=overwrite_then_open):
            self.assertEqual(self.verify()['archives']['backend']['sha256'],hashlib.sha256(b'backend').hexdigest())
    def test_symlink_archive_refuses(self):
        actual=self.path.with_name('actual.zip');self.path.rename(actual)
        self.path.symlink_to(actual)
        with self.assertRaisesRegex(RuntimeError,'schema148_ci_archive_invalid'):self.verify()
    def test_expired_wrong_run_source_repository_workflow_and_failed_ci_refuse(self):
        for key,value in (('head_sha','e'*40),('path','untrusted.yml'),('conclusion','failure'),('run_attempt',True),('repository',{'full_name':'untrusted/repo'})):
            original=copy.deepcopy(self.run);self.run[key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):self.verify()
            self.run=original
        self.artifact['expired']=True
        with self.assertRaises(RuntimeError):self.verify()
    def test_overlay_or_changed_source_image_inputs_run_and_authority_claim_refuse(self):
        for key,value in (('build_mode','offline-source-overlay'),('source_sha','e'*40),('images',{}),('inputs_sha256',{}),('run_id',12),('version',True),('production_authorized',True)):
            original=copy.deepcopy(self.receipt);self.receipt[key]=value;self.write()
            with self.subTest(key=key),self.assertRaises(RuntimeError):self.verify()
            self.receipt=original
    def test_traversal_extra_and_duplicate_members_refuse_without_extraction(self):
        for name in ('../outside','extra.json','receipt.json'):
            self.write(extra=name)
            with self.subTest(name=name),self.assertRaises(RuntimeError):self.verify()
    def test_image_archive_content_digest_refuses_even_when_outer_zip_matches(self):
        self.receipt['archives']['backend']['sha256']='0'*64;self.write()
        with self.assertRaises(RuntimeError):self.verify()
    def test_wrong_artifact_head_and_name_cannot_rebind_receipt(self):
        self.artifact['workflow_run']['head_sha']='e'*40
        with self.assertRaises(RuntimeError):self.verify()
        self.artifact['workflow_run']['head_sha']=self.sha;self.artifact['name']='other'
        with self.assertRaises(RuntimeError):self.verify()

    def test_application_ci_must_be_exact_source_and_latest_successful_run(self):
        records={workflow:{'workflow_runs':[{**self.run,'name':name,'path':'.github/workflows/'+workflow}]}
            for workflow,name in (('backend-check.yml','Backend Check'),('frontend-check.yml','Frontend Check'))}
        verify_required_ci(records,self.sha)
        for changed in ('failure','in_progress','wrong_source','wrong_repository','wrong_workflow'):
            invalid=copy.deepcopy(records);row=invalid['backend-check.yml']['workflow_runs'][0]
            if changed=='failure':row['conclusion']='failure'
            elif changed=='in_progress':row['status']='in_progress'
            elif changed=='wrong_source':row['head_sha']='e'*40
            elif changed=='wrong_repository':row['repository']={'full_name':'untrusted/repo'}
            else:row['path']='untrusted.yml'
            with self.subTest(reason=changed),self.assertRaises(RuntimeError):verify_required_ci(invalid,self.sha)
        older=copy.deepcopy(records['backend-check.yml']['workflow_runs'][0])
        records['backend-check.yml']['workflow_runs'].append({**older,'id':12,'conclusion':'failure'})
        with self.assertRaises(RuntimeError):verify_required_ci(records,self.sha)

    def test_runtime_manifest_and_config_id_are_explicitly_bound_across_engines(self):
        config=b'{"architecture":"amd64","os":"linux"}'
        config_id='sha256:'+hashlib.sha256(config).hexdigest()
        manifest=json.dumps({'schemaVersion':2,'config':{'digest':config_id}}).encode()
        identity='sha256:'+hashlib.sha256(manifest).hexdigest()
        path=self.path.parent/'image.tar.gz'
        def write(config_bytes=config,manifests=None):
            files={'index.json':json.dumps({'manifests':manifests or [{'digest':identity}]}).encode(),
                'manifest.json':json.dumps([{'Config':'blobs/sha256/'+config_id.split(':')[1]}]).encode(),
                'blobs/sha256/'+identity.split(':')[1]:manifest,'blobs/sha256/'+config_id.split(':')[1]:config_bytes}
            with tarfile.open(path,'w:gz') as archive:
                for name,data in files.items():
                    member=tarfile.TarInfo(name);member.size=len(data);archive.addfile(member,io.BytesIO(data))
        write()
        self.assertEqual(archive_runtime_identity(path,config_id),identity)
        self.assertEqual(archive_runtime_identity(path,identity),identity)
        with self.assertRaises(RuntimeError):archive_runtime_identity(path,'sha256:'+'0'*64)
        write(config_bytes=b'tampered')
        with self.assertRaises(RuntimeError):archive_runtime_identity(path,config_id)
        write(manifests=[{'digest':identity},{'digest':identity}])
        with self.assertRaises(RuntimeError):archive_runtime_identity(path,config_id)

    def oci_fixture(self,changed=None):
        self.receipt['build_timestamp']='2026-10-20T10:00:00Z';payloads={}
        self.receipt['build_host_image_ids']={}
        for role in self.images:
            labels={'org.opencontainers.image.revision':self.sha,'com.madar.release.sha':self.sha,
                'com.madar.release.built_at':self.receipt['build_timestamp'],'com.madar.build.mode':'fresh-locked-ci'}
            if role=='frontend':labels['com.madar.frontend.api_origin']='/api'
            if changed and changed[0]==role:labels.update(changed[1])
            config=json.dumps({'architecture':'amd64','os':'linux','config':{'Labels':labels}}).encode()
            config_id='sha256:'+hashlib.sha256(config).hexdigest()
            manifest=json.dumps({'schemaVersion':2,'config':{'digest':config_id}}).encode()
            identity='sha256:'+hashlib.sha256(manifest).hexdigest()
            files={'index.json':json.dumps({'manifests':[{'digest':identity}]}).encode(),
                'manifest.json':json.dumps([{'Config':'blobs/sha256/'+config_id.split(':')[1]}]).encode(),
                'blobs/sha256/'+identity.split(':')[1]:manifest,'blobs/sha256/'+config_id.split(':')[1]:config}
            result=io.BytesIO()
            with tarfile.open(fileobj=result,mode='w:gz') as archive:
                for name,data in files.items():
                    member=tarfile.TarInfo(name);member.size=len(data);archive.addfile(member,io.BytesIO(data))
            payloads[role]=result.getvalue();self.images[role]=identity
            self.receipt['build_host_image_ids'][role]=config_id
            self.receipt['archives'][role].update(bytes=len(payloads[role]),sha256=hashlib.sha256(payloads[role]).hexdigest())
        self.write(payloads=payloads)

    def capture(self,name='captured'):
        return capture_candidate_archive(self.path,self.path.parent/name,self.artifact,self.run,
            source_sha=self.sha,images=self.images,expected_inputs=self.inputs)

    def test_capture_preserves_authenticated_bytes_and_actual_oci_provenance(self):
        self.oci_fixture();original=self.path.read_bytes()
        receipt=self.capture();self.assertEqual(receipt,self.receipt)
        retained=self.path.parent/'captured'/'archive.zip'
        self.assertEqual(retained.read_bytes(),original);self.assertEqual(retained.stat().st_mode&0o777,0o600)
        self.path.write_bytes(b'operator input changed')
        self.assertEqual(retained.read_bytes(),original);self.assertFalse(receipt['production_authorized'])

    def test_capture_rejects_actual_wrong_source_overlay_origin_and_build_labels(self):
        for index,(role,labels) in enumerate((('backend',{'org.opencontainers.image.revision':'e'*40}),
                ('backend',{'com.madar.release.sha':'e'*40}),('backend',{'com.madar.build.mode':'overlay'}),
                ('backend',{'com.madar.staging.build_mode':'offline-overlay'}),
                ('frontend',{'com.madar.frontend.api_origin':'http://foreign.invalid'}),
                ('frontend',{'com.madar.release.built_at':'changed'}))):
            self.oci_fixture((role,labels))
            with self.subTest(labels=labels),self.assertRaisesRegex(RuntimeError,'captured_image_incompatible'):
                self.capture(str(index))

    def test_capture_rejects_receipt_relabeling_of_actual_oci_identity(self):
        self.oci_fixture();self.images['backend']='sha256:'+'0'*64
        payloads={}
        with zipfile.ZipFile(self.path) as archive:
            for role in self.images:payloads[role]=archive.read(role+'.tar.gz')
        self.write(payloads=payloads)
        with self.assertRaisesRegex(RuntimeError,'captured_image_incompatible'):self.capture()

    def test_failed_capture_cannot_overwrite_or_reuse_partial_directory(self):
        self.path.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'archive_digest_changed'):self.capture()
        self.assertTrue((self.path.parent/'captured').is_dir())
        self.oci_fixture()
        with self.assertRaises(FileExistsError):self.capture()

    def test_capture_refuses_symlink_destination_without_touching_target(self):
        self.oci_fixture();target=self.path.parent/'other';target.mkdir()
        (self.path.parent/'captured').symlink_to(target,target_is_directory=True)
        with self.assertRaises(FileExistsError):self.capture()
        self.assertEqual(list(target.iterdir()),[])


class CandidateSealTests(unittest.TestCase):
    """MODEL transport/ownership only; never a root installation acceptance."""
    def setUp(self):
        self.fixture=ArtifactTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;f.oci_fixture()
        self.root=f.path.parent/'attempt';self.root.mkdir()
        from test_completed_normal_admission import fixture_contract
        contract=fixture_contract();contract['candidate'].update(source_sha=f.sha,images=f.images)
        self.actor=SimpleNamespace(root=self.root,contract=contract)
        self.binding={'archive':str(f.path),'artifact_id':22,'run_id':11}
        receipt=capture_candidate_archive(f.path,self.root/'candidate-artifacts',f.artifact,f.run,
            source_sha=f.sha,images=f.images,expected_inputs=f.inputs)
        self.record=artifacts.candidate_seal_binding(self.actor,self.binding,f.artifact,f.run,receipt)
        self.write()
        for p in (patch.object(artifacts,'provenance_inputs',return_value=(f.artifact,f.run,f.inputs)),
                patch('deployment.lib.provider_recovery_runtime.protected',lambda p,**kw:Path(p)),
                patch('deployment.lib.provider_recovery_runtime.readonly_configuration',side_effect=AssertionError('mutable fallback'))):
            p.start();self.addCleanup(p.stop)

    def write(self):
        (self.root/'candidate-artifact-seal.json').write_text(json.dumps(self.record))

    def test_reverification_uses_retained_archive_after_original_disappears(self):
        self.fixture.path.unlink()
        self.assertEqual(artifacts.verify_provenance(self.actor,self.binding),self.fixture.receipt)

    def test_seal_drift_in_source_controller_database_plan_or_images_rejects(self):
        for key in ('context_sha256','plan_sha256','source_sha','controller_sha','database','images','migration_manifest_sha256','run_attempt','authority_issued'):
            original=self.record[key];self.record[key]='changed';self.write()
            with self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'candidate_seal_changed'):
                artifacts.verify_provenance(self.actor,self.binding)
            self.record[key]=original;self.write()

    def test_partial_capture_never_falls_back_to_original_archive(self):
        (self.root/'candidate-artifact-seal.json').unlink()
        with self.assertRaises(FileNotFoundError):artifacts.verify_provenance(self.actor,self.binding)

    def test_modified_retained_archive_and_expired_api_evidence_reject(self):
        archive=self.root/'candidate-artifacts'/'archive.zip';original=archive.read_bytes()
        archive.write_bytes(original+b'changed')
        with self.assertRaisesRegex(RuntimeError,'archive_digest_changed'):
            artifacts.verify_provenance(self.actor,self.binding)
        archive.write_bytes(original);self.fixture.artifact['expired']=True
        with self.assertRaisesRegex(RuntimeError,'artifact_identity_invalid'):
            artifacts.verify_provenance(self.actor,self.binding)

    def test_capture_wrapper_rejects_nonroot_before_api_or_any_file_effect(self):
        with patch.object(artifacts.os,'geteuid',return_value=1000),self.assertRaisesRegex(RuntimeError,'protected_capture_required'):
            artifacts.seal_candidate_provenance(self.actor,self.binding)
