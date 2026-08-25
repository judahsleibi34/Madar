-- Full disposable tenant fixture for the schema-083 deletion operational drill.
-- This file contains no production identifiers, customer data, or credentials.
begin;

insert into public.tenants (tenant_id,brand_name,owner_name,business_type)
values (9103,'Synthetic Lifecycle Tenant','Synthetic Lifecycle Owner','business');

insert into auth.users(id,email,email_confirmed_at,confirmed_at) values
 ('00000000-0000-0000-0000-000000009301','lifecycle-owner@staging.invalid',now(),now()),
 ('00000000-0000-0000-0000-000000009302','lifecycle-member@staging.invalid',now(),now());

insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified,user_type)
values
 ('00000000-0000-0000-0000-000000009301','Synthetic','Lifecycle Owner','lifecycle-owner@staging.invalid',9103,'active',true,'user'),
 ('00000000-0000-0000-0000-000000009302','Synthetic','Lifecycle Member','lifecycle-member@staging.invalid',9103,'active',true,'user');

insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status)
select 9103,id,auth_id,case when email='lifecycle-owner@staging.invalid' then 'owner' else 'member' end,'active'
from public.users where tenant_id=9103;

insert into public.tenant_subscriptions(
  tenant_id,plan_id,state,catalog_version,price_minor,period_start,period_end,source
) values (9103,'business','active','2026-08',0,now(),now()+interval '30 days','synthetic_staging');

insert into public.builder_projects(
  id,tenant_id,owner_user_id,name,slug,status,draft_schema,published_schema,
  published_version,last_published_at,draft_revision,published_revision,schema_version
)
select '00000000-0000-0000-0000-000000009303',9103,id,'Lifecycle Site','lifecycle-site','published',
  '{"pages":[{"id":"home","slug":"/","isDefault":true,"sections":[]}],"forms":[],"defaultPageId":"home"}'::jsonb,
  '{"pages":[{"id":"home","slug":"/","isDefault":true,"sections":[]}],"forms":[{"id":"quiz-1","title":"Synthetic Quiz"}],"siteChrome":{"brand":"Synthetic Lifecycle Tenant","footerStoreName":"Synthetic Lifecycle Tenant"},"defaultPageId":"home"}'::jsonb,
  1,now(),1,1,1
from public.users where auth_id='00000000-0000-0000-0000-000000009301';

insert into public.website_settings(
  user_id,tenant_id,published_project_id,standard_path_slug,brand,footer_store_name,
  legacy_subdomain_routing_preserved,branded_subdomain_commercial_status
)
select id,9103,'00000000-0000-0000-0000-000000009303','lifecycle-tenant',
       'Synthetic Lifecycle Tenant','Synthetic Lifecycle Tenant',false,'not_applicable'
from public.users where auth_id='00000000-0000-0000-0000-000000009301';

insert into public.builder_form_submissions(
  id,tenant_id,project_id,form_id,form_title,form_version,status,answers,quiz_result,field_snapshot
) values (
  '00000000-0000-0000-0000-000000009340',9103,'00000000-0000-0000-0000-000000009303',
  'form-1','Synthetic Form',1,'new','{"field-1":"synthetic"}',null,'[]'
);

insert into public.public_quiz_attempts(
  id,tenant_id,project_id,form_id,publication_version,publication_hash,subject_hash,state,
  started_at,deadline_at,question_order,private_form_snapshot
) values (
  '00000000-0000-0000-0000-000000009350',9103,'00000000-0000-0000-0000-000000009303',
  'quiz-1',1,repeat('a',64),repeat('b',64),'active',now(),now()+interval '1 hour',
  '["question-1"]','{"id":"quiz-1","answerKey":"server-only"}'
);

insert into public.builder_reservations(
  id,tenant_id,project_id,block_id,block_type,reservation_title,starts_at,ends_at,
  timezone,status,payload,field_snapshot,exclusive_slot
) values (
  '00000000-0000-0000-0000-000000009360',9103,'00000000-0000-0000-0000-000000009303',
  'booking-1','reservation','Synthetic Booking',now()+interval '2 hours',now()+interval '3 hours',
  'UTC','confirmed','{}','[]',true
);

insert into public.notification_outbox(
  id,tenant_id,user_id,channel,template,payload,status,attempts,max_attempts,deduplication_key
)
select '00000000-0000-0000-0000-000000009370',9103,id,'internal','synthetic.lifecycle',
       '{}','pending',0,3,'synthetic-lifecycle-9103'
from public.users where auth_id='00000000-0000-0000-0000-000000009301';

insert into public.calendar_sync_connections(
  tenant_id,user_id,provider,account_label,external_account_id,direction,status,encrypted_credentials
)
select 9103,id,'microsoft','Synthetic lifecycle fixture','synthetic-account','read','connected','fixture-redacted'
from public.users where auth_id='00000000-0000-0000-0000-000000009301';

insert into public.builder_assets(
  id,tenant_id,project_id,uploader_user_id,storage_key,original_filename,managed_filename,
  mime_type,size_bytes,sha256,status,reference_count
)
select '00000000-0000-0000-0000-000000009380',9103,
       '00000000-0000-0000-0000-000000009303',id,
       'tenant_9103/builder_assets/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png','synthetic.png',
       'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png','image/png',16,repeat('c',64),'active',1
from public.users where auth_id='00000000-0000-0000-0000-000000009301';

insert into public.builder_asset_references(asset_id,project_id,reference_path)
values ('00000000-0000-0000-0000-000000009380','00000000-0000-0000-0000-000000009303','pages.home.logo');

insert into public.storage_objects(tenant_id,user_id,category,storage_key,size_bytes,sha256,status,metadata)
select 9103,id,'avatar','users/00000000-0000-0000-0000-000000009301/avatar.png',12,repeat('d',64),'active','{}'::jsonb
from public.users where auth_id='00000000-0000-0000-0000-000000009301'
union all
select 9103,id,'dataset','tenant_9103/user_'||id||'/full-delete.bin',24,repeat('e',64),'active','{}'::jsonb
from public.users where auth_id='00000000-0000-0000-0000-000000009301';

commit;
