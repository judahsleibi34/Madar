import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

from fastapi import HTTPException, Response
from routes import ecommerce_routes as routes
from services.observability_service import CORRELATION_ID, JsonFormatter
from tests.test_ecommerce_product_variants import product_payload, PRODUCT_ID


class DbError(Exception):
    def __init__(self, code, message, constraint=None):
        self.code, self.message, self.constraint = code, message, constraint
        super().__init__(message)


class EcommerceReconciliationTests(unittest.TestCase):
    def test_all_known_constraints_map_to_specific_safe_codes(self):
        for constraint, code in routes.CATALOG_CONSTRAINT_CODES.items():
            with self.subTest(constraint=constraint), self.assertRaises(HTTPException) as caught:
                routes._handle_catalog_error(DbError('23505', f'duplicate key violates unique constraint "{constraint}"'))
            self.assertEqual(caught.exception.status_code, 409)
            self.assertEqual(caught.exception.detail['code'], code)
            self.assertNotIn(constraint, json.dumps(caught.exception.detail))

    def test_explicit_cross_sku_exception_is_catalog_sku_conflict(self):
        with self.assertRaises(HTTPException) as caught:
            routes._handle_catalog_error(DbError('23505', 'ecommerce_sku_conflict'))
        self.assertEqual(caught.exception.detail['code'], 'CATALOG_SKU_CONFLICT')

    def test_domain_duplicate_exceptions_are_precise(self):
        for code in ('OPTION_NAME_CONFLICT','OPTION_VALUE_CONFLICT','VARIANT_COMBINATION_CONFLICT'):
            with self.subTest(code=code), self.assertRaises(HTTPException) as caught:
                routes._handle_catalog_error(DbError('23505', code))
            self.assertEqual(caught.exception.detail['code'], code)

    def test_merged_variant_validation_returns_safe_domain_error(self):
        from pydantic import ValidationError
        from pydantic_core import PydanticCustomError
        class InvalidVariantModel(routes.BaseModel):
            name: str
            @routes.model_validator(mode="after")
            def reject_duplicate(self):
                raise PydanticCustomError("OPTION_VALUE_CONFLICT", "private customer value")
        try:
            InvalidVariantModel(name="private customer value")
        except ValidationError as error:
            with self.assertRaises(HTTPException) as caught:
                routes._handle_catalog_error(error)
        self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(caught.exception.detail["code"], "OPTION_VALUE_CONFLICT")
        self.assertNotIn("private", json.dumps(caught.exception.detail))

    def test_unknown_unique_violation_is_not_claimed_to_be_sku_or_slug(self):
        error = DbError('23505', 'duplicate key violates unique constraint "unknown_catalog_key"; secret payload')
        with self.assertRaises(HTTPException) as caught:
            routes._handle_catalog_error(error)
        self.assertEqual(caught.exception.detail['code'], 'CATALOG_UNIQUE_CONFLICT')
        self.assertNotIn('SKU', caught.exception.detail['message'])
        self.assertNotIn('secret', json.dumps(caught.exception.detail))

    def test_diagnostics_do_not_trust_customer_values_as_constraint_names(self):
        error=DbError('23505', 'duplicate key; Key (sku)=(VARIANT_COMBINATION_CONFLICT ecommerce_products_tenant_id_sku_key) already exists')
        with self.assertRaises(HTTPException) as caught:
            routes._handle_catalog_error(error)
        self.assertEqual(caught.exception.detail['code'],'CATALOG_UNIQUE_CONFLICT')

    def test_structured_log_and_reference_are_complete_and_sanitized(self):
        token=CORRELATION_ID.set('request-1234')
        try:
            request=SimpleNamespace(url=SimpleNamespace(path='/ecommerce/products/'+PRODUCT_ID),method='PUT')
            context=SimpleNamespace(tenant_id=7,user_id=42)
            with patch.object(routes.logger, 'warning') as log, self.assertRaises(HTTPException) as caught:
                routes._handle_catalog_error(DbError('23505','secret payload','unknown_catalog_key'),request=request,context=context,product_id=PRODUCT_ID,stage='atomic_product_save')
            fields=log.call_args.kwargs['extra']
            self.assertEqual(fields['tenant_id'],7)
            self.assertEqual(fields['user_id'],42)
            self.assertEqual(fields['constraint'],'unknown_catalog_key')
            self.assertEqual(fields['sqlstate'],'23505')
            self.assertEqual(fields['status_code'],409)
            self.assertEqual(fields['correlation_id'],'request-1234')
            self.assertNotIn('secret',json.dumps(fields))
            self.assertEqual(caught.exception.detail['context']['reference_id'],'request-1234')
            import logging
            record=logging.LogRecord('test',logging.WARNING,'',1,'ecommerce.catalog_save_failed',(),None)
            for key,value in fields.items():setattr(record,key,value)
            rendered=json.loads(JsonFormatter().format(record))
            for key in ('tenant_id','user_id','product_id','sqlstate','constraint','operation_stage'):self.assertEqual(rendered[key],fields[key])
        finally:CORRELATION_ID.reset(token)

    def test_full_update_uses_single_transaction_rpc_and_no_separate_mutations(self):
        payload=routes.ProductPayload(**product_payload())
        product={**payload.model_dump(mode='json'),'id':PRODUCT_ID,'tag_ids':[],'options':[],'variants':[]}
        service=Mock();service.rpc.return_value.execute.return_value=SimpleNamespace(data=product)
        context=SimpleNamespace(tenant_id=7,user_id=42)
        with patch.object(routes,'service_supabase',service), patch.object(routes,'_require_ecommerce_access',return_value=context), patch.object(routes,'_require_role'), patch.object(routes,'_tenant_row',return_value={'images':[]}), patch.object(routes,'invalidate_ecommerce_cache'), patch.object(routes,'_managed_catalog_asset_keys'):
            result=routes.update_product(UUID(PRODUCT_ID),payload,object(),Response())
        service.table.assert_not_called()
        service.rpc.assert_called_once()
        self.assertEqual(service.rpc.call_args.args[0],'update_ecommerce_product_v3_safe')
        params=service.rpc.call_args.args[1]
        self.assertIsNone(params['p_aggregate'])
        self.assertEqual(params['p_tenant_id'],7)
        self.assertEqual(result['product']['id'],PRODUCT_ID)

    def test_failed_transaction_does_not_run_post_commit_work(self):
        service=Mock();service.rpc.return_value.execute.side_effect=DbError('23505','VARIANT_COMBINATION_CONFLICT')
        with patch.object(routes,'service_supabase',service), patch.object(routes,'_require_ecommerce_access',return_value=SimpleNamespace(tenant_id=7,user_id=42)), patch.object(routes,'_require_role'), patch.object(routes,'_tenant_row',return_value={'images':[]}), patch.object(routes,'invalidate_ecommerce_cache') as side_effect, self.assertRaises(HTTPException):
            routes.update_product(UUID(PRODUCT_ID),routes.ProductPayload(**product_payload()),object(),Response())
        side_effect.assert_not_called()
        service.table.assert_not_called()

    def test_missing_v3_fails_closed_without_unsafe_fallback(self):
        service=Mock();service.rpc.return_value.execute.side_effect=DbError('PGRST202','missing function')
        p=routes.ProductPayload(**product_payload(options=[],variants=[]))
        with patch.object(routes,'service_supabase',service),self.assertRaises(DbError):routes._save_product_aggregate(7,PRODUCT_ID,p)
        service.rpc.assert_called_once()

    def test_stale_catalog_state_has_precise_conflict_code(self):
        with self.assertRaises(HTTPException) as caught:
            routes._handle_catalog_error(DbError('P0001','CATALOG_CHANGED_CONFLICT'))
        self.assertEqual(caught.exception.status_code,409)
        self.assertEqual(caught.exception.detail['code'],'CATALOG_CHANGED_CONFLICT')

    def test_catalog_snapshot_rpc_is_tenant_scoped_and_single_roundtrip(self):
        service=Mock(); service.rpc.return_value.execute.return_value=SimpleNamespace(data={'products':[], 'tags':[], 'categories':[], 'commerce_currency':'USD'})
        with patch.object(routes,'service_supabase',service):
            result=routes._catalog_for_tenant(7)
        service.table.assert_not_called()
        service.rpc.assert_called_once_with('read_ecommerce_catalog_v3_safe',{'p_tenant_id':7})
        self.assertEqual(result['stock_summary'],{'low_stock':0,'out_of_stock':0})

    def test_catalog_snapshot_unknown_database_error_propagates(self):
        service=Mock(); service.rpc.return_value.execute.side_effect=DbError('XX000','database failure')
        with patch.object(routes,'service_supabase',service), self.assertRaises(DbError):
            routes._catalog_for_tenant(7)

    def test_current_public_options_filter_history_without_leaking_columns(self):
        from routes import public_site_routes as public
        service=Mock(); service.table.return_value.select.return_value.eq.return_value.order.return_value.order.return_value.execute.return_value=SimpleNamespace(data=[
            {'id':'live','product_id':PRODUCT_ID,'active':True,'normalized_name':'private','name_translations':{'en':'Size'}},
            {'id':'history','product_id':PRODUCT_ID,'active':False},
        ])
        with patch.object(public,'service_supabase',service):
            result=public._current_ecommerce_option_rows(7,columns='id,name_translations')
        self.assertEqual(result,[{'id':'live','name_translations':{'en':'Size'}}])

    def test_semantic_names_do_not_depend_on_locale_key_order(self):
        from tests.test_ecommerce_product_variants import OPTION_ID, VALUE_ID, VARIANT_ID
        def payload(labels):
            return routes.ProductPayload(**product_payload(options=[{'id':OPTION_ID,'code':'color','name_translations':labels,'values':[{'id':VALUE_ID,'code':'red','value_translations':{'ar':'أحمر','en':'Red'}}]}],variants=[{'id':VARIANT_ID,'sku':'RED','option_value_ids':[VALUE_ID]}]))
        a=routes._product_aggregate_payload(payload({'ar':'اللون','en':'Color'}))
        b=routes._product_aggregate_payload(payload({'en':'Color','ar':'اللون'}))
        self.assertEqual(a['options'][0]['normalized_name'],'color')
        self.assertEqual(a['options'][0]['values'][0]['normalized_value'],'red')
        self.assertEqual(a['options'][0]['normalized_name'],b['options'][0]['normalized_name'])

    def test_unhandled_database_errors_are_not_swallowed(self):
        error=DbError('XX000','internal database failure')
        with self.assertRaises(DbError) as caught:routes._handle_catalog_error(error)
        self.assertIs(caught.exception,error)

    def test_atomic_rpc_preserves_brand_and_multi_category_parameters(self):
        category="11111111-1111-4111-8111-111111111111";second="22222222-2222-4222-8222-222222222222"
        brand="33333333-3333-4333-8333-333333333333"
        payload=routes.ProductPayload(**product_payload(category_ids=[category,second],brand_id=brand))
        data,categories,tags=routes._product_data(payload,SimpleNamespace(tenant_id=7),atomic=True)
        self.assertEqual(categories,[category,second]);self.assertEqual(data['brand_id'],brand)
        self.assertEqual(data['category_id'],category)

    def test_omitted_aggregate_components_are_preserved(self):
        payload=routes.ProductPayload(**product_payload(attributes=[]))
        aggregate=routes._product_aggregate_payload(payload)
        self.assertEqual(aggregate['attributes'],[])
        self.assertIsNone(aggregate['options']);self.assertIsNone(aggregate['variants'])

    def test_inventory_guard_flags_reach_variant_transaction(self):
        service=Mock();service.rpc.return_value.execute.return_value=SimpleNamespace(data={})
        payload=routes.ProductPayload(**product_payload(options=[],variants=[],expected_catalog_version='a'*64,expected_inventory_version='b'*64,preserve_inventory=True))
        with patch.object(routes,'service_supabase',service):routes._save_product_aggregate(7,PRODUCT_ID,payload)
        params=service.rpc.call_args.args[1]
        self.assertEqual(params['p_expected_inventory_version'],'b'*64);self.assertTrue(params['p_preserve_inventory'])
