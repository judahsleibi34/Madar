"""SQL behavior and ordering tests on a marked, disposable local database only."""
import json
import os
import unittest
from uuid import uuid4
import psycopg
from psycopg.conninfo import conninfo_to_dict

DSN = os.getenv("ELEARNING_SYNTHETIC_DATABASE_DSN")


@unittest.skipUnless(DSN, "Requires a marked disposable local E-Learning database")
class ELearningStructureDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if conninfo_to_dict(DSN).get("host") not in {"localhost", "127.0.0.1", "::1"}: raise RuntimeError("Requires loopback database")
        with psycopg.connect(DSN) as db:
            marker = db.execute("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()").fetchone()[0]
            if marker != "madar-elearning-synthetic-rehearsal": raise RuntimeError("Requires disposable marked database")

    def setUp(self):
        self.db = psycopg.connect(DSN); self.addCleanup(self.db.close)
        self.tenant = self.db.execute("insert into public.tenants(brand_name,owner_name) values('Structure test','Local') returning tenant_id").fetchone()[0]
        auth = uuid4()
        self.db.execute("insert into auth.users(id,email) values(%s,%s)", (auth, f"{auth}@example.com"))
        self.user = self.db.execute("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified) values(%s,'Structure','Test',%s,%s,'active',true) returning id", (auth, f"{auth}@example.com", self.tenant)).fetchone()[0]
        self.db.execute("insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'owner','active')", (self.tenant,self.user,auth))
        self.course = self.db.execute("insert into public.elearning_courses(tenant_id,name) values(%s,'Structure test') returning id",(self.tenant,)).fetchone()[0]
        self.revision = 1

    def run_command(self, action, entity=None, payload=None, revision=None):
        result = self.db.execute("select public.manage_elearning_structure(%s,%s,%s,%s,%s,%s,%s::jsonb)", (self.tenant,self.course,self.user,revision if revision is not None else self.revision,action,entity,json.dumps(payload or {}))).fetchone()[0]
        self.revision = result["revision"]
        self.db.execute("set constraints all immediate")
        self.db.execute("set constraints all deferred")
        return result

    def section(self, name):
        return self.run_command("create_section", payload={"name":name})["sections"][-1]["id"]

    def lesson(self, section, name):
        data = self.run_command("create_lesson", payload={"section_id":section,"name":name})
        return next(s for s in data["sections"] if s["id"]==section)["lessons"][-1]["id"]

    def assert_positions(self, data):
        self.assertEqual([s["position"] for s in data["sections"]], list(range(len(data["sections"]))))
        for section in data["sections"]:
            self.assertEqual([l["position"] for l in section["lessons"]],list(range(len(section["lessons"]))))

    def test_order_move_duplicate_delete_and_counts(self):
        a,b = self.section("A"),self.section("B")
        l1,l2 = self.lesson(a,"One"),self.lesson(a,"Two")
        data = self.run_command("reorder_lesson",l2,{"direction":"up"})
        self.assertEqual(data["sections"][0]["lessons"][0]["id"],l2)
        data = self.run_command("move_lesson",l1,{"section_id":b})
        self.assertEqual(data["sections"][1]["lessons"][0]["id"],l1)
        self.assert_positions(data)
        data = self.run_command("duplicate_section",a)
        self.assertEqual(data["sections"][-1]["lessons"][0]["name"],"Two")
        self.assertNotEqual(data["sections"][-1]["lessons"][0]["id"],l2)
        self.assertEqual(data["sections"][-1]["lessons"][0]["status"],"draft")
        data = self.run_command("duplicate_lesson",l1)
        self.assertEqual(len(data["sections"][1]["lessons"]),2)
        self.assertEqual(data["lesson_count"],4)
        data = self.run_command("reorder_section",b,{"direction":"up"})
        self.assertEqual(data["sections"][0]["id"],b)
        self.assert_positions(data)
        data = self.run_command("delete_lesson",l2,{"confirmed":True})
        data = self.run_command("delete_section",a,{"confirmed":True})
        self.assert_positions(data)

    def test_archive_preserves_children_restore_and_safe_delete(self):
        section = self.section("Section"); lesson = self.lesson(section,"Lesson")
        with self.assertRaisesRegex(psycopg.errors.RaiseException,"elearning_section_not_empty"):
            with self.db.transaction(): self.run_command("delete_section",section,{"confirmed":True})
        data = self.run_command("archive_section",section)
        self.assertEqual(data["lesson_count"],0); self.assertEqual(data["section_count"],0)
        self.assertEqual(data["sections"][0]["lessons"][0]["id"],lesson)
        self.assertIsNotNone(data["sections"][0]["archived_at"])
        data = self.run_command("update_section",section,{"name":"Restored","status":"published"})
        self.assertEqual(data["lesson_count"],1); self.assertIsNone(data["sections"][0]["archived_at"])
        data = self.run_command("archive_lesson",lesson)
        self.assertEqual(data["lesson_count"],0)
        with self.assertRaisesRegex(psycopg.errors.InvalidParameterValue,"confirmation_required"):
            with self.db.transaction(): self.run_command("delete_lesson",lesson)

    def test_stale_revision_tenant_and_cross_course_rejected_atomically(self):
        a = self.section("A")
        with self.assertRaisesRegex(psycopg.errors.RaiseException,"elearning_structure_conflict"):
            with self.db.transaction(): self.run_command("create_section",payload={"name":"Stale"},revision=1)
        other = self.db.execute("insert into public.elearning_courses(tenant_id,name) values(%s,'Other') returning id",(self.tenant,)).fetchone()[0]
        with self.assertRaises(psycopg.errors.NoDataFound):
            with self.db.transaction():
                self.db.execute("select public.manage_elearning_structure(%s,%s,%s,1,'update_section',%s,'{\"name\":\"Stolen\"}'::jsonb)",(self.tenant,other,self.user,a))
        with self.assertRaises(psycopg.errors.NoDataFound):
            with self.db.transaction():
                self.db.execute("select public.get_elearning_structure(%s,%s)",(self.tenant+10000,self.course))
        self.assertEqual(self.db.execute("select structure_revision from public.elearning_courses where id=%s",(self.course,)).fetchone()[0],self.revision)

    def test_rpc_only_mutations_and_client_access_denied(self):
        for table in ('elearning_sections','elearning_lessons'):
            for role in ('anon','authenticated'):
                self.assertFalse(self.db.execute("select has_table_privilege(%s,%s,'SELECT,INSERT,UPDATE,DELETE')",(role,'public.'+table)).fetchone()[0])
            self.assertFalse(self.db.execute("select has_table_privilege('service_role',%s,'INSERT,UPDATE,DELETE')",('public.'+table,)).fetchone()[0])
        for role in ('anon','authenticated'):
            self.assertFalse(self.db.execute("select has_function_privilege(%s,'public.manage_elearning_structure(integer,uuid,integer,integer,text,uuid,jsonb)','EXECUTE')",(role,)).fetchone()[0])

    def test_concurrent_commands_have_one_winner_and_no_lost_ordering(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        # This test's fixtures are committed only inside the disposable rehearsal.
        self.db.commit()
        barrier = Barrier(2)
        def create(name):
            with psycopg.connect(DSN) as db:
                barrier.wait(timeout=5)
                try:
                    db.execute("select public.manage_elearning_structure(%s,%s,%s,1,'create_section',null,%s::jsonb)", (self.tenant,self.course,self.user,json.dumps({"name":name})))
                    return "created"
                except psycopg.errors.RaiseException as error:
                    if "elearning_structure_conflict" not in str(error): raise
                    return "conflict"
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(create,name) for name in ('Concurrent A','Concurrent B')]
            self.assertEqual(sorted(future.result(timeout=10) for future in futures),['conflict','created'])
        data = self.db.execute("select public.get_elearning_structure(%s,%s)",(self.tenant,self.course)).fetchone()[0]
        self.assertEqual(data["revision"],2)
        self.assertEqual(len(data["sections"]),1)
        self.assert_positions(data)
