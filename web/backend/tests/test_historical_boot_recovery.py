"""Historical restart contracts with modeled infrastructure; no reboot claim."""
import copy,hashlib,json,tempfile,time,unittest,uuid
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from deployment.lib import automatic_release_recovery as recovery
from deployment.lib import automatic_release_admission as admission
from deployment.lib import historical_origin as origin
from deployment.lib import exceptional_release_approval as approval
from deployment.lib.completed_normal_resources import measured_spec
from deployment.lib.migration_inventory import canonical,digest
import test_historical_origin as origin_fixtures

POLICY_READER=recovery.policy
BOOT_CONTROLS_READER=recovery.require_historical_boot_controls


class HistoricalBootRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.state=self.root/'state';self.state.mkdir();self.journal=self.root/'recovery';self.journal.mkdir()
        self.enterContext(patch.object(recovery,'ROOT',self.journal));self.enterContext(patch.object(recovery,'STATE',self.state))
        self.enterContext(patch.object(admission,'ROOT',self.root/'admissions'))
        self.binding=origin_fixtures.HistoricalPreparationBindingTests().contract()['source_roles']
        self.slot='green';self.source=self.binding['application_sha'];self.controller=self.binding['controller_sha']
        self.worker={'owner':'CANDIDATE','candidate':{'sha':self.source,'slot':self.slot},'generation':'original-generation'}
        self.known={'sha':self.source,'slot':self.slot,'schema':146,'schema_compatible_min':144,'schema_compatible_max':146,
            'worker_generation':self.worker['generation'],'historical_origin':{'enrollment_sha256':self.binding['enrollment_sha256']}}
        self.release={'known_good_release':self.known,'active_slot':self.slot}
        (self.state/'state.json').write_bytes(canonical(self.release));(self.state/'worker-ownership.json').write_bytes(canonical(self.worker))
        route=self.root/'route.conf';route.write_bytes(b'actual original route fixture');self.enterContext(patch.object(recovery,'ROUTE',route))
        self.config={}
        for name,path in (('application','/etc/madar/production.env'),('backup','/etc/madar/backup.env'),('database_transport','/etc/madar/automatic-database.dsn')):
            target=self.root/(name+'.conf');target.write_bytes(('original '+name).encode());self.config[path]=target
        self.enterContext(patch.object(recovery,'protected',lambda p,**kw:Path(p)))
        self.enterContext(patch.object(recovery,'readonly_configuration',lambda p,**kw:self.config.get(str(p),Path(p))))
        self.rows=[];names=[*recovery.PROVIDERS,*['madar-green-'+r for r in recovery.ROLES],'madar-release-proxy','operator-database','operator-auth']
        for n,name in enumerate(names,1):
            self.rows.append({'Id':f'{n:064x}','Name':'/'+name,'Image':'sha256:'+'a'*64,'Config':{'Env':[]},
                'HostConfig':{'RestartPolicy':{'Name':'no'},'Memory':64*1024**2,'NanoCpus':250000000,'PidsLimit':64},'Mounts':[],
                'State':{'Running':True},'NetworkSettings':{'Networks':{'native':{'NetworkID':'b'*64}}}})
        scope={r['Id']:{'name':r['Name'],'image':r['Image'],'spec_sha256':measured_spec(r),'binds':{}} for r in self.rows}
        self.host={'version':2,'guest_uuid':str(uuid.uuid4()),'machine_id':'machine','root_filesystem_uuid':str(uuid.uuid4()),
            'realm_id':'realm','database_system_identifier':'123456789','database_container_id':self.rows[0]['Id'],'runtime_scope':scope}
        self.bootstrap={'phase':'bootstrap_adopted','release_sha':self.source,'schema':{'observed':146}}
        self.original={'source_sha':self.source,'database':{'schema':146,'system_identifier':'123456789','structure_sha256':'c'*64},
            'history_sha256':'d'*64,'bootstrap_sha256':digest(self.bootstrap),'worker_authority':self.worker,
            'configuration_sha256':{k:hashlib.sha256(self.config[p].read_bytes()).hexdigest() for k,p in
                (('application','/etc/madar/production.env'),('backup','/etc/madar/backup.env'),('database_transport','/etc/madar/automatic-database.dsn'))},
            'runtime':{r['Name']:{'id':r['Id'],'image':r['Image'],'spec_sha256':measured_spec(r)} for r in self.rows},
            'runtime_scope_sha256':digest(scope),'independent_operator_scope':{'actor_ids':[self.rows[-2]['Id'],self.rows[-1]['Id']]}}
        self.context={'kind':origin.KIND,'source_binding':self.binding,'request_record':{'payload':{'observation':self.original}},
            'enrollment_record':{'payload':{'expires_at':int(time.time())+3600}},'history':self.original['database']}
        self.p={'version':2,'historical_origin':self.binding,'controller_sha':self.controller,'expires_at':int(time.time())+300}
        self.system=SimpleNamespace(installed_sha=Mock(return_value=self.controller),interlock_file=self.root/'interlock',repo=self.root)
        self.enterContext(patch.object(recovery,'policy',return_value=(self.p,self.host)))
        self.enterContext(patch.object(recovery,'inspect_all',side_effect=lambda:copy.deepcopy(self.rows)))
        self.enterContext(patch.object(recovery,'historical_context',return_value=self.context))
        self.enterContext(patch.object(recovery,'require_historical_boot_controls')) # MODEL systemd; separate exact-unit tests.
        self.enterContext(patch.object(origin,'restored_context',side_effect=lambda *a,**kw:self.original))
        self.enterContext(patch.object(origin,'bootstrap_record',return_value=self.bootstrap))
        self.enterContext(patch.object(origin,'attest',return_value=self.binding))
        self.enterContext(patch.object(origin,'operation_locks',return_value=nullcontext(lambda:None)))
        self.enterContext(patch('deployment.lib.control_plane_upgrade.require_root_directory',lambda p,**kw:Path(p).mkdir(exist_ok=True)))
        from deployment.lib.control_plane_upgrade_authorization import RELEASE_OPERATOR_POLICY
        operator=self.root/'operator.json';operator.write_bytes(canonical({'auth_service':{'id':self.rows[-1]['Id']}}))
        self.enterContext(patch('deployment.lib.control_plane_upgrade_authorization.RELEASE_OPERATOR_POLICY',operator))

    def seal(self):
        recovery.seal_historical_known_good(self.system)
        return recovery.read(self.journal/'known-good.json')

    def test_enrolled_bootstrap_seal_is_neither_completion_nor_write_grant(self):
        with patch.object(recovery,'completed') as completed,patch.object(recovery,'grant') as grant:
            m=self.seal();self.assertEqual(m['kind'],'historical-bootstrap-known-good-recovery')
            for key in ('admission','completion_sha256','authority_sha256'):self.assertNotIn(key,m)
            self.assertEqual(recovery.validate_manifest(self.system)[1],m)
            recovery.historical_restart_authority(self.system,m)
            completed.assert_not_called();grant.assert_not_called()

    def test_restore_hold_never_expires_itself_or_allows_restart(self):
        self.seal();(self.journal/'independent-restore-in-progress.json').write_bytes(canonical({'expired_at':0}))
        with patch.object(recovery,'run') as effect:
            with self.assertRaisesRegex(RuntimeError,'operation_or_restore_pending'):recovery.validate_manifest(self.system)
            effect.assert_not_called()

    def test_interlock_and_consumed_successor_block_legacy_restart(self):
        self.seal();self.system.interlock_file.write_bytes(b'pending protected operation')
        with self.assertRaisesRegex(RuntimeError,'operation_or_restore_pending'):recovery.validate_manifest(self.system)
        self.system.interlock_file.unlink();path=Path(self.binding['enrollment_root']);path.mkdir(parents=True)
        (path/'bootstrap-origin-release-use.json').write_bytes(b'consumed successor')
        with self.assertRaisesRegex(RuntimeError,'operation_or_restore_pending'):recovery.validate_manifest(self.system)

    def test_consumption_binding_crash_gap_cannot_hide_approval_from_boot(self):
        self.seal();request=admission.ROOT/'exceptional'/str(uuid.uuid4());request.mkdir(parents=True)
        key=self.root/'approval.key';key.write_bytes(b'independent unit-test signing key only')
        for name,value in (('approval-consumed.json',{'consumed':True}),('request.json',{'admission':{'kind':approval.CANONICAL_KIND,'contract':{'source_roles':self.binding}}})):
            (request/name).write_bytes(canonical(approval.sign(value,key.read_bytes())))
        with patch.object(approval,'KEY',key),patch.object(approval,'protected',lambda p,**kw:Path(p)):
            with self.assertRaisesRegex(RuntimeError,'consumed_operation_requires_recovery'):recovery.validate_manifest(self.system)

    def test_wrong_database_unknown_actor_and_float_schema_refuse(self):
        m=self.seal();self.host['database_system_identifier']='987654321'
        with self.assertRaisesRegex(RuntimeError,'original_data_changed'):recovery.validate_manifest(self.system)
        self.host['database_system_identifier']='123456789';self.release['known_good_release']['schema']=146.0
        (self.state/'state.json').write_bytes(canonical(self.release))
        with self.assertRaisesRegex(RuntimeError,'owner_or_route_changed'):recovery.validate_manifest(self.system)
        self.release['known_good_release']['schema']=146;(self.state/'state.json').write_bytes(canonical(self.release))
        self.rows.append(dict(self.rows[-1],Id='f'*64,Name='/foreign'))
        with self.assertRaisesRegex(RuntimeError,'historical_runtime_changed'):recovery.historical_restart_authority(self.system,m)

    def test_existing_worker_owner_and_private_configuration_cannot_change(self):
        self.seal();changed=copy.deepcopy(self.worker);changed['owner']='NONE'
        (self.state/'worker-ownership.json').write_bytes(canonical(changed))
        with self.assertRaisesRegex(RuntimeError,'owner_or_route_changed'):recovery.validate_manifest(self.system)
        (self.state/'worker-ownership.json').write_bytes(canonical(self.worker))
        self.config['/etc/madar/automatic-database.dsn'].write_bytes(b'changed database transport')
        with self.assertRaisesRegex(RuntimeError,'configuration_changed'):recovery.validate_manifest(self.system)

    def test_historical_policy_cannot_silently_seal_ordinary_future_releases(self):
        path=self.root/'recovery-policy.json';path.write_bytes(canonical(self.p))
        with patch.object(recovery,'POLICY',path),patch.object(recovery,'completed') as completed:
            with self.assertRaisesRegex(RuntimeError,'completed_policy_required'):recovery.seal_known_good(self.system,{})
            completed.assert_not_called()

    def exercise_recovery(self,*,candidate_failure=False):
        """Real coordinator/locks/journal, modeled Docker/database observations."""
        import os
        from deployment.lib import environment_file,isolated_release_environment
        self.p.update(control_interface='ens3',control_gateway='10.0.2.2',max_recovery_seconds=30);self.seal()
        self.system.upgrade_root=self.root;self.system.control_root=self.root/'installed'
        events=[]
        ids={r['Name'].removeprefix('/'):r['Id'] for r in self.rows}
        def effect(args):
            events.append(('effect',args))
            if args[:3]==['/usr/sbin/ip','-json','route']:return b'[{"gateway":"10.0.2.2"}]'
            if args[:3]==['/usr/sbin/ip','-json','address']:
                return b'[{"addr_info":[{"local":"10.0.2.15","prefixlen":24}]}]'
            self.assertEqual(args[0],'/usr/bin/docker');return b''
        class Operations:
            def __init__(self,*args):pass
            def validate_candidate_core(self,*args):events.append(('core_ready',args))
            def _require_worker_authority(self,*args):events.append(('worker_owner',args))
            def _require_other_worker_slot_inactive(self,*args):events.append(('other_slot_inactive',args))
            def validate_candidate(self,*args):
                events.append(('candidate_ready',args))
                if candidate_failure:raise RuntimeError('controlled_candidate_health_failure')
            def switch_traffic(self,*args):events.append(('route',args))
            def validate_stable_candidate(self,*args):events.append(('stable',args))
        def native(*args):events.append(('database_verified',()));return self.original['database']
        def restart(*args):events.append(('historical_authority',()))
        with patch.object(recovery,'run',side_effect=effect),patch.object(recovery,'verify_fence'),\
                patch.object(recovery,'native',side_effect=native),\
                patch.object(recovery,'historical_restart_authority',side_effect=restart),\
                patch.object(recovery,'recover_historical_operator',side_effect=lambda *a:events.append(('operator_recovered',()))),\
                patch.object(recovery,'grant') as grant,patch.object(recovery,'completed') as completed,\
                patch.object(environment_file,'load_environment_file'),\
                patch.object(isolated_release_environment,'observe',return_value={'control_interface':'ens3'}),\
                patch.dict(os.environ):
            if candidate_failure:
                with self.assertRaisesRegex(RuntimeError,'controlled_candidate_health_failure'):
                    recovery.recover(self.system,Operations)
                result=recovery.read(next(self.journal.glob('boot-*.json')))
            else:result=recovery.recover(self.system,Operations)
            grant.assert_not_called();completed.assert_not_called()
        return events,ids,result

    def test_real_recovery_coordinator_orders_grantless_owner_before_workers_and_traffic(self):
        events,ids,result=self.exercise_recovery()
        self.assertEqual(result['phase'],'healthy')
        self.assertEqual(result['operation'],'historical-known-good-boot-recovery')
        for name in ('deployment_authority_issued','migration_sql_executed','protected_completion_claimed'):
            self.assertIs(result[name],False)
        def index(predicate):return next(i for i,event in enumerate(events) if predicate(event))
        starts=lambda identity: index(lambda e:e==('effect',['/usr/bin/docker','start',identity]))
        database=index(lambda e:e[0]=='database_verified')
        authority=index(lambda e:e[0]=='historical_authority')
        owner=index(lambda e:e[0]=='worker_owner')
        candidate=index(lambda e:e[0]=='candidate_ready')
        self.assertEqual(events[0][1][:4],['/usr/bin/docker','stop','--time','15'])
        self.assertLess(starts(ids['supabase-db']),database)
        self.assertLess(database,starts(ids['supabase-auth']))
        self.assertLess(authority,starts(ids['madar-green-backend']))
        self.assertLess(owner,starts(ids['madar-green-notification-worker']))
        self.assertLess(candidate,starts(ids['madar-release-proxy']))
        self.assertLess(starts(ids['madar-release-proxy']),index(lambda e:e[0]=='route'))
        self.assertEqual(events[-1][0],'stable')

    def test_candidate_failure_fences_original_writers_without_promoting_or_issuing_authority(self):
        events,ids,result=self.exercise_recovery(candidate_failure=True)
        self.assertEqual(result['phase'],'fenced');self.assertEqual(result['error_code'],'controlled_candidate_health_failure')
        self.assertFalse(any(e[0] in {'route','stable'} for e in events))
        self.assertFalse(any(e==('effect',['/usr/bin/docker','start',ids['madar-release-proxy']]) for e in events))
        self.assertEqual(events[-1][1][:4],['/usr/bin/docker','stop','--time','15'])
        self.assertIn(ids['madar-green-notification-worker'],events[-1][1])

    def test_independent_historical_policy_cannot_change_guest_controller_or_schema(self):
        from deployment.lib import active_recovery_inputs
        policy={'version':2,'kind':'isolated-historical-recovery-policy','environment_id':'isolated-realm',
            'guest_uuid':self.host['guest_uuid'],'machine_id':self.host['machine_id'],'root_filesystem_uuid':self.host['root_filesystem_uuid'],
            'controller_sha':self.controller,'controller_tree_sha256':'e'*64,'expires_at':int(time.time())+120,
            'control_interface':'ens3','control_mac':'52:54:00:12:34:56','control_address':'10.0.2.15/24',
            'control_gateway':'10.0.2.2','max_recovery_seconds':120,'historical_origin':self.binding}
        with patch.object(recovery,'read',return_value=policy),patch.object(recovery,'observe_host',return_value=self.host),patch.object(active_recovery_inputs,'controller_tree_digest',return_value='e'*64),patch.object(Path,'read_text',return_value=policy['control_mac']):
            self.assertEqual(POLICY_READER(self.system),(policy,self.host))
            for key,value in (('guest_uuid',str(uuid.uuid4())),('controller_sha','f'*40),('version',True),('kind','isolated-known-good-recovery-policy')):
                old=policy[key];policy[key]=value
                with self.subTest(key=key),self.assertRaises(RuntimeError):POLICY_READER(self.system)
                policy[key]=old
            policy['historical_origin']=dict(self.binding,schema=160)
            with self.assertRaisesRegex(RuntimeError,'source_binding_invalid'):POLICY_READER(self.system)


class HistoricalNetworkBootControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        for name,body in recovery.unit_definitions().items():
            if '/' in name:continue
            (self.root/name).write_text(body);(self.root/name).chmod(0o644)
        (self.root/'madar-release-proxy.service').write_text('[Service]\nExecStart=/original/proxy\n')
        self.barrier_state='active';self.barrier_dropins='';self.reload='no';self.restart_state='inactive'
        def command(label,args):
            if args[1]=='list-unit-files':
                return SimpleNamespace(stdout='\n'.join(n+' enabled enabled' for n in
                    ('madar-isolated-fence.service','madar-known-good-recovery.service','madar-release-proxy.service')))
            name=args[2]
            fields={'FragmentPath':str(self.root/name),'DropInPaths':'','LoadState':'loaded',
                'ActiveState':self.restart_state if name=='madar-known-good-recovery.service' else 'active','UnitFileState':'enabled'}
            if label=='historical_network_barrier':fields.update(DropInPaths=self.barrier_dropins,ActiveState=self.barrier_state,
                SubState='exited',MainPID='0',ControlPID='0',Job='',NeedDaemonReload=self.reload)
            if label=='historical_restart_unit':fields={k:fields[k] for k in ('FragmentPath','DropInPaths','UnitFileState')}|{'NeedDaemonReload':self.reload}
            return SimpleNamespace(stdout='\n'.join(k+'='+v for k,v in fields.items()))
        self.system=SimpleNamespace(command=Mock(side_effect=command))
        self.enterContext(patch.object(origin,'BOOT_UNIT_ROOT',self.root))
        self.enterContext(patch.object(origin,'protected',lambda p,**kw:Path(p)))
        self.enterContext(patch.object(recovery,'protected',lambda p,**kw:Path(p)))
        stat=Path.stat
        def metadata(path,*a,**kw):
            value=stat(path,*a,**kw)
            if path.is_relative_to(self.root):
                values=list(value);values[4]=0;return __import__('os').stat_result(values)
            return value
        self.enterContext(patch.object(Path,'stat',metadata))

    def test_exact_network_barrier_is_not_a_stoppable_application_supervisor(self):
        controls=origin.boot_controls(self.system)
        self.assertNotIn('madar-isolated-fence.service',controls['units'])
        self.assertEqual(set(controls['network_barriers']),{'madar-isolated-fence.service'})
        self.assertIn(str(self.root/'madar-isolated-fence.service'),controls['files'])
        BOOT_CONTROLS_READER(self.system,{'boot_controls':controls})
        # The recovery unit observes itself while running; immutable loaded
        # code/configuration, rather than its transient active state, is pinned.
        self.restart_state='activating';BOOT_CONTROLS_READER(self.system,{'boot_controls':controls})

    def test_missing_inactive_modified_or_overridden_barrier_refuses(self):
        controls=origin.boot_controls(self.system)
        for field,value in (('barrier_state','inactive'),('barrier_dropins','/unreviewed/override.conf'),('reload','yes')):
            old=getattr(self,field);setattr(self,field,value)
            with self.subTest(field=field),self.assertRaisesRegex(RuntimeError,'network_barrier_changed'):
                origin.network_barrier_control(self.system)
            setattr(self,field,old)
        (self.root/'madar-isolated-fence.service').write_text('[Service]\nExecStart=/bin/true\n')
        with self.assertRaisesRegex(RuntimeError,'network_barrier_changed'):BOOT_CONTROLS_READER(self.system,{'boot_controls':controls})

    def test_boot_control_name_alone_cannot_authorize_other_restart_code(self):
        controls=origin.boot_controls(self.system)
        (self.root/'madar-known-good-recovery.service').write_text('[Service]\nExecStart=/unreviewed/code\n')
        with self.assertRaisesRegex(RuntimeError,'restart_unit_changed'):BOOT_CONTROLS_READER(self.system,{'boot_controls':controls})
