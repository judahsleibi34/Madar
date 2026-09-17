#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WEB_ROOT="$(cd -- "$SCRIPT_DIR/canonical/web" && pwd)"
CONTAINER_NAME="madar-097-rehearsal-$RANDOM-$$"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:17-alpine}"
cleanup() { docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$CONTAINER_NAME" --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=1g -e POSTGRES_HOST_AUTH_METHOD=trust "$POSTGRES_IMAGE" >/dev/null
docker exec "$CONTAINER_NAME" sh -c 'until pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done'
docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
create role anon nologin; create role authenticated nologin; create role service_role nologin;
create schema auth; create table auth.users(id uuid primary key,email_confirmed_at timestamptz,confirmed_at timestamptz);
create function auth.uid() returns uuid language sql stable as $$ select null::uuid $$;
create schema storage; create table storage.buckets(id text primary key,name text not null,public boolean not null default false,file_size_limit bigint,allowed_mime_types text[]);
create table storage.objects(id uuid primary key default gen_random_uuid(),bucket_id text references storage.buckets(id),name text); alter table storage.objects enable row level security;
create schema extensions; create extension pgcrypto schema extensions;
SQL

for migration in "$WEB_ROOT"/database/migrations/*.sql; do
  number="$(basename "$migration" | cut -d_ -f1)"
  ((10#$number > 96)) && continue
  docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q < "$migration"
done

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
do $$ begin if (select schema_version from public.application_schema_state where contract_key='core')<>96 then raise exception 'schema_state_not_96_before_upgrade'; end if; end $$;
SQL
docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'

insert into public.tenants(tenant_id,brand_name,owner_name) values(961,'Historic Store','Owner');
insert into auth.users(id,email_confirmed_at) values('00000000-0000-0000-0000-000000000961',now());
insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified,email_verified_at) values('00000000-0000-0000-0000-000000000961','Owner','One','owner-961@example.invalid',961,'active',true,now());
insert into public.website_settings(user_id,tenant_id,subdomain,ecommerce_currency) select id,961,'historic-store','ILS' from public.users where tenant_id=961;
insert into public.ecommerce_tenant_service_areas(tenant_id,service_area_id,enabled) values(961,'95000000-0000-0000-0000-000000000001',true);
insert into public.ecommerce_products(id,tenant_id,sku,slug,translations,status,price,currency,inventory_quantity) values
('96100000-0000-0000-0000-000000000001',961,'SIMPLE-961','simple-961','{"en":{"name":"Simple product"}}','active',10,'ILS',17),
('96100000-0000-0000-0000-000000000002',961,'CLASSIC-961','classic-t-shirt','{"en":{"name":"Classic T-Shirt"},"ar":{"name":"قميص كلاسيكي"}}','draft',20,'ILS',0);
select public.save_ecommerce_product_aggregate_safe(961,'96100000-0000-0000-0000-000000000002','[]','[{"id":"96100000-0000-0000-0000-000000000020","client_id":"size","code":"size","name_translations":{"en":"Size","ar":"المقاس"},"normalized_name":"size","required":true,"sort_order":0,"values":[{"id":"96100000-0000-0000-0000-000000000030","code":"s","value_translations":{"en":"S"},"normalized_value":"s","active":true,"sort_order":0},{"id":"96100000-0000-0000-0000-000000000031","code":"m","value_translations":{"en":"M"},"normalized_value":"m","active":true,"sort_order":1},{"id":"96100000-0000-0000-0000-000000000032","code":"l","value_translations":{"en":"L"},"normalized_value":"l","active":true,"sort_order":2}]},{"id":"96100000-0000-0000-0000-000000000021","client_id":"color","code":"color","name_translations":{"en":"Color","ar":"اللون"},"normalized_name":"color","required":true,"sort_order":1,"values":[{"id":"96100000-0000-0000-0000-000000000040","code":"red","value_translations":{"en":"Red"},"normalized_value":"red","active":true,"sort_order":0},{"id":"96100000-0000-0000-0000-000000000041","code":"green","value_translations":{"en":"Green"},"normalized_value":"green","active":true,"sort_order":1},{"id":"96100000-0000-0000-0000-000000000042","code":"blue","value_translations":{"en":"Blue"},"normalized_value":"blue","active":true,"sort_order":2}]}]','[{"id":"96100000-0000-0000-0000-000000000050","sku":"SHIRT-S-RED","barcode":"BAR-0","price_override":25,"compare_at_price_override":40,"track_inventory":true,"inventory_quantity":11,"low_stock_threshold":2,"allow_backorder":false,"images":["https://example.invalid/shirt-0.webp"],"active":true,"option_value_ids":["96100000-0000-0000-0000-000000000030","96100000-0000-0000-0000-000000000040"]},{"id":"96100000-0000-0000-0000-000000000051","sku":"SHIRT-M-RED","barcode":"BAR-1","price_override":null,"compare_at_price_override":41,"track_inventory":true,"inventory_quantity":12,"low_stock_threshold":3,"allow_backorder":true,"images":["https://example.invalid/shirt-1.webp"],"active":true,"option_value_ids":["96100000-0000-0000-0000-000000000031","96100000-0000-0000-0000-000000000040"]},{"id":"96100000-0000-0000-0000-000000000052","sku":"SHIRT-M-BLUE","barcode":"BAR-2","price_override":27,"compare_at_price_override":42,"track_inventory":true,"inventory_quantity":13,"low_stock_threshold":4,"allow_backorder":false,"images":["https://example.invalid/shirt-2.webp"],"active":true,"option_value_ids":["96100000-0000-0000-0000-000000000031","96100000-0000-0000-0000-000000000042"]}]');
update public.ecommerce_products set status='active' where id='96100000-0000-0000-0000-000000000002';
select public.create_ecommerce_order_safe('{"tenant_id":961,"customer_name":"Historic Buyer","email":"buyer@example.invalid","phone":"0590000961","street":"Main Street","service_area_id":"95000000-0000-0000-0000-000000000001","payment_method":"cash_on_delivery","items":[{"product_id":"96100000-0000-0000-0000-000000000002","variant_id":"96100000-0000-0000-0000-000000000050","quantity":2},{"product_id":"96100000-0000-0000-0000-000000000001","quantity":1}]}',repeat('6',64),repeat('6',64),repeat('6',64));
update public.ecommerce_product_option_values set active=false where id='96100000-0000-0000-0000-000000000040';
update public.ecommerce_product_variants set active=false where id in ('96100000-0000-0000-0000-000000000050','96100000-0000-0000-0000-000000000051');
create schema verification;
create table verification.baseline(table_name text primary key, data jsonb);
insert into verification.baseline select 'tenants',coalesce(jsonb_agg(to_jsonb(t)-'updated_at' order by to_jsonb(t)::text),'[]') from public.tenants t where tenant_id=961;
insert into verification.baseline select 'users',coalesce(jsonb_agg(to_jsonb(t)-'updated_at' order by to_jsonb(t)::text),'[]') from public.users t where tenant_id=961;
insert into verification.baseline select 'website_settings',coalesce(jsonb_agg(to_jsonb(t)-'updated_at' order by to_jsonb(t)::text),'[]') from public.website_settings t where tenant_id=961;
insert into verification.baseline select 'ecommerce_products',coalesce(jsonb_agg(to_jsonb(t)-'updated_at' order by to_jsonb(t)::text),'[]') from public.ecommerce_products t where tenant_id=961;
insert into verification.baseline select 'ecommerce_product_options',coalesce(jsonb_agg(to_jsonb(t)-'updated_at' order by to_jsonb(t)::text),'[]') from public.ecommerce_product_options t where tenant_id=961;
insert into verification.baseline select 'ecommerce_product_option_values',coalesce(jsonb_agg(to_jsonb(t)-'updated_at' order by to_jsonb(t)::text),'[]') from public.ecommerce_product_option_values t where tenant_id=961;
insert into verification.baseline select 'ecommerce_product_variants',coalesce(jsonb_agg(to_jsonb(t)-'updated_at' order by to_jsonb(t)::text),'[]') from public.ecommerce_product_variants t where tenant_id=961;
insert into verification.baseline select 'ecommerce_variant_option_values',coalesce(jsonb_agg(to_jsonb(t)-'updated_at' order by to_jsonb(t)::text),'[]') from public.ecommerce_variant_option_values t where tenant_id=961;
insert into verification.baseline select 'ecommerce_orders',coalesce(jsonb_agg(to_jsonb(t)-'updated_at' order by to_jsonb(t)::text),'[]') from public.ecommerce_orders t where tenant_id=961;
insert into verification.baseline select 'ecommerce_order_items',coalesce(jsonb_agg(to_jsonb(t)-'updated_at' order by to_jsonb(t)::text),'[]') from public.ecommerce_order_items t where tenant_id=961;
insert into verification.baseline select 'ecommerce_inventory_movements',coalesce(jsonb_agg(to_jsonb(t)-'updated_at' order by to_jsonb(t)::text),'[]') from public.ecommerce_inventory_movements t where tenant_id=961;
create table verification.catalog_contract as select c.conname,pg_get_constraintdef(c.oid) definition from pg_constraint c join pg_class t on t.oid=c.conrelid where t.relname in ('ecommerce_products','ecommerce_product_options','ecommerce_product_option_values','ecommerce_product_variants','ecommerce_variant_option_values');
create table verification.catalog_indexes as select indexname,indexdef from pg_indexes where tablename in ('ecommerce_products','ecommerce_product_options','ecommerce_product_option_values','ecommerce_product_variants','ecommerce_variant_option_values');

SQL
docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q < "$WEB_ROOT/database/migrations/097_create_ecommerce_verified_loyalty_core.sql"
docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'

do $ declare r record; current_data jsonb; begin
 for r in select * from verification.baseline loop
 execute format('select coalesce(jsonb_agg(to_jsonb(t)-''updated_at''-''customer_id''-''loyalty_entitlement_id''-''display_type''-''color_hex'' order by (to_jsonb(t)-''customer_id''-''loyalty_entitlement_id''-''display_type''-''color_hex'')::text),''[]'') from public.%I t where tenant_id=961',r.table_name) into current_data;
 if current_data is distinct from r.data then raise exception 'preservation_failed_%',r.table_name; end if;
 end loop;
 if exists(select 1 from verification.catalog_contract b left join pg_constraint c on c.conname=b.conname where c.oid is null or pg_get_constraintdef(c.oid)<>b.definition) then raise exception 'historical_constraint_changed'; end if;
 if exists(select 1 from verification.catalog_indexes b left join pg_indexes i on i.indexname=b.indexname where i.indexname is null or i.indexdef<>b.indexdef) then raise exception 'historical_index_changed'; end if;
end $;

SQL

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
do $$ begin if (select schema_version from public.application_schema_state where contract_key='core')<>97 then raise exception 'schema_state_not_97'; end if; end $$;

insert into public.tenants(tenant_id,brand_name,owner_name) values(971,'Loyalty Store','Owner'),(972,'Customer Home','Customer');
insert into auth.users(id,email_confirmed_at) values('00000000-0000-0000-0000-000000000971',now()),('00000000-0000-0000-0000-000000000972',now());
insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified,email_verified_at) values
('00000000-0000-0000-0000-000000000971','Owner','One','owner-971@example.invalid',971,'active',true,now()),
('00000000-0000-0000-0000-000000000972','Customer','One','customer-972@example.invalid',972,'active',true,now());
insert into public.website_settings(user_id,tenant_id,subdomain,ecommerce_currency) select id,tenant_id,case tenant_id when 971 then 'loyalty-store' else 'customer-home' end,'ILS' from public.users where tenant_id in(971,972);
insert into public.ecommerce_tenant_service_areas(tenant_id,service_area_id,enabled) values(971,'95000000-0000-0000-0000-000000000001',true);
insert into public.ecommerce_products(id,tenant_id,sku,slug,translations,status,price,currency,inventory_quantity) values
('97100000-0000-0000-0000-000000000001',971,'EARN-971','earn-971','{"en":{"name":"Earn"}}','active',100,'ILS',20),
('97100000-0000-0000-0000-000000000002',971,'REWARD-971','reward-971','{"en":{"name":"Reward"}}','draft',100,'ILS',0);
select public.save_ecommerce_product_aggregate_safe(971,'97100000-0000-0000-0000-000000000002','[]',
'[{"id":"97120000-0000-0000-0000-000000000001","client_id":"size","code":"size","name_translations":{"en":"Size"},"normalized_name":"size","required":true,"sort_order":0,"values":[{"id":"97130000-0000-0000-0000-000000000001","code":"one","value_translations":{"en":"One"},"normalized_value":"one","active":true,"sort_order":0}]}]',
'[{"id":"97140000-0000-0000-0000-000000000001","sku":"REWARD-971-ONE","price_override":100,"track_inventory":true,"inventory_quantity":20,"low_stock_threshold":1,"allow_backorder":false,"images":[],"active":true,"option_value_ids":["97130000-0000-0000-0000-000000000001"]}]');
update public.ecommerce_products set status='active' where id='97100000-0000-0000-0000-000000000002';

select public.save_ecommerce_loyalty_rule_safe(971,(select id from public.users where tenant_id=971),true,500,5,'97100000-0000-0000-0000-000000000002','fixed_period',30);
select public.create_ecommerce_order_safe('{"tenant_id":971,"customer_name":"Typed guest text","email":"untrusted@example.invalid","phone":"000","street":"Main Street","service_area_id":"95000000-0000-0000-0000-000000000001","payment_method":"cash_on_delivery","items":[{"product_id":"97100000-0000-0000-0000-000000000001","quantity":1}]}',repeat('a',64),repeat('b',64),repeat('c',64),(select id from public.users where tenant_id=972));

do $$ declare oid uuid; actor integer; begin
  select id into oid from public.ecommerce_orders where idempotency_key_hash=repeat('a',64); select id into actor from public.users where tenant_id=971;
  perform public.collect_ecommerce_cod_payment_safe(971,oid,actor);
  perform public.transition_ecommerce_order_status_safe(971,oid,'confirmed',actor,'',repeat('1',64));
  perform public.transition_ecommerce_order_status_safe(971,oid,'preparing',actor,'',repeat('2',64));
  perform public.transition_ecommerce_order_status_safe(971,oid,'out_for_delivery',actor,'',repeat('3',64));
  perform public.transition_ecommerce_order_status_safe(971,oid,'delivered',actor,'',repeat('4',64));
  perform public.collect_ecommerce_cod_payment_safe(971,oid,actor);
  perform public.transition_ecommerce_order_status_safe(971,oid,'delivered',actor,'',repeat('4',64));
end $$;
SQL
CONCURRENT_ORDER_ID="$(docker exec "$CONTAINER_NAME" psql -U postgres -Atqc "select id from public.ecommerce_orders where idempotency_key_hash=repeat('0',64)")"
MERCHANT_ACTOR_ID="$(docker exec "$CONTAINER_NAME" psql -U postgres -Atqc "select id from public.users where tenant_id=971")"
docker exec "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q -c "select public.collect_ecommerce_cod_payment_safe(971,'$CONCURRENT_ORDER_ID',$MERCHANT_ACTOR_ID)" >/dev/null &
first_pid=$!
docker exec "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q -c "select public.transition_ecommerce_order_status_safe(971,'$CONCURRENT_ORDER_ID','delivered',$MERCHANT_ACTOR_ID,'',repeat('5',64))" >/dev/null &
second_pid=$!
wait "$first_pid" "$second_pid"
docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<SQL
do \$\$ begin
  if (select count(*) from public.ecommerce_loyalty_transactions where order_id='$CONCURRENT_ORDER_ID' and transaction_type='earn')<>1 then raise exception 'concurrent_earning_not_exactly_once'; end if;
  if (select sum(points_delta) from public.ecommerce_loyalty_transactions where tenant_id=971)<>(select current_balance from public.ecommerce_loyalty_accounts where tenant_id=971) then raise exception 'concurrent_projection_mismatch'; end if;
end \$\$;
SQL

source "$SCRIPT_DIR/rehearse-extra.sh"
echo "migration 097 loyalty rehearsal passed on PostgreSQL 17"

do $$ begin
  if (select count(*) from public.ecommerce_loyalty_transactions where transaction_type='earn')<>1 then raise exception 'earning_not_exactly_once'; end if;
  if (select points_delta from public.ecommerce_loyalty_transactions where transaction_type='earn')<>5 then raise exception 'floor_formula_wrong'; end if;
  if (select count(*) from public.ecommerce_loyalty_transactions where transaction_type='reward_unlock')<>1 then raise exception 'unlock_not_exactly_once'; end if;
  if (select current_balance from public.ecommerce_loyalty_accounts where tenant_id=971)<>0 then raise exception 'threshold_not_consumed'; end if;
end $$;

select public.create_ecommerce_order_safe('{"tenant_id":971,"customer_name":"Customer","email":"customer-972@example.invalid","phone":"059","street":"Main Street","service_area_id":"95000000-0000-0000-0000-000000000001","payment_method":"cash_on_delivery","items":[{"product_id":"97100000-0000-0000-0000-000000000002","variant_id":"97140000-0000-0000-0000-000000000001","quantity":2}]}',repeat('d',64),repeat('e',64),repeat('f',64),(select id from public.users where tenant_id=972));
select public.create_ecommerce_order_safe('{"tenant_id":971,"customer_name":"Guest","email":"customer-972@example.invalid","phone":"059","street":"Main Street","service_area_id":"95000000-0000-0000-0000-000000000001","payment_method":"cash_on_delivery","items":[{"product_id":"97100000-0000-0000-0000-000000000002","variant_id":"97140000-0000-0000-0000-000000000001","quantity":1}]}',repeat('7',64),repeat('8',64),repeat('9',64),null);

do $$ declare ent uuid; actor integer; begin
  if not exists(select 1 from public.ecommerce_orders where idempotency_key_hash=repeat('d',64) and subtotal=200 and discount_total=20 and total=180 and customer_id=(select id from public.users where tenant_id=972)) then raise exception 'variant_quantity_discount_wrong'; end if;
  if not exists(select 1 from public.ecommerce_order_items where order_id=(select id from public.ecommerce_orders where idempotency_key_hash=repeat('d',64)) and list_unit_price=100 and discount_amount=20 and unit_price=90 and line_total=180 and discount_source='loyalty' and loyalty_entitlement_id is not null) then raise exception 'discount_snapshot_wrong'; end if;
  if not exists(select 1 from public.ecommerce_orders where idempotency_key_hash=repeat('7',64) and customer_id is null and discount_total=0 and total=100) then raise exception 'guest_contact_matched_identity'; end if;
  select id into ent from public.ecommerce_loyalty_entitlements where tenant_id=971 and status='active'; select id into actor from public.users where tenant_id=971;
  perform public.revoke_ecommerce_loyalty_entitlement_safe(971,ent,actor); perform public.revoke_ecommerce_loyalty_entitlement_safe(971,ent,actor);
  if (select current_balance from public.ecommerce_loyalty_accounts where tenant_id=971)<>5 then raise exception 'revocation_restore_wrong'; end if;
  if (select count(*) from public.ecommerce_loyalty_transactions where transaction_type='reward_unlock_reversal')<>1 then raise exception 'revocation_not_exactly_once'; end if;
end $$;

select public.save_ecommerce_loyalty_rule_safe(971,(select id from public.users where tenant_id=971),true,600,5,'97100000-0000-0000-0000-000000000002','fixed_period',10);
do $$ declare oid uuid; actor integer; balance_before bigint; begin
  if not exists(select 1 from public.ecommerce_loyalty_entitlements where tenant_id=971 and rule_version=1 and status='revoked' and validity_days=30 and reward_discount_basis_points=1000) then raise exception 'entitlement_snapshot_changed_after_rule_edit'; end if;
  select id into oid from public.ecommerce_orders where idempotency_key_hash=repeat('d',64); select id into actor from public.users where tenant_id=971;
  perform public.transition_ecommerce_order_status_safe(971,oid,'confirmed',actor,'',repeat('a',64));
  perform public.transition_ecommerce_order_status_safe(971,oid,'preparing',actor,'',repeat('b',64));
  perform public.transition_ecommerce_order_status_safe(971,oid,'out_for_delivery',actor,'',repeat('c',64));
  perform public.transition_ecommerce_order_status_safe(971,oid,'delivered',actor,'',repeat('d',64));
  perform public.collect_ecommerce_cod_payment_safe(971,oid,actor);
  if (select current_balance from public.ecommerce_loyalty_accounts where tenant_id=971)<>10 then raise exception 'multiple_thresholds_should_unlock_only_one'; end if;
  if (select count(*) from public.ecommerce_loyalty_entitlements where tenant_id=971 and status='active' and rule_version=2)<>1 then raise exception 'new_rule_entitlement_missing'; end if;
  select current_balance into balance_before from public.ecommerce_loyalty_accounts where tenant_id=971;
  update public.ecommerce_loyalty_entitlements set expires_at=now()-interval '1 second' where tenant_id=971 and status='active';
  perform public.expire_ecommerce_loyalty_entitlements_safe(971,(select id from public.users where tenant_id=972));
  if exists(select 1 from public.ecommerce_loyalty_entitlements where tenant_id=971 and status='active') then raise exception 'entitlement_not_expired'; end if;
  if (select current_balance from public.ecommerce_loyalty_accounts where tenant_id=971)<>balance_before then raise exception 'expiry_restored_points'; end if;
end $$;

do $$ begin
  begin update public.ecommerce_loyalty_transactions set metadata='{}' where tenant_id=971; raise exception 'ledger_update_allowed'; exception when sqlstate 'P0001' then if sqlerrm<>'ecommerce_loyalty_ledger_append_only' then raise; end if; end;
  if (select sum(points_delta) from public.ecommerce_loyalty_transactions where tenant_id=971)<>(select current_balance from public.ecommerce_loyalty_accounts where tenant_id=971) then raise exception 'ledger_projection_mismatch'; end if;
end $$;
SQL

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
select public.create_ecommerce_order_safe('{"tenant_id":971,"customer_name":"Concurrent","email":"customer-972@example.invalid","phone":"059","street":"Main Street","service_area_id":"95000000-0000-0000-0000-000000000001","payment_method":"cash_on_delivery","items":[{"product_id":"97100000-0000-0000-0000-000000000001","quantity":1}]}',repeat('0',64),repeat('1',64),repeat('2',64),(select id from public.users where tenant_id=972));
do $$ declare oid uuid; actor integer; begin
  select id into oid from public.ecommerce_orders where idempotency_key_hash=repeat('0',64); select id into actor from public.users where tenant_id=971;
  perform public.transition_ecommerce_order_status_safe(971,oid,'confirmed',actor,'',repeat('e',64));
  perform public.transition_ecommerce_order_status_safe(971,oid,'preparing',actor,'',repeat('f',64));
  perform public.transition_ecommerce_order_status_safe(971,oid,'out_for_delivery',actor,'',repeat('0',64));
end $$;
