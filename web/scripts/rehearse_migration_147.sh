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

docker create --memory=768m --cpus=0.75 --pids-limit=128 --name "$CONTAINER_NAME" --label madar.rehearsal=synthetic-notification-147 \
  --publish 127.0.0.1:55448:5432 --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=1g \
  -e POSTGRES_HOST_AUTH_METHOD=trust "$POSTGRES_IMAGE" >/dev/null
created=true
docker start "$CONTAINER_NAME" >/dev/null
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
if [[ "${RUN_SCHEMA148_ADMISSION:-false}" == true ]]; then
  docker run --rm --memory=1g --cpus=1 --pids-limit=256 --network host --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=128m --env PYTHONPATH=/app:/release/web --env PYTHONDONTWRITEBYTECODE=1 \
    --env SCHEMA148_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=55448 dbname=postgres user=postgres connect_timeout=5' \
    --env SCHEMA148_SOURCE_ROOT=/release \
    --env MADAR_TEST_REPOSITORY_ROOT=/release/web \
    --volume "$WEB_ROOT/backend:/app:ro" --volume "$WEB_ROOT/..:/release:ro" \
    --entrypoint python "$BACKEND_TEST_IMAGE" -m unittest tests.test_schema148_cutover_database -v
  if [[ "${RUN_SCHEMA149_ADMISSION:-false}" == true ]]; then
    docker run --rm --memory=1g --cpus=1 --pids-limit=256 --network host --read-only \
      --tmpfs /tmp:rw,noexec,nosuid,size=128m --env PYTHONPATH=/app:/release/web --env PYTHONDONTWRITEBYTECODE=1 \
      --env SCHEMA148_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=55448 dbname=postgres user=postgres connect_timeout=5' \
      --env SCHEMA148_SOURCE_ROOT=/release \
      --env MADAR_TEST_REPOSITORY_ROOT=/release/web \
      --volume "$WEB_ROOT/backend:/app:ro" --volume "$WEB_ROOT/..:/release:ro" \
      --entrypoint python "$BACKEND_TEST_IMAGE" -m unittest tests.test_schema149_cutover_database -v
  fi
  if [[ "${RUN_DELETION_INTEGRITY:-false}" == true ]]; then
    docker run --rm --memory=768m --cpus=1 --pids-limit=256 --network host --read-only \
      --tmpfs /tmp:rw,noexec,nosuid,size=128m --env PYTHONPATH=/app:/release/web --env PYTHONDONTWRITEBYTECODE=1 \
      --env SCHEMA148_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=55448 dbname=postgres user=postgres connect_timeout=5' \
      --env SCHEMA148_SOURCE_ROOT=/release \
      --env MADAR_TEST_REPOSITORY_ROOT=/release/web \
      --volume "$WEB_ROOT/backend:/app:ro" --volume "$WEB_ROOT/..:/release:ro" \
      --entrypoint python "$BACKEND_TEST_IMAGE" -m unittest tests.test_schema150_cutover_database -v
  fi
fi

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
  --volume "$WEB_ROOT/database/historical-architecture-146-150/147_fence_notification_delivery_claims.sql:/migration147.sql:ro" \
  --entrypoint python "$BACKEND_TEST_IMAGE" tests/test_notification_fencing_database.py
echo "Migration147 coordinated rollback/upgrade and native claim ownership suite passed"
if [[ "${RUN_BUSINESS_INTEGRITY:-false}" == true ]]; then
  docker exec "$CONTAINER_NAME" psql -X -U postgres -Atc \
    "select shobj_description(oid,'pg_database') from pg_database where datname=current_database()" \
    | grep -qx madar-notification-synthetic-rehearsal
  before_status_function="$(docker exec "$CONTAINER_NAME" psql -X -U postgres -Atc "select md5(pg_get_functiondef('public.update_builder_reservation_status_notified_safe(uuid,integer,text,timestamptz)'::regprocedure))")"
  {
    printf 'begin;\n'
    sed -e '/^begin;$/Id' -e '/^commit;$/Id' "$WEB_ROOT/database/historical-architecture-146-150/148_guard_reservation_reactivation_capacity.sql"
    printf '\nrollback;\n'
  } | docker exec -i "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q
  docker exec "$CONTAINER_NAME" psql -X -U postgres -Atc \
    "select schema_version=147 and has_table_privilege('service_role','public.builder_reservations','UPDATE') from public.application_schema_state where contract_key='core'" | grep -qx t
  test "$before_status_function" = "$(docker exec "$CONTAINER_NAME" psql -X -U postgres -Atc "select md5(pg_get_functiondef('public.update_builder_reservation_status_notified_safe(uuid,integer,text,timestamptz)'::regprocedure))")"
  docker exec -i "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q \
    < "$WEB_ROOT/database/historical-architecture-146-150/148_guard_reservation_reactivation_capacity.sql"
  docker exec "$CONTAINER_NAME" psql -X -U postgres -Atc \
    "select schema_version=148 from public.application_schema_state where contract_key='core'" | grep -qx t

  docker run --rm --memory=768m --cpus=1 --pids-limit=256 --network host --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m --env PYTHONPATH=/app --env PYTHONDONTWRITEBYTECODE=1 \
    --env BUSINESS_INTEGRITY_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=55448 dbname=postgres user=postgres connect_timeout=5' \
    --volume "$WEB_ROOT/backend:/app:ro" --entrypoint python "$BACKEND_TEST_IMAGE" \
    -m unittest tests.test_native_business_integrity_database -v
  docker run --rm --memory=768m --cpus=1 --pids-limit=256 --network host --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m --env PYTHONPATH=/app --env PYTHONDONTWRITEBYTECODE=1 \
    --env APP_ENV=test --env SUPABASE_URL=http://127.0.0.1:54321 \
    --env SUPABASE_ANON_KEY=madar-ci-placeholder-anon-not-a-secret \
    --env SUPABASE_SERVICE_KEY=madar-ci-placeholder-service-not-a-secret \
    --env BUSINESS_INTEGRITY_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=55448 dbname=postgres user=postgres connect_timeout=5' \
    --volume "$WEB_ROOT/backend:/app:ro" --entrypoint python "$BACKEND_TEST_IMAGE" \
    -m unittest tests.test_calendar_event_concurrency_database -v
  if replay_output="$(docker exec -i "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q \
      < "$WEB_ROOT/database/historical-architecture-146-150/148_guard_reservation_reactivation_capacity.sql" 2>&1)"; then
    echo "Migration148 unexpectedly accepted re-entry" >&2
    exit 1
  fi
  [[ "$replay_output" == *migration_148_expected_schema_147* ]]
  docker exec "$CONTAINER_NAME" psql -X -U postgres -Atc \
    "select schema_version=148 from public.application_schema_state where contract_key='core'" | grep -qx t
  echo "Migration148 rollback, native business integrity and re-entry refusal passed"
fi

if [[ "${RUN_OUTBOX_INTEGRITY:-false}" == true ]]; then
  docker run --rm --memory=768m --cpus=1 --pids-limit=256 --network host --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m --env PYTHONPATH=/app --env PYTHONDONTWRITEBYTECODE=1 \
    --env APP_ENV=test --env EMAIL_CHANNEL_ENABLED=false --env WEB_PUSH_ENABLED=false \
    --env SUPABASE_URL=http://127.0.0.1:54321 \
    --env SUPABASE_ANON_KEY=madar-ci-placeholder-anon-not-a-secret \
    --env SUPABASE_SERVICE_KEY=madar-ci-placeholder-service-not-a-secret \
    --env OUTBOX_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=55448 dbname=postgres user=postgres connect_timeout=5' \
    --env OUTBOX_MIGRATION_SQL=/migration149.sql \
    --volume "$WEB_ROOT/backend:/app:ro" \
    --volume "$WEB_ROOT/database/historical-architecture-146-150/149_fence_notification_outbox_claims.sql:/migration149.sql:ro" \
    --entrypoint python "$BACKEND_TEST_IMAGE" tests/test_notification_outbox_fencing_database.py
  echo "Migration149 coordinated rollback/upgrade and native outbox ownership suite passed"
  # New queue ACLs must preserve transactional business notification enqueuers.
  # Repeat the same22 business invariants on149, after all fencing cases.
  docker run --rm --memory=768m --cpus=1 --pids-limit=256 --network host --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m --env PYTHONPATH=/app --env PYTHONDONTWRITEBYTECODE=1 \
    --env BUSINESS_INTEGRITY_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=55448 dbname=postgres user=postgres connect_timeout=5' \
    --volume "$WEB_ROOT/backend:/app:ro" --entrypoint python "$BACKEND_TEST_IMAGE" \
    -m unittest tests.test_native_business_integrity_database -v
  echo "Schema149 reservation, inventory/order and simulated payment invariants passed"
fi

if [[ "${RUN_DELETION_INTEGRITY:-false}" == true ]]; then
  docker exec "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q -c 'alter role service_role bypassrls'
  docker run --rm --memory=768m --cpus=1 --pids-limit=256 --network host --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m --env PYTHONPATH=/app --env PYTHONDONTWRITEBYTECODE=1 \
    --env APP_ENV=test --env SUPABASE_URL=http://127.0.0.1:54321 \
    --env SUPABASE_ANON_KEY=madar-ci-placeholder-anon-not-a-secret \
    --env SUPABASE_SERVICE_KEY=madar-ci-placeholder-service-not-a-secret \
    --env DELETION_FENCING_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=55448 dbname=postgres user=postgres connect_timeout=5' \
    --env SCHEMA150_LEGACY_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=55448 dbname=postgres user=postgres connect_timeout=5' \
    --env MADAR_TEST_REPOSITORY_ROOT=/test-repository \
    --env DELETION_MIGRATION_SQL=/migration150.sql \
    --volume "$WEB_ROOT/backend:/app:ro" \
    --volume "$WEB_ROOT/deployment:/test-repository/deployment:ro" \
    --volume "$WEB_ROOT/database/historical-architecture-146-150/150_fence_data_deletion_ownership.sql:/migration150.sql:ro" \
    --entrypoint python "$BACKEND_TEST_IMAGE" -m unittest \
    tests.test_schema150_legacy_admission_database tests.test_data_deletion_fencing_database -v
  # Revalidate retained transaction/tenant/version invariants at the corrected
  # target too;148/149 executions alone do not establish150 compatibility.
  docker run --rm --memory=768m --cpus=1 --pids-limit=256 --network host --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m --env PYTHONPATH=/app --env PYTHONDONTWRITEBYTECODE=1 \
    --env APP_ENV=test --env SUPABASE_URL=http://127.0.0.1:54321 \
    --env SUPABASE_ANON_KEY=madar-ci-placeholder-anon-not-a-secret \
    --env SUPABASE_SERVICE_KEY=madar-ci-placeholder-service-not-a-secret \
    --env BUSINESS_INTEGRITY_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=55448 dbname=postgres user=postgres connect_timeout=5' \
    --volume "$WEB_ROOT/backend:/app:ro" --entrypoint python "$BACKEND_TEST_IMAGE" \
    -m unittest tests.test_native_business_integrity_database tests.test_calendar_event_concurrency_database -v
  echo "Schema150 reservation, stock, order/payment and calendar invariants passed"
  # A committed metadata RPC can lose its response. Retain its referenced
  # private bytes and quota instead of treating transport failure as rollback.
  docker run --rm --memory=512m --cpus=0.5 --pids-limit=128 --network host --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=128m --env PYTHONPATH=/app --env PYTHONDONTWRITEBYTECODE=1 \
    --env APP_ENV=test --env SUPABASE_URL=http://127.0.0.1:54321 \
    --env SUPABASE_ANON_KEY=madar-ci-placeholder-anon-not-a-secret \
    --env SUPABASE_SERVICE_KEY=madar-ci-placeholder-service-not-a-secret \
    --env PUBLIC_UPLOADS_DIR=/tmp/madar-test/public --env DATA_UPLOAD_DIR=/tmp/madar-test/data \
    --env PRIVATE_CHARTS_DIR=/tmp/madar-test/charts --env MADAR_UPLOAD_WORKSPACE_DIR=/tmp/madar-test/parser \
    --env MPLCONFIGDIR=/tmp/matplotlib --env XDG_CACHE_HOME=/tmp/cache --env PYGWALKER_TELEMETRY_ENABLED=false \
    --env LEARNING_PRIVATE_UPLOAD_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=55448 dbname=postgres user=postgres connect_timeout=5' \
    --volume "$WEB_ROOT/backend:/app:ro" --entrypoint python "$BACKEND_TEST_IMAGE" \
    -m unittest tests.test_learning_private_upload_ack_database -v
  echo "Schema150 committed private-upload metadata retains referenced bytes after acknowledgement loss"
fi
