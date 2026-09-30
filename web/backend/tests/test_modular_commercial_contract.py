import copy
import unittest
from itertools import combinations
from os import environ
from unittest.mock import patch
from fastapi import HTTPException
from services import entitlement_service as ent
from services.commercial_catalog import CORE_MODULE_IDS, MODULE_CAPABILITIES, module_entitlements, normalize_module_ids, get_catalog, GIB
from tests.test_commercial_authority import snapshot


class ModularCommercialContractTests(unittest.TestCase):
    def setUp(self):
        env=patch.dict(environ,{"COMMERCIAL_ENTITLEMENTS_ENFORCED":"true"});env.start();self.addCleanup(env.stop)

    def state(self,modules):
        state=snapshot()
        state['subscriptions'][0]['module_basis']={module:state['subscriptions'][0]['module_basis'][module] for module in modules}
        state['period']['module_ids']=list(modules)
        return state

    def test_seven_unions_and_storage_maximum(self):
        for n in (1,2,3):
            for modules in combinations(CORE_MODULE_IDS,n):
                capabilities,allowances=module_entitlements(modules)
                self.assertEqual(capabilities,set().union(*(MODULE_CAPABILITIES[m] for m in modules)))
                self.assertEqual(allowances['storage_bytes'],(5 if 'ecommerce' in modules else 2 if 'website' in modules else 1)*GIB)
                self.assertEqual(module_entitlements(list(reversed(modules))), (capabilities,allowances))
                state=self.state(modules)
                with patch.object(ent,'resolve_commercial_access',return_value=state):
                    result=ent.get_tenant_entitlements(7)
                self.assertEqual(set(result['capabilities']),capabilities)
                self.assertEqual(set(result['effective_modules']),set(modules))
                self.assertNotIn('ai_analytics',capabilities)
                self.assertNotIn('priority_support',capabilities)

    def test_module_isolation(self):
        self.assertNotIn('page_builder',MODULE_CAPABILITIES['ecommerce'])
        self.assertNotIn('website_publish',MODULE_CAPABILITIES['ecommerce'])
        self.assertNotIn('ecommerce',MODULE_CAPABILITIES['website'])
        self.assertNotIn('forms',MODULE_CAPABILITIES['website'])
        self.assertNotIn('ecommerce',MODULE_CAPABILITIES['forms'])
        self.assertNotIn('page_builder',MODULE_CAPABILITIES['forms'])
        self.assertTrue({'reservations','reservation_management','internal_calendar','reservation_analytics'}<=MODULE_CAPABILITIES['website'])
        self.assertIn('data_exports',MODULE_CAPABILITIES['forms'])

    def test_assignment_coverage_intersection_no_unassigned_grant(self):
        state=self.state(['website']);state['period']['module_ids']=['website','ecommerce']
        with patch.object(ent,'resolve_commercial_access',return_value=state):
            self.assertNotIn('ecommerce',ent.get_tenant_entitlements(7)['capabilities'])
        state=self.state(['website','ecommerce']);state['period']['module_ids']=['website']
        with patch.object(ent,'resolve_commercial_access',return_value=state):
            self.assertNotIn('ecommerce',ent.get_tenant_entitlements(7)['capabilities'])
        state['period']=None
        with patch.object(ent,'resolve_commercial_access',return_value=state):
            self.assertEqual(ent.get_tenant_entitlements(7)['capabilities'],[])

    def test_legacy_ladder_never_authorizes_and_reports_review(self):
        for legacy in ('forms','website','business','business_plus'):
            state=snapshot();state['subscriptions'][0].update(plan_id=legacy,module_basis=None)
            with patch.object(ent,'resolve_commercial_access',return_value=state):
                result=ent.get_tenant_entitlements(7)
            self.assertEqual(result['commercial_denial_code'],'commercial_review_required')
            self.assertTrue(result['legacy_assignment_requires_review'])
            self.assertEqual(result['capabilities'],[])

    def test_public_module_boundaries_use_canonical_owner(self):
        for module in CORE_MODULE_IDS:
            with patch.object(ent,'resolve_commercial_access',return_value=self.state([module])):
                for owner,capability in (('forms','public_form_links'),('website','website_publish'),('website','reservations'),('ecommerce','ecommerce')):
                    if owner==module:
                        ent.require_public_runtime_entitlement({'tenant_id':7},capability)
                    else:
                        with self.assertRaises(HTTPException) as error:ent.require_public_runtime_entitlement({'tenant_id':7},capability)
                        self.assertEqual(error.exception.status_code,503)
                        self.assertEqual(error.exception.detail['code'],'tenant_service_unavailable')

    def test_empty_unknown_duplicate_modules_not_paid_bundles(self):
        for value in ([],['business'],['forms','forms'],['website',None]):
            with self.assertRaises(ValueError):normalize_module_ids(value)

    def test_core_catalog_no_new_legacy_ladder(self):
        catalog=get_catalog(public_only=True)
        core=[p for p in catalog['products'] if p['type']=='core_module']
        self.assertEqual({p['id'] for p in core},set(CORE_MODULE_IDS))
        self.assertEqual({p['name'] for p in core},{'Madar Forms','Madar Website','Madar Commerce'})
        self.assertTrue(catalog['sales_activation_required'])
        self.assertNotIn('business',[p['id'] for p in catalog['products']])
        self.assertNotIn('business_plus',[p['id'] for p in catalog['products']])

    def test_website_native_form_exception_cannot_authorize_standalone_form(self):
        from routes import public_site_routes as routes
        settings={'tenant_id':7,'published_project_id':'site-project'}
        with patch.object(ent,'resolve_commercial_access',return_value=self.state(['website'])) as lookup, patch.object(routes,'get_bound_published_project',return_value={'published_schema':{'forms':[{'id':'embedded'}]}}):
            routes.require_public_form_product(settings,'embedded')
            lookup.assert_called_once_with(7)
            with self.assertRaises(HTTPException):routes.require_public_form_product(settings,'standalone-other-project')
        with patch.object(ent,'resolve_commercial_access',return_value=self.state(['ecommerce'])), patch.object(routes,'get_bound_published_project') as project:
            with self.assertRaises(HTTPException):routes.require_public_form_product(settings,'embedded')
            project.assert_not_called()
