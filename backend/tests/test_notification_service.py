from services import notification_service


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
        }

    def table(self, table_name):
        return FakeQuery(self, table_name)


def test_create_tenant_notification_event_fans_out_to_active_members(monkeypatch):
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
    assert len(fake_supabase.tables["user_notifications"]) == 2
    assert {row["user_id"] for row in fake_supabase.tables["user_notifications"]} == {11, 12}
    assert fake_supabase.tables["user_notifications"][0]["data"]["block_type"] == "form"
