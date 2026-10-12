"""Exchange calls the independent Forms pipeline with server-derived context."""
import asyncio
from types import SimpleNamespace
from uuid import uuid4
from unittest import TestCase
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from services import academy_exchange_service as exchange
from services import elearning_forms_service as forms
from services import academy_owner_service as owner
from tests.test_elearning_forms import schema


class ExchangeFormsServiceTests(TestCase):
    def setUp(self):
        self.actor=SimpleNamespace(tenant_id=7,user_id=17,role='owner')

    def test_exchange_gate_requires_schema_exchange_and_existing_forms_entitlements(self):
        with patch.object(exchange,'settings_available',return_value=False),patch.object(exchange,'available') as available:
            with self.assertRaises(HTTPException) as error:exchange.gate(self.actor)
            self.assertEqual(error.exception.status_code,503);available.assert_not_called()
        with patch.object(exchange,'settings_available',return_value=True),patch.object(exchange,'available') as available,patch.object(forms,'gate') as gate:
            exchange.gate(self.actor);available.assert_called_once_with(self.actor,'exchange');gate.assert_called_once_with(7,'forms')

    def test_exchange_submission_uses_one_forms_rpc_with_immutable_context(self):
        form={'id':str(uuid4()),'version':1,'status':'active','schema':schema()};opportunity=uuid4()
        payload={'version':1,'idempotency_key':str(uuid4()),'answers':{'student':'No','university':'Hidden'}}
        with patch.object(forms,'public_access'),patch.object(exchange,'gate'),patch.object(forms,'rpc',return_value={'id':'r','duplicate':False}) as rpc:
            asyncio.run(forms.submit(7,form,self.actor,payload,[],opportunity))
            name,params=rpc.call_args.args
            self.assertEqual(name,'submit_elearning_form');self.assertEqual(params['p_opportunity'],str(opportunity));self.assertEqual(params['p_user'],17);self.assertEqual(params['p_tenant'],7);self.assertEqual(params['p_answers'],{'student':'No'})
            first=params['p_hash'];asyncio.run(forms.submit(7,form,self.actor,payload,[],uuid4()));self.assertNotEqual(first,rpc.call_args.args[1]['p_hash'])

    def test_guest_and_foreign_actor_cannot_submit_exchange_context(self):
        form={'id':str(uuid4()),'version':1,'status':'active','schema':schema()}
        with patch.object(forms,'public_access'),patch.object(exchange,'gate'),patch.object(forms,'rpc') as rpc:
            for actor in [None,SimpleNamespace(tenant_id=8,user_id=17)]:
                with self.assertRaises(HTTPException):asyncio.run(forms.submit(7,form,actor,{},[],uuid4()))
            rpc.assert_not_called()

    def test_new_opportunity_activation_requires_forms_gate(self):
        payload=owner.Opportunity(title='Exchange',status='published',application_form_id=uuid4())
        with patch.object(owner,'require_upgrade'),patch.object(owner,'available'),patch.object(exchange,'gate',side_effect=HTTPException(402,'Forms unavailable')),patch.object(owner,'service_supabase') as db:
            with self.assertRaises(HTTPException):owner.save_opportunity(self.actor,payload)
            db.rpc.assert_not_called()

    def test_filtered_inbox_keeps_tenant_form_and_opportunity_filters(self):
        db=MagicMock();query=db.table.return_value.select.return_value
        query.eq.return_value=query;query.order.return_value=query;query.range.return_value=query;query.execute.return_value.data=[]
        with patch.object(forms,'service_supabase',db),patch.object(forms,'gate'),patch.object(exchange,'gate'):
            forms.responses(self.actor,form_id='form',opportunity_id='opportunity')
        self.assertEqual(query.eq.call_args_list[0].args,('tenant_id',7))
        self.assertIn((('opportunity_id','opportunity'),{}),query.eq.call_args_list)
        self.assertIn((('form_id','form'),{}),query.eq.call_args_list)

    def test_decision_authority_is_actor_tenant_and_user_never_payload(self):
        payload=exchange.Decision(status='approved',revision=2,note='Reviewed')
        with patch.object(exchange,'gate'),patch.object(forms,'rpc',return_value={'status':'approved'}) as rpc:
            exchange.review(self.actor,uuid4(),payload)
            self.assertEqual(rpc.call_args.args[1]['p_tenant'],7);self.assertEqual(rpc.call_args.args[1]['p_admin'],17)

    def test_specialized_exchange_api_rejects_new_answers_even_before_schema142(self):
        from services import academy_programme_service as programmes
        payload=programmes.Application(kind='exchange',details={'terms_accepted':True},idempotency_key=uuid4())
        db=MagicMock();query=db.table.return_value.select.return_value
        query.eq.return_value=query;query.limit.return_value=query;query.execute.return_value.data=[]
        with patch.object(programmes,'available'),patch.object(programmes,'service_supabase',db),patch.object(programmes,'programme_rpc') as rpc:
            with self.assertRaises(HTTPException) as error:programmes.submit(self.actor,payload)
            self.assertEqual(error.exception.detail['code'],'exchange_use_learning_forms');rpc.assert_not_called()
            query.execute.return_value.data=[{'id':'historical'}]
            rpc.return_value='historical';self.assertEqual(programmes.submit(self.actor,payload),{'id':'historical'})
            self.assertEqual(query.eq.call_args_list[0].args,('tenant_id',7))

    def test_publication_rejects_when_existing_forms_runtime_capability_is_missing(self):
        payload=owner.Opportunity(title='Exchange',status='published',application_form_id=uuid4())
        with patch.object(owner,'require_upgrade'),patch.object(owner,'available'),patch.object(exchange,'gate'),patch('services.entitlement_service.require_entitlement',side_effect=HTTPException(402,'Public Form access unavailable')) as entitlement,patch.object(owner,'service_supabase') as db:
            with self.assertRaises(HTTPException):owner.save_opportunity(self.actor,payload)
            entitlement.assert_called_once_with(7,'public_form_links');db.rpc.assert_not_called()

    def test_forms_history_remains_readable_without_exchange_review_entitlement(self):
        record={'id':str(uuid4()),'form_id':str(uuid4()),'version':1,'opportunity_id':str(uuid4()),'answers':{'student':'No'}}
        db=MagicMock();response_query=MagicMock();response_query.eq.return_value=response_query;response_query.limit.return_value=response_query;response_query.execute.return_value.data=[record]
        file_query=MagicMock();file_query.eq.return_value=file_query;file_query.execute.return_value.data=[]
        db.table.side_effect=lambda name:SimpleNamespace(select=lambda *_:response_query if name=='elearning_form_responses' else file_query)
        with patch.object(forms,'gate'),patch.object(forms,'settings_available',side_effect=lambda minimum=141:minimum<=142),patch.object(forms,'service_supabase',db),patch.object(forms,'definition',return_value={'schema':schema()}),patch.object(exchange,'review_context',side_effect=HTTPException(402,'Exchange unavailable')):
            result=forms.response_detail(self.actor,record['id'])
            self.assertEqual(result['answers'],{'student':'No'});self.assertIsNone(result['exchange'])
