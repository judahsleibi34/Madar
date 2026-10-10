import unittest
from types import SimpleNamespace
from unittest.mock import patch
from decimal import Decimal
from pydantic import ValidationError
from fastapi import HTTPException
from services import academy_referral_service as service
from services.elearning_settings_service import ELearningSettings


class AcademyReferralServiceTests(unittest.TestCase):
    def test_schema_gate_does_not_call_new_rpc(self):
        with patch.object(service,'settings_available',return_value=False),patch.object(service,'service_supabase') as db:
            self.assertFalse(service.account(SimpleNamespace(tenant_id=3,user_id=7))['available'])
            with self.assertRaises(HTTPException): service.attach(3,7,'code')
            db.rpc.assert_not_called()

    def test_session_identity_is_the_only_balance_authority(self):
        with patch.object(service,'settings_available',return_value=True),patch.object(service,'service_supabase') as db:
            db.rpc.return_value.execute.return_value.data={'available':True}
            self.assertTrue(service.account(SimpleNamespace(tenant_id=3,user_id=7))['available'])
            db.rpc.assert_called_once_with('get_academy_referral_account',{'p_tenant_id':3,'p_user_id':7})

    def test_reward_amount_validation_is_exact_and_bounded(self):
        for values in ({'referral_rewards_enabled':True},{'referral_reward_amount':'1.001'},{'referral_reward_amount':'-1'},{'referral_reward_currency':'usd'},{'referral_reward_currency':'US'},{'referral_reward_amount':'NaN'}):
            with self.subTest(values=values),self.assertRaises(ValidationError):ELearningSettings(**values)
        self.assertEqual(ELearningSettings(referral_rewards_enabled=True,referral_reward_amount='5.25',referral_reward_currency='USD').referral_reward_amount,Decimal('5.25'))
