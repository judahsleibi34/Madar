#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WEB_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONTAINER_NAME="madar-096-rehearsal-$RANDOM-$$"
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
  ((10#$number > 95)) && continue
  docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" \
    psql -U postgres -v ON_ERROR_STOP=1 -q < "$migration"
done

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" \
  psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
do $$ begin
  if (select schema_version from public.application_schema_state where contract_key='core') <> 95
  then raise exception 'schema_state_not_95_before_upgrade'; end if;
end $$;
SQL

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" \
  psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$WEB_ROOT/database/migrations/096_create_ecommerce_product_variants.sql"

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" \
  psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
do $$ begin
  if (select schema_version from public.application_schema_state where contract_key='core') <> 96
  then raise exception 'schema_state_not_96'; end if;
end $$;

insert into public.tenants(tenant_id,brand_name,owner_name) values(961,'Variant Store','Owner');
insert into auth.users(id) values('00000000-0000-0000-0000-000000000961');
insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status)
values('00000000-0000-0000-0000-000000000961','Owner','One','owner-961@example.invalid',961,'active');
insert into public.website_settings(user_id,tenant_id,subdomain,ecommerce_currency)
select id,961,'variant-store','ILS' from public.users where tenant_id=961;
insert into public.ecommerce_tenant_service_areas(tenant_id,service_area_id,enabled)
values(961,'95000000-0000-0000-0000-000000000001',true);
insert into public.ecommerce_products(id,tenant_id,sku,slug,translations,status,price,currency,inventory_quantity)
values
('96100000-0000-0000-0000-000000000001',961,'SIMPLE-961','simple-961','{"en":{"name":"Simple"}}','active',10,'ILS',1),
('96100000-0000-0000-0000-000000000002',961,'SHIRT-961','shirt-961','{"en":{"name":"Shirt"}}','draft',20,'ILS',0);

select public.save_ecommerce_product_aggregate_safe(
  961,'96100000-0000-0000-0000-000000000002',
  '[{"id":"96110000-0000-0000-0000-000000000001","name_translations":{"en":"Material","ar":"الخامة"},"value_translations":{"en":"Cotton","ar":"قطن"},"normalized_name":"material","sort_order":0}]',
  '[{"id":"96120000-0000-0000-0000-000000000001","client_id":"96120000-0000-0000-0000-000000000001","code":"finish","name_translations":{"en":"Finish","ar":"التشطيب"},"normalized_name":"finish","required":true,"sort_order":0,"values":[{"id":"96130000-0000-0000-0000-000000000001","code":"matte","value_translations":{"en":"Matte","ar":"مطفي"},"normalized_value":"matte","active":true,"sort_order":0},{"id":"96130000-0000-0000-0000-000000000002","code":"gloss","value_translations":{"en":"Gloss"},"normalized_value":"gloss","active":true,"sort_order":1}]}]',
  '[{"id":"96140000-0000-0000-0000-000000000001","sku":"SHIRT-961-MATTE","barcode":"961-M","price_override":24,"track_inventory":true,"inventory_quantity":1,"low_stock_threshold":0,"allow_backorder":false,"images":["https://example.invalid/matte.webp"],"active":true,"option_value_ids":["96130000-0000-0000-0000-000000000001"]},{"id":"96140000-0000-0000-0000-000000000002","sku":"SHIRT-961-GLOSS","price_override":null,"track_inventory":true,"inventory_quantity":1,"low_stock_threshold":0,"allow_backorder":false,"images":[],"active":true,"option_value_ids":["96130000-0000-0000-0000-000000000002"]}]'
);
update public.ecommerce_products set status='active' where id='96100000-0000-0000-0000-000000000002';

select public.create_ecommerce_order_safe(
  '{"tenant_id":961,"customer_name":"Buyer","email":"buyer@example.invalid","phone":"0590000961","street":"Main Street","service_area_id":"95000000-0000-0000-0000-000000000001","payment_method":"cash_on_delivery","items":[{"product_id":"96100000-0000-0000-0000-000000000002","variant_id":"96140000-0000-0000-0000-000000000001","quantity":1}]}',
  repeat('a',64),repeat('b',64),repeat('c',64)
);
select public.create_ecommerce_order_safe(
  '{"tenant_id":961,"customer_name":"Buyer","email":"buyer@example.invalid","phone":"0590000961","street":"Main Street","service_area_id":"95000000-0000-0000-0000-000000000001","payment_method":"cash_on_delivery","items":[{"product_id":"96100000-0000-0000-0000-000000000001","quantity":1}]}',
  repeat('d',64),repeat('e',64),repeat('f',64)
);

do $$ declare v_variant_order uuid; v_simple_order uuid; v_snapshot jsonb; begin
  if (select inventory_quantity from public.ecommerce_product_variants where sku='SHIRT-961-MATTE') <> 0
  then raise exception 'variant_not_allocated'; end if;
  if (select inventory_quantity from public.ecommerce_product_variants where sku='SHIRT-961-GLOSS') <> 1
  then raise exception 'independent_variant_changed'; end if;
  if (select inventory_quantity from public.ecommerce_products where sku='SIMPLE-961') <> 0
  then raise exception 'simple_not_allocated'; end if;
  if not exists(select 1 from public.ecommerce_order_items where variant_id='96140000-0000-0000-0000-000000000001' and sku='SHIRT-961-MATTE' and unit_price=24 and variant_snapshot->>'barcode'='961-M')
  then raise exception 'variant_commercial_snapshot_invalid'; end if;
  if not exists(select 1 from public.ecommerce_inventory_movements where variant_id='96140000-0000-0000-0000-000000000001' and quantity_delta=-1)
  then raise exception 'variant_movement_invalid'; end if;
  select order_id,selected_options_snapshot into v_variant_order,v_snapshot
  from public.ecommerce_order_items where variant_id='96140000-0000-0000-0000-000000000001';
  update public.ecommerce_product_options set name_translations='{"en":"Surface"}' where id='96120000-0000-0000-0000-000000000001';
  update public.ecommerce_product_option_values set value_translations='{"en":"Flat"}' where id='96130000-0000-0000-0000-000000000001';
  update public.ecommerce_product_variants set active=false where id='96140000-0000-0000-0000-000000000001';
  if (select selected_options_snapshot from public.ecommerce_order_items where order_id=v_variant_order) <> v_snapshot
  then raise exception 'historical_snapshot_changed'; end if;
  perform public.restore_ecommerce_order_inventory_safe(961,v_variant_order,'cancelled',repeat('1',64));
  perform public.restore_ecommerce_order_inventory_safe(961,v_variant_order,'cancelled',repeat('1',64));
  if (select inventory_quantity from public.ecommerce_product_variants where sku='SHIRT-961-MATTE') <> 1
  then raise exception 'variant_restore_not_exactly_once'; end if;
  select order_id into v_simple_order from public.ecommerce_order_items where product_id='96100000-0000-0000-0000-000000000001';
  perform public.restore_ecommerce_order_inventory_safe(961,v_simple_order,'rejected',repeat('2',64));
  if (select inventory_quantity from public.ecommerce_products where sku='SIMPLE-961') <> 1
  then raise exception 'simple_restore_regression'; end if;
end $$;
SQL

if [[ "${MADAR_REHEARSE_TO_099:-false}" == true ]]; then
  docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q < "$WEB_ROOT/database/verification/099_preservation_seed.sql"
  for number in 097 098 099; do
    files=("$WEB_ROOT"/database/migrations/"${number}"_*.sql)
    docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q < "${files[0]}"
    docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q -v expected="$((10#$number))" <<'SQL'
select schema_version = :expected as correct from public.application_schema_state where contract_key='core' \gset
\if :correct
\else
\quit 1
\endif
SQL
  done
  docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q < "$WEB_ROOT/database/verification/099_preservation_assertions.sql"
  echo "096 -> 097 -> 098 -> 099 preservation and functional rehearsal passed"
fi

echo "migration 096 rehearsal passed on PostgreSQL 17"
