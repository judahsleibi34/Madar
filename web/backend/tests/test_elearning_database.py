"""Real SQL regressions, enabled only for a marked disposable local database."""
import os
import unittest

import psycopg
from psycopg.conninfo import conninfo_to_dict

DSN = os.getenv("ELEARNING_SYNTHETIC_DATABASE_DSN")


@unittest.skipUnless(DSN, "Requires disposable local E-Learning database")
class ELearningDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if conninfo_to_dict(DSN).get("host") not in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError("E-Learning SQL tests require a loopback database")
        with psycopg.connect(DSN) as db:
            marker = db.execute("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()").fetchone()[0]
            if marker != "madar-elearning-synthetic-rehearsal":
                raise RuntimeError("Database is not marked as a disposable E-Learning rehearsal")

    def setUp(self):
        self.db = psycopg.connect(DSN)
        # Roll back every test, including fixtures, rather than deleting records.
        self.addCleanup(self.db.close)
        self.tenant = self.db.execute("insert into public.tenants(brand_name,owner_name) values('Local E-Learning test','Local') returning tenant_id").fetchone()[0]

    def test_schema_and_service_only_access(self):
        self.assertGreaterEqual(self.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0], 117)
        for table in ("elearning_settings", "elearning_courses"):
            self.assertTrue(self.db.execute("select relrowsecurity from pg_class where oid=%s::regclass", (table,)).fetchone()[0])
            for role in ("anon", "authenticated"):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.db.transaction():
                        self.db.execute(f"set local role {role}")
                        self.db.execute(f"select * from public.{table}")
        self.assertFalse(self.db.execute("select has_table_privilege('service_role','public.elearning_courses','DELETE')").fetchone()[0])

    def test_settings_merge_preserves_future_keys(self):
        self.db.execute("set local role service_role")
        self.db.execute("select public.save_elearning_settings(%s, %s::jsonb)", (self.tenant, '{"course_label":"Program","future_setting":true}'))
        self.db.execute("select public.save_elearning_settings(%s, %s::jsonb)", (self.tenant, '{"course_label":"Training"}'))
        self.assertEqual(self.db.execute("select settings from public.elearning_settings where tenant_id=%s", (self.tenant,)).fetchone()[0], {"course_label": "Training", "future_setting": True})

    def test_course_defaults_revision_conflicts_and_archive(self):
        self.db.execute("set local role service_role")
        course = self.db.execute("insert into public.elearning_courses(tenant_id,name) values(%s,'Local course') returning id,status,access_type,revision", (self.tenant,)).fetchone()
        course_id = course[0]
        self.assertEqual(course[1:], ("draft", "private", 1))
        updated = self.db.execute("update public.elearning_courses set name='Updated',revision=2 where tenant_id=%s and id=%s and revision=1 returning revision", (self.tenant, course_id)).fetchall()
        self.assertEqual(updated, [(2,)])
        stale = self.db.execute("update public.elearning_courses set name='Stale',revision=2 where tenant_id=%s and id=%s and revision=1 returning id", (self.tenant, course_id)).fetchall()
        self.assertEqual(stale, [])
        self.db.execute("update public.elearning_courses set status='archived',revision=3 where id=%s", (course_id,))
        self.assertEqual(self.db.execute("select name,status,revision from public.elearning_courses where id=%s", (course_id,)).fetchone(), ("Updated", "archived", 3))

    def test_cover_cannot_reference_another_tenant(self):
        with self.assertRaises(psycopg.errors.CheckViolation):
            with self.db.transaction():
                self.db.execute("insert into public.elearning_courses(tenant_id,name,cover_asset) values(%s,'Invalid',%s)", (self.tenant, f"/uploads/tenant_{self.tenant + 1}/builder_assets/" + "a" * 32 + ".png"))
