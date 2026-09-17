#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

target="${1:-81}"
[[ "$target" =~ ^[0-9]+$ && "$target" -ge 1 && "$target" -le 83 ]] \
  || { echo "usage: $0 [target-schema<=83]" >&2; exit 2; }
container="${MADAR_STAGING_POSTGRES_CONTAINER:-madar-stage-postgres}"
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

docker exec "$container" sh -c 'until pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done'
docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$container" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
do $$ begin create role anon nologin; exception when duplicate_object then null; end $$;
do $$ begin create role authenticated nologin; exception when duplicate_object then null; end $$;
do $$ begin create role service_role nologin bypassrls; exception when duplicate_object then null; end $$;
do $$ begin create role authenticator login password 'staging-only' noinherit; exception when duplicate_object then null; end $$;
grant anon, authenticated, service_role to authenticator;
create schema if not exists auth;
create table if not exists auth.users (
  id uuid primary key,
  email text,
  encrypted_password text,
  email_confirmed_at timestamptz,
  confirmed_at timestamptz,
  raw_app_meta_data jsonb default '{}'::jsonb,
  raw_user_meta_data jsonb default '{}'::jsonb
);
create or replace function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid
$$;
grant usage on schema auth to anon,authenticated,service_role;
create schema if not exists storage;
create table if not exists storage.buckets (
  id text primary key,name text not null,public boolean not null default false,
  file_size_limit bigint,allowed_mime_types text[]
);
create table if not exists storage.objects (
  id uuid primary key default gen_random_uuid(),bucket_id text references storage.buckets(id),name text
);
alter table storage.objects enable row level security;
SQL

for migration in "$repo_root"/database/migrations/*.sql; do
  number="$(basename "$migration" | cut -d_ -f1)"
  ((10#$number > target)) && continue
  docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$container" \
    psql -U postgres -v ON_ERROR_STOP=1 -q <"$migration"
done

actual="$(docker exec "$container" psql -U postgres -Atqc \
  "select schema_version from public.application_schema_state where contract_key='core'" 2>/dev/null || true)"
[[ "$actual" == "$target" ]] || { echo "schema mismatch expected=$target actual=$actual" >&2; exit 1; }
docker exec "$container" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
grant usage on schema public to anon,authenticated,service_role;
notify pgrst,'reload schema';
SQL
printf 'staging schema prepared: %s\n' "$actual"
