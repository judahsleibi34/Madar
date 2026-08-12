import copy
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from routes import builder_routes, public_site_routes
from tests.test_builder_form_submissions import (
    FakeSupabase,
    PROJECT_ID,
    PUBLISHED_SCHEMA,
    RESERVATION_BLOCK_ID,
    SUBMISSION_ID,
    build_builder_client,
    build_public_client,
    fake_context,
)

RESERVATION_ID = "33333333-3333-4333-8333-333333333333"


def add_published_reservation_block(fake_supabase):
    published_schema = copy.deepcopy(PUBLISHED_SCHEMA)
    published_schema["pages"][0]["sections"][0]["rows"][0]["columns"][0]["elements"].append(
        {
            "id": RESERVATION_BLOCK_ID,
            "type": "reservationBlock",
            "reservation": {"title": "Book a table", "services": ["Dinner"]},
        }
    )
    fake_supabase.tables["builder_projects"][0]["published_schema"] = published_schema


def seed_reservations(fake_supabase):
    fake_supabase.tables["builder_reservations"] = [
        {
            "id": RESERVATION_ID,
            "tenant_id": 1,
            "project_id": PROJECT_ID,
            "site_subdomain": "tenant-site",
            "block_id": RESERVATION_BLOCK_ID,
            "block_type": "reservationBlock",
            "reservation_title": "Book a table",
            "customer_name": "Ada",
            "customer_email": "ada@example.com",
            "customer_phone": "+123",
            "starts_at": "2026-07-10T19:00:00",
            "ends_at": None,
            "timezone": "Asia/Jerusalem",
            "status": "new",
            "payload": {"service": "Dinner"},
            "field_snapshot": [{"block_id": RESERVATION_BLOCK_ID}],
            "created_at": "2026-07-08T12:00:00+00:00",
            "updated_at": "2026-07-08T12:00:00+00:00",
        },
        {
            "id": "44444444-4444-4444-8444-444444444444",
            "tenant_id": 2,
            "project_id": PROJECT_ID,
            "site_subdomain": "other-site",
            "block_id": RESERVATION_BLOCK_ID,
            "block_type": "reservationBlock",
            "reservation_title": "Other tenant",
            "customer_name": "Eve",
            "status": "new",
            "payload": {},
            "field_snapshot": [],
            "created_at": "2026-07-08T13:00:00+00:00",
            "updated_at": "2026-07-08T13:00:00+00:00",
        },
    ]


class PublicBuilderReservationTests(unittest.TestCase):
    def test_reservation_timing_defaults_and_preserves_explicit_end(self):
        defaulted = public_site_routes.normalize_reservation_timing({
            "starts_at": "2026-07-10T19:00:00+03:00",
        })
        self.assertEqual(defaulted["ends_at"], "2026-07-10T19:30:00+03:00")
        self.assertEqual(
            datetime.fromisoformat(defaulted["ends_at"]).timestamp()
            - datetime.fromisoformat(defaulted["starts_at"]).timestamp(),
            30 * 60,
        )

        explicit = public_site_routes.normalize_reservation_timing({
            "starts_at": "2026-07-10T19:00:00+03:00",
            "ends_at": "2026-07-10T20:15:00+03:00",
        })
        self.assertEqual(explicit["ends_at"], "2026-07-10T20:15:00+03:00")

    def test_reservation_timing_rejects_zero_negative_and_malformed_ranges(self):
        for ends_at in (
            "2026-07-10T19:00:00+03:00",
            "2026-07-10T18:59:00+03:00",
            "not-a-time",
        ):
            with self.subTest(ends_at=ends_at), self.assertRaises(HTTPException) as raised:
                public_site_routes.normalize_reservation_timing({
                    "starts_at": "2026-07-10T19:00:00+03:00",
                    "ends_at": ends_at,
                })
            self.assertEqual(raised.exception.status_code, 400)

    def test_naive_reservation_timing_requires_timezone_and_retains_zone(self):
        with self.assertRaises(HTTPException) as raised:
            public_site_routes.normalize_reservation_timing({
                "starts_at": "2026-07-10T19:00:00",
            })
        self.assertEqual(raised.exception.detail["code"], "reservation_timezone_required")

        normalized = public_site_routes.normalize_reservation_timing({
            "date": "2026-07-10",
            "time": "19:00",
            "timezone": "Asia/Jerusalem",
        })
        self.assertEqual(normalized["starts_at"], "2026-07-10T19:00:00+03:00")
        self.assertEqual(normalized["ends_at"], "2026-07-10T19:30:00+03:00")

    def test_role_restricted_reservation_requires_login(self):
        fake_supabase = FakeSupabase()
        add_published_reservation_block(fake_supabase)
        fake_supabase.tables["builder_projects"][0]["published_schema"]["roles"] = [{
            "id": "customer",
            "permissions": {"makeReservations": True},
            "resourceAccess": {"reservationBlockIds": [RESERVATION_BLOCK_ID]},
        }]
        client = build_public_client(fake_supabase)
        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"), \
             patch.object(public_site_routes, "get_optional_tenant_visitor", return_value=None):
            response = client.post(
                "/public/sites/tenant-site/events",
                json={
                    "block_type": "reservationBlock",
                    "block_id": RESERVATION_BLOCK_ID,
                    "payload": {"name": "Ada", "date": "2026-07-10", "time": "19:00", "timezone": "Asia/Jerusalem"},
                },
            )
        self.assertEqual(response.status_code, 401)

    def test_logged_in_reservation_records_member_ownership(self):
        fake_supabase = FakeSupabase()
        add_published_reservation_block(fake_supabase)
        client = build_public_client(fake_supabase)
        identity = ({"id": 31}, {"id": 41, "status": "active"})
        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"), \
             patch.object(public_site_routes, "authorize_site_resource", return_value=identity):
            response = client.post(
                "/public/sites/tenant-site/events",
                json={
                    "block_type": "reservationBlock",
                    "block_id": RESERVATION_BLOCK_ID,
                    "payload": {"name": "Ada", "date": "2026-07-10", "time": "19:00", "timezone": "Asia/Jerusalem"},
                },
            )
        self.assertEqual(response.status_code, 200, response.text)
        saved = fake_supabase.tables["builder_reservations"][-1]
        self.assertEqual(saved["site_user_id"], 31)
        self.assertEqual(saved["site_membership_id"], 41)

    def test_member_reservations_endpoint_is_not_exposed(self):
        client = build_public_client(FakeSupabase())
        response = client.get("/public/sites/tenant-site/me/reservations")
        self.assertEqual(response.status_code, 404)
    def test_public_reservation_event_creates_durable_row_and_notification(self):
        fake_supabase = FakeSupabase()
        add_published_reservation_block(fake_supabase)
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                "/public/sites/tenant-site/events",
                json={
                    "block_type": "reservationBlock",
                    "block_id": RESERVATION_BLOCK_ID,
                    "event_type": "builder.reservation_requested",
                    "payload": {
                        "tenant_id": 999,
                        "project_id": "client-project",
                        "name": "Ada",
                        "email": "ada@example.com",
                        "phone": "+123",
                        "service": "Dinner",
                        "date": "2026-07-10",
                        "time": "19:00",
                        "timezone": "Asia/Jerusalem",
                    },
                },
                headers={"User-Agent": "reservation-agent"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["reservation_id"], SUBMISSION_ID)
        self.assertEqual(body["message"], "Reservation submitted successfully.")
        self.assertNotIn("tenant_id", body)
        self.assertNotIn("project_id", body)

        saved = fake_supabase.tables["builder_reservations"][-1]
        self.assertEqual(saved["tenant_id"], 1)
        self.assertEqual(saved["project_id"], PROJECT_ID)
        self.assertEqual(saved["site_subdomain"], "tenant-site")
        self.assertEqual(saved["block_id"], RESERVATION_BLOCK_ID)
        self.assertEqual(saved["customer_name"], "Ada")
        self.assertEqual(saved["customer_email"], "ada@example.com")
        self.assertEqual(saved["customer_phone"], "+123")
        self.assertEqual(saved["starts_at"], "2026-07-10T19:00:00+03:00")
        self.assertEqual(saved["ends_at"], "2026-07-10T19:30:00+03:00")
        self.assertEqual(saved["timezone"], "Asia/Jerusalem")
        self.assertEqual(saved["status"], "new")
        self.assertEqual(saved["user_agent"], "reservation-agent")
        self.assertEqual(saved["payload"]["tenant_id"], 999)

    def test_public_reservation_unknown_subdomain_fails_without_insert(self):
        fake_supabase = FakeSupabase()
        add_published_reservation_block(fake_supabase)
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                "/public/sites/missing-site/events",
                json={"block_type": "reservationBlock", "block_id": RESERVATION_BLOCK_ID, "payload": {}},
            )

        self.assertEqual(response.status_code, 404)
        self.assertNotIn("builder_reservations", fake_supabase.tables)

    def test_public_reservation_honeypot_is_rejected_before_insert(self):
        fake_supabase = FakeSupabase()
        add_published_reservation_block(fake_supabase)
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                "/public/sites/tenant-site/events",
                json={
                    "block_type": "reservationBlock",
                    "block_id": RESERVATION_BLOCK_ID,
                    "honeypot": "bot-filled",
                    "payload": {},
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "submission_rejected")
        self.assertNotIn("builder_reservations", fake_supabase.tables)

    def test_public_reservation_rejects_invalid_timezone(self):
        fake_supabase = FakeSupabase()
        add_published_reservation_block(fake_supabase)
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                "/public/sites/tenant-site/events",
                json={
                    "block_type": "reservationBlock",
                    "block_id": RESERVATION_BLOCK_ID,
                    "payload": {
                        "date": "2026-07-10",
                        "time": "19:00",
                        "timezone": "Not/A_Timezone",
                    },
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"]["code"],
            "reservation_timezone_invalid",
        )

    def test_idempotent_replay_does_not_duplicate_notification(self):
        fake_supabase = FakeSupabase()
        add_published_reservation_block(fake_supabase)
        client = build_public_client(fake_supabase)
        saved = {
            "id": RESERVATION_ID,
            "tenant_id": 1,
            "project_id": PROJECT_ID,
        }

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"), \
             patch.object(
                 public_site_routes,
                 "insert_builder_reservation",
                 side_effect=[(saved, False), (saved, True)],
             ):
            request_json = {
                "block_type": "reservationBlock",
                "block_id": RESERVATION_BLOCK_ID,
                "idempotency_key": "madar-reservation-test-0001",
                "payload": {
                    "date": "2026-07-10",
                    "time": "19:00",
                    "timezone": "Asia/Jerusalem",
                },
            }
            first = client.post("/public/sites/tenant-site/events", json=request_json)
            second = client.post("/public/sites/tenant-site/events", json=request_json)

        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.json()["idempotent_replay"])
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()["idempotent_replay"])
        self.assertEqual(
            first.json()["cancellation_token"],
            second.json()["cancellation_token"],
        )

    def test_storage_conflicts_have_stable_codes(self):
        idempotency_error = public_site_routes._reservation_storage_error(
            RuntimeError("database error: idempotency_conflict")
        )
        slot_error = public_site_routes._reservation_storage_error(
            RuntimeError("database error: reservation_slot_unavailable")
        )

        self.assertEqual(idempotency_error.status_code, 409)
        self.assertEqual(idempotency_error.detail["code"], "idempotency_conflict")
        self.assertEqual(slot_error.status_code, 409)
        self.assertEqual(slot_error.detail["code"], "reservation_slot_unavailable")

    def test_cancellation_replay_has_stable_code(self):
        fake_supabase = FakeSupabase()
        fake_supabase.rpc = MagicMock(
            return_value=MagicMock(
                execute=MagicMock(
                    side_effect=RuntimeError("reservation_cancellation_replayed")
                )
            )
        )
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                f"/public/reservations/{RESERVATION_ID}/cancel",
                json={"token": "x" * 40},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"]["code"],
            "reservation_cancellation_replayed",
        )

    def test_public_reservation_unknown_block_fails_without_insert(self):
        fake_supabase = FakeSupabase()
        add_published_reservation_block(fake_supabase)
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                "/public/sites/tenant-site/events",
                json={"block_type": "reservationBlock", "block_id": "missing", "payload": {}},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Block not found")
        self.assertNotIn("builder_reservations", fake_supabase.tables)


class BuilderReservationManagementTests(unittest.TestCase):
    def setUp(self):
        self.entitlement_patch = patch.object(
            builder_routes,
            "require_entitlement",
            return_value={},
        )
        self.entitlement_patch.start()

    def tearDown(self):
        self.entitlement_patch.stop()

    def test_tenant_can_list_own_reservations_with_filters_and_pagination(self):
        fake_supabase = FakeSupabase()
        seed_reservations(fake_supabase)
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()):
            response = client.get(
                f"/builder/reservations?status=new&project_id={PROJECT_ID}&limit=1&offset=0"
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["reservations"]), 1)
        self.assertEqual(body["reservations"][0]["id"], RESERVATION_ID)
        self.assertEqual(body["reservations"][0]["customer_name"], "Ada")
        self.assertEqual(body["pagination"]["limit"], 1)

    def test_tenant_can_read_own_reservation(self):
        fake_supabase = FakeSupabase()
        seed_reservations(fake_supabase)
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()):
            response = client.get(f"/builder/reservations/{RESERVATION_ID}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reservation"]["id"], RESERVATION_ID)

    def test_tenant_can_update_reservation_status(self):
        fake_supabase = FakeSupabase()
        seed_reservations(fake_supabase)
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_builder_write_access", return_value=fake_context()):
            response = client.patch(
                f"/builder/reservations/{RESERVATION_ID}/status",
                json={"status": "confirmed"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reservation"]["status"], "confirmed")
        self.assertEqual(fake_supabase.tables["builder_reservations"][0]["status"], "confirmed")

    def test_invalid_status_is_rejected(self):
        fake_supabase = FakeSupabase()
        seed_reservations(fake_supabase)
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_builder_write_access", return_value=fake_context()):
            response = client.patch(
                f"/builder/reservations/{RESERVATION_ID}/status",
                json={"status": "maybe"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid reservation status")
        self.assertEqual(fake_supabase.tables["builder_reservations"][0]["status"], "new")

    def test_cross_tenant_reservation_read_is_rejected(self):
        fake_supabase = FakeSupabase()
        seed_reservations(fake_supabase)
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context(tenant_id=2)):
            response = client.get(f"/builder/reservations/{RESERVATION_ID}")

        self.assertEqual(response.status_code, 404)

    def test_cross_tenant_reservation_status_update_is_rejected(self):
        fake_supabase = FakeSupabase()
        seed_reservations(fake_supabase)
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_builder_write_access", return_value=fake_context(tenant_id=2)):
            response = client.patch(
                f"/builder/reservations/{RESERVATION_ID}/status",
                json={"status": "confirmed"},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(fake_supabase.tables["builder_reservations"][0]["status"], "new")

    def test_unauthenticated_reservation_list_is_rejected(self):
        fake_supabase = FakeSupabase()
        seed_reservations(fake_supabase)
        client = build_builder_client(fake_supabase)

        with patch.object(
            builder_routes,
            "require_active_tenant_member",
            side_effect=HTTPException(status_code=401, detail="Not authenticated"),
        ):
            response = client.get("/builder/reservations")

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
