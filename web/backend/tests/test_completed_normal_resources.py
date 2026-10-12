"""Actual allocator used by both preflight and the locked staging boundary."""
import copy
import json
import os
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

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
    def setUp(self):
        self.contract=fixture_contract();self.runtime=Inventory()
        # Exercise real bind/listen without probing serving production ports.
        sockets=[socket.socket() for _ in range(3)]
        try:
            for listener in sockets:listener.bind(('127.0.0.1',0))
            self.ports=dict(zip(('backend','frontend','redis'),(str(s.getsockname()[1]) for s in sockets)))
        finally:
            for listener in sockets:listener.close()
        original=dict(m.PORTS)
        changed=patch.dict(m.PORTS,dict(original,green=self.ports),clear=True);changed.start();self.addCleanup(changed.stop)
    def test_preflight_and_locked_recheck_have_exact_same_immutable_resolution(self):
        before=m.verify_allocation(self.contract,'green',self.runtime)
        self.assertEqual(before,m.verify_allocation(self.contract,'green',self.runtime))
        self.assertEqual(before['ports'],self.ports)
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
            'HostConfig':{'RestartPolicy':{'Name':'no'},'PortBindings':{'8000/tcp':[{'HostPort':self.ports['backend']}]}},'State':{'Running':False}}
        self.runtime.rows=[row]
        with self.assertRaisesRegex(RuntimeError,'already_reserved'):m.verify_allocation(self.contract,'green',self.runtime)
        self.contract['resources']['green']['retired_port_declarations']={'madar-historical':
            {'container_id':row['Id'],'image_id':row['Image'],'spec_sha256':spec(row)}}
        m.verify_allocation(self.contract,'green',self.runtime)
        row['Image']='sha256:'+'e'*64
        with self.assertRaisesRegex(RuntimeError,'already_reserved'):m.verify_allocation(self.contract,'green',self.runtime)
    def test_running_retained_container_never_displaced(self):
        row={'Id':'c'*64,'Name':'/madar-historical','Image':'sha256:'+'d'*64,'Config':{},'Mounts':[],
            'HostConfig':{'RestartPolicy':{'Name':'no'},'PortBindings':{'8000/tcp':[{'HostPort':self.ports['backend']}]}},'State':{'Running':True}}
        self.runtime.rows=[row]
        self.contract['resources']['green']['retired_port_declarations']={'madar-historical':
            {'container_id':row['Id'],'image_id':row['Image'],'spec_sha256':spec(row)}}
        with self.assertRaisesRegex(RuntimeError,'already_reserved'):m.verify_allocation(self.contract,'green',self.runtime)
    def test_retained_resource_binding_uses_same_complete_mount_measurement(self):
        row={'Id':'c'*64,'Name':'/madar-historical','Image':'sha256:'+'d'*64,'Config':{},
            'Mounts':[{'Destination':'/a','Source':'/one','RW':False},{'Destination':'/b','Source':'/two','RW':True}],
            'HostConfig':{'RestartPolicy':{'Name':'no'},'PortBindings':{'8000/tcp':[{'HostPort':self.ports['backend']}]}},'State':{'Running':False}}
        self.runtime.rows=[row]
        self.contract['resources']['green']['retired_port_declarations']={'madar-historical':
            {'container_id':row['Id'],'image_id':row['Image'],'spec_sha256':m.measured_spec(row)}}
        row['Mounts'].reverse();m.verify_allocation(self.contract,'green',self.runtime)
        row['Mounts'][0]['RW']=False
        with self.assertRaisesRegex(RuntimeError,'already_reserved'):m.verify_allocation(self.contract,'green',self.runtime)

class CompletedNormalSpecificationTests(unittest.TestCase):
    def setUp(self):
        self.row={'Id':'a'*64,'Image':'sha256:'+'b'*64,'Config':{'Env':['NONSECRET=fixture']},
            'HostConfig':{'Dns':None,'OomKillDisable':False,'Privileged':False},
            'Mounts':[{'Destination':'/'+str(i),'Source':'/fixture/'+str(i),'Type':'bind','RW':False,
                'Propagation':'rprivate'} for i in range(9)]}
    def test_new_native_and_candidate_hashes_are_order_independent_without_dropping_mount_fields(self):
        before=copy.deepcopy(self.row);expected=m.measured_spec(self.row)
        changed=copy.deepcopy(self.row);changed['Mounts'].reverse();changed['HostConfig']['Dns']=[]
        self.assertEqual(m.measured_spec(changed),expected)
        self.assertEqual(self.row,before)
        for field,value in (('RW',True),('Source','/other'),('Destination','/other'),
                ('Propagation','shared'),('Type','volume')):
            altered=copy.deepcopy(changed);altered['Mounts'][0][field]=value
            self.assertFalse(m.measured_spec_matches(altered,expected))
        changed['Mounts'][0]['extra_security_field']='changed'
        self.assertFalse(m.measured_spec_matches(changed,expected))
    def test_default_dns_and_worker_first_start_remain_narrow(self):
        expected=m.measured_spec(self.row)
        changed=copy.deepcopy(self.row);changed['HostConfig']['OomKillDisable']=None
        self.assertFalse(m.measured_spec_matches(changed,expected))
        self.assertTrue(m.measured_spec_matches(changed,expected,started_worker=True))
        for key,value in (('OomKillDisable',True),('Dns',['1.1.1.1']),('Privileged',True)):
            altered=copy.deepcopy(changed);altered['HostConfig'][key]=value
            self.assertFalse(m.measured_spec_matches(altered,expected,started_worker=True))
    def test_legacy_origin_comparison_preserves_exact_historical_hash(self):
        self.row['Mounts']=self.row['Mounts'][:5];before=copy.deepcopy(self.row);expected=spec(self.row)
        changed=copy.deepcopy(self.row);changed['Mounts'].reverse()
        self.assertTrue(m.origin_spec_matches(changed,expected))
        self.assertEqual(spec(self.row),expected);self.assertEqual(self.row,before)
        changed['Mounts'][0]['RW']=True
        self.assertFalse(m.origin_spec_matches(changed,expected))
    def test_docker_restart_default_dns_options_and_search_serialization(self):
        from itertools import product
        row=copy.deepcopy(self.row);row['Mounts']=row['Mounts'][:5]
        row['HostConfig'].update(Dns=None,DnsOptions=None,DnsSearch=None)
        expected=m.measured_spec(row);historical=spec(row)
        for values in product((None,[]),repeat=3):
            changed=copy.deepcopy(row);changed['HostConfig'].update(dict(zip(('Dns','DnsOptions','DnsSearch'),values)))
            self.assertTrue(m.measured_spec_matches(changed,expected))
            self.assertTrue(m.origin_spec_matches(changed,historical))
        for field,value in (('Dns',['1.1.1.1']),('DnsOptions',['use-vc']),('DnsSearch',['other.invalid'])):
            changed=copy.deepcopy(row);changed['HostConfig'][field]=value
            self.assertFalse(m.measured_spec_matches(changed,expected))
            self.assertFalse(m.origin_spec_matches(changed,historical))
        self.assertEqual(spec(row),historical)
    def test_ambiguous_inventory_and_unbounded_legacy_search_fail_closed(self):
        changed=copy.deepcopy(self.row);changed['Mounts'][0]['Destination']=changed['Mounts'][1]['Destination']
        with self.assertRaisesRegex(RuntimeError,'mount_inventory_invalid'):m.measured_spec(changed)
        expected=spec(self.row);self.row['Mounts'].reverse()
        self.assertFalse(m.origin_spec_matches(self.row,expected))

if __name__=='__main__':unittest.main()
