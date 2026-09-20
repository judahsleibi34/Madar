begin;

create table public.ecommerce_delivery_pricing (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  from_area_id uuid not null references public.ecommerce_service_areas(id) on delete restrict,
  to_area_id uuid not null references public.ecommerce_service_areas(id) on delete restrict,
  price numeric(14,2) not null constraint ecommerce_delivery_pricing_price_check check (price >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ecommerce_delivery_pricing_unique unique (tenant_id, from_area_id, to_area_id),
  constraint ecommerce_delivery_pricing_different_areas check (from_area_id <> to_area_id)
);

create index ecommerce_delivery_pricing_tenant_idx
  on public.ecommerce_delivery_pricing (tenant_id);

alter table public.ecommerce_delivery_pricing enable row level security;
revoke all on table public.ecommerce_delivery_pricing from anon, authenticated;
grant select, insert, update, delete on table public.ecommerce_delivery_pricing to service_role;

do $$ declare v_schema_version public.application_schema_state.schema_version%TYPE; begin
  select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
  if v_schema_version is null then raise exception using errcode='P0001',message='migration_103_schema_state_missing'; end if;
  if v_schema_version <> 102 then raise exception using errcode='P0001',message=format('migration_103_expected_schema_102_got_%s',v_schema_version); end if;
  update public.application_schema_state set schema_version = 103,applied_at=now() where contract_key = 'core';
end $$;

notify pgrst,'reload schema';
commit;
