"""Actual Git snapshots/bundles; root/KVM/API boundaries modeled explicitly."""
import copy,hashlib,os,subprocess,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from deployment.lib import schema160_release as release
from deployment.lib import control_plane_upgrade as upgrade
from deployment.lib import isolated_github_observation as github
from deployment.lib.completed_normal_execution import CompletedNormalUpgrade
from deployment.lib.completed_normal_profile import RECONCILED
from deployment.lib.historical_origin import KIND


class IsolatedControllerSourceTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.repo=self.root/'repository';self.repo.mkdir()
        def git(*args):
            return subprocess.check_output(['git','-c','core.hooksPath=/dev/null',*args],cwd=self.repo,stderr=subprocess.DEVNULL).decode().strip()
        self.git=git;git('init','-q','--initial-branch=Saliba-Branch')
        git('config','user.name','Saliba-codes');git('config','user.email','75858844+Saliba-codes@users.noreply.github.com')
        git('remote','add','origin','https://github.com/judahsleibi34/Madar.git')
        (self.repo/'payload').write_text('real test Git main source\n');git('add','.');git('commit','-qm','Original test main')
        self.main=git('rev-parse','HEAD');git('update-ref','refs/remotes/origin/main',self.main)
        (self.repo/'payload').write_text('explicit isolated controller source\n');git('commit','-qam','Isolated controller')
        self.sha=git('rev-parse','HEAD');self.tree=git('rev-parse','HEAD^{tree}')
        self.selection={'version':1,'kind':'isolated-historical-controller-source','repository':'judahsleibi34/Madar',
            'source_branch':'Saliba-Branch','source_sha':self.sha,'tree_oid':self.tree}
        self.contract={'candidate':{'controller_sha':self.sha},'source_roles':{'origin_kind':KIND}}
        self.ops=SimpleNamespace(repo=self.repo,installed_sha=Mock(return_value=self.sha))
        self.enterContext(patch.object(os,'geteuid',return_value=0))
        self.registration=self.enterContext(patch.object(release,'isolated_registration',return_value={'exact':'root registration'}))
        self.api=self.enterContext(patch.object(github,'api',return_value={'sha':self.sha,'commit':{'tree':{'sha':self.tree}}}))

    def test_exact_isolated_source_does_not_rewrite_or_claim_remote_main(self):
        before=self.git('show-ref')
        self.assertEqual(release.isolated_controller_source(self.selection,self.contract,self.ops),self.sha)
        self.assertEqual(self.git('show-ref'),before)
        self.assertEqual(self.git('rev-parse','refs/remotes/origin/main'),self.main)
        self.registration.assert_called_once_with(self.contract)
        self.api.assert_called_once_with('repos/judahsleibi34/Madar/commits/'+self.sha,
            operations=self.ops,label='isolated_controller_source')

    def test_wrong_source_tree_branch_database_registration_or_remote_refuses(self):
        for key,value in (('source_sha','f'*40),('tree_oid','f'*40),('source_branch','main'),('version',True)):
            with self.subTest(key=key),self.assertRaises(RuntimeError):
                release.isolated_controller_source(dict(self.selection,**{key:value}),self.contract,self.ops)
        with patch.object(release,'isolated_registration',side_effect=RuntimeError('wrong database')):
            with self.assertRaisesRegex(RuntimeError,'wrong database'):
                release.isolated_controller_source(self.selection,self.contract,self.ops)
        self.git('remote','set-url','origin','https://attacker.invalid/Madar.git')
        with self.assertRaisesRegex(RuntimeError,'repository_invalid'):
            release.isolated_controller_source(self.selection,self.contract,self.ops)

    def test_changed_git_objects_are_not_authenticated_by_api_identity_alone(self):
        import zlib
        path=self.repo/'.git/objects'/self.tree[:2]/self.tree[2:];body=zlib.decompress(path.read_bytes());path.chmod(0o600)
        path.write_bytes(zlib.compress(body[:-1]+bytes([body[-1]^1])))
        with self.assertRaises(RuntimeError):release.isolated_controller_source(self.selection,self.contract,self.ops)

    def test_existing_resolver_keeps_main_fetch_path_separate_from_registered_isolated_source(self):
        ops=object.__new__(upgrade.SystemOperations);ops.repo=self.repo
        ops.repository_origin=Mock(return_value=upgrade.EXPECTED_CONTRACT['MADAR_CANONICAL_GIT_REMOTE'])
        ops.installed_sha=self.ops.installed_sha;ops.repository_head=Mock(return_value=self.sha);ops.require_clean_repository=Mock()
        def madar_git(label,*args,**kw):
            result=subprocess.run(['git',*args],cwd=self.repo,capture_output=True,text=True)
            return upgrade.CommandResult(result.stdout.strip(),result.stderr,result.returncode)
        ops.madar_git=Mock(side_effect=madar_git)
        ops.resolve_candidate(self.sha,dry_run=False,isolated_selection=self.selection,isolated_contract=self.contract)
        self.assertFalse(any(a.args[1] in {'fetch','ls-remote'} for a in ops.madar_git.call_args_list))
        for kwargs in ({'isolated_selection':self.selection},{'isolated_contract':self.contract},
                {'isolated_selection':self.selection,'isolated_contract':self.contract,'immutable_selection':{}}):
            with self.assertRaisesRegex(RuntimeError,'ambiguous'):ops.resolve_candidate(self.sha,dry_run=False,**kwargs)
        self.assertEqual(self.git('rev-parse','refs/remotes/origin/main'),self.main)

    def test_existing_bundle_stager_exports_selected_controller_without_changing_main(self):
        ops=object.__new__(upgrade.SystemOperations);ops.repo=self.repo;ops.staging_root=self.root/'staging';ops.staging_root.mkdir()
        ops.prepare_upgrade_roots=Mock();ops.resolve_candidate=Mock()
        def command(label,*args,**kwargs):
            result=subprocess.run(['git',*map(str,args)],cwd=self.repo,capture_output=True,text=True,
                env={**os.environ,'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_NO_REPLACE_OBJECTS':'1'})
            if kwargs.get('check',True) and result.returncode:raise RuntimeError('test Git command failed: '+label)
            return upgrade.CommandResult(result.stdout.strip(),result.stderr,result.returncode)
        ops.madar_git=command;ops.root_git=command;ops.staging_git=command
        before=self.git('show-ref');transaction,staged=ops.stage_candidate(self.sha,
            isolated_selection=self.selection,isolated_contract=self.contract)
        self.assertEqual((staged/'payload').read_text(),'explicit isolated controller source\n')
        self.assertEqual(self.git('show-ref'),before)
        self.assertEqual(subprocess.check_output(['git','-C',str(staged),'rev-parse','HEAD']).decode().strip(),self.sha)
        ops.resolve_candidate.assert_called_once_with(self.sha,dry_run=True,immutable_selection=None,
            isolated_selection=self.selection,isolated_contract=self.contract)

    def test_coordinator_cannot_offer_isolated_source_as_real_main_or_an_ordinary_release(self):
        driver=CompletedNormalUpgrade.__new__(CompletedNormalUpgrade)
        driver.document={'isolated_controller_source':self.selection,'fixture_only':True,'production_authorization':False}
        driver.profile=RECONCILED;driver.contract=self.contract;driver.controller=self.sha;driver.ops=SimpleNamespace(resolve_candidate=Mock())
        self.assertEqual(driver.source_options(),{'isolated_selection':self.selection,'isolated_contract':self.contract})
        driver.verify_candidate_remote();driver.ops.resolve_candidate.assert_called_once()
        with self.assertRaisesRegex(RuntimeError,'not_github_main'):driver.canonical_main()
        for key,value in (('fixture_only',False),('production_authorization',True),('immutable_release_selection',{})):
            with patch.dict(driver.document,{key:value}),self.assertRaisesRegex(RuntimeError,'not_historical_rehearsal'):
                driver.source_options()
