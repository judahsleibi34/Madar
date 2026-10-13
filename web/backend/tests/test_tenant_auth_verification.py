import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import HTTPException, Response
from routes import public_site_routes as routes
from services.academy_auth_service import verification_redirect

class ProviderError(Exception):
    def __init__(self, code):
        super().__init__('private provider diagnostic')
        self.code = code

class TenantVerificationTests(unittest.TestCase):
    def login_error(self, code):
        with patch.object(routes, 'resolve_website_settings', return_value={'tenant_id':1}), patch.object(routes, 'resolve_tenant_id', return_value=1), patch.object(routes, 'enforce_auth_rate_limit'), patch.object(routes.supabase.auth, 'sign_in_with_password', side_effect=ProviderError(code)):
            with self.assertRaises(HTTPException) as result:
                routes.login_tenant_account('academy', SimpleNamespace(email='learner@example.com',password='test-password'), SimpleNamespace(),Response())
            return result.exception

    def test_unconfirmed_email_has_safe_actionable_error(self):
        error=self.login_error('email_not_confirmed')
        self.assertEqual(error.status_code,403)
        self.assertEqual(error.detail['code'],'email_not_verified')
        self.assertNotIn('private provider',str(error.detail))

    def test_other_provider_failures_do_not_disclose_diagnostics(self):
        error=self.login_error('invalid_credentials')
        self.assertEqual(error.status_code,401)
        self.assertEqual(error.detail,'Invalid email or password')

    def test_allowlisted_local_verification_returns_to_its_academy(self):
        with patch.dict(os.environ,{'APP_ENV':'development','FRONTEND_URL':'http://127.0.0.1:5180','FRONTEND_URLS':'http://127.0.0.1:5180'}):
            result=verification_redirect('academy',SimpleNamespace(headers={'origin':'http://127.0.0.1:5180'}),'/academy/academy/dashboard')
        self.assertEqual(result,'http://127.0.0.1:5180/academy/academy/login?returnTo=%2Facademy%2Facademy%2Fdashboard')

    def test_untrusted_origin_cannot_change_verification_destination(self):
        with patch.dict(os.environ,{'APP_ENV':'development','FRONTEND_URL':'http://127.0.0.1:5180','FRONTEND_URLS':'http://127.0.0.1:5180'}):
            result=verification_redirect('academy',SimpleNamespace(headers={'origin':'https://evil.example'}),'/academy/academy/dashboard')
        self.assertTrue(result.startswith('https://academy.'))
        self.assertNotIn('evil.example',result)

    def test_production_keeps_canonical_tenant_host(self):
        with patch.dict(os.environ,{'APP_ENV':'production','FRONTEND_URL':'http://127.0.0.1:5180','FRONTEND_URLS':'http://127.0.0.1:5180'}):
            result=verification_redirect('academy',SimpleNamespace(headers={'origin':'http://127.0.0.1:5180'}),'/academy/academy/dashboard')
        self.assertTrue(result.startswith('https://academy.'))
        self.assertTrue(result.endswith('/academy/login?returnTo=%2Facademy%2Fdashboard'))

    def test_disabled_tenant_policy_confirms_existing_learner_after_valid_password(self):
        from unittest.mock import MagicMock
        verified_user=SimpleNamespace(id='auth-1',email_confirmed_at='2026-10-13T00:00:00Z')
        session=SimpleNamespace(access_token='access',refresh_token='refresh')
        query=MagicMock()
        query.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data=[{'id':11,'auth_id':'auth-1','tenant_id':1}]
        service=MagicMock()
        service.table.return_value=query
        provider=ProviderError('email_not_confirmed')
        with patch.object(routes,'service_supabase',service),patch.object(routes,'resolve_website_settings',return_value={'tenant_id':1}),patch.object(routes,'resolve_tenant_id',return_value=1),patch.object(routes,'enforce_auth_rate_limit'),patch.object(routes.supabase.auth,'sign_in_with_password',side_effect=[provider,SimpleNamespace(user=verified_user,session=session)]) as sign_in,patch.object(routes,'get_tenant_staff_membership',return_value={'role':'learner','status':'active'}),patch.object(routes,'get_local_user_by_auth_id',return_value={'id':11,'auth_id':'auth-1','tenant_id':1}),patch.object(routes,'synchronize_verified_account',return_value=({'id':11,'auth_id':'auth-1','tenant_id':1},True)),patch.object(routes,'set_auth_cookies',return_value='csrf'):
            result=routes.login_tenant_account('academy',SimpleNamespace(email='learner@example.com',password='correct-password'),SimpleNamespace(),Response(),allow_learning_membership=True,email_verification_required=False)
        self.assertTrue(result['logged_in'])
        self.assertEqual(sign_in.call_count,2)
        service.auth.admin.update_user_by_id.assert_called_once_with('auth-1',{'email_confirm':True})

    def test_required_policy_never_admin_confirms_pending_identity(self):
        service=SimpleNamespace(auth=SimpleNamespace(admin=SimpleNamespace(update_user_by_id=unittest.mock.Mock())))
        with patch.object(routes,'service_supabase',service),patch.object(routes,'resolve_website_settings',return_value={'tenant_id':1}),patch.object(routes,'resolve_tenant_id',return_value=1),patch.object(routes,'enforce_auth_rate_limit'),patch.object(routes.supabase.auth,'sign_in_with_password',side_effect=ProviderError('email_not_confirmed')):
            with self.assertRaises(HTTPException) as result:
                routes.login_tenant_account('academy',SimpleNamespace(email='learner@example.com',password='password'),SimpleNamespace(),Response(),email_verification_required=True)
        self.assertEqual(result.exception.detail['code'],'email_not_verified')
        service.auth.admin.update_user_by_id.assert_not_called()
