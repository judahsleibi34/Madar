#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WEB_ROOT="${ROOT_DIR}/web"
POSTGRES_IMAGE="postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73"
CONTAINER_NAME="madar-staging-chain-${RANDOM}-$$"
BACKUP_FILE="$(mktemp /tmp/madar-schema136-XXXXXX.dump)"

cleanup() {
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  rm -f "${BACKUP_FILE}"
}
trap cleanup EXIT

python3 "${WEB_ROOT}/scripts/check_data_sources_staging_chain.py"

docker run -d --name "${CONTAINER_NAME}" --network none \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=2g \
  -e POSTGRES_HOST_AUTH_METHOD=trust "${POSTGRES_IMAGE}" >/dev/null
for _ in $(seq 1 60); do
  docker exec "${CONTAINER_NAME}" pg_isready -U postgres >/dev/null 2>&1 && break
  sleep 1
done
docker exec "${CONTAINER_NAME}" pg_isready -U postgres >/dev/null

docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres <<'SQL'
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
comment on database postgres is 'madar-data-sources-staging-chain-disposable';
SQL

apply_range() {
  local minimum="$1"
  local maximum="$2"
  local migration number
  for migration in "${WEB_ROOT}"/database/migrations/*.sql; do
    number="$(basename "${migration}" | cut -d_ -f1)"
    if ((10#${number} < minimum || 10#${number} > maximum || 10#${number} == 142)); then
      continue
    fi
    docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "${CONTAINER_NAME}" \
      psql -X -v ON_ERROR_STOP=1 -U postgres -q < "${migration}"
  done
}

apply_range 1 114
docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q \
  -c 'alter table auth.users add column email text'
apply_range 115 136
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select schema_version from public.application_schema_state where contract_key='core'")" = "136"

# A real schema136 backup must be readable and restore to the same contract.
docker exec "${CONTAINER_NAME}" pg_dump -U postgres -Fc postgres > "${BACKUP_FILE}"
test -s "${BACKUP_FILE}"
docker exec "${CONTAINER_NAME}" createdb -U postgres schema136_restore
docker exec -i "${CONTAINER_NAME}" pg_restore -U postgres -d schema136_restore \
  --no-owner --no-privileges < "${BACKUP_FILE}"
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -d schema136_restore -Atc \
  "select schema_version from public.application_schema_state where contract_key='core'")" = "136"
docker exec "${CONTAINER_NAME}" dropdb -U postgres schema136_restore

apply_range 137 153
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select schema_version from public.application_schema_state where contract_key='core'")" = "153"

# A forced rollback of the last transition may not expose partial schema154 DDL.
{
  sed -e '/^begin;$/Id' -e '/^commit;$/Id' \
    "${WEB_ROOT}/database/migrations/154_add_shared_immutable_storage.sql"
  printf '\nselect 1/0;\n'
} | if docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "${CONTAINER_NAME}" \
  psql -X -v ON_ERROR_STOP=1 -U postgres -1 -q; then
  echo 'Forced migration154 failure unexpectedly succeeded' >&2
  exit 1
fi
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select schema_version from public.application_schema_state where contract_key='core'")" = "153"

apply_range 154 154
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select schema_version from public.application_schema_state where contract_key='core'")" = "154"
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select count(*) from public.application_schema_state where contract_key='core'")" = "1"

# Candidate155 remains unselected. Rehearse its rollback and exact continuation.
{
  sed -e '/^begin;$/Id' -e '/^commit;$/Id' \
    "${WEB_ROOT}/database/migrations/155_add_data_source_credential_vault.sql"
  printf '\nselect 1/0;\n'
} | if docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "${CONTAINER_NAME}" \
  psql -X -v ON_ERROR_STOP=1 -U postgres -1 -q; then
  echo 'Forced migration155 failure unexpectedly succeeded' >&2
  exit 1
fi
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select schema_version from public.application_schema_state where contract_key='core'")" = "154"

apply_range 155 155
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select schema_version from public.application_schema_state where contract_key='core'")" = "155"

echo 'Disposable full schema136 -> 155 upgrade, schema136 restore, and schema154/155 rollback passed'
