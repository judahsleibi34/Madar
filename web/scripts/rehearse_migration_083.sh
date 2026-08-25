#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONTAINER_NAME="madar-083-rehearsal-$RANDOM-$$"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:17-alpine}"

cleanup() { docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$CONTAINER_NAME" \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=1g \
  -e POSTGRES_HOST_AUTH_METHOD=trust "$POSTGRES_IMAGE" >/dev/null
docker exec "$CONTAINER_NAME" sh -c \
  'until pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done'

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
create role anon nologin;
create role authenticated nologin;
create role service_role nologin;
create schema auth;
create table auth.users (id uuid primary key,email_confirmed_at timestamptz,confirmed_at timestamptz);
create function auth.uid() returns uuid language sql stable as $$ select null::uuid $$;
create schema storage;
create table storage.buckets (id text primary key,name text not null,public boolean not null default false,file_size_limit bigint,allowed_mime_types text[]);
create table storage.objects (id uuid primary key default gen_random_uuid(),bucket_id text references storage.buckets(id),name text);
alter table storage.objects enable row level security;
SQL

for migration in "$REPO_ROOT"/database/migrations/*.sql; do
  number="$(basename "$migration" | cut -d_ -f1)"
  ((10#$number > 82)) && continue
  docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q < "$migration"
done

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
insert into public.tenants (tenant_id,brand_name,owner_name,business_type) values
  (701,'Deletion Test','Owner','business'),(702,'Tenant Delete','Owner','business');
insert into auth.users(id,email_confirmed_at,confirmed_at) values
  ('00000000-0000-0000-0000-000000000701',now(),now()),
  ('00000000-0000-0000-0000-000000000702',now(),now()),
  ('00000000-0000-0000-0000-000000000703',now(),now());
insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified,user_type) values
  ('00000000-0000-0000-0000-000000000701','Owner','One','owner701@example.invalid',701,'active',true,'user'),
  ('00000000-0000-0000-0000-000000000702','Member','One','member701@example.invalid',701,'active',true,'user'),
  ('00000000-0000-0000-0000-000000000703','Owner','Two','owner702@example.invalid',702,'active',true,'user');
insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status)
select tenant_id,id,auth_id,case when email like 'member%' then 'member' else 'owner' end,'active'
from public.users where tenant_id in (701,702);
SQL

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/083_create_entitlement_mapping_and_deletion_lifecycle.sql"

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
do $$
declare result jsonb; member_id integer; owner_id integer; tenant_owner_id integer;
  deletion_id uuid; retention_id uuid; claimed integer;
begin
  select id into owner_id from public.users where email='owner701@example.invalid';
  select id into member_id from public.users where email='member701@example.invalid';
  select id into tenant_owner_id from public.users where email='owner702@example.invalid';
  result := public.apply_tenant_entitlement_mapping_batch(jsonb_build_array(
    jsonb_build_object('tenant_id',701,'target_state','active','plan_id','business','approved_by','operator','approved_at',now(),'mapping_id','approved-701-v1','addons',jsonb_build_array(jsonb_build_object('addon_id','additional_storage_5gb','quantity',2))),
    jsonb_build_object('tenant_id',702,'target_state','inactive','plan_id',null,'approved_by','operator','approved_at',now(),'mapping_id','approved-702-v1','addons','[]'::jsonb)
  ));
  if result->>'applied'<>'2' then raise exception 'mapping_batch_not_applied'; end if;
  -- Exact replay is idempotent and restores no duplicate capability rows.
  perform public.apply_tenant_entitlement_mapping_batch(jsonb_build_array(
    jsonb_build_object('tenant_id',701,'target_state','active','plan_id','business','approved_by','operator','approved_at',now(),'mapping_id','approved-701-v1','addons',jsonb_build_array(jsonb_build_object('addon_id','additional_storage_5gb','quantity',2))),
    jsonb_build_object('tenant_id',702,'target_state','inactive','plan_id',null,'approved_by','operator','approved_at',now(),'mapping_id','approved-702-v1','addons','[]'::jsonb)
  ));
  if (select count(*) from public.tenant_subscriptions where tenant_id=701 and state in ('active','trial','grace'))<>1
    or (select count(*) from public.tenant_addons where tenant_id=701 and state='active')<>1
  then raise exception 'mapping_idempotency_failed'; end if;

  -- A newly approved transition cancels the prior authority. Reapplying the
  -- original approved document later is deterministic rather than silently
  -- pointing the decision record at a canceled subscription.
  perform public.apply_tenant_entitlement_mapping_batch(jsonb_build_array(
    jsonb_build_object('tenant_id',701,'target_state','grandfathered','plan_id','website','grace_until',now()+interval '7 days','grandfather_reason','explicit rehearsal','approved_by','operator','approved_at',now(),'mapping_id','approved-701-v2','addons','[]'::jsonb),
    jsonb_build_object('tenant_id',702,'target_state','inactive','plan_id',null,'approved_by','operator','approved_at',now(),'mapping_id','approved-702-v2','addons','[]'::jsonb)
  ));
  perform public.apply_tenant_entitlement_mapping_batch(jsonb_build_array(
    jsonb_build_object('tenant_id',701,'target_state','active','plan_id','business','approved_by','operator','approved_at',now(),'mapping_id','approved-701-v1','addons',jsonb_build_array(jsonb_build_object('addon_id','additional_storage_5gb','quantity',2))),
    jsonb_build_object('tenant_id',702,'target_state','inactive','plan_id',null,'approved_by','operator','approved_at',now(),'mapping_id','approved-702-v1','addons','[]'::jsonb)
  ));
  if (select count(*) from public.tenant_subscriptions where tenant_id=701 and state in ('active','trial','grace'))<>1
    or (select target_state from public.tenant_entitlement_decisions where tenant_id=701)<>'active'
  then raise exception 'mapping_transition_replay_failed'; end if;

  select id into deletion_id from public.create_data_deletion_request('user',member_id,null,owner_id,null);
  if (select account_status from public.users where id=member_id)<>'deletion_pending'
    or (select count(*) from public.data_deletion_steps where request_id=deletion_id)<>10
    or (select count(*) from public.data_deletion_subjects where request_id=deletion_id)<>1
  then raise exception 'user_deletion_request_invalid'; end if;
  begin
    perform public.create_data_deletion_request('user',member_id,null,owner_id,null);
    raise exception 'duplicate_deletion_request_accepted';
  exception when unique_violation then null; end;
  if has_table_privilege('authenticated','public.data_deletion_requests','select')
    or has_function_privilege('authenticated','public.create_data_deletion_request(text,integer,integer,integer,timestamptz)','execute')
  then raise exception 'deletion_state_exposed'; end if;
  if (select schema_version from public.application_schema_state where contract_key='core')<>83
  then raise exception 'schema_state_not_83'; end if;

  select id into retention_id from public.create_data_deletion_request(
    'tenant',null,702,tenant_owner_id,now()+interval '1 day'
  );
  if (select state from public.data_deletion_requests where id=retention_id)<>'waiting_retention'
    or (select lifecycle_state from public.tenants where tenant_id=702)<>'deletion_pending'
  then raise exception 'retention_request_invalid'; end if;

  select count(*) into claimed from public.claim_data_deletion_requests('worker-a',5,now(),60);
  if claimed<>1 then raise exception 'retention_or_claim_filter_invalid'; end if;
  select count(*) into claimed from public.claim_data_deletion_requests('worker-b',5,now(),60);
  if claimed<>0 then raise exception 'double_claim_accepted'; end if;
  update public.data_deletion_requests set lease_until=now()-interval '1 second'
    where id=deletion_id;
  select count(*) into claimed from public.claim_data_deletion_requests('worker-b',5,now(),60);
  if claimed<>1 then raise exception 'crash_lease_not_recovered'; end if;
end $$;
SQL

# Migration rerun is schema-idempotent and preserves all durable rows.
docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/083_create_entitlement_mapping_and_deletion_lifecycle.sql"

echo "migration 083 rehearsal passed on PostgreSQL 17"
