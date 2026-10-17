"""Adversarial provenance parsing; synthetic API/ZIP fixtures grant no authority."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
sys.path.insert(0,os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib.schema148_artifacts import verify_archive,INPUTS,WORKFLOW

class ArtifactTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.path=Path(temporary.name)/'artifact.zip'
        self.sha='a'*40;self.images={'backend':'sha256:'+'b'*64,'frontend':'sha256:'+'c'*64}
        self.inputs={name:'d'*64 for name in INPUTS}
        self.run={'id':11,'run_attempt':1,'head_sha':self.sha,'repository':{'full_name':'judahsleibi34/Madar'},
            'head_repository':{'full_name':'judahsleibi34/Madar'},'path':WORKFLOW,'name':'Schema148 Candidate Artifacts','status':'completed','conclusion':'success'}
        self.artifact={'id':22,'expired':False,'name':f'schema148-candidate-{self.sha}-11-1','workflow_run':{'id':11,'head_sha':self.sha}}
        self.receipt={'version':1,'repository':'judahsleibi34/Madar','source_sha':self.sha,'build_mode':'fresh-locked-ci','images':self.images,
            'inputs_sha256':self.inputs,'run_id':11,'run_attempt':1,'production_authorized':False,
            'archives':{role:{'file':role+'.tar.gz','sha256':hashlib.sha256(role.encode()).hexdigest(),'bytes':len(role)} for role in self.images}}
        self.write()
    def write(self,extra=None):
        with zipfile.ZipFile(self.path,'w') as archive:
            archive.writestr('receipt.json',json.dumps(self.receipt))
            for role in self.images:archive.writestr(role+'.tar.gz',role)
            if extra:archive.writestr(extra,'untrusted')
        self.artifact['digest']='sha256:'+hashlib.sha256(self.path.read_bytes()).hexdigest()
    def verify(self):return verify_archive(self.path,self.artifact,self.run,source_sha=self.sha,images=self.images,expected_inputs=self.inputs)
    def test_authenticated_exact_source_archive_parses_without_loading_images(self):
        self.assertEqual(self.verify()['images'],self.images)
        self.assertFalse(self.verify()['production_authorized'])
    def test_tampered_archive_digest_refuses(self):
        self.path.write_bytes(self.path.read_bytes()+b'changed')
        with self.assertRaises(RuntimeError):self.verify()
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
