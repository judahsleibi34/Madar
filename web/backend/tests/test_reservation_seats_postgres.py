"""Opt-in acceptance in the owned, network-isolated synthetic PostgreSQL container.
Run: MADAR_RUN_SEAT_SQL_TESTS=1 python -m unittest tests.test_reservation_seats_postgres
No installed database or migration selection is used.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest
from concurrent.futures import ThreadPoolExecutor

WEB = Path(__file__).resolve().parents[2]
CONTAINER = "madar-reservation-seats-review"
DATABASE = f"madar_seat_review_{os.getpid()}"
PROJECT = "00000000-0000-4000-8000-000000000001"


def sql(query, *, check=True, database=DATABASE):
    result = subprocess.run(["docker", "exec", "-i", CONTAINER, "psql", "-X", "-U", "postgres", "-d", database,
                             "-v", "ON_ERROR_STOP=1", "-At"], input=query, text=True, capture_output=True, timeout=30)
    if check and result.returncode:
        raise AssertionError(result.stderr)
    return result


def function_sql(path, name):
    source = path.read_text()
    start = source.index("create or replace function public." + name + "(")
    return source[start:source.index("$$;", start) + 3]


def request_sql(seats=1, capacity=3, key="one", block="session", start="2030-08-02T09:00:00Z", tenant=1, group=True, session=None):
    reservation = {"bookingMode": "restricted", "sessionType": "group" if group else "private", "seatCapacity": capacity}
    payload = {"tenant_id": tenant, "project_id": PROJECT, "block_id": block, "block_type": "reservationBlock",
               "customer_email": "fixture@example.invalid", "starts_at": start, "payload": {"guests": seats},
               "field_snapshot": [{"reservation": reservation}]}
    if session is not None:
        payload["field_snapshot"][0]["session"] = session
        group = session["sessionType"] == "group"
    digest = hashlib.sha256(key.encode()).hexdigest()
    rpc = "create_builder_reservation_seated_safe" if group else "create_builder_reservation_notified_safe"
    return f"select public.{rpc}($fixture${json.dumps(payload)}$fixture$::jsonb,'{digest}','{'a'*64}',true,'{{}}'::jsonb);"


@unittest.skipUnless(os.getenv("MADAR_RUN_SEAT_SQL_TESTS") == "1", "requires owned disposable container")
class ReservationSeatPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        inspect = subprocess.run(["docker", "inspect", CONTAINER], capture_output=True, text=True, check=True)
        value = json.loads(inspect.stdout)[0]
        if (value["Config"]["Labels"].get("madar.task") != "reservation-seats-review"
                or value["HostConfig"]["NetworkMode"] != "none" or value["HostConfig"].get("Binds")):
            raise RuntimeError("Not the owned, isolated seat-test container")
        sql(f"create database {DATABASE};", database="postgres")
        sql("""
do $$ begin
  if not exists(select 1 from pg_catalog.pg_roles where rolname='anon') then create role anon; end if;
  if not exists(select 1 from pg_catalog.pg_roles where rolname='authenticated') then create role authenticated; end if;
  if not exists(select 1 from pg_catalog.pg_roles where rolname='service_role') then create role service_role; end if;
end $$;
create table public.tenant_site_memberships(id bigint,tenant_id integer,user_id integer,status text);
create table public.tenant_memberships(tenant_id integer,user_id integer,status text);
create table public.users(id integer,tenant_id integer);
create table public.website_settings(tenant_id integer,user_id integer);
create table public.tenants(tenant_id integer primary key);
create table public.builder_projects(id uuid primary key,tenant_id integer,status text);
insert into public.tenants values(1),(2);
insert into public.builder_projects values('00000000-0000-4000-8000-000000000001',1,'published');
""")
        source = (WEB / "supabase/migrations/044_create_builder_reservations.sql").read_text()
        start = source.index("create table if not exists public.builder_reservations")
        sql(source[start:source.index("\n);", start) + 3])
        sql((WEB / "supabase/migrations/046_harden_public_reservations.sql").read_text())
        sql("""
alter table public.builder_reservations add site_user_id integer, add site_membership_id bigint;
create table public.fixture_intents(key text unique);
create function public.create_notification_event_intent(integer,text,text,text,text,text,jsonb,text)
returns void language sql as 'insert into public.fixture_intents values($8)';
create table public.notification_outbox(tenant_id integer,channel text,template text,recipient_reference text,
payload jsonb,status text,available_at timestamptz,deduplication_key text unique,retention_until timestamptz);
""")
        sql(function_sql(WEB / "supabase/migrations/093_harden_public_ownership_and_web_push.sql", "create_builder_reservation_notified_safe"))
        sql(function_sql(WEB / "supabase/migrations/158_guard_reservation_reactivation_capacity.sql", "update_builder_reservation_status_notified_safe"))
        sql((WEB / "database/candidates/reservation_seat_capacity.sql").read_text())
        print("Native PostgreSQL version:", sql("show server_version;").stdout.strip())

    def setUp(self):
        sql("truncate public.builder_reservations,public.fixture_intents,public.notification_outbox;")

    def test_weighted_seats_capacity_and_idempotent_retry(self):
        sql(request_sql(seats=2))
        self.assertTrue(json.loads(sql(request_sql(seats=2)).stdout)["duplicate"])
        sql(request_sql(key="two"))
        self.assertIn("reservation_slot_unavailable", sql(request_sql(key="overflow"), check=False).stderr)
        for table in ["builder_reservations", "fixture_intents", "notification_outbox"]:
            self.assertEqual(sql(f"select count(*) from public.{table};").stdout.strip(), "2")

    def test_concurrent_final_seat_has_one_winner(self):
        sql(request_sql(seats=2))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda key: sql("begin;" + request_sql(key=key) + "select pg_sleep(0.3);commit;", check=False), ["race-a", "race-b"]))
        self.assertEqual(sum(result.returncode == 0 for result in results), 1)
        self.assertIn("reservation_slot_unavailable", next(result.stderr for result in results if result.returncode))
        self.assertEqual(sql("select sum((payload->>'guests')::integer) from public.builder_reservations;").stdout.strip(), "3")

    def test_cancel_releases_seats_and_full_reactivation_is_refused(self):
        first = json.loads(sql(request_sql(seats=2)).stdout)["reservation"]["id"]
        sql(f"select public.update_builder_reservation_status_notified_safe('{first}',1,'cancelled');")
        sql(request_sql(seats=3, key="replacement"))
        failure = sql(f"select public.update_builder_reservation_status_notified_safe('{first}',1,'confirmed');", check=False)
        self.assertIn("reservation_slot_unavailable", failure.stderr)
        self.assertEqual(sql(f"select status from public.builder_reservations where id='{first}';").stdout.strip(), "cancelled")

    def test_private_slots_and_independent_blocks_remain_separate(self):
        sql(request_sql(group=False))
        self.assertIn("reservation_slot_unavailable", sql(request_sql(group=False, key="private-overflow"), check=False).stderr)
        sql(request_sql(block="independent", key="other", seats=3))
        sql(request_sql(start="2030-08-02T10:00:00Z", key="later", seats=3))
        self.assertIn("builder_project_not_found", sql(request_sql(tenant=2, key="wrong-tenant"), check=False).stderr)
        self.assertEqual(sql("select count(*) from public.builder_reservations;").stdout.strip(), "3")

    def test_invalid_seats_and_repeatable_read_refuse(self):
        for seats in [0, 4, 1.5, True]:
            self.assertIn("reservation_seats_invalid", sql(request_sql(seats=seats), check=False).stderr)
        failure = sql("begin isolation level repeatable read;" + request_sql() + "commit;", check=False)
        self.assertIn("reservation_capacity_retry_required", failure.stderr)
        self.assertEqual(sql("select count(*) from public.builder_reservations;").stdout.strip(), "0")

    def test_direct_reactivation_cannot_bypass_capacity(self):
        first = json.loads(sql(request_sql(seats=3)).stdout)["reservation"]["id"]
        sql(f"update public.builder_reservations set status='cancelled' where id='{first}';")
        sql(request_sql(seats=3, key="replacement"))
        failure = sql(f"update public.builder_reservations set status='confirmed' where id='{first}';", check=False)
        self.assertIn("reservation_slot_unavailable", failure.stderr)

    def test_mixed_session_snapshot_overrides_the_block_default(self):
        session = {"sessionType": "group", "seatCapacity": 2}
        sql(request_sql(seats=2, capacity=10, session=session))
        self.assertIn("reservation_slot_unavailable", sql(request_sql(capacity=10, session=session, key="overflow"), check=False).stderr)
        private = {"sessionType": "private", "seatCapacity": 1}
        sql(request_sql(capacity=10, session=private, key="private", start="2030-08-02T11:00:00Z"))
        self.assertIn("reservation_slot_unavailable", sql(request_sql(capacity=10, session=private, key="private-overflow", start="2030-08-02T11:00:00Z"), check=False).stderr)

    def test_notification_failure_rolls_back_the_seat(self):
        sql("""create or replace function public.create_notification_event_intent(integer,text,text,text,text,text,jsonb,text)
returns void language plpgsql as $$ begin raise exception 'fixture_notification_failure'; end $$;""")
        try:
            self.assertIn("fixture_notification_failure", sql(request_sql(), check=False).stderr)
            self.assertEqual(sql("select count(*) from public.builder_reservations;").stdout.strip(), "0")
            self.assertEqual(sql("select count(*) from public.notification_outbox;").stdout.strip(), "0")
        finally:
            sql("""create or replace function public.create_notification_event_intent(integer,text,text,text,text,text,jsonb,text)
returns void language sql as 'insert into public.fixture_intents values($8)';""")

    def test_group_rpc_is_service_only(self):
        self.assertIn("permission denied", sql("set role anon;" + request_sql(), check=False).stderr)


if __name__ == "__main__":
    unittest.main()
