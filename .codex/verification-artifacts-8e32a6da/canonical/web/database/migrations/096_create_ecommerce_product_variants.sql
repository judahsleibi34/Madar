begin;

create table public.ecommerce_product_attributes (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  product_id uuid not null,
  name_translations jsonb not null,
  value_translations jsonb not null,
  normalized_name text not null,
  sort_order integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ecommerce_product_attributes_product_fk foreign key (tenant_id,product_id)
    references public.ecommerce_products(tenant_id,id) on delete cascade,
  constraint ecommerce_product_attributes_translation_check check (
    jsonb_typeof(name_translations)='object' and jsonb_typeof(value_translations)='object'
    and octet_length(name_translations::text)<=4000 and octet_length(value_translations::text)<=12000
  ),
  constraint ecommerce_product_attributes_name_check check (normalized_name ~ '^[^[:cntrl:]]{1,200}$'),
  constraint ecommerce_product_attributes_sort_check check (sort_order between 0 and 1000000),
  unique (tenant_id,product_id,normalized_name),
  unique (tenant_id,id)
);

create table public.ecommerce_product_options (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  product_id uuid not null,
  code text not null,
  name_translations jsonb not null,
  normalized_name text not null,
  required boolean not null default true,
  sort_order integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ecommerce_product_options_product_fk foreign key (tenant_id,product_id)
    references public.ecommerce_products(tenant_id,id) on delete cascade,
  constraint ecommerce_product_options_code_check check (code ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$' and length(code)<=80),
  constraint ecommerce_product_options_translation_check check (jsonb_typeof(name_translations)='object' and octet_length(name_translations::text)<=4000),
  constraint ecommerce_product_options_name_check check (normalized_name ~ '^[^[:cntrl:]]{1,200}$'),
  constraint ecommerce_product_options_sort_check check (sort_order between 0 and 1000000),
  unique (tenant_id,product_id,code),
  unique (tenant_id,product_id,normalized_name),
  unique (tenant_id,product_id,id),
  unique (tenant_id,id)
);

create table public.ecommerce_product_option_values (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  product_id uuid not null,
  option_id uuid not null,
  code text not null,
  value_translations jsonb not null,
  normalized_value text not null,
  sort_order integer not null default 0,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ecommerce_product_option_values_option_fk foreign key (tenant_id,product_id,option_id)
    references public.ecommerce_product_options(tenant_id,product_id,id) on delete restrict,
  constraint ecommerce_product_option_values_code_check check (code ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$' and length(code)<=80),
  constraint ecommerce_product_option_values_translation_check check (jsonb_typeof(value_translations)='object' and octet_length(value_translations::text)<=4000),
  constraint ecommerce_product_option_values_value_check check (normalized_value ~ '^[^[:cntrl:]]{1,200}$'),
  constraint ecommerce_product_option_values_sort_check check (sort_order between 0 and 1000000),
  unique (tenant_id,option_id,code),
  unique (tenant_id,option_id,normalized_value),
  unique (tenant_id,product_id,option_id,id),
  unique (tenant_id,id)
);

create table public.ecommerce_product_variants (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  product_id uuid not null,
  sku text not null,
  barcode text,
  price_override numeric(14,2),
  compare_at_price_override numeric(14,2),
  track_inventory boolean not null default true,
  inventory_quantity integer not null default 0,
  low_stock_threshold integer not null default 5,
  allow_backorder boolean not null default false,
  images jsonb not null default '[]'::jsonb,
  active boolean not null default true,
  option_signature text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ecommerce_product_variants_product_fk foreign key (tenant_id,product_id)
    references public.ecommerce_products(tenant_id,id) on delete restrict,
  constraint ecommerce_product_variants_sku_check check (length(trim(sku)) between 1 and 120),
  constraint ecommerce_product_variants_price_check check (price_override is null or price_override>=0),
  constraint ecommerce_product_variants_compare_check check (compare_at_price_override is null or compare_at_price_override>=0),
  constraint ecommerce_product_variants_inventory_check check (inventory_quantity>=0 and low_stock_threshold>=0),
  constraint ecommerce_product_variants_images_check check (jsonb_typeof(images)='array' and jsonb_array_length(images)<=4),
  constraint ecommerce_product_variants_signature_check check (option_signature ~ '^[0-9a-f]{64}$'),
  unique (tenant_id,sku),
  unique (tenant_id,product_id,option_signature),
  unique (tenant_id,product_id,id),
  unique (tenant_id,id)
);

create table public.ecommerce_variant_option_values (
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  product_id uuid not null,
  variant_id uuid not null,
  option_id uuid not null,
  option_value_id uuid not null,
  created_at timestamptz not null default now(),
  primary key (variant_id,option_id),
  unique (variant_id,option_value_id),
  constraint ecommerce_variant_option_values_variant_fk foreign key (tenant_id,product_id,variant_id)
    references public.ecommerce_product_variants(tenant_id,product_id,id) on delete cascade,
  constraint ecommerce_variant_option_values_value_fk foreign key (tenant_id,product_id,option_id,option_value_id)
    references public.ecommerce_product_option_values(tenant_id,product_id,option_id,id) on delete restrict
);

create index ecommerce_product_attributes_product_idx on public.ecommerce_product_attributes(tenant_id,product_id,sort_order);
create index ecommerce_product_options_product_idx on public.ecommerce_product_options(tenant_id,product_id,sort_order);
create index ecommerce_option_values_option_idx on public.ecommerce_product_option_values(tenant_id,option_id,sort_order);
create index ecommerce_variants_product_idx on public.ecommerce_product_variants(tenant_id,product_id,active);
create index ecommerce_variant_values_value_idx on public.ecommerce_variant_option_values(tenant_id,option_value_id);

do $$ declare v_table text; begin
  foreach v_table in array array['ecommerce_product_attributes','ecommerce_product_options','ecommerce_product_option_values','ecommerce_product_variants','ecommerce_variant_option_values'] loop
    execute format('alter table public.%I enable row level security',v_table);
    execute format('revoke all on table public.%I from anon,authenticated',v_table);
    execute format('grant select,insert,update,delete on table public.%I to service_role',v_table);
  end loop;
end $$;

do $$ declare v_table text; begin
  foreach v_table in array array['ecommerce_product_attributes','ecommerce_product_options','ecommerce_product_option_values','ecommerce_product_variants'] loop
    execute format('create trigger set_%I_updated_at before update on public.%I for each row execute function public.set_updated_at()',v_table,v_table);
  end loop;
end $$;

create or replace function public.enforce_ecommerce_catalog_sku_unique()
returns trigger language plpgsql set search_path=public as $$
begin
  perform pg_advisory_xact_lock(hashtextextended('ecommerce-sku:'||new.tenant_id,0));
  if tg_table_name='ecommerce_products' and exists(
    select 1 from public.ecommerce_product_variants where tenant_id=new.tenant_id and lower(sku)=lower(new.sku)
  ) then raise exception using errcode='23505',message='ecommerce_sku_conflict'; end if;
  if tg_table_name='ecommerce_product_variants' and exists(
    select 1 from public.ecommerce_products where tenant_id=new.tenant_id and lower(sku)=lower(new.sku)
  ) then raise exception using errcode='23505',message='ecommerce_sku_conflict'; end if;
  return new;
end $$;
create trigger ecommerce_products_cross_sku before insert or update of sku on public.ecommerce_products
for each row execute function public.enforce_ecommerce_catalog_sku_unique();
create trigger ecommerce_variants_cross_sku before insert or update of sku on public.ecommerce_product_variants
for each row execute function public.enforce_ecommerce_catalog_sku_unique();

alter table public.ecommerce_order_items add column variant_id uuid;
alter table public.ecommerce_order_items add constraint ecommerce_order_items_variant_tenant_fk
  foreign key (tenant_id,product_id,variant_id) references public.ecommerce_product_variants(tenant_id,product_id,id) on delete restrict;
alter table public.ecommerce_inventory_movements add column variant_id uuid;
alter table public.ecommerce_inventory_movements add constraint ecommerce_inventory_movements_variant_tenant_fk
  foreign key (tenant_id,product_id,variant_id) references public.ecommerce_product_variants(tenant_id,product_id,id) on delete restrict;
create index ecommerce_inventory_movements_variant_idx on public.ecommerce_inventory_movements(tenant_id,variant_id,created_at desc) where variant_id is not null;


create or replace function public.create_ecommerce_order_safe(p_order jsonb,p_idempotency_key_hash text,p_request_hash text,p_confirmation_token_hash text)
returns jsonb language plpgsql security definer set search_path=public as $$
declare v_tenant_id integer; v_currency text; v_existing public.ecommerce_orders; v_order public.ecommerce_orders; v_area record; v_requested record; v_product public.ecommerce_products; v_variant public.ecommerce_product_variants; v_order_item public.ecommerce_order_items; v_count integer; v_subtotal numeric(14,2):=0; v_price numeric(14,2); v_total numeric(14,2); v_allocated integer; v_has_options boolean; v_options jsonb;
begin
  if jsonb_typeof(p_order)<>'object' or jsonb_typeof(p_order->'items')<>'array' then raise exception using errcode='P0001',message='ecommerce_order_payload_invalid'; end if;
  if p_idempotency_key_hash is null or p_idempotency_key_hash!~'^[0-9a-f]{64}$' or p_request_hash is null or p_request_hash!~'^[0-9a-f]{64}$' or p_confirmation_token_hash is null or p_confirmation_token_hash!~'^[0-9a-f]{64}$' then raise exception using errcode='P0001',message='idempotency_key_invalid'; end if;
  v_tenant_id:=nullif(p_order->>'tenant_id','')::integer;
  if v_tenant_id is null or coalesce(p_order->>'payment_method','')<>'cash_on_delivery' then raise exception using errcode='P0001',message='ecommerce_order_payload_invalid'; end if;
  if length(trim(coalesce(p_order->>'street','')))<3 then raise exception using errcode='P0001',message='ecommerce_delivery_street_required'; end if;
  v_count:=jsonb_array_length(p_order->'items');
  if v_count<1 or v_count>50 then raise exception using errcode='P0001',message='ecommerce_order_items_invalid'; end if;
  if (select count(*) from (select item->>'product_id',coalesce(item->>'variant_id','') from jsonb_array_elements(p_order->'items') item group by 1,2)q)<>v_count then raise exception using errcode='P0001',message='ecommerce_order_items_duplicate'; end if;
  perform pg_advisory_xact_lock(hashtextextended(concat_ws(':','ecommerce-order',v_tenant_id,p_idempotency_key_hash),0));
  select * into v_existing from public.ecommerce_orders where tenant_id=v_tenant_id and idempotency_key_hash=p_idempotency_key_hash for update;
  if found then
    if v_existing.request_hash is distinct from p_request_hash then raise exception using errcode='P0001',message='idempotency_conflict'; end if;
    return jsonb_build_object('duplicate',true,'order',to_jsonb(v_existing));
  end if;
  select area.* into v_area from public.ecommerce_service_areas area join public.ecommerce_tenant_service_areas mapping on mapping.service_area_id=area.id and mapping.tenant_id=v_tenant_id and mapping.enabled where area.id=nullif(p_order->>'service_area_id','')::uuid and area.active for share of area,mapping;
  if not found then raise exception using errcode='P0001',message='ecommerce_delivery_area_unavailable'; end if;
  select ecommerce_currency into v_currency from public.website_settings where tenant_id=v_tenant_id;
  if v_currency is null then raise exception using errcode='P0001',message='ecommerce_currency_configuration_required'; end if;
  insert into public.ecommerce_orders(tenant_id,order_number,status,payment_status,payment_method,currency,subtotal,discount_total,total,customer_name,customer_email,customer_phone,address_line_1,address_line_2,city,postal_code,country,notes,service_area_id,service_area_code,service_area_name_en,service_area_name_ar,street,building,floor_apartment,address_description,delivery_notes,confirmation_token_hash,confirmation_created_at,idempotency_key_hash,request_hash)
  values(v_tenant_id,'MD-'||to_char(timezone('UTC',now()),'YYYYMMDD')||'-'||upper(substr(replace(gen_random_uuid()::text,'-',''),1,8)),'pending','unpaid','cash_on_delivery',v_currency,0,0,0,trim(coalesce(p_order->>'customer_name','')),lower(trim(coalesce(p_order->>'email',''))),trim(coalesce(p_order->>'phone','')),trim(p_order->>'street'),concat_ws(', ',nullif(trim(coalesce(p_order->>'building','')),''),nullif(trim(coalesce(p_order->>'floor_apartment','')),'')),v_area.name_en,'',trim(coalesce(p_order->>'country','')),trim(coalesce(p_order->>'delivery_notes','')),v_area.id,v_area.code,v_area.name_en,v_area.name_ar,trim(p_order->>'street'),trim(coalesce(p_order->>'building','')),trim(coalesce(p_order->>'floor_apartment','')),trim(coalesce(p_order->>'address_description','')),trim(coalesce(p_order->>'delivery_notes','')),p_confirmation_token_hash,now(),p_idempotency_key_hash,p_request_hash) returning * into v_order;
  for v_requested in select * from jsonb_to_recordset(p_order->'items') as r(product_id uuid,variant_id uuid,quantity integer) order by product_id,variant_id nulls first loop
    if v_requested.quantity is null or v_requested.quantity<1 or v_requested.quantity>99 then raise exception using errcode='P0001',message='ecommerce_quantity_invalid'; end if;
    select * into v_product from public.ecommerce_products where tenant_id=v_tenant_id and id=v_requested.product_id and status='active' for update;
    if not found then raise exception using errcode='P0001',message='ecommerce_product_unavailable'; end if;
    if v_product.currency<>v_currency then raise exception using errcode='P0001',message='ecommerce_currency_product_mismatch'; end if;
    select exists(select 1 from public.ecommerce_product_options where tenant_id=v_tenant_id and product_id=v_product.id) into v_has_options;
    v_options:='{}'::jsonb;
    if v_has_options then
      if v_requested.variant_id is null then raise exception using errcode='P0001',message='ecommerce_variant_required'; end if;
      select * into v_variant from public.ecommerce_product_variants where tenant_id=v_tenant_id and product_id=v_product.id and id=v_requested.variant_id and active for update;
      if not found then raise exception using errcode='P0001',message='ecommerce_variant_unavailable'; end if;
      if exists(select 1 from public.ecommerce_product_options o where o.tenant_id=v_tenant_id and o.product_id=v_product.id and o.required and not exists(select 1 from public.ecommerce_variant_option_values l where l.variant_id=v_variant.id and l.option_id=o.id)) then raise exception using errcode='P0001',message='ecommerce_variant_incomplete'; end if;
      select jsonb_build_object('items',coalesce(jsonb_agg(jsonb_build_object('option_code',o.code,'option_name_translations',o.name_translations,'value_code',ov.code,'value_translations',ov.value_translations) order by o.sort_order,ov.sort_order),'[]'::jsonb)) into v_options from public.ecommerce_variant_option_values l join public.ecommerce_product_options o on o.id=l.option_id join public.ecommerce_product_option_values ov on ov.id=l.option_value_id where l.tenant_id=v_tenant_id and l.variant_id=v_variant.id;
      v_price:=coalesce(v_variant.price_override,v_product.price);
      if v_variant.track_inventory and not v_variant.allow_backorder and v_requested.quantity>v_variant.inventory_quantity then raise exception using errcode='P0001',message='ecommerce_inventory_insufficient'; end if;
      v_allocated:=case when v_variant.track_inventory then least(v_requested.quantity,v_variant.inventory_quantity) else 0 end;
    else
      if v_requested.variant_id is not null then raise exception using errcode='P0001',message='ecommerce_variant_not_allowed'; end if;
      v_price:=v_product.price;
      if v_product.track_inventory and not v_product.allow_backorder and v_requested.quantity>v_product.inventory_quantity then raise exception using errcode='P0001',message='ecommerce_inventory_insufficient'; end if;
      v_allocated:=case when v_product.track_inventory then least(v_requested.quantity,v_product.inventory_quantity) else 0 end;
    end if;
    v_total:=(v_price*v_requested.quantity)::numeric(14,2); v_subtotal:=v_subtotal+v_total;
    insert into public.ecommerce_order_items(tenant_id,order_id,product_id,variant_id,sku,product_name,product_slug,product_snapshot,variant_snapshot,selected_options_snapshot,quantity,list_unit_price,discount_amount,discount_source,unit_price,line_total,inventory_allocated_quantity)
    values(v_tenant_id,v_order.id,v_product.id,v_requested.variant_id,case when v_has_options then v_variant.sku else v_product.sku end,coalesce(nullif(v_product.translations->'en'->>'name',''),v_product.slug),v_product.slug,jsonb_build_object('slug',v_product.slug,'translations',v_product.translations,'brand',v_product.brand,'images',v_product.images),case when v_has_options then jsonb_build_object('id',v_variant.id,'sku',v_variant.sku,'barcode',v_variant.barcode,'images',v_variant.images,'price_override',v_variant.price_override,'compare_at_price_override',v_variant.compare_at_price_override) else '{}'::jsonb end,v_options,v_requested.quantity,v_price,0,null,v_price,v_total,v_allocated) returning * into v_order_item;
    if v_allocated>0 then
      if v_has_options then update public.ecommerce_product_variants set inventory_quantity=inventory_quantity-v_allocated where tenant_id=v_tenant_id and id=v_variant.id; else update public.ecommerce_products set inventory_quantity=inventory_quantity-v_allocated where tenant_id=v_tenant_id and id=v_product.id; end if;
      insert into public.ecommerce_inventory_movements(tenant_id,product_id,variant_id,order_id,order_item_id,movement_type,quantity_delta,idempotency_key_hash,reason) values(v_tenant_id,v_product.id,v_requested.variant_id,v_order.id,v_order_item.id,'order_allocation',-v_allocated,encode(extensions.digest('allocate:'||v_order_item.id::text,'sha256'),'hex'),'order_created');
    end if;
  end loop;
  update public.ecommerce_orders set subtotal=v_subtotal,discount_total=0,total=v_subtotal where id=v_order.id and tenant_id=v_tenant_id returning * into v_order;
  insert into public.ecommerce_order_status_history(tenant_id,order_id,previous_status,new_status,actor_id,note,idempotency_key_hash) values(v_tenant_id,v_order.id,null,'pending',null,'Order created',encode(extensions.digest('initial-status:'||v_order.id::text,'sha256'),'hex'));
  return jsonb_build_object('duplicate',false,'order',to_jsonb(v_order));
end $$;

create or replace function public.restore_ecommerce_order_inventory_safe(p_tenant_id integer,p_order_id uuid,p_reason text,p_idempotency_key_hash text)
returns jsonb language plpgsql security definer set search_path=public as $$
declare v_order public.ecommerce_orders; v_item record; v_movement_id uuid; v_restored integer:=0;
begin
  if p_reason not in ('cancelled','rejected') or p_idempotency_key_hash is null or p_idempotency_key_hash!~'^[0-9a-f]{64}$' then raise exception using errcode='P0001',message='ecommerce_inventory_restoration_invalid'; end if;
  perform pg_advisory_xact_lock(hashtextextended(concat_ws(':','ecommerce-order-restore',p_tenant_id,p_order_id),0));
  select * into v_order from public.ecommerce_orders where id=p_order_id and tenant_id=p_tenant_id for update;
  if not found then raise exception using errcode='P0002',message='ecommerce_order_not_found'; end if;
  if v_order.status='fulfilled' then raise exception using errcode='P0001',message='ecommerce_inventory_restore_fulfilled_order'; end if;
  if v_order.inventory_restored_at is not null then return jsonb_build_object('order_id',p_order_id,'status',v_order.status,'restored_quantity',0,'duplicate',true); end if;
  for v_item in select * from public.ecommerce_order_items where tenant_id=p_tenant_id and order_id=p_order_id and inventory_allocated_quantity>0 order by id for update loop
    if v_item.product_id is null then raise exception using errcode='P0001',message='ecommerce_inventory_restore_product_missing'; end if;
    v_movement_id:=null;
    insert into public.ecommerce_inventory_movements(tenant_id,product_id,variant_id,order_id,order_item_id,movement_type,quantity_delta,idempotency_key_hash,reason) values(p_tenant_id,v_item.product_id,v_item.variant_id,p_order_id,v_item.id,'order_restoration',v_item.inventory_allocated_quantity,encode(extensions.digest(p_idempotency_key_hash||':'||v_item.id::text,'sha256'),'hex'),p_reason) on conflict do nothing returning id into v_movement_id;
    if v_movement_id is not null then
      if v_item.variant_id is not null then update public.ecommerce_product_variants set inventory_quantity=inventory_quantity+v_item.inventory_allocated_quantity where tenant_id=p_tenant_id and product_id=v_item.product_id and id=v_item.variant_id; else update public.ecommerce_products set inventory_quantity=inventory_quantity+v_item.inventory_allocated_quantity where tenant_id=p_tenant_id and id=v_item.product_id; end if;
      if not found then raise exception using errcode='P0001',message='ecommerce_inventory_restore_product_missing'; end if;
      v_restored:=v_restored+v_item.inventory_allocated_quantity;
    end if;
  end loop;
  update public.ecommerce_orders set status=p_reason,status_reason=p_reason,inventory_restored_at=now(),updated_at=now() where id=p_order_id and tenant_id=p_tenant_id returning * into v_order;
  return jsonb_build_object('order_id',p_order_id,'status',v_order.status,'restored_quantity',v_restored,'duplicate',false);
end $$;

revoke all on function public.create_ecommerce_order_safe(jsonb,text,text,text) from public,anon,authenticated;
revoke all on function public.restore_ecommerce_order_inventory_safe(integer,uuid,text,text) from public,anon,authenticated;
grant execute on function public.create_ecommerce_order_safe(jsonb,text,text,text) to service_role;
grant execute on function public.restore_ecommerce_order_inventory_safe(integer,uuid,text,text) to service_role;
-- One explicit-save transaction owns every nested product-specific structure.
create or replace function public.save_ecommerce_product_aggregate_safe(
  p_tenant_id integer,p_product_id uuid,p_attributes jsonb,p_options jsonb,p_variants jsonb
) returns jsonb language plpgsql security definer set search_path=public as $$
declare v_product public.ecommerce_products; v_option jsonb; v_value jsonb; v_variant jsonb; v_option_id uuid; v_variant_id uuid; v_value_ids uuid[]; v_signature text;
begin
  if jsonb_typeof(p_attributes)<>'array' or jsonb_typeof(p_options)<>'array' or jsonb_typeof(p_variants)<>'array'
     or jsonb_array_length(p_attributes)>50 or jsonb_array_length(p_options)>5 or jsonb_array_length(p_variants)>500 then
    raise exception using errcode='P0001',message='ecommerce_product_aggregate_limit';
  end if;
  select * into v_product from public.ecommerce_products where tenant_id=p_tenant_id and id=p_product_id for update;
  if not found then raise exception using errcode='P0002',message='ecommerce_product_not_found'; end if;
  perform pg_advisory_xact_lock(hashtextextended('ecommerce-sku:'||p_tenant_id,0));

  delete from public.ecommerce_product_attributes where tenant_id=p_tenant_id and product_id=p_product_id;
  insert into public.ecommerce_product_attributes(id,tenant_id,product_id,name_translations,value_translations,normalized_name,sort_order)
  select (x->>'id')::uuid,p_tenant_id,p_product_id,x->'name_translations',x->'value_translations',lower(trim(x->>'normalized_name')),coalesce((x->>'sort_order')::integer,0)
  from jsonb_array_elements(p_attributes) x;

  create temporary table if not exists pg_temp.p1_option_ids(client_id text primary key,id uuid not null) on commit drop;
  truncate pg_temp.p1_option_ids;
  for v_option in select * from jsonb_array_elements(p_options) loop
    if jsonb_typeof(v_option->'values')<>'array' or jsonb_array_length(v_option->'values')>50 then
      raise exception using errcode='P0001',message='ecommerce_option_values_limit';
    end if;
    v_option_id:=(v_option->>'id')::uuid;
    insert into pg_temp.p1_option_ids values(v_option->>'client_id',v_option_id);
    insert into public.ecommerce_product_options(id,tenant_id,product_id,code,name_translations,normalized_name,required,sort_order)
    values(v_option_id,p_tenant_id,p_product_id,v_option->>'code',v_option->'name_translations',lower(trim(v_option->>'normalized_name')),coalesce((v_option->>'required')::boolean,true),coalesce((v_option->>'sort_order')::integer,0))
    on conflict(id) do update set code=excluded.code,name_translations=excluded.name_translations,normalized_name=excluded.normalized_name,required=excluded.required,sort_order=excluded.sort_order
    where ecommerce_product_options.tenant_id=p_tenant_id and ecommerce_product_options.product_id=p_product_id;
    for v_value in select * from jsonb_array_elements(v_option->'values') loop
      insert into public.ecommerce_product_option_values(id,tenant_id,product_id,option_id,code,value_translations,normalized_value,sort_order,active)
      values((v_value->>'id')::uuid,p_tenant_id,p_product_id,v_option_id,v_value->>'code',v_value->'value_translations',lower(trim(v_value->>'normalized_value')),coalesce((v_value->>'sort_order')::integer,0),coalesce((v_value->>'active')::boolean,true))
      on conflict(id) do update set code=excluded.code,value_translations=excluded.value_translations,normalized_value=excluded.normalized_value,sort_order=excluded.sort_order,active=excluded.active
      where ecommerce_product_option_values.tenant_id=p_tenant_id and ecommerce_product_option_values.product_id=p_product_id;
    end loop;
  end loop;

  for v_variant in select * from jsonb_array_elements(p_variants) loop
    select array_agg(value_id order by value_id) into v_value_ids from jsonb_array_elements_text(v_variant->'option_value_ids') q(value_id_text)
      cross join lateral (select q.value_id_text::uuid value_id) casted;
    if v_value_ids is null or cardinality(v_value_ids)=0 then raise exception using errcode='P0001',message='ecommerce_variant_options_required'; end if;
    if exists(select 1 from unnest(v_value_ids) value_id left join public.ecommerce_product_option_values x on x.id=value_id and x.tenant_id=p_tenant_id and x.product_id=p_product_id where x.id is null) then
      raise exception using errcode='P0001',message='ecommerce_variant_option_value_invalid';
    end if;
    if (select count(distinct option_id) from public.ecommerce_product_option_values where tenant_id=p_tenant_id and product_id=p_product_id and id=any(v_value_ids))<>cardinality(v_value_ids) then
      raise exception using errcode='P0001',message='ecommerce_variant_duplicate_option';
    end if;
    if exists(select 1 from public.ecommerce_product_options o where o.tenant_id=p_tenant_id and o.product_id=p_product_id and o.required and not exists(select 1 from public.ecommerce_product_option_values ov where ov.option_id=o.id and ov.id=any(v_value_ids))) then
      raise exception using errcode='P0001',message='ecommerce_variant_required_option_missing';
    end if;
    v_signature:=encode(extensions.digest(array_to_string(v_value_ids,','),'sha256'),'hex');
    v_variant_id:=(v_variant->>'id')::uuid;
    insert into public.ecommerce_product_variants(id,tenant_id,product_id,sku,barcode,price_override,compare_at_price_override,track_inventory,inventory_quantity,low_stock_threshold,allow_backorder,images,active,option_signature)
    values(v_variant_id,p_tenant_id,p_product_id,trim(v_variant->>'sku'),nullif(trim(v_variant->>'barcode'),''),nullif(v_variant->>'price_override','')::numeric,nullif(v_variant->>'compare_at_price_override','')::numeric,coalesce((v_variant->>'track_inventory')::boolean,true),coalesce((v_variant->>'inventory_quantity')::integer,0),coalesce((v_variant->>'low_stock_threshold')::integer,5),coalesce((v_variant->>'allow_backorder')::boolean,false),coalesce(v_variant->'images','[]'::jsonb),coalesce((v_variant->>'active')::boolean,true),v_signature)
    on conflict(id) do update set sku=excluded.sku,barcode=excluded.barcode,price_override=excluded.price_override,compare_at_price_override=excluded.compare_at_price_override,track_inventory=excluded.track_inventory,inventory_quantity=excluded.inventory_quantity,low_stock_threshold=excluded.low_stock_threshold,allow_backorder=excluded.allow_backorder,images=excluded.images,active=excluded.active,option_signature=excluded.option_signature
    where ecommerce_product_variants.tenant_id=p_tenant_id and ecommerce_product_variants.product_id=p_product_id;
    delete from public.ecommerce_variant_option_values where tenant_id=p_tenant_id and variant_id=v_variant_id;
    insert into public.ecommerce_variant_option_values(tenant_id,product_id,variant_id,option_id,option_value_id)
    select p_tenant_id,p_product_id,v_variant_id,option_id,id from public.ecommerce_product_option_values where tenant_id=p_tenant_id and product_id=p_product_id and id=any(v_value_ids);
  end loop;

  -- Referenced values/variants are archived; unreferenced omissions are removed.
  update public.ecommerce_product_variants set active=false where tenant_id=p_tenant_id and product_id=p_product_id
    and id not in (select nullif(x->>'id','')::uuid from jsonb_array_elements(p_variants)x where nullif(x->>'id','') is not null);
  delete from public.ecommerce_product_option_values v where tenant_id=p_tenant_id and product_id=p_product_id
    and not exists(select 1 from jsonb_array_elements(p_options)o,jsonb_array_elements(o->'values')x where nullif(x->>'id','')::uuid=v.id)
    and not exists(select 1 from public.ecommerce_variant_option_values l where l.option_value_id=v.id);
  update public.ecommerce_product_option_values v set active=false where tenant_id=p_tenant_id and product_id=p_product_id
    and not exists(select 1 from jsonb_array_elements(p_options)o,jsonb_array_elements(o->'values')x where nullif(x->>'id','')::uuid=v.id);
  delete from public.ecommerce_product_options o where tenant_id=p_tenant_id and product_id=p_product_id
    and not exists(select 1 from jsonb_array_elements(p_options)x where nullif(x->>'id','')::uuid=o.id)
    and not exists(select 1 from public.ecommerce_product_option_values v join public.ecommerce_variant_option_values l on l.option_value_id=v.id where v.option_id=o.id);

  if v_product.status='active' and jsonb_array_length(p_options)>0 and not exists(select 1 from public.ecommerce_product_variants where tenant_id=p_tenant_id and product_id=p_product_id and active) then
    raise exception using errcode='P0001',message='ecommerce_variant_product_not_purchasable';
  end if;
  return jsonb_build_object('product_id',p_product_id,'saved',true);
end $$;


create or replace function public.validate_ecommerce_variant_product_publication()
returns trigger language plpgsql security definer set search_path=public as $$
begin
  if new.status='active' and exists(
    select 1 from public.ecommerce_product_options where tenant_id=new.tenant_id and product_id=new.id
  ) then
    if not exists(
      select 1 from public.ecommerce_product_variants where tenant_id=new.tenant_id and product_id=new.id and active
    ) then
      raise exception using errcode='P0001',message='ecommerce_variant_product_not_purchasable';
    end if;
    if exists(
      select 1 from public.ecommerce_product_variants variant
      where variant.tenant_id=new.tenant_id and variant.product_id=new.id and variant.active
        and (
          exists(select 1 from public.ecommerce_product_options option where option.tenant_id=new.tenant_id and option.product_id=new.id and option.required and not exists(select 1 from public.ecommerce_variant_option_values link where link.variant_id=variant.id and link.option_id=option.id))
          or exists(select 1 from public.ecommerce_variant_option_values link join public.ecommerce_product_option_values value on value.id=link.option_value_id where link.variant_id=variant.id and not value.active)
        )
    ) then
      raise exception using errcode='P0001',message='ecommerce_variant_incomplete';
    end if;
  end if;
  return new;
end $$;

create trigger validate_ecommerce_variant_product_publication_trigger
before insert or update of status on public.ecommerce_products
for each row execute function public.validate_ecommerce_variant_product_publication();

revoke all on function public.save_ecommerce_product_aggregate_safe(integer,uuid,jsonb,jsonb,jsonb) from public,anon,authenticated;
grant execute on function public.save_ecommerce_product_aggregate_safe(integer,uuid,jsonb,jsonb,jsonb) to service_role;

do $$ declare v_schema_version public.application_schema_state.schema_version%TYPE; begin
  select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
  if v_schema_version is null then raise exception using errcode='P0001',message='migration_096_schema_state_missing'; end if;
  if v_schema_version<>95 then raise exception using errcode='P0001',message=format('migration_096_expected_schema_95_got_%s',v_schema_version); end if;
  update public.application_schema_state set schema_version = 96, applied_at = now() where contract_key = 'core';
end $$;

notify pgrst,'reload schema';
commit;
