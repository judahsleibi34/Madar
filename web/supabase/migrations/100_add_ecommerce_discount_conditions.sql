begin;

-- Preserve legacy scalar fields and immutable historical rewards. Conditions
-- extend rule and entitlement snapshots; one bundle still costs one threshold.
alter table public.ecommerce_loyalty_rules
  add column discount_conditions jsonb not null default '[]'::jsonb
    check (jsonb_typeof(discount_conditions)='array' and jsonb_array_length(discount_conditions)<=10);
alter table public.ecommerce_loyalty_entitlements
  add column reward_conditions jsonb not null default '[]'::jsonb
    check (jsonb_typeof(reward_conditions)='array' and jsonb_array_length(reward_conditions)<=10);

create or replace function public.save_ecommerce_loyalty_rule_v2_safe(
  p_tenant_id integer,p_actor_id integer,p_enabled boolean,
  p_earning_rate_basis_points integer,p_threshold_points bigint,p_conditions jsonb
) returns jsonb language plpgsql security definer set search_path=public as $$
declare v_condition jsonb; v_product text; v_primary jsonb; v_rule jsonb;
begin
  if p_conditions is null or jsonb_typeof(p_conditions)<>'array' then
    raise exception using errcode='P0001',message='ecommerce_loyalty_rule_invalid';
  end if;
  if jsonb_array_length(p_conditions) not between 1 and 10 then
    raise exception using errcode='P0001',message='ecommerce_loyalty_rule_invalid';
  end if;
  for v_condition in select * from jsonb_array_elements(p_conditions) loop
    if jsonb_typeof(v_condition)<>'object'
       or coalesce(v_condition->>'audience','') not in ('normal','loyalty')
       or coalesce(v_condition->>'discount_basis_points','') !~ '^[0-9]+$'
       or (v_condition->>'discount_basis_points')::integer not between 1 and 10000
       or coalesce(v_condition->>'validity_mode','') not in ('lifetime','fixed_period')
       or (v_condition->>'validity_mode'='fixed_period' and
           (coalesce(v_condition->>'validity_days','') !~ '^[0-9]+$'
            or (v_condition->>'validity_days')::integer not between 1 and 3650))
       or (v_condition->>'validity_mode'='lifetime' and v_condition->>'validity_days' is not null)
       or jsonb_typeof(v_condition->'product_ids') is distinct from 'array' then
      raise exception using errcode='P0001',message='ecommerce_loyalty_rule_invalid';
    end if;
    if jsonb_array_length(v_condition->'product_ids') not between 1 and 100
       or (select count(distinct value) from jsonb_array_elements_text(v_condition->'product_ids'))
          <> jsonb_array_length(v_condition->'product_ids') then
      raise exception using errcode='P0001',message='ecommerce_loyalty_rule_invalid';
    end if;
    for v_product in select * from jsonb_array_elements_text(v_condition->'product_ids') loop
      if not exists(select 1 from public.ecommerce_products
          where tenant_id=p_tenant_id and id=v_product::uuid and status in ('active','inactive')) then
        raise exception using errcode='P0001',message='ecommerce_loyalty_reward_product_invalid';
      end if;
    end loop;
    if v_condition->>'audience'='loyalty' and v_primary is null then v_primary:=v_condition; end if;
  end loop;
  if v_primary is null then
    raise exception using errcode='P0001',message='ecommerce_loyalty_rule_invalid';
  end if;
  -- Reuse actor validation, currency validation, advisory locking and versioning.
  v_rule:=public.save_ecommerce_loyalty_rule_safe(p_tenant_id,p_actor_id,p_enabled,
    p_earning_rate_basis_points,p_threshold_points,(v_primary->'product_ids'->>0)::uuid,
    v_primary->>'validity_mode',(v_primary->>'validity_days')::integer);
  update public.ecommerce_loyalty_rules set discount_conditions=p_conditions
    where tenant_id=p_tenant_id and id=(v_rule->>'id')::uuid
    returning to_jsonb(ecommerce_loyalty_rules.*) into v_rule;
  return v_rule;
end $$;

create or replace function public.snapshot_ecommerce_reward_conditions()
returns trigger language plpgsql security definer set search_path=public as $$
declare v_conditions jsonb; v_lifetime boolean; v_days integer;
begin
  select coalesce(jsonb_agg(c),'[]'::jsonb) into v_conditions
    from public.ecommerce_loyalty_rules r,
         lateral jsonb_array_elements(r.discount_conditions) c
    where r.tenant_id=new.tenant_id and r.id=new.rule_id and c->>'audience'='loyalty';
  if jsonb_array_length(v_conditions)>0 then
    new.reward_conditions:=v_conditions;
    select bool_or(c->>'validity_mode'='lifetime'),max((c->>'validity_days')::integer)
      into v_lifetime,v_days from jsonb_array_elements(v_conditions) c;
    -- Outer validity represents the entire bundle; each condition is evaluated
    -- separately from granted_at. Expiring one offer never expires a lifetime one.
    new.validity_mode:=case when v_lifetime then 'lifetime' else 'fixed_period' end;
    new.validity_days:=case when v_lifetime then null else v_days end;
    new.expires_at:=case when v_lifetime then null else new.granted_at+make_interval(days=>v_days) end;
  end if;
  return new;
end $$;
create trigger ecommerce_reward_conditions_snapshot before insert
  on public.ecommerce_loyalty_entitlements for each row
  execute function public.snapshot_ecommerce_reward_conditions();

-- Server-authoritative maximum per product. Normal offers remain an eligible
-- fallback for everyone; loyalty candidates require this customer's active
-- entitlement. Ties prefer loyalty for an unambiguous historical source.
create or replace function public.best_ecommerce_product_discount_safe(
  p_tenant_id integer,p_customer_id integer,p_product_id uuid
) returns jsonb language sql stable security definer set search_path=public as $$
  with candidates as (
    select (c->>'discount_basis_points')::integer as basis_points,
           'normal'::text as source,null::uuid as entitlement_id
      from public.ecommerce_loyalty_rules r,
           lateral jsonb_array_elements(r.discount_conditions) c
      where r.tenant_id=p_tenant_id and r.is_current and r.enabled
        and c->>'audience'='normal' and c->'product_ids' ? p_product_id::text
        and (c->>'validity_mode'='lifetime'
          or r.created_at+make_interval(days=>(c->>'validity_days')::integer)>now())
    union all
    select (c->>'discount_basis_points')::integer,'loyalty',e.id
      from public.ecommerce_loyalty_entitlements e,
           lateral jsonb_array_elements(e.reward_conditions) c
      where e.tenant_id=p_tenant_id and e.customer_id=p_customer_id and e.status='active'
        and (e.expires_at is null or e.expires_at>now())
        and c->'product_ids' ? p_product_id::text
        and (c->>'validity_mode'='lifetime'
          or e.granted_at+make_interval(days=>(c->>'validity_days')::integer)>now())
    union all
    select e.reward_discount_basis_points,'loyalty',e.id
      from public.ecommerce_loyalty_entitlements e
      where e.tenant_id=p_tenant_id and e.customer_id=p_customer_id and e.status='active'
        and (e.expires_at is null or e.expires_at>now())
        and e.reward_conditions='[]'::jsonb and e.reward_product_id=p_product_id
  )
  select coalesce((select jsonb_build_object('basis_points',basis_points,
       'source',source,'entitlement_id',entitlement_id)
       from candidates order by basis_points desc,(source='loyalty') desc,entitlement_id
       limit 1),'{"basis_points":0,"source":null,"entitlement_id":null}'::jsonb);
$$;

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
  if exists(select 1 from public.ecommerce_loyalty_transactions where tenant_id=p_tenant_id and order_id=p_order_id and transaction_type='earn') then return jsonb_build_object('awarded',false,'duplicate',true); end if;
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


create or replace function public.create_ecommerce_order_safe(p_order jsonb,p_idempotency_key_hash text,p_request_hash text,p_confirmation_token_hash text,p_customer_id integer)
returns jsonb language plpgsql security definer set search_path=public as $$
declare v_tenant_id integer; v_currency text; v_existing public.ecommerce_orders; v_order public.ecommerce_orders; v_area record; v_requested record; v_product public.ecommerce_products; v_variant public.ecommerce_product_variants; v_order_item public.ecommerce_order_items; v_entitlement public.ecommerce_loyalty_entitlements; v_discount jsonb; v_count integer; v_subtotal numeric(14,2):=0; v_discount_total numeric(14,2):=0; v_price numeric(14,2); v_unit_discount numeric(14,2); v_final_unit numeric(14,2); v_total numeric(14,2); v_allocated integer; v_has_options boolean; v_options jsonb;
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
  perform 1 from public.ecommerce_loyalty_rules where tenant_id=v_tenant_id and is_current for share;
  if p_customer_id is not null then
    perform public.expire_ecommerce_loyalty_entitlements_safe(v_tenant_id,p_customer_id);
    perform 1 from public.ecommerce_loyalty_entitlements where tenant_id=v_tenant_id and customer_id=p_customer_id and status='active' order by id for share;
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
    v_discount:=public.best_ecommerce_product_discount_safe(v_tenant_id,p_customer_id,v_product.id);
    v_unit_discount:=round(v_price*(v_discount->>'basis_points')::integer/10000.0,2); v_final_unit:=v_price-v_unit_discount; v_total:=(v_final_unit*v_requested.quantity)::numeric(14,2); v_subtotal:=v_subtotal+(v_price*v_requested.quantity)::numeric(14,2); v_discount_total:=v_discount_total+(v_unit_discount*v_requested.quantity)::numeric(14,2);
    insert into public.ecommerce_order_items(tenant_id,order_id,product_id,variant_id,sku,product_name,product_slug,product_snapshot,variant_snapshot,selected_options_snapshot,quantity,list_unit_price,discount_amount,discount_source,loyalty_entitlement_id,unit_price,line_total,inventory_allocated_quantity)
    values(v_tenant_id,v_order.id,v_product.id,v_requested.variant_id,case when v_has_options then v_variant.sku else v_product.sku end,coalesce(nullif(v_product.translations->'en'->>'name',''),v_product.slug),v_product.slug,jsonb_build_object('slug',v_product.slug,'translations',v_product.translations,'brand',v_product.brand,'images',v_product.images),case when v_has_options then jsonb_build_object('id',v_variant.id,'sku',v_variant.sku,'barcode',v_variant.barcode,'images',v_variant.images,'price_override',v_variant.price_override,'compare_at_price_override',v_variant.compare_at_price_override) else '{}'::jsonb end,v_options,v_requested.quantity,v_price,v_unit_discount*v_requested.quantity,case when v_unit_discount>0 then v_discount->>'source' else null end,case when v_unit_discount>0 then (v_discount->>'entitlement_id')::uuid else null end,v_final_unit,v_total,v_allocated) returning * into v_order_item;
    if v_allocated>0 then if v_has_options then update public.ecommerce_product_variants set inventory_quantity=inventory_quantity-v_allocated where tenant_id=v_tenant_id and id=v_variant.id; else update public.ecommerce_products set inventory_quantity=inventory_quantity-v_allocated where tenant_id=v_tenant_id and id=v_product.id; end if; insert into public.ecommerce_inventory_movements(tenant_id,product_id,variant_id,order_id,order_item_id,movement_type,quantity_delta,idempotency_key_hash,reason) values(v_tenant_id,v_product.id,v_requested.variant_id,v_order.id,v_order_item.id,'order_allocation',-v_allocated,encode(extensions.digest('allocate:'||v_order_item.id::text,'sha256'),'hex'),'order_created'); end if;
  end loop;
  update public.ecommerce_orders set subtotal=v_subtotal,discount_total=v_discount_total,total=v_subtotal-v_discount_total where id=v_order.id and tenant_id=v_tenant_id returning * into v_order;
  insert into public.ecommerce_order_status_history(tenant_id,order_id,previous_status,new_status,actor_id,note,idempotency_key_hash) values(v_tenant_id,v_order.id,null,'pending',null,'Order created',encode(extensions.digest('initial-status:'||v_order.id::text,'sha256'),'hex'));
  return jsonb_build_object('duplicate',false,'order',to_jsonb(v_order));
end $$;

revoke all on function public.save_ecommerce_loyalty_rule_v2_safe(integer,integer,boolean,integer,bigint,jsonb) from public,anon,authenticated;
revoke all on function public.best_ecommerce_product_discount_safe(integer,integer,uuid) from public,anon,authenticated;
revoke all on function public.snapshot_ecommerce_reward_conditions() from public,anon,authenticated;
grant execute on function public.save_ecommerce_loyalty_rule_v2_safe(integer,integer,boolean,integer,bigint,jsonb) to service_role;
grant execute on function public.best_ecommerce_product_discount_safe(integer,integer,uuid) to service_role;

do $$ declare v_schema_version public.application_schema_state.schema_version%TYPE; begin
  select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
  if v_schema_version is null then raise exception using errcode='P0001',message='migration_100_schema_state_missing'; end if;
  if v_schema_version <> 99 then raise exception using errcode='P0001',message=format('migration_100_expected_schema_99_got_%s',v_schema_version); end if;
  update public.application_schema_state set schema_version = 100,applied_at=now() where contract_key = 'core';
end $$;

notify pgrst,'reload schema';
commit;
