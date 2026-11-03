"""Root-policy/real-signature component tests; filesystem trust is modeled."""
import copy
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from deployment.lib import automatic_release_admission as admission
import test_automatic_release_admission as fixtures


class ExecutionPolicyConfigurationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.file=Path(temp.name)/'policy.json'
        self.enterContext(patch.object(admission,'EXECUTION_POLICY',self.file))
        self.enterContext(patch.object(admission,'protected',lambda p,**kw:p))
        self.enterContext(patch.object(admission.os,'geteuid',return_value=0))
        self.enterContext(patch('deployment.lib.active_recovery_inputs.controller_tree_digest',return_value='a'*64))
        self.ops=SimpleNamespace(installed_sha=lambda:'b'*40)
        self.policy={'version':1,'enabled':True,'environment':'isolated-test','environment_id':'isolated-fixture',
            'controller_sha':'b'*40,'controller_tree_sha256':'a'*64,'test_public_key_sha256':'c'*64,
            'test_runner_sha256':'d'*64,'test_commands_sha256':'e'*64,'evidence_max_age_seconds':600,
            'operation_max_seconds':900,'recovery_max_age_seconds':86400,'denied_database_identifiers':['123']}

    def read(self,p):
        self.file.write_text(json.dumps(p))
        return admission.execution_policy_configuration(self.ops)

    def test_legacy_policy_unchanged_and_new_budget_never_implicit(self):
        self.assertEqual(self.read(self.policy),self.policy)
        with self.assertRaises(RuntimeError):
            self.read(dict(self.policy,physical_recovery_max_age_seconds=1800))
        with self.assertRaises(RuntimeError):self.read(dict(self.policy,version=2))

    def test_explicit_v2_is_bounded_and_does_not_extend_ephemeral_observations(self):
        p=dict(self.policy,version=2,physical_recovery_max_age_seconds=1800)
        self.assertEqual(self.read(p),p)
        for value in (False,0,-1,3601,1800.0,'1800'):
            with self.subTest(value=value),self.assertRaises(RuntimeError):
                self.read(dict(p,physical_recovery_max_age_seconds=value))
        for change in ({'evidence_max_age_seconds':601},{'recovery_max_age_seconds':900},
                       {'version':3},{'environment':'production'},{'controller_sha':'f'*40}):
            with self.subTest(change=change),self.assertRaises(RuntimeError):self.read(p|change)


class PhysicalAcceptanceAgeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.PhysicalRecoveryAdmissionTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups);f=self.fixture;now=int(time.time())
        f.receipt.update(received_at=now-1000,accepted_at=now-900)
        f.trust.update(backup_earliest_at=now-1200,expires_at=now+200)
        f.policy['recovery_max_age_seconds']=86400
        f.seal_receiver()

    def test_v1_stays_stale_but_explicit_v2_accepts_valid_physical_receipt(self):
        f=self.fixture
        with self.assertRaisesRegex(RuntimeError,'physical_recovery_stale'):
            admission.independent_evidence('a'*40,f.policy)
        f.policy.update(version=2,physical_recovery_max_age_seconds=1800)
        self.assertEqual(admission.independent_evidence('a'*40,f.policy),f.payload)
        self.assertEqual(f.policy['evidence_max_age_seconds'],300)

    def test_v2_does_not_extend_receiver_expiry_or_old_physical_acceptance(self):
        f=self.fixture;f.policy.update(version=2,physical_recovery_max_age_seconds=1800)
        f.trust['expires_at']=int(time.time())-1;f.seal_receiver()
        with self.assertRaisesRegex(RuntimeError,'physical_recovery_root_binding_invalid'):
            admission.independent_evidence('a'*40,f.policy)
        f.trust['expires_at']=int(time.time())+200
        f.receipt.update(accepted_at=int(time.time())-1900,received_at=int(time.time())-2000)
        f.trust['backup_earliest_at']=int(time.time())-2100;f.seal_receiver()
        with self.assertRaisesRegex(RuntimeError,'physical_recovery_stale'):
            admission.independent_evidence('a'*40,f.policy)

    def test_v2_does_not_extend_source_ci_staging_observation_freshness(self):
        f=self.fixture;f.policy.update(version=2,physical_recovery_max_age_seconds=1800)
        f.payload['observed_at']=int(time.time())-400;f.publish()
        with self.assertRaisesRegex(RuntimeError,'scope_or_freshness'):
            admission.independent_evidence('a'*40,f.policy)

    def test_v2_still_requires_authentic_receiver_bytes_and_identity(self):
        f=self.fixture;f.policy.update(version=2,physical_recovery_max_age_seconds=1800)
        packet=copy.deepcopy(f.trust['receipt']);packet['payload']['receiver_id']='00000000-0000-0000-0000-000000000000'
        f.trust['receipt']=packet
        from deployment.lib.migration_inventory import canonical,digest
        sha=digest(packet);f.trust['receipt_sha256']=sha
        (f.root/(sha+'.json')).write_bytes(canonical(f.trust))
        f.payload['gates']['recovery']['receipt_sha256']=sha;f.publish()
        with self.assertRaisesRegex(RuntimeError,'receiver_signature_invalid'):
            admission.independent_evidence('a'*40,f.policy)


if __name__=='__main__':unittest.main()
