"""Restart authority and firewall boundaries, separate from native boot proof."""
import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from deployment.lib import automatic_release_recovery as recovery
from deployment.lib.isolated_release_environment import required_rules
from test_automatic_release_admission import sample


class RecoveryBoundaries(unittest.TestCase):
    def table(self):
        return {'nftables':[
            *[{'chain':{'name':k,'hook':k,'type':'filter','prio':200,'policy':'accept'}} for k in required_rules('ens3',execution=True)],
            *[{'rule':{'chain':k,'expr':v}} for k,values in required_rules('ens3',execution=True).items() for v in values]]}

    def test_early_fence_checks_exact_rule_semantics_without_default_route_or_docker(self):
        with patch.object(recovery,'run',return_value=json.dumps(self.table()).encode()) as run:
            recovery.verify_fence('ens3')
        self.assertEqual(run.call_count,1)
        self.assertEqual(run.call_args.args[0][:3],['/usr/sbin/nft','--stateless','--json'])

    def test_weakened_rule_extra_chain_or_priority_are_not_repaired(self):
        for mutation in ('rule','chain','priority'):
            table=self.table()
            if mutation=='rule':table['nftables'][-1]['rule']['expr'][-1]={'accept':None}
            elif mutation=='chain':table['nftables'].append({'chain':{'name':'foreign'}})
            else:table['nftables'][0]['chain']['prio']=-10
            with self.subTest(mutation=mutation),patch.object(recovery,'run',return_value=json.dumps(table).encode()),self.assertRaisesRegex(RuntimeError,'firewall_tampered'):
                recovery.verify_fence('ens3')

    def test_missing_table_is_atomically_created_but_present_tampering_is_refused(self):
        answers=[json.dumps([{'ifname':'lo'},{'ifname':'ens3'}]).encode(),json.dumps({'nftables':[]}).encode()]
        with patch.object(recovery,'policy',return_value=({'control_interface':'ens3'},{'guest_uuid':'owned'})),patch.object(recovery,'run',side_effect=answers),patch.object(recovery,'verify_fence') as verify,patch.object(recovery.subprocess,'run') as apply:
            result=recovery.restore_isolation(object())
        self.assertFalse(result['authority_issued']);self.assertEqual(verify.call_count,1)
        batch=json.loads(apply.call_args.kwargs['input'])
        self.assertNotIn('delete',str(batch));self.assertEqual(len(batch['nftables']),9)
        answers[1]=json.dumps({'nftables':[{'table':{'family':'inet','name':recovery.TABLE}}]}).encode()
        with patch.object(recovery,'policy',return_value=({'control_interface':'ens3'},{})),patch.object(recovery,'run',side_effect=answers),patch.object(recovery,'verify_fence',side_effect=RuntimeError('tampered')),patch.object(recovery.subprocess,'run') as apply,self.assertRaisesRegex(RuntimeError,'tampered'):
            recovery.restore_isolation(object())
        apply.assert_not_called()

    def test_install_cannot_write_systemd_before_independent_guest_policy_verification(self):
        with patch.object(recovery,'policy',side_effect=RuntimeError('foreign_guest')),patch.object(recovery.os,'open') as create,self.assertRaisesRegex(RuntimeError,'foreign_guest'):
            recovery.install(object())
        create.assert_not_called()

    def test_existing_grant_must_be_exact_normal_scope_and_is_never_reissued(self):
        from deployment.lib.automatic_release_execution import runtime_context
        from deployment.lib.migration_inventory import digest
        value=sample()
        expected={'version':4,'operation':recovery.admission.OPERATION,'operation_id':value['operation_id'],'attempt_id':value['attempt_id'],
            'schema':value['database']['target_schema'],'target_schema':value['database']['target_schema'],
            'release_sha':value['source_sha'],'contract_digest':runtime_context(value),'mode':'NORMAL',
            'controller_sha':value['controller_sha'],'database_system_identifier':value['database']['system_identifier'],
            'plan_sha256':digest(value['plan']),'compatible_min':value['candidate']['compatible_min'],'compatible_max':value['candidate']['compatible_max']}
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'authority.json';p.write_text(json.dumps(expected))
            with patch.object(recovery,'protected',return_value=p),patch('deployment.lib.automatic_release_execution.publish_candidate_grant') as issue:
                self.assertEqual(len(recovery.grant(value)),64)
                for field in ('mode','database_system_identifier','release_sha','attempt_id','controller_sha'):
                    changed=copy.deepcopy(expected);changed[field]='substituted';p.write_text(json.dumps(changed))
                    with self.subTest(field=field),self.assertRaisesRegex(RuntimeError,'normal_authority_changed'):recovery.grant(value)
                issue.assert_not_called()

    def test_unit_order_precedes_network_and_docker_without_unsafe_container_restarts(self):
        units=recovery.unit_definitions()
        self.assertIn('Before=network-pre.target network.target docker.service docker.socket',units['madar-isolated-fence.service'])
        self.assertIn('Requires=madar-isolated-fence.service',units['docker.socket.d/madar-isolated-fence.conf'])
        self.assertIn('--recover-known-good',units['madar-known-good-recovery.service'])
        self.assertNotIn('ConditionPathExists',str(units))
        self.assertNotIn('restart=always',str(units))
        self.assertNotIn('automatic-poll',str(units))

    def test_uncertain_migration_or_candidate_effects_do_not_resume_as_preparation(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(recovery.admission,'ROOT',Path(tmp)),patch.object(recovery,'read',return_value={'attempt_id':'2fa2bc18-a4fb-4e60-8c5b-7ce4acd052d9'}):
            pointer=Path(tmp)/'in-progress.json';pointer.touch()
            root=Path(tmp)/'attempts/2fa2bc18-a4fb-4e60-8c5b-7ce4acd052d9';root.mkdir(parents=True)
            for name in ('migration-execution.json','candidate-runtime.json'):
                p=root/name;p.touch()
                with self.subTest(boundary=name),self.assertRaisesRegex(RuntimeError,'effectful_operation'):recovery.pending_scope({}, {})
                p.unlink()


class ConfigurationBindingTests(unittest.TestCase):
    def test_changed_operator_environment_refuses_before_completed_authority_or_effects(self):
        from types import SimpleNamespace
        from deployment.lib.migration_inventory import digest
        host={'guest_uuid':'own','machine_id':'own','root_filesystem_uuid':'own','realm_id':'own'}
        policy={'trusted':'independent'}
        with tempfile.TemporaryDirectory() as tmp:
            env=Path(tmp)/'production.env';env.write_text('changed bytes')
            manifest={'version':1,'kind':'completed-known-good-recovery','policy_sha256':digest(policy),
                'recovery_controller_sha':'a'*40,'environment':host,'operator_configuration_sha256':'b'*64}
            system=SimpleNamespace(installed_sha=lambda:'a'*40)
            with patch.object(recovery,'policy',return_value=(policy,host)),patch.object(recovery,'read',return_value=manifest),patch.object(recovery,'readonly_configuration',return_value=env),patch.object(recovery,'completed') as complete,patch.object(recovery,'inspect_all') as actors,self.assertRaisesRegex(RuntimeError,'operator_configuration_changed'):
                recovery.validate_manifest(system)
            complete.assert_not_called();actors.assert_not_called()

class ApplicationFailureRecoveryTests(unittest.TestCase):
    def test_attestation_time_alone_is_not_a_different_known_good_identity(self):
        original={'sha':'a'*40,'schema':160,'worker_generation':'b'*64,'images':{'backend':'pinned'},'schema_attested_at':'earlier'}
        self.assertTrue(recovery.same_known_good(original,dict(original,schema_attested_at='later')))
        for change in ({'sha':'c'*40},{'schema':161},{'worker_generation':'c'*64},{'images':{'backend':'foreign'}}):
            with self.subTest(change=change):self.assertFalse(recovery.same_known_good(original,dict(original,**change)))

    def test_app_only_cleanup_allows_abort_but_sql_or_surviving_candidate_refuses(self):
        from deployment.lib.migration_inventory import digest
        value=sample();value['database']['origin_schema']=value['database']['target_schema']=160
        scope={'version':1,'operation':recovery.admission.OPERATION,'attempt_id':value['attempt_id'],
            'admission_sha256':digest(value),'source_sha':value['source_sha'],'operation_id':value['operation_id'],
            'database_system_identifier':value['database']['system_identifier']}
        m={'source_sha':value['origin']['source_sha'],'admission':{'candidate':{'slot':value['origin']['slot']}},
            'history':{'schema':160,'system_identifier':value['database']['system_identifier']},'worker_ownership':{'same':'original'}}
        with tempfile.TemporaryDirectory() as tmp,patch.object(recovery.admission,'ROOT',Path(tmp)),patch.object(recovery.admission,'sealed'),patch.object(recovery.admission,'require_reserved'),patch.object(recovery,'grant') as grant,patch.object(recovery,'inspect_all',return_value=[{'Id':'accepted'}]) as rows:
            root=Path(tmp);(root/'in-progress.json').touch();attempt=root/'attempts'/value['attempt_id'];attempt.mkdir(parents=True)
            prepared=root/value['source_sha'];prepared.mkdir();(prepared/'admission.json').touch()
            runtime=attempt/'candidate-runtime.json';runtime.touch()
            candidate={str(i):{} for i in range(8)}
            def read(path,**kw):
                if path==root/'in-progress.json':return scope
                if path==prepared/'admission.json':return value
                if path==runtime:return candidate
                if path.name=='consumed.json':return {'admission_sha256':digest(value),'source_sha':value['source_sha'],'operation_id':value['operation_id'],'attempt_id':value['attempt_id'],'pid':2,'process_start':'1','boot_id':'2fa2bc18-a4fb-4e60-8c5b-7ce4acd052d9'}
                if path.name=='worker-ownership.json':return m['worker_ownership']
                self.fail(str(path))
            with patch.object(recovery,'read',side_effect=read):
                self.assertEqual(recovery.pending_scope(m,{}),scope)
                grant.assert_called_once_with(value,mode='READ_ONLY')
                rows.return_value=[{'Id':'0'}]
                with self.assertRaisesRegex(RuntimeError,'effectful_operation'):recovery.pending_scope(m,{})
                rows.return_value=[{'Id':'accepted'}]
                value['plan']['migrations']=[{'actual':'SQL'}]
                scope['admission_sha256']=digest(value)
                with self.assertRaisesRegex(RuntimeError,'effectful_operation'):recovery.pending_scope(m,{})


class HistoricalConsumptionTests(unittest.TestCase):
    def test_historical_observation_does_not_relax_live_authority_or_allow_a_living_owner(self):
        import subprocess,sys
        from deployment.lib.migration_inventory import digest
        value=sample()
        # The CI test runner is PID1. Exercise a real supported owner PID rather
        # than relaxing the controller's host-process validation for the test.
        child=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.read(1)'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            record={'admission_sha256':digest(value),'source_sha':value['source_sha'],
                'operation_id':value['operation_id'],'attempt_id':value['attempt_id'],'pid':child.pid,
                'process_start':Path('/proc',str(child.pid),'stat').read_text().split(') ',1)[1].split()[19],
                'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
            with patch.object(recovery,'read',return_value=record),patch.object(recovery.admission,'require_reserved') as live:
                with self.assertRaisesRegex(RuntimeError,'owner_still_running'):recovery.observe_reserved_attempt(value)
                record['boot_id']='2fa2bc18-a4fb-4e60-8c5b-7ce4acd052d9'
                self.assertEqual(recovery.observe_reserved_attempt(value),record);live.assert_not_called()
                record['source_sha']='f'*40
                with self.assertRaisesRegex(RuntimeError,'consumed_attempt_changed'):recovery.observe_reserved_attempt(value)
        finally:
            child.stdin.close();child.wait(timeout=5)


class EarlyRecoverySafetyTests(unittest.TestCase):
    def test_foreign_or_expired_guest_policy_refuses_before_lock_or_journal_creation(self):
        from types import SimpleNamespace
        system=SimpleNamespace(upgrade_root=Path('/unusable'))
        with patch.object(recovery,'policy',side_effect=RuntimeError('unapproved_guest')),patch('deployment.lib.control_plane_upgrade.acquire_lock') as lock,patch.object(recovery,'atomic_json') as publish,self.assertRaisesRegex(RuntimeError,'unapproved_guest'):
            recovery.recover(system,object)
        lock.assert_not_called();publish.assert_not_called()
