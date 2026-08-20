#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONTAINER_NAME="madar-074-rehearsal-$RANDOM-$$"
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
  ((10#$number > 73)) && continue
  docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q < "$migration"
done

docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/074_create_app_installations.sql"
docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/074_create_app_installations.sql"

docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
insert into public.tenants (tenant_id,brand_name,owner_name,business_type)
values (401,'Installation Test','Owner','business');
insert into auth.users (id,email_confirmed_at,confirmed_at) values
  ('00000000-0000-0000-0000-000000000401',now(),now()),
  ('00000000-0000-0000-0000-000000000402',now(),now());
insert into public.users (auth_id,first_name,last_name,email,tenant_id,account_status,email_verified)
values
  ('00000000-0000-0000-0000-000000000401','One','Member','one@example.invalid',401,'active',true),
  ('00000000-0000-0000-0000-000000000402','Two','Member','two@example.invalid',401,'active',true);
insert into public.tenant_memberships (tenant_id,user_id,auth_id,role,status)
select 401,id,auth_id,'member','active' from public.users where tenant_id=401;

select public.register_app_installation(
  id,401,'123e4567-e89b-42d3-a456-426614174000','linux','browser','default',false
) from public.users;
select public.register_app_installation(
  min(id),401,'123e4567-e89b-42d3-a456-426614174000','linux','standalone','granted',true
) from public.users;

do $$
begin
  if (select count(*) from public.app_installations) <> 2 then
    raise exception 'shared_browser_user_isolation_failed'; end if;
  if (select count(*) from public.app_installations where installed_confirmed_at is not null) <> 1 then
    raise exception 'standalone_confirmation_failed'; end if;
  if not (select relrowsecurity from pg_class where oid='public.app_installations'::regclass) then
    raise exception 'installation_rls_disabled'; end if;
  if has_table_privilege('authenticated','public.app_installations','select') then
    raise exception 'installation_authenticated_grant_present'; end if;
end $$;

select public.bind_web_push_subscription_to_installation(
  min(id),401,'123e4567-e89b-42d3-a456-426614174000',
  'https://push.example.invalid/shared','key-one','auth-one','test'
) from public.users;
select public.bind_web_push_subscription_to_installation(
  max(id),401,'123e4567-e89b-42d3-a456-426614174000',
  'https://push.example.invalid/shared','key-two','auth-two','test'
) from public.users;

do $$
declare second_user integer := (select max(id) from public.users where tenant_id=401);
begin
  if not exists (
    select 1 from public.web_push_subscriptions subscription
    join public.app_installations installation on installation.id=subscription.app_installation_id
    where subscription.endpoint='https://push.example.invalid/shared'
      and subscription.user_id=second_user and installation.user_id=second_user
      and subscription.revoked_at is null
  ) then raise exception 'shared_endpoint_safe_rebind_failed'; end if;
  if not exists (
    select 1 from public.web_push_subscriptions
    where user_id <> second_user and endpoint like 'revoked:%'
      and revoked_at is not null
  ) then raise exception 'prior_account_binding_not_preserved_as_revoked'; end if;
end $$;

-- Legacy rows remain valid and nullable during the rollout window.
insert into public.web_push_subscriptions (tenant_id,user_id,endpoint,p256dh,auth)
select 401,min(id),'https://push.example.invalid/legacy','key','auth'
from public.users where tenant_id=401;

select public.register_app_installation(
  max(id),401,'223e4567-e89b-42d3-a456-426614174000','linux','browser','granted',false
) from public.users where tenant_id=401;
select public.bind_web_push_subscription_to_installation(
  max(id),401,'223e4567-e89b-42d3-a456-426614174000',
  'https://push.example.invalid/device-b','key-b','auth-b','test'
) from public.users where tenant_id=401;

-- Device-scoped logout revokes only the selected user's/install binding.
select public.revoke_installation_push_subscriptions(
  max(id),'123e4567-e89b-42d3-a456-426614174000'
) from public.users where tenant_id=401;
do $$
begin
  if exists (
    select 1 from public.web_push_subscriptions
    where endpoint='https://push.example.invalid/shared' and revoked_at is null
  ) then raise exception 'scoped_revoke_failed'; end if;
  if not exists (
    select 1 from public.web_push_subscriptions
    where endpoint='https://push.example.invalid/legacy' and revoked_at is null
      and app_installation_id is null
  ) then raise exception 'legacy_subscription_broken'; end if;
  if not exists (
    select 1 from public.web_push_subscriptions
    where endpoint='https://push.example.invalid/device-b' and revoked_at is null
  ) then raise exception 'other_device_was_revoked'; end if;
end $$;
SQL

echo "migration 074 rehearsal passed"
