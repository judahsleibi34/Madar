-- Representative pre-071 data for a disposable database containing 001–070.
-- Never run against production.

insert into public.tenants (tenant_id,brand_name,owner_name,business_type)
select
  id,
  case when id=108 then 'Internal test tenant' else 'Tenant '||id end,
  'Owner '||id,
  case when id=108 then 'internal_test' else 'business' end
from generate_series(101,110) id;

insert into auth.users (id,email_confirmed_at,confirmed_at)
select
  ('00000000-0000-0000-0000-'||lpad(id::text,12,'0'))::uuid,
  now(),
  now()
from generate_series(101,110) id;

insert into public.users (
  auth_id,first_name,last_name,email,tenant_id,account_status,email_verified
)
select
  ('00000000-0000-0000-0000-'||lpad(id::text,12,'0'))::uuid,
  'Owner',
  id::text,
  'owner'||id||'@example.invalid',
  id,
  'active',
  true
from generate_series(101,110) id;

insert into public.tenant_memberships (
  tenant_id,user_id,auth_id,role,status
)
select tenant_id,id,auth_id,'owner','active'
from public.users
where tenant_id between 101 and 110;

insert into public.features (
  tenant_id,subscription_type,plan,builder_type,payment_status,updated_at
) values
  -- The newer inactive Complete row must not elevate this active Forms record.
  (102,'individual_builder','basic','forms','active',now()),
  (102,'full_platform','complete',null,'canceled',now()+interval '1 minute'),
  (103,'full_platform','cms',null,'active',now()),
  -- Two active records are deliberately ambiguous.
  (104,'full_platform','cms',null,'active',now()),
  (104,'individual_builder','premium','reservation','active',now()),
  (105,'full_platform','starter',null,'active',now()),
  (106,'full_platform','complete',null,'active',now()),
  (107,'full_platform','cms',null,'active',now()),
  (108,'full_platform','cms',null,'active',now());

insert into public.builder_projects (
  id,tenant_id,owner_user_id,name,slug,status,draft_schema,published_schema,
  published_version,last_published_at
)
select
  ('10000000-0000-0000-0000-'||lpad(t::text,12,'0'))::uuid,
  t,
  users.id,
  'Project '||t,
  'project-'||t,
  case when t=107 then 'archived' else 'published' end,
  '{"pages":[],"forms":[]}'::jsonb,
  case when t=107 then null else '{"pages":[],"forms":[]}'::jsonb end,
  case when t=107 then 0 else 1 end,
  case when t=107 then null else now() end
from generate_series(101,110) t
join public.users users on users.tenant_id=t;

insert into public.website_settings (
  user_id,tenant_id,subdomain,brand,published_project_id
)
select
  users.id,
  users.tenant_id,
  values_to_seed.subdomain,
  'Brand '||users.tenant_id,
  case when values_to_seed.bind_published then
    ('10000000-0000-0000-0000-'||lpad(users.tenant_id::text,12,'0'))::uuid
  else null end
from public.users users
join (values
  (101,' Clean-Site ',false),
  (102,' lower-active ',false),
  (103,' Foo Shop ',false),
  (104,'duplicate shop',false),
  (105,'duplicate--shop',false),
  (106,'LiveLegacy',true),
  (107,'archived-legacy',false),
  (108,'Admin',false),
  (109,'!!!',false),
  (110,'site-109',false)
) as values_to_seed(tenant_id,subdomain,bind_published)
  on values_to_seed.tenant_id=users.tenant_id;

insert into public.storage_accounts (
  tenant_id,scope_key,user_id,used_bytes,reserved_bytes,quota_bytes
) values (102,'tenant',null,8589934592,0,10737418240);

insert into public.ai_usage_daily (
  user_id,tenant_id,usage_date,message_count,code_generation_count
)
select id,102,current_date,17,3
from public.users
where tenant_id=102;

insert into public.builder_form_submissions (
  tenant_id,project_id,form_id,answers
) values (
  106,'10000000-0000-0000-0000-000000000106',
  'legacy-form','{"name":"Preserved"}'
);

insert into public.builder_reservations (
  tenant_id,project_id,site_subdomain,block_id,customer_name,status
) values (
  106,'10000000-0000-0000-0000-000000000106',
  'LiveLegacy','reservation-block','Preserved','new'
);

insert into public.calendars (id,tenant_id,name,visibility)
values (
  '20000000-0000-0000-0000-000000000106',
  106,'Legacy Calendar','private'
);

insert into public.calendar_events (
  tenant_id,calendar_id,title,starts_at,ends_at
) values (
  106,'20000000-0000-0000-0000-000000000106',
  'Preserved event',now()+interval '1 day',now()+interval '2 days'
);
