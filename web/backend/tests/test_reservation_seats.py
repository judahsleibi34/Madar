import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from routes import public_site_routes as routes


class ReservationSeatTests(unittest.TestCase):
    def group(self, capacity=3):
        return {"reservation": {"bookingMode": "restricted", "sessionType": "group", "seatCapacity": capacity}}

    def test_group_counts_people_and_private_defaults_to_one(self):
        payload = {"guests": "2"}
        routes.validate_reservation_seats(self.group(), payload)
        self.assertEqual(payload["guests"], 2)
        self.assertEqual(routes.reservation_seat_capacity({"reservation": {}}), 1)
        for value in [0, -1, 4, 1.5, True, "2.5", "no", None]:
            with self.subTest(value=value), self.assertRaises(HTTPException):
                routes.validate_reservation_seats(self.group(), {"guests": value})
        with self.assertRaises(HTTPException):
            routes.validate_reservation_seats({"reservation": {}}, {"guests": 2})

    def test_mixed_appointments_resolve_independently_and_snapshot_the_selected_session(self):
        block = {"reservation": {"bookingMode": "restricted", "weeklyRepeatDates": ["2026-08-07"],
            "timeSlotsByDate": {"2026-08-07": ["09:00", "11:00"], "2026-08-21": ["11:00"]},
            "sessionSettingsByDate": {"2026-08-07": {"11:00": {"sessionType": "group", "seatCapacity": 6}}}}}
        private = {"date": "2026-08-07", "time": "09:00", "guests": 2}
        group = {"date": "2026-08-07", "time": "11:00", "guests": 6}
        with self.assertRaises(HTTPException):
            routes.validate_reservation_seats(block, private)
        routes.validate_reservation_seats(block, group)
        self.assertEqual(routes.reservation_seat_capacity(block, group), 6)
        self.assertEqual(routes.reservation_seat_capacity(block, {"date": "2026-08-14", "time": "11:00"}), 6)
        self.assertEqual(routes.reservation_seat_capacity(block, {"date": "2026-08-21", "time": "11:00"}), 1)
        snapshot = routes.build_reservation_field_snapshot(block, "session", "reservationBlock", group)
        self.assertEqual(snapshot[0]["session"], {"sessionType": "group", "seatCapacity": 6})
        self.assertEqual(block["reservation"]["sessionSettingsByDate"]["2026-08-07"]["11:00"]["seatCapacity"], 6)

    def test_date_requests_do_not_inherit_fixed_session_limits(self):
        block = {"reservation": {"bookingMode": "flexible", "sessionType": "group", "seatCapacity": 6,
            "sessionSettingsByDate": {"2026-08-07": {"09:00": {"sessionType": "group", "seatCapacity": 3}}}}}
        payload = {"date": "2026-08-07", "time": "09:00", "guests": 10}
        routes.validate_reservation_seats(block, payload)
        self.assertEqual(routes.reservation_seat_capacity(block, payload), 1)
        self.assertNotIn("session", routes.build_reservation_field_snapshot(block, "session", "reservationBlock", payload)[0])

    def test_invalid_capacity_fails_closed(self):
        for value in [None, True, 1, 0, 1001, "3", 3.5]:
            with self.subTest(value=value), self.assertRaises(HTTPException):
                routes.reservation_seat_capacity(self.group(value))

    def test_group_uses_dedicated_atomic_rpc_and_keeps_exclusive_intent(self):
        storage = MagicMock()
        storage.rpc.return_value.execute.return_value.data = {"reservation": {"id": "synthetic"}, "duplicate": False}
        with patch.object(routes, "service_supabase", storage):
            routes.insert_builder_reservation({}, idempotency_key_hash=None, request_hash="a" * 64,
                exclusive_slot=True, seat_capacity=3, notification={})
        self.assertEqual(storage.rpc.call_args.args[0], "create_builder_reservation_seated_safe")
        self.assertTrue(storage.rpc.call_args.args[1]["p_exclusive_slot"])

    def test_missing_adapter_never_falls_back_to_an_unlimited_insert(self):
        storage = MagicMock()
        storage.rpc = None
        with patch.object(routes, "service_supabase", storage), self.assertRaises(HTTPException) as raised:
            routes.insert_builder_reservation({}, idempotency_key_hash=None, request_hash="a" * 64,
                exclusive_slot=True, seat_capacity=3, notification={})
        self.assertEqual(raised.exception.detail["code"], "reservation_capacity_unavailable")
        storage.table.assert_not_called()
        self.assertEqual(routes._reservation_storage_error(RuntimeError("reservation_slot_unavailable")).status_code, 409)
        self.assertEqual(routes._reservation_storage_error(RuntimeError(
            "PGRST202 Could not find create_builder_reservation_seated_safe")).status_code, 503)


if __name__ == "__main__":
    unittest.main()
