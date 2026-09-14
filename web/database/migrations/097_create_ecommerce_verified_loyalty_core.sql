begin;

alter table public.ecommerce_orders add column customer_id integer references public.users(id) on delete set null;
alter table public.ecommerce_order_items add column loyalty_entitlement_id uuid;

create table public.ecommerce_loyalty_accounts (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  customer_id integer not null references public.users(id) on delete restrict,
  current_balance bigint not null default 0 check (current_balance >= 0),
  lifetime_earned bigint not null default 0 check (lifetime_earned >= 0),
  lifetime_spent bigint not null default 0 check (lifetime_spent >= 0),
  version bigint not null default 0 check (version >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, customer_id),
  unique (tenant_id, id)
);

create table public.ecommerce_loyalty_rules (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  rule_key uuid not null,
  version integer not null check (version > 0),
  enabled boolean not null default false,
  is_current boolean not null default true,
  currency text not null check (currency ~ '^[A-Z]{3}$'),
  earning_rate_basis_points integer not null default 500 check (earning_rate_basis_points between 1 and 10000),
  threshold_points bigint not null check (threshold_points > 0),
  reward_product_id uuid not null,
  reward_discount_basis_points integer not null default 1000 check (reward_discount_basis_points = 1000),
  validity_mode text not null check (validity_mode in ('fixed_period','lifetime')),
  validity_days integer check (
    (validity_mode='fixed_period' and validity_days between 1 and 3650)
    or (validity_mode='lifetime' and validity_days is null)
  ),
  created_by integer references public.users(id) on delete set null,
  created_at timestamptz not null default now(),
  unique (tenant_id, id),
  unique (tenant_id, rule_key, version),
  constraint ecommerce_loyalty_rules_product_fk foreign key (tenant_id,reward_product_id)
    references public.ecommerce_products(tenant_id,id) on delete restrict
);
create unique index ecommerce_loyalty_rules_current_idx on public.ecommerce_loyalty_rules(tenant_id)
  where is_current;

create table public.ecommerce_loyalty_entitlements (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  account_id uuid not null,
  customer_id integer not null references public.users(id) on delete restrict,
  rule_id uuid not null,
  rule_key uuid not null,
  rule_version integer not null,
  reward_product_id uuid not null,
  threshold_points bigint not null check (threshold_points > 0),
  reward_discount_basis_points integer not null check (reward_discount_basis_points = 1000),
  validity_mode text not null check (validity_mode in ('fixed_period','lifetime')),
  validity_days integer,
  status text not null default 'active' check (status in ('active','expired','revoked')),
  granted_at timestamptz not null default now(),
  expires_at timestamptz,
  revoked_at timestamptz,
  revoked_by integer references public.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id,id),
  constraint ecommerce_loyalty_entitlements_account_fk foreign key (tenant_id,account_id)
    references public.ecommerce_loyalty_accounts(tenant_id,id) on delete restrict,
  constraint ecommerce_loyalty_entitlements_rule_fk foreign key (tenant_id,rule_id)
    references public.ecommerce_loyalty_rules(tenant_id,id) on delete restrict,
  constraint ecommerce_loyalty_entitlements_product_fk foreign key (tenant_id,reward_product_id)
    references public.ecommerce_products(tenant_id,id) on delete restrict,
  constraint ecommerce_loyalty_entitlements_validity_check check (
    (validity_mode='fixed_period' and validity_days between 1 and 3650 and expires_at is not null)
    or (validity_mode='lifetime' and validity_days is null and expires_at is null)
  ),
  constraint ecommerce_loyalty_entitlements_revocation_check check (
    (status='revoked' and revoked_at is not null) or (status<>'revoked' and revoked_at is null)
  )
);
create unique index ecommerce_loyalty_entitlements_active_reward_idx
  on public.ecommerce_loyalty_entitlements(tenant_id,customer_id,rule_key,reward_product_id)
  where status='active';
create index ecommerce_loyalty_entitlements_customer_idx
  on public.ecommerce_loyalty_entitlements(tenant_id,customer_id,created_at desc);

create table public.ecommerce_loyalty_transactions (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  account_id uuid not null,
  customer_id integer not null references public.users(id) on delete restrict,
  transaction_type text not null check (transaction_type in ('earn','reward_unlock','reward_unlock_reversal')),
  points_delta bigint not null check (points_delta <> 0),
  balance_after bigint not null check (balance_after >= 0),
  order_id uuid,
  rule_id uuid,
  rule_version integer,
  entitlement_id uuid,
  idempotency_key text not null check (length(idempotency_key) between 16 and 300),
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata)='object'),
  created_at timestamptz not null default now(),
  constraint ecommerce_loyalty_transactions_account_fk foreign key (tenant_id,account_id)
    references public.ecommerce_loyalty_accounts(tenant_id,id) on delete restrict,
  constraint ecommerce_loyalty_transactions_order_fk foreign key (tenant_id,order_id)
    references public.ecommerce_orders(tenant_id,id) on delete restrict,
  constraint ecommerce_loyalty_transactions_rule_fk foreign key (tenant_id,rule_id)
    references public.ecommerce_loyalty_rules(tenant_id,id) on delete restrict,
  constraint ecommerce_loyalty_transactions_entitlement_fk foreign key (tenant_id,entitlement_id)
    references public.ecommerce_loyalty_entitlements(tenant_id,id) on delete restrict,
  unique (tenant_id,idempotency_key)
);
create index ecommerce_loyalty_transactions_account_idx
  on public.ecommerce_loyalty_transactions(tenant_id,account_id,created_at desc);

alter table public.ecommerce_order_items add constraint ecommerce_order_items_loyalty_entitlement_fk
  foreign key (tenant_id,loyalty_entitlement_id)
  references public.ecommerce_loyalty_entitlements(tenant_id,id) on delete restrict;

alter table public.ecommerce_loyalty_accounts enable row level security;
alter table public.ecommerce_loyalty_rules enable row level security;
alter table public.ecommerce_loyalty_entitlements enable row level security;
alter table public.ecommerce_loyalty_transactions enable row level security;

create or replace function public.reject_ecommerce_loyalty_ledger_mutation()
returns trigger language plpgsql as $$ begin
  raise exception using errcode='P0001',message='ecommerce_loyalty_ledger_append_only';
end $$;
create trigger ecommerce_loyalty_transactions_append_only
before update or delete on public.ecommerce_loyalty_transactions
for each row execute function public.reject_ecommerce_loyalty_ledger_mutation();

create or replace function public.save_ecommerce_loyalty_rule_safe(
  p_tenant_id integer,p_actor_id integer,p_enabled boolean,p_earning_rate_basis_points integer,
  p_threshold_points bigint,p_reward_product_id uuid,p_validity_mode text,p_validity_days integer
) returns jsonb language plpgsql security definer set search_path=public as $$
declare v_currency text; v_current public.ecommerce_loyalty_rules; v_rule public.ecommerce_loyalty_rules;
begin
  if p_actor_id is null or not exists(select 1 from public.users where id=p_actor_id and tenant_id=p_tenant_id) then raise exception using errcode='P0001',message='ecommerce_loyalty_actor_invalid'; end if;
  if p_earning_rate_basis_points not between 1 and 10000 or p_threshold_points<1 or p_validity_mode not in ('fixed_period','lifetime') or (p_validity_mode='fixed_period' and p_validity_days not between 1 and 3650) or (p_validity_mode='lifetime' and p_validity_days is not null) then raise exception using errcode='P0001',message='ecommerce_loyalty_rule_invalid'; end if;
  select ecommerce_currency into v_currency from public.website_settings where tenant_id=p_tenant_id;
  if v_currency is null then raise exception using errcode='P0001',message='ecommerce_currency_configuration_required'; end if;
  if not exists(select 1 from public.ecommerce_products where tenant_id=p_tenant_id and id=p_reward_product_id and status in ('active','inactive')) then raise exception using errcode='P0001',message='ecommerce_loyalty_reward_product_invalid'; end if;
  perform pg_advisory_xact_lock(hashtextextended('ecommerce-loyalty-rule:'||p_tenant_id,0));
  select * into v_current from public.ecommerce_loyalty_rules where tenant_id=p_tenant_id and is_current for update;
  if found then update public.ecommerce_loyalty_rules set is_current=false where id=v_current.id; end if;
  insert into public.ecommerce_loyalty_rules(tenant_id,rule_key,version,enabled,is_current,currency,earning_rate_basis_points,threshold_points,reward_product_id,reward_discount_basis_points,validity_mode,validity_days,created_by)
  values(p_tenant_id,coalesce(v_current.rule_key,gen_random_uuid()),coalesce(v_current.version,0)+1,p_enabled,true,v_currency,p_earning_rate_basis_points,p_threshold_points,p_reward_product_id,1000,p_validity_mode,case when p_validity_mode='lifetime' then null else p_validity_days end,p_actor_id)
  returning * into v_rule;
  return to_jsonb(v_rule);
end $$;

create or replace function public.expire_ecommerce_loyalty_entitlements_safe(p_tenant_id integer,p_customer_id integer)
returns integer language plpgsql security definer set search_path=public as $$
declare v_count integer;
begin
  update public.ecommerce_loyalty_entitlements set status='expired',updated_at=now()
  where tenant_id=p_tenant_id and customer_id=p_customer_id and status='active' and expires_at<=now();
  get diagnostics v_count=row_count; return v_count;
end $$;

create or replace function public.process_ecommerce_loyalty_order_safe(p_tenant_id integer,p_order_id uuid)
returns jsonb language plpgsql security definer set search_path=public as $$
declare v_order public.ecommerce_orders; v_rule public.ecommerce_loyalty_rules; v_account public.ecommerce_loyalty_accounts; v_entitlement public.ecommerce_loyalty_entitlements; v_points bigint; v_balance bigint; v_key text;
begin
  select * into v_order from public.ecommerce_orders where tenant_id=p_tenant_id and id=p_order_id for update;
  if not found then raise exception using errcode='P0002',message='ecommerce_order_not_found'; end if;
  if v_order.status<>'delivered' or v_order.payment_status not in ('collected','paid') or v_order.customer_id is null then return jsonb_build_object('awarded',false,'reason','not_eligible'); end if;
  if not exists(select 1 from public.users where id=v_order.customer_id and auth_id is not null and email_verified=true) then return jsonb_build_object('awarded',false,'reason','customer_not_verified'); end if;
  select * into v_rule from public.ecommerce_loyalty_rules where tenant_id=p_tenant_id and is_current and enabled for share;
  if not found then return jsonb_build_object('awarded',false,'reason','rule_disabled'); end if;
  v_key:=concat_ws(':','earn',p_tenant_id,p_order_id,v_rule.version);
  if exists(select 1 from public.ecommerce_loyalty_transactions where tenant_id=p_tenant_id and idempotency_key=v_key) then return jsonb_build_object('awarded',false,'duplicate',true); end if;
  v_points:=floor((v_order.total::numeric*v_rule.earning_rate_basis_points::numeric)/10000)::bigint;
  if v_points<1 then return jsonb_build_object('awarded',false,'reason','zero_points'); end if;
  insert into public.ecommerce_loyalty_accounts(tenant_id,customer_id) values(p_tenant_id,v_order.customer_id)
  on conflict(tenant_id,customer_id) do nothing;
  select * into v_account from public.ecommerce_loyalty_accounts where tenant_id=p_tenant_id and customer_id=v_order.customer_id for update;
  v_balance:=v_account.current_balance+v_points;
  update public.ecommerce_loyalty_accounts set current_balance=v_balance,lifetime_earned=lifetime_earned+v_points,version=version+1,updated_at=now() where id=v_account.id;
  insert into public.ecommerce_loyalty_transactions(tenant_id,account_id,customer_id,transaction_type,points_delta,balance_after,order_id,rule_id,rule_version,idempotency_key,metadata)
  values(p_tenant_id,v_account.id,v_order.customer_id,'earn',v_points,v_balance,p_order_id,v_rule.id,v_rule.version,v_key,jsonb_build_object('eligible_amount',v_order.total,'earning_rate_basis_points',v_rule.earning_rate_basis_points));
  perform public.expire_ecommerce_loyalty_entitlements_safe(p_tenant_id,v_order.customer_id);
  if v_balance>=v_rule.threshold_points and not exists(select 1 from public.ecommerce_loyalty_entitlements where tenant_id=p_tenant_id and customer_id=v_order.customer_id and rule_key=v_rule.rule_key and reward_product_id=v_rule.reward_product_id and status='active') then
    insert into public.ecommerce_loyalty_entitlements(tenant_id,account_id,customer_id,rule_id,rule_key,rule_version,reward_product_id,threshold_points,reward_discount_basis_points,validity_mode,validity_days,expires_at)
    values(p_tenant_id,v_account.id,v_order.customer_id,v_rule.id,v_rule.rule_key,v_rule.version,v_rule.reward_product_id,v_rule.threshold_points,v_rule.reward_discount_basis_points,v_rule.validity_mode,v_rule.validity_days,case when v_rule.validity_mode='fixed_period' then now()+make_interval(days=>v_rule.validity_days) else null end)
    returning * into v_entitlement;
    v_balance:=v_balance-v_rule.threshold_points;
    update public.ecommerce_loyalty_accounts set current_balance=v_balance,lifetime_spent=lifetime_spent+v_rule.threshold_points,version=version+1,updated_at=now() where id=v_account.id;
    insert into public.ecommerce_loyalty_transactions(tenant_id,account_id,customer_id,transaction_type,points_delta,balance_after,order_id,rule_id,rule_version,entitlement_id,idempotency_key,metadata)
    values(p_tenant_id,v_account.id,v_order.customer_id,'reward_unlock',-v_rule.threshold_points,v_balance,p_order_id,v_rule.id,v_rule.version,v_entitlement.id,concat_ws(':','unlock',p_tenant_id,v_entitlement.id),jsonb_build_object('reward_product_id',v_rule.reward_product_id,'discount_basis_points',v_rule.reward_discount_basis_points));
  end if;
  return jsonb_build_object('awarded',true,'points',v_points,'balance',v_balance,'entitlement_id',v_entitlement.id);
end $$;

create or replace function public.revoke_ecommerce_loyalty_entitlement_safe(p_tenant_id integer,p_entitlement_id uuid,p_actor_id integer)
returns jsonb language plpgsql security definer set search_path=public as $$
declare v_entitlement public.ecommerce_loyalty_entitlements; v_account public.ecommerce_loyalty_accounts; v_key text; v_balance bigint;
begin
  if p_actor_id is null or not exists(select 1 from public.users where id=p_actor_id and tenant_id=p_tenant_id) then raise exception using errcode='P0001',message='ecommerce_loyalty_actor_invalid'; end if;
  select * into v_entitlement from public.ecommerce_loyalty_entitlements where tenant_id=p_tenant_id and id=p_entitlement_id for update;
  if not found then raise exception using errcode='P0002',message='ecommerce_loyalty_entitlement_not_found'; end if;
  if v_entitlement.status='revoked' then return jsonb_build_object('duplicate',true,'entitlement',to_jsonb(v_entitlement)); end if;
  if v_entitlement.status<>'active' then raise exception using errcode='P0001',message='ecommerce_loyalty_entitlement_not_active'; end if;
  select * into v_account from public.ecommerce_loyalty_accounts where tenant_id=p_tenant_id and id=v_entitlement.account_id for update;
  v_key:=concat_ws(':','revoke-restore',p_tenant_id,p_entitlement_id); v_balance:=v_account.current_balance+v_entitlement.threshold_points;
  update public.ecommerce_loyalty_entitlements set status='revoked',revoked_at=now(),revoked_by=p_actor_id,updated_at=now() where id=p_entitlement_id returning * into v_entitlement;
  update public.ecommerce_loyalty_accounts set current_balance=v_balance,lifetime_spent=greatest(0,lifetime_spent-v_entitlement.threshold_points),version=version+1,updated_at=now() where id=v_account.id;
  insert into public.ecommerce_loyalty_transactions(tenant_id,account_id,customer_id,transaction_type,points_delta,balance_after,rule_id,rule_version,entitlement_id,idempotency_key,metadata)
  values(p_tenant_id,v_account.id,v_entitlement.customer_id,'reward_unlock_reversal',v_entitlement.threshold_points,v_balance,v_entitlement.rule_id,v_entitlement.rule_version,v_entitlement.id,v_key,jsonb_build_object('revoked_by',p_actor_id));
  return jsonb_build_object('duplicate',false,'entitlement',to_jsonb(v_entitlement),'balance',v_balance);
end $$;

create or replace function public.create_ecommerce_order_safe(p_order jsonb,p_idempotency_key_hash text,p_request_hash text,p_confirmation_token_hash text,p_customer_id integer)
returns jsonb language plpgsql security definer set search_path=public as $$
declare v_tenant_id integer; v_currency text; v_existing public.ecommerce_orders; v_order public.ecommerce_orders; v_area record; v_requested record; v_product public.ecommerce_products; v_variant public.ecommerce_product_variants; v_order_item public.ecommerce_order_items; v_entitlement public.ecommerce_loyalty_entitlements; v_count integer; v_subtotal numeric(14,2):=0; v_discount_total numeric(14,2):=0; v_price numeric(14,2); v_unit_discount numeric(14,2); v_final_unit numeric(14,2); v_total numeric(14,2); v_allocated integer; v_has_options boolean; v_options jsonb;
begin
  if jsonb_typeof(p_order)<>'object' or jsonb_typeof(p_order->'items')<>'array' then raise exception using errcode='P0001',message='ecommerce_order_payload_invalid'; end if;
  if p_idempotency_key_hash is null or p_idempotency_key_hash!~'^[0-9a-f]{64}$' or p_request_hash is null or p_request_hash!~'^[0-9a-f]{64}$' or p_confirmation_token_hash is null or p_confirmation_token_hash!~'^[0-9a-f]{64}$' then raise exception using errcode='P0001',message='idempotency_key_invalid'; end if;
  v_tenant_id:=nullif(p_order->>'tenant_id','')::integer;
  if v_tenant_id is null or coalesce(p_order->>'payment_method','')<>'cash_on_delivery' then raise exception using errcode='P0001',message='ecommerce_order_payload_invalid'; end if;
  if p_customer_id is not null and not exists(select 1 from public.users where id=p_customer_id and auth_id is not null and email_verified=true) then raise exception using errcode='P0001',message='ecommerce_loyalty_customer_unverified'; end if;
  if length(trim(coalesce(p_order->>'street','')))<3 then raise exception using errcode='P0001',message='ecommerce_delivery_street_required'; end if;
  v_count:=jsonb_array_length(p_order->'items'); if v_count<1 or v_count>50 then raise exception using errcode='P0001',message='ecommerce_order_items_invalid'; end if;
  if (select count(*) from (select item->>'product_id',coalesce(item->>'variant_id','') from jsonb_array_elements(p_order->'items') item group by 1,2)q)<>v_count then raise exception using errcode='P0001',message='ecommerce_order_items_duplicate'; end if;
  perform pg_advisory_xact_lock(hashtextextended(concat_ws(':','ecommerce-order',v_tenant_id,p_idempotency_key_hash),0));
  select * into v_existing from public.ecommerce_orders where tenant_id=v_tenant_id and idempotency_key_hash=p_idempotency_key_hash for update;
  if found then if v_existing.request_hash is distinct from p_request_hash then raise exception using errcode='P0001',message='idempotency_conflict'; end if; return jsonb_build_object('duplicate',true,'order',to_jsonb(v_existing)); end if;
  select area.* into v_area from public.ecommerce_service_areas area join public.ecommerce_tenant_service_areas mapping on mapping.service_area_id=area.id and mapping.tenant_id=v_tenant_id and mapping.enabled where area.id=nullif(p_order->>'service_area_id','')::uuid and area.active for share of area,mapping;
  if not found then raise exception using errcode='P0001',message='ecommerce_delivery_area_unavailable'; end if;
  select ecommerce_currency into v_currency from public.website_settings where tenant_id=v_tenant_id; if v_currency is null then raise exception using errcode='P0001',message='ecommerce_currency_configuration_required'; end if;
  if p_customer_id is not null then
    perform public.expire_ecommerce_loyalty_entitlements_safe(v_tenant_id,p_customer_id);
    select * into v_entitlement from public.ecommerce_loyalty_entitlements where tenant_id=v_tenant_id and customer_id=p_customer_id and status='active' and (expires_at is null or expires_at>now()) and reward_product_id in (select (item->>'product_id')::uuid from jsonb_array_elements(p_order->'items') item) order by granted_at,id limit 1 for update;
  end if;
  insert into public.ecommerce_orders(tenant_id,customer_id,order_number,status,payment_status,payment_method,currency,subtotal,discount_total,total,customer_name,customer_email,customer_phone,address_line_1,address_line_2,city,postal_code,country,notes,service_area_id,service_area_code,service_area_name_en,service_area_name_ar,street,building,floor_apartment,address_description,delivery_notes,confirmation_token_hash,confirmation_created_at,idempotency_key_hash,request_hash)
  values(v_tenant_id,p_customer_id,'MD-'||to_char(timezone('UTC',now()),'YYYYMMDD')||'-'||upper(substr(replace(gen_random_uuid()::text,'-',''),1,8)),'pending','unpaid','cash_on_delivery',v_currency,0,0,0,trim(coalesce(p_order->>'customer_name','')),lower(trim(coalesce(p_order->>'email',''))),trim(coalesce(p_order->>'phone','')),trim(p_order->>'street'),concat_ws(', ',nullif(trim(coalesce(p_order->>'building','')),''),nullif(trim(coalesce(p_order->>'floor_apartment','')),'')),v_area.name_en,'',trim(coalesce(p_order->>'country','')),trim(coalesce(p_order->>'delivery_notes','')),v_area.id,v_area.code,v_area.name_en,v_area.name_ar,trim(p_order->>'street'),trim(coalesce(p_order->>'building','')),trim(coalesce(p_order->>'floor_apartment','')),trim(coalesce(p_order->>'address_description','')),trim(coalesce(p_order->>'delivery_notes','')),p_confirmation_token_hash,now(),p_idempotency_key_hash,p_request_hash) returning * into v_order;
  for v_requested in select * from jsonb_to_recordset(p_order->'items') as r(product_id uuid,variant_id uuid,quantity integer) order by product_id,variant_id nulls first loop
    if v_requested.quantity is null or v_requested.quantity<1 or v_requested.quantity>99 then raise exception using errcode='P0001',message='ecommerce_quantity_invalid'; end if;
    select * into v_product from public.ecommerce_products where tenant_id=v_tenant_id and id=v_requested.product_id and status='active' for update; if not found then raise exception using errcode='P0001',message='ecommerce_product_unavailable'; end if;
    if v_product.currency<>v_currency then raise exception using errcode='P0001',message='ecommerce_currency_product_mismatch'; end if;
    select exists(select 1 from public.ecommerce_product_options where tenant_id=v_tenant_id and product_id=v_product.id) into v_has_options; v_options:='{}'::jsonb;
    if v_has_options then
      if v_requested.variant_id is null then raise exception using errcode='P0001',message='ecommerce_variant_required'; end if;
      select * into v_variant from public.ecommerce_product_variants where tenant_id=v_tenant_id and product_id=v_product.id and id=v_requested.variant_id and active for update; if not found then raise exception using errcode='P0001',message='ecommerce_variant_unavailable'; end if;
      if exists(select 1 from public.ecommerce_product_options o where o.tenant_id=v_tenant_id and o.product_id=v_product.id and o.required and not exists(select 1 from public.ecommerce_variant_option_values l where l.variant_id=v_variant.id and l.option_id=o.id)) then raise exception using errcode='P0001',message='ecommerce_variant_incomplete'; end if;
      select jsonb_build_object('items',coalesce(jsonb_agg(jsonb_build_object('option_code',o.code,'option_name_translations',o.name_translations,'value_code',ov.code,'value_translations',ov.value_translations) order by o.sort_order,ov.sort_order),'[]'::jsonb)) into v_options from public.ecommerce_variant_option_values l join public.ecommerce_product_options o on o.id=l.option_id join public.ecommerce_product_option_values ov on ov.id=l.option_value_id where l.tenant_id=v_tenant_id and l.variant_id=v_variant.id;
      v_price:=coalesce(v_variant.price_override,v_product.price); if v_variant.track_inventory and not v_variant.allow_backorder and v_requested.quantity>v_variant.inventory_quantity then raise exception using errcode='P0001',message='ecommerce_inventory_insufficient'; end if; v_allocated:=case when v_variant.track_inventory then least(v_requested.quantity,v_variant.inventory_quantity) else 0 end;
    else
      if v_requested.variant_id is not null then raise exception using errcode='P0001',message='ecommerce_variant_not_allowed'; end if; v_price:=v_product.price; if v_product.track_inventory and not v_product.allow_backorder and v_requested.quantity>v_product.inventory_quantity then raise exception using errcode='P0001',message='ecommerce_inventory_insufficient'; end if; v_allocated:=case when v_product.track_inventory then least(v_requested.quantity,v_product.inventory_quantity) else 0 end;
    end if;
    v_unit_discount:=case when v_entitlement.id is not null and v_entitlement.reward_product_id=v_product.id then round(v_price*v_entitlement.reward_discount_basis_points/10000.0,2) else 0 end; v_final_unit:=v_price-v_unit_discount; v_total:=(v_final_unit*v_requested.quantity)::numeric(14,2); v_subtotal:=v_subtotal+(v_price*v_requested.quantity)::numeric(14,2); v_discount_total:=v_discount_total+(v_unit_discount*v_requested.quantity)::numeric(14,2);
    insert into public.ecommerce_order_items(tenant_id,order_id,product_id,variant_id,sku,product_name,product_slug,product_snapshot,variant_snapshot,selected_options_snapshot,quantity,list_unit_price,discount_amount,discount_source,loyalty_entitlement_id,unit_price,line_total,inventory_allocated_quantity)
    values(v_tenant_id,v_order.id,v_product.id,v_requested.variant_id,case when v_has_options then v_variant.sku else v_product.sku end,coalesce(nullif(v_product.translations->'en'->>'name',''),v_product.slug),v_product.slug,jsonb_build_object('slug',v_product.slug,'translations',v_product.translations,'brand',v_product.brand,'images',v_product.images),case when v_has_options then jsonb_build_object('id',v_variant.id,'sku',v_variant.sku,'barcode',v_variant.barcode,'images',v_variant.images,'price_override',v_variant.price_override,'compare_at_price_override',v_variant.compare_at_price_override) else '{}'::jsonb end,v_options,v_requested.quantity,v_price,v_unit_discount*v_requested.quantity,case when v_unit_discount>0 then 'loyalty' else null end,case when v_unit_discount>0 then v_entitlement.id else null end,v_final_unit,v_total,v_allocated) returning * into v_order_item;
    if v_allocated>0 then if v_has_options then update public.ecommerce_product_variants set inventory_quantity=inventory_quantity-v_allocated where tenant_id=v_tenant_id and id=v_variant.id; else update public.ecommerce_products set inventory_quantity=inventory_quantity-v_allocated where tenant_id=v_tenant_id and id=v_product.id; end if; insert into public.ecommerce_inventory_movements(tenant_id,product_id,variant_id,order_id,order_item_id,movement_type,quantity_delta,idempotency_key_hash,reason) values(v_tenant_id,v_product.id,v_requested.variant_id,v_order.id,v_order_item.id,'order_allocation',-v_allocated,encode(extensions.digest('allocate:'||v_order_item.id::text,'sha256'),'hex'),'order_created'); end if;
  end loop;
  update public.ecommerce_orders set subtotal=v_subtotal,discount_total=v_discount_total,total=v_subtotal-v_discount_total where id=v_order.id and tenant_id=v_tenant_id returning * into v_order;
  insert into public.ecommerce_order_status_history(tenant_id,order_id,previous_status,new_status,actor_id,note,idempotency_key_hash) values(v_tenant_id,v_order.id,null,'pending',null,'Order created',encode(extensions.digest('initial-status:'||v_order.id::text,'sha256'),'hex'));
  return jsonb_build_object('duplicate',false,'order',to_jsonb(v_order));
end $$;

create or replace function public.create_ecommerce_order_safe(p_order jsonb,p_idempotency_key_hash text,p_request_hash text,p_confirmation_token_hash text)
returns jsonb language plpgsql security definer set search_path=public as $$ begin
  return public.create_ecommerce_order_safe(p_order,p_idempotency_key_hash,p_request_hash,p_confirmation_token_hash,null);
end $$;

create or replace function public.transition_ecommerce_order_status_safe(p_tenant_id integer,p_order_id uuid,p_new_status text,p_actor_id integer,p_note text,p_idempotency_key_hash text)
returns jsonb language plpgsql security definer set search_path=public as $$
declare v_order public.ecommerce_orders; v_previous text; v_history public.ecommerce_order_status_history;
begin
  if p_idempotency_key_hash is null or p_idempotency_key_hash!~'^[0-9a-f]{64}$' then raise exception using errcode='P0001',message='idempotency_key_invalid'; end if;
  perform pg_advisory_xact_lock(hashtextextended(concat_ws(':','ecommerce-order-status',p_tenant_id,p_order_id),0));
  select * into v_history from public.ecommerce_order_status_history where tenant_id=p_tenant_id and order_id=p_order_id and idempotency_key_hash=p_idempotency_key_hash;
  if found then if v_history.new_status<>p_new_status then raise exception using errcode='P0001',message='idempotency_conflict'; end if; select * into v_order from public.ecommerce_orders where tenant_id=p_tenant_id and id=p_order_id; return jsonb_build_object('duplicate',true,'order',to_jsonb(v_order)); end if;
  select * into v_order from public.ecommerce_orders where tenant_id=p_tenant_id and id=p_order_id for update; if not found then raise exception using errcode='P0002',message='ecommerce_order_not_found'; end if;
  if p_actor_id is null or not exists(select 1 from public.users where id=p_actor_id and tenant_id=p_tenant_id) then raise exception using errcode='P0001',message='ecommerce_order_actor_invalid'; end if;
  if v_order.status=p_new_status then perform public.process_ecommerce_loyalty_order_safe(p_tenant_id,p_order_id); return jsonb_build_object('duplicate',true,'order',to_jsonb(v_order)); end if;
  if not ((v_order.status='pending' and p_new_status in ('confirmed','cancelled','rejected')) or (v_order.status='confirmed' and p_new_status in ('preparing','cancelled','rejected')) or (v_order.status='preparing' and p_new_status in ('out_for_delivery','cancelled')) or (v_order.status='out_for_delivery' and p_new_status='delivered')) then raise exception using errcode='P0001',message='ecommerce_order_transition_invalid'; end if;
  v_previous:=v_order.status; if p_new_status in ('cancelled','rejected') then perform public.restore_ecommerce_order_inventory_safe(p_tenant_id,p_order_id,p_new_status,p_idempotency_key_hash); else update public.ecommerce_orders set status=p_new_status,status_reason=trim(coalesce(p_note,'')),updated_at=now() where tenant_id=p_tenant_id and id=p_order_id returning * into v_order; end if;
  insert into public.ecommerce_order_status_history(tenant_id,order_id,previous_status,new_status,actor_id,note,idempotency_key_hash) values(p_tenant_id,p_order_id,v_previous,p_new_status,p_actor_id,nullif(trim(coalesce(p_note,'')),''),p_idempotency_key_hash);
  perform public.process_ecommerce_loyalty_order_safe(p_tenant_id,p_order_id); select * into v_order from public.ecommerce_orders where tenant_id=p_tenant_id and id=p_order_id;
  return jsonb_build_object('duplicate',false,'order',to_jsonb(v_order));
end $$;

create or replace function public.collect_ecommerce_cod_payment_safe(p_tenant_id integer,p_order_id uuid,p_actor_id integer)
returns jsonb language plpgsql security definer set search_path=public as $$
declare v_order public.ecommerce_orders;
begin
  perform pg_advisory_xact_lock(hashtextextended(concat_ws(':','ecommerce-cod',p_tenant_id,p_order_id),0)); select * into v_order from public.ecommerce_orders where tenant_id=p_tenant_id and id=p_order_id for update;
  if not found then raise exception using errcode='P0002',message='ecommerce_order_not_found'; end if; if p_actor_id is null or not exists(select 1 from public.users where id=p_actor_id and tenant_id=p_tenant_id) then raise exception using errcode='P0001',message='ecommerce_order_actor_invalid'; end if; if v_order.payment_method<>'cash_on_delivery' then raise exception using errcode='P0001',message='ecommerce_cod_required'; end if;
  if v_order.payment_status in ('collected','paid') then perform public.process_ecommerce_loyalty_order_safe(p_tenant_id,p_order_id); return jsonb_build_object('duplicate',true,'order',to_jsonb(v_order)); end if;
  if v_order.payment_status<>'unpaid' then raise exception using errcode='P0001',message='ecommerce_payment_transition_invalid'; end if;
  update public.ecommerce_orders set payment_status='collected',payment_collected_at=now(),payment_collected_by=p_actor_id,updated_at=now() where tenant_id=p_tenant_id and id=p_order_id returning * into v_order;
  perform public.process_ecommerce_loyalty_order_safe(p_tenant_id,p_order_id); return jsonb_build_object('duplicate',false,'order',to_jsonb(v_order));
end $$;

revoke all on function public.save_ecommerce_loyalty_rule_safe(integer,integer,boolean,integer,bigint,uuid,text,integer) from public,anon,authenticated;
revoke all on function public.expire_ecommerce_loyalty_entitlements_safe(integer,integer) from public,anon,authenticated;
revoke all on function public.process_ecommerce_loyalty_order_safe(integer,uuid) from public,anon,authenticated;
revoke all on function public.revoke_ecommerce_loyalty_entitlement_safe(integer,uuid,integer) from public,anon,authenticated;
revoke all on function public.create_ecommerce_order_safe(jsonb,text,text,text,integer) from public,anon,authenticated;
grant execute on function public.save_ecommerce_loyalty_rule_safe(integer,integer,boolean,integer,bigint,uuid,text,integer) to service_role;
grant execute on function public.expire_ecommerce_loyalty_entitlements_safe(integer,integer) to service_role;
grant execute on function public.process_ecommerce_loyalty_order_safe(integer,uuid) to service_role;
grant execute on function public.revoke_ecommerce_loyalty_entitlement_safe(integer,uuid,integer) to service_role;
grant execute on function public.create_ecommerce_order_safe(jsonb,text,text,text,integer) to service_role;

do $$ declare v_schema_version public.application_schema_state.schema_version%TYPE; begin
  select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
  if v_schema_version is null then raise exception using errcode='P0001',message='migration_097_schema_state_missing'; end if;
  if v_schema_version <> 96 then raise exception using errcode='P0001',message=format('migration_097_expected_schema_96_got_%s',v_schema_version); end if;
  update public.application_schema_state set schema_version = 97, applied_at=now() where contract_key = 'core';
end $$;

notify pgrst,'reload schema';
commit;
