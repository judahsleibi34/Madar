"""Schema-145 strict paid-continuity regressions on disposable PostgreSQL."""
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb


DSN = os.getenv("COMMERCIAL_SYNTHETIC_DATABASE_DSN")
MODULES = ["forms", "website", "ecommerce"]


@unittest.skipUnless(DSN, "Requires disposable PostgreSQL commercial rehearsal")
class StrictPaidContinuityDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = psycopg.connect(DSN, autocommit=True)
        self.addCleanup(self.db.close)
        token = uuid4().hex
        self.tenant = self.db.execute(
            "insert into public.tenants(brand_name,owner_name) values(%s,'Synthetic') returning tenant_id",
            ("Continuity " + token,),
        ).fetchone()[0]
        auth_id = uuid4()
        self.db.execute("insert into auth.users(id,email_confirmed_at) values(%s,now())", (auth_id,))
        self.actor = self.db.execute(
            "insert into public.users(auth_id,first_name,last_name,email,user_type,account_status,email_verified,email_verified_at) "
            "values(%s,'Continuity','Admin',%s,'admin','active',true,now()) returning id",
            (auth_id, token + "@example.invalid"),
        ).fetchone()[0]
        self.old_book = "old_" + token[:20]
        self.current_book = "current_" + token[:20]
        self._book(self.old_book, effective_offset="-3 days")

    def _book(self, book_id, *, effective_offset="-1 day", prices=None):
        prices = prices or {"forms": 1500, "website": 2000, "ecommerce": 2000}
        self.db.execute(
            "insert into public.commercial_price_books"
            "(id,version,effective_from,currency,billing_interval,standalone_minor,bundle_minor,sales_start_at) "
            "values(%s,%s,clock_timestamp()+(%s)::interval,'USD','month',%s,%s,clock_timestamp()+(%s)::interval)",
            (book_id, book_id, effective_offset, Jsonb(prices), Jsonb({"2": 3000, "3": 4000}), effective_offset),
        )

    def state(self, db=None):
        return (db or self.db).execute(
            "select public.resolve_commercial_access(%s)", (self.tenant,)
        ).fetchone()[0]

    def command(self, operation, request, *, key=None, revision=None, db=None, actor=None, aal="aal2"):
        db = db or self.db
        body = {"reason": "Synthetic strict continuity", "expected_revision": revision or self.state(db)["revision"], **request}
        return db.execute(
            "select public.apply_commercial_access_command(%s,%s,%s,%s,%s,%s,%s)",
            (self.tenant, actor or self.actor, aal, operation, key or str(uuid4()),
             "continuity-test", Jsonb({"request": body, "quote": {}})),
        ).fetchone()[0]

    def assign(self, modules=MODULES, *, books=None, db=None, revision=None):
        books = books or {module: self.old_book for module in modules}
        return self.command("assign_modules", {"module_ids": modules, "price_books": books},
                            db=db, revision=revision)

    def pay(self, start, end, *, modules=MODULES, db=None, revision=None, key=None):
        return self.command("manual_payment", {
            "module_ids": modules, "valid_from": start.isoformat(), "valid_until": end.isoformat(),
            "method": "cash", "actual_minor": 4000, "currency": "USD", "billing_months": 1,
            "paid_at": datetime.now(timezone.utc).isoformat(), "receipt_reference": str(uuid4()),
            "override_reason": "Synthetic amount override",
        }, db=db, revision=revision, key=key)

    def close_old(self):
        self.db.execute(
            "update public.commercial_price_books set sales_end_at=clock_timestamp() where id=%s",
            (self.old_book,),
        )

    def active_basis(self):
        return self.db.execute(
            "select module_basis from public.tenant_subscriptions where tenant_id=%s and state='active'",
            (self.tenant,),
        ).fetchone()[0]

    def seed_paid(self, *, start=None, end=None, modules=MODULES):
        now = datetime.now(timezone.utc)
        start = start or now - timedelta(days=1)
        end = end or now + timedelta(days=1)
        self.assign(modules)
        result = self.pay(start, end, modules=modules)
        self.close_old()
        return result

    def test_failed_future_renewal_does_not_shorten_paid_coverage(self):
        now = datetime.now(timezone.utc)
        first = self.seed_paid(start=now - timedelta(hours=1), end=now + timedelta(hours=2))
        before = self.db.execute(
            "select valid_from,valid_until,price_snapshot from public.commercial_access_periods where id=%s",
            (first["period_id"],),
        ).fetchone()
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            self.pay(now + timedelta(hours=3), now + timedelta(hours=4))
        after = self.db.execute(
            "select valid_from,valid_until,price_snapshot from public.commercial_access_periods where id=%s",
            (first["period_id"],),
        ).fetchone()
        self.assertEqual(after, before)
        self.assertEqual(self.state()["access_state"], "active")

    def test_exact_boundary_expires_access_and_grandfathering(self):
        now = datetime.now(timezone.utc)
        self.seed_paid(start=now - timedelta(hours=2), end=now - timedelta(hours=1))
        basis = self.active_basis()
        boundary = now - timedelta(hours=1)
        for module in MODULES:
            self.assertIsNone(self.db.execute(
                "select public.commercial_paid_continuity_end(%s,%s,%s,%s)",
                (self.tenant, module, self.old_book, boundary),
            ).fetchone()[0])
        self.assertEqual(self.state()["access_state"], "expired")
        self.assertEqual(
            self.db.execute("select public.inspect_tenant_module_price(%s,%s)",
                            (self.tenant, Jsonb(basis))).fetchone()[0]["pricing_status"],
            "review_required",
        )

    def test_adjacent_advance_renewal_preserves_all_founding_modules(self):
        now = datetime.now(timezone.utc)
        boundary = now + timedelta(hours=2)
        self.assign()
        self.pay(now - timedelta(hours=1), boundary)
        self.pay(boundary, boundary + timedelta(days=1))
        self.close_old()
        quote = self.db.execute(
            "select public.quote_commercial_modules(%s,%s)",
            (self.tenant, Jsonb({"module_ids": MODULES})),
        ).fetchone()[0]
        self.assertTrue(all(group["grandfathered"] for group in quote["pricing"]["price_groups"]))
        self.assertEqual(quote["pricing"]["module_ids"], sorted(MODULES))

    def test_late_payment_rejected_and_ordinary_resubscription_uses_open_book(self):
        now = datetime.now(timezone.utc)
        self.seed_paid(start=now - timedelta(days=2), end=now - timedelta(days=1))
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            self.pay(now, now + timedelta(days=1))
        historical = self.db.execute(
            "select module_basis from public.tenant_subscriptions where tenant_id=%s order by updated_at desc limit 1",
            (self.tenant,),
        ).fetchone()[0]
        self._book(self.current_book)
        reassigned = self.assign(books={module: self.current_book for module in MODULES})
        self.assertEqual(
            {value["price_book_id"] for value in reassigned["price_snapshot"]["price_groups"]},
            {self.current_book},
        )
        self.assertEqual({value["price_book_id"] for value in historical.values()}, {self.old_book})
        self.assertEqual({value["price_book_id"] for value in self.active_basis().values()}, {self.current_book})

    def test_mixed_price_books_and_holds_preserve_periods_and_basis(self):
        second = "second_" + uuid4().hex[:20]
        self._book(second, prices={"forms": 1700, "website": 2100, "ecommerce": 2300})
        books = {"forms": self.old_book, "website": second, "ecommerce": second}
        self.assign(books=books)
        now = datetime.now(timezone.utc)
        paid = self.pay(now - timedelta(hours=1), now + timedelta(days=1))
        before_period = self.db.execute(
            "select to_jsonb(p) from public.commercial_access_periods p where id=%s", (paid["period_id"],)
        ).fetchone()[0]
        before_basis = self.active_basis()
        self.command("suspend", {})
        self.command("reactivate", {})
        self.assertEqual(before_period, self.db.execute(
            "select to_jsonb(p) from public.commercial_access_periods p where id=%s", (paid["period_id"],)
        ).fetchone()[0])
        self.assertEqual(before_basis, self.active_basis())
        self.assertEqual(len(paid["price_snapshot"]["price_groups"]), 2)

    def test_restoration_is_aal2_audited_idempotent_and_one_time(self):
        now = datetime.now(timezone.utc)
        self.seed_paid(start=now - timedelta(days=2), end=now - timedelta(days=1), modules=["forms"])
        request = {"module_ids": ["forms"], "price_books": {"forms": self.old_book},
                   "reference": "approval-ticket-145"}
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.command("restore_price_basis", request, aal="aal1")
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.command("restore_price_basis", request, actor=2147483647)
        key = str(uuid4())
        original_revision = self.state()["revision"]
        restored = self.command("restore_price_basis", request, key=key,
                                revision=original_revision)
        replay = self.command("restore_price_basis", request, key=key,
                              revision=original_revision)
        self.assertEqual(replay, restored)
        basis = self.active_basis()["forms"]
        self.assertTrue(basis["restoration_pending"])
        self.assertEqual(basis["restoration_reference"], "approval-ticket-145")
        audit = self.db.execute(
            "select metadata from public.audit_logs where tenant_id=%s and action='admin.commercial.restore_price_basis'",
            (self.tenant,),
        ).fetchone()[0]
        self.assertEqual(audit["reference"], "approval-ticket-145")
        start = datetime.now(timezone.utc) + timedelta(seconds=1)
        paid = self.pay(start, start + timedelta(days=1), modules=["forms"])
        self.assertNotIn("restoration_pending", self.active_basis()["forms"])
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            self.pay(start + timedelta(days=2), start + timedelta(days=3), modules=["forms"])
        self.assertIsNotNone(paid["period_id"])

    def test_expiration_preserves_tenant_content_and_immutable_evidence(self):
        now = datetime.now(timezone.utc)
        paid = self.seed_paid(start=now - timedelta(days=2), end=now - timedelta(days=1))
        project = uuid4()
        self.db.execute(
            "insert into public.builder_projects(id,tenant_id,name,slug,status,schema_version) "
            "values(%s,%s,'Preserved','preserved','draft',1)", (project, self.tenant),
        )
        counts = self.db.execute(
            "select (select count(*) from public.commercial_manual_payments where tenant_id=%s),"
            "(select count(*) from public.commercial_access_periods where tenant_id=%s),"
            "(select count(*) from public.builder_projects where tenant_id=%s)",
            (self.tenant, self.tenant, self.tenant),
        ).fetchone()
        self.assertEqual(self.state()["access_state"], "expired")
        self.assertEqual(counts, self.db.execute(
            "select (select count(*) from public.commercial_manual_payments where tenant_id=%s),"
            "(select count(*) from public.commercial_access_periods where tenant_id=%s),"
            "(select count(*) from public.builder_projects where tenant_id=%s)",
            (self.tenant, self.tenant, self.tenant),
        ).fetchone())
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.db.execute("delete from public.commercial_access_periods where id=%s", (paid["period_id"],))

    def test_concurrent_boundary_renewal_and_assignment_has_one_serialized_winner(self):
        now = datetime.now(timezone.utc)
        boundary = now + timedelta(seconds=1.2)
        self.assign(["website"])
        self.pay(now - timedelta(hours=1), boundary, modules=["website"])
        self.close_old()
        self._book(self.current_book)
        revision = self.state()["revision"]

        def run(kind):
            delay = max(0, (boundary - datetime.now(timezone.utc)).total_seconds())
            time.sleep(delay)
            with psycopg.connect(DSN, autocommit=True) as db:
                try:
                    if kind == "renew":
                        self.pay(boundary, boundary + timedelta(days=1), modules=["website"],
                                 db=db, revision=revision)
                    else:
                        self.assign(["website"], books={"website": self.current_book},
                                    db=db, revision=revision)
                    return "success"
                except psycopg.errors.SerializationFailure:
                    return "stale"
                except psycopg.errors.InvalidParameterValue:
                    return "continuity"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, ["renew", "assign"]))
        self.assertEqual(results.count("success"), 1)
        self.assertIn(results[0] if results[1] == "success" else results[1], {"stale", "continuity"})
        basis = self.active_basis()["website"]["price_book_id"]
        continuation = self.db.execute(
            "select public.commercial_paid_continuity_end(%s,'website',%s,clock_timestamp())",
            (self.tenant, self.old_book),
        ).fetchone()[0]
        self.assertTrue((basis == self.old_book and continuation is not None)
                        or (basis == self.current_book and continuation is None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
