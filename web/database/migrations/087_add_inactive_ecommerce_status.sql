begin;

-- Expand ecommerce lifecycle statuses without invalidating existing rows.
alter table public.ecommerce_tags
  drop constraint if exists ecommerce_tags_status_check;
alter table public.ecommerce_tags
  add constraint ecommerce_tags_status_check
  check (status in ('draft', 'active', 'inactive', 'archived'));

alter table public.ecommerce_categories
  drop constraint if exists ecommerce_categories_status_check;
alter table public.ecommerce_categories
  add constraint ecommerce_categories_status_check
  check (status in ('draft', 'active', 'inactive', 'archived'));

alter table public.ecommerce_products
  drop constraint if exists ecommerce_products_status_check;
alter table public.ecommerce_products
  add constraint ecommerce_products_status_check
  check (status in ('draft', 'active', 'inactive', 'archived'));

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
      message = 'migration_087_schema_state_missing';
  end if;

  if v_schema_version <> 86 then
    raise exception using
      errcode = 'P0001',
      message = format(
        'migration_087_expected_schema_86_got_%s',
        v_schema_version
      );
  end if;

  update public.application_schema_state
  set schema_version = 87,
      applied_at = now()
  where contract_key = 'core';
end;
$$;

notify pgrst, 'reload schema';
commit;
