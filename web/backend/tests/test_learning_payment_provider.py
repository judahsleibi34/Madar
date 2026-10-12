import os
import unittest
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes.elearning_commerce_routes import router
from services import learning_payment_provider as payments


class PaymentBoundaryTests(unittest.TestCase):
    def setUp(self):
        app=FastAPI();app.include_router(router);self.client=TestClient(app)

    def test_unconfigured_webhook_fails_closed_without_payment_writes(self):
        with patch.dict(payments.PROVIDERS, {}, clear=True), patch.dict(os.environ, {'MADAR_PAYMENT_PROVIDER': ''}), patch.object(payments, 'apply_verified_event') as apply:
            self.assertEqual(self.client.post('/elearning/payments/webhook',content=b'{}').status_code,503)
            apply.assert_not_called()

    def test_signature_rejection_cannot_activate_purchase(self):
        provider=MagicMock();provider.configured.return_value=True
        provider.verify_webhook.side_effect=payments.InvalidPaymentSignature()
        with patch.dict(payments.PROVIDERS, {'test_provider':provider}, clear=True), patch.dict(os.environ, {'MADAR_PAYMENT_PROVIDER':'test_provider'}), patch('services.elearning_settings_service.settings_available', return_value=True), patch.object(payments,'apply_verified_event') as apply:
            response=self.client.post('/elearning/payments/webhook',content=b'unsigned event')
            self.assertEqual(response.status_code,400);apply.assert_not_called()
            provider.verify_webhook.assert_called_once()

    def test_only_adapter_verified_event_reaches_existing_atomic_rpc(self):
        event=payments.VerifiedPaymentEvent(tenant_id=7,checkout_id=uuid4(),event_id='verified-event',transaction_id='transaction',sequence=2,state='refunded',amount=Decimal('30.00'),currency='USD')
        provider=MagicMock();provider.configured.return_value=True;provider.verify_webhook.return_value=event
        with patch.dict(payments.PROVIDERS, {'test_provider':provider}, clear=True), patch.dict(os.environ, {'MADAR_PAYMENT_PROVIDER':'test_provider'}), patch('services.elearning_settings_service.settings_available', return_value=True), patch.object(payments,'service_supabase') as db:
            db.rpc.return_value.execute.return_value.data={'success':True}
            self.assertEqual(self.client.post('/elearning/payments/webhook',content=b'verified bytes').status_code,200)
            name,args=db.rpc.call_args.args;self.assertEqual(name,'apply_commerce_payment_event')
            self.assertEqual((args['p_tenant_id'],args['p_state'],args['p_provider'],args['p_amount']),(7,'refunded','test_provider','30.00'))
