"""CI producer/real child agreement; simulated Docker results, no authority."""
import io
import hashlib
import zipfile
from types import SimpleNamespace
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import test_completed_normal_compose as fixture
from test_schema160_release import reconciled_contract
from deployment.lib.schema148_artifacts import candidate_image_tags, verify_prepared_candidate_images

class CandidateImagesTests(unittest.TestCase):
    def setUp(self):
        self.contract=reconciled_contract();self.candidate=self.contract['candidate']
        self.sha=self.candidate['source_sha'];self.tags=candidate_image_tags(self.sha)
        self.rows={tag:{'Id':self.candidate['images'][role],'Config':{'Labels':{
            'com.madar.release.sha':self.sha,'org.opencontainers.image.revision':self.sha,
            'com.madar.release.built_at':'accepted-time','com.madar.build.mode':'fresh-locked-ci',
            **({'com.madar.frontend.api_origin':'/api'} if role=='frontend' else {})}}}
            for role,tag in self.tags.items()}
        self.commands=[]
    def command(self,args):
        self.commands.append(args)
        self.assertEqual(args[:3],['docker','image','inspect'])
        return json.dumps([self.rows[args[3]]])
    def verify(self):return verify_prepared_candidate_images(self.contract,'accepted-time',self.command)
    def test_readonly_preflight_accepts_exact_imported_images(self):
        self.assertFalse(self.verify()['authority_issued']);self.assertEqual(len(self.commands),2)
    def test_missing_images_refuse_before_effects(self):
        self.rows.clear()
        with self.assertRaisesRegex(RuntimeError,'candidate_image_unavailable'):self.verify()
    def test_substitution_labels_api_timestamp_and_build_mode_refuse(self):
        baseline=copy.deepcopy(self.rows)
        for role,key,value in [('backend','Id','sha256:'+'0'*64),
                ('backend','com.madar.release.sha','0'*40),('backend','org.opencontainers.image.revision','0'*40),
                ('frontend','com.madar.frontend.api_origin','https://foreign.invalid'),
                ('backend','com.madar.release.built_at','other'),('backend','com.madar.build.mode','manual'),
                ('backend','com.madar.staging.build_mode','synthetic')]:
            with self.subTest(role=role,key=key):
                self.rows=copy.deepcopy(baseline);row=self.rows[self.tags[role]]
                if key=='Id':row[key]=value
                else:row['Config']['Labels'][key]=value
                with self.assertRaisesRegex(RuntimeError,'candidate_image_changed'):self.verify()
    def test_real_child_uses_ci_names_and_never_builds_missing_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            ops=fixture.cli.DockerGitOperations(fixture.WEB.parent,Path(directory),Path(directory)/'env',
                fixture.cli.Compatibility.load(fixture.WEB/'deployment/releases/schema-146-160-coordinated.json'))
            ops.release_root=fixture.WEB.parent;ops.completed_normal_admission=self.contract
            def run(args,**kwargs):
                self.assertEqual(args[:3],['docker','image','inspect'])
                row=self.rows.get(args[-1])
                if row is None:raise subprocess.CalledProcessError(1,args)
                return json.dumps(row['Config']['Labels']) if args[4]=='{{json .Config.Labels}}' else row['Id']
            ops.run=run
            with patch('deployment.lib.schema160_release.isolated_registration',return_value={}), patch.dict(os.environ,{'VITE_API_URL':'/api','PUBLIC_SITE_DOMAIN':'madarportal.com','MADAR_COMPOSE_OVERRIDE':''}):
                result=ops.build(self.sha,self.candidate['slot'])
                self.assertEqual(result['backend'],self.tags['backend']+'@'+self.candidate['images']['backend'])
                self.rows.clear()
                with self.assertRaisesRegex(RuntimeError,'accepted_artifact_changed'):ops.build(self.sha,self.candidate['slot'])

class ImportTests(unittest.TestCase):
    def test_member_is_verified_before_actual_load_fd_is_given_to_docker(self):
        from deployment.lib.isolated_candidate_images import load_member
        payload=b'bounded synthetic archive bytes';metadata={'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:z.writestr('backend.tar.gz',payload)
        buf.seek(0)
        with zipfile.ZipFile(buf) as archive:
            def run(args,**kwargs):
                self.assertEqual(args,['docker','image','load'])
                self.assertEqual(kwargs['stdin'].read(),payload)
                return SimpleNamespace(returncode=0)
            with patch('deployment.lib.isolated_candidate_images.subprocess.run',side_effect=run) as effect:
                load_member(archive,'backend',metadata);effect.assert_called_once()
            for changed in ({'bytes':len(payload)-1},{'sha256':'0'*64}):
                with patch('deployment.lib.isolated_candidate_images.subprocess.run') as effect:
                    with self.assertRaisesRegex(RuntimeError,'member_changed'):
                        load_member(archive,'backend',dict(metadata,**changed))
                    effect.assert_not_called()
            with patch('deployment.lib.isolated_candidate_images.subprocess.run',return_value=SimpleNamespace(returncode=1)):
                with self.assertRaisesRegex(RuntimeError,'import_failed'):load_member(archive,'backend',metadata)
    def test_production_and_nonroot_preparation_refuse_without_effect(self):
        from deployment.lib.isolated_candidate_images import prepare
        actor=SimpleNamespace(contract={},document={})
        with patch('deployment.lib.isolated_candidate_images.subprocess.run') as effect:
            with self.assertRaisesRegex(RuntimeError,'scope_required'):prepare(actor,lambda:None)
            effect.assert_not_called()

if __name__=='__main__':unittest.main()
