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
            self.assertIn("website_publish",entitlement_service.get_tenant_entitlements(self.tenant)["capabilities"])
            before=self.state()["revision"]; self.command("suspend")
            self.assertEqual(entitlement_service.get_tenant_entitlements(self.tenant)["commercial_denial_code"],"commercial_access_suspended")
            self.command("reactivate")
            restored=entitlement_service.get_tenant_entitlements(self.tenant)
            self.assertIn("website_publish",restored["capabilities"])
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
