-- Non-customer fixtures used only in the disposable Madar staging database.
insert into public.tenants (tenant_id,brand_name,owner_name,business_type)
values (9101,'Synthetic Tenant A','Synthetic Owner A','business'),
       (9102,'Synthetic Tenant B','Synthetic Owner B','business')
on conflict (tenant_id) do nothing;

insert into auth.users(id,email,email_confirmed_at,confirmed_at) values
 ('00000000-0000-0000-0000-000000009101','owner-a@staging.invalid',now(),now()),
 ('00000000-0000-0000-0000-000000009102','member-a@staging.invalid',now(),now()),
 ('00000000-0000-0000-0000-000000009201','owner-b@staging.invalid',now(),now())
on conflict (id) do nothing;

insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified,user_type)
values
 ('00000000-0000-0000-0000-000000009101','Synthetic','Owner A','owner-a@staging.invalid',9101,'active',true,'user'),
 ('00000000-0000-0000-0000-000000009102','Synthetic','Member A','member-a@staging.invalid',9101,'active',true,'user'),
 ('00000000-0000-0000-0000-000000009201','Synthetic','Owner B','owner-b@staging.invalid',9102,'active',true,'user')
on conflict (auth_id) do nothing;

insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status)
select tenant_id,id,auth_id,
       case when email='member-a@staging.invalid' then 'member' else 'owner' end,
       'active'
from public.users where tenant_id in (9101,9102)
on conflict do nothing;

-- Synthetic canonical authority. It never leaves the disposable database.
insert into public.tenant_subscriptions(
  tenant_id,plan_id,state,catalog_version,price_minor,period_start,period_end,source
)
values (9101,'business','active','2026-08',0,now(),now()+interval '30 days','synthetic_staging'),
       (9102,'website','active','2026-08',0,now(),now()+interval '30 days','synthetic_staging')
on conflict do nothing;
