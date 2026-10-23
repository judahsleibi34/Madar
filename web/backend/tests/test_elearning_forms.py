"""Learning schema/server validation and independent persistence boundaries."""
import asyncio,json,unittest,io,csv
from types import SimpleNamespace
from unittest.mock import MagicMock,patch
from uuid import uuid4
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers
from services import elearning_forms_service as service
from pydantic import ValidationError


def schema():
    return {'title':'Student feedback','sections':[{'id':'page','title':'Page','fields':[{'id':'student','type':'radio','label':'Student?','options':['Yes','No'],'required':True},{'id':'university','type':'shortText','label':'University','required':True}]}],'logicRules':[{'sourceFieldId':'student','targetFieldId':'university','operator':'equals','action':'show','value':'Yes'}],'access':'public'}

class LearningFormValidationTests(unittest.TestCase):
    def test_bilingual_labels_do_not_change_canonical_answers_or_logic(self):
        value=schema();value.update(languageMode='bilingual',defaultLanguage='ar',localized={'title':{'ar':'ملاحظات الطالب'}})
        value['sections'][0]['fields'][0]['localized']={'label':{'ar':'هل أنت طالب؟'},'options':{'ar':['نعم','لا']}}
        service.Definition(name='Bilingual feedback',schema=value)
        self.assertEqual(service.clean_answers(value,{'student':'No'}),{'student':'No'})
        with self.assertRaises(HTTPException):service.clean_answers(value,{'student':'لا'})
        value['sections'][0]['fields'][0]['localized']['options']['ar']=['نعم']
        with self.assertRaises(ValidationError):service.Definition(name='Invalid choices',schema=value)

    def test_translation_metadata_cannot_alter_authorization_or_accept_unknown_languages(self):
        for localized in [{'access':{'ar':'public'}},{'title':{'fr':'Untrusted'}},{'title':{'ar':{'html':'unsafe'}}}]:
            with self.assertRaises(ValidationError):service.Definition(name='Invalid',schema={**schema(),'localized':localized})

    def test_hidden_required_answers_are_removed_and_cannot_influence_nested_logic(self):
        self.assertEqual(service.clean_answers(schema(),{'student':'No','university':'Injected'}),{'student':'No'})
        with self.assertRaises(HTTPException):service.clean_answers(schema(),{'student':'Yes'})
        self.assertEqual(service.clean_answers(schema(),{'student':'Yes','university':'University'}),{'student':'Yes','university':'University'})
    def test_invalid_options_unknown_fields_and_bad_schema_rejected(self):
        for answers in [{'student':'Other'},{'student':'No','unknown':'value'}]:
            with self.assertRaises(HTTPException):service.clean_answers(schema(),answers)
        for mutation in [lambda s:s['sections'][0]['fields'][0].update(type='script'),lambda s:s['logicRules'][0].update(sourceFieldId='university'),lambda s:s['sections'][0]['fields'][0].update(type=[]),lambda s:s.update(connectedCollectionId='builder')]:
            s=schema();mutation(s)
            with self.assertRaises(ValidationError):service.Definition(name='Form',schema=s)
    def test_supported_types_and_validation_limits(self):
        values={'shortText':'answer','paragraph':'long answer','email':'student@example.com','phone':'+972 555123456','number':'2.5','dropdown':'Yes','radio':'Yes','checkboxes':['Yes'],'date':'2026-10-11','file':{'id':str(uuid4()),'name':'document.pdf','size':10,'type':'application/pdf'}}
        for t,value in values.items():
            field={'id':'f','type':t,'label':'Field','options':['Yes','No']};service.validate_value(field,value)
        for field,value in [({'type':'number','validation':{'max':2}},'3'),({'type':'number'},'NaN'),({'type':'date'},'2026-02-30'),({'type':'email'},'bad'),({'type':'shortText','validation':{'minLength':4}},'abc')]:
            with self.assertRaises(ValueError):service.validate_value(field,value)
    def test_export_preserves_snapshot_and_rejects_overflow(self):
        actor=SimpleNamespace(tenant_id=1,user_id=9)
        record={'id':'r','form_id':'f','version':1,'submitted_at':'now','user_id':None,'answers':{'student':'No'}}
        with patch.object(service,'gate'),patch.object(service,'responses',return_value={'items':[record],'has_more':False}),patch.object(service,'definition',return_value={'schema':schema()}) as definition:
            exported=list(csv.DictReader(io.StringIO(service.export_csv(actor,{}))))
            self.assertEqual(json.loads(exported[0]['schema_snapshot']),schema());definition.assert_called_once_with(1,'f',1)
        with patch.object(service,'gate'),patch.object(service,'responses',return_value={'items':[],'has_more':True}):
            with self.assertRaises(HTTPException) as error:service.export_csv(actor,{})
            self.assertEqual(error.exception.status_code,413)
    def test_file_defaults_cannot_claim_an_upload(self):
        s=schema();s['sections'][0]['fields'].append({'id':'file','type':'file','label':'File','defaultValue':{'id':str(uuid4()),'name':'document.pdf','size':10,'type':'application/pdf'}})
        with self.assertRaises(ValidationError):service.Definition(name='Form',schema=s)
    def test_public_and_authenticated_access_enforces_plan_and_identity(self):
        f={'status':'active','schema':schema()}
        with patch.object(service,'gate'),patch.object(service,'require_entitlement'),patch.object(service,'rpc',return_value=False):
            service.public_access(1,f,None)
            f['schema']['access']='authenticated'
            with self.assertRaises(HTTPException):service.public_access(1,f,None)
            with self.assertRaises(HTTPException):service.public_access(1,f,SimpleNamespace(tenant_id=2,user_id=9))
            f['schema']['access']='enrolled'
            with self.assertRaises(HTTPException):service.public_access(1,f,SimpleNamespace(tenant_id=1,user_id=9))
    def test_guests_may_view_but_not_submit_sign_in_forms(self):
        f={'status':'active','schema':{**schema(),'access':'authenticated','workflow':{'kind':'exchange'}}}
        with patch.object(service,'gate'),patch.object(service,'require_entitlement') as entitlement,patch.object(service,'require_reviews') as reviews:
            self.assertEqual(service.public_access(1,f,None,viewing=True),{'requires_sign_in':True,'locked_reason':None})
            entitlement.assert_called_once_with(1,'public_form_links');reviews.assert_called()
            learner=SimpleNamespace(tenant_id=1,user_id=9)
            import services.academy_programme_service as programmes
            with patch.object(programmes,'available'),patch.object(programmes,'programme_rpc',return_value={'exchange_eligible':False}):
                self.assertEqual(service.public_access(1,f,learner,viewing=True),{'requires_sign_in':False,'locked_reason':'eligibility'})
                with self.assertRaises(HTTPException) as ineligible:service.public_access(1,f,learner)
                self.assertEqual(ineligible.exception.status_code,403)
            with self.assertRaises(HTTPException) as denied:service.public_access(1,f,None)
            self.assertEqual(denied.exception.status_code,401)
            f['status']='archived'
            with self.assertRaises(HTTPException):service.public_access(1,f,None,viewing=True)
    def test_disabled_forms_fail_before_write(self):
        with patch.object(service,'settings_available',return_value=True),patch.object(service,'require_entitlement',side_effect=HTTPException(402,'Disabled')),patch.object(service,'rpc') as rpc:
            with self.assertRaises(HTTPException):service.save(SimpleNamespace(tenant_id=1,user_id=9),service.Definition(name='Form',schema=schema()))
            rpc.assert_not_called()
    def test_submission_uses_only_learning_rpc_and_hidden_values_never_persist(self):
        f={'id':str(uuid4()),'version':1,'status':'active','schema':schema()}
        with patch.object(service,'public_access'),patch.object(service,'rpc',return_value={'id':'response','duplicate':False}) as rpc:
            result=asyncio.run(service.submit(1,f,None,{'version':1,'idempotency_key':str(uuid4()),'answers':{'student':'No','university':'Hidden'}},[]))
            self.assertFalse(result['duplicate']);self.assertEqual(rpc.call_args.args[0],'submit_elearning_form');self.assertEqual(rpc.call_args.args[1]['p_answers'],{'student':'No'})
    def test_cross_tenant_response_export_and_file_access_fail_closed(self):
        db=MagicMock();db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data=[]
        actor=SimpleNamespace(tenant_id=1,user_id=9)
        with patch.object(service,'service_supabase',db),patch.object(service,'gate'),patch.object(service,'download_builder_asset') as download:
            with self.assertRaises(HTTPException):service.response_detail(actor,uuid4())
            with self.assertRaises(HTTPException):service.download(actor,uuid4(),uuid4())
            download.assert_not_called();db.table.return_value.select.return_value.eq.assert_called_with('tenant_id',1)
        with patch.object(service,'gate',side_effect=HTTPException(402,'Disabled')),patch.object(service,'responses') as responses:
            with self.assertRaises(HTTPException):service.export_csv(actor,{})
            responses.assert_not_called()
    def test_spoofed_file_descriptors_cannot_reference_other_response_uploads(self):
        s=schema();s['sections'][0]['fields'].append({'id':'file','type':'file','label':'File'})
        f={'id':str(uuid4()),'version':1,'schema':s,'status':'active'}
        with patch.object(service,'public_access'),patch.object(service,'rpc') as rpc:
            with self.assertRaises(HTTPException):asyncio.run(service.submit(1,f,None,{'version':1,'idempotency_key':str(uuid4()),'answers':{'student':'No','file':{'id':str(uuid4()),'name':'stolen.pdf','size':10,'type':'application/pdf'}}},[]))
            rpc.assert_not_called()


class LearningFormFilesTests(unittest.TestCase):
    def form(self):
        s=schema();s['sections'][0]['fields'].append({'id':'proof','type':'file','label':'Proof','required':True})
        return {'id':str(uuid4()),'version':1,'status':'active','schema':s}
    def payload(self):return {'version':1,'idempotency_key':str(uuid4()),'answers':{'student':'No'}}
    def test_unsafe_file_rejected_before_storage(self):
        file=UploadFile(io.BytesIO(b'<script>unsafe</script>'),filename='../../proof.pdf',headers=Headers({'content-type':'application/pdf'}))
        with patch.object(service,'public_access'),patch.object(service,'store_builder_asset') as store:
            with self.assertRaises(HTTPException):asyncio.run(service.submit(1,self.form(),None,self.payload(),[('proof',file)]))
            store.assert_not_called()
    def test_private_upload_is_response_owned_and_duplicate_cleans_only_staged_bytes(self):
        file=UploadFile(io.BytesIO(b'%PDF-1.4\n%%EOF\n'),filename='../../proof.pdf',headers=Headers({'content-type':'application/pdf'}))
        with patch.object(service,'public_access'),patch.object(service,'require_private_storage'),patch.object(service,'reserve_storage',return_value='r'),patch.object(service,'finish_storage') as finish,patch.object(service,'release_storage',return_value=True) as release,patch.object(service,'store_builder_asset') as store,patch.object(service,'delete_builder_asset') as remove,patch.object(service,'rpc',return_value={'id':str(uuid4()),'duplicate':True}) as rpc:
            result=asyncio.run(service.submit(1,self.form(),None,self.payload(),[('proof',file)]))
            self.assertTrue(result['duplicate']);key=store.call_args.kwargs['storage_key'];self.assertTrue(key.startswith('elearning-private/tenant_1/response_'));self.assertNotIn('..',key)
            values=rpc.call_args.args[1];self.assertEqual(values['p_files'][0]['field_id'],'proof');self.assertEqual(values['p_answers']['proof']['id'],values['p_files'][0]['id'])
            remove.assert_called_once_with(storage_key=key);release.assert_called_once();finish.assert_called_once()
    def test_storage_cleanup_failure_does_not_mask_original_failure(self):
        staged=[({'storage_key':'private-key'},'reservation')]
        with patch.object(service,'delete_builder_asset',side_effect=RuntimeError('storage offline')),patch.object(service,'release_storage') as release:
            service.cleanup_files(1,staged);release.assert_not_called()

    def test_unknown_or_malformed_metadata_reply_retains_bytes_and_quota(self):
        for reply in (RuntimeError('reply lost'), None, {}, {'id':str(uuid4()),'duplicate':'true'}, {'id':str(uuid4()),'duplicate':False}):
            with self.subTest(reply=reply),patch.object(service,'public_access'),patch.object(service,'require_private_storage'),patch.object(service,'reserve_storage',return_value='r'),patch.object(service,'finish_storage') as finish,patch.object(service,'release_storage') as release,patch.object(service,'store_builder_asset'),patch.object(service,'delete_builder_asset') as remove,patch.object(service,'rpc',side_effect=reply if isinstance(reply,Exception) else None,return_value=reply) as rpc:
                file=UploadFile(io.BytesIO(b'%PDF-1.4\n%%EOF\n'),headers=Headers({'content-type':'application/pdf'}))
                payload=self.payload()
                with self.assertRaises(HTTPException) as uncertain:asyncio.run(service.submit(1,self.form(),None,payload,[('proof',file)]))
                self.assertEqual(uncertain.exception.status_code,503)
                self.assertEqual(uncertain.exception.detail['code'],'private_upload_outcome_unknown')
                self.assertEqual(uncertain.exception.detail['idempotency_key'],payload['idempotency_key'])
                remove.assert_not_called();release.assert_not_called();rpc.assert_called_once()
                finish.assert_called_once();self.assertTrue(finish.call_args.kwargs['succeeded'])

    def test_acknowledged_duplicate_of_same_response_retains_referenced_staged_bytes(self):
        file=UploadFile(io.BytesIO(b'%PDF-1.4\n%%EOF\n'),headers=Headers({'content-type':'application/pdf'}))
        with patch.object(service,'public_access'),patch.object(service,'require_private_storage'),patch.object(service,'reserve_storage',return_value='r'),patch.object(service,'finish_storage'),patch.object(service,'release_storage') as release,patch.object(service,'store_builder_asset'),patch.object(service,'delete_builder_asset') as remove,patch.object(service,'rpc',side_effect=lambda _name,body:{'id':body['p_id'],'duplicate':True}):
            self.assertTrue(asyncio.run(service.submit(1,self.form(),None,self.payload(),[('proof',file)]))['duplicate'])
            remove.assert_not_called();release.assert_not_called()

    def test_acknowledged_new_response_retains_private_files(self):
        file=UploadFile(io.BytesIO(b'%PDF-1.4\n%%EOF\n'),headers=Headers({'content-type':'application/pdf'}))
        with patch.object(service,'public_access'),patch.object(service,'require_private_storage'),patch.object(service,'reserve_storage',return_value='r'),patch.object(service,'finish_storage'),patch.object(service,'release_storage') as release,patch.object(service,'store_builder_asset'),patch.object(service,'delete_builder_asset') as remove,patch.object(service,'rpc',side_effect=lambda _name,body:{'id':body['p_id'],'duplicate':False}):
            self.assertFalse(asyncio.run(service.submit(1,self.form(),None,self.payload(),[('proof',file)]))['duplicate'])
            remove.assert_not_called();release.assert_not_called()

    def test_staging_failure_before_rpc_cleans_without_claiming_unknown_commit(self):
        file=UploadFile(io.BytesIO(b'%PDF-1.4\n%%EOF\n'),headers=Headers({'content-type':'application/pdf'}))
        with patch.object(service,'public_access'),patch.object(service,'require_private_storage'),patch.object(service,'reserve_storage',return_value='r'),patch.object(service,'finish_storage'),patch.object(service,'release_storage',return_value=True) as release,patch.object(service,'store_builder_asset',side_effect=RuntimeError('upload interrupted')),patch.object(service,'delete_builder_asset') as remove,patch.object(service,'rpc') as rpc:
            with self.assertRaises(RuntimeError):asyncio.run(service.submit(1,self.form(),None,self.payload(),[('proof',file)]))
            rpc.assert_not_called();remove.assert_called_once();release.assert_called_once()

class LearningFormApiTests(unittest.TestCase):
    def setUp(self):
        from routes import elearning_forms_routes
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        self.routes=elearning_forms_routes;self.actor=SimpleNamespace(tenant_id=1,user_id=9,role='owner');self.db=MagicMock()
        for patcher in [patch.object(self.routes,'owner',return_value=self.actor),patch.object(service,'service_supabase',self.db),patch.object(service,'gate'),patch.object(self.routes,'audit')]:
            patcher.start();self.addCleanup(patcher.stop)
        app=FastAPI();app.include_router(self.routes.router);app.include_router(self.routes.public);self.client=TestClient(app)
    def test_definition_write_is_tenant_scoped_and_schema_validated(self):
        self.db.rpc.return_value.execute.return_value.data={'id':str(uuid4()),'version':1}
        response=self.client.post('/elearning/forms',json={'name':'Feedback','status':'inactive','schema':schema()})
        self.assertEqual(response.status_code,200);self.assertEqual(self.db.rpc.call_args.args[1]['p_tenant'],1)
        self.assertEqual(self.client.post('/elearning/forms',json={'name':'Feedback','schema':schema(),'tenant_id':2}).status_code,422)
    def test_cross_tenant_response_id_is_not_found(self):
        self.db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data=[]
        response=self.client.get('/elearning/forms/responses/'+str(uuid4()));self.assertEqual(response.status_code,404)
        self.db.table.assert_called_with('elearning_form_responses');self.db.table.return_value.select.return_value.eq.assert_called_with('tenant_id',1)
    @patch("services.entitlement_service.require_public_runtime_entitlement")
    def test_public_render_requires_own_published_project_reference(self, website_access):
        from routes import public_site_routes
        from services import elearning_settings_service
        identifier=uuid4();f={'id':str(identifier),'version':1,'status':'active','schema':schema()}
        query=self.db.table.return_value.select.return_value
        published=query.eq.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute
        published.return_value.data=[{'published_schema':{'elements':[{'type':'academyForm','academy':{'formId':str(identifier)}}]}}]
        with patch.object(public_site_routes,'resolve_website_settings',return_value={'tenant_id':1,'academy_project_id':'own-project'}),patch.object(elearning_settings_service,'get_settings',return_value={'enabled':True,'academy_enabled':True}),patch('database.service_supabase',self.db),patch.object(self.routes,'require_active_tenant_member',side_effect=HTTPException(401,'Guest')),patch.object(self.routes,'enforce_public_rate_limit'),patch.object(service,'definition',return_value=f) as definition,patch.object(service,'public_access'):
            self.assertEqual(self.client.get(f'/public/academies/own/forms/{identifier}').status_code,200);definition.assert_called_with(1,identifier)
            published.return_value.data=[{'published_schema':{'elements':[{'type':'academyForm','academy':{'formId':str(uuid4())}}]}}]
            self.assertEqual(self.client.get(f'/public/academies/own/forms/{identifier}').status_code,404)
    def test_public_http_submission_uses_learning_record_only(self):
        identifier=uuid4();f={'id':str(identifier),'version':1,'status':'active','schema':schema()}
        with patch.object(self.routes,'context',return_value=(1,f,None)),patch.object(self.routes,'enforce_public_form_submission_rate_limit'),patch.object(service,'public_access'),patch.object(service,'rpc',return_value={'id':'r','duplicate':False}) as rpc:
            response=self.client.post(f'/public/academies/own/forms/{identifier}/responses',json={'answers':{'student':'No','university':'Hidden'},'version':1,'idempotency_key':str(uuid4())})
            self.assertEqual(response.status_code,200);self.assertEqual(rpc.call_args.args[0],'submit_elearning_form');self.assertEqual(rpc.call_args.args[1]['p_answers'],{'student':'No'})

class ApplicantResponseFeedTests(unittest.TestCase):
    def test_feed_scopes_tenant_and_user_and_reuses_private_projection(self):
        actor=SimpleNamespace(tenant_id=17,user_id=9)
        query=MagicMock();query.select.return_value=query;query.eq.return_value=query;query.order.return_value=query;query.range.return_value=query
        query.execute.return_value.data=[{'id':'own-response'},{'id':'next-page'}]
        projection={'id':'own-response','status':'approved','submitted_at':'2026-10-12','schema':{'title':'Application','localized':{'title':{'ar':'طلب'}}},'answers':{'private':'answer'},'note':'must not leak'}
        with patch.object(service,'gate'),patch.object(service,'require_reviews'),patch.object(service,'service_supabase') as db,patch.object(service,'applicant_response',return_value=projection) as own:
            db.table.return_value=query
            result=service.applicant_responses(actor,limit=1,offset=2)
        query.eq.assert_any_call('tenant_id',17);query.eq.assert_any_call('user_id',9);query.range.assert_called_once_with(2,3)
        own.assert_called_once_with(actor,'own-response')
        self.assertTrue(result['has_more']);self.assertEqual(set(result['items'][0]),{'id','status','submitted_at','title','localized'})
        self.assertNotIn('private',str(result));self.assertNotIn('must not leak',str(result))
