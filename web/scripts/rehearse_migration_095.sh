#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WEB_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONTAINER_NAME="madar-095-rehearsal-$RANDOM-$$"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:17-alpine}"

cleanup() { docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$CONTAINER_NAME" \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=1g \
  -e POSTGRES_HOST_AUTH_METHOD=trust "$POSTGRES_IMAGE" >/dev/null
docker exec "$CONTAINER_NAME" sh -c \
  'until pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done'

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" \
  psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
create role anon nologin;
create role authenticated nologin;
create role service_role nologin;
create schema auth;
create table auth.users (id uuid primary key,email_confirmed_at timestamptz,confirmed_at timestamptz);
create function auth.uid() returns uuid language sql stable as $$ select null::uuid $$;
create schema storage;
create table storage.buckets (id text primary key,name text not null,public boolean not null default false,file_size_limit bigint,allowed_mime_types text[]);
create table storage.objects (id uuid primary key default gen_random_uuid(),bucket_id text references storage.buckets(id),name text);
alter table storage.objects enable row level security;
create schema extensions;
create extension pgcrypto schema extensions;
SQL

for migration in "$WEB_ROOT"/database/migrations/*.sql; do
  number="$(basename "$migration" | cut -d_ -f1)"
  ((10#$number > 94)) && continue
  docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" \
    psql -U postgres -v ON_ERROR_STOP=1 -q < "$migration"
done

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" \
  psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
do $$
begin
  if (select schema_version from public.application_schema_state where contract_key='core') <> 94
  then raise exception 'schema_state_not_94_before_upgrade'; end if;
end $$;
SQL

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" \
  psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$WEB_ROOT/database/migrations/095_create_ecommerce_delivery_and_order_operations.sql"

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" \
  psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
do $$
begin
  if (select schema_version from public.application_schema_state where contract_key='core') <> 95
  then raise exception 'schema_state_not_95'; end if;
  if (select count(*) from public.ecommerce_service_areas where active) <> 12
  then raise exception 'canonical_area_count_not_12'; end if;
  if (select count(*) from public.ecommerce_service_areas where code='jerusalem') <> 1
  then raise exception 'jerusalem_count_not_1'; end if;
  if exists (select 1 from public.ecommerce_tenant_service_areas)
  then raise exception 'tenant_areas_not_zero_by_default'; end if;
end $$;

insert into public.tenants (tenant_id,brand_name,owner_name,business_type)
values (951,'Delivery Test','Owner','business');
insert into auth.users (id,email_confirmed_at,confirmed_at)
values ('00000000-0000-0000-0000-000000000951',now(),now());
insert into public.users (auth_id,first_name,last_name,email,tenant_id,account_status,email_verified)
values ('00000000-0000-0000-0000-000000000951','Delivery','Owner','delivery@example.invalid',951,'active',true);
insert into public.website_settings (user_id,tenant_id,subdomain,brand,ecommerce_currency)
select id,951,'delivery-test','Delivery Test','ILS' from public.users where email='delivery@example.invalid';
insert into public.ecommerce_products (
  id,tenant_id,sku,slug,translations,status,price,currency,track_inventory,inventory_quantity,allow_backorder
) values (
  '95100000-0000-0000-0000-000000000001',951,'SKU-951','test-product',
  '{"en":{"name":"Test Product"}}','active',12.50,'ILS',true,5,false
);

do $$
begin
  begin
    perform public.create_ecommerce_order_safe(
      jsonb_build_object(
        'tenant_id',951,'customer_name','Buyer','email','buyer@example.invalid','phone','0590000000',
        'service_area_id','95000000-0000-0000-0000-000000000001','street','Main Street',
        'payment_method','cash_on_delivery','items',jsonb_build_array(jsonb_build_object('product_id','95100000-0000-0000-0000-000000000001','quantity',2))
      ), repeat('a',64), repeat('b',64), repeat('c',64)
    );
    raise exception 'unavailable_area_accepted';
  exception when sqlstate 'P0001' then
    if sqlerrm <> 'ecommerce_delivery_area_unavailable' then raise; end if;
  end;
  if exists (select 1 from public.ecommerce_orders where tenant_id=951)
  then raise exception 'failed_checkout_left_order'; end if;
end $$;

select public.set_ecommerce_delivery_areas_safe(
  951,array['95000000-0000-0000-0000-000000000001'::uuid]
);
select public.create_ecommerce_order_safe(
  jsonb_build_object(
    'tenant_id',951,'customer_name','Buyer','email','buyer@example.invalid','phone','0590000000',
    'service_area_id','95000000-0000-0000-0000-000000000001','street','Main Street',
    'building','7','floor_apartment','2A','address_description','Near the square','delivery_notes','Call first',
    'payment_method','cash_on_delivery','items',jsonb_build_array(jsonb_build_object('product_id','95100000-0000-0000-0000-000000000001','quantity',2))
  ), repeat('a',64), repeat('b',64), repeat('c',64)
);

select public.collect_ecommerce_cod_payment_safe(
  951,(select id from public.ecommerce_orders where tenant_id=951),(select id from public.users where tenant_id=951)
);
select public.transition_ecommerce_order_status_safe(
  951,(select id from public.ecommerce_orders where tenant_id=951),'confirmed',(select id from public.users where tenant_id=951),'Accepted',repeat('d',64)
);
select public.transition_ecommerce_order_status_safe(
  951,(select id from public.ecommerce_orders where tenant_id=951),'preparing',(select id from public.users where tenant_id=951),'Packing',repeat('e',64)
);
select public.transition_ecommerce_order_status_safe(
  951,(select id from public.ecommerce_orders where tenant_id=951),'cancelled',(select id from public.users where tenant_id=951),'Customer request',repeat('f',64)
);
select public.transition_ecommerce_order_status_safe(
  951,(select id from public.ecommerce_orders where tenant_id=951),'cancelled',(select id from public.users where tenant_id=951),'Customer request',repeat('f',64)
);

do $$
begin
  if (select inventory_quantity from public.ecommerce_products where tenant_id=951) <> 5
  then raise exception 'inventory_not_restored_exactly_once'; end if;
  if (select count(*) from public.ecommerce_inventory_movements where tenant_id=951 and movement_type='order_restoration') <> 1
  then raise exception 'restoration_movement_count_invalid'; end if;
  if (select count(*) from public.ecommerce_order_status_history where tenant_id=951) <> 4
  then raise exception 'status_history_not_idempotent'; end if;
  if not exists (
    select 1 from public.ecommerce_orders where tenant_id=951 and status='cancelled'
      and payment_status='collected' and payment_collected_at is not null
      and service_area_code='ramallah' and street='Main Street'
  ) then raise exception 'order_snapshot_lifecycle_or_cod_invalid'; end if;
  begin
    perform public.create_ecommerce_order_safe('{}'::jsonb,repeat('1',64),repeat('2',64));
    raise exception 'legacy_checkout_rpc_did_not_fail_closed';
  exception when sqlstate 'P0001' then
    if sqlerrm <> 'ecommerce_delivery_upgrade_required' then raise; end if;
  end;
end $$;
SQL

echo "migration 095 rehearsal passed on PostgreSQL 17"
