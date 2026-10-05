begin;

do $$
declare
  v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version into v_schema_version
  from public.application_schema_state
  where contract_key = 'core' for update;
  if v_schema_version is null then
    raise exception 'migration_117_schema_state_missing';
  end if;
  if v_schema_version <> 116 then
    raise exception 'migration_117_expected_schema_116_got_%', v_schema_version;
  end if;
  update public.application_schema_state
  set schema_version = 117, applied_at = now()
  where contract_key = 'core';
end;
$$;

create table public.elearning_courses (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  name text not null check (char_length(btrim(name)) between 1 and 120),
  description text not null default '' check (char_length(description) <= 4000),
  cover_asset text not null default '' check (
    cover_asset = '' or cover_asset ~ (
      '^/uploads/tenant_' || tenant_id::text || '/builder_assets/[a-f0-9]{32}\.(png|jpg|webp)$'
    )
  ),
  status text not null default 'draft' check (status in ('draft', 'published', 'archived')),
  access_type text not null default 'private' check (access_type in ('free', 'paid', 'private')),
  revision integer not null default 1 check (revision > 0),
  created_by integer references public.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, id)
);
create index elearning_courses_tenant_created_idx on public.elearning_courses (tenant_id, created_at desc, id);
create trigger set_elearning_courses_updated_at
before update on public.elearning_courses
for each row execute function public.set_updated_at();

-- Service-role API only: client access and permanent deletion are not exposed.
alter table public.elearning_courses enable row level security;
revoke all on public.elearning_courses from public, anon, authenticated;
revoke all on public.elearning_courses from service_role;
grant select, insert, update on public.elearning_courses to service_role;

notify pgrst, 'reload schema';
commit;
