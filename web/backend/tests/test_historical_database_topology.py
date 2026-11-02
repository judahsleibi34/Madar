"""Exercise the real native observer; Docker/SQL transport is modeled here."""
import copy,json,unittest
from unittest.mock import Mock,patch
from deployment.lib import completed_normal_database as database
from deployment.lib import historical_origin as origin
from deployment.lib.completed_normal_profile import RECONCILED
from deployment.lib.completed_normal_resources import measured_spec
from test_historical_origin import HistoricalPreparationBindingTests


class HistoricalDatabaseTopologyTests(unittest.TestCase):
    def setUp(self):
        self.contract=HistoricalPreparationBindingTests().contract()
        self.expected=self.contract['database']
        self.topology={self.expected['network_name']:self.expected['network_id'],'historical-control':'7'*64}
        self.row={'Id':self.expected['container_id'],'Image':self.expected['image'],'Name':'/supabase-db',
            'Config':{},'HostConfig':{},'Mounts':[],
            'State':{'Running':True,'Health':{'Status':'healthy'}},
            'NetworkSettings':{'Networks':{k:{'NetworkID':v,'EndpointID':'endpoint','IPAddress':'10.1.0.2'} for k,v in self.topology.items()}}}
        self.expected['spec_sha256']=measured_spec(self.row)
        self.observed={'database':{'system_identifier':self.expected['system_identifier']},'database_networks':copy.deepcopy(self.topology)}
        self.objects=dict(self.topology)
        def command(args):
            if args[:3]==['docker','network','inspect']:
                return json.dumps([{'Id':self.objects[args[3]]}]) if args[3] in self.objects else '[]'
            self.assertEqual(args[:3],['docker','exec',self.expected['container_id']])
            return json.dumps({'system_identifier':self.expected['system_identifier'],'schema':146})
        self.runtime=Mock();self.runtime.command.side_effect=command
        self.runtime.inspect.side_effect=lambda _: {'db':self.row}
        self.enterContext(patch.object(origin,'recorded_observation',return_value=self.observed))
        self.enterContext(patch.object(origin.os,'geteuid',return_value=0))
        self.enterContext(patch.object(database,'profile',return_value=RECONCILED))

    def check(self,**kw):return database.observe_native(self.contract,self.runtime,**kw)

    def test_exact_two_enrolled_bridges_are_observed_independently(self):
        self.assertEqual(self.check(),146)
        observed=[c.args[0][3] for c in self.runtime.command.call_args_list if c.args[0][:3]==['docker','network','inspect']]
        self.assertEqual(set(observed),set(self.topology))

    def test_same_configuration_hash_cannot_mask_endpoint_substitution(self):
        self.row['NetworkSettings']['Networks']['historical-control']['NetworkID']='8'*64
        self.assertEqual(measured_spec(self.row),self.expected['spec_sha256'])
        with self.assertRaisesRegex(RuntimeError,'native_database_network_changed'):self.check()

    def test_extra_or_missing_network_and_replaced_network_object_refuse(self):
        endpoints=copy.deepcopy(self.row['NetworkSettings']['Networks'])
        for changed in (dict(endpoints,foreign={'NetworkID':'9'*64}),{self.expected['network_name']:endpoints[self.expected['network_name']]}):
            self.row['NetworkSettings']['Networks']=changed
            with self.assertRaisesRegex(RuntimeError,'native_database_network_changed'):self.check()
        self.row['NetworkSettings']['Networks']=endpoints
        self.objects['historical-control']='8'*64
        with self.assertRaisesRegex(RuntimeError,'native_database_network_changed'):self.check()

    def test_missing_enrollment_topology_does_not_fall_back_to_legacy_single_network(self):
        self.observed.pop('database_networks')
        with self.assertRaisesRegex(RuntimeError,'database_networks_changed'):self.check()

    def test_running_container_with_cleared_endpoint_cannot_claim_pending(self):
        self.row['NetworkSettings']['Networks']['historical-control']={'NetworkID':''}
        with self.assertRaisesRegex(RuntimeError,'native_database_network_changed'):self.check(allow_pending=True)

    def test_stopped_endpoints_still_require_exact_network_objects(self):
        from deployment.lib.emergency_routing_repair import AvailabilityFailure
        self.row['State']={'Running':False,'Status':'exited'}
        for endpoint in self.row['NetworkSettings']['Networks'].values():endpoint.clear();endpoint['NetworkID']=''
        with self.assertRaises(AvailabilityFailure):self.check(allow_pending=True)
        self.objects.pop('historical-control')
        with self.assertRaisesRegex(RuntimeError,'native_database_network_changed'):self.check(allow_pending=True)

    def test_ordinary_completed_origins_keep_single_network_contract(self):
        self.contract['source_roles'].pop('origin_kind')
        with self.assertRaisesRegex(RuntimeError,'native_database_network_changed'):self.check()
        self.row['NetworkSettings']['Networks'].pop('historical-control')
        self.assertEqual(self.check(),146)

    def test_different_operation_cannot_gain_historical_multi_network_permission(self):
        self.contract['operation']='completed-normal-schema115-136-upgrade'
        with self.assertRaisesRegex(RuntimeError,'database_networks_changed'):self.check()
