#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WEB_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONTAINER_NAME="madar-147-synthetic-$RANDOM-$$"
POSTGRES_IMAGE="postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73"
BACKEND_TEST_IMAGE="${BACKEND_TEST_IMAGE:-madar-backend-test}"
created=false

cleanup() {
  if "$created"; then
    docker rm -f "$CONTAINER_NAME" >/dev/null
  fi
}
trap cleanup EXIT

docker run -d --memory=768m --cpus=0.75 --pids-limit=128 --name "$CONTAINER_NAME" --label madar.rehearsal=synthetic-notification-147 \
  --publish 127.0.0.1:55448:5432 --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=1g \
  -e POSTGRES_HOST_AUTH_METHOD=trust "$POSTGRES_IMAGE" >/dev/null
created=true
for attempt in $(seq 1 60); do
  if docker exec "$CONTAINER_NAME" pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker exec "$CONTAINER_NAME" pg_isready -h 127.0.0.1 -U postgres >/dev/null
docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" \
  psql -X -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
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
comment on database postgres is 'madar-notification-synthetic-rehearsal';
SQL

for migration in "$WEB_ROOT"/database/migrations/*.sql; do
  number="$(basename "$migration" | cut -d_ -f1)"
  if ((10#$number > 114)); then
    continue
  fi
  docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" \
    psql -X -U postgres -v ON_ERROR_STOP=1 -q < "$migration"
done
docker exec "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q \
  -c 'alter table auth.users add column email text'
for migration in "$WEB_ROOT"/database/migrations/*.sql; do
  number="$(basename "$migration" | cut -d_ -f1)"
  if ((10#$number < 115 || 10#$number > 144 || 10#$number == 142)); then
    continue
  fi
  docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" \
    psql -X -U postgres -v ON_ERROR_STOP=1 -q < "$migration"
done
docker exec "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -Atc \
  "select schema_version=144 from public.application_schema_state where contract_key='core'" | grep -qx t

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" \
  psql -X -U postgres -v ON_ERROR_STOP=1 -q \
  < "$WEB_ROOT/database/migrations/145_enforce_paid_commercial_continuity.sql"
docker exec "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -Atc \
  "select schema_version=145 from public.application_schema_state where contract_key='core'" | grep -qx t

docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" \
  psql -X -U postgres -v ON_ERROR_STOP=1 -q < "$WEB_ROOT/database/migrations/146_revise_launch_price_book.sql"
docker run --rm --memory=1g --cpus=1 --pids-limit=256 --network host --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=128m \
  --env PYTHONDONTWRITEBYTECODE=1 --env PYTHONPATH=/app --env APP_ENV=test \
  --env SUPABASE_URL=http://127.0.0.1:54321 \
  --env SUPABASE_ANON_KEY=madar-ci-placeholder-anon-not-a-secret \
  --env SUPABASE_SERVICE_KEY=madar-ci-placeholder-service-not-a-secret \
  --env PYGWALKER_TELEMETRY_ENABLED=false \
  --env NOTIFICATION_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=55448 dbname=postgres user=postgres connect_timeout=5' \
  --env NOTIFICATION_MIGRATION_SQL=/migration147.sql \
  --volume "$WEB_ROOT/backend:/app:ro" \
  --volume "$WEB_ROOT/database/migrations/147_fence_notification_delivery_claims.sql:/migration147.sql:ro" \
  --entrypoint python "$BACKEND_TEST_IMAGE" tests/test_notification_fencing_database.py
echo "Migration147 coordinated rollback/upgrade and native claim ownership suite passed"
