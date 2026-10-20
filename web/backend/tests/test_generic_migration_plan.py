"""Source-bound generic plans and read-only policy decisions; no real authority."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest
sys.path.insert(0,os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
import test_generic_migration_source as source_fixture
from deployment.lib.migration_inventory import discover, canonical
from deployment.lib.migration_plan import generate, verify, INTENT_PATH, AUTOMATION_INPUTS
from deployment.lib.migration_risk import scaffold
from deployment.lib.migration_policy import assess, validate_policy


class PlanTests(unittest.TestCase):
    def setUp(self):
        source_fixture.SourceFixture.setUp(self)
        self.intent()
        for relative in AUTOMATION_INPUTS:
            path=self.root/relative; path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('# synthetic reviewed automation input\n')
        self.base=self.commit()
    git=source_fixture.SourceFixture.git
    write=source_fixture.SourceFixture.write
    commit=source_fixture.SourceFixture.commit

    def intent(self,**updates):
        intent={'version':1,'compatible_min':1,'compatible_max':1000,'rolling_compatible':True,
                'worker_protocols':{'delivery':2,'outbox':2,'deletion':2},'declared_class':'A'}
        intent.update(updates)
        path=self.root/INTENT_PATH; path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(canonical(intent))
        return intent

    def plan(self,origin=1):
        sha=self.git('rev-parse','HEAD')
        inventory=discover(self.root,source_sha=sha,history_base_sha=self.base)
        return generate(self.root,inventory,origin=origin),inventory

    def accepted_context(self,plan):
        value=plan.document()
        policy={'version':1,'policy_id':'fixture-only','environment_id':'synthetic-isolated',
            'database_system_identifier':'syntheticcluster','controller_sha':'c'*40,
            'repository':'judahsleibi34/Madar','branch':'refs/heads/main','enabled':True,
            'expires_at':2000,'max_migrations':10,'risk_classes':['A'],
            'automation_inputs_sha256':value['automation_inputs']['sha256']}
        observation={key:policy[key] for key in ('environment_id','database_system_identifier','controller_sha','repository','branch')}
        observation.update({key:value[key] for key in ('source_sha','origin_schema','target_schema','operation_id')})
        observation.update(plan_sha256=plan.sha256,evidence_expires_at=2000,operation_consumed=False,
                           gates={gate:True for gate in value['required_gates']})
        return policy,observation

    def test_multiple_migrations_and_deterministic_canonical_bytes(self):
        self.intent(); self.write(2); self.write(3); self.commit()
        first,inventory=self.plan(); second,_=self.plan()
        self.assertEqual(first.encoded,second.encoded)
        self.assertEqual([m['number'] for m in first.document()['migrations']],[2,3])
        self.assertEqual(first.document()['risk_class'],'A')
        self.assertEqual(verify(self.root,inventory,encoded=first.encoded),first)
        self.assertFalse(first.document()['authority_issued'])

    def test_arbitrary_future_numbers_without_profiles(self):
        for number in range(2,151): self.write(number,b'-- synthetic retained baseline\n')
        self.base=self.commit(); self.intent(); self.write(151); self.write(152); self.commit()
        plan,_=self.plan(origin=150)
        self.assertEqual([m['number'] for m in plan.document()['migrations']],[151,152])
        self.assertEqual(plan.document()['risk_class'],'A')
        self.assertEqual(plan.document()['target_schema'],152)

    def test_application_only_has_no_fake_migration_or_mandatory_backup(self):
        self.intent(); self.commit(); plan,_=self.plan()
        value=plan.document()
        self.assertEqual(value['kind'],'application-only'); self.assertEqual(value['migrations'],[])
        self.assertNotIn('backup_integrity',value['required_gates'])
        self.assertEqual(value['backup_policy'],'policy-dependent')

    def test_manifest_substitution_rejected(self):
        self.intent(); self.write(2); self.commit(); plan,inventory=self.plan()
        for field,bad in (('source_sha','f'*40),('risk_class','B'),('required_gates',[]),('authority_issued',True)):
            altered=plan.document(); altered[field]=bad
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError,'substitution'):
                verify(self.root,inventory,encoded=canonical(altered))
        self.assertRaises(RuntimeError,verify,self.root,inventory,encoded=plan.encoded+b' ')

    def test_declared_class_cannot_lower_ast_risk(self):
        self.intent(declared_class='A'); self.write(2,scaffold(1,2,'DROP TABLE public.example;')); self.commit()
        plan,_=self.plan(); self.assertEqual(plan.document()['risk_class'],'D')
        policy,obs=self.accepted_context(plan)
        result=assess(plan,policy,obs,now=1000)
        self.assertFalse(result['policy_match']); self.assertFalse(result['production_execution_allowed'])

    def test_declared_or_protocol_coordination_escalates(self):
        self.intent(rolling_compatible=False); self.write(2); self.commit()
        plan,_=self.plan(); self.assertEqual(plan.document()['risk_class'],'C')
        self.assertIn('provider_and_worker_quiescence',plan.document()['required_gates'])

    def test_changed_worker_protocol_escalates_without_sql_keyword(self):
        self.intent(worker_protocols={'delivery':2,'outbox':3,'deletion':2})
        self.write(2); self.commit(); plan,_=self.plan()
        self.assertEqual(plan.document()['risk_class'],'C')
        self.assertTrue(plan.document()['worker_protocol_change'])

    def test_missing_compatibility_blocks_even_additive_sql(self):
        (self.root/INTENT_PATH).unlink(); self.write(2); self.commit(); plan,_=self.plan()
        self.assertEqual(plan.document()['risk_class'],'A')
        policy,obs=self.accepted_context(plan)
        self.assertFalse(assess(plan,policy,obs,now=1000)['policy_match'])

    def test_protected_controller_change_requires_independent_upgrade(self):
        self.intent(); self.write(2)
        path=self.root/'web/deployment/lib/example.py'; path.parent.mkdir(parents=True,exist_ok=True); path.write_text('# controller change\n')
        self.commit(); plan,_=self.plan()
        self.assertTrue(plan.document()['protected_control_plane_changed'])
        self.assertIn('protected_control_plane_upgrade',plan.document()['required_gates'])
        policy,obs=self.accepted_context(plan)
        self.assertFalse(assess(plan,policy,obs,now=1000)['policy_match'])

    def test_matching_isolated_policy_never_authorizes_execution(self):
        # The intent itself is a protected path: capture it in the origin's
        # reviewed control-plane baseline before changing only migration SQL.
        self.intent(); self.base=self.commit(); self.write(2); self.commit(); plan,_=self.plan()
        policy,obs=self.accepted_context(plan)
        result=assess(plan,policy,obs,now=1000)
        self.assertTrue(result['policy_match']); self.assertEqual(result['decision'],'PREPARATION_ELIGIBLE')
        self.assertFalse(result['authority_issued']); self.assertFalse(result['production_execution_allowed'])

    def test_every_missing_gate_wrong_identity_expired_artifact_and_replay_blocks(self):
        self.intent(); self.base=self.commit(); self.write(2); self.commit(); plan,_=self.plan()
        policy,obs=self.accepted_context(plan)
        for key in ('environment_id','database_system_identifier','controller_sha','repository','branch','source_sha',
                    'origin_schema','target_schema','operation_id','plan_sha256','evidence_expires_at','operation_consumed'):
            bad=copy.deepcopy(obs); bad.pop(key)
            with self.subTest(key=key): self.assertFalse(assess(plan,policy,bad,now=1000)['policy_match'])
        for gate in plan.document()['required_gates']:
            if gate=='fresh_independent_authority': continue
            bad=copy.deepcopy(obs); del bad['gates'][gate]
            with self.subTest(gate=gate): self.assertFalse(assess(plan,policy,bad,now=1000)['policy_match'])
        for key,badvalue in (('branch','refs/heads/unprotected'),('operation_consumed',True),('evidence_expires_at',999),('origin_schema',True)):
            bad=copy.deepcopy(obs); bad[key]=badvalue
            with self.subTest(key=key): self.assertFalse(assess(plan,policy,bad,now=1000)['policy_match'])

    def test_policy_cannot_expand_to_coordinated_or_destructive_class(self):
        self.intent(); self.base=self.commit(); self.write(2); self.commit(); plan,_=self.plan()
        policy,obs=self.accepted_context(plan)
        for classes in (['A','B'],['A','C'],['D'],[]):
            bad=dict(policy,risk_classes=classes)
            with self.assertRaises(RuntimeError): validate_policy(bad)
        for updates in ({'enabled':False},{'expires_at':999}):
            self.assertFalse(assess(plan,dict(policy,**updates),obs,now=1000)['policy_match'])

    def test_duplicate_json_keys_and_nonfinite_constants_rejected(self):
        from deployment.lib.migration_inventory import strict_json
        for body in ('{"enabled":false,"enabled":true}','{"x":NaN}','{"x":Infinity}'):
            with self.assertRaises(RuntimeError): strict_json(body)
        intent=self.root/INTENT_PATH
        intent.write_text('{"version":1,"version":1}')
        self.write(2); self.commit()
        with self.assertRaisesRegex(RuntimeError,'duplicate_key'): self.plan()

    def test_ci_cannot_approve_changed_workflow_even_after_base_advances(self):
        self.write(2); self.commit(); accepted,_=self.plan()
        policy,_=self.accepted_context(accepted)
        (self.root/'.github/workflows/migration-safety.yml').write_text('# changed verification workflow\n')
        self.base=self.commit()  # moving PR/main base must not renew root policy
        self.write(3); self.commit(); changed,_=self.plan(origin=2)
        self.assertFalse(changed.document()['protected_control_plane_changed'])
        _,obs=self.accepted_context(changed)
        result=assess(changed,policy,obs,now=1000)
        self.assertFalse(result['policy_match'])
        self.assertIn('automation_trust_root_changed',result['reasons'])
        self.assertFalse(result['production_execution_allowed'])

    def test_missing_automation_input_blocks_routine_policy(self):
        (self.root/'web/backend/requirements-migration-tools.txt').unlink()
        self.write(2); self.commit(); plan,_=self.plan()
        policy,obs=self.accepted_context(plan)
        self.assertIn('automation_inputs_incomplete',assess(plan,policy,obs,now=1000)['reasons'])

    def test_malformed_intent_blocks_generation(self):
        self.intent(worker_protocols={'delivery':True}); self.write(2); self.commit()
        with self.assertRaisesRegex(RuntimeError,'intent_invalid'): self.plan()


if __name__=='__main__': unittest.main()
