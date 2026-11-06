"""Real private files and modeled daemon: scope, references and partial failures."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB/'staging/integration'))
import run_cleanup as cleanup


class DisposableCleanupTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.source='a'*40;self.project='madar-full-provider-'+self.source[:12]
        self.calls=[];self.rows={};self.volumes={};self.networks={};self.fail_once=None
        for change in (patch.object(cleanup.manage,'RUNTIME',self.root),
                patch.object(cleanup.manage,'PROJECT',self.project),patch.object(cleanup.manage,'OWNER',self.project),
                patch.object(cleanup.manage,'require_staging_host'),patch.object(cleanup.manage,'docker',side_effect=self.docker)):
            change.start();self.addCleanup(change.stop)
        self.policy=cleanup.reserve(self.root,source=self.source)
        self.labels={cleanup.OWNER:self.project,cleanup.PROJECT:self.project}
        created='2099-01-01T00:00:00Z'
        self.rows['a'*64]={'Id':'a'*64,'Created':created,'Config':{'Labels':dict(self.labels,**{'com.docker.compose.service':'postgres'})},
            'State':{'Running':False,'Restarting':False},'Mounts':[],'NetworkSettings':{'Networks':{}}}
        self.volumes[self.project+'_database']={'Name':self.project+'_database','CreatedAt':created,
            'Driver':'local','Options':None,'Labels':dict(self.labels)}
        self.networks[self.project+'_isolated']={'Name':self.project+'_isolated','Created':created,
            'Containers':{},'Labels':dict(self.labels)}

    def docker(self,*args,**kwargs):
        self.calls.append(args)
        if args[:2]==('ps','-aq'):return '\n'.join(self.rows).encode()
        if args[0]=='inspect':return json.dumps([self.rows[k] for k in args[1:]]).encode()
        if args[0]=='rm':del self.rows[args[1]];return b''
        resources={'network':self.networks,'volume':self.volumes}
        table=resources[args[0]]
        if args[1]=='ls':return '\n'.join(table).encode()
        if args[1]=='inspect':return json.dumps([table[args[2]]]).encode()
        if args[1]=='rm':
            if self.fail_once==args[0]:self.fail_once=None;raise RuntimeError('synthetic_remove_failure')
            del table[args[2]];return b''
        self.fail('Unexpected Docker command '+repr(args))

    def run_cleanup(self,**kwargs):return cleanup.teardown(self.root,services={'postgres'},**kwargs)

    def test_dry_run_does_not_mutate_and_apply_verifies_no_leaks_then_repeats(self):
        plan=self.run_cleanup()
        self.assertTrue(plan['dry_run']);self.assertTrue(self.rows);self.assertTrue(self.volumes)
        self.assertFalse(any('rm' in command for command in self.calls))
        result=self.run_cleanup(apply=True)
        self.assertEqual(len(result['removed']),3)
        self.assertFalse(self.rows or self.volumes or self.networks)
        self.assertEqual(self.run_cleanup(apply=True)['removed'],[])
        self.assertTrue(json.loads((self.root/'cleanup-result.json').read_bytes())['complete'])
        self.assertTrue((self.root/cleanup.POLICY).is_file())

    def test_running_restarting_foreign_or_protected_containers_refuse_before_removal(self):
        original=copy.deepcopy(self.rows)
        for change in ('running','restart','foreign','protected','service'):
            self.rows=copy.deepcopy(original);row=self.rows['a'*64]
            if change=='running':row['State']['Running']=True
            elif change=='restart':row['State']['Restarting']=True
            elif change=='foreign':row['Config']['Labels'][cleanup.OWNER]='unrelated'
            elif change=='protected':row['Config']['Labels'][cleanup.PROTECTED]='true'
            else:row['Config']['Labels']['com.docker.compose.service']='unknown'
            with self.subTest(change=change),self.assertRaises(RuntimeError):self.run_cleanup(apply=True)
        self.assertFalse(any('rm' in command for command in self.calls))

    def test_external_stopped_container_volume_or_network_reference_blocks_whole_plan(self):
        for kind in ('volume','network'):
            foreign={'Id':'b'*64,'Config':{'Labels':{}},'State':{'Running':False},
                'Mounts':[],'NetworkSettings':{'Networks':{}}}
            if kind=='volume':foreign['Mounts']=[{'Type':'volume','Name':next(iter(self.volumes))}]
            else:foreign['NetworkSettings']['Networks'][next(iter(self.networks))]={}
            self.rows['b'*64]=foreign
            with self.subTest(kind=kind),self.assertRaisesRegex(RuntimeError,'external_reference'):self.run_cleanup(apply=True)
            del self.rows['b'*64]
        self.assertFalse(any('rm' in command for command in self.calls))

    def test_unknown_endpoint_or_protected_volume_is_not_deleted(self):
        network=next(iter(self.networks.values()));network['Containers']={'b'*64:{}}
        with self.assertRaisesRegex(RuntimeError,'unknown_endpoint'):self.run_cleanup(apply=True)
        network['Containers']={}
        next(iter(self.volumes.values()))['Labels'][cleanup.PROTECTED]='true'
        with self.assertRaisesRegex(RuntimeError,'protected_resource'):self.run_cleanup(apply=True)
        self.assertFalse(any('rm' in command for command in self.calls))

    def test_resource_older_than_fresh_reservation_is_not_adopted(self):
        next(iter(self.volumes.values()))['CreatedAt']='2000-01-01T00:00:00Z'
        with self.assertRaisesRegex(RuntimeError,'predates_run'):self.run_cleanup(apply=True)
        self.assertFalse(any('rm' in command for command in self.calls))

    def test_retained_review_stack_never_stops_or_deletes(self):
        policy=self.policy|{'retain':True}
        (self.root/cleanup.POLICY).write_text(json.dumps(policy))
        with patch.object(cleanup.manage,'compose') as compose:
            with self.assertRaisesRegex(RuntimeError,'explicitly_retained'):
                cleanup.stop_and_teardown(self.root,services={'postgres'})
            compose.assert_not_called()
        self.assertFalse(self.calls)

    def test_legacy_or_symlinked_policy_is_not_adopted(self):
        (self.root/cleanup.POLICY).unlink()
        with self.assertRaises(FileNotFoundError):self.run_cleanup(apply=True)
        other=self.root/'private.json';other.write_text(json.dumps(self.policy));other.chmod(0o600)
        (self.root/cleanup.POLICY).symlink_to(other)
        with self.assertRaisesRegex(RuntimeError,'private_record_required'):self.run_cleanup(apply=True)
        self.assertFalse(self.calls)

    def test_partial_failure_is_audited_and_retry_removes_only_remaining_resources(self):
        self.fail_once='volume'
        with self.assertRaisesRegex(RuntimeError,'synthetic_remove_failure'):self.run_cleanup(apply=True)
        result=json.loads((self.root/'cleanup-result.json').read_bytes())
        self.assertFalse(result['complete']);self.assertEqual(len(result['removed']),2)
        self.assertEqual(len(self.run_cleanup(apply=True)['removed']),1)

    def test_unrelated_project_remains_untouched(self):
        self.rows['b'*64]={'Id':'b'*64,'Config':{'Labels':{cleanup.PROJECT:'unrelated'}},
            'State':{'Running':True},'Mounts':[],'NetworkSettings':{'Networks':{}}}
        self.run_cleanup(apply=True)
        self.assertEqual(set(self.rows),{'b'*64})
