"""Specification comparisons only; these tests issue no runtime authority."""
import copy
import os
from pathlib import Path
import sys
import unittest

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_candidate import default_dns_spec_matches,worker_spec_matches
from deployment.lib.emergency_routing_repair import spec


class DefaultDNSBindingTests(unittest.TestCase):
    def setUp(self):
        self.original={'Id':'a'*64,'Image':'sha256:'+'b'*64,'Config':{'Env':['NONSECRET=example']},
                       'HostConfig':{'Dns':None,'OomKillDisable':False,'Privileged':False},'Mounts':[]}
        self.expected=spec(self.original)
        self.actual=copy.deepcopy(self.original)
        self.actual['HostConfig']['Dns']=[]

    def test_default_dns_survives_daemon_serialization_without_rewriting_receipt(self):
        before=copy.deepcopy(self.original);observed=copy.deepcopy(self.actual)
        self.assertNotEqual(spec(self.actual),self.expected)
        self.assertTrue(default_dns_spec_matches(self.actual,self.expected))
        self.assertTrue(default_dns_spec_matches(self.original,spec(self.actual)))
        self.assertEqual(self.original,before);self.assertEqual(self.actual,observed)
        self.assertEqual(spec(self.original),self.expected)

    def test_explicit_or_missing_dns_is_not_default(self):
        for dns in (['127.0.0.1'],['1.1.1.1'],{},False,''):
            with self.subTest(dns=dns):
                row=copy.deepcopy(self.actual);row['HostConfig']['Dns']=dns
                self.assertFalse(default_dns_spec_matches(row,self.expected))
        del self.actual['HostConfig']['Dns']
        self.assertFalse(default_dns_spec_matches(self.actual,self.expected))

    def test_other_spec_changes_are_rejected(self):
        for key,value in (('Id','c'*64),('Image','sha256:'+'c'*64),('Config',{'Env':['NONSECRET=changed']}),
                          ('Mounts',[{'Source':'/other'}])):
            with self.subTest(field=key):
                row=copy.deepcopy(self.actual);row[key]=value
                self.assertFalse(default_dns_spec_matches(row,self.expected))
        self.actual['HostConfig']['Privileged']=True
        self.assertFalse(default_dns_spec_matches(self.actual,self.expected))

    def test_worker_oom_and_default_dns_require_governed_start(self):
        self.actual['HostConfig']['OomKillDisable']=None
        self.assertFalse(worker_spec_matches(self.actual,self.expected))
        self.assertTrue(worker_spec_matches(self.actual,self.expected,started_worker=True))
        self.actual['HostConfig']['OomKillDisable']=True
        self.assertFalse(worker_spec_matches(self.actual,self.expected,started_worker=True))

    def test_security_change_is_not_hidden_by_worker_lifecycle(self):
        self.actual['HostConfig'].update(OomKillDisable=None,Privileged=True)
        self.assertFalse(worker_spec_matches(self.actual,self.expected,started_worker=True))


if __name__=='__main__':unittest.main()
