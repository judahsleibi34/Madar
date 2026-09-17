-- ============================================================
-- Remove legacy website_settings user_id compatibility from RLS
-- ============================================================

alter table public.website_settings enable row level security;

drop policy if exists website_settings_select_member on public.website_settings;
drop policy if exists website_settings_insert_member on public.website_settings;
drop policy if exists website_settings_update_member on public.website_settings;

create policy website_settings_select_member
on public.website_settings
for select
to authenticated
using (
    website_settings.tenant_id is not null
    and exists (
        select 1
        from public.tenant_memberships tm
        where tm.tenant_id = website_settings.tenant_id
          and tm.auth_id = auth.uid()
          and tm.status = 'active'
    )
);

create policy website_settings_insert_member
on public.website_settings
for insert
to authenticated
with check (
    website_settings.tenant_id is not null
    and exists (
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
    website_settings.tenant_id is not null
    and exists (
        select 1
        from public.tenant_memberships tm
        where tm.tenant_id = website_settings.tenant_id
          and tm.auth_id = auth.uid()
          and tm.status = 'active'
          and tm.role in ('owner', 'admin', 'member')
    )
)
with check (
    website_settings.tenant_id is not null
    and exists (
        select 1
        from public.tenant_memberships tm
        where tm.tenant_id = website_settings.tenant_id
          and tm.auth_id = auth.uid()
          and tm.status = 'active'
          and tm.role in ('owner', 'admin', 'member')
    )
);

notify pgrst, 'reload schema';
