"""Actual allocator used by both preflight and the locked staging boundary."""
import copy
import json
import os
from pathlib import Path
import socket
import sys
import unittest

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB))
from deployment.lib import completed_normal_resources as m
from deployment.lib.emergency_routing_repair import spec
from test_completed_normal_admission import fixture_contract

class Inventory:
    def __init__(self):self.rows=[];self.nets=[]
    def command(self,args,**kw):
        if args[:3]==['docker','ps','-aq']:return '\n'.join(r['Id'] for r in self.rows)
        if args[:2]==['docker','inspect']:return json.dumps(self.rows)
        if args[:4]==['docker','network','ls','-q']:return '\n'.join(r['Id'] for r in self.nets)
        if args[:3]==['docker','network','inspect']:return json.dumps(self.nets)
        raise AssertionError('allocator attempted a mutation')

class CompletedNormalResourceTests(unittest.TestCase):
    def setUp(self):self.contract=fixture_contract();self.runtime=Inventory()
    def test_preflight_and_locked_recheck_have_exact_same_immutable_resolution(self):
        before=m.verify_allocation(self.contract,'green',self.runtime)
        self.assertEqual(before,m.verify_allocation(self.contract,'green',self.runtime))
        self.assertEqual(before['ports'],{'backend':'8201','frontend':'3200','redis':'6382'})
        self.assertTrue(all(n.startswith('madar-schema136-') for n in before['containers'].values()))
        self.assertFalse(any(n.startswith('madar-green-') for n in before['containers'].values()))
    def test_name_or_network_acquired_between_preflight_and_staging_rejects(self):
        selected=m.verify_allocation(self.contract,'green',self.runtime)
        self.runtime.rows=[{'Id':'c'*64,'Name':'/'+selected['containers']['backend']}]
        with self.assertRaisesRegex(RuntimeError,'container_occupied'):m.verify_allocation(self.contract,'green',self.runtime)
        self.runtime.rows=[];self.runtime.nets=[{'Id':'n','Name':selected['networks']['default']}]
        with self.assertRaisesRegex(RuntimeError,'network_occupied'):m.verify_allocation(self.contract,'green',self.runtime)
    def test_subnet_collision_fails_even_with_different_network_name(self):
        self.runtime.nets=[{'Id':'n','Name':'other-owner','IPAM':{'Config':[{'Subnet':'10.249.4.0/25'}]}}]
        with self.assertRaisesRegex(RuntimeError,'subnet_occupied'):m.verify_allocation(self.contract,'green',self.runtime)
    def test_stopped_port_reservation_requires_exact_fresh_binding_and_inhibition(self):
        row={'Id':'c'*64,'Name':'/madar-historical','Image':'sha256:'+'d'*64,'Config':{},'Mounts':[],
            'HostConfig':{'RestartPolicy':{'Name':'no'},'PortBindings':{'8000/tcp':[{'HostPort':'8201'}]}},'State':{'Running':False}}
        self.runtime.rows=[row]
        with self.assertRaisesRegex(RuntimeError,'already_reserved'):m.verify_allocation(self.contract,'green',self.runtime)
        self.contract['resources']['green']['retired_port_declarations']={'madar-historical':
            {'container_id':row['Id'],'image_id':row['Image'],'spec_sha256':spec(row)}}
        m.verify_allocation(self.contract,'green',self.runtime)
        row['Image']='sha256:'+'e'*64
        with self.assertRaisesRegex(RuntimeError,'already_reserved'):m.verify_allocation(self.contract,'green',self.runtime)
    def test_running_retained_container_never_displaced(self):
        row={'Id':'c'*64,'Name':'/madar-historical','Image':'sha256:'+'d'*64,'Config':{},'Mounts':[],
            'HostConfig':{'RestartPolicy':{'Name':'no'},'PortBindings':{'8000/tcp':[{'HostPort':'8201'}]}},'State':{'Running':True}}
        self.runtime.rows=[row]
        self.contract['resources']['green']['retired_port_declarations']={'madar-historical':
            {'container_id':row['Id'],'image_id':row['Image'],'spec_sha256':spec(row)}}
        with self.assertRaisesRegex(RuntimeError,'already_reserved'):m.verify_allocation(self.contract,'green',self.runtime)

if __name__=='__main__':unittest.main()
