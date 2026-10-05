-- Synthetic fixtures only. Run against the disposable rehearsal database.
create function pg_temp.uid(v text) returns uuid language sql immutable as $$select md5(v)::uuid$$;
create temporary table test_assertions(label text);
create function pg_temp.assert_true(v boolean,label text) returns void language plpgsql as $$
begin if v is distinct from true then raise exception 'assertion_failed:%',label; end if; insert into test_assertions values(label); end $$;
insert into public.tenants(tenant_id,brand_name,owner_name) values(1161,'Rehearsal One','Owner'),(1162,'Rehearsal Two','Owner');
insert into public.ecommerce_categories(id,tenant_id,slug,translations) values
(pg_temp.uid('cat1'),1161,'cat1','{"en":{"name":"One"}}'),(pg_temp.uid('cat2'),1161,'cat2','{"en":{"name":"Two"}}'),(pg_temp.uid('foreigncat'),1162,'cat1','{"en":{"name":"Foreign"}}');
insert into public.ecommerce_tags(id,tenant_id,slug,translations) values
(pg_temp.uid('tag1'),1161,'tag1','{"en":{"name":"One"}}'),(pg_temp.uid('tag2'),1161,'tag2','{"en":{"name":"Two"}}'),(pg_temp.uid('foreigntag'),1162,'tag1','{"en":{"name":"Foreign"}}');
insert into public.ecommerce_products(id,tenant_id,sku,slug,translations,status,category_id) values
(pg_temp.uid('product'),1161,'BASE','product','{"en":{"name":"Product"}}','draft',pg_temp.uid('cat1')),
(pg_temp.uid('other'),1161,'OTHER','other','{"en":{"name":"Other"}}','draft',null),
(pg_temp.uid('foreign'),1162,'BASE','product','{"en":{"name":"Foreign"}}','draft',null);
insert into public.ecommerce_product_tags values(1161,pg_temp.uid('product'),pg_temp.uid('tag1'),now());
create temporary table test_payload(a jsonb);
insert into test_payload select jsonb_build_object('attributes','[]'::jsonb,'options',jsonb_build_array(
 jsonb_build_object('id',pg_temp.uid('size'),'client_id',pg_temp.uid('size'),'code','size','name_translations',jsonb_build_object('en','Size','ar','المقاس'),'normalized_name','size','display_type','text','values',jsonb_build_array(
  jsonb_build_object('id',pg_temp.uid('36'),'code','variant-1-36','value_translations',jsonb_build_object('en','36'),'normalized_value','36','sort_order',0),
  jsonb_build_object('id',pg_temp.uid('37'),'code','variant-2-37','value_translations',jsonb_build_object('en','37'),'normalized_value','37','sort_order',1))),
 jsonb_build_object('id',pg_temp.uid('color'),'client_id',pg_temp.uid('color'),'code','color','name_translations',jsonb_build_object('en','Color'),'normalized_name','color','display_type','color','values',jsonb_build_array(
  jsonb_build_object('id',pg_temp.uid('red'),'code','color-1-red','value_translations',jsonb_build_object('en','Red'),'normalized_value','red','color_hex','#FF0000','sort_order',0),
  jsonb_build_object('id',pg_temp.uid('blue'),'code','color-2-blue','value_translations',jsonb_build_object('en','Blue'),'normalized_value','blue','color_hex','#0000FF','sort_order',1)))
 ),'variants',jsonb_build_array(
 jsonb_build_object('id',pg_temp.uid('v36'),'sku','SKU36','inventory_quantity',10,'option_value_ids',jsonb_build_array(pg_temp.uid('36'),pg_temp.uid('red'))),
 jsonb_build_object('id',pg_temp.uid('v37'),'sku','SKU37','inventory_quantity',20,'option_value_ids',jsonb_build_array(pg_temp.uid('37'),pg_temp.uid('red')))));
create function pg_temp.save(a jsonb) returns jsonb language sql as $$
 select public.save_ecommerce_product_aggregate_v3_safe(1161,pg_temp.uid('product'),a->'attributes',a->'options',a->'variants'); $$;
create function pg_temp.snapshot() returns jsonb language sql as $$
 select public.read_ecommerce_product_catalog_v3_safe(1161,pg_temp.uid('product'))||jsonb_build_object('_registry',(select coalesce(jsonb_agg(to_jsonb(a) order by a.id),'[]') from public.builder_assets a where tenant_id=1161));
$$;
create function pg_temp.expect_conflict(a jsonb,label text, expected_constraint text default null,full_save boolean default false)
returns void language plpgsql as $$
declare before jsonb:=pg_temp.snapshot(); caught boolean:=false; con text; msg text;
begin
 begin
  if full_save then
   perform public.update_ecommerce_product_v3_safe(1161,pg_temp.uid('product'),jsonb_build_object('price',999,'category_id',pg_temp.uid('cat2'),'translations',jsonb_build_object('en',jsonb_build_object('name','Changed'))),jsonb_build_array(pg_temp.uid('tag2')),a);
  else perform pg_temp.save(a); end if;
 exception when unique_violation then
  caught:=true; get stacked diagnostics con=constraint_name,msg=message_text;
  if expected_constraint is not null then
   perform pg_temp.assert_true(con=expected_constraint or msg=expected_constraint,label||':constraint:'||coalesce(con,msg));
  end if;
 end;
 perform pg_temp.assert_true(caught,label||':rejected');
 perform pg_temp.assert_true(pg_temp.snapshot()=before,label||':rollback');
 raise notice 'PASS % [%]',label,con;
end $$;
select pg_temp.save(a) is not null from test_payload;
-- Same request repeatedly, quantity and SKU edits retain all IDs and links.
do $$ declare a jsonb; b jsonb; before jsonb; begin
 select t.a into a from test_payload t;
 before:=pg_temp.snapshot(); perform pg_temp.save(a);
 perform pg_temp.assert_true((select count(*)=2 from ecommerce_product_variants where id in (pg_temp.uid('v36'),pg_temp.uid('v37'))),'unchanged_variant_ids');
 perform pg_temp.assert_true((select count(*)=4 from ecommerce_product_option_values where product_id=pg_temp.uid('product') and active),'unchanged_value_ids');
 a:=jsonb_set(a,'{variants,0,inventory_quantity}','12'); perform pg_temp.save(a);
 perform pg_temp.assert_true((select inventory_quantity=12 from ecommerce_product_variants where id=pg_temp.uid('v36')),'quantity_edit');
 a:=jsonb_set(a,'{variants,0,sku}','"SKU36-NEW"'); perform pg_temp.save(a);
 perform pg_temp.assert_true((select sku='SKU36-NEW' from ecommerce_product_variants where id=pg_temp.uid('v36')),'sku_edit');
 -- Final-valid SKU swap and semantic value/code swap must not depend on loop order.
 a:=jsonb_set(a,'{variants,0,sku}','"SKU37"'); a:=jsonb_set(a,'{variants,1,sku}','"SKU36-NEW"'); perform pg_temp.save(a);
 a:=jsonb_set(a,'{options,0,values,0,code}','"variant-2-37"'); a:=jsonb_set(a,'{options,0,values,1,code}','"variant-1-36"');
 a:=jsonb_set(a,'{options,0,values,0,value_translations,en}','"37"'); a:=jsonb_set(a,'{options,0,values,1,value_translations,en}','"36"');
 a:=jsonb_set(a,'{options,0,values,0,normalized_value}','"37"'); a:=jsonb_set(a,'{options,0,values,1,normalized_value}','"36"'); perform pg_temp.save(a);
 -- Swap option codes/names, including a display metadata update.
 a:=jsonb_set(a,'{options,0,code}','"color"'); a:=jsonb_set(a,'{options,1,code}','"size"');
 a:=jsonb_set(a,'{options,0,name_translations,en}','"Color"'); a:=jsonb_set(a,'{options,1,name_translations,en}','"Size"');
 a:=jsonb_set(a,'{options,0,normalized_name}','"color"'); a:=jsonb_set(a,'{options,1,normalized_name}','"size"'); perform pg_temp.save(a);
 select t.a into a from test_payload t; perform pg_temp.save(a);
 -- Cross-table SKU swap is valid only in its final transaction state.
 a:=jsonb_set(a,'{variants,0,sku}','"BASE"');
 perform public.update_ecommerce_product_v3_safe(1161,pg_temp.uid('product'),'{"sku":"SKU36"}',jsonb_build_array(pg_temp.uid('tag1')),a);
 perform pg_temp.assert_true((select sku='BASE' from ecommerce_product_variants where id=pg_temp.uid('v36')),'cross_table_sku_swap');
 select t.a into a from test_payload t;
 perform public.update_ecommerce_product_v3_safe(1161,pg_temp.uid('product'),'{"sku":"BASE"}',jsonb_build_array(pg_temp.uid('tag1')),a);
 -- Retained variant IDs can exchange their combinations without transient collisions.
 b:=jsonb_set(a,'{variants,0,option_value_ids}',a#>'{variants,1,option_value_ids}');
 b:=jsonb_set(b,'{variants,1,option_value_ids}',a#>'{variants,0,option_value_ids}'); perform pg_temp.save(b);
 perform pg_temp.assert_true(exists(select 1 from ecommerce_variant_option_values where variant_id=pg_temp.uid('v36') and option_value_id=pg_temp.uid('37')),'retained_combination_swap');
 perform pg_temp.save(a);
 -- Generic three-dimensional options retain identities when reordered.
 b:=jsonb_set(a,'{options}',(a->'options')||jsonb_build_array(jsonb_build_object('id',pg_temp.uid('finish'),'client_id',pg_temp.uid('finish'),'code','finish','name_translations',jsonb_build_object('en','Finish'),'normalized_name','finish','sort_order',2,'values',jsonb_build_array(jsonb_build_object('id',pg_temp.uid('matte'),'code','matte','value_translations',jsonb_build_object('en','Matte'),'normalized_value','matte')))));
 b:=jsonb_set(b,'{variants,0,option_value_ids}',(b#>'{variants,0,option_value_ids}')||jsonb_build_array(pg_temp.uid('matte')));
 b:=jsonb_set(b,'{variants,1,option_value_ids}',(b#>'{variants,1,option_value_ids}')||jsonb_build_array(pg_temp.uid('matte'))); perform pg_temp.save(b);
 perform pg_temp.assert_true((select count(*)=3 from ecommerce_variant_option_values where variant_id=pg_temp.uid('v36')),'generic_three_dimensions');
 b:=jsonb_set(b,'{options,2,sort_order}','0');b:=jsonb_set(b,'{options,0,sort_order}','2');perform pg_temp.save(b);
 perform pg_temp.assert_true((select id=pg_temp.uid('finish') and sort_order=0 from ecommerce_product_options where id=pg_temp.uid('finish')),'generic_option_reorder_identity');
 perform pg_temp.save(a);
 -- Reorder sizes/colors with the same immutable identities and codes.
 a:=jsonb_set(a,'{options,0,values,0,sort_order}','1'); a:=jsonb_set(a,'{options,0,values,1,sort_order}','0');
 a:=jsonb_set(a,'{options,1,values,0,sort_order}','1'); a:=jsonb_set(a,'{options,1,values,1,sort_order}','0'); perform pg_temp.save(a);
 perform pg_temp.assert_true((select code='variant-1-36' and sort_order=1 from ecommerce_product_option_values where id=pg_temp.uid('36')),'reorder_size');
 perform pg_temp.assert_true((select code='color-1-red' and sort_order=1 from ecommerce_product_option_values where id=pg_temp.uid('red')),'reorder_color');
 select t.a into a from test_payload t;
 -- Remove/recreate a size and its variant using NEW client UUIDs. Old history is canonical.
 b:=jsonb_set(a,'{options,0,values}',jsonb_build_array(a#>'{options,0,values,1}'));
 b:=jsonb_set(b,'{variants}',jsonb_build_array(a#>'{variants,1}')); perform pg_temp.save(b);
 perform pg_temp.assert_true((select not active from ecommerce_product_variants where id=pg_temp.uid('v36')),'archive_variant');
 perform pg_temp.assert_true((select not active from ecommerce_product_option_values where id=pg_temp.uid('36')),'archive_size');
 perform pg_temp.assert_true((select count(*)=2 from ecommerce_variant_option_values where variant_id=pg_temp.uid('v36')),'historical_links_retained');
 b:=jsonb_set(a,'{options,0,values,0,id}',to_jsonb(pg_temp.uid('new36')));
 b:=jsonb_set(b,'{variants,0,id}',to_jsonb(pg_temp.uid('newv36')));
 b:=jsonb_set(b,'{variants,0,option_value_ids,0}',to_jsonb(pg_temp.uid('new36')));
 perform pg_temp.save(b); perform pg_temp.save(b);
 perform pg_temp.assert_true((select active from ecommerce_product_option_values where id=pg_temp.uid('36')),'reuse_size');
 perform pg_temp.assert_true((select active from ecommerce_product_variants where id=pg_temp.uid('v36')),'reuse_variant');
 perform pg_temp.assert_true(not exists(select 1 from ecommerce_product_variants where id=pg_temp.uid('newv36')),'no_identity_churn');
 -- Remove/recreate shared color, including values without historical variant references.
 b:=jsonb_set(a,'{options,1,values}',jsonb_build_array(a#>'{options,1,values,1}')); b:=jsonb_set(b,'{variants}','[]'); perform pg_temp.save(b);
 b:=jsonb_set(a,'{options,1,values,0,id}',to_jsonb(pg_temp.uid('newred')));
 b:=jsonb_set(b,'{variants,0,option_value_ids,1}',to_jsonb(pg_temp.uid('newred')));
 b:=jsonb_set(b,'{variants,1,option_value_ids,1}',to_jsonb(pg_temp.uid('newred'))); perform pg_temp.save(b);
 perform pg_temp.assert_true((select count(*)=2 from ecommerce_variant_option_values where option_value_id=pg_temp.uid('red')),'shared_color_reused');
 -- Old API normalization used JSON object key order. Prefer translated labels
 -- when reusing new IDs so bilingual historical rows remain canonical.
 update ecommerce_product_option_values set normalized_value='أحمر' where id=pg_temp.uid('red');
 perform pg_temp.save(b);
 perform pg_temp.assert_true((select normalized_value='red' and active from ecommerce_product_option_values where id=pg_temp.uid('red')),'translated_history_canonical_reuse');
 raise notice 'PASS identity_quantity_sku_swaps_reorders_archival_shared_color';
end $$;
-- Constraint diagnostics are checked against PostgreSQL's actual identities.
select conname from pg_constraint where contype='u' and conrelid in ('ecommerce_product_options'::regclass,'ecommerce_product_option_values'::regclass,'ecommerce_product_variants'::regclass) order by conname;
do $$ declare a jsonb; b jsonb; begin
 select t.a into a from test_payload t;
 b:=jsonb_set(a,'{variants,1,sku}',a#>'{variants,0,sku}');
 perform pg_temp.expect_conflict(b,'duplicate_variant_sku','ecommerce_product_variants_tenant_id_sku_key');
 perform pg_temp.expect_conflict(b,'full_save_nested_atomicity','ecommerce_product_variants_tenant_id_sku_key',true);
 b:=jsonb_set(a,'{variants,0,sku}','"base"'); perform pg_temp.expect_conflict(b,'cross_catalog_sku','ecommerce_sku_conflict');
 b:=jsonb_set(a,'{variants,1,option_value_ids}',a#>'{variants,0,option_value_ids}'); perform pg_temp.expect_conflict(b,'duplicate_combination');
 b:=jsonb_set(a,'{options,0,values,1,code}',a#>'{options,0,values,0,code}'); perform pg_temp.expect_conflict(b,'duplicate_value_code');
 b:=jsonb_set(a,'{options,0,values,1,normalized_value}',a#>'{options,0,values,0,normalized_value}'); perform pg_temp.expect_conflict(b,'duplicate_value');
 b:=jsonb_set(a,'{options,1,code}',a#>'{options,0,code}'); perform pg_temp.expect_conflict(b,'duplicate_option_code');
 b:=jsonb_set(a,'{options,1,normalized_name}',a#>'{options,0,normalized_name}'); perform pg_temp.expect_conflict(b,'duplicate_option_name');
 raise notice 'PASS conflicts_and_atomicity';
end $$;
-- Product SKU/slug and tenant-reference failures also roll back base row and links.
do $$ declare before jsonb:=pg_temp.snapshot(); key text; patch jsonb; caught boolean; con text; begin
 foreach key in array array['sku','slug','category_id','tag_id'] loop
  patch:=case key when 'sku' then '{"sku":"OTHER"}'::jsonb when 'slug' then '{"slug":"other"}'::jsonb
    when 'category_id' then jsonb_build_object('category_id',pg_temp.uid('foreigncat')) else '{}'::jsonb end;
  caught:=false;
  begin
   perform public.update_ecommerce_product_v3_safe(1161,pg_temp.uid('product'),patch,case when key='tag_id' then jsonb_build_array(pg_temp.uid('foreigntag')) else jsonb_build_array(pg_temp.uid('tag2')) end,null);
  exception when unique_violation or foreign_key_violation then caught:=true; get stacked diagnostics con=constraint_name;
  end;
  perform pg_temp.assert_true(caught,'product_conflict:'||key);
  perform pg_temp.assert_true(pg_temp.snapshot()=before,'product_rollback:'||key);
  raise notice 'PASS product_% [%]',key,con;
 end loop;
end $$;
-- Legacy combined history coexists with independent sizes. Rehydrated second save
-- and repeating a NEW-ID transformation both resolve to the same canonical rows.
do $$ declare a jsonb; b jsonb; before_links integer; begin
 select t.a into a from test_payload t;
 b:=jsonb_set(a,'{options,0,values}',jsonb_build_array(jsonb_build_object('id',pg_temp.uid('combined'),'code','combined','value_translations',jsonb_build_object('en','36 - 37'),'normalized_value','36 - 37')));
 b:=jsonb_set(b,'{variants}',jsonb_build_array(jsonb_build_object('id',pg_temp.uid('vcombined'),'sku','COMBINED','inventory_quantity',30,'option_value_ids',jsonb_build_array(pg_temp.uid('combined'),pg_temp.uid('red')))));
 perform pg_temp.save(b); perform pg_temp.save(a); perform pg_temp.save(a);
 perform pg_temp.assert_true((select not active from ecommerce_product_variants where id=pg_temp.uid('vcombined')),'combined_variant_archived');
 perform pg_temp.assert_true((select not active from ecommerce_product_option_values where id=pg_temp.uid('combined')),'combined_value_archived');
 perform pg_temp.assert_true((select count(*)=2 from ecommerce_variant_option_values where variant_id=pg_temp.uid('vcombined')),'combined_history_links');
 b:=jsonb_set(a,'{options,0,values,0,id}',to_jsonb(pg_temp.uid('split-new36')));
 b:=jsonb_set(b,'{options,0,values,1,id}',to_jsonb(pg_temp.uid('split-new37')));
 b:=jsonb_set(b,'{variants,0,id}',to_jsonb(pg_temp.uid('split-v36'))); b:=jsonb_set(b,'{variants,1,id}',to_jsonb(pg_temp.uid('split-v37')));
 b:=jsonb_set(b,'{variants,0,option_value_ids,0}',to_jsonb(pg_temp.uid('split-new36'))); b:=jsonb_set(b,'{variants,1,option_value_ids,0}',to_jsonb(pg_temp.uid('split-new37')));
 perform pg_temp.save(b); perform pg_temp.save(b);
 perform pg_temp.assert_true((select count(*)=3 from ecommerce_product_variants where product_id=pg_temp.uid('product')),'combined_idempotent');
 raise notice 'PASS combined_conversion_with_history';
end $$;
-- Foreign product IDs cannot be borrowed, and non-service callers cannot mutate.
do $$ declare a jsonb; before jsonb:=pg_temp.snapshot(); caught boolean:=false; begin
 select t.a into a from test_payload t;
 a:=jsonb_set(a,'{options,0,id}',to_jsonb(pg_temp.uid('color')));
 begin perform pg_temp.save(a); exception when raise_exception then caught:=true; end;
 perform pg_temp.assert_true(caught,'option_identity_ownership');
 perform pg_temp.assert_true(pg_temp.snapshot()=before,'ownership_rollback');
 perform pg_temp.assert_true(not has_function_privilege('authenticated','public.save_ecommerce_product_aggregate_v3_safe(integer,uuid,jsonb,jsonb,jsonb,text,boolean,text,boolean)','execute'),'authenticated_rpc_denied');
 perform pg_temp.assert_true(not has_function_privilege('service_role','public.save_ecommerce_product_aggregate_v3_core_safe(integer,uuid,jsonb,jsonb,jsonb)','execute'),'internal_core_denied');
 raise notice 'PASS ownership_and_privileges';
end $$;
select 'CATALOG_RECONCILIATION_REGRESSIONS PASS';
-- Real checkout allocation, archived option semantics, order history and restore.
insert into auth.users(id) values(pg_temp.uid('auth1161'));
insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status)
values(pg_temp.uid('auth1161'),'Owner','One','synthetic1161@example.invalid',1161,'active');
insert into public.website_settings(user_id,tenant_id,subdomain,ecommerce_currency)
select id,1161,'catalog-regression-1161','USD' from public.users where tenant_id=1161;
insert into public.ecommerce_tenant_service_areas(tenant_id,service_area_id,enabled)
values(1161,'95000000-0000-0000-0000-000000000001',true);
insert into public.ecommerce_delivery_pricing(tenant_id,service_area_id,price) values(1161,'95000000-0000-0000-0000-000000000001',0);

insert into public.builder_assets(id,tenant_id,storage_key,managed_filename,mime_type,size_bytes,sha256)
select pg_temp.uid('asset'||n),1161,'tenant_1161/builder_assets/'||repeat(n,32)||'.png',repeat(n,32)||'.png','image/png',0,repeat('0',64) from unnest(array['a','b','c','d']) n;
do $$ declare a jsonb; before jsonb; v_order_id uuid; qty integer; result jsonb; caught boolean:=false; begin
 select t.a into a from test_payload t;
 a:=jsonb_set(a,'{variants,0,images}',jsonb_build_array('/uploads/tenant_1161/builder_assets/'||repeat('b',32)||'.png'));
 perform public.update_ecommerce_product_v3_safe(1161,pg_temp.uid('product'),jsonb_build_object('status','active','price',20,'images',jsonb_build_array('/uploads/tenant_1161/builder_assets/'||repeat('a',32)||'.png')),jsonb_build_array(pg_temp.uid('tag1')),a);
 perform pg_temp.assert_true((select count(*)=2 from builder_assets where tenant_id=1161 and status='active'),'asset_registry_activation');
 select inventory_quantity into qty from ecommerce_product_variants where id=pg_temp.uid('v36');
 result:=public.create_ecommerce_order_safe(jsonb_build_object('tenant_id',1161,'payment_method','cash_on_delivery','customer_name','Synthetic Buyer','email','synthetic@example.invalid','phone','+970590000000','street','Test Street','service_area_id','95000000-0000-0000-0000-000000000001','items',jsonb_build_array(jsonb_build_object('product_id',pg_temp.uid('product'),'variant_id',pg_temp.uid('v36'),'quantity',1))),repeat('d',64),repeat('e',64),repeat('f',64));
 select i.order_id into v_order_id from ecommerce_order_items i where i.tenant_id=1161 and i.variant_id=pg_temp.uid('v36');
 perform pg_temp.assert_true((select inventory_quantity=qty-1 from ecommerce_product_variants where id=pg_temp.uid('v36')),'checkout_allocation');
 perform pg_temp.assert_true((select count(*)=1 from ecommerce_inventory_movements m where m.tenant_id=1161 and m.variant_id=pg_temp.uid('v36') and quantity_delta=-1),'checkout_movement');
 before:=(select to_jsonb(i) from ecommerce_order_items i where i.order_id=v_order_id);
 -- Archive every option and variant: this is now a valid simple active product.
 perform public.update_ecommerce_product_v3_safe(1161,pg_temp.uid('product'),'{"images":[],"inventory_quantity":2}',jsonb_build_array(pg_temp.uid('tag1')),'{"attributes":[],"options":[],"variants":[]}');
 perform pg_temp.assert_true((select count(*)=0 from ecommerce_current_product_options where tenant_id=1161 and product_id=pg_temp.uid('product')),'omitted_options_are_history');
 perform pg_temp.assert_true((select to_jsonb(i)=before from ecommerce_order_items i where i.order_id=v_order_id),'order_snapshot_preserved');
 perform pg_temp.assert_true((select status='active' from builder_assets where id=pg_temp.uid('asseta')),'historical_product_media_retained');
 perform pg_temp.assert_true((select status='active' from builder_assets where id=pg_temp.uid('assetb')),'historical_variant_media_retained');
 perform public.restore_ecommerce_order_inventory_safe(1161,v_order_id,'cancelled',repeat('1',64));
 perform public.restore_ecommerce_order_inventory_safe(1161,v_order_id,'cancelled',repeat('1',64));
 perform pg_temp.assert_true((select inventory_quantity=qty from ecommerce_product_variants where id=pg_temp.uid('v36')),'archived_variant_restore_exactly_once');
 -- Simple checkout ignores archived options; base stock allocation is unaffected.
 perform public.create_ecommerce_order_safe(jsonb_build_object('tenant_id',1161,'payment_method','cash_on_delivery','customer_name','Synthetic Buyer','email','synthetic@example.invalid','phone','+970590000000','street','Test Street','service_area_id','95000000-0000-0000-0000-000000000001','items',jsonb_build_array(jsonb_build_object('product_id',pg_temp.uid('product'),'quantity',1))),repeat('2',64),repeat('3',64),repeat('4',64));
 perform pg_temp.assert_true((select inventory_quantity=1 from ecommerce_products where id=pg_temp.uid('product')),'simple_checkout_after_archival');
 -- Reactivate the same option/value/variant identities and publication atomically.
 perform public.update_ecommerce_product_v3_safe(1161,pg_temp.uid('product'),'{"status":"active"}',jsonb_build_array(pg_temp.uid('tag1')),a);
 perform pg_temp.assert_true((select count(*)=2 from ecommerce_current_product_options where tenant_id=1161 and product_id=pg_temp.uid('product')),'options_reactivated');
 -- Unreferenced removal gets retention; registry must also roll back on a conflict.
 perform public.update_ecommerce_product_v3_safe(1161,pg_temp.uid('product'),jsonb_build_object('images',jsonb_build_array('/uploads/tenant_1161/builder_assets/'||repeat('c',32)||'.png')),jsonb_build_array(pg_temp.uid('tag1')),a);
 a:=jsonb_set(a,'{variants,1,sku}',a#>'{variants,0,sku}');
 a:=jsonb_set(a,'{variants,1,images}',jsonb_build_array('/uploads/tenant_1161/builder_assets/'||repeat('d',32)||'.png'));
 perform pg_temp.expect_conflict(a,'registry_nested_atomicity','ecommerce_product_variants_tenant_id_sku_key',true);
 perform public.update_ecommerce_product_v3_safe(1161,pg_temp.uid('product'),'{"images":[]}',jsonb_build_array(pg_temp.uid('tag1')),null);
 perform pg_temp.assert_true((select status='unreferenced' and retention_until>now() from builder_assets where id=pg_temp.uid('assetc')),'unreferenced_media_retention');
 -- Database publication rejects active variants selecting inactive values.
 select t.a into a from test_payload t; a:=jsonb_set(a,'{options,0,values,0,active}','false');
 begin perform pg_temp.save(a); exception when raise_exception then caught:=true; end;
 perform pg_temp.assert_true(caught,'inactive_value_publication_rejected');
 raise notice 'PASS checkout_inventory_orders_assets_option_archival_publication';
end $$;
select 'CHECKOUT_INVENTORY_ASSETS_REGRESSIONS PASS';

-- Snapshot version prevents a stale editor from restoring stock allocated by checkout.
do $$ declare a jsonb; version text; inventory_version text; before jsonb; caught boolean:=false; msg text; begin
 select t.a into a from test_payload t;
 version:=public.read_ecommerce_product_catalog_v3_safe(1161,pg_temp.uid('product'))->>'catalog_version';
 inventory_version:=public.read_ecommerce_product_catalog_v3_safe(1161,pg_temp.uid('product'))->>'inventory_version';
 perform pg_temp.assert_true((select p->>'catalog_version'=version from jsonb_array_elements(public.read_ecommerce_catalog_v3_safe(1161)->'products')p where p->>'id'=pg_temp.uid('product')::text),'initial_catalog_version_present');
 perform public.create_ecommerce_order_safe(jsonb_build_object('tenant_id',1161,'payment_method','cash_on_delivery','customer_name','Synthetic Buyer','email','synthetic@example.invalid','phone','+970590000000','street','Test Street','service_area_id','95000000-0000-0000-0000-000000000001','items',jsonb_build_array(jsonb_build_object('product_id',pg_temp.uid('product'),'variant_id',pg_temp.uid('v36'),'quantity',1))),repeat('5',64),repeat('6',64),repeat('7',64));
 before:=pg_temp.snapshot();
 begin perform public.save_ecommerce_product_aggregate_v3_safe(1161,pg_temp.uid('product'),null,a->'options',a->'variants',version,true,inventory_version,false);
 exception when raise_exception then caught:=true; get stacked diagnostics msg=message_text; end;
 perform pg_temp.assert_true(caught and msg='CATALOG_CHANGED_CONFLICT','stale_variant_edit_rejected');
 perform pg_temp.assert_true(pg_temp.snapshot()=before,'stale_variant_edit_rollback');
 caught:=false;
 begin perform public.update_ecommerce_product_v3_safe(1161,pg_temp.uid('product'),jsonb_build_object('price',99,'expected_catalog_version',version,'expected_inventory_version',inventory_version),jsonb_build_array(pg_temp.uid('tag2')),a);
 exception when raise_exception then caught:=true; get stacked diagnostics msg=message_text; end;
 perform pg_temp.assert_true(caught and msg='CATALOG_CHANGED_CONFLICT','stale_full_edit_rejected');
 perform pg_temp.assert_true(pg_temp.snapshot()=before,'stale_full_edit_rollback');
 -- A descriptive edit after checkout keeps current quantities and accepts the catalog version.
 perform public.update_ecommerce_product_v3_safe(1161,pg_temp.uid('product'),jsonb_build_object('price',21,'expected_catalog_version',version,'expected_inventory_version',inventory_version,'preserve_inventory',true),jsonb_build_array(pg_temp.uid('tag1')),a);
 perform pg_temp.assert_true((select inventory_quantity=(before->'variants'->0->>'inventory_quantity')::integer from ecommerce_product_variants where id=(before->'variants'->0->>'id')::uuid),'descriptive_edit_preserves_checkout_stock');
 -- Attribute-only full save preserves the other omitted nested components.
 perform public.update_ecommerce_product_v3_safe(1161,pg_temp.uid('product'),'{}',jsonb_build_array(pg_temp.uid('tag1')),'{"attributes":[],"options":null,"variants":null}');
 perform pg_temp.assert_true((select count(*)=2 from ecommerce_product_variants where product_id=pg_temp.uid('product') and active),'attribute_only_preserves_variants');
 -- Descriptive attribute timestamps/identity must be untouched by a variant-only save.
 insert into ecommerce_product_attributes(id,tenant_id,product_id,name_translations,value_translations,normalized_name)
 values(pg_temp.uid('material'),1161,pg_temp.uid('product'),' {"en":"Material"}',' {"en":"Cotton"}','material');
 before:=(select to_jsonb(t) from ecommerce_product_attributes t where id=pg_temp.uid('material'));
 perform public.save_ecommerce_product_aggregate_v3_safe(1161,pg_temp.uid('product'),null,a->'options',a->'variants');
 perform pg_temp.assert_true((select to_jsonb(t)=before from ecommerce_product_attributes t where id=pg_temp.uid('material')),'variant_only_preserves_attributes');
 perform pg_temp.assert_true((select count(*)=1 from jsonb_array_elements(public.read_ecommerce_catalog_v3_safe(1162)->'products')),'catalog_rpc_tenant_isolation');
end $$;
-- Current schema brands, categories and historical deletion restrictions.
insert into ecommerce_brands(id,tenant_id,name,slug) values
(pg_temp.uid('brand1'),1161,'Brand One','brand-one'),(pg_temp.uid('brand2'),1161,'Brand Two','brand-two'),(pg_temp.uid('foreignbrand'),1162,'Foreign Brand','foreign-brand');
do $$ declare a jsonb; before jsonb; caught boolean:=false; begin
 select t.a into a from test_payload t;
 perform public.update_ecommerce_product_v3_safe(1161,pg_temp.uid('product'),jsonb_build_object('brand_id',pg_temp.uid('brand1'),'brand','Untrusted name'),jsonb_build_array(pg_temp.uid('tag1')),a,jsonb_build_array(pg_temp.uid('cat1'),pg_temp.uid('cat2')));
 perform pg_temp.assert_true((select brand_id=pg_temp.uid('brand1') and brand='Brand One' and category_id=pg_temp.uid('cat1') from ecommerce_products where id=pg_temp.uid('product')),'brand_and_primary_category');
 perform pg_temp.assert_true((select category_ids=jsonb_build_array(pg_temp.uid('cat1'),pg_temp.uid('cat2')) from jsonb_to_record(public.read_ecommerce_product_catalog_v3_safe(1161,pg_temp.uid('product'))) as x(category_ids jsonb)),'ordered_multi_categories');
 before:=pg_temp.snapshot();a:=jsonb_set(a,'{variants,1,sku}',a#>'{variants,0,sku}');
 begin perform public.update_ecommerce_product_v3_safe(1161,pg_temp.uid('product'),jsonb_build_object('brand_id',pg_temp.uid('brand2'),'price',999),jsonb_build_array(pg_temp.uid('tag2')),a,jsonb_build_array(pg_temp.uid('cat2'),pg_temp.uid('cat1')));
 exception when unique_violation then caught:=true; end;
 perform pg_temp.assert_true(caught and before=pg_temp.snapshot(),'brand_categories_tags_nested_rollback');
 caught:=false;
 begin perform public.update_ecommerce_product_v3_safe(1161,pg_temp.uid('product'),jsonb_build_object('brand_id',pg_temp.uid('foreignbrand')),jsonb_build_array(pg_temp.uid('tag1')),null,'[]');
 exception when foreign_key_violation then caught:=true; end;
 perform pg_temp.assert_true(caught and before=pg_temp.snapshot(),'brand_tenant_isolation');
 caught:=false;
 begin perform public.delete_ecommerce_product_v3_safe(1161,pg_temp.uid('product')); exception when foreign_key_violation then caught:=true; end;
 perform pg_temp.assert_true(caught and before=pg_temp.snapshot(),'historical_product_deletion_restricted');
end $$;
select 'DATABASE_ASSERTIONS_PASS:'||count(*) from test_assertions;
-- SQL-only timings: do not equate these to real PostgREST/network latency.
create temporary table benchmark(label text, ms numeric);
do $$ declare a jsonb; bad jsonb; pid uuid:=pg_temp.uid('benchmark-small'); failed_pid uuid:=pg_temp.uid('failed-create'); started timestamptz; key text; caught boolean:=false; begin
 select t.a into a from test_payload t;
 foreach key in array array['size','color','36','37','red','blue','v36','v37'] loop
  a:=replace(a::text,pg_temp.uid(key)::text,pg_temp.uid('benchmark-'||key)::text)::jsonb;
 end loop;
 a:=replace(replace(a::text,'SKU36','BENCH-small-36'),'SKU37','BENCH-small-37')::jsonb;
 bad:=jsonb_set(a,'{variants,1,sku}',a#>'{variants,0,sku}');
 begin
  perform public.create_ecommerce_product_v3_safe(1161,jsonb_build_object('sku','FAILED-CREATE','slug','failed-create','translations','{"en":{"name":"Failed synthetic"}}'::jsonb,'brand_id',pg_temp.uid('brand1')),jsonb_build_array(pg_temp.uid('tag1')),bad,null,jsonb_build_array(pg_temp.uid('cat1'),pg_temp.uid('cat2')),failed_pid);
 exception when unique_violation then caught:=true; end;
 perform pg_temp.assert_true(caught and not exists(select 1 from ecommerce_products where id=failed_pid),'failed_create_no_partial_draft');
 perform pg_temp.assert_true(not exists(select 1 from ecommerce_product_categories where product_id=failed_pid) and not exists(select 1 from ecommerce_product_tags where product_id=failed_pid),'failed_create_no_partial_relationships');
 perform public.create_ecommerce_product_v3_safe(1161,jsonb_build_object('sku','BENCH-small','slug','bench-small','translations','{"en":{"name":"Synthetic benchmark"}}'::jsonb,'brand_id',pg_temp.uid('brand1'),'price',20),jsonb_build_array(pg_temp.uid('tag1')),a,null,jsonb_build_array(pg_temp.uid('cat1'),pg_temp.uid('cat2')),pid);
 perform pg_temp.assert_true((select brand_id=pg_temp.uid('brand1') from ecommerce_products where id=pid) and (select count(*)=2 from ecommerce_product_categories where product_id=pid),'atomic_create_current_brand_categories');
 started:=clock_timestamp();
 for n in 1..50 loop perform public.save_ecommerce_product_aggregate_v2_safe(1161,pid,a->'attributes',a->'options',a->'variants'); end loop;
 insert into benchmark values('old_v2_aggregate',1000*extract(epoch from clock_timestamp()-started)/50);
 started:=clock_timestamp();
 for n in 1..50 loop perform public.save_ecommerce_product_aggregate_v3_safe(1161,pid,a->'attributes',a->'options',a->'variants'); end loop;
 insert into benchmark values('new_v3_aggregate_with_catalog_response',1000*extract(epoch from clock_timestamp()-started)/50);
 started:=clock_timestamp();
 for n in 1..50 loop perform public.update_ecommerce_product_v3_safe(1161,pid,'{"price":20}',jsonb_build_array(pg_temp.uid('tag1')),a); end loop;
 insert into benchmark values('new_atomic_full_product_with_catalog_response',1000*extract(epoch from clock_timestamp()-started)/50);
end $$;
-- Maximum supported editor topology: 25 sizes x 20 colors, 500 variants.
do $$ declare a jsonb; opts jsonb; vs jsonb; started timestamptz; pid uuid:=pg_temp.uid('benchmark500'); begin
 insert into ecommerce_products(id,tenant_id,sku,slug,translations,status,price)
 values(pid,1161,'BENCH500','bench500','{"en":{"name":"Synthetic benchmark"}}','draft',20);
 select jsonb_build_array(
 jsonb_build_object('id',pg_temp.uid('bench-size'),'client_id',pg_temp.uid('bench-size'),'code','size','name_translations','{"en":"Size"}'::jsonb,'normalized_name','size','values',
  (select jsonb_agg(jsonb_build_object('id',pg_temp.uid('bs'||n),'code','bs'||n,'value_translations',jsonb_build_object('en',n::text),'normalized_value',n::text)) from generate_series(1,25)n)),
 jsonb_build_object('id',pg_temp.uid('bench-color'),'client_id',pg_temp.uid('bench-color'),'code','color','name_translations','{"en":"Color"}'::jsonb,'normalized_name','color','values',
  (select jsonb_agg(jsonb_build_object('id',pg_temp.uid('bc'||n),'code','bc'||n,'value_translations',jsonb_build_object('en','Color '||n),'normalized_value','color '||n)) from generate_series(1,20)n))) into opts;
 select jsonb_agg(jsonb_build_object('id',pg_temp.uid('bv'||s||':'||c),'sku','BENCH-'||s||'-'||c,'inventory_quantity',10,'option_value_ids',jsonb_build_array(pg_temp.uid('bs'||s),pg_temp.uid('bc'||c)))) into vs from generate_series(1,25)s cross join generate_series(1,20)c;
 a:=jsonb_build_object('attributes','[]'::jsonb,'options',opts,'variants',vs);
 perform public.save_ecommerce_product_aggregate_v2_safe(1161,pid,'[]',opts,vs);
 started:=clock_timestamp();
 for n in 1..3 loop perform public.save_ecommerce_product_aggregate_v2_safe(1161,pid,'[]',opts,vs); end loop;
 insert into benchmark values('500_variants_old_v2_aggregate',1000*extract(epoch from clock_timestamp()-started)/3);
 started:=clock_timestamp();
 for n in 1..3 loop perform public.update_ecommerce_product_v3_safe(1161,pid,'{"price":20}','[]',a); end loop;
 insert into benchmark values('500_variants_new_atomic_full_with_catalog_response',1000*extract(epoch from clock_timestamp()-started)/3);
end $$;
select label||':'||round(ms,3)||'ms_per_save' from benchmark;

-- Product-owned children still cascade when no order/movement history exists.
select public.delete_ecommerce_product_v3_safe(1161,pg_temp.uid('benchmark500'));
select pg_temp.assert_true(not exists(select 1 from ecommerce_product_variants where product_id=pg_temp.uid('benchmark500')),'unreferenced_product_deletion_cascades');
select 'FINAL_DATABASE_ASSERTIONS_PASS:'||count(*) from test_assertions;
