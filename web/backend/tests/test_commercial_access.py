import unittest
from datetime import datetime, timedelta, timezone
from os import environ
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from services import commercial_access_service as access
from services import entitlement_service as entitlements
from services import tenant_selection_service as selection
from services.commercial_catalog import CAPABILITIES, get_product


class CommercialAccessTests(unittest.TestCase):
    def payload(self, **changes):
        result=dict(idempotency_key='synthetic-command-1234',reason='Verified synthetic receipt',plan_id='business',
                    valid_from='2026-09-08T12:00:00Z',valid_until='2026-10-08T12:00:00Z',
                    method='cash',actual_minor=2500,currency='USD',paid_at='2026-09-08T12:00:00Z',receipt_reference='SYNTHETIC')
        result.update(changes); return result

    def test_strict_manual_payment_input(self):
        access.ManualPayment(**self.payload())
        for changes in [dict(actual_minor=25.0),dict(actual_minor=True),dict(actual_minor='2500'),dict(actual_minor=0),
                        dict(plan_id='unknown'),dict(currency='EUR'),dict(created_by=1),dict(expected_minor=1),
                        dict(valid_from='2026-09-08T12:00:00'),dict(valid_until='2026-09-01T12:00:00Z'),
                        dict(valid_until='2026-10-09T12:00:00Z'),dict(idempotency_key='short')]:
            with self.subTest(fields=tuple(changes)), self.assertRaises(ValidationError):
                access.ManualPayment(**self.payload(**changes))
        access.ManualPayment(**self.payload(valid_until='2026-10-09T12:00:00Z',override_reason='Explicit nonstandard term'))

    def test_monthly_calendar_boundaries(self):
        access.ManualPayment(**self.payload(valid_from='2026-01-31T12:00:00Z',valid_until='2026-02-28T12:00:00Z'))
        access.ManualPayment(**self.payload(valid_from='2028-01-31T12:00:00Z',valid_until='2028-02-29T12:00:00Z'))

    def test_backend_derives_quote_and_excludes_idempotency_from_request(self):
        db=MagicMock(); db.rpc.return_value.execute.return_value.data={'tenant_id':7,'operation':'manual_payment'}
        with patch.object(access,'service_supabase',db):
            access.execute_commercial_command(tenant_id=7,actor_user_id=3,aal='aal2',request_id='test-request',operation='manual_payment',command=access.ManualPayment(**self.payload()))
        args=db.rpc.call_args.args[1]
        self.assertEqual(args['p_payload']['quote']['expected_minor'],2500)
        self.assertNotIn('idempotency_key',args['p_payload']['request'])
        self.assertEqual(args['p_actor_user_id'],3)

    def test_no_aal2_no_database_access(self):
        with patch.object(access,'service_supabase') as db, self.assertRaises(HTTPException) as caught:
            access.execute_commercial_command(tenant_id=7,actor_user_id=3,aal='aal1',request_id='test',operation='manual_payment',command=access.ManualPayment(**self.payload()))
        self.assertEqual(caught.exception.status_code,403);db.rpc.assert_not_called()

    def test_resolver_fails_closed_except_verified_schema93_bridge(self):
        class Missing(Exception): code='PGRST202'
        db=MagicMock();db.rpc.return_value.execute.side_effect=Missing()
        with patch.dict(environ,{'COMMERCIAL_ACCESS_TEST_LOOKUPS':'true'}),patch.object(access,'service_supabase',db):
            for schema in [None,92,94]:
                db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[] if schema is None else [{'schema_version':schema}]
                with self.assertRaises(HTTPException) as caught:access.read_commercial_snapshot(7)
                self.assertEqual(caught.exception.status_code,503)
            db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[{'schema_version':93}]
            self.assertIsNone(access.read_commercial_snapshot(7))

    def state(self, plan='business_plus', **changes):
        now=datetime.now(timezone.utc)
        snapshot=dict(tenant_id=7,revision=2,review_state='reviewed',addons=[],has_history=True,next_transition_at=None,
                      period=dict(id='period-a',tenant_id=7,plan_id=plan,valid_from=(now-timedelta(days=1)).isoformat(),valid_until=(now+timedelta(days=1)).isoformat()))
        snapshot.update(changes)
        return entitlements._reviewed_commercial_state(7,snapshot)

    def test_authorized_plan_matrix(self):
        expected={'forms':(False,False,False),'website':(True,True,False),'business':(True,True,True),'business_plus':(True,True,True)}
        for plan,(website,reservations,commerce) in expected.items():
            capabilities=set(self.state(plan)['capabilities'])
            self.assertIn('forms',capabilities)
            for cap,wanted in [('page_builder',website),('reservations',reservations),('internal_calendar',reservations),('ecommerce_management',commerce),('ecommerce_publish',commerce),('ecommerce_orders',commerce),('ecommerce_refunds',commerce)]:
                with self.subTest(plan=plan,capability=cap):self.assertEqual(cap in capabilities,wanted)
        self.assertEqual(set(get_product('business_plus')['capabilities'])-set(get_product('business')['capabilities']),{'priority_support'})
        self.assertEqual(len(CAPABILITIES),len(set(CAPABILITIES)))

    def test_review_unknown_period_and_tenant_denials(self):
        self.assertEqual(self.state(review_state='review_required')['capabilities'],[])
        self.assertEqual(self.state('unknown')['capabilities'],[])
        for start,end in [('bad','bad'),('2100-01-01T00:00:00Z','2101-01-01T00:00:00Z'),('2000-01-01T00:00:00Z','2001-01-01T00:00:00Z'),('2030-01-01T00:00:00Z','2020-01-01T00:00:00Z')]:
            self.assertEqual(self.state(period=dict(tenant_id=7,plan_id='business',valid_from=start,valid_until=end))['capabilities'],[])
        with self.assertRaises(HTTPException):self.state(period=dict(tenant_id=8,plan_id='business'))

    def test_revision_changes_on_downgrade_revocation_expiry_and_catalog(self):
        original=self.state()
        downgraded=self.state('forms',revision=3)
        expired=self.state(period=None)
        revoked=self.state(period=None,revision=4)
        self.assertNotIn('ecommerce_management',downgraded['capabilities'])
        self.assertEqual(len({s['entitlement_revision'] for s in [original,downgraded,expired,revoked]}),4)
        with patch('services.commercial_catalog.CATALOG_VERSION','next-version'):
            self.assertNotEqual(original['entitlement_revision'],self.state()['entitlement_revision'])

    def test_grandfathered_address_does_not_grant_website_to_forms(self):
        self.assertIn('branded_madar_subdomain',self.state('website',grandfathered_subdomain=True)['capabilities'])
        self.assertNotIn('branded_madar_subdomain',self.state('forms',grandfathered_subdomain=True)['capabilities'])


class TenantSelectionTests(unittest.TestCase):
    user={'id':4,'auth_id':'synthetic-auth','tenant_id':7,'user_type':'user'}
    def request(self,value):return Request({'type':'http','headers':[(b'x-madar-tenant-id',value.encode())]})
    def db(self,rows):
        db=MagicMock();db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data=rows
        return db
    def membership(self,**changes):return dict(tenant_id=8,user_id=4,auth_id='synthetic-auth',status='active',role='member',**changes)
    def test_switch_is_membership_bound_and_request_scoped(self):
        with patch.object(selection,'service_supabase',self.db([self.membership()])),patch.object(selection,'tenant_is_active',return_value=True):
            switched=selection.select_request_tenant(self.request('8'),self.user)
        self.assertEqual(switched['tenant_id'],8);self.assertEqual(self.user['tenant_id'],7)
        self.assertEqual(switched['user_type'],'user')
    def test_wrong_membership_and_closed_tenant_deny(self):
        for rows in [[],[{**self.membership(),'user_id':99}],[{**self.membership(),'auth_id':'other'}],[{**self.membership(),'status':'disabled'}],[{**self.membership(),'role':'superadmin'}]]:
            with patch.object(selection,'service_supabase',self.db(rows)),patch.object(selection,'tenant_is_active',return_value=True),self.assertRaises(HTTPException):
                selection.select_request_tenant(self.request('8'),self.user)
        with patch.object(selection,'service_supabase',self.db([self.membership()])),patch.object(selection,'tenant_is_active',return_value=False),self.assertRaises(HTTPException):
            selection.select_request_tenant(self.request('8'),self.user)
    def test_infrastructure_failure_and_invalid_selector_never_grant(self):
        for selector in ['-1','0','8 OR 1=1','2147483648','8.0']:
            with self.assertRaises(HTTPException):selection.select_request_tenant(self.request(selector),self.user)
        db=self.db([]);db.table.side_effect=RuntimeError('unavailable')
        with patch.object(selection,'service_supabase',db),self.assertRaises(HTTPException) as caught:
            selection.select_request_tenant(self.request('8'),self.user)
        self.assertEqual(caught.exception.status_code,503)
    def test_platform_admin_privileges_remain_separate(self):
        user={**self.user,'user_type':'admin'}
        with patch.object(selection,'service_supabase') as db:
            self.assertEqual(selection.select_request_tenant(self.request('8'),user),user)
        db.table.assert_not_called()
