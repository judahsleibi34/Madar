from types import SimpleNamespace
from unittest.mock import patch

from fastapi import Response

from routes import builder_routes, public_site_routes


def tenant_context():
    return SimpleNamespace(tenant_id=12, user_id=34)


def test_workspace_heartbeat_is_scoped_to_authenticated_tenant_user():
    payload = builder_routes.ScreenTimeHeartbeat(active_seconds=15)

    with (
        patch.object(builder_routes, "require_builder_context", return_value=tenant_context()),
        patch.object(builder_routes, "record_screen_time") as record,
    ):
        result = builder_routes.create_screen_time_heartbeat(
            payload,
            SimpleNamespace(),
            Response(),
        )

    assert result == {"success": True}
    record.assert_called_once_with(tenant_id=12, user_id=34, active_seconds=15)


def test_monthly_summary_uses_current_tenant_and_project():
    summary = {
        "period": "month",
        "range_start": "2026-08-01",
        "range_end": "2026-08-30",
        "total_seconds": 90,
        "users": [{"user_id": 34, "name": "Sulaima", "active_seconds": 90}],
    }

    with (
        patch.object(builder_routes, "require_builder_context", return_value=tenant_context()),
        patch.object(builder_routes, "get_project_for_tenant") as get_project,
        patch.object(builder_routes, "get_weekly_screen_time", return_value=summary) as get_summary,
    ):
        result = builder_routes.read_weekly_screen_time(
            SimpleNamespace(),
            Response(),
            project_id="project-1",
            period="month",
        )

    get_project.assert_called_once_with("project-1", 12)
    get_summary.assert_called_once_with(
        tenant_id=12,
        current_user_id=34,
        project_id="project-1",
        period="month",
    )
    assert result["users"][0]["name"] == "Sulaima"


def test_public_site_heartbeat_uses_authenticated_role_member_identity():
    payload = public_site_routes.PublicScreenTimeHeartbeat(active_seconds=12)

    with (
        patch.object(
            public_site_routes,
            "require_tenant_visitor",
            return_value=({"id": 77}, {"tenant_id": 12}),
        ),
        patch.object(public_site_routes, "enforce_public_rate_limit"),
        patch.object(public_site_routes, "record_screen_time") as record,
    ):
        result = public_site_routes.create_public_screen_time_heartbeat(
            "tenant-site",
            payload,
            SimpleNamespace(),
            Response(),
        )

    assert result == {"success": True}
    record.assert_called_once_with(tenant_id=12, user_id=77, active_seconds=12)