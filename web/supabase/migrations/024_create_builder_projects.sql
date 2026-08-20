/* ============================================================
   023_create_builder_projects.sql

   Purpose:
   - Add backend-backed Page Builder project storage.
   - Store full draft project JSON first.
   - Store immutable published JSON snapshots on publish.
   ============================================================ */

begin;

create table if not exists public.builder_projects (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  owner_user_id integer references public.users(id) on delete set null,
  name text not null,
  slug text not null,
  status text not null default 'draft',
  draft_schema jsonb not null default '{}'::jsonb,
  published_schema jsonb,
  published_version integer not null default 0,
  last_published_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint builder_projects_tenant_slug_unique unique (tenant_id, slug),
  constraint builder_projects_status_check check (status in ('draft', 'published', 'archived'))
);

drop trigger if exists set_builder_projects_updated_at on public.builder_projects;

create trigger set_builder_projects_updated_at
before update on public.builder_projects
for each row
execute function public.set_updated_at();

create index if not exists builder_projects_tenant_id_idx
on public.builder_projects (tenant_id);

create index if not exists builder_projects_slug_idx
on public.builder_projects (slug);

create index if not exists builder_projects_status_idx
on public.builder_projects (status);

grant select, insert, update, delete
on table public.builder_projects
to authenticated;

grant select, insert, update, delete
on table public.builder_projects
to service_role;

alter table public.builder_projects enable row level security;

drop policy if exists builder_projects_select_tenant_member on public.builder_projects;
drop policy if exists builder_projects_insert_tenant_member on public.builder_projects;
drop policy if exists builder_projects_update_tenant_member on public.builder_projects;
drop policy if exists builder_projects_delete_tenant_admin on public.builder_projects;

create policy builder_projects_select_tenant_member
on public.builder_projects
for select
to authenticated
using (
  exists (
    select 1
    from public.tenant_memberships tm
    where tm.tenant_id = builder_projects.tenant_id
      and tm.auth_id = auth.uid()
      and tm.status = 'active'
  )
);

create policy builder_projects_insert_tenant_member
on public.builder_projects
for insert
to authenticated
with check (
  exists (
    select 1
    from public.tenant_memberships tm
    where tm.tenant_id = builder_projects.tenant_id
      and tm.auth_id = auth.uid()
      and tm.status = 'active'
      and tm.role in ('owner', 'admin', 'member')
  )
);

create policy builder_projects_update_tenant_member
on public.builder_projects
for update
to authenticated
using (
  exists (
    select 1
    from public.tenant_memberships tm
    where tm.tenant_id = builder_projects.tenant_id
      and tm.auth_id = auth.uid()
      and tm.status = 'active'
      and tm.role in ('owner', 'admin', 'member')
  )
)
with check (
  exists (
    select 1
    from public.tenant_memberships tm
    where tm.tenant_id = builder_projects.tenant_id
      and tm.auth_id = auth.uid()
      and tm.status = 'active'
      and tm.role in ('owner', 'admin', 'member')
  )
);

create policy builder_projects_delete_tenant_admin
on public.builder_projects
for delete
to authenticated
using (
  exists (
    select 1
    from public.tenant_memberships tm
    where tm.tenant_id = builder_projects.tenant_id
      and tm.auth_id = auth.uid()
      and tm.status = 'active'
      and tm.role in ('owner', 'admin')
  )
);

notify pgrst, 'reload schema';

commit;
