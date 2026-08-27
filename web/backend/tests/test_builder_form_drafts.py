from unittest.mock import patch

from routes import builder_routes, public_site_routes
from tests.test_builder_form_submissions import (
    FORM_ID,
    PROJECT_ID,
    FakeSupabase,
    build_builder_client,
    build_public_client,
    fake_context,
)


def save_draft(client):
    return client.post(
        f"/public/sites/tenant-site/forms/{FORM_ID}/drafts",
        json={
            "answers": {"field_name": "Ada"},
            "page_index": 3,
            "language": "en",
            "submission_elapsed_ms": 1000,
        },
    )


def test_save_resume_and_complete_removes_incomplete_record():
    fake_supabase = FakeSupabase()
    client = build_public_client(fake_supabase)
    with patch.object(public_site_routes, "service_supabase", fake_supabase), \
         patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"), \
         patch.object(public_site_routes, "require_public_runtime_entitlement"), \
         patch.object(public_site_routes, "authorize_site_resource", return_value=None):
        saved = save_draft(client)
        assert saved.status_code == 200
        draft = saved.json()["draft"]
        assert draft["answers"] == {"field_name": "Ada"}
        assert draft["pageIndex"] == 3
        assert draft["resumeToken"]

        resumed = client.get(
            f"/public/sites/tenant-site/forms/{FORM_ID}/drafts/{draft['resumeToken']}"
        )
        assert resumed.status_code == 200
        assert resumed.json()["draft"]["answers"]["field_name"] == "Ada"

        completed = client.post(
            f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
            json={
                "answers": {"field_name": "Ada", "field_email": "ada@example.com"},
                "resume_token": draft["resumeToken"],
            },
        )
        assert completed.status_code == 200
        assert fake_supabase.tables["builder_form_drafts"] == []


def test_authenticated_builder_can_list_incomplete_forms():
    fake_supabase = FakeSupabase()
    public_client = build_public_client(fake_supabase)
    with patch.object(public_site_routes, "service_supabase", fake_supabase), \
         patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"), \
         patch.object(public_site_routes, "require_public_runtime_entitlement"), \
         patch.object(public_site_routes, "authorize_site_resource", return_value=None):
        assert save_draft(public_client).status_code == 200

    builder_client = build_builder_client(fake_supabase)
    with patch.object(builder_routes, "service_supabase", fake_supabase), \
         patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()), \
         patch.object(builder_routes, "require_entitlement"):
        response = builder_client.get(
            f"/builder/projects/{PROJECT_ID}/form-drafts?form_id={FORM_ID}"
        )

    assert response.status_code == 200
    assert len(response.json()["drafts"]) == 1
    assert response.json()["drafts"][0]["status"] == "Incomplete"
    assert response.json()["drafts"][0]["resumeToken"]
