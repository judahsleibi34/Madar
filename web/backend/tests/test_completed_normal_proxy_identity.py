"""Fresh proxy bindings preserve complete specifications across inspect order."""
import copy
from types import SimpleNamespace
import unittest

from test_completed_normal_resources import m
from deployment.lib.completed_normal_boot_actor import CompletedNormalBootActor


class ProxyIdentityTests(unittest.TestCase):
    def setUp(self):
        self.row={'Id':'a'*64,'Image':'sha256:'+'b'*64,'Config':{'Env':[]},
            'HostConfig':{'Dns':None,'Privileged':False},
            'Mounts':[{'Destination':'/a','Source':'/first','RW':False},
                      {'Destination':'/b','Source':'/second','RW':True}]}
        self.actor=object.__new__(CompletedNormalBootActor)
        self.actor.document={'proxy_runtime':{'id':self.row['Id'],'image':self.row['Image'],
            'spec_sha256':m.measured_spec(self.row)}}
        self.actor.runtime=SimpleNamespace(inspect=lambda ids:{self.row['Id']:self.row})

    def test_repeated_proxy_inspection_accepts_only_mount_order_and_default_dns(self):
        for _ in range(5):
            self.row['Mounts'].reverse()
            self.row['HostConfig']['Dns']=[]
            self.assertIs(self.actor.proxy_identity(),self.row)

    def test_identity_permissions_mount_fields_or_security_change_fails(self):
        original=copy.deepcopy(self.row)
        for mutate in (lambda r:r.update(Id='c'*64),lambda r:r.update(Image='sha256:'+'d'*64),
                lambda r:r['Mounts'][0].update(RW=True),lambda r:r['Mounts'][0].update(Source='/other'),
                lambda r:r['HostConfig'].update(Privileged=True),lambda r:r['Config'].update(Env=['changed=1'])):
            self.row=copy.deepcopy(original);mutate(self.row)
            with self.assertRaisesRegex(RuntimeError,'proxy_identity_changed'):
                self.actor.proxy_identity()

if __name__=='__main__':unittest.main()
