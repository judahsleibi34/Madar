"""Operator exception must preserve exact-artifact and all other recovery gates."""
import copy
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from deployment.lib.provider_recovery_phases import (EMERGENCY_MODE, AUTOMATED_AUTH_CHECKS,
    acceptance_gates, preparation_binding, sha256, validate_automated_acceptance)
import test_provider_recovery_phases as phase_fixtures

class EmergencyAcceptanceTests(unittest.TestCase):
    def setUp(self):
        fixtures = phase_fixtures.PhaseTests(); fixtures.setUp()
        self.contract, self.metadata = fixtures.contract, fixtures.metadata
        self.report = copy.deepcopy(fixtures.report)
        self.report.pop("human_evidence")
        self.report["acceptance_mode"] = EMERGENCY_MODE
        self.report["checks"].pop("human_auth")
        self.report["checks"]["automated_auth"] = "PASS"
        now = datetime.now(timezone.utc)
        self.authorization = {"scope":EMERGENCY_MODE,"operator":"Madar production operator",
            "explicitly_authorized":True,"issued_at":now.isoformat(),
            "expires_at":(now+timedelta(hours=4)).isoformat(),
            "preparation_binding":sha256(preparation_binding(self.contract,self.metadata))}
        self.report["operator_authorization_digest"] = sha256(self.authorization)
        self.report["automated_evidence"] = {"source_sha":self.contract.sha,"images":self.contract.images,
            "schema":115,"isolated_fixture":True,"customer_credentials_used":False,
            "sensitive_values_recorded":False,"migrations_executed":False,
            "checks":{key:"PASS" for key in AUTOMATED_AUTH_CHECKS}}

    def validate(self):
        return validate_automated_acceptance(self.contract,self.metadata,self.report,self.authorization)

    def test_explicit_exception_passes_without_claiming_human_auth(self):
        self.assertEqual(len(self.validate()),64)
        self.assertNotIn("human_auth",acceptance_gates(self.report))
        self.assertIn("automated_auth",acceptance_gates(self.report))
        self.assertNotIn("human_evidence",self.report)

    def test_no_default_or_unknown_mode_bypass(self):
        self.assertIn("human_auth",acceptance_gates({}))
        with self.assertRaises(RuntimeError):acceptance_gates({"acceptance_mode":"skip"})
        self.report["human_evidence"]={}
        with self.assertRaises(RuntimeError):self.validate()

    def test_missing_unapproved_expired_or_unbound_authorization_fails(self):
        for key,value in [("scope","other"),("operator","untrusted"),("explicitly_authorized",False),
                ("preparation_binding","0"*64),("expires_at",(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat())]:
            original=copy.deepcopy(self.authorization)
            self.authorization[key]=value;self.report["operator_authorization_digest"]=sha256(self.authorization)
            with self.subTest(key=key),self.assertRaises(RuntimeError):self.validate()
            self.authorization=original
        self.report["operator_authorization_digest"]="0"*64
        with self.assertRaises(RuntimeError):self.validate()

    def test_every_automated_check_must_pass(self):
        for key in AUTOMATED_AUTH_CHECKS:
            self.report["automated_evidence"]["checks"][key]="PENDING"
            with self.subTest(key=key),self.assertRaises(RuntimeError):self.validate()
            self.report["automated_evidence"]["checks"][key]="PASS"

    def test_source_images_schema_credentials_and_migrations_cannot_change(self):
        for key,value in [("source_sha","0"*40),("images",{}),("schema",116),
                ("isolated_fixture",False),("customer_credentials_used",True),
                ("sensitive_values_recorded",True),("migrations_executed",True)]:
            original=copy.deepcopy(self.report["automated_evidence"])
            self.report["automated_evidence"][key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):self.validate()
            self.report["automated_evidence"]=original

    def test_expired_issuance_does_not_break_already_authorized_runtime_rollback(self):
        issued = datetime.now(timezone.utc)-timedelta(hours=2)
        self.authorization.update(issued_at=issued.isoformat(), expires_at=(issued+timedelta(hours=1)).isoformat())
        self.report["operator_authorization_digest"]=sha256(self.authorization)
        with self.assertRaises(RuntimeError): self.validate()
        self.assertEqual(len(validate_automated_acceptance(self.contract,self.metadata,self.report,self.authorization,
            authorized_at=(issued+timedelta(minutes=30)).isoformat())),64)

    def test_other_activation_gates_remain_required(self):
        self.assertEqual(acceptance_gates(self.report)-{"automated_auth"},acceptance_gates({})-{"human_auth"})

if __name__=="__main__":unittest.main()
