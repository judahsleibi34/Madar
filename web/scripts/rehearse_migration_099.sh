#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WEB_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONTAINER_NAME="madar-099-clean-install-$RANDOM-$$"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:17-alpine}"
cleanup() { docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$CONTAINER_NAME" --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=1g -e POSTGRES_HOST_AUTH_METHOD=trust "$POSTGRES_IMAGE" >/dev/null
docker exec "$CONTAINER_NAME" sh -c 'until pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done'
docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
create role anon nologin; create role authenticated nologin; create role service_role nologin;
create schema auth; create table auth.users(id uuid primary key,email_confirmed_at timestamptz,confirmed_at timestamptz);
create function auth.uid() returns uuid language sql stable as $$ select null::uuid $$;
create schema storage; create table storage.buckets(id text primary key,name text not null,public boolean not null default false,file_size_limit bigint,allowed_mime_types text[]);
create table storage.objects(id uuid primary key default gen_random_uuid(),bucket_id text references storage.buckets(id),name text); alter table storage.objects enable row level security;
create schema extensions; create extension pgcrypto schema extensions;
SQL

for migration in "$WEB_ROOT"/database/migrations/*.sql; do
  docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q < "$migration"
done
docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
do $$ begin
  if (select schema_version from public.application_schema_state where contract_key='core') is distinct from 99 then raise exception 'clean_install_not_099'; end if;
  if to_regclass('public.site_visit_counters') is null or to_regprocedure('public.save_ecommerce_product_aggregate_v2_safe(integer,uuid,jsonb,jsonb,jsonb)') is null then raise exception 'clean_install_objects_missing'; end if;
end $$;
SQL
MADAR_REHEARSE_TO_099=true bash "$SCRIPT_DIR/rehearse_migration_096.sh"
echo "clean install through 099 passed on PostgreSQL 17"
