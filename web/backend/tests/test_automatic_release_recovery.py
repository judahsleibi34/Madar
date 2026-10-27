"""Restart authority and firewall boundaries, separate from native boot proof."""
import copy,json,tempfile,unittest
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
