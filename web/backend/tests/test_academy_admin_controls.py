import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from fastapi import HTTPException
from pydantic import ValidationError
from services import academy_owner_service as service
from services.elearning_settings_service import ELearningSettings

ACTOR = SimpleNamespace(tenant_id=18, user_id=3, role='owner')


class AcademyAdminControlTests(unittest.TestCase):
    def test_controls_wait_for_schema_145_without_calling_the_database(self):
        with patch.object(service, 'settings_available', return_value=False), patch.object(service, 'service_supabase') as db:
            for call in (lambda: service.review_reward(ACTOR, uuid4(), service.RewardReview(decision='earned')),
                         lambda: service.set_tuition_override(ACTOR, 7, service.TuitionOverride(eligible=True, reason='Board decision')),
                         lambda: service.set_institution_verification(ACTOR, 7, service.InstitutionVerification(verified=True)),
                         lambda: service.audit_log(ACTOR)):
                with self.assertRaises(HTTPException) as failure: call()
                self.assertEqual(failure.exception.status_code, 503)
            db.rpc.assert_not_called()

    def test_reasons_are_required_where_the_document_needs_them(self):
        with patch.object(service, 'settings_available', return_value=True), patch.object(service, 'service_supabase') as db:
            with self.assertRaises(HTTPException): service.review_reward(ACTOR, uuid4(), service.RewardReview(decision='rejected', note='  '))
            with self.assertRaises(HTTPException): service.set_tuition_override(ACTOR, 7, service.TuitionOverride(eligible=False, reason='   '))
            db.rpc.assert_not_called()
        with self.assertRaises(ValidationError): service.TuitionOverride(eligible=True)
        with self.assertRaises(ValidationError): service.RewardReview(decision='approved')

    def test_session_identity_is_the_acting_admin(self):
        referral = uuid4()
        with patch.object(service, 'settings_available', return_value=True), patch.object(service, 'service_supabase') as db:
            service.review_reward(ACTOR, referral, service.RewardReview(decision='earned'))
            db.rpc.assert_called_with('academy_review_reward', {'p_tenant': 18, 'p_admin': 3, 'p_referral': str(referral), 'p_decision': 'earned', 'p_note': ''})
            service.set_tuition_override(ACTOR, 7, service.TuitionOverride(eligible=None, reason='Back to automatic'))
            db.rpc.assert_called_with('academy_set_tuition_override', {'p_tenant': 18, 'p_admin': 3, 'p_user': 7, 'p_eligible': None, 'p_reason': 'Back to automatic'})

    def test_reward_review_is_off_by_default(self):
        self.assertFalse(ELearningSettings().referral_reward_review_required)
