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


insert into public.site_visit_counters(tenant_id,website_visits,store_visits) values(961,17,9);

-- Preserve real commercial ledger, revision, and audit records across the forward transition.
update public.users set user_type='admin' where tenant_id=961;
select public.apply_commercial_access_command(961,(select id from public.users where tenant_id=961),'aal2',
  'manual_payment','forward-101-payment','forward-101-request',
  jsonb_build_object('request',jsonb_build_object('plan_id','business','method','cash','actual_minor',2500,
    'currency','USD','billing_months',1,'paid_at',now(),'valid_from',now(),'valid_until',now()+interval '1 month',
    'receipt_reference','FORWARD-101-PROOF','reason','Synthetic preservation proof'),
    'quote',jsonb_build_object('expected_minor',2500,'catalog_version','synthetic')));
