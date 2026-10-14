"""Real traffic-validator ranges and real staging-Git signature regression."""
import importlib.machinery
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from test_completed_normal_compose import WEB
from test_completed_normal_application_release import application_contract
from test_completed_normal_admission import fixture_contract
from test_completed_normal_manual_profile import manual_contract
from deployment.lib.control_plane_upgrade import SystemOperations

loader=importlib.machinery.SourceFileLoader('application_release_traffic',str(WEB/'deployment/bin/madar-switch-traffic'))
traffic=importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name,loader));loader.exec_module(traffic)

class ActualFailureRegression(unittest.TestCase):
    def test_exact_authorized_application_and_historical_bounds(self):
        for contract,minimum,maximum,excluded in ((fixture_contract(),115,136,[]),(manual_contract(),136,144,[142]),(application_contract(),136,144,[142])):
            identity={'release_sha':contract['candidate']['source_sha'],'release_slot':contract['candidate']['slot'],
                'schema_compatible_min':minimum,'schema_compatible_max':maximum,'schema_excluded_versions':excluded}
            traffic.verify_completed_identity(contract,identity['release_slot'],identity)
            for changes in ({'schema_compatible_min':minimum+1},{'schema_compatible_max':maximum+1},
                    {'schema_excluded_versions':[143]},{'release_slot':'wrong'},{'release_sha':'0'*40}):
                with self.subTest(changes=changes),self.assertRaises(RuntimeError):
                    traffic.verify_completed_identity(contract,identity['release_slot'],dict(identity,**changes))

    def test_real_staging_git_reproduces_bad_keyword_and_accepts_git_C(self):
        ops=object.__new__(SystemOperations)
        def command(label,args,timeout=300):
            r=subprocess.run(args,capture_output=True,text=True,timeout=timeout,check=True)
            return SimpleNamespace(stdout=r.stdout.strip())
        ops.command=command
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(['git','init','-q',d],check=True)
            subprocess.run(['git','-C',d,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--allow-empty','-qm','fixture'],check=True)
            with self.assertRaises(TypeError):ops.staging_git('before','rev-parse','HEAD',cwd=Path(d))
            expected=subprocess.check_output(['git','-C',d,'rev-parse','HEAD'],text=True).strip()
            self.assertEqual(ops.staging_git('after','-C',d,'rev-parse','HEAD').stdout,expected)
