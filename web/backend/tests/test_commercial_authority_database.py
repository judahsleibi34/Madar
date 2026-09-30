"""Real PostgreSQL ledger regressions; enabled only in disposable rehearsal."""
import os
import time
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

import psycopg
from psycopg.types.json import Jsonb

DSN = os.getenv("COMMERCIAL_SYNTHETIC_DATABASE_DSN")


@unittest.skipUnless(DSN, "Requires disposable PostgreSQL commercial rehearsal")
class CommercialLedgerDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = psycopg.connect(DSN, autocommit=True)
        self.addCleanup(self.db.close)
        self.tenant = self.db.execute("insert into public.tenants(brand_name,owner_name) values('Synthetic commercial test','Synthetic') returning tenant_id").fetchone()[0]
        auth_id = uuid4()
        self.db.execute("insert into auth.users(id,email_confirmed_at) values(%s,now())", (auth_id,))
        self.actor = self.db.execute("insert into public.users(auth_id,first_name,last_name,email,user_type,account_status,email_verified,email_verified_at) values(%s,'Synthetic','Admin',%s,'admin','active',true,now()) returning id", (auth_id, str(auth_id)+'@example.invalid')).fetchone()[0]

    def state(self):
        return self.db.execute("select public.resolve_commercial_access(%s)", (self.tenant,)).fetchone()[0]

    def command(self, operation, request=None, key=None, *, aal="aal2", actor=None, db=None, quote=None):
        request = {"reason":"Synthetic commercial review", "expected_revision":self.state()["revision"], **(request or {})}
        return (db or self.db).execute("select public.apply_commercial_access_command(%s,%s,%s,%s,%s,%s,%s)",
            (self.tenant, actor or self.actor, aal, operation, key or str(uuid4()), "synthetic-request-id",
             Jsonb({"request":request, "quote":quote or {"expected_minor":2500,"catalog_version":"synthetic"}}))).fetchone()[0]

    def grant(self, expired=False, payment=False):
        now = datetime.now(timezone.utc)
        start = now-timedelta(days=3)
        end = now-timedelta(days=1) if expired else now+timedelta(days=3)
        request = {"plan_id":"business","valid_from":start.isoformat(),"valid_until":end.isoformat()}
        if payment:
            request.update(method="cash",actual_minor=2500,currency="USD",billing_months=1,
                           paid_at=now.isoformat(),receipt_reference="SYNTHETIC")
        return self.command("manual_payment" if payment else "complimentary", request)

    def test_schema_transition_and_snapshot_contract(self):
        self.assertEqual(self.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0],115)
        self.assertEqual(self.state()["contract_version"],115)
        self.assertEqual(self.state()["subscriptions"],[])

    def test_runtime_context_contains_same_statement_ledger_and_preserves_privileges(self):
        subdomain = "gate-" + str(self.tenant)
        self.db.execute("insert into public.website_settings(user_id,tenant_id,subdomain) values(%s,%s,%s)", (self.actor,self.tenant,subdomain))
        def context():
            return self.db.execute("select settings from public.get_public_site_runtime_context(%s,false)", (subdomain,)).fetchone()[0]["_commercial_snapshot"]
        for operation in (None, "suspend", "reactivate"):
            if operation:
                self.command(operation)
            result = context()
            expected = self.state()
            self.assertEqual(result["tenant_id"], self.tenant)
            self.assertEqual(result["revision"], expected["revision"])
            self.assertEqual(result["commercial_suspended_at"], expected["commercial_suspended_at"])
            self.assertEqual(result["contract_version"], 115)
        signature = "public.get_public_site_runtime_context(text,boolean)"
        for role, allowed in (("service_role",True),("anon",False),("authenticated",False)):
            self.assertEqual(self.db.execute("select has_function_privilege(%s,%s,'EXECUTE')", (role,signature)).fetchone()[0], allowed)
        self.assertEqual(self.db.execute("select count(*) from public.get_public_site_runtime_context('other-tenant',false)").fetchone()[0], 0)

    def test_rls_and_privileges(self):
        for table in ("tenant_commercial_state","commercial_access_periods","commercial_access_events","commercial_manual_payments"):
            self.assertTrue(self.db.execute("select relrowsecurity from pg_class where oid=%s::regclass", ("public."+table,)).fetchone()[0])
            for role in ("anon","authenticated","service_role"):
                self.assertFalse(self.db.execute("select has_table_privilege(%s,%s,'UPDATE')", (role,"public."+table)).fetchone()[0])
        signature="public.apply_commercial_access_command(integer,integer,text,text,text,text,jsonb)"
        self.assertTrue(self.db.execute("select has_function_privilege('service_role',%s,'EXECUTE')",(signature,)).fetchone()[0])
        self.assertFalse(self.db.execute("select has_function_privilege('authenticated',%s,'EXECUTE')",(signature,)).fetchone()[0])

    def test_admin_and_aal2_required(self):
        for aal in ("aal1",None):
            with self.assertRaises(psycopg.errors.InsufficientPrivilege): self.command("suspend",aal=aal)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege): self.command("suspend",actor=2147483647)
        self.assertIsNone(self.state()["commercial_suspended_at"])

    def test_tenant_admin_identity_cannot_issue_ledger_command(self):
        auth_id=uuid4()
        self.db.execute("insert into auth.users(id,email_confirmed_at) values(%s,now())",(auth_id,))
        actor=self.db.execute("insert into public.users(auth_id,first_name,last_name,email,user_type,tenant_id,account_status,email_verified,email_verified_at) values(%s,'Synthetic','Owner',%s,'user',%s,'active',true,now()) returning id",(auth_id,str(auth_id)+'@example.invalid',self.tenant)).fetchone()[0]
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.command("suspend",actor=actor)
        self.assertIsNone(self.state()["commercial_suspended_at"])

    def test_reason_and_revision_required(self):
        for request in ({"reason":"  "},{"expected_revision":None},{"expected_revision":"1"}):
            with self.assertRaises(psycopg.errors.InvalidParameterValue): self.command("suspend",request)

    def test_hold_and_revision_then_reactivate_preserve_review(self):
        before=self.state()
        suspended=self.command("suspend")
        self.assertEqual(suspended["revision"],before["revision"]+1)
        self.assertIsNotNone(self.state()["commercial_suspended_at"])
        restored=self.command("reactivate")
        self.assertEqual(restored["revision"],suspended["revision"]+1)
        self.assertIsNone(self.state()["commercial_suspended_at"])
        self.assertEqual(self.state()["review_state"],"review_required")

    def test_durable_replay_precedes_stale_revision(self):
        revision=self.state()["revision"]; key=str(uuid4())
        request={"expected_revision":revision}
        first=self.command("suspend",request,key)
        second=self.command("suspend",request,key)
        self.assertEqual(first,second)
        self.assertEqual(self.state()["revision"],first["revision"])
        self.assertEqual(self.db.execute("select count(*) from public.commercial_access_events where tenant_id=%s",(self.tenant,)).fetchone()[0],1)

    def test_payment_replay_preserves_original_quote_after_catalog_change(self):
        now=datetime.now(timezone.utc); key=str(uuid4())
        request={"reason":"Synthetic payment", "expected_revision":self.state()["revision"],
            "plan_id":"business","valid_from":now.isoformat(),"valid_until":(now+timedelta(days=30)).isoformat(),
            "method":"cash","actual_minor":2500,"currency":"USD","billing_months":1,"paid_at":now.isoformat(),
            "receipt_reference":"SYNTHETIC-RETRY"}
        first=self.command("manual_payment",request,key)
        again=self.command("manual_payment",request,key,quote={"expected_minor":3000,"catalog_version":"later"})
        self.assertEqual(first,again)
        self.assertEqual(self.db.execute("select count(*) from public.commercial_manual_payments where tenant_id=%s",(self.tenant,)).fetchone()[0],1)

    def test_key_reuse_different_payload_or_operation_conflicts(self):
        key=str(uuid4()); self.command("suspend",key=key)
        with self.assertRaises(psycopg.errors.UniqueViolation): self.command("suspend",{"reason":"Different review"},key)
        with self.assertRaises(psycopg.errors.UniqueViolation): self.command("reactivate",key=key)

    def test_stale_revision_no_mutation(self):
        revision=self.state()["revision"]; self.command("suspend")
        with self.assertRaises(psycopg.errors.SerializationFailure): self.command("reactivate",{"expected_revision":revision})
        self.assertIsNotNone(self.state()["commercial_suspended_at"])

    def test_opposite_concurrent_commands_have_one_winner(self):
        revision=self.state()["revision"]
        def run(operation):
            with psycopg.connect(DSN,autocommit=True) as db:
                try:
                    self.command(operation,{"expected_revision":revision},db=db)
                    return "success"
                except psycopg.errors.SerializationFailure:
                    return "stale"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(run,["suspend","reactivate"]))
        self.assertCountEqual(results,["success","stale"])
        self.assertEqual(self.state()["revision"],revision+1)

    def test_paid_period_and_auth_membership_untouched_by_hold(self):
        self.grant(payment=True)
        period=self.db.execute("select to_jsonb(p) from public.commercial_access_periods p where tenant_id=%s",(self.tenant,)).fetchone()[0]
        users=self.db.execute("select jsonb_agg(to_jsonb(u)) from public.users u").fetchone()[0]
        memberships=self.db.execute("select jsonb_agg(to_jsonb(m)) from public.tenant_memberships m").fetchone()[0]
        self.command("suspend"); self.command("reactivate")
        self.assertEqual(period,self.db.execute("select to_jsonb(p) from public.commercial_access_periods p where tenant_id=%s",(self.tenant,)).fetchone()[0])
        self.assertEqual(users,self.db.execute("select jsonb_agg(to_jsonb(u)) from public.users u").fetchone()[0])
        self.assertEqual(memberships,self.db.execute("select jsonb_agg(to_jsonb(m)) from public.tenant_memberships m").fetchone()[0])
        self.assertIsNotNone(self.state()["period"])

    def test_expired_period_not_restored(self):
        self.grant(expired=True); self.command("suspend"); self.command("reactivate")
        self.assertIsNone(self.state()["period"])
        self.assertTrue(self.state()["has_history"])

    def test_future_dated_grant_is_inactive_until_start(self):
        now=datetime.now(timezone.utc)
        self.command("complimentary", {"plan_id":"business", "valid_from":(now+timedelta(days=1)).isoformat(),
            "valid_until":(now+timedelta(days=2)).isoformat()})
        state=self.state()
        self.assertIsNone(state["period"])
        self.assertEqual(state["access_state"],"inactive")
        self.assertIsNotNone(state["next_transition_at"])

    def test_overlap_constraint_preserved(self):
        self.grant()
        with self.assertRaises(psycopg.errors.ExclusionViolation): self.grant()
        self.assertEqual(self.db.execute("select count(*) from public.commercial_access_periods where tenant_id=%s",(self.tenant,)).fetchone()[0],1)

    def test_history_and_audit_context_immutable(self):
        self.grant(payment=True); self.command("suspend"); self.command("reactivate")
        actions=self.db.execute("select action,metadata from public.audit_logs where tenant_id=%s order by created_at",(self.tenant,)).fetchall()
        self.assertEqual([a[0] for a in actions],["admin.commercial.manual_payment","admin.commercial.suspend","admin.commercial.reactivate"])
        context=actions[1][1]
        for field in ("aal","request_id","idempotency_key","previous_revision","revision","previous_state","resulting_state","reason","reference","actor_role"):
            self.assertIn(field,context)
        self.assertIsNone(context["previous_state"]["commercial_suspended_at"])
        self.assertIsNotNone(context["resulting_state"]["commercial_suspended_at"])
        for table in ("commercial_manual_payments","commercial_access_events"):
            with self.assertRaises(psycopg.errors.InsufficientPrivilege): self.db.execute(f"delete from public.{table} where tenant_id=%s",(self.tenant,))

    def test_real_payment_assignment_hold_and_restoration_reach_runtime_resolver(self):
        # Real ledger snapshot through the actual application resolver, with a
        # local SQL adapter replacing only the HTTP transport to PostgREST.
        from services import commercial_access_service, entitlement_service
        self.db.execute("select public.assign_commercial_subscription(%s,'business','active','synthetic',2500,%s,'Synthetic assignment',%s)",
                        (self.tenant,self.actor,str(uuid4())))
        class LocalLedger:
            def rpc(inner, name, params):
                self.assertEqual(name,"resolve_commercial_access")
                state=self.db.execute("select public.resolve_commercial_access(%s)",(params["p_tenant_id"],)).fetchone()[0]
                return SimpleNamespace(execute=lambda: SimpleNamespace(data=state))
        with patch.object(commercial_access_service,"service_supabase",LocalLedger()), patch.dict(os.environ,{
            "COMMERCIAL_ENTITLEMENT_TEST_LOOKUPS":"true","COMMERCIAL_ENTITLEMENTS_ENFORCED":"true"}):
            self.assertEqual(entitlement_service.get_tenant_entitlements(self.tenant)["capabilities"],[])
            self.grant(payment=True)
            self.assertEqual(entitlement_service.get_tenant_entitlements(self.tenant)["commercial_denial_code"],"commercial_review_required")
            before=self.state()["revision"]; self.command("suspend")
            self.assertEqual(entitlement_service.get_tenant_entitlements(self.tenant)["commercial_denial_code"],"commercial_access_suspended")
            self.command("reactivate")
            restored=entitlement_service.get_tenant_entitlements(self.tenant)
            self.assertEqual(restored["commercial_denial_code"],"commercial_review_required")
            self.assertEqual(restored["commercial_revision"],before+2)

    def test_expiry_changes_snapshot_without_revision_or_job(self):
        now=datetime.now(timezone.utc)
        self.command("complimentary", {"plan_id":"business", "valid_from":(now-timedelta(seconds=1)).isoformat(),
            "valid_until":(now+timedelta(seconds=1)).isoformat()})
        self.assertIsNotNone(self.state()["period"])
        revision=self.state()["revision"]
        time.sleep(1.1)
        state=self.state()
        self.assertIsNone(state["period"])
        self.assertEqual(state["access_state"],"expired")
        self.assertEqual(state["revision"],revision)

    def test_payment_correction_appends_without_rewriting_evidence(self):
        first=self.grant(payment=True)
        original=self.db.execute("select to_jsonb(p) from public.commercial_manual_payments p where id=%s",(first["payment_id"],)).fetchone()[0]
        correction={"payment_id":first["payment_id"],"actual_minor":2500,"paid_at":datetime.now(timezone.utc).isoformat(),"receipt_reference":"SYNTHETIC-CORRECTION"}
        result=self.command("correct_payment",correction)
        self.assertEqual(original,self.db.execute("select to_jsonb(p) from public.commercial_manual_payments p where id=%s",(first["payment_id"],)).fetchone()[0])
        self.assertEqual(self.db.execute("select corrects_payment_id::text from public.commercial_manual_payments where id=%s",(result["payment_id"],)).fetchone()[0],first["payment_id"])
        self.assertEqual(self.db.execute("select count(*) from public.commercial_access_periods where tenant_id=%s",(self.tenant,)).fetchone()[0],1)
        with self.assertRaises(psycopg.errors.UniqueViolation): self.command("correct_payment",correction)

    def test_financial_deletion_protection_preserved(self):
        self.grant(payment=True)
        with self.assertRaises(psycopg.errors.RaiseException): self.db.execute("update public.tenants set lifecycle_state='deletion_pending' where tenant_id=%s",(self.tenant,))
        with self.assertRaises(psycopg.errors.ForeignKeyViolation): self.db.execute("delete from public.tenants where tenant_id=%s",(self.tenant,))



@unittest.skipUnless(DSN, "Requires disposable PostgreSQL commercial rehearsal")
class ModuleCommercialDatabaseTests(unittest.TestCase):
    command=CommercialLedgerDatabaseTests.command
    state=CommercialLedgerDatabaseTests.state

    def setUp(self):
        CommercialLedgerDatabaseTests.setUp(self)
        self.db.execute("begin")
        raw = self.db
        class SavepointDB:
            # Expected constraint failures must not abort the surrounding
            # fixture rollback transaction. Production code is unchanged.
            def execute(inner, query, params=None):
                if query.lower().strip() == "rollback":
                    return raw.execute(query)
                raw.execute("savepoint fixture_statement")
                try:
                    result=raw.execute(query,params)
                except Exception:
                    raw.execute("rollback to savepoint fixture_statement")
                    raw.execute("release savepoint fixture_statement")
                    raise
                raw.execute("release savepoint fixture_statement")
                return result
        self.db=SavepointDB()
        self.addCleanup(lambda:self.db.execute("rollback"))
        self.db.execute("update public.commercial_price_books set sales_start_at=statement_timestamp()-interval '1 second' where id='launch_2026'")

    def assign(self, modules, books=None):
        return self.command("assign_modules",{"module_ids":modules,"price_books":books or {}})

    def basis(self):
        return next(row['module_basis'] for row in self.state()['subscriptions'] if row['state']=='active')

    def quote(self):
        return self.db.execute("select public.resolve_module_price(%s)",(Jsonb(self.basis()),)).fetchone()[0]

    def pay(self, modules):
        now=datetime.now(timezone.utc)
        return self.command("manual_payment",{"module_ids":modules,"valid_from":now.isoformat(),"valid_until":(now+timedelta(days=30)).isoformat(),
            "method":"cash","actual_minor":self.quote()['recurring_minor'],"currency":"USD","billing_months":1,"paid_at":now.isoformat(),"receipt_reference":"SYNTHETIC-V2"})

    def close_launch(self):
        self.db.execute("update public.commercial_price_books set sales_end_at=statement_timestamp() where id='launch_2026'")

    def test_all_seven_bundle_prices_order_and_empty(self):
        from itertools import combinations
        for n in (1,2,3):
            for modules in combinations(('forms','website','ecommerce'),n):
                self.assign(list(reversed(modules)))
                expected=({'forms':1500,'website':2000,'ecommerce':2000}[modules[0]] if n==1 else {2:3000,3:4000}[n])
                self.assertEqual(self.quote()['recurring_minor'],expected)
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            self.db.execute("select public.resolve_module_price('{}')")

    def test_grandfather_single_pair_three_after_close_and_hold(self):
        acquired=[]
        for modules,amount in ((['website'],2000),(['forms','website'],3000),(['forms','website','ecommerce'],4000)):
            # Independent tenant for each acquisition, within this transaction.
            if self.state()['subscriptions']:
                self.tenant=self.db.execute("insert into public.tenants(brand_name,owner_name) values('Synthetic','Synthetic') returning tenant_id").fetchone()[0]
            self.assign(modules); self.pay(modules)
            self.command('suspend'); self.command('reactivate')
            self.assertEqual(self.quote()['recurring_minor'],amount)
            self.assertTrue(all(value['paid_since'] for value in self.basis().values()))
            acquired.append((self.tenant,amount))
        self.close_launch()
        for tenant,amount in acquired:
            self.tenant=tenant
            self.assertEqual(self.quote()['recurring_minor'],amount)
        self.assertEqual(self.quote()['recurring_minor'],4000)
        self.assign(['forms','website'])
        self.assertEqual(self.quote()['recurring_minor'],3000)
        self.assertNotIn('ecommerce',self.basis())
        with self.assertRaises(psycopg.errors.InvalidParameterValue):self.assign(['forms','website','ecommerce'])

    def test_mixed_book_readd_uses_current_basis_no_cross_discount(self):
        self.assign(['forms','website','ecommerce']);self.pay(['forms','website','ecommerce']);self.close_launch()
        self.assign(['forms','website'])
        self.db.execute("insert into public.commercial_price_books(id,version,effective_from,currency,billing_interval,standalone_minor,sales_start_at) values('synthetic_future','test',statement_timestamp()-interval '1 day','USD','month','{\"ecommerce\":2700}',statement_timestamp()-interval '1 second')")
        self.assign(['forms','website','ecommerce'])
        price=self.quote()
        self.assertEqual(price['recurring_minor'],5700)
        self.assertEqual(self.basis()['ecommerce']['price_book_id'],'synthetic_future')
        self.assertIsNone(self.basis()['ecommerce']['paid_since'])
        self.assertEqual(len(price['price_groups']),2)
        self.assertEqual(self.state()['period']['price_snapshot']['recurring_minor'],4000)

    def test_add_while_open_and_full_cancel_forfeits_rights(self):
        self.assign(['website']);self.pay(['website']);self.assign(['forms','website'])
        self.assertEqual(self.quote()['recurring_minor'],3000)
        self.assertIsNone(self.basis()['forms']['paid_since'])
        self.assign([]);self.command('suspend');self.command('reactivate');self.close_launch()
        self.assertFalse(any(row['state']=='active' for row in self.state()['subscriptions']))
        with self.assertRaises(psycopg.errors.InvalidParameterValue):self.assign(['website'])

    def test_snapshot_immutable_and_module_order_idempotent_stale_conflict(self):
        key=str(uuid4()); revision=self.state()['revision']
        first=self.command('assign_modules',{'module_ids':['website','forms'],'expected_revision':revision},key)
        replay=self.command('assign_modules',{'module_ids':['forms','website'],'expected_revision':revision},key)
        self.assertEqual(first,replay)
        with self.assertRaises(psycopg.errors.UniqueViolation):self.command('assign_modules',{'module_ids':['ecommerce'],'expected_revision':revision},key)
        with self.assertRaises(psycopg.errors.SerializationFailure):self.command('assign_modules',{'module_ids':['ecommerce'],'expected_revision':revision})
        paid=self.pay(['forms','website'])
        snap=self.db.execute('select price_snapshot from public.commercial_manual_payments where id=%s',(paid['payment_id'],)).fetchone()[0]
        for field in ('tenant_id','module_ids','price_groups','catalog_version','currency','billing_interval','recurring_minor','effective_from','effective_until','reference','previous_revision','revision','addons'):
            self.assertIn(field,snap)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):self.db.execute("update public.commercial_price_books set standalone_minor='{\"forms\":9000}' where id='launch_2026'")
        self.assertEqual(snap,self.db.execute('select price_snapshot from public.commercial_manual_payments where id=%s',(paid['payment_id'],)).fetchone()[0])
        self.assertIn('price_snapshot',paid)

    def test_complimentary_does_not_create_paid_lock_and_does_not_restore_cancelled(self):
        self.assign(['website','ecommerce'])
        now=datetime.now(timezone.utc)
        self.command('complimentary',{'module_ids':['website','ecommerce'],'valid_from':now.isoformat(),'valid_until':(now+timedelta(days=1)).isoformat()})
        self.assertTrue(all(value['paid_since'] is None for value in self.basis().values()))
        self.assign(['website']);self.command('suspend');self.command('reactivate')
        self.assertEqual(set(self.basis()),{'website'})
        self.assertEqual(self.state()['period']['module_ids'],['ecommerce','website'])

    def test_paid_module_runtime_removal_hold_and_second_tenant(self):
        from services import entitlement_service as ent
        with patch.dict(os.environ,{"COMMERCIAL_ENTITLEMENTS_ENFORCED":"true"}):
            self.assign(['website','ecommerce']);self.pay(['website','ecommerce'])
            active=ent.get_tenant_entitlements(self.tenant,commercial_snapshot=self.state())
            self.assertIn('ecommerce',active['capabilities']);self.assertIn('website_publish',active['capabilities'])
            self.assign(['website']);self.command('suspend');self.command('reactivate')
            restored=ent.get_tenant_entitlements(self.tenant,commercial_snapshot=self.state())
            self.assertIn('website_publish',restored['capabilities']);self.assertNotIn('ecommerce',restored['capabilities'])
            first=self.tenant;self.command('suspend')
            self.tenant=self.db.execute("insert into public.tenants(brand_name,owner_name) values('Second synthetic','Synthetic') returning tenant_id").fetchone()[0]
            self.assign(['ecommerce']);self.pay(['ecommerce'])
            self.assertIn('ecommerce',ent.get_tenant_entitlements(self.tenant,commercial_snapshot=self.state())['capabilities'])
            self.tenant=first
            self.assertEqual(ent.get_tenant_entitlements(first,commercial_snapshot=self.state())['commercial_denial_code'],'commercial_access_suspended')

    def test_prepared_price_book_assignment_no_paid_right_before_activation(self):
        self.db.execute("insert into public.commercial_price_books(id,version,effective_from,currency,billing_interval,standalone_minor) values('synthetic_prepared','test',statement_timestamp()-interval '1 day','USD','month',%s)",(Jsonb({'website':2000}),))
        self.assign(['website'],{'website':'synthetic_prepared'})
        with self.assertRaises(psycopg.errors.InvalidParameterValue):self.pay(['website'])
        self.assertIsNone(self.basis()['website']['paid_since'])
        self.assertFalse(self.quote()['price_groups'][0]['new_sales_active'])

    def test_access_period_evidence_and_price_books_privileges(self):
        self.assign(['website']);paid=self.pay(['website'])
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):self.db.execute("update public.commercial_access_periods set price_snapshot='{}' where id=%s",(paid['period_id'],))
        for role in ('anon','authenticated','service_role'):
            self.assertFalse(self.db.execute("select has_table_privilege(%s,'public.commercial_price_books','UPDATE')",(role,)).fetchone()[0])
        self.assertTrue(self.db.execute("select relrowsecurity from pg_class where oid='public.commercial_price_books'::regclass").fetchone()[0])

    def test_user_safety_scope_accepts_advertised_5gib_and_downgrade_preserves_usage(self):
        gib=1024**3
        self.db.execute("insert into public.storage_accounts(tenant_id,scope_key,user_id,quota_bytes,used_bytes) values(%s,%s,%s,%s,%s)",(self.tenant,'user:'+str(self.actor),self.actor,gib,gib))
        reservation=self.db.execute("select public.reserve_storage_bytes(%s,%s,'dataset',%s,%s,%s)",(self.tenant,self.actor,2*gib,5*gib,5*gib)).fetchone()[0]
        self.assertIsNotNone(reservation)
        with self.assertRaises(psycopg.errors.RaiseException):self.db.execute("select public.reserve_storage_bytes(%s,%s,'dataset',1,%s,%s)",(self.tenant,self.actor,gib,gib))
        self.assertEqual(self.db.execute("select used_bytes from public.storage_accounts where tenant_id=%s and scope_key=%s",(self.tenant,'user:'+str(self.actor))).fetchone()[0],gib)


if __name__ == "__main__":
    unittest.main(verbosity=2)
