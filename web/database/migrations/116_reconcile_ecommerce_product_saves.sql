begin;

-- Refuse ambiguous normalized history instead of choosing a row by iteration order.
-- No semantic-name/SKU/history backfill is attempted.
do $$ begin
 if exists(select 1 from public.ecommerce_product_options group by tenant_id,product_id,lower(trim(coalesce(name_translations->>'en',name_translations->>'ar',normalized_name))) having count(*)>1) then
  raise exception using errcode='P0001',message='migration_116_ambiguous_option_history';
 end if;
 if exists(select 1 from public.ecommerce_product_option_values group by tenant_id,option_id,lower(trim(coalesce(value_translations->>'en',value_translations->>'ar',normalized_value))) having count(*)>1) then
  raise exception using errcode='P0001',message='migration_116_ambiguous_value_history';
 end if;
end $$;

alter table public.ecommerce_product_options add column active boolean not null default true;
-- Only unambiguous historical membership is initialized inactive: values exist,
-- all are inactive, and no active variant references this option. IDs/FKs/labels,
-- quantities, SKUs, required flags and order snapshots remain untouched.
update public.ecommerce_product_options o set active=false
 where exists(select 1 from public.ecommerce_product_option_values v where v.tenant_id=o.tenant_id and v.option_id=o.id)
 and not exists(select 1 from public.ecommerce_product_option_values v where v.tenant_id=o.tenant_id and v.option_id=o.id and v.active)
 and not exists(select 1 from public.ecommerce_product_option_values v join public.ecommerce_variant_option_values l on l.option_value_id=v.id and l.tenant_id=v.tenant_id
   join public.ecommerce_product_variants vr on vr.id=l.variant_id and vr.tenant_id=l.tenant_id where v.tenant_id=o.tenant_id and v.option_id=o.id and vr.active);

create view public.ecommerce_current_product_options with (security_invoker=true) as
 select * from public.ecommerce_product_options where active;
revoke all on public.ecommerce_current_product_options from public,anon,authenticated;
grant select on public.ecommerce_current_product_options to service_role;
-- Retain the latest checkout (including loyalty/discounts) and publication code,
-- replacing only its source of current options. Historical options remain intact.
do $$ declare definition text; signature text; begin
 foreach signature in array array['public.create_ecommerce_order_safe(jsonb,text,text,text,integer)','public.validate_ecommerce_variant_product_publication()'] loop
  definition:=pg_get_functiondef(signature::regprocedure);
  if position('public.ecommerce_product_options' in definition)=0 then raise exception 'migration_116_option_source_missing'; end if;
  execute replace(definition,'public.ecommerce_product_options','public.ecommerce_current_product_options');
 end loop;
end $$;

-- Preserve all final semantic uniqueness, including inactive history. Deferral is
-- opt-in only within the new RPC, allowing swaps to reach their valid final state.
-- Composite tenant/ID FK targets and primary keys remain immediate.
do $$
declare r record;
begin
  for r in select c.conname,t.relname,pg_get_constraintdef(c.oid) definition
    from pg_constraint c join pg_class t on t.oid=c.conrelid
    join pg_namespace n on n.oid=t.relnamespace
    where n.nspname='public' and c.contype='u'
      and t.relname in ('ecommerce_product_options','ecommerce_product_option_values','ecommerce_product_variants')
      and not exists(select 1 from unnest(c.conkey) k join pg_attribute a on a.attrelid=t.oid and a.attnum=k where a.attname='id')
  loop
    execute format('alter table public.%I drop constraint %I',r.relname,r.conname);
    execute format('alter table public.%I add constraint %I %s deferrable initially immediate',r.relname,r.conname,r.definition);
  end loop;
end $$;

-- Lock immediately but check the final cross-table SKU namespace at the boundary.
create function public.lock_ecommerce_catalog_sku_namespace()
returns trigger language plpgsql security definer set search_path=public as $$
begin
  perform pg_advisory_xact_lock(hashtextextended('ecommerce-sku:'||new.tenant_id,0));
  return new;
end $$;
drop trigger ecommerce_products_cross_sku on public.ecommerce_products;
drop trigger ecommerce_variants_cross_sku on public.ecommerce_product_variants;
create trigger ecommerce_products_sku_lock before insert or update of sku on public.ecommerce_products
for each row execute function public.lock_ecommerce_catalog_sku_namespace();
create trigger ecommerce_variants_sku_lock before insert or update of sku on public.ecommerce_product_variants
for each row execute function public.lock_ecommerce_catalog_sku_namespace();
create index ecommerce_products_tenant_lower_sku_idx on public.ecommerce_products(tenant_id,lower(sku));
create index ecommerce_variants_tenant_lower_sku_idx on public.ecommerce_product_variants(tenant_id,lower(sku));
create function public.check_ecommerce_catalog_sku_namespace()
returns trigger language plpgsql security definer set search_path=public as $$
declare final_sku text; conflict boolean;
begin
 if tg_table_name='ecommerce_products' then
  select lower(sku) into final_sku from public.ecommerce_products where tenant_id=new.tenant_id and id=new.id;
  select exists(select 1 from public.ecommerce_product_variants where tenant_id=new.tenant_id and lower(sku)=final_sku) into conflict;
 else
  select lower(sku) into final_sku from public.ecommerce_product_variants where tenant_id=new.tenant_id and id=new.id;
  select exists(select 1 from public.ecommerce_products where tenant_id=new.tenant_id and lower(sku)=final_sku) into conflict;
 end if;
 if conflict then raise exception using errcode='23505',message='ecommerce_sku_conflict',constraint='ecommerce_sku_conflict'; end if;
 return new;
end $$;
create constraint trigger ecommerce_products_cross_sku after insert or update of sku on public.ecommerce_products
  deferrable initially immediate for each row execute function public.check_ecommerce_catalog_sku_namespace();
create constraint trigger ecommerce_variants_cross_sku after insert or update of sku on public.ecommerce_product_variants
  deferrable initially immediate for each row execute function public.check_ecommerce_catalog_sku_namespace();

create or replace function public.save_ecommerce_product_aggregate_v3_core_safe(
  p_tenant_id integer,p_product_id uuid,p_attributes jsonb,p_options jsonb,p_variants jsonb
) returns jsonb language plpgsql security definer set search_path=public as $$
declare v_product public.ecommerce_products; v_option jsonb; v_value jsonb; v_variant jsonb; v_option_id uuid; v_variant_id uuid; v_value_ids uuid[]; v_signature text; v_display_type text;
begin
  if (p_attributes is not null and jsonb_typeof(p_attributes)<>'array') or jsonb_typeof(p_options)<>'array' or jsonb_typeof(p_variants)<>'array'
     or jsonb_array_length(p_attributes)>50 or jsonb_array_length(p_options)>5 or jsonb_array_length(p_variants)>500 then
    raise exception using errcode='P0001',message='ecommerce_product_aggregate_limit';
  end if;
  select * into v_product from public.ecommerce_products where tenant_id=p_tenant_id and id=p_product_id for update;
  if not found then raise exception using errcode='P0002',message='ecommerce_product_not_found'; end if;
  perform pg_advisory_xact_lock(hashtextextended('ecommerce-sku:'||p_tenant_id,0));

  if p_attributes is not null then
  if exists(select 1 from jsonb_array_elements(p_attributes) x join public.ecommerce_product_attributes a on a.id=(x->>'id')::uuid where a.tenant_id<>p_tenant_id or a.product_id<>p_product_id) then
    raise exception using errcode='P0001',message='ecommerce_identity_ownership_invalid';
  end if;
  delete from public.ecommerce_product_attributes where tenant_id=p_tenant_id and product_id=p_product_id;
  insert into public.ecommerce_product_attributes(id,tenant_id,product_id,name_translations,value_translations,normalized_name,sort_order)
  select (x->>'id')::uuid,p_tenant_id,p_product_id,x->'name_translations',x->'value_translations',lower(trim(x->>'normalized_name')),coalesce((x->>'sort_order')::integer,0)
  from jsonb_array_elements(p_attributes) x;

  end if;

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
    on conflict(id) do update set code=excluded.code,name_translations=excluded.name_translations,normalized_name=excluded.normalized_name,required=excluded.required,sort_order=excluded.sort_order,active=true
    where ecommerce_product_options.tenant_id=p_tenant_id and ecommerce_product_options.product_id=p_product_id;
    for v_value in select * from jsonb_array_elements(v_option->'values') loop
      insert into public.ecommerce_product_option_values(id,tenant_id,product_id,option_id,code,value_translations,normalized_value,sort_order,active)
      values((v_value->>'id')::uuid,p_tenant_id,p_product_id,v_option_id,v_value->>'code',v_value->'value_translations',lower(trim(v_value->>'normalized_value')),coalesce((v_value->>'sort_order')::integer,0),coalesce((v_value->>'active')::boolean,true))
      on conflict(id) do update set code=excluded.code,value_translations=excluded.value_translations,normalized_value=excluded.normalized_value,sort_order=excluded.sort_order,active=excluded.active
      where ecommerce_product_option_values.tenant_id=p_tenant_id and ecommerce_product_option_values.product_id=p_product_id and ecommerce_product_option_values.option_id=v_option_id;
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
    if exists(select 1 from public.ecommerce_product_options o where o.tenant_id=p_tenant_id and o.product_id=p_product_id and o.required and o.id in (select (x->>'id')::uuid from jsonb_array_elements(p_options)x) and not exists(select 1 from public.ecommerce_product_option_values ov where ov.option_id=o.id and ov.id=any(v_value_ids))) then
      raise exception using errcode='P0001',message='ecommerce_variant_required_option_missing';
    end if;
    if coalesce(nullif(v_variant->>'compare_at_price_override','')::numeric,v_product.compare_at_price) is not null
       and coalesce(nullif(v_variant->>'compare_at_price_override','')::numeric,v_product.compare_at_price)<=coalesce(nullif(v_variant->>'price_override','')::numeric,v_product.price) then
      raise exception using errcode='P0001',message='ecommerce_variant_compare_price_invalid';
    end if;
    if exists(select 1 from jsonb_array_elements_text(coalesce(v_variant->'images','[]')) image
      where image like '/uploads/%' and image not like '/uploads/tenant_'||p_tenant_id||'/builder_assets/%') then
      raise exception using errcode='P0001',message='ecommerce_image_ownership_invalid';
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
  update public.ecommerce_product_option_values v set active=false where tenant_id=p_tenant_id and product_id=p_product_id
    and not exists(select 1 from jsonb_array_elements(p_options)o,jsonb_array_elements(o->'values')x where nullif(x->>'id','')::uuid=v.id);
  update public.ecommerce_product_options o set active=false where tenant_id=p_tenant_id and product_id=p_product_id
    and not exists(select 1 from jsonb_array_elements(p_options)x where (x->>'id')::uuid=o.id);

  if v_product.status='active' and jsonb_array_length(p_options)>0 and not exists(select 1 from public.ecommerce_product_variants where tenant_id=p_tenant_id and product_id=p_product_id and active) then
    raise exception using errcode='P0001',message='ecommerce_variant_product_not_purchasable';
  end if;
  for v_option in select * from jsonb_array_elements(p_options) loop
    v_option_id := (v_option->>'id')::uuid;
    v_display_type := coalesce(nullif(v_option->>'display_type',''),'text');
    if v_display_type not in ('text','color') then
      raise exception using errcode='P0001',message='ecommerce_option_display_type_invalid';
    end if;

    update public.ecommerce_product_options
       set display_type=v_display_type
     where id=v_option_id and tenant_id=p_tenant_id and product_id=p_product_id;
    if not found then
      raise exception using errcode='P0001',message='ecommerce_option_presentation_target_invalid';
    end if;

    for v_value in select * from jsonb_array_elements(v_option->'values') loop
      if v_display_type='color' and coalesce((v_value->>'active')::boolean,true)
         and coalesce(v_value->>'color_hex','') !~ '^#[0-9A-Fa-f]{6}$' then
        raise exception using errcode='P0001',message='ecommerce_color_swatch_required';
      end if;
      if v_display_type='text' and nullif(v_value->>'color_hex','') is not null then
        raise exception using errcode='P0001',message='ecommerce_text_value_swatch_invalid';
      end if;
      update public.ecommerce_product_option_values
         set color_hex=case when v_display_type='color' then upper(v_value->>'color_hex') else null end
       where id=(v_value->>'id')::uuid
         and option_id=v_option_id
         and tenant_id=p_tenant_id
         and product_id=p_product_id;
      if not found then
        raise exception using errcode='P0001',message='ecommerce_value_presentation_target_invalid';
      end if;
    end loop;
  end loop;
  return jsonb_build_object('product_id',p_product_id,'saved',true);
end $$;



-- Registry state is a DB projection. Refresh it atomically and in batches,
-- without touching storage files. Historical snapshots retain media references.
create function public.refresh_ecommerce_product_assets_v3_safe(p_tenant_id integer,p_previous jsonb,p_current jsonb)
returns void language plpgsql security definer set search_path=public as $$
begin
 if p_previous=p_current then return; end if;
 -- Preserve current reference accounting: project rows + site slots + source
 -- existence for each taxonomy/catalog type. History is an additional retained source.
 with affected as (
 select a.*, '/uploads/'||a.storage_key url from public.builder_assets a
 where a.tenant_id=p_tenant_id and a.status<>'soft_deleted'
 and exists(select 1 from jsonb_array_elements_text(coalesce(p_previous,'[]')||coalesce(p_current,'[]')) u where u='/uploads/'||a.storage_key)
 ), counts as (
 select a.id,
 (select count(*) from public.builder_asset_references r where r.asset_id=a.id)
 +coalesce((select coalesce((s.logo_url=a.url)::integer,0)+coalesce(((to_jsonb(s)->>'loading_image_url')=a.url)::integer,0) from public.website_settings s where tenant_id=p_tenant_id),0)
 +coalesce((select count(*) from public.website_settings s cross join lateral jsonb_array_elements(coalesce(s.ecommerce_theme->'landing_page'->'slides','[]')) slide where s.tenant_id=p_tenant_id and slide->>'image_url'=a.url),0)
 +(exists(select 1 from public.ecommerce_categories c where tenant_id=p_tenant_id and image_url=a.url))::integer
 +(exists(select 1 from public.ecommerce_brands b where tenant_id=p_tenant_id and image_url=a.url))::integer
 +(exists(select 1 from public.ecommerce_products p where tenant_id=p_tenant_id and images ? a.url))::integer
 +(exists(select 1 from public.ecommerce_product_variants v where tenant_id=p_tenant_id and images ? a.url))::integer
 +(exists(select 1 from public.ecommerce_order_items i where tenant_id=p_tenant_id and ((i.product_snapshot->'images') ? a.url or (i.variant_snapshot->'images') ? a.url)))::integer refs
 from affected a
 )
 update public.builder_assets a set status=case when refs>0 then 'active' else 'unreferenced' end,
 reference_count=refs,last_referenced_at=case when refs>0 then now() else null end,
 retention_until=case when refs>0 then null else coalesce(a.retention_until,now()+interval '7 days') end,deleted_at=null,
 metadata=a.metadata||case when coalesce(p_current,'[]') ? ('/uploads/'||a.storage_key) then '{"usage":"ecommerce_product"}'::jsonb else '{}'::jsonb end
 from counts c where c.id=a.id and a.tenant_id=p_tenant_id;

end $$;
revoke all on function public.refresh_ecommerce_product_assets_v3_safe(integer,jsonb,jsonb) from public,anon,authenticated,service_role;

-- Catalog versions ignore allocation quantities/timestamps; inventory has its own guard.
create function public.ecommerce_catalog_metadata_v3(p_value jsonb) returns jsonb
language plpgsql immutable set search_path=public as $$
declare result jsonb; begin
 if jsonb_typeof(p_value)='object' then
  select coalesce(jsonb_object_agg(key,public.ecommerce_catalog_metadata_v3(value)),'{}') into result from jsonb_each(p_value) where key not in ('updated_at','inventory_quantity');
 elsif jsonb_typeof(p_value)='array' then
  select coalesce(jsonb_agg(public.ecommerce_catalog_metadata_v3(value) order by ord),'[]') into result from jsonb_array_elements(p_value) with ordinality x(value,ord);
 else result:=p_value; end if;
 return result;
end $$;
revoke all on function public.ecommerce_catalog_metadata_v3(jsonb) from public,anon,authenticated,service_role;

-- One product-scoped snapshot; used as the committed response and editor reload.
create function public.read_ecommerce_product_catalog_v3_safe(p_tenant_id integer,p_product_id uuid)
returns jsonb language sql stable security definer set search_path=public as $$
  select snapshot||jsonb_build_object('catalog_version',encode(extensions.digest(public.ecommerce_catalog_metadata_v3(snapshot)::text,'sha256'),'hex'),
    'inventory_version',encode(extensions.digest(jsonb_build_object('quantity',snapshot->'inventory_quantity','variants',(select coalesce(jsonb_agg(jsonb_build_object('id',v->>'id','quantity',v->'inventory_quantity') order by v->>'id'),'[]') from jsonb_array_elements(snapshot->'variants')v))::text,'sha256'),'hex')) from (
  select to_jsonb(p)||jsonb_build_object(
    'category_ids',coalesce((select jsonb_agg(category_id order by sort_order,category_id) from public.ecommerce_product_categories where tenant_id=p_tenant_id and product_id=p.id),'[]'),
    'tag_ids',coalesce((select jsonb_agg(tag_id order by tag_id) from public.ecommerce_product_tags where tenant_id=p_tenant_id and product_id=p.id),'[]'),
    'attributes',coalesce((select jsonb_agg(to_jsonb(a) order by sort_order,id) from public.ecommerce_product_attributes a where tenant_id=p_tenant_id and product_id=p.id),'[]'),
    'options',coalesce((select jsonb_agg(to_jsonb(o)||jsonb_build_object('values',
      coalesce((select jsonb_agg(to_jsonb(v) order by sort_order,id) from public.ecommerce_product_option_values v where tenant_id=p_tenant_id and option_id=o.id),'[]')) order by o.sort_order,o.id)
      from public.ecommerce_product_options o where tenant_id=p_tenant_id and product_id=p.id and active),'[]'),
    'variants',coalesce((select jsonb_agg(to_jsonb(v)||jsonb_build_object('option_value_ids',
      coalesce((select jsonb_agg(option_value_id order by option_id,option_value_id) from public.ecommerce_variant_option_values l where tenant_id=p_tenant_id and variant_id=v.id),'[]')) order by v.created_at,v.id)
      from public.ecommerce_product_variants v where tenant_id=p_tenant_id and product_id=p.id),'[]')
  ) as snapshot from public.ecommerce_products p where tenant_id=p_tenant_id and id=p_product_id) catalog;
$$;
revoke all on function public.read_ecommerce_product_catalog_v3_safe(integer,uuid) from public,anon,authenticated;
grant execute on function public.read_ecommerce_product_catalog_v3_safe(integer,uuid) to service_role;

-- Catalog reads supply the same concurrency token as committed save responses.
-- This replaces serial tenant-wide PostgREST loads with one snapshot RPC.
create function public.read_ecommerce_catalog_v3_safe(p_tenant_id integer)
returns jsonb language sql stable security definer set search_path=public as $$
 select jsonb_build_object(
  'tags',coalesce((select jsonb_agg(to_jsonb(t) order by created_at desc,id) from public.ecommerce_tags t where tenant_id=p_tenant_id),'[]'),
  'brands',coalesce((select jsonb_agg(to_jsonb(b) order by name,id) from public.ecommerce_brands b where tenant_id=p_tenant_id),'[]'),
  'categories',coalesce((select jsonb_agg(to_jsonb(c) order by sort_order,created_at,id) from public.ecommerce_categories c where tenant_id=p_tenant_id),'[]'),
  'products',coalesce((select jsonb_agg(public.read_ecommerce_product_catalog_v3_safe(p_tenant_id,p.id) order by p.created_at desc,p.id) from public.ecommerce_products p where tenant_id=p_tenant_id),'[]'),
  'commerce_currency',(select ecommerce_currency from public.website_settings where tenant_id=p_tenant_id));
$$;
revoke all on function public.read_ecommerce_catalog_v3_safe(integer) from public,anon,authenticated;
grant execute on function public.read_ecommerce_catalog_v3_safe(integer) to service_role;

-- Resolve only new identities by semantics. Retained IDs represent deliberate edits;
-- never move a claimed ID across a tenant, product or option. Conflicting claims
-- and duplicate final semantics are rejected by unchanged unique constraints.
create function public.save_ecommerce_product_aggregate_v3_safe(
  p_tenant_id integer,p_product_id uuid,p_attributes jsonb,p_options jsonb,p_variants jsonb,p_expected_catalog_version text default null,p_include_catalog boolean default true,p_expected_inventory_version text default null,p_preserve_inventory boolean default false
) returns jsonb language plpgsql security definer set search_path=public as $$
declare
  o jsonb; val jsonb; vr jsonb; options_out jsonb:='[]'; values_out jsonb; variants_out jsonb:='[]';
  candidate_quantity integer; oid uuid; vid uuid; rid uuid; candidate uuid; ids uuid[]; sig text; code_out text; option_code text;
  v_catalog_snapshot jsonb; value_map jsonb:='{}'; seen uuid[]:='{}'; signatures text[]:='{}'; old_images jsonb; new_images jsonb;
begin
  -- PostgREST JSON null means an omitted component, just like SQL NULL.
  p_attributes:=nullif(p_attributes,'null'::jsonb);
  p_options:=nullif(p_options,'null'::jsonb);
  p_variants:=nullif(p_variants,'null'::jsonb);
  -- Common SKU-before-product lock ordering avoids checkout/editor lock inversion.
  perform pg_advisory_xact_lock(hashtextextended('ecommerce-sku:'||p_tenant_id,0));
  perform 1 from public.ecommerce_products where tenant_id=p_tenant_id and id=p_product_id for update;
  if not found then raise exception using errcode='P0002',message='ecommerce_product_not_found'; end if;
  if p_expected_catalog_version is not null or (not p_preserve_inventory and p_expected_inventory_version is not null) or p_options is null or p_variants is null then
    v_catalog_snapshot:=public.read_ecommerce_product_catalog_v3_safe(p_tenant_id,p_product_id);
  end if;
  if p_expected_catalog_version is not null and p_expected_catalog_version is distinct from v_catalog_snapshot->>'catalog_version' then
    raise exception using errcode='P0001',message='CATALOG_CHANGED_CONFLICT';
  end if;
  if not p_preserve_inventory and p_expected_inventory_version is not null and p_expected_inventory_version is distinct from v_catalog_snapshot->>'inventory_version' then
    raise exception using errcode='P0001',message='CATALOG_CHANGED_CONFLICT';
  end if;
  if p_options is null then p_options:=v_catalog_snapshot->'options'; end if;
  if p_variants is null then select coalesce(jsonb_agg(v),'[]') into p_variants from jsonb_array_elements(v_catalog_snapshot->'variants')v where (v->>'active')::boolean; end if;
  if p_options is null or p_variants is null
     or (p_attributes is not null and jsonb_typeof(p_attributes)<>'array') or jsonb_typeof(p_options)<>'array' or jsonb_typeof(p_variants)<>'array'
     or jsonb_array_length(p_attributes)>50 or jsonb_array_length(p_options)>5 or jsonb_array_length(p_variants)>500 then
    raise exception using errcode='P0001',message='ecommerce_product_aggregate_limit';
  end if;
  for o in select * from jsonb_array_elements(p_options) loop
    oid:=(o->>'id')::uuid; option_code:=o->>'code';
    if exists(select 1 from public.ecommerce_product_options where id=oid and (tenant_id<>p_tenant_id or product_id<>p_product_id)) then
      raise exception using errcode='P0001',message='ecommerce_identity_ownership_invalid';
    end if;
    if not exists(select 1 from public.ecommerce_product_options where id=oid) then
    if (select count(*) from public.ecommerce_product_options where tenant_id=p_tenant_id and product_id=p_product_id and (lower(trim(normalized_name))=lower(trim(o->>'normalized_name')) or lower(trim(coalesce(name_translations->>'en',name_translations->>'ar',normalized_name)))=lower(trim(coalesce(o->'name_translations'->>'en',o->'name_translations'->>'ar',o->>'normalized_name')))))>1 then
      raise exception using errcode='23505',message='OPTION_NAME_CONFLICT';
    end if;
      select id,code into candidate,option_code from public.ecommerce_product_options
        where tenant_id=p_tenant_id and product_id=p_product_id and (lower(trim(normalized_name))=lower(trim(o->>'normalized_name')) or lower(trim(coalesce(name_translations->>'en',name_translations->>'ar',normalized_name)))=lower(trim(coalesce(o->'name_translations'->>'en',o->'name_translations'->>'ar',o->>'normalized_name'))));
      if candidate is not null then oid:=candidate; else option_code:=o->>'code'; end if;
    end if;
    values_out:='[]';
    if jsonb_typeof(o->'values') is distinct from 'array' or jsonb_array_length(o->'values')>50 then
      raise exception using errcode='P0001',message='ecommerce_option_values_limit';
    end if;
    for val in select * from jsonb_array_elements(o->'values') loop
      vid:=(val->>'id')::uuid; code_out:=val->>'code';
      if exists(select 1 from public.ecommerce_product_option_values where id=vid and
          (tenant_id<>p_tenant_id or product_id<>p_product_id or option_id<>oid)) then
        raise exception using errcode='P0001',message='ecommerce_identity_ownership_invalid';
      end if;
      if not exists(select 1 from public.ecommerce_product_option_values where id=vid) then
    if (select count(*) from public.ecommerce_product_option_values where tenant_id=p_tenant_id and option_id=oid and (lower(trim(normalized_value))=lower(trim(val->>'normalized_value')) or lower(trim(coalesce(value_translations->>'en',value_translations->>'ar',normalized_value)))=lower(trim(coalesce(val->'value_translations'->>'en',val->'value_translations'->>'ar',val->>'normalized_value')))))>1 then
        raise exception using errcode='23505',message='OPTION_VALUE_CONFLICT';
      end if;
          select id,code into candidate,code_out from public.ecommerce_product_option_values
          where tenant_id=p_tenant_id and option_id=oid and (lower(trim(normalized_value))=lower(trim(val->>'normalized_value')) or lower(trim(coalesce(value_translations->>'en',value_translations->>'ar',normalized_value)))=lower(trim(coalesce(val->'value_translations'->>'en',val->'value_translations'->>'ar',val->>'normalized_value'))));
        if candidate is not null then vid:=candidate; else code_out:=val->>'code'; end if;
      end if;
      if lower(option_code)='size' and coalesce(val->'value_translations'->>'en','') ~ '[/,+&]|[[:space:]]+(or|او)[[:space:]]+' and not exists(
        select 1 from public.ecommerce_product_option_values where tenant_id=p_tenant_id and option_id=oid and id=vid and value_translations->>'en'=val->'value_translations'->>'en') then
        raise exception using errcode='P0001',message='ecommerce_new_combined_size_invalid';
      end if;
      value_map:=value_map||jsonb_build_object(val->>'id',vid);
      values_out:=values_out||jsonb_build_array(val||jsonb_build_object('id',vid,'code',code_out));
    end loop;
    options_out:=options_out||jsonb_build_array(o||jsonb_build_object('id',oid,'code',option_code,'client_id',oid,'values',values_out));
  end loop;
  for vr in select * from jsonb_array_elements(p_variants) loop
    rid:=(vr->>'id')::uuid;
    if exists(select 1 from public.ecommerce_product_variants where id=rid and (tenant_id<>p_tenant_id or product_id<>p_product_id)) then
      raise exception using errcode='P0001',message='ecommerce_identity_ownership_invalid';
    end if;
    if exists(select 1 from jsonb_array_elements_text(vr->'option_value_ids') x where not value_map ? x) then
      raise exception using errcode='P0001',message='ecommerce_variant_option_value_invalid';
    end if;
    select array_agg((value_map->>x)::uuid order by (value_map->>x)::uuid) into ids
      from jsonb_array_elements_text(vr->'option_value_ids') x;
    sig:=encode(extensions.digest(array_to_string(ids,','),'sha256'),'hex');
    if not exists(select 1 from public.ecommerce_product_variants where id=rid) then
      select id into candidate from public.ecommerce_product_variants
        where tenant_id=p_tenant_id and product_id=p_product_id and option_signature=sig;
      if candidate is not null then rid:=candidate; end if;
    end if;
    if p_preserve_inventory then
      select inventory_quantity into candidate_quantity from public.ecommerce_product_variants where tenant_id=p_tenant_id and product_id=p_product_id and id=rid;
      if found then vr:=jsonb_set(vr,'{inventory_quantity}',to_jsonb(candidate_quantity)); end if;
    end if;
    if sig=any(signatures) then raise exception using errcode='23505',message='VARIANT_COMBINATION_CONFLICT'; end if;
    if rid=any(seen) then raise exception using errcode='23505',message='CATALOG_UNIQUE_CONFLICT'; end if;
    signatures:=array_append(signatures,sig);
    seen:=array_append(seen,rid);
    variants_out:=variants_out||jsonb_build_array(vr||jsonb_build_object('id',rid,'option_value_ids',to_jsonb(ids)));
  end loop;
  -- Repeated mapped option/value IDs would otherwise overwrite each other.
  if (select count(*) from jsonb_array_elements(options_out))<>(select count(distinct x->>'id') from jsonb_array_elements(options_out)x) then
    raise exception using errcode='23505',message='OPTION_NAME_CONFLICT';
  end if;
  if (select count(*) from jsonb_array_elements(options_out)qo,jsonb_array_elements(qo->'values')qv)<>
     (select count(distinct qv->>'id') from jsonb_array_elements(options_out)qo,jsonb_array_elements(qo->'values')qv) then
    raise exception using errcode='23505',message='OPTION_VALUE_CONFLICT';
  end if;
  select coalesce(jsonb_agg(url order by url),'[]') into old_images from
  (select distinct url from public.ecommerce_product_variants v cross join lateral jsonb_array_elements_text(v.images) url where v.tenant_id=p_tenant_id and v.product_id=p_product_id) images;
  set constraints all deferred;
  perform public.save_ecommerce_product_aggregate_v3_core_safe(p_tenant_id,p_product_id,p_attributes,options_out,variants_out);
  select coalesce(jsonb_agg(url order by url),'[]') into new_images from
  (select distinct url from public.ecommerce_product_variants v cross join lateral jsonb_array_elements_text(v.images) url where v.tenant_id=p_tenant_id and v.product_id=p_product_id) images;
  perform public.refresh_ecommerce_product_assets_v3_safe(p_tenant_id,old_images,new_images);
  update public.ecommerce_products set status=status where tenant_id=p_tenant_id and id=p_product_id;
  -- Force final validation inside the RPC so PostgREST returns the constraint identity.
  set constraints all immediate;
  if p_include_catalog then return public.read_ecommerce_product_catalog_v3_safe(p_tenant_id,p_product_id); end if;
  return jsonb_build_object('product_id',p_product_id,'saved',true);
end $$;

create function public.update_ecommerce_product_v3_safe(
  p_tenant_id integer,p_product_id uuid,p_product jsonb,p_tag_ids jsonb,p_aggregate jsonb,p_category_ids jsonb default null
) returns jsonb language plpgsql security definer set search_path=public as $$
declare old_product public.ecommerce_products; new_product public.ecommerce_products; desired_status text; currency text; brand_name text; v_catalog_snapshot jsonb;
begin
  perform pg_advisory_xact_lock(hashtextextended('ecommerce-sku:'||p_tenant_id,0));
  select * into old_product from public.ecommerce_products where tenant_id=p_tenant_id and id=p_product_id for update;
  if not found then raise exception using errcode='P0002',message='ecommerce_product_not_found'; end if;
  if jsonb_typeof(p_product) is distinct from 'object' or jsonb_typeof(p_tag_ids) is distinct from 'array'
      or jsonb_array_length(p_tag_ids)>100 then raise exception using errcode='P0001',message='ecommerce_product_payload_invalid'; end if;
  if nullif(p_product->>'expected_catalog_version','') is not null or (not coalesce((p_product->>'preserve_inventory')::boolean,false) and nullif(p_product->>'expected_inventory_version','') is not null) then
    v_catalog_snapshot:=public.read_ecommerce_product_catalog_v3_safe(p_tenant_id,p_product_id);
  end if;
  if nullif(p_product->>'expected_catalog_version','') is not null and p_product->>'expected_catalog_version' is distinct from v_catalog_snapshot->>'catalog_version' then
    raise exception using errcode='P0001',message='CATALOG_CHANGED_CONFLICT';
  end if;
  if not coalesce((p_product->>'preserve_inventory')::boolean,false) and nullif(p_product->>'expected_inventory_version','') is not null and p_product->>'expected_inventory_version' is distinct from v_catalog_snapshot->>'inventory_version' then
    raise exception using errcode='P0001',message='CATALOG_CHANGED_CONFLICT';
  end if;
  if p_category_ids is null then
    if p_product ? 'category_id' then p_category_ids:=case when p_product->>'category_id' is null then '[]'::jsonb else jsonb_build_array(p_product->>'category_id') end;
    else select coalesce(jsonb_agg(category_id order by sort_order,category_id),'[]') into p_category_ids from public.ecommerce_product_categories where tenant_id=p_tenant_id and product_id=p_product_id; end if;
  end if;
  if jsonb_typeof(p_category_ids) is distinct from 'array' or jsonb_array_length(p_category_ids)>20 then raise exception using errcode='P0001',message='ecommerce_product_categories_invalid'; end if;
  new_product:=jsonb_populate_record(old_product,p_product);
  new_product.category_id:=nullif(p_category_ids->>0,'')::uuid;
  if coalesce((p_product->>'preserve_inventory')::boolean,false) then new_product.inventory_quantity:=old_product.inventory_quantity; end if;
  brand_name:='';
  if new_product.brand_id is not null then
    select name into brand_name from public.ecommerce_brands where tenant_id=p_tenant_id and id=new_product.brand_id;
    if not found then raise exception using errcode='23503',message='ecommerce_brand_reference_invalid'; end if;
  end if;
  new_product.brand:=brand_name;
  select ecommerce_currency into currency from public.website_settings where tenant_id=p_tenant_id;
  if currency is not null then new_product.currency:=currency; end if;
  -- Category and tag ownership is also enforced by composite tenant FKs.
  desired_status:=new_product.status;
  set constraints all deferred;
  update public.ecommerce_products set
    category_id=new_product.category_id,
    sku=new_product.sku,
    barcode=new_product.barcode,
    slug=new_product.slug,
    translations=new_product.translations,
    product_type=new_product.product_type,
    brand_id=new_product.brand_id,brand=new_product.brand,
    price=new_product.price,
    compare_at_price=new_product.compare_at_price,
    cost_price=new_product.cost_price,
    currency=new_product.currency,
    track_inventory=new_product.track_inventory,
    inventory_quantity=new_product.inventory_quantity,
    low_stock_threshold=new_product.low_stock_threshold,
    allow_backorder=new_product.allow_backorder,
    images=new_product.images,
    weight=new_product.weight,
    weight_unit=new_product.weight_unit,
    requires_shipping=new_product.requires_shipping,
    taxable=new_product.taxable,
    seo_title=new_product.seo_title,
    seo_description=new_product.seo_description,status=case when p_aggregate is null then desired_status else 'draft' end
    where tenant_id=p_tenant_id and id=p_product_id;
  delete from public.ecommerce_product_categories where tenant_id=p_tenant_id and product_id=p_product_id;
  insert into public.ecommerce_product_categories(tenant_id,product_id,category_id,sort_order)
    select p_tenant_id,p_product_id,x::uuid,min(ord)-1 from jsonb_array_elements_text(p_category_ids) with ordinality c(x,ord) group by x;
  delete from public.ecommerce_product_tags where tenant_id=p_tenant_id and product_id=p_product_id;
  insert into public.ecommerce_product_tags(tenant_id,product_id,tag_id)
    select distinct p_tenant_id,p_product_id,x::uuid from jsonb_array_elements_text(p_tag_ids)x;
  if p_aggregate is not null then
    perform public.save_ecommerce_product_aggregate_v3_safe(p_tenant_id,p_product_id,
      p_aggregate->'attributes',p_aggregate->'options',p_aggregate->'variants',null,false,null,coalesce((p_product->>'preserve_inventory')::boolean,false));
  end if;
  update public.ecommerce_products set status=desired_status where tenant_id=p_tenant_id and id=p_product_id returning * into new_product;
  perform public.refresh_ecommerce_product_assets_v3_safe(p_tenant_id,old_product.images,new_product.images);
  set constraints all immediate;
  return public.read_ecommerce_product_catalog_v3_safe(p_tenant_id,p_product_id);
end $$;

create function public.create_ecommerce_product_v3_safe(p_tenant_id integer,p_product jsonb,p_tag_ids jsonb,p_aggregate jsonb,p_user_id integer,p_category_ids jsonb default null,p_product_id uuid default null)
returns jsonb language plpgsql security definer set search_path=public as $$
declare pid uuid:=coalesce(p_product_id,gen_random_uuid());
begin
  perform pg_advisory_xact_lock(hashtextextended('ecommerce-sku:'||p_tenant_id,0));
  set constraints all deferred;
  insert into public.ecommerce_products(id,tenant_id,sku,slug,translations,status,created_by)
    values(pid,p_tenant_id,p_product->>'sku',p_product->>'slug',p_product->'translations','draft',p_user_id);
  return public.update_ecommerce_product_v3_safe(p_tenant_id,pid,p_product,p_tag_ids,p_aggregate,p_category_ids);
end $$;
revoke all on function public.create_ecommerce_product_v3_safe(integer,jsonb,jsonb,jsonb,integer,jsonb,uuid) from public,anon,authenticated;
grant execute on function public.create_ecommerce_product_v3_safe(integer,jsonb,jsonb,jsonb,integer,jsonb,uuid) to service_role;

revoke all on function public.save_ecommerce_product_aggregate_v3_core_safe(integer,uuid,jsonb,jsonb,jsonb) from public,anon,authenticated,service_role;

revoke all on function public.save_ecommerce_product_aggregate_v3_safe(integer,uuid,jsonb,jsonb,jsonb,text,boolean,text,boolean) from public,anon,authenticated;
grant execute on function public.save_ecommerce_product_aggregate_v3_safe(integer,uuid,jsonb,jsonb,jsonb,text,boolean,text,boolean) to service_role;

revoke all on function public.update_ecommerce_product_v3_safe(integer,uuid,jsonb,jsonb,jsonb,jsonb) from public,anon,authenticated;
grant execute on function public.update_ecommerce_product_v3_safe(integer,uuid,jsonb,jsonb,jsonb,jsonb) to service_role;

-- Current schema112 permits deletion only where historical FKs allow it.
-- Delete owned children in dependency order; any history conflict rolls all back.
create function public.delete_ecommerce_product_v3_safe(p_tenant_id integer,p_product_id uuid)
returns void language plpgsql security definer set search_path=public as $$
declare previous_images jsonb; begin
 perform pg_advisory_xact_lock(hashtextextended('ecommerce-sku:'||p_tenant_id,0));
 perform 1 from public.ecommerce_products where tenant_id=p_tenant_id and id=p_product_id for update;
 if not found then raise exception using errcode='P0002',message='ecommerce_product_not_found'; end if;
 select coalesce(jsonb_agg(distinct url),'[]') into previous_images from (
  select url from public.ecommerce_products p cross join lateral jsonb_array_elements_text(p.images) url where p.tenant_id=p_tenant_id and p.id=p_product_id
  union select url from public.ecommerce_product_variants v cross join lateral jsonb_array_elements_text(v.images) url where v.tenant_id=p_tenant_id and v.product_id=p_product_id
 ) images;
 delete from public.ecommerce_product_variants where tenant_id=p_tenant_id and product_id=p_product_id;
 delete from public.ecommerce_product_option_values where tenant_id=p_tenant_id and product_id=p_product_id;
 delete from public.ecommerce_product_options where tenant_id=p_tenant_id and product_id=p_product_id;
 delete from public.ecommerce_products where tenant_id=p_tenant_id and id=p_product_id;
 perform public.refresh_ecommerce_product_assets_v3_safe(p_tenant_id,previous_images,'[]');
end $$;
revoke all on function public.delete_ecommerce_product_v3_safe(integer,uuid) from public,anon,authenticated;
grant execute on function public.delete_ecommerce_product_v3_safe(integer,uuid) to service_role;

do $$ declare v_schema_version public.application_schema_state.schema_version%TYPE; begin
  select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
  if v_schema_version is null then raise exception using errcode='P0001',message='migration_116_schema_state_missing'; end if;
  if v_schema_version<>115 then raise exception using errcode='P0001',message=format('migration_116_expected_schema_115_got_%s',v_schema_version); end if;
  update public.application_schema_state set schema_version=116,applied_at=now() where contract_key = 'core';
end $$;
notify pgrst,'reload schema';
commit;
