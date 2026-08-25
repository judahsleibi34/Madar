-- Deterministic, non-customer fixtures for authenticated cross-tenant staging tests.
\set ON_ERROR_STOP on

-- This is a disposable canonical plan assignment used to reach calendar routes.
-- It is not evidence or a recommendation for any production tenant.
update public.tenant_subscriptions
set plan_id = 'business_plus', updated_at = now()
where tenant_id = 9101 and source = 'synthetic_staging';

insert into public.builder_projects(id, tenant_id, owner_user_id, name, slug, draft_schema)
select '00000000-0000-0000-0000-000000099101', 9101, id,
       'Tenant A isolation fixture', 'tenant-a-isolation-fixture', '{}'::jsonb
from public.users where auth_id = '00000000-0000-0000-0000-000000009101'
on conflict (id) do update set owner_user_id = excluded.owner_user_id;

insert into public.builder_projects(id, tenant_id, owner_user_id, name, slug, draft_schema)
select '00000000-0000-0000-0000-000000099102', 9102, id,
       'Tenant B isolation fixture', 'tenant-b-isolation-fixture', '{}'::jsonb
from public.users where auth_id = '00000000-0000-0000-0000-000000009201'
on conflict (id) do update set owner_user_id = excluded.owner_user_id;

insert into public.calendars(id, tenant_id, owner_user_id, name, is_default)
select '00000000-0000-0000-0000-000000098101', 9101, id,
       'Tenant A staging calendar', true
from public.users where auth_id = '00000000-0000-0000-0000-000000009101'
on conflict (id) do update set owner_user_id = excluded.owner_user_id;

insert into public.calendars(id, tenant_id, owner_user_id, name, is_default)
select '00000000-0000-0000-0000-000000098102', 9102, id,
       'Tenant B staging calendar', true
from public.users where auth_id = '00000000-0000-0000-0000-000000009201'
on conflict (id) do update set owner_user_id = excluded.owner_user_id;

insert into public.user_notifications(id, tenant_id, user_id, event_type, title, body)
select '00000000-0000-0000-0000-000000097102', 9102, id,
       'staging.isolation', 'TENANT_B_PRIVATE_SENTINEL', 'Synthetic isolation evidence'
from public.users where auth_id = '00000000-0000-0000-0000-000000009201'
on conflict (id) do nothing;

insert into public.data_deletion_requests(
  id, request_type, target_user_id, target_user_id_snapshot,
  requested_by_user_id, state, current_phase, verification_status, completed_at
)
select '00000000-0000-0000-0000-000000096102', 'user', id, id, id,
       'completed_with_retained_records', 'complete',
       'verified_with_retained_records', now()
from public.users where auth_id = '00000000-0000-0000-0000-000000009201'
on conflict (id) do nothing;
