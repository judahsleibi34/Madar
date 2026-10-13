"""Disabling programme activity must not hide authorized historical evidence."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from routes import academy_programme_routes as routes
from services import academy_programme_service as service

class AcademyFinanceReadAccessTests(unittest.TestCase):
    def setUp(self):
        self.actor = SimpleNamespace(tenant_id=17, user_id=9, role='owner')
        self.db = MagicMock()
        self.db.rpc.return_value.execute.return_value.data = {'items': []}
        for target, name, kwargs in [(routes, 'owner', {'return_value': self.actor}), (service, 'settings_available', {'return_value': True}), (service, 'require_capability', {}), (service, 'get_settings', {'return_value': {'programmes_enabled': False}}), (service, 'service_supabase', {'new': self.db})]:
            helper = patch.object(target, name, **kwargs)
            helper.start(); self.addCleanup(helper.stop)
        app = FastAPI(); app.include_router(routes.router); self.client = TestClient(app)

    def test_history_reads_remain_available_with_programmes_disabled(self):
        for kind in ['transactions', 'referrals', 'rewards']:
            with self.subTest(kind=kind):
                response = self.client.get(f'/elearning/programmes/finance/{kind}?limit=25&offset=50')
                self.assertEqual(response.status_code, 200)
                self.db.rpc.assert_called_with('academy_owner_finance', {'p_tenant':17,'p_admin':9,'p_kind':kind,'p_limit':25,'p_offset':50})

    def test_entitlement_and_schema_denials_still_precede_history_reads(self):
        for status in [402, 403]:
            with patch.object(service, 'require_capability', side_effect=HTTPException(status)), self.subTest(status=status):
                self.assertEqual(self.client.get('/elearning/programmes/finance/transactions').status_code, status)
        with patch.object(service, 'settings_available', return_value=False):
            self.assertEqual(self.client.get('/elearning/programmes/finance/transactions').status_code, 503)
        self.db.rpc.assert_not_called()

    def test_non_owners_cannot_read_finance(self):
        with patch.object(routes, 'owner', side_effect=HTTPException(403)):
            self.assertEqual(self.client.get('/elearning/programmes/finance/transactions').status_code, 403)
        self.db.rpc.assert_not_called()

    def test_disabled_programmes_still_block_business_actions(self):
        with self.assertRaises(HTTPException) as caught:
            service.programme_rpc('academy_request_withdrawal', self.actor)
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(caught.exception.detail['code'], 'academy_programmes_disabled')
        self.db.rpc.assert_not_called()

    def test_admin_record_reads_remain_tenant_scoped_and_learner_reads_stay_blocked(self):
        service.records(self.actor, 'academy_withdrawals', admin=True, limit=25, offset=50)
        self.db.table.return_value.select.return_value.eq.assert_called_with('tenant_id', 17)
        with self.assertRaises(HTTPException):
            service.records(SimpleNamespace(tenant_id=17,user_id=11,role='learner'), 'academy_withdrawals')
