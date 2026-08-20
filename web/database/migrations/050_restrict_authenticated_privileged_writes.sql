begin;

-- Browser clients use backend HTTP routes for every privileged mutation.
-- Keep tenant-scoped reads available, but make writes service-role-only so RLS
-- row ownership cannot bypass backend validation, audit, revision, or privilege
-- checks.
revoke insert, update, delete on table public.users from authenticated;
revoke insert, update, delete on table public.builder_projects from authenticated;
revoke insert, update, delete on table public.website_settings from authenticated;

grant select on table public.users to authenticated;
grant select on table public.builder_projects to authenticated;
grant select on table public.website_settings to authenticated;

grant select, insert, update, delete on table public.users to service_role;
grant select, insert, update, delete on table public.builder_projects to service_role;
grant select, insert, update, delete on table public.website_settings to service_role;

-- Remove inert write policies as defense in depth. A future broad grant must not
-- silently reactivate direct browser mutations.
drop policy if exists users_insert_own on public.users;
drop policy if exists users_update_own on public.users;

drop policy if exists builder_projects_insert_tenant_member on public.builder_projects;
drop policy if exists builder_projects_update_tenant_member on public.builder_projects;
drop policy if exists builder_projects_delete_tenant_admin on public.builder_projects;

drop policy if exists website_settings_insert_member on public.website_settings;
drop policy if exists website_settings_update_member on public.website_settings;
drop policy if exists website_settings_delete_admin on public.website_settings;

notify pgrst, 'reload schema';

commit;
