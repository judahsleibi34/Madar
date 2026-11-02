#!/usr/bin/env bash
# Disposable negative acceptance plus retained schema160 fencing acceptance.
set -euo pipefail
umask 077
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${MADAR_REHEARSAL_PYTHON:-python3}"
RUN_ID="deletion166-${RANDOM}-$$"
PG_NAME="madar-${RUN_ID}-pg"
REST_NAME="madar-${RUN_ID}-rest"
VAULT_NAME="madar-${RUN_ID}-vault"
VAULT_STARTED=NO
NETWORK="madar-${RUN_ID}"
EVIDENCE="$(mktemp -d /tmp/madar-deletion166-XXXXXX)"
PG_IMAGE='postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73'
REST_IMAGE='public.ecr.aws/supabase/postgrest@sha256:d155c6718ed9a9f990d159a2ab7c0a3f16944dbb6d0a0344557421042acfe0df'
cleanup() {
  docker logs "${PG_NAME}" >"${EVIDENCE}/postgres.log" 2>&1 || true
  docker logs "${REST_NAME}" >"${EVIDENCE}/postgrest.log" 2>&1 || true
  docker rm -f "${REST_NAME}" "${PG_NAME}" >/dev/null 2>&1 || true
  if [[ "${VAULT_STARTED}" == YES ]]; then docker rm -f "${VAULT_NAME}" >/dev/null 2>&1 || true; fi
  rm -f "${EVIDENCE}/vault-token"
  docker network rm "${NETWORK}" >/dev/null 2>&1 || true
}
trap cleanup EXIT
printf 'Private evidence: %s\n' "${EVIDENCE}"
mkdir -m 0700 "${EVIDENCE}/private-tmp"
export TMPDIR="${EVIDENCE}/private-tmp"
mkdir -m 0700 "${EVIDENCE}/restore-control"
export ACCOUNT_ERASURE_RESTORE_FLOOR_FILE="${EVIDENCE}/restore-control/floor.json"
docker network create "${NETWORK}" >/dev/null
docker run -d --name "${PG_NAME}" --network "${NETWORK}" --network-alias pg \
  -p 127.0.0.1::5432 --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=2g \
  -e POSTGRES_HOST_AUTH_METHOD=scram-sha-256 -e POSTGRES_PASSWORD=disposable-only \
  "${PG_IMAGE}" >/dev/null
for _ in $(seq 1 60); do
  docker exec "${PG_NAME}" pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1 && break
  sleep 0.5
done
docker exec "${PG_NAME}" pg_isready -h 127.0.0.1 -U postgres >/dev/null
docker exec -i "${PG_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres >"${EVIDENCE}/bootstrap.log" <<'SQL'
create role anon nologin; create role authenticated nologin;
create role service_role nologin bypassrls;
create role authenticator noinherit login password 'disposable-rest-only';
grant anon,authenticated,service_role to authenticator;
create schema auth;
create table auth.users(id uuid primary key,email_confirmed_at timestamptz,confirmed_at timestamptz);
create function auth.uid() returns uuid language sql stable as $$select coalesce(nullif(current_setting('request.jwt.claim.sub',true),''),nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'sub')::uuid$$;
create schema storage;
create table storage.buckets(id text primary key,name text not null,public boolean not null default false,file_size_limit bigint,allowed_mime_types text[]);
create table storage.objects(id uuid primary key default gen_random_uuid(),bucket_id text references storage.buckets(id),name text);
alter table storage.objects enable row level security;
create schema extensions; create extension pgcrypto schema extensions;
comment on database postgres is 'madar-notification-synthetic-rehearsal';
SQL
apply_range() {
  local minimum="$1" maximum="$2" migration number
  for migration in "${ROOT_DIR}"/web/database/migrations/*.sql; do
    number="$(basename "${migration}" | cut -d_ -f1)"
    if ((10#${number}<minimum || 10#${number}>maximum || 10#${number}==142)); then continue; fi
    docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "${PG_NAME}" \
      psql -X -v ON_ERROR_STOP=1 -U postgres -q <"${migration}" >>"${EVIDENCE}/migrations.log" 2>&1
  done
}
apply_range 1 114
docker exec "${PG_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q -c 'alter table auth.users add column email text'
apply_range 115 160
PG_PORT="$(docker port "${PG_NAME}" 5432/tcp | cut -d: -f2)"
export DELETION_FENCING_SYNTHETIC_DATABASE_DSN="host=127.0.0.1 port=${PG_PORT} dbname=postgres user=postgres password=disposable-only"
export MADAR_ENV_FILE=/dev/null MADAR_ENV_OVERRIDE=false
export SUPABASE_URL=http://127.0.0.1:1 SUPABASE_ANON_KEY=disposable-anon SUPABASE_SERVICE_KEY=disposable-service
export PYTHONPATH="${ROOT_DIR}/web/backend:${ROOT_DIR}/web"
cd "${ROOT_DIR}/web/backend"
"${PYTHON}" - >"${EVIDENCE}/schema160.log" 2>&1 <<'PY'
import unittest
from tests.test_data_deletion_fencing_database import Deletion150OwnershipTests, Deletion150WorkflowTests
suite = unittest.TestSuite()
for cls in (Deletion150OwnershipTests, Deletion150WorkflowTests):
    for name in unittest.defaultTestLoader.getTestCaseNames(cls):
        # This one asserts the archived schema150 controller's exact horizon,
        # not the retained ownership RPCs. It must not be retargeted to160.
        if name == 'test_new150_pending_request_is_not_classified_as_legacy_backlog':
            print('NOT APPLICABLE: archived schema150 controller quiescence test at canonical160')
            continue
        suite.addTest(cls(name))
raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
PY
for version in $(seq 160 166); do
  if ((version>160)); then apply_range "${version}" "${version}"; fi
  docker exec "${PG_NAME}" psql -X -U postgres -Atc \
    "select schema_version,public.data_deletion_ownership_protocol() from public.application_schema_state where contract_key='core'" >>"${EVIDENCE}/protocol-matrix.txt"
done
if [[ "${MADAR_DELETION167:-NO}" == YES ]]; then
  "${PYTHON}" "${ROOT_DIR}/web/scripts/check_account_recovery_candidate.py" >"${EVIDENCE}/candidate167.json"
  MIGRATION167="${ROOT_DIR}/web/database/migrations/167_add_account_recovery_hold.sql"
  docker exec -i "${PG_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q <<'SQL'
alter table auth.users add column banned_until timestamptz;
create table auth.sessions(id uuid primary key,user_id uuid not null references auth.users(id) on delete cascade);
create table auth.refresh_tokens(id bigserial primary key,token text not null unique,user_id uuid not null references auth.users(id) on delete cascade,session_id uuid references auth.sessions(id) on delete cascade);
alter table storage.objects add column owner_id uuid;
SQL
  # Admission must refuse unreconciled legacy work before changing DDL/ACLs.
  docker exec "${PG_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q -c \
    "insert into public.data_deletion_requests(id,request_type,target_user_id_snapshot) values('16700000-0000-4000-8000-000000000001','user',2147483000)"
  if docker exec -i "${PG_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q <"${MIGRATION167}" >"${EVIDENCE}/167-backlog.log" 2>&1; then
    echo 'Candidate167 incorrectly accepted legacy backlog' >&2;exit 1
  fi
  rg -q 'migration_167_requires_reconciled_deletion_backlog' "${EVIDENCE}/167-backlog.log"
  docker exec "${PG_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q -c \
    "delete from public.data_deletion_requests where id='16700000-0000-4000-8000-000000000001'"
  { sed -e '/^begin;$/d' -e '/^commit;$/d' "${MIGRATION167}";printf '\nselect 1/0;\n'; } |
    if docker exec -i "${PG_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -1 -q >"${EVIDENCE}/167-rollback.log" 2>&1; then
      echo 'Candidate167 forced rollback incorrectly succeeded' >&2;exit 1
    fi
  rg -q 'division by zero' "${EVIDENCE}/167-rollback.log"
  test "$(docker exec "${PG_NAME}" psql -X -U postgres -Atc "select schema_version=166 and to_regclass('public.account_lifecycles167') is null and to_regprocedure('public.create_data_deletion_request160(text,integer,integer,integer,timestamptz)') is null from public.application_schema_state where contract_key='core'")" = t
  docker exec -i "${PG_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q <"${MIGRATION167}" >"${EVIDENCE}/167-a.log" 2>&1 & A167=$!
  docker exec -i "${PG_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q <"${MIGRATION167}" >"${EVIDENCE}/167-b.log" 2>&1 & B167=$!
  set +e;wait "${A167}";AS167=$?;wait "${B167}";BS167=$?;set -e
  if ! { [[ "${AS167}" == 0 && "${BS167}" != 0 ]] || [[ "${BS167}" == 0 && "${AS167}" != 0 ]]; }; then
    echo 'Candidate167 competing migration admission failed' >&2;exit 1
  fi
  rg -q 'migration_167_expected_schema_166' "${EVIDENCE}/167-a.log" "${EVIDENCE}/167-b.log"
fi
JWT_SECRET="$(openssl rand -hex 32)"
export DELETION166_JWT_SECRET="${JWT_SECRET}"
export DELETION166_SERVICE_JWT="$(JWT_SECRET="${JWT_SECRET}" "${PYTHON}" -c 'import jwt,os,time;print(jwt.encode({"role":"service_role","exp":int(time.time())+600},os.environ["JWT_SECRET"],algorithm="HS256"))')"
export DELETION166_ANON_JWT="$(JWT_SECRET="${JWT_SECRET}" "${PYTHON}" -c 'import jwt,os,time;print(jwt.encode({"role":"authenticated","exp":int(time.time())+600},os.environ["JWT_SECRET"],algorithm="HS256"))')"
docker run -d --name "${REST_NAME}" --network "${NETWORK}" -p 127.0.0.1::3000 \
  -e PGRST_DB_URI='postgres://authenticator:disposable-rest-only@pg:5432/postgres' \
  -e PGRST_DB_SCHEMAS=public -e PGRST_DB_ANON_ROLE=anon \
  -e PGRST_JWT_SECRET="${JWT_SECRET}" -e PGRST_DB_CONFIG=false "${REST_IMAGE}" >/dev/null
REST_PORT="$(docker port "${REST_NAME}" 3000/tcp | cut -d: -f2)"
export DELETION166_REST_URL="http://127.0.0.1:${REST_PORT}"
if [[ "${MADAR_ERASURE_VAULT:-NO}" == YES ]]; then
  test "${MADAR_DELETION167:-NO}" = YES
  VAULT_IMAGE='hashicorp/vault@sha256:5be49781ecf78bfe775c5309c6a4d9f4e9e040b6c885c99eb2b12fb69855e1a2'
  ROOT_TOKEN="$(openssl rand -hex 32)"
  docker run -d --name "${VAULT_NAME}" --network "${NETWORK}" -p 127.0.0.1::8200 \
    -e VAULT_DEV_ROOT_TOKEN_ID="${ROOT_TOKEN}" -e VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200 \
    -v "${ROOT_DIR}/web/deployment/vault/data-sources-transit-policy.hcl:/vault/data-sources-policy.hcl:ro" \
    "${VAULT_IMAGE}" server -dev >/dev/null
  VAULT_STARTED=YES
  for _ in $(seq 1 60); do
    docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN="${ROOT_TOKEN}" "${VAULT_NAME}" vault status >/dev/null 2>&1 && break
    sleep 0.25
  done
  for action in 'secrets enable transit' 'write transit/keys/madar-data-sources derived=true exportable=false allow_plaintext_backup=false' 'policy write madar-data-sources /vault/data-sources-policy.hcl'; do
    # Fixed fixture-owned CLI words; no user-controlled command evaluation.
    read -r -a vault_args <<<"${action}"
    docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN="${ROOT_TOKEN}" "${VAULT_NAME}" vault "${vault_args[@]}" >/dev/null
  done
  APP_TOKEN="$(docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN="${ROOT_TOKEN}" "${VAULT_NAME}" vault token create -policy=madar-data-sources -ttl=20m -explicit-max-ttl=30m -field=token)"
  printf '%s' "${APP_TOKEN}" >"${EVIDENCE}/vault-token"
  chmod 0400 "${EVIDENCE}/vault-token"
  VAULT_PORT="$(docker port "${VAULT_NAME}" 8200/tcp | cut -d: -f2)"
  export APP_ENV=test DATA_SOURCE_CREDENTIAL_ENVIRONMENT=test DATA_SOURCE_VAULT_ADDR="http://127.0.0.1:${VAULT_PORT}"
  export DATA_SOURCE_VAULT_TOKEN_FILE="${EVIDENCE}/vault-token" DATA_SOURCE_VAULT_TRANSIT_KEY=madar-data-sources
fi
if [[ "${MADAR_DELETION167:-NO}" == YES ]]; then
  # Catalog only: no customer row values or credentials in coverage evidence.
  docker exec -i "${PG_NAME}" psql -X -U postgres -At >"${EVIDENCE}/coverage-schema.json" <<'SQL'
select json_agg(x order by x.relname) from (
 select c.relname,
 (select json_agg(json_build_object('name',a.attname,'type',format_type(a.atttypid,a.atttypmod)) order by a.attnum) from pg_attribute a where a.attrelid=c.oid and a.attnum>0 and not a.attisdropped) as columns,
 (select json_agg(pg_get_constraintdef(f.oid)) from pg_constraint f where f.conrelid=c.oid and f.contype='f') as foreign_keys,
 (select json_agg(t.tgname) from pg_trigger t where t.tgrelid=c.oid and not t.tgisinternal) as triggers
 from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind='r'
) x;
SQL
  "${PYTHON}" -m unittest -v tests.test_account_lifecycle_database >"${EVIDENCE}/schema167.log" 2>&1
else
  "${PYTHON}" -m unittest -v tests.test_schema166_deletion_compatibility_database >"${EVIDENCE}/schema166.log" 2>&1
fi
printf 'Regression checks passed; permanent deletion acceptance remains BLOCKED. Evidence: %s\n' "${EVIDENCE}"
