#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WEB_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONTAINER_NAME="madar-115-synthetic-$RANDOM-$$"
POSTGRES_IMAGE="postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73"
BACKEND_TEST_IMAGE="${BACKEND_TEST_IMAGE:-madar-backend-test}"
created=false
cleanup() { if "$created"; then docker rm -f "$CONTAINER_NAME" >/dev/null; fi; }
trap cleanup EXIT
docker run -d --name "$CONTAINER_NAME" --label madar.rehearsal=synthetic-commercial-115 \
  --publish 127.0.0.1:55445:5432 --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=1g \
  -e POSTGRES_HOST_AUTH_METHOD=trust "$POSTGRES_IMAGE" >/dev/null
created=true
for attempt in $(seq 1 60); do
  if docker exec "$CONTAINER_NAME" pg_isready -U postgres >/dev/null 2>&1; then break; fi
  sleep 1
done
docker exec "$CONTAINER_NAME" pg_isready -U postgres >/dev/null
docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
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
comment on database postgres is 'madar-commercial-synthetic-rehearsal';
SQL
for migration in "$WEB_ROOT"/database/migrations/*.sql; do
  number="$(basename "$migration" | cut -d_ -f1)"
  ((10#$number > 114)) && continue
  docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q < "$migration"
done
docker exec "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -Atc "select schema_version=114 from public.application_schema_state where contract_key='core'" | rg '^t$'
docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q < "$WEB_ROOT/database/migrations/115_reconcile_commercial_access.sql"
docker run --rm --network host --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --env PYTHONPATH=/app \
  --env APP_ENV=test \
  --env SUPABASE_URL=http://127.0.0.1:54321 \
  --env SUPABASE_ANON_KEY=madar-ci-placeholder-anon-not-a-secret \
  --env SUPABASE_SERVICE_KEY=madar-ci-placeholder-service-not-a-secret \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --env COMMERCIAL_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=55445 dbname=postgres user=postgres connect_timeout=10' \
  --volume "$WEB_ROOT/backend/tests/test_commercial_authority_database.py:/commercial-tests.py:ro" \
  "$BACKEND_TEST_IMAGE" python /commercial-tests.py
echo "Migration 115 synthetic 114 to 115 upgrade and ledger regression suite passed"
