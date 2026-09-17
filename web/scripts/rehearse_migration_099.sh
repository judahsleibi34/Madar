#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WEB_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONTAINER_NAME="madar-099-synthetic-$RANDOM-$$"
POSTGRES_IMAGE="postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73"
BACKEND_TEST_IMAGE="${BACKEND_TEST_IMAGE:-madar-backend-test}"
created=false
cleanup() { if "$created"; then docker rm -f "$CONTAINER_NAME" >/dev/null; fi; }
trap cleanup EXIT
docker run -d --name "$CONTAINER_NAME" --label madar.rehearsal=synthetic-commercial-099 \
  --publish 127.0.0.1:55435:5432 --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=1g \
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
  ((10#$number > 99)) && continue
  docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q < "$migration"
done
docker run --rm --network host --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --env COMMERCIAL_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=55435 dbname=postgres user=postgres connect_timeout=10' \
  --volume "$WEB_ROOT/backend/tests/test_commercial_ledger_database.py:/commercial-tests.py:ro" \
  "$BACKEND_TEST_IMAGE" python /commercial-tests.py
# Validate the exact RLS/grants contract against the freshly migrated database.
docker run --rm --network host --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --env SUPABASE_DB_URL='host=127.0.0.1 port=55435 dbname=postgres user=postgres connect_timeout=10' \
  --volume "$WEB_ROOT/backend/scripts/verify_rls_grants.py:/verify-rls.py:ro" \
  "$BACKEND_TEST_IMAGE" python /verify-rls.py
# Seed a real synthetic ledger transaction, then prove logical restore coverage.
docker exec -i "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
do $$
declare tid integer; actor integer;
begin
  insert into public.tenants(brand_name,owner_name) values('Synthetic backup proof','Synthetic') returning tenant_id into tid;
  select id into actor from public.users where user_type='admin' and account_status='active' limit 1;
  perform public.apply_commercial_access_command(tid,actor,'aal2','manual_payment','synthetic-backup-command','synthetic-backup-request',
    jsonb_build_object('request',jsonb_build_object('plan_id','business','method','cash','actual_minor',2500,'currency','USD',
      'billing_months',1,'paid_at',now(),'valid_from',now(),'valid_until',now()+interval '1 month','receipt_reference','SYNTHETIC-BACKUP','reason','Synthetic restore proof'),
      'quote',jsonb_build_object('expected_minor',2500,'catalog_version','synthetic')));
end $$;
SQL
docker exec "$CONTAINER_NAME" pg_dump -U postgres --format=custom --file=/tmp/commercial-proof.dump postgres
docker exec "$CONTAINER_NAME" createdb -U postgres commercial_restore
docker exec "$CONTAINER_NAME" pg_restore -U postgres --exit-on-error --dbname=commercial_restore /tmp/commercial-proof.dump
docker exec -i "$CONTAINER_NAME" psql -X -U postgres -d commercial_restore -v ON_ERROR_STOP=1 -q <<'SQL'
do $$
begin
  if (select schema_version from public.application_schema_state where contract_key='core')<>99 then raise exception 'restored_schema_mismatch'; end if;
  if exists(select 1 from pg_index where not indisvalid) then raise exception 'restored_invalid_indexes'; end if;
  if (select count(*) from public.commercial_manual_payments)<>1 or (select count(*) from public.commercial_access_periods)<>1
     or (select count(*) from public.commercial_access_events)<>1 then raise exception 'restored_ledger_incomplete'; end if;
  if not exists(select 1 from public.audit_logs where action='admin.commercial.manual_payment') then raise exception 'restored_audit_missing'; end if;
end $$;
SQL
docker exec "$CONTAINER_NAME" sha256sum /tmp/commercial-proof.dump
docker exec "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -At -c "select schema_version from public.application_schema_state where contract_key='core'; select count(*) from pg_index where not indisvalid;"
echo "Migration 099 fresh synthetic upgrade and PostgreSQL regression suite passed"
