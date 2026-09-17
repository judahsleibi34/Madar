#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONTAINER_NAME="madar-093-rehearsal-$RANDOM-$$"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:17-alpine}"

cleanup() { docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$CONTAINER_NAME" \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=1g \
  -e POSTGRES_HOST_AUTH_METHOD=trust "$POSTGRES_IMAGE" >/dev/null
docker exec "$CONTAINER_NAME" sh -c \
  'until pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done'

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" \
  psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
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
create schema extensions;
create extension pgcrypto schema extensions;
SQL

for migration in "$REPO_ROOT"/database/migrations/*.sql; do
  number="$(basename "$migration" | cut -d_ -f1)"
  ((10#$number > 92)) && continue
  docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" \
    psql -U postgres -v ON_ERROR_STOP=1 -q < "$migration"
done

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" \
  psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
insert into public.tenants (tenant_id,brand_name,owner_name,business_type)
values (901,'Ownership Test','Owner','business');
insert into auth.users (id,email_confirmed_at,confirmed_at) values
  ('00000000-0000-0000-0000-000000000901',now(),now()),
  ('00000000-0000-0000-0000-000000000902',now(),now());
insert into public.users (auth_id,first_name,last_name,email,tenant_id,account_status,email_verified)
values
  ('00000000-0000-0000-0000-000000000901','Staff','Owner','staff@example.invalid',901,'active',true),
  ('00000000-0000-0000-0000-000000000902','Site','Member','site@example.invalid',901,'active',true);
insert into public.tenant_memberships (tenant_id,user_id,auth_id,role,status)
select 901,id,auth_id,'owner','active' from public.users where email='staff@example.invalid';
insert into public.tenant_site_memberships (tenant_id,user_id,auth_id,role,status)
select 901,id,auth_id,'customer','active' from public.users where email='site@example.invalid';
insert into public.builder_projects (
  id,tenant_id,owner_user_id,name,slug,status,draft_schema,published_schema,
  published_version,published_revision,last_published_at
)
select '90000000-0000-0000-0000-000000000901',901,id,'Test','test','published',
  '{"defaultPageId":"home","pages":[{"id":"home","slug":"/","isDefault":true,"sections":[]}],"forms":[]}',
  '{"defaultPageId":"home","pages":[{"id":"home","slug":"/","isDefault":true,"sections":[]}],"forms":[]}',
  1,0,now()
from public.users where email='staff@example.invalid';
insert into public.website_settings (
  user_id,tenant_id,subdomain,brand,published_project_id,standard_path_slug
)
select id,901,'ownership-test','Ownership Test',
  '90000000-0000-0000-0000-000000000901','ownership-test'
from public.users where email='staff@example.invalid';

select public.register_app_installation(
  id,901,'123e4567-e89b-42d3-a456-426614174000','linux','browser','granted',false
) from public.users where email='staff@example.invalid';
select public.bind_web_push_subscription_to_installation(
  id,901,'123e4567-e89b-42d3-a456-426614174000',
  'https://push.example.invalid/device','old-key','old-auth','test'
) from public.users where email='staff@example.invalid';
SQL

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" \
  psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/093_harden_public_ownership_and_web_push.sql"

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" \
  psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
-- Production-style pgcrypto placement must support endpoint/key rotation.
select public.bind_web_push_subscription_to_installation(
  id,901,'123e4567-e89b-42d3-a456-426614174000',
  'https://push.example.invalid/device','rotated-key','rotated-auth','test'
) from public.users where email='staff@example.invalid';

select public.create_builder_form_submission_notified_safe(
  jsonb_build_object(
    'tenant_id',901,
    'project_id','90000000-0000-0000-0000-000000000901',
    'form_id','contact',
    'status','new',
    'answers','{}'::jsonb,
    'field_snapshot','[]'::jsonb,
    'site_user_id',(select id from public.users where email='site@example.invalid'),
    'site_membership_id',(select id from public.tenant_site_memberships where tenant_id=901)
  ),
  null,
  repeat('a',64),
  jsonb_build_object(
    'event_type','builder.form_submitted','source_type','form',
    'title','New form submission','body','A form was submitted','data','{}'::jsonb
  )
);

select public.create_builder_reservation_notified_safe(
  jsonb_build_object(
    'tenant_id',901,
    'project_id','90000000-0000-0000-0000-000000000901',
    'block_id','reservation',
    'block_type','reservationBlock',
    'status','new',
    'payload','{}'::jsonb,
    'field_snapshot','[]'::jsonb,
    'site_user_id',(select id from public.users where email='staff@example.invalid'),
    'site_membership_id',null
  ),
  null,
  repeat('b',64),
  false,
  jsonb_build_object(
    'event_type','builder.reservation_requested','source_type','reservationBlock',
    'title','New reservation','body','A reservation was submitted','data','{}'::jsonb
  )
);

do $$
begin
  if (select schema_version from public.application_schema_state where contract_key='core') <> 93
  then raise exception 'schema_state_not_93'; end if;
  if not exists (
    select 1 from public.web_push_subscriptions
    where endpoint like 'revoked:%' and p256dh='old-key' and revoked_at is not null
  ) then raise exception 'qualified_digest_rotation_failed'; end if;
  if not exists (
    select 1 from public.builder_form_submissions submission
    join public.tenant_site_memberships membership
      on membership.id=submission.site_membership_id
     and membership.user_id=submission.site_user_id
     and membership.tenant_id=submission.tenant_id
    where submission.tenant_id=901
  ) then raise exception 'site_submission_owner_not_atomic'; end if;
  if not exists (
    select 1 from public.builder_reservations reservation
    join public.users staff on staff.id=reservation.site_user_id
    where reservation.tenant_id=901 and reservation.site_membership_id is null
      and staff.email='staff@example.invalid'
  ) then raise exception 'staff_reservation_owner_not_atomic'; end if;
  if has_function_privilege(
    'authenticated',
    'public.bind_web_push_subscription_to_installation(integer,integer,uuid,text,text,text,text)',
    'execute'
  ) then raise exception 'authenticated_bind_grant_present'; end if;
  if not (
    select 'search_path=public'=any(coalesce(proconfig,'{}'::text[]))
    from pg_proc where oid='public.bind_web_push_subscription_to_installation(integer,integer,uuid,text,text,text,text)'::regprocedure
  ) then raise exception 'bind_search_path_widened'; end if;
end $$;

-- A site membership from another identity must fail before any row is stored.
do $$
declare before_count bigint;
begin
  select count(*) into before_count from public.builder_form_submissions;
  begin
    perform public.create_builder_form_submission_notified_safe(
      jsonb_build_object(
        'tenant_id',901,
        'project_id','90000000-0000-0000-0000-000000000901',
        'form_id','invalid-owner',
        'site_user_id',(select id from public.users where email='staff@example.invalid'),
        'site_membership_id',(select id from public.tenant_site_memberships where tenant_id=901)
      ),
      null,repeat('c',64),'{}'::jsonb
    );
    raise exception 'mismatched_site_owner_accepted';
  exception when sqlstate 'P0001' then
    if sqlerrm <> 'site_record_owner_invalid' then raise; end if;
  end;
  if (select count(*) from public.builder_form_submissions) <> before_count
  then raise exception 'invalid_owner_left_durable_row'; end if;
end $$;
SQL

echo "migration 093 rehearsal passed on PostgreSQL 17"
