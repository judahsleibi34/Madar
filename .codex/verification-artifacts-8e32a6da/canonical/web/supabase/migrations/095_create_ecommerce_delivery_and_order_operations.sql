begin;

create table public.ecommerce_service_areas (
  id uuid primary key,
  code text not null unique,
  name_en text not null,
  name_ar text not null,
  active boolean not null default true,
  sort_order integer not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ecommerce_service_areas_code_check check (code ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  constraint ecommerce_service_areas_names_check check (trim(name_en) <> '' and trim(name_ar) <> ''),
  constraint ecommerce_service_areas_sort_check check (sort_order >= 0)
);

insert into public.ecommerce_service_areas (id, code, name_en, name_ar, active, sort_order) values
  ('95000000-0000-0000-0000-000000000001','ramallah','Ramallah','رام الله',true,10),
  ('95000000-0000-0000-0000-000000000002','al-bireh','Al-Bireh','البيرة',true,20),
  ('95000000-0000-0000-0000-000000000003','nablus','Nablus','نابلس',true,30),
  ('95000000-0000-0000-0000-000000000004','al-khalil','Hebron / Al-Khalil','الخليل',true,40),
  ('95000000-0000-0000-0000-000000000005','bethlehem','Bethlehem','بيت لحم',true,50),
  ('95000000-0000-0000-0000-000000000006','jenin','Jenin','جنين',true,60),
  ('95000000-0000-0000-0000-000000000007','tulkarm','Tulkarm','طولكرم',true,70),
  ('95000000-0000-0000-0000-000000000008','qalqilya','Qalqilya','قلقيلية',true,80),
  ('95000000-0000-0000-0000-000000000009','jericho','Jericho','أريحا',true,90),
  ('95000000-0000-0000-0000-000000000010','salfit','Salfit','سلفيت',true,100),
  ('95000000-0000-0000-0000-000000000011','tubas','Tubas','طوباس',true,110),
  ('95000000-0000-0000-0000-000000000012','jerusalem','Jerusalem','القدس',true,120);

create table public.ecommerce_tenant_service_areas (
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  service_area_id uuid not null references public.ecommerce_service_areas(id) on delete restrict,
  enabled boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, service_area_id)
);
create index ecommerce_tenant_service_areas_enabled_idx
  on public.ecommerce_tenant_service_areas (tenant_id, enabled, service_area_id);

alter table public.ecommerce_service_areas enable row level security;
alter table public.ecommerce_tenant_service_areas enable row level security;
revoke all on table public.ecommerce_service_areas, public.ecommerce_tenant_service_areas from anon, authenticated;
grant select, insert, update, delete on table public.ecommerce_service_areas, public.ecommerce_tenant_service_areas to service_role;

alter table public.ecommerce_orders add column service_area_id uuid references public.ecommerce_service_areas(id) on delete restrict;
alter table public.ecommerce_orders add column service_area_code text;
alter table public.ecommerce_orders add column service_area_name_en text;
alter table public.ecommerce_orders add column service_area_name_ar text;
alter table public.ecommerce_orders add column street text;
alter table public.ecommerce_orders add column building text not null default '';
alter table public.ecommerce_orders add column floor_apartment text not null default '';
alter table public.ecommerce_orders add column address_description text not null default '';
alter table public.ecommerce_orders add column delivery_notes text not null default '';
alter table public.ecommerce_orders add column confirmation_token_hash text;
alter table public.ecommerce_orders add column confirmation_created_at timestamptz;
alter table public.ecommerce_orders add column payment_collected_at timestamptz;
alter table public.ecommerce_orders add column payment_collected_by integer references public.users(id) on delete set null;

alter table public.ecommerce_orders drop constraint if exists ecommerce_orders_status_check;
alter table public.ecommerce_orders add constraint ecommerce_orders_status_check
  check (status in ('pending','confirmed','preparing','out_for_delivery','delivered','fulfilled','cancelled','rejected'));
alter table public.ecommerce_orders drop constraint if exists ecommerce_orders_payment_status_check;
alter table public.ecommerce_orders add constraint ecommerce_orders_payment_status_check
  check (payment_status in ('unpaid','collected','paid','refunded'));
alter table public.ecommerce_orders add constraint ecommerce_orders_confirmation_hash_check
  check (confirmation_token_hash is null or confirmation_token_hash ~ '^[0-9a-f]{64}$') not valid;
create unique index ecommerce_orders_confirmation_token_unique_idx
  on public.ecommerce_orders (tenant_id, confirmation_token_hash)
  where confirmation_token_hash is not null;
create index ecommerce_orders_operations_idx
  on public.ecommerce_orders (tenant_id, status, payment_status, created_at desc);
create index ecommerce_orders_service_area_idx
  on public.ecommerce_orders (tenant_id, service_area_id, created_at desc);

alter table public.ecommerce_order_items add column variant_snapshot jsonb not null default '{}'::jsonb;
alter table public.ecommerce_order_items add column selected_options_snapshot jsonb not null default '{}'::jsonb;
alter table public.ecommerce_order_items add constraint ecommerce_order_items_future_snapshots_check
  check (jsonb_typeof(variant_snapshot) = 'object' and jsonb_typeof(selected_options_snapshot) = 'object') not valid;

create table public.ecommerce_order_status_history (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  order_id uuid not null,
  previous_status text,
  new_status text not null,
  actor_id integer references public.users(id) on delete set null,
  note text,
  idempotency_key_hash text not null,
  created_at timestamptz not null default now(),
  constraint ecommerce_order_status_history_order_fk foreign key (tenant_id, order_id)
    references public.ecommerce_orders(tenant_id, id) on delete restrict,
  constraint ecommerce_order_status_history_hash_check check (idempotency_key_hash ~ '^[0-9a-f]{64}$'),
  unique (tenant_id, order_id, idempotency_key_hash)
);
create index ecommerce_order_status_history_order_idx
  on public.ecommerce_order_status_history (tenant_id, order_id, created_at);
alter table public.ecommerce_order_status_history enable row level security;
revoke all on table public.ecommerce_order_status_history from anon, authenticated;
grant select, insert on table public.ecommerce_order_status_history to service_role;

create or replace function public.set_ecommerce_delivery_areas_safe(
  p_tenant_id integer,
  p_service_area_ids uuid[]
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_ids uuid[] := coalesce(p_service_area_ids, '{}'::uuid[]);
begin
  if p_tenant_id is null or not exists (select 1 from public.tenants where tenant_id = p_tenant_id) then
    raise exception using errcode = 'P0002', message = 'ecommerce_tenant_not_found';
  end if;
  if exists (
    select 1 from (select distinct unnest(v_ids) as id) requested
    left join public.ecommerce_service_areas area on area.id = requested.id and area.active
    where area.id is null
  ) then
    raise exception using errcode = 'P0001', message = 'ecommerce_service_area_invalid';
  end if;

  perform pg_advisory_xact_lock(hashtextextended('ecommerce-delivery:' || p_tenant_id::text, 0));
  update public.ecommerce_tenant_service_areas
  set enabled = false, updated_at = now()
  where tenant_id = p_tenant_id and enabled;

  insert into public.ecommerce_tenant_service_areas (tenant_id, service_area_id, enabled)
  select p_tenant_id, requested.id, true
  from (select distinct unnest(v_ids) as id) requested
  on conflict (tenant_id, service_area_id) do update
    set enabled = true, updated_at = now();

  return jsonb_build_object(
    'enabled_service_area_ids', coalesce((
      select jsonb_agg(mapping.service_area_id order by area.sort_order)
      from public.ecommerce_tenant_service_areas mapping
      join public.ecommerce_service_areas area on area.id = mapping.service_area_id
      where mapping.tenant_id = p_tenant_id and mapping.enabled and area.active
    ), '[]'::jsonb)
  );
end;
$$;

create or replace function public.create_ecommerce_order_safe(
  p_order jsonb,
  p_idempotency_key_hash text,
  p_request_hash text,
  p_confirmation_token_hash text
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
  v_area record;
  v_product record;
  v_order_item public.ecommerce_order_items;
  v_requested_count integer;
  v_matched_count integer := 0;
  v_subtotal numeric(14, 2) := 0;
  v_line_total numeric(14, 2);
  v_allocated integer;
begin
  if jsonb_typeof(p_order) <> 'object' or jsonb_typeof(p_order -> 'items') <> 'array' then
    raise exception using errcode = 'P0001', message = 'ecommerce_order_payload_invalid';
  end if;
  if p_idempotency_key_hash is null or p_idempotency_key_hash !~ '^[0-9a-f]{64}$'
     or p_request_hash is null or p_request_hash !~ '^[0-9a-f]{64}$'
     or p_confirmation_token_hash is null or p_confirmation_token_hash !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = 'P0001', message = 'idempotency_key_invalid';
  end if;
  v_tenant_id := nullif(p_order ->> 'tenant_id', '')::integer;
  if v_tenant_id is null or coalesce(p_order ->> 'payment_method', '') <> 'cash_on_delivery' then
    raise exception using errcode = 'P0001', message = 'ecommerce_order_payload_invalid';
  end if;
  if length(trim(coalesce(p_order ->> 'street', ''))) < 3 then
    raise exception using errcode = 'P0001', message = 'ecommerce_delivery_street_required';
  end if;

  v_requested_count := jsonb_array_length(p_order -> 'items');
  if v_requested_count < 1 or v_requested_count > 50 then
    raise exception using errcode = 'P0001', message = 'ecommerce_order_items_invalid';
  end if;
  if (select count(*) from (
    select item ->> 'product_id' from jsonb_array_elements(p_order -> 'items') item group by item ->> 'product_id'
  ) unique_items) <> v_requested_count then
    raise exception using errcode = 'P0001', message = 'ecommerce_order_items_duplicate';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(concat_ws(':','ecommerce-order',v_tenant_id,p_idempotency_key_hash),0));
  select * into v_existing from public.ecommerce_orders
  where tenant_id = v_tenant_id and idempotency_key_hash = p_idempotency_key_hash for update;
  if found then
    if v_existing.request_hash is distinct from p_request_hash then
      raise exception using errcode = 'P0001', message = 'idempotency_conflict';
    end if;
    return jsonb_build_object('duplicate',true,'order',to_jsonb(v_existing));
  end if;

  select area.* into v_area
  from public.ecommerce_service_areas area
  join public.ecommerce_tenant_service_areas mapping
    on mapping.service_area_id = area.id and mapping.tenant_id = v_tenant_id and mapping.enabled
  where area.id = nullif(p_order ->> 'service_area_id','')::uuid and area.active
  for share of area, mapping;
  if not found then
    raise exception using errcode = 'P0001', message = 'ecommerce_delivery_area_unavailable';
  end if;

  select ecommerce_currency into v_currency from public.website_settings where tenant_id = v_tenant_id;
  if v_currency is null then
    raise exception using errcode = 'P0001', message = 'ecommerce_currency_configuration_required';
  end if;

  insert into public.ecommerce_orders (
    tenant_id,order_number,status,payment_status,payment_method,currency,
    subtotal,discount_total,total,customer_name,customer_email,customer_phone,
    address_line_1,address_line_2,city,postal_code,country,notes,
    service_area_id,service_area_code,service_area_name_en,service_area_name_ar,
    street,building,floor_apartment,address_description,delivery_notes,
    confirmation_token_hash,confirmation_created_at,idempotency_key_hash,request_hash
  ) values (
    v_tenant_id,'MD-'||to_char(timezone('UTC',now()),'YYYYMMDD')||'-'||upper(substr(replace(gen_random_uuid()::text,'-',''),1,8)),
    'pending','unpaid','cash_on_delivery',v_currency,0,0,0,
    trim(coalesce(p_order->>'customer_name','')),lower(trim(coalesce(p_order->>'email',''))),trim(coalesce(p_order->>'phone','')),
    trim(p_order->>'street'),concat_ws(', ',nullif(trim(coalesce(p_order->>'building','')),''),nullif(trim(coalesce(p_order->>'floor_apartment','')),'')),
    v_area.name_en,'',trim(coalesce(p_order->>'country','')),trim(coalesce(p_order->>'delivery_notes','')),
    v_area.id,v_area.code,v_area.name_en,v_area.name_ar,trim(p_order->>'street'),trim(coalesce(p_order->>'building','')),
    trim(coalesce(p_order->>'floor_apartment','')),trim(coalesce(p_order->>'address_description','')),trim(coalesce(p_order->>'delivery_notes','')),
    p_confirmation_token_hash,now(),p_idempotency_key_hash,p_request_hash
  ) returning * into v_order;

  for v_product in
    select product.*, requested.quantity
    from jsonb_to_recordset(p_order -> 'items') as requested(product_id uuid, quantity integer)
    join public.ecommerce_products product on product.id=requested.product_id and product.tenant_id=v_tenant_id and product.status='active'
    order by product.id for update of product
  loop
    v_matched_count := v_matched_count + 1;
    if v_product.quantity is null or v_product.quantity < 1 or v_product.quantity > 99 then
      raise exception using errcode = 'P0001', message = 'ecommerce_quantity_invalid';
    end if;
    if v_product.currency <> v_currency then
      raise exception using errcode = 'P0001', message = 'ecommerce_currency_product_mismatch';
    end if;
    if v_product.track_inventory and not v_product.allow_backorder and v_product.quantity > v_product.inventory_quantity then
      raise exception using errcode = 'P0001', message = 'ecommerce_inventory_insufficient';
    end if;
    v_allocated := case when v_product.track_inventory then least(v_product.quantity,v_product.inventory_quantity) else 0 end;
    v_line_total := (v_product.price*v_product.quantity)::numeric(14,2);
    v_subtotal := v_subtotal+v_line_total;
    insert into public.ecommerce_order_items (
      tenant_id,order_id,product_id,sku,product_name,product_slug,product_snapshot,
      variant_snapshot,selected_options_snapshot,quantity,list_unit_price,discount_amount,
      discount_source,unit_price,line_total,inventory_allocated_quantity
    ) values (
      v_tenant_id,v_order.id,v_product.id,v_product.sku,
      coalesce(nullif(v_product.translations->'en'->>'name',''),v_product.slug),v_product.slug,
      jsonb_build_object('slug',v_product.slug,'translations',v_product.translations,'brand',v_product.brand,'images',v_product.images),
      '{}'::jsonb,'{}'::jsonb,v_product.quantity,v_product.price,0,null,v_product.price,v_line_total,v_allocated
    ) returning * into v_order_item;
    if v_allocated > 0 then
      update public.ecommerce_products set inventory_quantity=inventory_quantity-v_allocated
      where id=v_product.id and tenant_id=v_tenant_id;
      insert into public.ecommerce_inventory_movements (
        tenant_id,product_id,order_id,order_item_id,movement_type,quantity_delta,idempotency_key_hash,reason
      ) values (
        v_tenant_id,v_product.id,v_order.id,v_order_item.id,'order_allocation',-v_allocated,
        encode(extensions.digest('allocate:'||v_order_item.id::text,'sha256'),'hex'),'order_created'
      );
    end if;
  end loop;
  if v_matched_count <> v_requested_count then
    raise exception using errcode = 'P0001', message = 'ecommerce_product_unavailable';
  end if;
  update public.ecommerce_orders set subtotal=v_subtotal,discount_total=0,total=v_subtotal
  where id=v_order.id and tenant_id=v_tenant_id returning * into v_order;
  insert into public.ecommerce_order_status_history (
    tenant_id,order_id,previous_status,new_status,actor_id,note,idempotency_key_hash
  ) values (
    v_tenant_id,v_order.id,null,'pending',null,'Order created',
    encode(extensions.digest('initial-status:'||v_order.id::text,'sha256'),'hex')
  );
  return jsonb_build_object('duplicate',false,'order',to_jsonb(v_order));
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
begin
  raise exception using
    errcode = 'P0001',
    message = 'ecommerce_delivery_upgrade_required';
end;
$$;

create or replace function public.transition_ecommerce_order_status_safe(
  p_tenant_id integer,
  p_order_id uuid,
  p_new_status text,
  p_actor_id integer,
  p_note text,
  p_idempotency_key_hash text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order public.ecommerce_orders;
  v_previous text;
  v_history public.ecommerce_order_status_history;
begin
  if p_idempotency_key_hash is null or p_idempotency_key_hash !~ '^[0-9a-f]{64}$' then
    raise exception using errcode='P0001', message='idempotency_key_invalid';
  end if;
  perform pg_advisory_xact_lock(hashtextextended(concat_ws(':','ecommerce-order-status',p_tenant_id,p_order_id),0));
  select * into v_history from public.ecommerce_order_status_history
  where tenant_id=p_tenant_id and order_id=p_order_id and idempotency_key_hash=p_idempotency_key_hash;
  if found then
    if v_history.new_status <> p_new_status then raise exception using errcode='P0001', message='idempotency_conflict'; end if;
    select * into v_order from public.ecommerce_orders where tenant_id=p_tenant_id and id=p_order_id;
    return jsonb_build_object('duplicate',true,'order',to_jsonb(v_order));
  end if;
  select * into v_order from public.ecommerce_orders where tenant_id=p_tenant_id and id=p_order_id for update;
  if not found then raise exception using errcode='P0002', message='ecommerce_order_not_found'; end if;
  if p_actor_id is null or not exists (select 1 from public.users where id=p_actor_id and tenant_id=p_tenant_id) then
    raise exception using errcode='P0001', message='ecommerce_order_actor_invalid';
  end if;
  if v_order.status = p_new_status then return jsonb_build_object('duplicate',true,'order',to_jsonb(v_order)); end if;
  if not (
    (v_order.status='pending' and p_new_status in ('confirmed','cancelled','rejected')) or
    (v_order.status='confirmed' and p_new_status in ('preparing','cancelled','rejected')) or
    (v_order.status='preparing' and p_new_status in ('out_for_delivery','cancelled')) or
    (v_order.status='out_for_delivery' and p_new_status='delivered')
  ) then raise exception using errcode='P0001', message='ecommerce_order_transition_invalid'; end if;
  v_previous := v_order.status;
  if p_new_status in ('cancelled','rejected') then
    perform public.restore_ecommerce_order_inventory_safe(p_tenant_id,p_order_id,p_new_status,p_idempotency_key_hash);
  else
    update public.ecommerce_orders set status=p_new_status,status_reason=trim(coalesce(p_note,'')),updated_at=now()
    where tenant_id=p_tenant_id and id=p_order_id returning * into v_order;
  end if;
  select * into v_order from public.ecommerce_orders where tenant_id=p_tenant_id and id=p_order_id;
  insert into public.ecommerce_order_status_history (
    tenant_id,order_id,previous_status,new_status,actor_id,note,idempotency_key_hash
  ) values (p_tenant_id,p_order_id,v_previous,p_new_status,p_actor_id,nullif(trim(coalesce(p_note,'')),''),p_idempotency_key_hash);
  return jsonb_build_object('duplicate',false,'order',to_jsonb(v_order));
end;
$$;

create or replace function public.collect_ecommerce_cod_payment_safe(
  p_tenant_id integer,
  p_order_id uuid,
  p_actor_id integer
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare v_order public.ecommerce_orders;
begin
  perform pg_advisory_xact_lock(hashtextextended(concat_ws(':','ecommerce-cod',p_tenant_id,p_order_id),0));
  select * into v_order from public.ecommerce_orders where tenant_id=p_tenant_id and id=p_order_id for update;
  if not found then raise exception using errcode='P0002', message='ecommerce_order_not_found'; end if;
  if p_actor_id is null or not exists (select 1 from public.users where id=p_actor_id and tenant_id=p_tenant_id) then
    raise exception using errcode='P0001', message='ecommerce_order_actor_invalid';
  end if;
  if v_order.payment_method <> 'cash_on_delivery' then raise exception using errcode='P0001', message='ecommerce_cod_required'; end if;
  if v_order.payment_status in ('collected','paid') then
    return jsonb_build_object('duplicate',true,'order',to_jsonb(v_order));
  end if;
  if v_order.payment_status <> 'unpaid' then raise exception using errcode='P0001', message='ecommerce_payment_transition_invalid'; end if;
  update public.ecommerce_orders set payment_status='collected',payment_collected_at=now(),payment_collected_by=p_actor_id,updated_at=now()
  where tenant_id=p_tenant_id and id=p_order_id returning * into v_order;
  return jsonb_build_object('duplicate',false,'order',to_jsonb(v_order));
end;
$$;

revoke all on function public.set_ecommerce_delivery_areas_safe(integer,uuid[]) from public,anon,authenticated;
revoke all on function public.create_ecommerce_order_safe(jsonb,text,text) from public,anon,authenticated;
revoke all on function public.create_ecommerce_order_safe(jsonb,text,text,text) from public,anon,authenticated;
revoke all on function public.transition_ecommerce_order_status_safe(integer,uuid,text,integer,text,text) from public,anon,authenticated;
revoke all on function public.collect_ecommerce_cod_payment_safe(integer,uuid,integer) from public,anon,authenticated;
grant execute on function public.set_ecommerce_delivery_areas_safe(integer,uuid[]) to service_role;
grant execute on function public.create_ecommerce_order_safe(jsonb,text,text) to service_role;
grant execute on function public.create_ecommerce_order_safe(jsonb,text,text,text) to service_role;
grant execute on function public.transition_ecommerce_order_status_safe(integer,uuid,text,integer,text,text) to service_role;
grant execute on function public.collect_ecommerce_cod_payment_safe(integer,uuid,integer) to service_role;

do $$
declare
  v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version into v_schema_version
  from public.application_schema_state where contract_key='core' for update;
  if v_schema_version is null then
    raise exception using errcode='P0001', message='migration_095_schema_state_missing';
  end if;
  if v_schema_version <> 94 then
    raise exception using errcode='P0001', message=format('migration_095_expected_schema_94_got_%s',v_schema_version);
  end if;
  update public.application_schema_state
  set schema_version = 95, applied_at = now()
  where contract_key = 'core';
end;
$$;

notify pgrst, 'reload schema';
commit;
