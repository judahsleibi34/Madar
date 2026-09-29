begin;

alter table public.ecommerce_product_variants
  drop constraint if exists ecommerce_product_variants_product_fk;

alter table public.ecommerce_product_variants
  add constraint ecommerce_product_variants_product_fk
  foreign key (tenant_id, product_id)
  references public.ecommerce_products(tenant_id, id)
  on delete cascade;

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
      message = 'migration_112_schema_state_missing';
  end if;

  if v_schema_version <> 111 then
    raise exception using
      errcode = 'P0001',
      message = format('migration_112_expected_schema_111_got_%s', v_schema_version);
  end if;

  update public.application_schema_state
  set schema_version = 112,
      applied_at = now()
  where contract_key = 'core';
end;
$$;

notify pgrst, 'reload schema';

commit;
