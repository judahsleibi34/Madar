"""Measured dependency binding regressions, never real acceptance evidence."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_inputs import observe_runtime_dependencies
from deployment.lib.provider_recovery_runtime import SERVICES

class Runtime:
    def __init__(self):
        self.redis='registered-redis';self.ping='PONG'
        canonical=[f'madar-{slot}-{role}' for slot in ('blue','green') for role in ('backend','frontend','notification-worker','calendar-sync-worker','data-deletion-worker')]
        self.rows={name:{'Id':str(i).zfill(64),'Image':'sha256:'+'c'*64,'Config':{},'HostConfig':{},'Mounts':[],
            'State':{'Running':name in SERVICES or name==self.redis,'Health':{'Status':'healthy'}},
            'NetworkSettings':{'Networks':{'retained':{'NetworkID':'d'*64,'IPAddress':'10.0.0.1'}}}} for i,name in enumerate([*SERVICES,self.redis,*canonical])}
        self.rows[self.redis]['State'].pop('Health')
    def input_bytes(self):return {}
    def inspect(self,names):return {name:copy.deepcopy(self.rows[name]) for name in names}
    def command(self,args):
        if args[1]=='exec':return self.ping
        return json.dumps([{'Name':'retained','Id':'d'*64,'Driver':'bridge','Internal':True,'IPAM':{},'Options':{}}])

class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.r=Runtime();p=patch('deployment.lib.emergency_routing_repair.identities',return_value=(None,None,{'backend':'registered-local-fallback-backend'},None));p.start();self.addCleanup(p.stop)
    def test_ip_reassignment_preserves_binding_but_image_change_does_not(self):
        original=observe_runtime_dependencies(self.r)[1]
        self.r.rows['supabase-db']['NetworkSettings']['Networks']['retained']['IPAddress']='10.0.0.9'
        self.assertEqual(original,observe_runtime_dependencies(self.r)[1])
        self.r.rows['supabase-db']['Image']='sha256:'+'a'*64
        self.assertNotEqual(original,observe_runtime_dependencies(self.r)[1])
    def test_missing_native_or_unhealthy_service_rejected(self):
        self.r.rows['supabase-auth']['State']['Health']['Status']='unhealthy'
        with self.assertRaisesRegex(RuntimeError,'dependency_unhealthy'):observe_runtime_dependencies(self.r)
    def test_redis_without_docker_health_requires_actual_ping(self):
        observe_runtime_dependencies(self.r)
        self.r.ping='NOAUTH'
        with self.assertRaisesRegex(RuntimeError,'redis_unhealthy'):observe_runtime_dependencies(self.r)
    def test_running_old_worker_rejected(self):
        self.r.rows['madar-blue-notification-worker']['State']['Running']=True
        with self.assertRaisesRegex(RuntimeError,'consumer_running'):observe_runtime_dependencies(self.r)
    def test_changed_volume_and_network_are_bound(self):
        original=observe_runtime_dependencies(self.r)[1]
        self.r.rows[self.r.redis]['Mounts']=[{'Source':'different'}]
        self.assertNotEqual(original,observe_runtime_dependencies(self.r)[1])
        self.r.rows[self.r.redis]['NetworkSettings']['Networks']['retained']['NetworkID']='a'*64
        self.assertNotEqual(original,observe_runtime_dependencies(self.r)[1])


class NativeContinuationTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from types import SimpleNamespace
        from deployment.lib.active_recovery_inputs import INPUTS,PRIVATE_CONFIGURATION
        from deployment.lib.provider_recovery_runtime import digest
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.runtime=Runtime();self.runtime.schema=lambda:None
        p=patch('deployment.lib.emergency_routing_repair.identities',return_value=(None,None,{'backend':'registered-local-fallback-backend'},None));p.start();self.addCleanup(p.stop)
        packet,hash_value=observe_runtime_dependencies(self.runtime)
        (self.root/'runtime-dependencies.json').write_text(json.dumps(packet))
        self.plan=SimpleNamespace(retained_inputs={'runtime_dependencies':hash_value})
        paths={}
        for key in ('native_configuration','native_compose','native_override','gateway_bootstrap','gateway_cds','gateway_lds'):
            paths[key]=self.root/key;paths[key].write_bytes(b'fixture');self.plan.retained_inputs[key]=__import__('hashlib').sha256(b'fixture').hexdigest()
        for name,value in [('INPUTS',paths),('readonly_configuration',lambda path,**kwargs:path),('protected',lambda path,**kwargs:path)]:
            p=patch('deployment.lib.active_recovery_inputs.'+name,value);p.start();self.addCleanup(p.stop)
    def verify(self):
        from deployment.lib.active_recovery_inputs import verify_native_continuation_dependencies
        return verify_native_continuation_dependencies(self.plan,self.root,self.runtime)
    def test_native_health_transition_is_pending_with_unchanged_identity(self):
        from deployment.lib.emergency_routing_repair import AvailabilityFailure
        self.runtime.rows['supabase-auth']['State']['Health']['Status']='starting'
        with self.assertRaises(AvailabilityFailure):self.verify()
        self.runtime.rows['supabase-auth']['State']['Health']['Status']='healthy'
        self.assertEqual(self.verify()['schema'],115)
    def test_image_or_network_change_is_integrity_failure_not_pending(self):
        self.runtime.rows['supabase-db']['Image']='sha256:'+'0'*64
        with self.assertRaisesRegex(RuntimeError,'identity_changed'):self.verify()
    def test_ip_reassignment_does_not_invalidate_identity(self):
        self.runtime.rows['supabase-db']['NetworkSettings']['Networks']['retained']['IPAddress']='10.0.0.99'
        self.verify()
    def test_native_config_change_is_fatal(self):
        (self.root/'native_configuration').write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'configuration_changed'):self.verify()
