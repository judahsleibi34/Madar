"""Leaf compensation: failed stops must still close public traffic.

Fixture-only runtime adapter; no production Docker, credentials or writes.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_completed_normal_admission import fixture_contract
from deployment.lib import completed_normal_boot_actor as m


class Runtime:
    def __init__(self):
        self.rows={};self.commands=[];self.deadline=None;self.fail_stop=None;self.fail_nginx=False
    def inspect(self,names):return {n:self.rows[n] for n in names if n in self.rows}
    def command(self,args):
        self.commands.append(args)
        if args[1]=='stop':
            if args[2]==self.fail_stop:raise RuntimeError('fixture_stop_failed')
            self.rows[args[2]]['State']['Running']=False
    def nginx_preflight(self,*args):
        if self.fail_nginx:raise RuntimeError('fixture_nginx_failed')
    def publish(self,body):self.commands.append(['publish-maintenance'])
    def reload(self):self.commands.append(['reload'])
    def verify_maintenance(self):self.commands.append(['verified-maintenance'])


class BootCompensationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        actor=object.__new__(m.CompletedNormalBootActor)
        actor.root=self.root;actor.contract=fixture_contract()
        actor.contract['source_roles']['completion_root']=str(self.root/'original')
        actor.document={'proxy_runtime':{'id':'proxy','image':'proxy-image','spec_sha256':'unused'}}
        actor.runtime=Runtime();self.actor=actor;self.events=[]
        actor.event=lambda *a,**kw:self.events.append((a,kw))
        actor.proxy_identity=lambda:actor.runtime.rows['proxy']
        roles=[*m.WORKERS,'backend']
        record={'runtimes':{k:{'id':k,'image':'accepted-image'} for k in roles}}
        (self.root/'candidate-runtime.json').write_text(json.dumps(record))
        for role in roles:actor.runtime.rows[role]={'Id':role,'Image':'accepted-image','State':{'Running':True}}
        actor.runtime.rows['proxy']={'Id':'proxy','Image':'proxy-image','State':{'Running':True}}
        self.patch=patch.object(m,'protected',lambda p,**kw:Path(p));self.patch.start();self.addCleanup(self.patch.stop)
        self.lock=patch.object(m,'runtime_mutation_lock',lambda p:__import__('contextlib').nullcontext());self.lock.start();self.addCleanup(self.lock.stop)
    def test_successful_stops_publish_verified_maintenance(self):
        self.actor.maintenance()
        self.assertIn(['verified-maintenance'],self.actor.runtime.commands)
        self.assertNotIn(['docker','stop','proxy'],self.actor.runtime.commands)
    def test_failed_worker_stop_still_stops_only_bound_proxy_and_reports_failure(self):
        self.actor.runtime.fail_stop=m.WORKERS[0]
        with self.assertRaisesRegex(RuntimeError,'compensation_worker_stop_failed'):self.actor.maintenance()
        self.assertIn(['docker','stop','proxy'],self.actor.runtime.commands)
        self.assertIn(['docker','stop','backend'],self.actor.runtime.commands)
        self.assertNotIn(['publish-maintenance'],self.actor.runtime.commands)
    def test_untrusted_candidate_receipt_cannot_skip_proxy_stop(self):
        (self.root/'candidate-runtime.json').write_text('invalid-json')
        with self.assertRaisesRegex(RuntimeError,'compensation_worker_stop_failed'):self.actor.maintenance()
        self.assertEqual(self.actor.runtime.commands,[['docker','stop','proxy']])
    def test_changed_proxy_identity_is_never_stopped_by_name(self):
        self.actor.runtime.fail_nginx=True
        self.actor.runtime.rows['proxy']['Image']='unbound-replacement'
        with self.assertRaisesRegex(RuntimeError,'safe_proxy_stop_unavailable'):self.actor.maintenance()
        self.assertNotIn(['docker','stop','proxy'],self.actor.runtime.commands)
    def test_failed_nginx_uses_exact_proxy_id_without_database_restore(self):
        self.actor.runtime.fail_nginx=True;self.actor.maintenance()
        self.assertIn(['docker','stop','proxy'],self.actor.runtime.commands)
        self.assertTrue(all(a[0]!='restore' for a in self.actor.runtime.commands))


if __name__=='__main__':unittest.main()
