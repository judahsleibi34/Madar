"""Restore captured Academy bindings before removing an explicitly created QA project.

Call only within the cleanup transaction after validating its loopback database.
A missing provenance snapshot fails closed; a pre-existing project is never deleted.
"""

def restore_academy_fixture_binding(db, fixture):
    project_id = fixture.get("builder_project")
    if not project_id:
        return
    tenant_id = fixture["tenant_id"]
    if "original_academy_bindings" not in fixture or "preexisting_builder_projects" not in fixture:
        raise ValueError("Academy cleanup requires the original bindings and project inventory")
    if project_id in fixture["preexisting_builder_projects"] or fixture.get("builder_project_created") is not True:
        raise ValueError("Academy cleanup cannot delete a pre-existing or unverified project")
    original = fixture["original_academy_bindings"]
    current = db.execute("select academy_project_id,academy_editor_project_id from public.website_settings where tenant_id=%s for update", (tenant_id,)).fetchone()
    if current is None:
        raise ValueError("Academy settings disappeared during QA")
    for actual, field in zip(current, ("published", "editor")):
        if actual is not None and str(actual) not in {project_id, original.get(field)}:
            raise ValueError("Academy binding changed outside the QA fixture")
    project = db.execute("select usage_profile from public.builder_projects where tenant_id=%s and id=%s", (tenant_id, project_id)).fetchone()
    if project is not None and project != ("academy",):
        raise ValueError("Academy cleanup profile mismatch")
    db.execute("update public.website_settings set academy_project_id=%s,academy_editor_project_id=%s where tenant_id=%s", (original.get("published"), original.get("editor"), tenant_id))
    if project:
        db.execute("delete from public.builder_projects where tenant_id=%s and id=%s and usage_profile='academy'", (tenant_id, project_id))
    restored = db.execute("select academy_project_id,academy_editor_project_id from public.website_settings where tenant_id=%s", (tenant_id,)).fetchone()
    assert all(str(actual) == str(original.get(field)) for actual, field in zip(restored, ("published", "editor")))
