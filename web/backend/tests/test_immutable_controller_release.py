"""Real Git provenance/bundle tests, never production migration evidence."""
import base64,copy,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import test_control_plane_upgrade as existing
upgrade=existing.upgrade
from deployment.lib.completed_normal_execution import CompletedNormalUpgrade

class ImmutableControllerTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.git=existing.ControlPlaneUpgradeTests.real_git
  self.source,self.selected=existing.ControlPlaneUpgradeTests().real_bundle_source(self.root)
  (self.source/'migration143.sql').write_text('newer development must not stage\n')
  self.git('-C',self.source,'add','.');self.git('-C',self.source,'commit','-qm','newer main')
  self.main=self.git('-C',self.source,'rev-parse','HEAD').stdout.strip()
  self.git('-C',self.source,'update-ref','refs/heads/main',self.main)
  self.git('-C',self.source,'update-ref','refs/remotes/origin/main',self.main)
  self.git('-C',self.source,'checkout','--detach','-q',self.selected)
  url=upgrade.EXPECTED_CONTRACT['MADAR_CANONICAL_GIT_REMOTE']
  self.git('-C',self.source,'remote','add','origin',url)
  self.git('-C',self.source,'config','url.'+str(self.source)+'.insteadOf',url)
  self.selection={'canonical_main_sha':self.main,'selected_tree_oid':self.git('-C',self.source,'rev-parse',self.selected+'^{tree}').stdout.strip(),'ancestry_commit_objects':[{'oid':oid,'body_base64':base64.b64encode(self.git('-C',self.source,'cat-file','commit',oid).stdout.encode()).decode()} for oid in (self.main,self.selected)]}
  self.ops=existing.ControlPlaneUpgradeTests.real_stage_operations(self.source,self.root/'staging')
  def transport(label,*args,**kw):
   r=self.git('-C',self.source,*args,check=False)
   if kw.get('check',True) and r.returncode:raise upgrade.UpgradeError('command_failed:'+label)
   r.stdout=r.stdout.strip();return r
  self.ops.madar_git=transport
  # The owned local transport rewrites URL execution only. Production's
  # canonical-remote guard is separately checked and never relaxed.
  self.ops.repository_origin=lambda:self.git('-C',self.source,'config','--get','remote.origin.url').stdout.strip()
 def test_newer_canonical_main_does_not_replace_exact_selected_tree(self):
  self.ops.resolve_candidate(self.selected,dry_run=True,immutable_selection=self.selection)
  before=self.git('-C',self.source,'show-ref').stdout
  _,staged=self.ops.stage_candidate(self.selected,immutable_selection=self.selection)
  self.assertEqual(self.git('-C',staged,'rev-parse','HEAD').stdout.strip(),self.selected)
  self.assertFalse((staged/'migration143.sql').exists())
  self.assertEqual(self.git('-C',self.source,'show-ref').stdout,before)
  self.assertEqual(self.git('-C',staged,'for-each-ref').stdout,'')
 def test_ordinary_admission_still_rejects_old_revision(self):
  with self.assertRaisesRegex(upgrade.UpgradeError,'approved_sha_not_current_origin_main'):
   self.ops.resolve_candidate(self.selected,dry_run=True)
 def test_fetch_and_staging_use_selected_objects(self):
  self.ops.resolve_candidate(self.selected,dry_run=False,immutable_selection=self.selection)
  _,p=self.ops.stage_candidate(self.selected,immutable_selection=self.selection)
  self.assertEqual((p/'payload.txt').read_text(),'approved\n')
 def test_altered_commit_or_tree_fails_closed(self):
  for mutation in ('body','tree','role','missing'):
   v=copy.deepcopy(self.selection);approved=self.selected
   if mutation=='body':v['ancestry_commit_objects'][0]['body_base64']=base64.b64encode(b'forged').decode()
   if mutation=='tree':v['selected_tree_oid']='0'*40
   if mutation=='role':approved='0'*40
   if mutation=='missing':v['ancestry_commit_objects']=v['ancestry_commit_objects'][:1]
   with self.subTest(mutation=mutation),self.assertRaisesRegex(upgrade.UpgradeError,'immutable_release_selection_invalid'):
    upgrade.validate_immutable_release_selection(v,approved)
 def test_main_change_between_resolution_and_staging_rejects(self):
  self.ops.resolve_candidate(self.selected,dry_run=True,immutable_selection=self.selection)
  self.git('-C',self.source,'update-ref','refs/heads/main',self.selected)
  with self.assertRaises(upgrade.UpgradeError):self.ops.stage_candidate(self.selected,immutable_selection=self.selection)
  self.assertNotIn(upgrade.SELECTED_RELEASE_REF,self.git('-C',self.source,'show-ref').stdout)
 def test_colliding_temporary_ref_preserved(self):
  self.git('-C',self.source,'update-ref',upgrade.SELECTED_RELEASE_REF,self.main)
  with self.assertRaises(upgrade.UpgradeError):self.ops.stage_candidate(self.selected,immutable_selection=self.selection)
  self.assertEqual(self.git('-C',self.source,'rev-parse',upgrade.SELECTED_RELEASE_REF).stdout.strip(),self.main)
 def test_bundle_failure_removes_only_owned_temporary_ref(self):
  original=self.ops.root_git
  def command(label,*a,**kw):
   if label=='git_bundle_create':raise upgrade.UpgradeError('injected_bundle_failure')
   return original(label,*a,**kw)
  self.ops.root_git=command
  with self.assertRaisesRegex(upgrade.UpgradeError,'injected_bundle_failure'):self.ops.stage_candidate(self.selected,immutable_selection=self.selection)
  self.assertNotIn(upgrade.SELECTED_RELEASE_REF,self.git('-C',self.source,'show-ref').stdout)
 def test_coordinator_admits_only_attested_canonical_head(self):
  driver=object.__new__(CompletedNormalUpgrade);driver.controller=self.selected;driver.document={'immutable_release_selection':self.selection};driver.ops=SimpleNamespace(madar_git=Mock(return_value=SimpleNamespace(stdout=self.main+' refs/heads/main')))
  driver.verify_candidate_remote()
  driver.ops.madar_git.return_value.stdout=self.selected+' refs/heads/main'
  with self.assertRaisesRegex(RuntimeError,'candidate_remote_changed'):driver.verify_candidate_remote()
