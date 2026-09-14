begin;

alter table public.website_settings
  add column if not exists ecommerce_currency text;

alter table public.website_settings
  drop constraint if exists website_settings_ecommerce_currency_check;
alter table public.website_settings
  add constraint website_settings_ecommerce_currency_check
  check (ecommerce_currency is null or ecommerce_currency ~ '^[A-Z]{3}$');

with currency_evidence as (
  select tenant_id, currency
  from public.ecommerce_products
  where status = 'active'
  union all
  select tenant_id, currency
  from public.ecommerce_orders
), tenant_currency as (
  select tenant_id, min(currency) as currency
  from currency_evidence
  group by tenant_id
  having count(distinct currency) = 1
)
update public.website_settings settings
set ecommerce_currency = tenant_currency.currency
from tenant_currency
where settings.tenant_id = tenant_currency.tenant_id
  and settings.ecommerce_currency is null;

alter table public.ecommerce_orders
  add column if not exists idempotency_key_hash text;
alter table public.ecommerce_orders
  add column if not exists request_hash text;
alter table public.ecommerce_orders
  add column if not exists discount_total numeric(14, 2) not null default 0;
alter table public.ecommerce_orders
  add column if not exists inventory_restored_at timestamptz;
alter table public.ecommerce_orders
  add column if not exists status_reason text not null default '';

alter table public.ecommerce_orders
  drop constraint if exists ecommerce_orders_status_check;
alter table public.ecommerce_orders
  add constraint ecommerce_orders_status_check
  check (status in ('pending', 'confirmed', 'fulfilled', 'cancelled', 'rejected'));

alter table public.ecommerce_orders
  drop constraint if exists ecommerce_orders_totals_check;
alter table public.ecommerce_orders
  add constraint ecommerce_orders_totals_check
  check (
    subtotal >= 0
    and discount_total >= 0
    and discount_total <= subtotal
    and total = subtotal - discount_total
  );

alter table public.ecommerce_orders
  add constraint ecommerce_orders_idempotency_hash_check
  check (idempotency_key_hash is null or idempotency_key_hash ~ '^[0-9a-f]{64}$') not valid;
alter table public.ecommerce_orders
  add constraint ecommerce_orders_request_hash_check
  check (request_hash is null or request_hash ~ '^[0-9a-f]{64}$') not valid;

create unique index if not exists ecommerce_orders_idempotency_unique_idx
  on public.ecommerce_orders (tenant_id, idempotency_key_hash)
  where idempotency_key_hash is not null;

alter table public.ecommerce_order_items
  add column if not exists product_slug text not null default '';
alter table public.ecommerce_order_items
  add column if not exists product_snapshot jsonb not null default '{}'::jsonb;
alter table public.ecommerce_order_items
  add column if not exists list_unit_price numeric(14, 2);
alter table public.ecommerce_order_items
  add column if not exists discount_amount numeric(14, 2) not null default 0;
alter table public.ecommerce_order_items
  add column if not exists discount_source text;
alter table public.ecommerce_order_items
  add column if not exists inventory_allocated_quantity integer not null default 0;

update public.ecommerce_order_items
set list_unit_price = unit_price
where list_unit_price is null;

alter table public.ecommerce_order_items
  alter column list_unit_price set not null;
alter table public.ecommerce_order_items
  add constraint ecommerce_order_items_discount_check
  check (
    list_unit_price >= 0
    and discount_amount >= 0
    and discount_amount <= list_unit_price * quantity
    and line_total = unit_price * quantity
    and list_unit_price * quantity = line_total + discount_amount
  ) not valid;
alter table public.ecommerce_order_items
  add constraint ecommerce_order_items_inventory_allocation_check
  check (inventory_allocated_quantity between 0 and quantity) not valid;
alter table public.ecommerce_order_items
  add constraint ecommerce_order_items_product_snapshot_check
  check (jsonb_typeof(product_snapshot) = 'object') not valid;

create unique index if not exists ecommerce_orders_tenant_id_id_unique_idx
  on public.ecommerce_orders (tenant_id, id);

create unique index if not exists ecommerce_order_items_tenant_id_id_unique_idx
  on public.ecommerce_order_items (tenant_id, id);

create table if not exists public.ecommerce_inventory_movements (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  product_id uuid references public.ecommerce_products(id) on delete restrict,
  order_id uuid,
  order_item_id uuid,
  movement_type text not null,
  quantity_delta integer not null,
  idempotency_key_hash text not null,
  reason text not null default '',
  created_at timestamptz not null default now(),
  constraint ecommerce_inventory_movements_type_check
    check (movement_type in ('order_allocation', 'order_restoration', 'adjustment')),
  constraint ecommerce_inventory_movements_quantity_check check (quantity_delta <> 0),
  constraint ecommerce_inventory_movements_idempotency_check
    check (idempotency_key_hash ~ '^[0-9a-f]{64}$'),
  constraint ecommerce_inventory_movements_order_tenant_fk
    foreign key (tenant_id, order_id)
    references public.ecommerce_orders(tenant_id, id) on delete restrict,
  constraint ecommerce_inventory_movements_item_tenant_fk
    foreign key (tenant_id, order_item_id)
    references public.ecommerce_order_items(tenant_id, id) on delete restrict,
  unique (tenant_id, idempotency_key_hash)
);

create index if not exists ecommerce_inventory_movements_product_idx
  on public.ecommerce_inventory_movements (tenant_id, product_id, created_at desc);
create index if not exists ecommerce_inventory_movements_order_idx
  on public.ecommerce_inventory_movements (tenant_id, order_id, created_at);
create unique index if not exists ecommerce_inventory_one_restoration_per_item_idx
  on public.ecommerce_inventory_movements (tenant_id, order_item_id)
  where movement_type = 'order_restoration';

alter table public.ecommerce_inventory_movements enable row level security;
revoke all on table public.ecommerce_inventory_movements from anon, authenticated;
grant select, insert, update, delete on table public.ecommerce_inventory_movements to service_role;

create or replace function public.set_ecommerce_currency_safe(
  p_tenant_id integer,
  p_currency text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_currency text := upper(trim(coalesce(p_currency, '')));
  v_settings public.website_settings;
begin
  if v_currency !~ '^[A-Z]{3}$' then
    raise exception using errcode = 'P0001', message = 'ecommerce_currency_invalid';
  end if;

  perform pg_advisory_xact_lock(hashtextextended('ecommerce-currency:' || p_tenant_id::text, 0));

  select * into v_settings
  from public.website_settings
  where tenant_id = p_tenant_id
  for update;

  if not found then
    raise exception using errcode = 'P0002', message = 'ecommerce_settings_not_found';
  end if;

  if v_settings.ecommerce_currency is not null
     and v_settings.ecommerce_currency <> v_currency
     and exists (
       select 1 from public.ecommerce_orders where tenant_id = p_tenant_id limit 1
     ) then
    raise exception using errcode = 'P0001', message = 'ecommerce_currency_locked';
  end if;

  if exists (
    select 1
    from public.ecommerce_orders
    where tenant_id = p_tenant_id
      and currency <> v_currency
  ) then
    raise exception using errcode = 'P0001', message = 'ecommerce_currency_order_mismatch';
  end if;

  if exists (
    select 1
    from public.ecommerce_products
    where tenant_id = p_tenant_id
      and status = 'active'
      and currency <> v_currency
  ) then
    raise exception using errcode = 'P0001', message = 'ecommerce_currency_product_mismatch';
  end if;

  update public.website_settings
  set ecommerce_currency = v_currency
  where tenant_id = p_tenant_id
  returning * into v_settings;

  return to_jsonb(v_settings);
end;
$$;

create or replace function public.create_ecommerce_order_safe(
  p_order jsonb,
  p_idempotency_key_hash text,
  p_request_hash text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_tenant_id integer;
  v_currency text;
  v_existing public.ecommerce_orders;
  v_order public.ecommerce_orders;
  v_product record;
  v_order_item public.ecommerce_order_items;
  v_requested_count integer;
  v_matched_count integer := 0;
  v_subtotal numeric(14, 2) := 0;
  v_line_total numeric(14, 2);
  v_allocated integer;
begin
  if jsonb_typeof(p_order) <> 'object'
     or jsonb_typeof(p_order -> 'items') <> 'array' then
    raise exception using errcode = 'P0001', message = 'ecommerce_order_payload_invalid';
  end if;
  if p_idempotency_key_hash is null or p_idempotency_key_hash !~ '^[0-9a-f]{64}$'
     or p_request_hash is null or p_request_hash !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = 'P0001', message = 'idempotency_key_invalid';
  end if;

  v_tenant_id := nullif(p_order ->> 'tenant_id', '')::integer;
  if v_tenant_id is null then
    raise exception using errcode = 'P0001', message = 'ecommerce_order_payload_invalid';
  end if;
  if coalesce(p_order ->> 'payment_method', '') <> 'cash_on_delivery' then
    raise exception using errcode = 'P0001', message = 'ecommerce_payment_method_invalid';
  end if;

  v_requested_count := jsonb_array_length(p_order -> 'items');
  if v_requested_count < 1 or v_requested_count > 50 then
    raise exception using errcode = 'P0001', message = 'ecommerce_order_items_invalid';
  end if;
  if (
    select count(*) from (
      select item ->> 'product_id'
      from jsonb_array_elements(p_order -> 'items') item
      group by item ->> 'product_id'
    ) unique_items
  ) <> v_requested_count then
    raise exception using errcode = 'P0001', message = 'ecommerce_order_items_duplicate';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(
    concat_ws(':', 'ecommerce-order', v_tenant_id, p_idempotency_key_hash), 0
  ));

  select * into v_existing
  from public.ecommerce_orders
  where tenant_id = v_tenant_id
    and idempotency_key_hash = p_idempotency_key_hash
  for update;
  if found then
    if v_existing.request_hash is distinct from p_request_hash then
      raise exception using errcode = 'P0001', message = 'idempotency_conflict';
    end if;
    return jsonb_build_object('duplicate', true, 'order', to_jsonb(v_existing));
  end if;

  select ecommerce_currency into v_currency
  from public.website_settings
  where tenant_id = v_tenant_id;
  if v_currency is null then
    raise exception using errcode = 'P0001', message = 'ecommerce_currency_configuration_required';
  end if;

  insert into public.ecommerce_orders (
    tenant_id, order_number, status, payment_status, payment_method, currency,
    subtotal, discount_total, total, customer_name, customer_email,
    customer_phone, address_line_1, address_line_2, city, postal_code,
    country, notes, idempotency_key_hash, request_hash
  ) values (
    v_tenant_id,
    'MD-' || to_char(timezone('UTC', now()), 'YYYYMMDD') || '-' || upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 8)),
    'pending', 'unpaid', 'cash_on_delivery', v_currency,
    0, 0, 0,
    trim(coalesce(p_order ->> 'customer_name', '')),
    lower(trim(coalesce(p_order ->> 'email', ''))),
    trim(coalesce(p_order ->> 'phone', '')),
    trim(coalesce(p_order ->> 'address_line_1', '')),
    trim(coalesce(p_order ->> 'address_line_2', '')),
    trim(coalesce(p_order ->> 'city', '')),
    trim(coalesce(p_order ->> 'postal_code', '')),
    trim(coalesce(p_order ->> 'country', '')),
    trim(coalesce(p_order ->> 'notes', '')),
    p_idempotency_key_hash,
    p_request_hash
  ) returning * into v_order;

  for v_product in
    select product.*, requested.quantity
    from jsonb_to_recordset(p_order -> 'items') as requested(product_id uuid, quantity integer)
    join public.ecommerce_products product
      on product.id = requested.product_id
     and product.tenant_id = v_tenant_id
     and product.status = 'active'
    order by product.id
    for update of product
  loop
    v_matched_count := v_matched_count + 1;
    if v_product.quantity is null or v_product.quantity < 1 or v_product.quantity > 99 then
      raise exception using errcode = 'P0001', message = 'ecommerce_quantity_invalid';
    end if;
    if v_product.currency <> v_currency then
      raise exception using errcode = 'P0001', message = 'ecommerce_currency_product_mismatch';
    end if;
    if v_product.track_inventory and not v_product.allow_backorder
       and v_product.quantity > v_product.inventory_quantity then
      raise exception using errcode = 'P0001', message = 'ecommerce_inventory_insufficient';
    end if;

    v_allocated := case
      when v_product.track_inventory then least(v_product.quantity, v_product.inventory_quantity)
      else 0
    end;
    v_line_total := (v_product.price * v_product.quantity)::numeric(14, 2);
    v_subtotal := v_subtotal + v_line_total;

    insert into public.ecommerce_order_items (
      tenant_id, order_id, product_id, sku, product_name, product_slug,
      product_snapshot, quantity, list_unit_price, discount_amount,
      discount_source, unit_price, line_total, inventory_allocated_quantity
    ) values (
      v_tenant_id, v_order.id, v_product.id, v_product.sku,
      coalesce(nullif(v_product.translations -> 'en' ->> 'name', ''), v_product.slug),
      v_product.slug,
      jsonb_build_object(
        'slug', v_product.slug,
        'translations', v_product.translations,
        'brand', v_product.brand,
        'images', v_product.images
      ),
      v_product.quantity, v_product.price, 0, null,
      v_product.price, v_line_total, v_allocated
    ) returning * into v_order_item;

    if v_allocated > 0 then
      update public.ecommerce_products
      set inventory_quantity = inventory_quantity - v_allocated
      where id = v_product.id and tenant_id = v_tenant_id;

      insert into public.ecommerce_inventory_movements (
        tenant_id, product_id, order_id, order_item_id, movement_type,
        quantity_delta, idempotency_key_hash, reason
      ) values (
        v_tenant_id, v_product.id, v_order.id, v_order_item.id,
        'order_allocation', -v_allocated,
        encode(extensions.digest('allocate:' || v_order_item.id::text, 'sha256'), 'hex'),
        'order_created'
      );
    end if;
  end loop;

  if v_matched_count <> v_requested_count then
    raise exception using errcode = 'P0001', message = 'ecommerce_product_unavailable';
  end if;

  update public.ecommerce_orders
  set subtotal = v_subtotal,
      discount_total = 0,
      total = v_subtotal
  where id = v_order.id and tenant_id = v_tenant_id
  returning * into v_order;

  return jsonb_build_object('duplicate', false, 'order', to_jsonb(v_order));
end;
$$;

create or replace function public.restore_ecommerce_order_inventory_safe(
  p_tenant_id integer,
  p_order_id uuid,
  p_reason text,
  p_idempotency_key_hash text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order public.ecommerce_orders;
  v_item record;
  v_movement_id uuid;
  v_restored integer := 0;
begin
  if p_reason not in ('cancelled', 'rejected')
     or p_idempotency_key_hash is null
     or p_idempotency_key_hash !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = 'P0001', message = 'ecommerce_inventory_restoration_invalid';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(
    concat_ws(':', 'ecommerce-order-restore', p_tenant_id, p_order_id), 0
  ));
  select * into v_order
  from public.ecommerce_orders
  where id = p_order_id and tenant_id = p_tenant_id
  for update;
  if not found then
    raise exception using errcode = 'P0002', message = 'ecommerce_order_not_found';
  end if;
  if v_order.status = 'fulfilled' then
    raise exception using errcode = 'P0001', message = 'ecommerce_inventory_restore_fulfilled_order';
  end if;
  if v_order.inventory_restored_at is not null then
    return jsonb_build_object(
      'order_id', p_order_id, 'status', v_order.status,
      'restored_quantity', 0, 'duplicate', true
    );
  end if;

  for v_item in
    select * from public.ecommerce_order_items
    where tenant_id = p_tenant_id
      and order_id = p_order_id
      and inventory_allocated_quantity > 0
    order by id
    for update
  loop
    if v_item.product_id is null then
      raise exception using errcode = 'P0001', message = 'ecommerce_inventory_restore_product_missing';
    end if;
    v_movement_id := null;
    insert into public.ecommerce_inventory_movements (
      tenant_id, product_id, order_id, order_item_id, movement_type,
      quantity_delta, idempotency_key_hash, reason
    ) values (
      p_tenant_id, v_item.product_id, p_order_id, v_item.id,
      'order_restoration', v_item.inventory_allocated_quantity,
      encode(extensions.digest(p_idempotency_key_hash || ':' || v_item.id::text, 'sha256'), 'hex'),
      p_reason
    )
    on conflict do nothing
    returning id into v_movement_id;

    if v_movement_id is not null then
      update public.ecommerce_products
      set inventory_quantity = inventory_quantity + v_item.inventory_allocated_quantity
      where id = v_item.product_id and tenant_id = p_tenant_id;
      if not found then
        raise exception using errcode = 'P0001', message = 'ecommerce_inventory_restore_product_missing';
      end if;
      v_restored := v_restored + v_item.inventory_allocated_quantity;
    end if;
  end loop;

  update public.ecommerce_orders
  set status = p_reason,
      status_reason = p_reason,
      inventory_restored_at = now(),
      updated_at = now()
  where id = p_order_id and tenant_id = p_tenant_id
  returning * into v_order;

  return jsonb_build_object(
    'order_id', p_order_id, 'status', v_order.status,
    'restored_quantity', v_restored, 'duplicate', false
  );
end;
$$;

revoke all on function public.set_ecommerce_currency_safe(integer, text) from public, anon, authenticated;
revoke all on function public.create_ecommerce_order_safe(jsonb, text, text) from public, anon, authenticated;
revoke all on function public.restore_ecommerce_order_inventory_safe(integer, uuid, text, text) from public, anon, authenticated;
grant execute on function public.set_ecommerce_currency_safe(integer, text) to service_role;
grant execute on function public.create_ecommerce_order_safe(jsonb, text, text) to service_role;
grant execute on function public.restore_ecommerce_order_inventory_safe(integer, uuid, text, text) to service_role;

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
    raise exception using errcode = 'P0001', message = 'migration_094_schema_state_missing';
  end if;
  if v_schema_version <> 93 then
    raise exception using errcode = 'P0001',
      message = format('migration_094_expected_schema_93_got_%s', v_schema_version);
  end if;

  update public.application_schema_state
  set schema_version = 94,
      applied_at = now()
  where contract_key = 'core';
end;
$$;

notify pgrst, 'reload schema';
commit;
