import os
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from uuid import uuid4
from pydantic import ValidationError
from services import elearning_commerce_service as service
from fastapi import HTTPException


class LearningCommerceModelsTests(unittest.TestCase):
    def test_nine_independent_billing_scope_combinations(self):
        for billing in ('one_time', 'monthly', 'yearly'):
            for scope in ('single_course', 'selected_courses', 'all_courses'):
                plan = service.Plan(name='Access',billing_type=billing,access_scope=scope,amount='49.00',currency='USD',course_ids=[] if scope=='all_courses' else [uuid4()])
                self.assertEqual(plan.billing_type,billing)

    def test_price_scope_and_forged_checkout_fields_rejected(self):
        for scope, ids in [('single_course',[]),('all_courses',[uuid4()]),('selected_courses',[])]:
            with self.assertRaises(ValidationError): service.Plan(name='Access',billing_type='one_time',access_scope=scope,amount='49',currency='USD',course_ids=ids)
        for amount in ['0','-1','49.001']:
            with self.assertRaises(ValidationError): service.Plan(name='Access',billing_type='one_time',access_scope='all_courses',amount=amount,currency='USD')
        for field,value in [('amount',1),('currency','USD'),('tenant_id',3),('user_id',1),('access_scope','all_courses')]:
            with self.assertRaises(ValidationError): service.Checkout(offering_id=uuid4(),idempotency_key=uuid4(),**{field:value})

    def test_local_adapter_cannot_enable_on_production_or_hosted_database(self):
        good={'APP_ENV':'development','MADAR_LOCAL_COMMERCE_ADAPTER':'true','SUPABASE_DB_URL':'postgresql://localhost:54322/postgres','SUPABASE_URL':'http://127.0.0.1:54321'}
        with patch.dict(os.environ,good,clear=True): self.assertTrue(service.local_adapter_enabled())
        for changes in [{'APP_ENV':'production'},{'MADAR_LOCAL_COMMERCE_ADAPTER':'false'},{'SUPABASE_DB_URL':'postgresql://hosted.example:54322/postgres'},{'SUPABASE_DB_URL':'postgresql://localhost:5432/postgres'},{'SUPABASE_URL':'https://hosted.example'}]:
            with patch.dict(os.environ,{**good,**changes},clear=True): self.assertFalse(service.local_adapter_enabled())

    def test_local_payment_cannot_reuse_another_learners_checkout(self):
        actor = SimpleNamespace(tenant_id=3,user_id=1)
        with patch.object(service,'adapter'), patch.object(service,'account',return_value={'checkouts':[],'entitlements':[]}):
            with self.assertRaises(HTTPException) as caught:
                service.simulate(actor,uuid4(),service.LocalEvent(state='paid'),None)
            self.assertEqual(caught.exception.status_code,404)

    def test_account_reads_use_session_identity_and_fail_before_upgrade(self):
        actor = SimpleNamespace(tenant_id=3,user_id=1)
        with patch.object(service,'settings_available',return_value=True), patch.object(service,'player_call',return_value={'checkouts':[],'entitlements':[]}) as rpc, patch.object(service,'get_settings',return_value={}):
            service.account(actor)
            rpc.assert_called_once_with('get_commerce_learning_account',actor)
        with patch.object(service,'settings_available',return_value=False), patch.object(service,'player_call') as rpc:
            with self.assertRaises(HTTPException) as caught:service.account(actor)
            self.assertEqual(caught.exception.status_code,503);rpc.assert_not_called()
