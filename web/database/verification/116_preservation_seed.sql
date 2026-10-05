-- Run at schema 115, before applying 116, using synthetic history.
insert into public.tenants(tenant_id,brand_name,owner_name) values(1071,'Preservation Store','Owner');
insert into auth.users(id) values('10710000-0000-4000-8000-000000000001');
insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status)
values('10710000-0000-4000-8000-000000000001','Owner','One','preservation1071@example.invalid',1071,'active');
insert into public.website_settings(user_id,tenant_id,subdomain,ecommerce_currency)
select id,1071,'catalog-preservation-1071','USD' from public.users where tenant_id=1071;
insert into public.ecommerce_tenant_service_areas(tenant_id,service_area_id,enabled)
values(1071,'95000000-0000-0000-0000-000000000001',true);
insert into public.ecommerce_delivery_pricing(tenant_id,service_area_id,price) values(1071,'95000000-0000-0000-0000-000000000001',0);

insert into public.ecommerce_products(id,tenant_id,sku,slug,translations,status,price,currency)
values('10710000-0000-4000-8000-000000000002',1071,'PRESERVE','preserve','{"en":{"name":"Preserve"}}','draft',20,'USD');
select public.save_ecommerce_product_aggregate_v2_safe(1071,'10710000-0000-4000-8000-000000000002','[]',
'[{"id":"10710000-0000-4000-8000-000000000003","client_id":"10710000-0000-4000-8000-000000000003","code":"size","name_translations":{"en":"Size"},"normalized_name":"size","values":[{"id":"10710000-0000-4000-8000-000000000004","code":"combined","value_translations":{"en":"36 - 37"},"normalized_value":"36 - 37"}]}]',
'[{"id":"10710000-0000-4000-8000-000000000005","sku":"PRESERVE-COMBINED","inventory_quantity":10,"option_value_ids":["10710000-0000-4000-8000-000000000004"]}]');
update public.ecommerce_products set status='active' where tenant_id=1071;
select public.create_ecommerce_order_safe(
'{"tenant_id":1071,"payment_method":"cash_on_delivery","customer_name":"Synthetic Buyer","email":"synthetic@example.invalid","phone":"+970590000000","service_area_id":"95000000-0000-0000-0000-000000000001","street":"Test Street","items":[{"product_id":"10710000-0000-4000-8000-000000000002","variant_id":"10710000-0000-4000-8000-000000000005","quantity":1}]}',repeat('a',64),repeat('b',64),repeat('c',64)) is not null;
select public.save_ecommerce_product_aggregate_v2_safe(1071,'10710000-0000-4000-8000-000000000002','[]',
'[{"id":"10710000-0000-4000-8000-000000000003","client_id":"10710000-0000-4000-8000-000000000003","code":"size","name_translations":{"en":"Size"},"normalized_name":"size","values":[{"id":"10710000-0000-4000-8000-000000000006","code":"size-36","value_translations":{"en":"36"},"normalized_value":"36"}]}]',
'[{"id":"10710000-0000-4000-8000-000000000007","sku":"PRESERVE-36","inventory_quantity":9,"option_value_ids":["10710000-0000-4000-8000-000000000006"]}]');

-- An entirely historical option remains referenced by an inactive variant.
insert into ecommerce_products(id,tenant_id,sku,slug,translations,status)
values('10710000-0000-4000-8000-000000000011',1071,'HISTORY','history','{"en":{"name":"History"}}','draft');
insert into ecommerce_product_options(id,tenant_id,product_id,code,name_translations,normalized_name,required)
values('10710000-0000-4000-8000-000000000012',1071,'10710000-0000-4000-8000-000000000011','old-size','{"en":"Old Size"}','old size',true);
insert into ecommerce_product_option_values(id,tenant_id,product_id,option_id,code,value_translations,normalized_value,active)
values('10710000-0000-4000-8000-000000000013',1071,'10710000-0000-4000-8000-000000000011','10710000-0000-4000-8000-000000000012','old-36','{"en":"36"}','36',false);
insert into ecommerce_product_variants(id,tenant_id,product_id,sku,inventory_quantity,active,option_signature)
values('10710000-0000-4000-8000-000000000014',1071,'10710000-0000-4000-8000-000000000011','HISTORY-36',7,false,encode(extensions.digest('10710000-0000-4000-8000-000000000013','sha256'),'hex'));
insert into ecommerce_variant_option_values(tenant_id,product_id,variant_id,option_id,option_value_id)
values(1071,'10710000-0000-4000-8000-000000000011','10710000-0000-4000-8000-000000000014','10710000-0000-4000-8000-000000000012','10710000-0000-4000-8000-000000000013');

-- Newer brand and ordered multi-category membership already exist at schema115.
insert into ecommerce_brands(id,tenant_id,name,slug) values('10710000-0000-4000-8000-000000000021',1071,'Preserved Brand','preserved-brand');
insert into ecommerce_categories(id,tenant_id,slug,translations) values
('10710000-0000-4000-8000-000000000022',1071,'first','{"en":{"name":"First"}}'),
('10710000-0000-4000-8000-000000000023',1071,'second','{"en":{"name":"Second"}}');
update ecommerce_products set brand_id='10710000-0000-4000-8000-000000000021',brand='Preserved Brand',category_id='10710000-0000-4000-8000-000000000022',images='["/uploads/tenant_1071/builder_assets/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png"]' where id='10710000-0000-4000-8000-000000000002';
insert into ecommerce_product_categories values
(1071,'10710000-0000-4000-8000-000000000002','10710000-0000-4000-8000-000000000022',0,now()),
(1071,'10710000-0000-4000-8000-000000000002','10710000-0000-4000-8000-000000000023',1,now());
insert into builder_assets(id,tenant_id,storage_key,managed_filename,mime_type,size_bytes,sha256,status,reference_count)
values('10710000-0000-4000-8000-000000000024',1071,'tenant_1071/builder_assets/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png','image/png',1,repeat('a',64),'active',1);
