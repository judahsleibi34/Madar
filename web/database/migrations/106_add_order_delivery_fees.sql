begin;

alter table public.ecommerce_orders
  add column delivery_fee numeric(14,2) not null default 0;

alter table public.ecommerce_orders
  add constraint ecommerce_orders_delivery_fee_check
  check (delivery_fee >= 0);

insert into public.ecommerce_delivery_pricing (tenant_id, service_area_id, price)
select mapping.tenant_id, mapping.service_area_id, 0
from public.ecommerce_tenant_service_areas mapping
where mapping.enabled
on conflict (tenant_id, service_area_id) do nothing;

create or replace function public.apply_ecommerce_order_delivery_fee()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_delivery_fee numeric(14,2);
begin
  if new.service_area_id is null then
    new.delivery_fee := 0;
  elsif tg_op = 'INSERT'
    or new.service_area_id is distinct from old.service_area_id then
    select pricing.price
    into v_delivery_fee
    from public.ecommerce_delivery_pricing pricing
    join public.ecommerce_tenant_service_areas mapping
      on mapping.tenant_id = pricing.tenant_id
     and mapping.service_area_id = pricing.service_area_id
     and mapping.enabled
    where pricing.tenant_id = new.tenant_id
      and pricing.service_area_id = new.service_area_id
    for share of pricing, mapping;

    if not found then
      raise exception using
        errcode = 'P0001',
        message = 'ecommerce_delivery_price_unavailable';
    end if;

    new.delivery_fee := v_delivery_fee;
  else
    -- Delivery prices can change after checkout. Keep the amount captured on
    -- the order immutable unless the destination itself changes.
    new.delivery_fee := old.delivery_fee;
  end if;

  new.total := round(
    coalesce(new.subtotal, 0)
      - coalesce(new.discount_total, 0)
      + coalesce(new.delivery_fee, 0),
    2
  );
  return new;
end;
$$;

drop trigger if exists ecommerce_orders_apply_delivery_fee
  on public.ecommerce_orders;
create trigger ecommerce_orders_apply_delivery_fee
before insert or update of subtotal, discount_total, delivery_fee, service_area_id
on public.ecommerce_orders
for each row execute function public.apply_ecommerce_order_delivery_fee();

revoke all on function public.apply_ecommerce_order_delivery_fee() from public, anon, authenticated;
grant execute on function public.apply_ecommerce_order_delivery_fee() to service_role;

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
      message = 'migration_106_schema_state_missing';
  end if;

  if v_schema_version <> 105 then
    raise exception using
      errcode = 'P0001',
      message = format('migration_106_expected_schema_105_got_%s', v_schema_version);
  end if;

  update public.application_schema_state
  set schema_version = 106,
      applied_at = now()
  where contract_key = 'core';
end;
$$;

notify pgrst, 'reload schema';

commit;
