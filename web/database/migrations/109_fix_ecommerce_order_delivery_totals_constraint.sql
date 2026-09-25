begin;

alter table public.ecommerce_orders
  drop constraint if exists ecommerce_orders_totals_check;

alter table public.ecommerce_orders
  add constraint ecommerce_orders_totals_check
  check (
    subtotal >= 0
    and discount_total >= 0
    and discount_total <= subtotal
    and delivery_fee >= 0
    and total = subtotal - discount_total + delivery_fee
  );

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
      message = 'migration_109_schema_state_missing';
  end if;

  if v_schema_version <> 108 then
    raise exception using
      errcode = 'P0001',
      message = format('migration_109_expected_schema_108_got_%s', v_schema_version);
  end if;

  update public.application_schema_state
  set schema_version = 109,
      applied_at = now()
  where contract_key = 'core';
end;
$$;

notify pgrst, 'reload schema';

commit;
