begin;

alter table public.ecommerce_delivery_pricing
  add column service_area_id uuid references public.ecommerce_service_areas(id) on delete restrict;

update public.ecommerce_delivery_pricing
set service_area_id = to_area_id
where service_area_id is null;

delete from public.ecommerce_delivery_pricing pricing
using (
  select id
  from (
    select
      id,
      row_number() over (
        partition by tenant_id, service_area_id
        order by updated_at desc, created_at desc, id desc
      ) as duplicate_position
    from public.ecommerce_delivery_pricing
  ) ranked
  where duplicate_position > 1
) duplicates
where pricing.id = duplicates.id;

alter table public.ecommerce_delivery_pricing
  alter column service_area_id set not null;

alter table public.ecommerce_delivery_pricing
  drop constraint ecommerce_delivery_pricing_unique,
  drop constraint ecommerce_delivery_pricing_different_areas,
  drop column from_area_id,
  drop column to_area_id;

alter table public.ecommerce_delivery_pricing
  add constraint ecommerce_delivery_pricing_area_unique unique (tenant_id, service_area_id);

do $$ declare v_schema_version public.application_schema_state.schema_version%TYPE; begin
  select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
  if v_schema_version is null then raise exception using errcode='P0001',message='migration_104_schema_state_missing'; end if;
  if v_schema_version <> 103 then raise exception using errcode='P0001',message=format('migration_104_expected_schema_103_got_%s',v_schema_version); end if;
  update public.application_schema_state set schema_version = 104,applied_at=now() where contract_key = 'core';
end $$;

notify pgrst,'reload schema';
commit;
