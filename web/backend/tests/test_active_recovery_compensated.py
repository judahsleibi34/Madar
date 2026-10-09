"""Post-publication evidence must prove NORMAL entry and revocation as DATA."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from deployment.lib.active_recovery_compensated import validate_history, verify_compensated_binding, EXPECTED_PHASES
from deployment.lib.provider_recovery_runtime import digest


class CompensatedHistoryTests(unittest.TestCase):
    def setUp(self):
        self.plan = SimpleNamespace(digest='a'*64, source_sha='b'*40, source_bundle_sha256='c'*64,
                                   candidate_images={'backend':'sha256:'+'d'*64,'frontend':'sha256:'+'e'*64},acceptance_execution_sha256='f'*64)
        p=self.plan
        self.records={
            'authorization.json':{'operation':'active-local-rollback-resumption','plan_sha256':p.digest,'source_bundle_sha256':p.source_bundle_sha256},
            'events.jsonl':[{'phase':phase,'plan_sha256':p.digest,'observed_at':f'2026-10-09T19:{i:02d}:00+00:00'} for i,phase in enumerate(EXPECTED_PHASES)],
            'installed-controller.json':{'plan_sha256':p.digest,'source_sha':p.source_sha,'source_bundle_sha256':p.source_bundle_sha256,
                'historical_authorization_reused':False,'volatile_credential_reconstructed':False},
            'normal-acceptance.json':{'operation':'actual-normal-runtime-verification','plan_sha256':p.digest,'source_sha':p.source_sha,
                'images':p.candidate_images,'schema':115,'database_restore_performed':False,
                'artifact_acceptance_execution_sha256':p.acceptance_execution_sha256,
                'started_at':'2026-10-09T19:08:20+00:00','finished_at':'2026-10-09T19:08:40+00:00',
                'observations':{key:{'http_status':200,'body':body} for key,body in (
                    ('frontend',{}),('api',{}),('readiness',{'ready':True}),
                    ('recovery',{'restricted':False,'business_writes_enabled':True}),
                    ('version',{'release_sha':p.source_sha,'schema_compatible_min':115,'schema_compatible_max':115}))}},
            'write-boundary.json':{'plan_sha256':p.digest,'source_sha':p.source_sha,'source_bundle_sha256':p.source_bundle_sha256,
                'began_at':'2026-10-09T19:08:10+00:00','customer_database_restore_permitted':False,'normal_writes_may_have_occurred':True},
            'write-authority/authority.json':{'mode':'READ_ONLY','schema':115,'release_sha':p.source_sha},
        }
    def test_actual_normal_then_revocation_is_accepted_as_history(self):
        validate_history(self.plan,self.records)
    def test_pass_summary_without_actual_observations_rejected(self):
        self.records['normal-acceptance.json']={'status':'PASS'}
        with self.assertRaisesRegex(RuntimeError,'execution_not_proven'):validate_history(self.plan,self.records)
    def test_normal_grant_not_revoked_rejected(self):
        self.records['write-authority/authority.json']['mode']='NORMAL'
        with self.assertRaisesRegex(RuntimeError,'not_revoked'):validate_history(self.plan,self.records)
    def test_missing_or_reordered_compensation_rejected(self):
        for phases in (EXPECTED_PHASES[:-1], (*EXPECTED_PHASES[:-2],*reversed(EXPECTED_PHASES[-2:]))):
            records=copy.deepcopy(self.records);records['events.jsonl']=records['events.jsonl'][:len(phases)]
            for row,phase in zip(records['events.jsonl'],phases):row['phase']=phase
            with self.assertRaisesRegex(RuntimeError,'history_invalid'):validate_history(self.plan,records)
    def test_changed_source_image_installation_or_schema_rejected(self):
        changes=(('installed-controller.json','source_sha','f'*40),('normal-acceptance.json','images',{}),
                 ('normal-acceptance.json','schema',116),('installed-controller.json','historical_authorization_reused',True))
        for file,key,value in changes:
            records=copy.deepcopy(self.records);records[file][key]=value
            with self.assertRaises(RuntimeError):validate_history(self.plan,records)
    def test_normal_observations_after_compensation_rejected(self):
        self.records['normal-acceptance.json']['finished_at']='2026-10-09T19:11:00+00:00'
        with self.assertRaisesRegex(RuntimeError,'execution_not_proven'):validate_history(self.plan,self.records)
    def test_changed_security_critical_current_identity_fails_closed(self):
        baseline={'previous_plan_sha256':'a'*64,'controller':'b'*64,'proxy':'c'*64}
        binding={'baseline':baseline,'baseline_sha256':digest(baseline)}
        with patch('deployment.lib.active_recovery_compensated.observe_compensated_state',return_value=baseline):
            self.assertEqual(verify_compensated_binding(binding),baseline)
        for key in ('controller','proxy'):
            changed=dict(baseline,**{key:'d'*64})
            with patch('deployment.lib.active_recovery_compensated.observe_compensated_state',return_value=changed):
                with self.assertRaisesRegex(RuntimeError,'current_state_changed'):verify_compensated_binding(binding)
    def test_unbound_or_modified_contract_rejected_before_runtime_inspection(self):
        with patch('deployment.lib.active_recovery_compensated.observe_compensated_state') as observe:
            for binding in ({}, {'baseline':{},'baseline_sha256':'a'*64}):
                with self.assertRaises(RuntimeError):verify_compensated_binding(binding)
            observe.assert_not_called()

class LifecycleClassificationTests(unittest.TestCase):
    def test_published_compensated_state_never_becomes_original_install(self):
        from deployment.lib.active_recovery_compensated import lifecycle_state
        records={'events.jsonl':[{'phase':'authorized'}]}
        self.assertEqual(lifecycle_state(records),'A_ORIGINAL_RESTRICTED_RECOVERY')
        records['candidate-identities.json']={}
        self.assertEqual(lifecycle_state(records),'B_CANDIDATE_STAGED')
        records['events.jsonl'].append({'phase':'read_only_serving'})
        self.assertEqual(lifecycle_state(records),'C_READ_ONLY_PUBLIC')
        records['installed-controller.json']={}
        self.assertEqual(lifecycle_state(records),'D_CONTROLLER_INSTALLED')
        records['normal-acceptance.json']={}
        self.assertEqual(lifecycle_state(records),'E_NORMAL_ACTIVATED')
        records['events.jsonl'].append({'phase':'restricted_fallback'})
        self.assertEqual(lifecycle_state(records),'F_COMPENSATED_RECOVERY')
        records['events.jsonl'].append({'phase':'normal'})
        records['normal-completion.json']={};records['post-cutover-backup.json']={}
        self.assertEqual(lifecycle_state(records),'E_NORMAL_ACTIVATED')
        records['backup-timers-resumed.json']={}
        self.assertEqual(lifecycle_state(records),'G_COMPLETED_NORMAL')

class RetainedSpecificationTests(unittest.TestCase):
    def test_only_recorded_restart_fence_explains_historical_difference(self):
        from deployment.lib.active_recovery_compensated import historical_retained_spec_matches
        from deployment.lib.emergency_routing_repair import spec
        row={'Id':'a'*64,'Image':'sha256:'+'b'*64,'Config':{'Env':['NONSECRET=fixture']},
             'HostConfig':{'RestartPolicy':{'Name':'unless-stopped','MaximumRetryCount':0}},'Mounts':[],
             'State':{'Running':False}}
        original={'spec_sha256':spec(row)}
        row['HostConfig']['RestartPolicy']['Name']='no'
        fence={'plan_sha256':'c'*64,'database_restore':False,'retained_container_ids':{'backend':row['Id']}}
        self.assertTrue(historical_retained_spec_matches(row,original,fence,'c'*64))
        for field,value in (('Image','changed'),('Id','changed'),('Config',{'Env':['NONSECRET=altered']})):
            changed=copy.deepcopy(row);changed[field]=value
            self.assertFalse(historical_retained_spec_matches(changed,original,fence,'c'*64))
        self.assertFalse(historical_retained_spec_matches(row,original,fence,'d'*64))
        row['State']['Running']=True
        self.assertFalse(historical_retained_spec_matches(row,original,fence,'c'*64))
