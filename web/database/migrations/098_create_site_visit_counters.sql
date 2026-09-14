begin;

create table if not exists public.site_visit_counters (
  tenant_id integer primary key references public.tenants(tenant_id) on delete cascade,
  website_visits bigint not null default 0 check (website_visits >= 0),
  store_visits bigint not null default 0 check (store_visits >= 0),
  updated_at timestamptz not null default now()
);

alter table public.site_visit_counters enable row level security;
revoke all on table public.site_visit_counters from public, anon, authenticated;
grant all on table public.site_visit_counters to service_role;

create or replace function public.record_public_site_visit_safe(
  p_tenant_id integer,
  p_surface text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_surface not in ('website', 'store') then
    raise exception using
      errcode = 'P0001',
      message = 'site_visit_surface_invalid';
  end if;

  if not exists (
    select 1
    from public.tenants tenant
    where tenant.tenant_id = p_tenant_id
      and tenant.status = 'active'
  ) then
    raise exception using
      errcode = 'P0002',
      message = 'site_visit_tenant_not_found';
  end if;

  insert into public.site_visit_counters (
    tenant_id,
    website_visits,
    store_visits,
    updated_at
  )
  values (
    p_tenant_id,
    case when p_surface = 'website' then 1 else 0 end,
    case when p_surface = 'store' then 1 else 0 end,
    now()
  )
  on conflict (tenant_id)
  do update set
    website_visits = public.site_visit_counters.website_visits
      + case when p_surface = 'website' then 1 else 0 end,
    store_visits = public.site_visit_counters.store_visits
      + case when p_surface = 'store' then 1 else 0 end,
    updated_at = now();
end;
$$;

revoke all on function public.record_public_site_visit_safe(integer, text)
  from public, anon, authenticated;
grant execute on function public.record_public_site_visit_safe(integer, text)
  to service_role;

do $$
declare
  v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version
  into v_schema_version
  from public.application_schema_state
  where contract_key = 'core'
  for update;

  if v_schema_version is null then
    raise exception using
      errcode = 'P0001',
      message = 'migration_098_schema_state_missing';
  end if;

  if v_schema_version <> 97 then
    raise exception using
      errcode = 'P0001',
      message = format(
        'migration_098_expected_schema_97_got_%s',
        v_schema_version
      );
  end if;

  update public.application_schema_state
  set schema_version = 98,
      applied_at = now()
  where contract_key = 'core';
end;
$$;

notify pgrst, 'reload schema';
commit;
