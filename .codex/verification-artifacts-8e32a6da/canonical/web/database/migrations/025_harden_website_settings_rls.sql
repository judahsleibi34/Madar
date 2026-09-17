-- ============================================================
-- Harden website_settings RLS for tenant-owned settings
-- ============================================================

revoke all on table public.website_settings from anon;
revoke all on table public.website_settings from authenticated;

grant select, insert, update
on table public.website_settings
to authenticated;

grant select, insert, update, delete
on table public.website_settings
to service_role;

alter table public.website_settings enable row level security;

drop policy if exists website_settings_select_member on public.website_settings;
drop policy if exists website_settings_insert_member on public.website_settings;
drop policy if exists website_settings_update_member on public.website_settings;
drop policy if exists website_settings_delete_admin on public.website_settings;

create policy website_settings_select_member
on public.website_settings
for select
to authenticated
using (
    exists (
        select 1
        from public.tenant_memberships tm
        where tm.tenant_id = website_settings.tenant_id
          and tm.auth_id = auth.uid()
          and tm.status = 'active'
    )
    or exists (
        select 1
        from public.users u
        where u.id = website_settings.user_id
          and u.auth_id = auth.uid()
    )
);

create policy website_settings_insert_member
on public.website_settings
for insert
to authenticated
with check (
    exists (
        select 1
        from public.users u
        where u.id = website_settings.user_id
          and u.auth_id = auth.uid()
          and (
              website_settings.tenant_id is null
              or u.tenant_id = website_settings.tenant_id
          )
    )
    or exists (
        select 1
        from public.tenant_memberships tm
        where tm.tenant_id = website_settings.tenant_id
          and tm.auth_id = auth.uid()
          and tm.status = 'active'
          and tm.role in ('owner', 'admin', 'member')
    )
);

create policy website_settings_update_member
on public.website_settings
for update
to authenticated
using (
    exists (
        select 1
        from public.tenant_memberships tm
        where tm.tenant_id = website_settings.tenant_id
          and tm.auth_id = auth.uid()
          and tm.status = 'active'
          and tm.role in ('owner', 'admin', 'member')
    )
    or exists (
        select 1
        from public.users u
        where u.id = website_settings.user_id
          and u.auth_id = auth.uid()
    )
)
with check (
    exists (
        select 1
        from public.users u
        where u.id = website_settings.user_id
          and u.auth_id = auth.uid()
          and (
              website_settings.tenant_id is null
              or u.tenant_id = website_settings.tenant_id
          )
    )
    or exists (
        select 1
        from public.tenant_memberships tm
        where tm.tenant_id = website_settings.tenant_id
          and tm.auth_id = auth.uid()
          and tm.status = 'active'
          and tm.role in ('owner', 'admin', 'member')
    )
);
