begin;

create extension if not exists pgcrypto;

create table if not exists public.ecommerce_orders (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  order_number text not null,
  status text not null default 'pending',
  payment_status text not null default 'unpaid',
  payment_method text not null default 'cash_on_delivery',
  currency text not null,
  subtotal numeric(14, 2) not null,
  total numeric(14, 2) not null,
  customer_name text not null,
  customer_email text not null,
  customer_phone text not null,
  address_line_1 text not null,
  address_line_2 text not null default '',
  city text not null,
  postal_code text not null default '',
  country text not null,
  notes text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ecommerce_orders_status_check check (status in ('pending', 'confirmed', 'fulfilled', 'cancelled')),
  constraint ecommerce_orders_payment_status_check check (payment_status in ('unpaid', 'paid', 'refunded')),
  constraint ecommerce_orders_payment_method_check check (payment_method in ('cash_on_delivery')),
  constraint ecommerce_orders_currency_check check (currency ~ '^[A-Z]{3}$'),
  constraint ecommerce_orders_totals_check check (subtotal >= 0 and total >= subtotal),
  unique (tenant_id, order_number),
  unique (tenant_id, id)
);

create table if not exists public.ecommerce_order_items (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  order_id uuid not null,
  product_id uuid references public.ecommerce_products(id) on delete set null,
  sku text not null,
  product_name text not null,
  quantity integer not null,
  unit_price numeric(14, 2) not null,
  line_total numeric(14, 2) not null,
  created_at timestamptz not null default now(),
  constraint ecommerce_order_items_quantity_check check (quantity between 1 and 99),
  constraint ecommerce_order_items_prices_check check (unit_price >= 0 and line_total = unit_price * quantity),
  constraint ecommerce_order_items_order_tenant_fk foreign key (tenant_id, order_id)
    references public.ecommerce_orders(tenant_id, id) on delete cascade
);

create index if not exists ecommerce_orders_tenant_created_idx
  on public.ecommerce_orders (tenant_id, created_at desc);
create index if not exists ecommerce_order_items_order_idx
  on public.ecommerce_order_items (tenant_id, order_id);

alter table public.ecommerce_orders enable row level security;
alter table public.ecommerce_order_items enable row level security;
revoke all on table public.ecommerce_orders, public.ecommerce_order_items from anon, authenticated;
grant select, insert, update, delete on table public.ecommerce_orders, public.ecommerce_order_items to service_role;

drop trigger if exists set_ecommerce_orders_updated_at on public.ecommerce_orders;
create trigger set_ecommerce_orders_updated_at before update on public.ecommerce_orders
for each row execute function public.set_updated_at();

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
      message = 'migration_090_schema_state_missing';
  end if;

  if v_schema_version <> 89 then
    raise exception using
      errcode = 'P0001',
      message = format(
        'migration_090_expected_schema_89_got_%s',
        v_schema_version
      );
  end if;

  update public.application_schema_state
  set schema_version = 90,
      applied_at = now()
  where contract_key = 'core';
end;
$$;

notify pgrst, 'reload schema';
commit;
