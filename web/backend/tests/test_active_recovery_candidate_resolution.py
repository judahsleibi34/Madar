"""Slot feasibility regressions; fixtures grant no production authorization."""
import copy,json,os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_candidate import resolve_candidate_destination,DetachedRecoveryCandidate,require_unreserved_ports,KINDS
from deployment.lib.provider_recovery_runtime import file_digest
from deployment.lib.emergency_routing_repair import spec

class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.prefix='madar-provider402-rehearsal-000000000000-candidate';self.net=self.prefix+'-blue-runtime'
        data={'worker_authority':{'owner':'RECOVERY','candidate':{'slot':'blue','sha':'b'*40},'old':{'slot':'green','sha':'c'*40}},
            'traffic':{'sha':'b'*40,'slot':'local-fallback','provider':'local','schema':115,'database_restore':False},
            'recovery_transaction':{'phase':'local_rollback_active','slot':'blue','sha':'b'*40},
            'local_transaction':{'phase':'local_rollback_active','sha':'b'*40},
            'release_state':{'active_slot':'green','known_good_release':{'schema':115,'slot':'green','sha':'c'*40}}}
        self.paths={};hashes={'runtime_dependencies':'e'*64}
        for k,v in data.items():
            p=Path(self.tmp.name)/k;p.write_text(json.dumps(v));self.paths[k]=p;hashes[k]=file_digest(p)
        self.plan=SimpleNamespace(retained_inputs=hashes,candidate_destination=None,digest='f'*64)
        self.rows={}
        for slot in ('blue','green'):
            for kind in ('backend','frontend',*(k+'-worker' for k in KINDS)):
                name='madar-'+slot+'-'+kind
                self.rows[name]={'Id':name,'Image':'sha256:'+'a'*64,'Config':{'Labels':{'org.opencontainers.image.revision':('a' if slot=='blue' else 'b')*40}},
                    'HostConfig':{'RestartPolicy':{'Name':'no'}},'State':{'Running':slot=='blue' and kind in ('backend','frontend')},'Mounts':[],'NetworkSettings':{'Networks':{self.net:{'NetworkID':'d'*64}}}}
        self.rows[self.prefix+'-redis']={'State':{'Running':True},'Config':{'Labels':{'com.madar.recovery.profile':'provider402-signin'}},'Mounts':[{'Type':'volume','Destination':'/data'}],'NetworkSettings':{'Networks':{self.net:{}}}}
        self.packet={'runtimes':{n:{'container_id':r['Id'],'image_id':r['Image'],'spec_sha256':spec(r),'networks':{self.net:'d'*64}} for n,r in self.rows.items() if n.startswith('madar-blue-') or n.startswith('madar-green-')},'networks':{self.net:{'Id':'d'*64}}}
        self.rt=Mock();self.rt.command.return_value='';self.rt.inspect.side_effect=lambda names:{n:copy.deepcopy(self.rows[n]) for n in names}
        self.rt.network.return_value={'Name':self.net,'Id':'d'*64,'Driver':'bridge','Internal':True}
        for target,value in [('deployment.lib.active_recovery_inputs.INPUTS',self.paths),('deployment.lib.active_recovery_candidate.protected',lambda p,**kw:p),
            ('deployment.lib.provider_recovery_runtime.readonly_configuration',lambda p,**kw:p),
            ('deployment.lib.active_recovery_inputs.observe_runtime_dependencies',lambda rt:(self.packet,'e'*64)),
            ('deployment.lib.active_recovery_candidate.identities',lambda value:(None,None,{'backend':self.prefix+'-local-fallback-backend'},None)),
            ('deployment.lib.active_recovery_candidate.require_unreserved_ports',Mock()),
            ('deployment.lib.active_recovery_candidate.DetachedRecoveryCandidate.free_subnet',lambda self:'10.253.0.0/24')]:
            p=patch(target,value);p.start();self.addCleanup(p.stop)
    def resolve(self):return resolve_candidate_destination(self.plan,self.rt)
    def test_historical_green_origin_and_occupied_blue_select_currently_permitted_green(self):
        result=self.resolve();self.assertEqual(result['slot'],'green');self.assertEqual((result['backend_port'],result['frontend_port']),(8201,3200))
        self.assertEqual(result['redis_network'],self.net);self.assertEqual(result['retained_source_sha'],'a'*40)
    def test_both_slots_occupied_never_displaces_or_falls_back_to_blue(self):
        with patch('deployment.lib.active_recovery_candidate.require_unreserved_ports',side_effect=RuntimeError('occupied')):
            with self.assertRaisesRegex(RuntimeError,'occupied'):self.resolve()
        self.assertEqual(self.rt.command.call_args_list[0].args[0],['docker','ps','-a','--format','{{.Names}}'])
        self.assertFalse(any(call.args[0][1] in {'stop','start','rename','update','rm'} for call in self.rt.command.call_args_list))
    def test_target_running_or_wrong_restart_policy_is_not_available(self):
        for change in ('running','restart'):
            row=self.rows['madar-green-backend'];before=copy.deepcopy(row)
            if change=='running':row['State']['Running']=True
            else:row['HostConfig']['RestartPolicy']['Name']='always'
            with self.subTest(change=change),self.assertRaises(RuntimeError):self.resolve()
            self.rows['madar-green-backend']=before
    def test_stale_or_changed_runtime_identity_rejected(self):
        self.rows['madar-green-backend']['Id']='different'
        with self.assertRaisesRegex(RuntimeError,'runtime_changed'):self.resolve()
    def test_changed_transaction_or_ownership_bytes_rejected(self):
        self.paths['worker_authority'].write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'ownership_changed'):self.resolve()
    def test_wrong_network_or_unhealthy_redis_rejected(self):
        self.rt.network.return_value['Internal']=False
        with self.assertRaisesRegex(RuntimeError,'redis_network_invalid'):self.resolve()
    def test_allocation_change_between_preflight_and_staging_rejected(self):
        destination=self.resolve();c=DetachedRecoveryCandidate.__new__(DetachedRecoveryCandidate);c.plan=SimpleNamespace(candidate_destination=destination)
        c.require_free_destinations=Mock();c.slot='green';c.backend_port=8201;c.frontend_port=3200
        with patch('deployment.lib.active_recovery_candidate.resolve_candidate_destination',return_value={**destination,'subnet':'10.253.1.0/24'}):
            with self.assertRaisesRegex(RuntimeError,'plan_changed'):c.require_feasible()
    def test_shared_preflight_and_stage_recheck_use_same_feasibility_method(self):
        import inspect
        self.assertIn('value.require_feasible()',inspect.getsource(DetachedRecoveryCandidate.read_only_feasibility))
        self.assertIn('self.require_feasible()',inspect.getsource(DetachedRecoveryCandidate.stage))
    def test_host_port_busy_and_stopped_docker_reservation_are_both_checked(self):
        # Exercise the real helper, independent of resolver fixture mocks.
        with patch('deployment.lib.active_recovery_candidate.socket.socket') as socket:
            socket.return_value.__enter__.return_value.bind.side_effect=OSError(98,'in use')
            with self.assertRaisesRegex(RuntimeError,'8201_errno_98'):require_unreserved_ports(self.rt,(8201,3200))
        self.rt.command.side_effect=lambda argv:json.dumps([{'HostConfig':{'PortBindings':{'8000/tcp':[{'HostPort':'8201'}]}}}]) if argv[1]=='inspect' else 'id'
        with self.assertRaisesRegex(RuntimeError,'already_reserved'):require_unreserved_ports(self.rt,(8201,3200))

    def test_invalid_recovery_phase_cannot_allocate_even_with_new_file_hash(self):
        path=self.paths['local_transaction'];data=json.loads(path.read_text());data['phase']='normal';path.write_text(json.dumps(data));self.plan.retained_inputs['local_transaction']=file_digest(path)
        with self.assertRaisesRegex(RuntimeError,'ownership_invalid'):self.resolve()
    def test_changed_image_is_rejected_before_port_allocation(self):
        self.rows['madar-green-backend']['Image']='sha256:'+'0'*64
        with self.assertRaisesRegex(RuntimeError,'runtime_changed'):self.resolve()
    def test_staging_is_inside_both_locks_after_allocation_revalidation(self):
        import inspect
        from deployment.lib.active_recovery_resumption import ActiveRecoveryResumption
        source=inspect.getsource(ActiveRecoveryResumption.execute)
        locked=source.split('with self.ops.upgrade_lock(), self.ops.deploy_lock():',1)[1]
        self.assertLess(locked.index('verify_active_rollback_inputs'),locked.index('stage_detached_read_only_candidate'))
        self.assertIn('self.verify_candidate_feasibility(plan)',inspect.getsource(__import__('deployment.lib.active_recovery_operations',fromlist=['ProductionActiveRecoveryOperations']).ProductionActiveRecoveryOperations.stage_detached_read_only_candidate))

    def test_only_exact_retired_nonrestarting_declaration_can_share_free_port(self):
        row=copy.deepcopy(self.rows['madar-green-backend']);row.update(Name='/madar-green-backend-legacy-000000000000')
        row['HostConfig']['PortBindings']={'8000/tcp':[{'HostIp':'127.0.0.1','HostPort':'8201'}]}
        allowed={row['Name'][1:]:{'container_id':row['Id'],'image_id':row['Image'],'spec_sha256':spec(row)}}
        self.rt.command.side_effect=lambda argv:json.dumps([row]) if argv[1]=='inspect' else 'id'
        require_unreserved_ports(self.rt,(8201,3200),allowed)
        for change in ('running','restart','identity','image'):
            altered=copy.deepcopy(row)
            if change=='running':altered['State']['Running']=True
            elif change=='restart':altered['HostConfig']['RestartPolicy']['Name']='always'
            elif change=='identity':altered['Id']='different'
            else:altered['Image']='different'
            self.rt.command.side_effect=lambda argv:json.dumps([altered]) if argv[1]=='inspect' else 'id'
            with self.subTest(change=change),self.assertRaisesRegex(RuntimeError,'already_reserved'):require_unreserved_ports(self.rt,(8201,3200),allowed)
