import os
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
import app as app_module
from services import storage_delivery_service as delivery
from routes.user_routes import get_storage_public_url, delete_old_avatar_if_storage_url
from routes.auth_callback_routes import allowed_frontend_redirect


class StorageDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app_module.app)
        self.real_client = httpx.Client
        self.calls = []

    def transport(self, status=200, headers=None, body=b'abcdef'):
        def handle(request):
            self.calls.append(request)
            return httpx.Response(status, headers=headers or {'Content-Type': 'image/png', 'Content-Length': str(len(body)), 'ETag': '"fixture"'}, stream=httpx.ByteStream(body))
        return patch.object(delivery.httpx, 'Client', side_effect=lambda **kwargs: self.real_client(transport=httpx.MockTransport(handle), **kwargs))

    def test_avatar_bytes_headers_and_no_provider_redirect(self):
        with self.transport(), patch.dict(os.environ, {'SUPABASE_URL': 'http://madar-supabase:8000', 'SUPABASE_SERVICE_KEY': 'fixture-server-key'}):
            r = self.client.get('/assets/avatars/users/example/photo.png')
        self.assertEqual(r.content, b'abcdef')
        self.assertEqual(r.headers['content-type'], 'image/png')
        self.assertEqual(r.headers['cache-control'], 'public, max-age=3600')
        self.assertEqual(r.headers['etag'], '"fixture"')
        self.assertNotIn('location', r.headers)
        self.assertNotIn('fixture-server-key', str(r.headers))
        self.assertEqual(self.calls[0].url.path, '/storage/v1/object/public/avatars/users/example/photo.png')

    def test_private_range_and_conditionals_are_preserved(self):
        with patch.object(app_module, '_asset_visibility', return_value=(True, True)), self.transport(206, {'Content-Type': 'video/mp4', 'Content-Length': '3', 'Content-Range': 'bytes 1-3/6', 'Accept-Ranges': 'bytes'}, b'bcd'):
            r = self.client.get('/uploads/tenant_999/builder_assets/' + 'a'*32 + '.mp4', headers={'Range': 'bytes=1-3', 'If-Range': '"fixture"'})
        self.assertEqual(r.status_code, 206)
        self.assertEqual(r.content, b'bcd')
        self.assertEqual(r.headers['content-range'], 'bytes 1-3/6')
        self.assertEqual(r.headers['content-type'], 'video/mp4')
        self.assertEqual(r.headers['cache-control'], 'private, no-store')
        self.assertEqual(self.calls[0].headers['range'], 'bytes=1-3')
        self.assertEqual(self.calls[0].headers['if-range'], '"fixture"')

    def test_visibility_denied_never_contacts_storage(self):
        with patch.object(app_module, '_asset_visibility', return_value=(False, False)), self.transport():
            r = self.client.get('/uploads/tenant_999/builder_assets/' + 'a'*32 + '.png')
        self.assertEqual(r.status_code, 404)
        self.assertFalse(self.calls)

    def test_public_bucket_cannot_be_selected_by_client(self):
        with self.transport(404, {'Content-Type': 'application/json'}, b'internal diagnostic'):
            r = self.client.get('/assets/avatars/builder-assets/private.pdf')
        self.assertEqual(r.status_code, 404)
        self.assertIn('/public/avatars/', self.calls[0].url.path)
        self.assertNotIn('internal diagnostic', r.text)

    def test_redirect_and_html_are_not_relayed(self):
        for status, headers in [(307, {'Location': 'http://madar-supabase:8000/secret'}), (200, {'Content-Type': 'text/html'})]:
            with self.transport(status, headers, b'sensitive upstream body'):
                r = self.client.get('/assets/avatars/photo.png')
            self.assertIn(r.status_code, (404, 502))
            self.assertNotIn('location', r.headers)
            self.assertNotIn('sensitive upstream body', r.text)

    def test_head_not_modified_and_unsatisfied_range(self):
        with self.transport():
            r = self.client.head('/assets/avatars/photo.png')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b'')
        self.assertEqual(r.headers['content-length'], '6')
        with self.transport(304, {'ETag': '"fixture"'}, b''):
            r = self.client.get('/assets/avatars/photo.png', headers={'If-None-Match': '"fixture"'})
        self.assertEqual(r.status_code, 304)
        self.assertEqual(self.calls[-1].headers['if-none-match'], '"fixture"')
        with self.transport(416, {'Content-Range': 'bytes */6'}, b'upstream error'):
            r = self.client.get('/assets/avatars/photo.png', headers={'Range': 'bytes=999-'})
        self.assertEqual(r.status_code, 416)
        self.assertEqual(r.headers['content-range'], 'bytes */6')
        self.assertEqual(r.content, b'')

    def test_path_validation_rejects_traversal_and_backslash(self):
        from fastapi import HTTPException
        for value in ('../builder-assets/private', 'users//photo.png', 'users/./photo.png', 'users\\photo.png'):
            with self.assertRaises(HTTPException):
                delivery.validate_object_path(value)

    def test_avatar_url_and_cleanup_preserve_owner_boundary(self):
        with patch.dict(os.environ, {'PUBLIC_API_URL': 'https://api.madarportal.com'}):
            self.assertEqual(get_storage_public_url('avatars', 'users/owner/photo.png'), 'https://api.madarportal.com/assets/avatars/users/owner/photo.png')
        with patch('routes.user_routes.service_supabase') as storage:
            self.assertIsNone(delete_old_avatar_if_storage_url('https://api.madarportal.com/assets/avatars/users/other/photo.png', 'owner'))
            storage.storage.from_.assert_not_called()

    def test_callback_redirect_policy(self):
        with patch.dict(os.environ, {'FRONTEND_PRIMARY_URL': 'https://madarportal.com'}):
            for url in ('https://madarportal.com/verify-email', 'https://madarportal.com/reset-password?request_token=fixture'):
                self.assertTrue(allowed_frontend_redirect(url))
            for url in ('http://madar-supabase:8000', 'https://attacker.example/reset-password', 'https://madarportal.com/anything', 'https://madarportal.com/reset-password?next=https://attacker.example'):
                self.assertFalse(allowed_frontend_redirect(url))
            for query in ('token=fixture&type=recovery&redirect_to=https://attacker.example', 'token=fixture&type=unsupported', 'token=fixture&type=signup&unexpected=1'):
                r = self.client.get('/auth/v1/verify?' + query)
                self.assertEqual(r.status_code, 400)


    def test_streaming_preserves_main_opaque_and_legacy_key_header_compatibility(self):
        for key in ['sb_secret_synthetic_fixture_not_a_credential', 'synthetic-legacy-service-role-jwt']:
            with self.subTest(key_kind='opaque' if key.startswith('sb_secret_') else 'legacy'):
                self.calls=[]
                with self.transport(), patch.dict(os.environ, {'SUPABASE_SERVICE_KEY': key}):
                    response=self.client.get('/assets/avatars/photo.png')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.calls[0].headers['apikey'], key)
                if key.startswith('sb_secret_'):
                    self.assertNotIn('authorization', self.calls[0].headers)
                else:
                    self.assertEqual(self.calls[0].headers['authorization'], 'Bearer '+key)
                self.assertNotIn(key, str(response.headers))


class AuthCallbackTransportTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app_module.app)

    def test_verification_and_recovery_redirect_without_provider_url(self):
        from types import SimpleNamespace
        for kind, path in [('signup', '/verify-email'), ('recovery', '/reset-password?request_token=fixture')]:
            location='https://madarportal.com'+path+'#access_token=synthetic-test-value'
            with patch.dict(os.environ, {'FRONTEND_PRIMARY_URL':'https://madarportal.com','SUPABASE_URL':'http://madar-supabase:8000'}), patch('routes.auth_callback_routes.requests.Session') as session:
                session.return_value.__enter__.return_value.get.return_value=SimpleNamespace(status_code=302,headers={'Location':location})
                r=self.client.get('/auth/v1/verify',params={'token':'synthetic-test-value','type':kind,'redirect_to':'https://madarportal.com'+path},follow_redirects=False)
                call=session.return_value.__enter__.return_value.get.call_args
            self.assertEqual(r.status_code,303)
            self.assertEqual(r.headers['location'],location)
            self.assertEqual(r.headers['cache-control'],'no-store')
            self.assertEqual(r.headers['referrer-policy'],'no-referrer')
            self.assertEqual(call.args[0],'http://madar-supabase:8000/auth/v1/verify')
            self.assertFalse(call.kwargs['allow_redirects'])

    def test_upstream_internal_or_unapproved_redirect_is_rejected(self):
        from types import SimpleNamespace
        for location in ['http://madar-supabase:8000/', 'https://attacker.example/', 'https://madarportal.com/unapproved']:
            with patch.dict(os.environ, {'FRONTEND_PRIMARY_URL':'https://madarportal.com'}), patch('routes.auth_callback_routes.requests.Session') as session:
                session.return_value.__enter__.return_value.get.return_value=SimpleNamespace(status_code=302,headers={'Location':location})
                r=self.client.get('/auth/v1/verify?token=synthetic-test-value&type=signup',follow_redirects=False)
            self.assertEqual(r.status_code,502)
            self.assertNotIn('location',r.headers)
            self.assertNotIn(location,r.text)

    def test_duplicate_callback_parameters_do_not_contact_auth(self):
        with patch('routes.auth_callback_routes.requests.Session') as session:
            r=self.client.get('/auth/v1/verify?token=fixture&token=other&type=signup')
            session.assert_not_called()
        self.assertEqual(r.status_code,400)
