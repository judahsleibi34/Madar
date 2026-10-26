"""Schema-146 revised launch price-book regressions on disposable PostgreSQL."""
import os
import unittest
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
from tests.disposable_database_support import connect_disposable_database


DSN = os.getenv("COMMERCIAL_SYNTHETIC_DATABASE_DSN")
DISPOSABLE_MARKERS = frozenset({"madar-price-book-synthetic-rehearsal", "madar-hardening-synthetic-146"})


@unittest.skipUnless(DSN, "Requires disposable PostgreSQL commercial rehearsal")
class RevisedLaunchPriceBookDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = connect_disposable_database(DSN, markers=DISPOSABLE_MARKERS)
        self.addCleanup(self.db.close)

    def book(self, book_id):
        return self.db.execute(
            "select standalone_minor,bundle_minor,sales_start_at,sales_end_at,currency,billing_interval "
            "from public.commercial_price_books where id=%s",
            (book_id,),
        ).fetchone()

    def test_schema_146_records_the_revised_prepared_book(self):
        self.assertEqual(self.db.execute(
            "select schema_version from public.application_schema_state where contract_key='core'"
        ).fetchone()[0], 146)
        standalone, bundles, start, end, currency, interval = self.book("launch_2026_v2")
        self.assertEqual(standalone, {"forms": 1500, "website": 2000, "ecommerce": 2500})
        self.assertEqual(bundles, {"2": 3000, "3": 4000})
        self.assertEqual((start, end, currency, interval), (None, None, "USD", "month"))

    def test_superseded_book_is_preserved_but_cannot_open(self):
        standalone, bundles, start, _end, _currency, _interval = self.book("launch_2026")
        self.assertEqual(standalone, {"forms": 1500, "website": 2000, "ecommerce": 2000})
        self.assertEqual(bundles, {"2": 3000, "3": 4000})
        self.assertIsNone(start)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege) as error:
            self.db.execute(
                "update public.commercial_price_books set sales_start_at=clock_timestamp() where id='launch_2026'"
            )
        self.assertIn("commercial_price_book_retired", str(error.exception))

    def test_price_book_amounts_remain_immutable(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.db.execute(
                "update public.commercial_price_books set standalone_minor=%s where id='launch_2026_v2'",
                (Jsonb({"forms": 1500, "website": 2000, "ecommerce": 2000}),),
            )
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.db.execute("delete from public.commercial_price_books where id='launch_2026_v2'")

    def test_opened_revised_book_quotes_commerce_and_unchanged_bundles(self):
        # Activation is a governed production step; here it is rolled back.
        windows_before = self.db.execute(
            "select id,sales_start_at,sales_end_at from public.commercial_price_books order by id"
        ).fetchall()
        with connect_disposable_database(DSN, markers=DISPOSABLE_MARKERS, autocommit=False) as db:
            # Continuity regressions deliberately create open synthetic books.
            # Isolate this automatic-selection assertion from those newer books
            # inside the same rollback transaction; preserve every price fact.
            db.execute(
                "update public.commercial_price_books set sales_end_at=clock_timestamp() "
                "where id ~ '^(old|current|second)_[0-9a-f]{20}$' "
                "and sales_start_at is not null and sales_end_at is null"
            )
            tenant = db.execute(
                "insert into public.tenants(brand_name,owner_name) values(%s,'Synthetic') returning tenant_id",
                ("Price book " + uuid4().hex,),
            ).fetchone()[0]
            db.execute(
                "update public.commercial_price_books set sales_start_at=clock_timestamp()-interval '1 minute' "
                "where id='launch_2026_v2'"
            )
            quote = lambda modules: db.execute(
                "select public.quote_commercial_modules(%s,%s)",
                (tenant, Jsonb({"module_ids": modules, "price_books": {}})),
            ).fetchone()[0]
            commerce = quote(["ecommerce"])
            self.assertEqual(commerce["pricing"]["recurring_minor"], 2500)
            self.assertEqual(commerce["module_basis"]["ecommerce"]["price_book_id"], "launch_2026_v2")
            self.assertEqual(quote(["forms"])["pricing"]["recurring_minor"], 1500)
            self.assertEqual(quote(["website"])["pricing"]["recurring_minor"], 2000)
            for pair in (["forms", "website"], ["forms", "ecommerce"], ["website", "ecommerce"]):
                self.assertEqual(quote(pair)["pricing"]["recurring_minor"], 3000)
            self.assertEqual(quote(["forms", "website", "ecommerce"])["pricing"]["recurring_minor"], 4000)
            db.rollback()
        self.assertIsNone(self.book("launch_2026_v2")[2])
        self.assertEqual(self.db.execute(
            "select id,sales_start_at,sales_end_at from public.commercial_price_books order by id"
        ).fetchall(), windows_before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
