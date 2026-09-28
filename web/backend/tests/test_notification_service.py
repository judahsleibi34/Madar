from unittest.mock import patch

from services import notification_delivery_service, notification_service, observability_service


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, supabase, table_name):
        self.supabase = supabase
        self.table_name = table_name
        self.filters = []
        self.insert_payload = None
        self.update_payload = None

    def select(self, *_args):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def is_(self, *_args):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args):
        return self

    def insert(self, payload):
        self.insert_payload = payload
        return self

    def update(self, payload):
        self.update_payload = payload
        return self

    def upsert(self, payload, **_kwargs):
        self.insert_payload = payload
        return self

    def execute(self):
        if self.insert_payload is not None:
            rows = self.insert_payload if isinstance(self.insert_payload, list) else [self.insert_payload]
            saved_rows = []

            for row in rows:
                saved = {"id": f"{self.table_name}-{len(self.supabase.tables.get(self.table_name, [])) + 1}", **row}
                self.supabase.tables.setdefault(self.table_name, []).append(saved)
                saved_rows.append(saved)

            return FakeResponse(saved_rows)

        rows = list(self.supabase.tables.get(self.table_name, []))

        for column, value in self.filters:
            rows = [row for row in rows if row.get(column) == value]

        if self.update_payload is not None:
            for row in rows:
                row.update(self.update_payload)

        return FakeResponse(rows)


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "tenant_memberships": [
                {"tenant_id": 7, "user_id": 11, "role": "owner", "status": "active"},
                {"tenant_id": 7, "user_id": 12, "role": "member", "status": "active"},
                {"tenant_id": 7, "user_id": 13, "role": "member", "status": "inactive"},
            ],
            "notification_events": [],
            "user_notifications": [],
            "web_push_subscriptions": [],
            "notification_outbox": [],
        }

    def table(self, table_name):
        return FakeQuery(self, table_name)

    def rpc(self, name, payload):
        assert name in {"create_notification_event_intent", "get_or_create_notification_event"}
        existing = next((
            event for event in self.tables["notification_events"]
            if event.get("tenant_id") == payload["p_tenant_id"]
            and event.get("deduplication_key") == payload["p_deduplication_key"]
        ), None)
        if existing:
            return FakeQueryResult([existing])
        event = {
            "id": "event-1",
            "tenant_id": payload["p_tenant_id"],
            "event_type": payload["p_event_type"],
            "source_type": payload["p_source_type"],
            "source_id": payload["p_source_id"],
            "title": payload["p_title"],
            "body": payload["p_body"],
            "data": payload["p_data"],
            "deduplication_key": payload["p_deduplication_key"],
        }
        self.tables["notification_events"].append(event)
        self.tables["notification_outbox"].append({"event_id": event["id"]})
        return FakeQueryResult([event])


class FakeQueryResult:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return self


def test_notification_read_exposes_serial_query_timing_breakdown():
    fake_supabase = FakeSupabase()
    token = observability_service.begin_request_timings()
    try:
        with patch.object(notification_service, "service_supabase", fake_supabase):
            notification_service.list_user_notifications(tenant_id=7, user_id=11)
        timings = observability_service.request_timings_snapshot()
    finally:
        observability_service.end_request_timings(token)

    assert {
        "notifications_list_query",
        "notifications_transform",
        "notifications_unread_query",
    }.issubset(timings)


def test_create_tenant_notification_event_creates_atomic_durable_intent(monkeypatch):
    fake_supabase = FakeSupabase()
    monkeypatch.setattr(notification_service, "service_supabase", fake_supabase)
    monkeypatch.delenv("WEB_PUSH_VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("WEB_PUSH_VAPID_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("WEB_PUSH_VAPID_SUBJECT", raising=False)

    event = notification_service.create_builder_block_event_notification(
        tenant_id=7,
        event_type="builder.form_submitted",
        block_type="form",
        source_id="submission-1",
        title="New form submission",
        body="Contact form received a new response.",
        data={"form_id": "contact"},
    )

    assert event["event_type"] == "builder.form_submitted"
    assert len(fake_supabase.tables["notification_events"]) == 1
    assert len(fake_supabase.tables["notification_outbox"]) == 1
    assert fake_supabase.tables["user_notifications"] == []
    assert event["data"]["block_type"] == "form"


def test_internal_reminder_is_delivered_only_to_its_target_user(monkeypatch):
    fake_supabase = FakeSupabase()
    monkeypatch.setattr(
        notification_delivery_service, "service_supabase", fake_supabase
    )

    notification_delivery_service.deliver_notification({
        "channel": "internal",
        "tenant_id": 7,
        "user_id": 11,
        "payload": {
            "event_type": "calendar_task_reminder",
            "source_type": "calendar_task",
            "source_id": "task-1",
            "title": "Task starts soon",
            "body": "Scheduled for now",
            "data": {"task_id": "task-1"},
        },
    })

    assert len(fake_supabase.tables["user_notifications"]) == 1
    assert fake_supabase.tables["user_notifications"][0]["user_id"] == 11


def test_ecommerce_order_notification_reaches_active_store_owner(monkeypatch):
    fake_supabase = FakeSupabase()
    monkeypatch.setattr(
        notification_delivery_service, "service_supabase", fake_supabase
    )

    notification_delivery_service.deliver_notification({
        "channel": "internal",
        "tenant_id": 7,
        "payload": {
            "event_type": "ecommerce_order_created",
            "source_type": "ecommerce_order",
            "source_id": "order-1",
            "title": "New order: MD-1001",
            "body": "MD-1001 was placed for ILS 25.00.",
            "data": {"order_id": "order-1", "order_number": "MD-1001"},
            "event_deduplication_key": "ecommerce-order:order-1",
        },
    })

    recipients = {
        row["user_id"] for row in fake_supabase.tables["user_notifications"]
    }
    assert recipients == {11, 12}
    owner_notification = next(
        row for row in fake_supabase.tables["user_notifications"]
        if row["user_id"] == 11
    )
    assert owner_notification["event_type"] == "ecommerce_order_created"
    assert owner_notification["data"]["order_id"] == "order-1"


def test_notification_rpc_accepts_single_object_response():
    assert notification_service._rows(FakeResponse({"id": "event-1"})) == [
        {"id": "event-1"}
    ]


def test_ecommerce_order_in_app_notification_is_mandatory_for_owner(monkeypatch):
    fake_supabase = FakeSupabase()
    monkeypatch.setattr(
        notification_delivery_service, "service_supabase", fake_supabase
    )
    monkeypatch.setattr(
        notification_delivery_service,
        "preference_enabled",
        lambda **_kwargs: False,
    )

    notification_delivery_service.deliver_notification({
        "channel": "internal",
        "tenant_id": 7,
        "payload": {
            "event_type": "ecommerce_order_created",
            "source_type": "ecommerce_order",
            "source_id": "order-mandatory-1",
            "title": "New order: MD-1002",
            "body": "MD-1002 was placed for ILS 25.00.",
            "data": {
                "order_id": "order-mandatory-1",
                "order_number": "MD-1002",
            },
            "event_deduplication_key": "ecommerce-order:order-mandatory-1",
        },
    })

    assert {
        row["user_id"] for row in fake_supabase.tables["user_notifications"]
    } == {11}
