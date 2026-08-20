from services.calendar_workspace_cache_service import (
    calendar_workspace_cache_key,
    calendar_workspace_cache_size,
    clear_calendar_workspace_cache,
    get_or_create_calendar_workspace,
    invalidate_calendar_workspace_cache,
    read_calendar_workspace_cache,
    write_calendar_workspace_cache,
)


def setup_function():
    clear_calendar_workspace_cache()


def teardown_function():
    clear_calendar_workspace_cache()


def test_calendar_cache_isolates_users_ranges_and_returns_copies():
    first = calendar_workspace_cache_key(
        tenant_id=7, user_id=11, role="member", start="a", end="b"
    )
    second = calendar_workspace_cache_key(
        tenant_id=7, user_id=12, role="member", start="a", end="b"
    )
    assert first != second
    payload = {"events": [{"id": "event-1"}]}
    write_calendar_workspace_cache(first, 7, payload)

    cached = read_calendar_workspace_cache(first)
    cached["events"][0]["id"] = "changed"
    assert read_calendar_workspace_cache(first) == payload
    assert read_calendar_workspace_cache(second) is None


def test_calendar_cache_reuses_payload_and_invalidates_only_target_tenant():
    first = calendar_workspace_cache_key(
        tenant_id=7, user_id=11, role="member", start="a", end="b"
    )
    second = calendar_workspace_cache_key(
        tenant_id=8, user_id=11, role="member", start="a", end="b"
    )
    calls = []

    created, first_hit = get_or_create_calendar_workspace(
        first, 7, lambda: calls.append("created") or {"events": []}
    )
    reused, second_hit = get_or_create_calendar_workspace(
        first, 7, lambda: calls.append("unexpected") or {"events": ["wrong"]}
    )
    write_calendar_workspace_cache(second, 8, {"events": []})

    assert created == reused
    assert first_hit is False
    assert second_hit is True
    assert calls == ["created"]
    assert calendar_workspace_cache_size() == 2
    assert invalidate_calendar_workspace_cache(7) == 1
    assert read_calendar_workspace_cache(first) is None
    assert read_calendar_workspace_cache(second) == {"events": []}


def test_invalidation_during_a_cache_miss_prevents_stale_result_from_being_stored():
    key = calendar_workspace_cache_key(
        tenant_id=7, user_id=11, role="member", start="a", end="b"
    )

    def load_then_invalidate():
        invalidate_calendar_workspace_cache(7)
        return {"events": [{"id": "stale"}]}

    payload, cache_hit = get_or_create_calendar_workspace(
        key, 7, load_then_invalidate
    )

    assert cache_hit is False
    assert payload == {"events": [{"id": "stale"}]}
    assert read_calendar_workspace_cache(key) is None
