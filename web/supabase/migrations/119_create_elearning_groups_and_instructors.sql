begin;

do $$
declare
  v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version into v_schema_version
  from public.application_schema_state
  where contract_key = 'core' for update;
  if v_schema_version is null then
    raise exception 'migration_119_schema_state_missing';
  end if;
  if v_schema_version <> 118 then
    raise exception 'migration_119_expected_schema_118_got_%', v_schema_version;
  end if;
  update public.application_schema_state
  set schema_version = 119, applied_at = now()
  where contract_key = 'core';
end;
$$;

create table public.elearning_groups (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  name text not null check (char_length(btrim(name)) between 1 and 120),
  description text not null default '' check (char_length(description) <= 4000),
  status text not null default 'active' check (status in ('active', 'archived')),
  revision integer not null default 1 check (revision > 0),
  created_by integer references public.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, id)
);
create index elearning_groups_tenant_created_idx on public.elearning_groups (tenant_id, created_at desc, id);
create trigger set_elearning_groups_updated_at before update on public.elearning_groups
for each row execute function public.set_updated_at();
alter table public.elearning_groups enable row level security;
revoke all on public.elearning_groups from public, anon, authenticated, service_role;
grant select, insert, update on public.elearning_groups to service_role;

create table public.elearning_instructors (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  name text not null check (char_length(btrim(name)) between 1 and 120),
  description text not null default '' check (char_length(description) <= 4000),
  email text not null default '' check (char_length(email) <= 254),
  status text not null default 'active' check (status in ('active', 'archived')),
  revision integer not null default 1 check (revision > 0),
  created_by integer references public.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, id)
);
create index elearning_instructors_tenant_created_idx on public.elearning_instructors (tenant_id, created_at desc, id);
create trigger set_elearning_instructors_updated_at before update on public.elearning_instructors
for each row execute function public.set_updated_at();
alter table public.elearning_instructors enable row level security;
revoke all on public.elearning_instructors from public, anon, authenticated, service_role;
grant select, insert, update on public.elearning_instructors to service_role;

notify pgrst, 'reload schema';
commit;
