-- Project-scoped roles for tenant-site memberships.
begin;
create extension if not exists pgcrypto;
create table if not exists public.tenant_site_project_roles (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  project_id uuid not null references public.builder_projects(id) on delete cascade,
  role_key text not null,
  capabilities text[] not null default array['view_protected_page','submit_protected_form','make_reservation']::text[],
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz,
  unique(project_id, role_key),
  unique(id, project_id),
  constraint tenant_site_project_roles_key_check check (role_key ~ '^[A-Za-z0-9_-]{1,160}$'),
  constraint tenant_site_project_roles_capability_check check (capabilities <@ array['view_protected_page','submit_protected_form','make_reservation']::text[])
);
create table if not exists public.tenant_site_project_role_assignments (
  membership_id bigint not null references public.tenant_site_memberships(id) on delete cascade,
  project_id uuid not null references public.builder_projects(id) on delete cascade,
  role_id uuid not null,
  assigned_by_user_id integer references public.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key(membership_id, project_id),
  foreign key(role_id, project_id) references public.tenant_site_project_roles(id, project_id) on delete restrict
);
create or replace function public.assign_tenant_site_project_role(
  target_membership_id bigint,
  target_tenant_id integer,
  target_project_id uuid,
  target_role_key text,
  actor_user_id integer default null
) returns uuid language plpgsql security definer set search_path='' as $$
declare selected_role_id uuid;
begin
  if target_role_key !~ '^[A-Za-z0-9_-]{1,160}$' then
    raise exception 'project_role_invalid' using errcode='22023';
  end if;
  if not exists(select 1 from public.builder_projects where id=target_project_id and tenant_id=target_tenant_id)
     or not exists(select 1 from public.tenant_site_memberships where id=target_membership_id and tenant_id=target_tenant_id) then
    raise exception 'membership_project_tenant_mismatch' using errcode='42501';
  end if;
  insert into public.tenant_site_project_roles(tenant_id,project_id,role_key)
  values(target_tenant_id,target_project_id,target_role_key)
  on conflict(project_id,role_key) do update set deleted_at=null,updated_at=now()
  returning id into selected_role_id;
  insert into public.tenant_site_project_role_assignments(membership_id,project_id,role_id,assigned_by_user_id)
  values(target_membership_id,target_project_id,selected_role_id,actor_user_id)
  on conflict(membership_id,project_id) do update set
    role_id=excluded.role_id,assigned_by_user_id=excluded.assigned_by_user_id,updated_at=now();
  return selected_role_id;
end; $$;
revoke all on function public.assign_tenant_site_project_role(bigint,integer,uuid,text,integer) from public,anon,authenticated;
grant execute on function public.assign_tenant_site_project_role(bigint,integer,uuid,text,integer) to service_role;
insert into public.tenant_site_project_roles(tenant_id,project_id,role_key)
select distinct project.tenant_id, project.id,
  case when coalesce(membership.role,'') ~ '^[A-Za-z0-9_-]{1,160}$' then membership.role else 'customer' end
from public.builder_projects project join public.tenant_site_memberships membership on membership.tenant_id=project.tenant_id
on conflict(project_id,role_key) do nothing;
insert into public.tenant_site_project_role_assignments(membership_id,project_id,role_id)
select membership.id, project.id, role.id from public.tenant_site_memberships membership
join public.builder_projects project on project.tenant_id=membership.tenant_id
join public.tenant_site_project_roles role on role.project_id=project.id and role.role_key=
  case when coalesce(membership.role,'') ~ '^[A-Za-z0-9_-]{1,160}$' then membership.role else 'customer' end
on conflict(membership_id,project_id) do nothing;
create index if not exists tenant_site_role_assignments_project_idx on public.tenant_site_project_role_assignments(project_id,role_id);
alter table public.tenant_site_project_roles enable row level security;
alter table public.tenant_site_project_role_assignments enable row level security;
revoke all on public.tenant_site_project_roles,public.tenant_site_project_role_assignments from anon,authenticated;
grant select,insert,update,delete on public.tenant_site_project_roles,public.tenant_site_project_role_assignments to service_role;
notify pgrst,'reload schema'; commit;
