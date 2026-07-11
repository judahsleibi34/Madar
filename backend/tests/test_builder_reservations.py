import copy
import unittest
from unittest.mock import patch

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
    def test_public_reservation_event_creates_durable_row_and_notification(self):
        fake_supabase = FakeSupabase()
        add_published_reservation_block(fake_supabase)
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"), \
             patch.object(public_site_routes, "create_builder_block_event_notification") as notify_event:
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
        self.assertEqual(saved["starts_at"], "2026-07-10T19:00:00")
        self.assertEqual(saved["timezone"], "Asia/Jerusalem")
        self.assertEqual(saved["status"], "new")
        self.assertEqual(saved["user_agent"], "reservation-agent")
        self.assertEqual(saved["payload"]["tenant_id"], 999)
        notify_event.assert_called_once()
        self.assertEqual(notify_event.call_args.kwargs["data"]["reservation_id"], SUBMISSION_ID)

    def test_public_reservation_unknown_subdomain_fails_without_insert(self):
        fake_supabase = FakeSupabase()
        add_published_reservation_block(fake_supabase)
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"), \
             patch.object(public_site_routes, "create_builder_block_event_notification") as notify_event:
            response = client.post(
                "/public/sites/missing-site/events",
                json={"block_type": "reservationBlock", "block_id": RESERVATION_BLOCK_ID, "payload": {}},
            )

        self.assertEqual(response.status_code, 404)
        self.assertNotIn("builder_reservations", fake_supabase.tables)
        notify_event.assert_not_called()

    def test_public_reservation_unknown_block_fails_without_insert(self):
        fake_supabase = FakeSupabase()
        add_published_reservation_block(fake_supabase)
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"), \
             patch.object(public_site_routes, "create_builder_block_event_notification") as notify_event:
            response = client.post(
                "/public/sites/tenant-site/events",
                json={"block_type": "reservationBlock", "block_id": "missing", "payload": {}},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Block not found")
        self.assertNotIn("builder_reservations", fake_supabase.tables)
        notify_event.assert_not_called()


class BuilderReservationManagementTests(unittest.TestCase):
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
