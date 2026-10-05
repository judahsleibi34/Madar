import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import HTTPException
from pydantic import ValidationError
from services import elearning_credentials_service as service
from services.credential_pdf_service import render_certificate

class CredentialServiceTests(unittest.TestCase):
    def test_placeholder_validation_and_no_client_image_snapshot(self):
        design=dict(name='Standard',title='Certificate',issuer_name='Academy',body='{{learner_name}} {{course_name}} {{completion_date}} {{issue_date}} {{issuer_name}} {{credential_id}}')
        service.TemplateDesign(**design)
        for body in ('{{secret}}','{{ learner_name','{{__import__("os")}}'):
            with self.assertRaises(ValidationError):service.TemplateDesign(**{**design,'body':body})
        with self.assertRaises(ValidationError):service.TemplateDesign(**design,logo_image='forged')

    def test_admin_defaults_reuse_saved_learning_branding(self):
        with patch.object(service,'call',return_value={'templates':[]}),patch.object(service,'get_settings',return_value={'primary_display_name':'Existing Organization','logo_url':'/uploads/tenant_3/builder_assets/logo.png'}):
            data=service.admin(SimpleNamespace(tenant_id=3,user_id=1))
            self.assertEqual(data['branding']['issuer_name'],'Existing Organization')
            self.assertTrue(data['branding']['logo_url'].startswith('/uploads/tenant_3/'))

    def test_public_invalid_token_does_not_query_private_data(self):
        with patch.object(service,'call') as call:
            self.assertIsNone(service.verification('123'));self.assertIsNone(service.verification('a'*63));call.assert_not_called()

    def test_schema_gate_and_identity_are_server_supplied(self):
        with patch.object(service,'settings_available',return_value=False):
            with self.assertRaises(HTTPException) as caught:service.mine(SimpleNamespace(tenant_id=3,user_id=1))
            self.assertEqual(caught.exception.status_code,503)
        with patch.object(service,'call',return_value={}) as call:
            service.mine(SimpleNamespace(tenant_id=3,user_id=1),'test')
            call.assert_called_once_with('get_elearning_my_certificates',p_tenant_id=3,p_user_id=1,p_id='test')

    def test_managed_image_only_and_presentation_whitelist(self):
        with self.assertRaises(HTTPException):service.image_snapshot(3,'https://example.com/logo.png')
        row={'snapshot':{'learner_name':'Original','course_name':'Course','design':{'title':'{{learner_name}}','issuer_name':'Academy'}},'completed_at':'2026-01-01','issued_at':'2026-01-02','credential_number':'MDR-X','verification_token':'a'*64,'status':'active','user_id':99,'completion_id':'private'}
        data=service.presentation(row)
        self.assertNotIn('user_id',data);self.assertNotIn('completion_id',data);self.assertEqual(data['design']['title'],'Original')
        self.assertTrue(data['verification_url'].endswith('/verify/credential/'+'a'*64))

    def test_pdf_real_landscape_unicode_and_qr(self):
        data=dict(learner_name='محمد أحمد',course_name='دورة التعلم',completion_date='2026-01-01',issue_date='2026-01-02',credential_number='MDR-TEST',status='active',verification_url='https://example.com/verify/credential/'+'a'*64,design={'issuer_name':'أكاديمية الاختبار','title':'شهادة إتمام','body':'أتم المتعلم جميع متطلبات الدورة','signer_name':'المدير'})
        pdf=render_certificate(data);self.assertTrue(pdf.startswith(b'%PDF'))
        import re
        media = re.search(rb'/MediaBox \[ 0 0 ([\d.]+) ([\d.]+) \]', pdf)
        self.assertIsNotNone(media)
        self.assertGreater(float(media[1]),float(media[2]))
        self.assertIn(b'/Subtype /Image',pdf)
