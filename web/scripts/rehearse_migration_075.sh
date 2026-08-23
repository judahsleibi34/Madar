#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONTAINER_NAME="madar-075-rehearsal-$RANDOM-$$"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:17-alpine}"

cleanup() { docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$CONTAINER_NAME" \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=1g \
  -e POSTGRES_HOST_AUTH_METHOD=trust "$POSTGRES_IMAGE" >/dev/null
docker exec "$CONTAINER_NAME" sh -c \
  'until pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done'

docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
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
  ((10#$number > 74)) && continue
  docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q < "$migration"
done

docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
insert into public.tenants (tenant_id,brand_name,owner_name,business_type)
values (501,'Lifecycle Test','Owner','business');
insert into auth.users (id,email_confirmed_at,confirmed_at)
values ('00000000-0000-0000-0000-000000000501',now(),now());
insert into public.users (auth_id,first_name,last_name,email,tenant_id,account_status,email_verified)
values ('00000000-0000-0000-0000-000000000501','Lifecycle','Member','lifecycle@example.invalid',501,'active',true);
insert into public.tenant_memberships (tenant_id,user_id,auth_id,role,status)
select 501,id,auth_id,'member','active' from public.users where tenant_id=501;

select public.register_app_installation(
  id,501,'123e4567-e89b-42d3-a456-426614174000','linux','browser','granted',false
) from public.users where tenant_id=501;
select public.register_app_installation(
  id,501,'223e4567-e89b-42d3-a456-426614174000','linux','browser','granted',false
) from public.users where tenant_id=501;
select public.bind_web_push_subscription_to_installation(
  id,501,'123e4567-e89b-42d3-a456-426614174000',
  'https://push.example.invalid/device-a','old-key','old-auth','test'
) from public.users where tenant_id=501;
select public.bind_web_push_subscription_to_installation(
  id,501,'223e4567-e89b-42d3-a456-426614174000',
  'https://push.example.invalid/device-b','device-b-key','device-b-auth','test'
) from public.users where tenant_id=501;
SQL

docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/075_harden_web_push_lifecycle.sql"
docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/075_harden_web_push_lifecycle.sql"

docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
-- Permission revocation is scoped to Device A and preserves Device B.
select public.register_app_installation(
  id,501,'123e4567-e89b-42d3-a456-426614174000','linux','browser','denied',false
) from public.users where tenant_id=501;
do $$ begin
  if exists (
    select 1 from public.web_push_subscriptions where endpoint='https://push.example.invalid/device-a' and revoked_at is null
  ) then raise exception 'denied_device_still_active'; end if;
  if not exists (
    select 1 from public.web_push_subscriptions where endpoint='https://push.example.invalid/device-b' and revoked_at is null
  ) then raise exception 'sibling_device_was_disabled'; end if;
end $$;

-- Same-endpoint key rotation preserves the old row as a tombstone.
select public.bind_web_push_subscription_to_installation(
  id,501,'223e4567-e89b-42d3-a456-426614174000',
  'https://push.example.invalid/device-b','rotated-key','rotated-auth','test'
) from public.users where tenant_id=501;
do $$ begin
  if (select count(*) from public.web_push_subscriptions where endpoint='https://push.example.invalid/device-b' and revoked_at is null) <> 1
  then raise exception 'key_rotation_active_binding_invalid'; end if;
  if not exists (
    select 1 from public.web_push_subscriptions where endpoint like 'revoked:%' and p256dh='device-b-key' and revoked_at is not null
  ) then raise exception 'key_rotation_history_not_preserved'; end if;
end $$;

-- Endpoint rotation selects only the replacement and retains prior history.
select public.bind_web_push_subscription_to_installation(
  id,501,'223e4567-e89b-42d3-a456-426614174000',
  'https://push.example.invalid/device-b-new','new-key','new-auth','test'
) from public.users where tenant_id=501;
do $$ begin
  if exists (
    select 1 from public.web_push_subscriptions where endpoint='https://push.example.invalid/device-b' and revoked_at is null
  ) then raise exception 'superseded_endpoint_still_active'; end if;
  if not exists (
    select 1 from public.web_push_subscriptions where endpoint='https://push.example.invalid/device-b-new' and revoked_at is null
  ) then raise exception 'replacement_endpoint_not_active'; end if;
  if has_function_privilege('authenticated', 'public.bind_web_push_subscription_to_installation(integer,integer,uuid,text,text,text,text)', 'execute')
  then raise exception 'authenticated_bind_grant_present'; end if;
end $$;
SQL

echo "migration 075 rehearsal passed"
