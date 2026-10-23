#!/usr/bin/env bash
set -euo pipefail

if [[ "${MADAR_CANONICAL_EXECUTOR_TESTS:-false}" == true && "${MADAR_RECONCILED_INTEGRITY_TESTS:-false}" == true ]]; then
  echo 'Choose either canonical executor acceptance or data-source/integrity acceptance; neither replaces the other' >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WEB_ROOT="${ROOT_DIR}/web"
POSTGRES_IMAGE="postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73"
CONTAINER_NAME="madar-staging-chain-${RANDOM}-$$"
CONTAINER_ID=''
BACKUP_FILE="$(mktemp /tmp/madar-schema136-XXXXXX.dump)"

cleanup() {
  if [[ -n "${CONTAINER_ID}" ]]; then
    if [[ "$(docker inspect --format '{{ index .Config.Labels "madar.rehearsal" }}' "${CONTAINER_ID}")" != 'data-source-chain' ]]; then
      echo 'Refusing cleanup of an unverified rehearsal container' >&2
      return 1
    fi
    docker rm -f "${CONTAINER_ID}" >/dev/null
  fi
  rm -f "${BACKUP_FILE}"
}
trap cleanup EXIT

python3 "${WEB_ROOT}/scripts/check_data_sources_staging_chain.py"

CONTAINER_ID="$(docker run -d --name "${CONTAINER_NAME}" --network none \
  --label madar.rehearsal=data-source-chain --memory=2g --cpus=1 --pids-limit=256 \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=2g \
  -e POSTGRES_HOST_AUTH_METHOD=trust "${POSTGRES_IMAGE}")"
for _ in $(seq 1 60); do
  # initdb's temporary server accepts Unix-socket connections, then exits.
  # Only the final server listens on TCP; do not admit that temporary window.
  docker exec "${CONTAINER_ID}" pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1 && break
  sleep 1
done
docker exec "${CONTAINER_ID}" pg_isready -h 127.0.0.1 -U postgres >/dev/null

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

apply_range 137 146
 test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select schema_version from public.application_schema_state where contract_key='core'")" = "146"
 echo 'Authoritative schema146 origin positively observed before main147–156'
# An explicit SQL-executor-only mode starts at the positively observed146.
# It does not certify the root controller, backup, providers or write issuer.
if [[ "${MADAR_CANONICAL_EXECUTOR_TESTS:-false}" == true ]]; then
  # Exercise the real application login with SCRAM, not the harness's admin
  # trust connection. The cluster is owned, network-isolated and disposable.
  docker exec -u postgres "${CONTAINER_ID}" sh -ec \
    'sed -i "1i host all authenticator 127.0.0.1/32 scram-sha-256" "$PGDATA/pg_hba.conf"'
  docker exec "${CONTAINER_ID}" psql -X -U postgres -v ON_ERROR_STOP=1 -q -c 'select pg_reload_conf()'
  docker exec "${CONTAINER_NAME}" psql -X -U postgres -v ON_ERROR_STOP=1 -q -c \
    "comment on database postgres is 'madar-notification-synthetic-rehearsal'"
  docker run --rm --read-only --memory=2g --cpus=1 --pids-limit=256 \
    --network "container:${CONTAINER_NAME}" --tmpfs /tmp:rw,noexec,nosuid,size=256m \
    --volume "${WEB_ROOT}/backend:/app:ro" --volume "${ROOT_DIR}:/release:ro" \
    --env PYTHONPATH=/app:/release/web --env PYTHONDONTWRITEBYTECODE=1 \
    --env MADAR_TEST_REPOSITORY_ROOT=/release/web \
    --env SUPABASE_URL=http://127.0.0.1:54321 \
    --env APP_ENV=test --env SUPABASE_ANON_KEY=synthetic-placeholder-anon --env SUPABASE_SERVICE_KEY=synthetic-placeholder-service \
    --env CANONICAL_EXECUTOR_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=5432 dbname=postgres user=postgres' \
    --env BUSINESS_INTEGRITY_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=5432 dbname=postgres user=postgres' \
    --env RECONCILED_SOURCE_ROOT=/release \
    --entrypoint python "${BACKEND_TEST_IMAGE:-madar-backend-test}" -m unittest \
      tests.test_schema160_executor_database -v
  echo 'Canonical SQL executor and calendar transaction acceptance only; full protected application upgrade NOT TESTED'
  exit 0
fi

apply_range 147 153
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

# Candidate156 remains unselected. Prove all DDL rolls back on failure.
{
  sed -e '/^begin;$/Id' -e '/^commit;$/Id' \
    "${WEB_ROOT}/database/migrations/156_add_automatic_source_synchronization.sql"
  printf '\nselect 1/0;\n'
} | if docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "${CONTAINER_NAME}" \
  psql -X -v ON_ERROR_STOP=1 -U postgres -1 -q; then
  echo 'Forced migration156 failure unexpectedly succeeded' >&2
  exit 1
fi
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select schema_version from public.application_schema_state where contract_key='core'")" = "155"
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select to_regclass('public.data_source_sync_schedules') is null")" = "t"

# Hold the core row and run two complete migration sessions. Exactly one may win.
TMP_156="$(mktemp -d)"
docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -c \
  "begin;select schema_version from public.application_schema_state where contract_key='core' for update;select pg_sleep(2);commit;" \
  >"${TMP_156}/blocker.log" 2>&1 & BLOCKER_PID=$!
for _ in $(seq 1 20); do
  docker exec "${CONTAINER_NAME}" psql -X -At -U postgres -c \
    "select count(*) from pg_stat_activity where query like '%select pg_sleep(2)%' and state='active'" \
    | grep -qx 1 && break
  sleep 0.1
done
docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres \
  < "${WEB_ROOT}/database/migrations/156_add_automatic_source_synchronization.sql" \
  >"${TMP_156}/a.log" 2>&1 & A_PID=$!
docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres \
  < "${WEB_ROOT}/database/migrations/156_add_automatic_source_synchronization.sql" \
  >"${TMP_156}/b.log" 2>&1 & B_PID=$!
set +e
wait "${A_PID}"; A_STATUS=$?
wait "${B_PID}"; B_STATUS=$?
wait "${BLOCKER_PID}"; BLOCKER_STATUS=$?
set -e
if [[ "${BLOCKER_STATUS}" -ne 0 ]] \
   || ! { [[ "${A_STATUS}" -eq 0 && "${B_STATUS}" -ne 0 ]] \
        || [[ "${B_STATUS}" -eq 0 && "${A_STATUS}" -ne 0 ]]; }; then
  cat "${TMP_156}/a.log" "${TMP_156}/b.log" >&2
  echo 'Competing migration156 sessions were not serialized' >&2
  exit 1
fi
FAILED_LOG="${TMP_156}/a.log"
[[ "${A_STATUS}" -eq 0 ]] && FAILED_LOG="${TMP_156}/b.log"
grep -q 'migration_156_expected_schema_155_got_156' "${FAILED_LOG}"
rm -rf "${TMP_156}"
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select schema_version from public.application_schema_state where contract_key='core'")" = "156"

# Exercise due/disabled selection and two real dispatcher processes.
docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres <<'SQL'
insert into auth.users(id,email,email_confirmed_at,confirmed_at)
values('70000000-0000-4000-8000-000000000001','sync@example.invalid',now(),now());
insert into public.tenants(tenant_id,brand_name,owner_name) values(7001,'Sync','Owner');
insert into public.users(id,auth_id,first_name,last_name,email,tenant_id,account_kind,account_status)
overriding system value values(7001,'70000000-0000-4000-8000-000000000001','Sync','Owner',
  'sync@example.invalid',7001,'platform','active');
insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status)
values(7001,7001,'70000000-0000-4000-8000-000000000001','owner','active');
insert into public.builder_projects(id,tenant_id,owner_user_id,name,slug,status,draft_schema)
values('70000000-0000-4000-8000-000000000002',7001,7001,'Sync project','sync-project','draft',
  '{"workspaceKind":"data"}'::jsonb);
insert into public.data_sources(id,tenant_id,project_id,creator_user_id,source_type,
  display_name,status,provider_key,resource_type)
values('70000000-0000-4000-8000-000000000003',7001,
  '70000000-0000-4000-8000-000000000002',7001,'api_provider','Fixture','active',
  'http_fixture','records');
insert into public.data_source_resources(id,tenant_id,project_id,source_id,resource_key)
values('70000000-0000-4000-8000-000000000004',7001,
  '70000000-0000-4000-8000-000000000002','70000000-0000-4000-8000-000000000003','records');
select public.configure_data_source_sync156(7001,'70000000-0000-4000-8000-000000000002',
  '70000000-0000-4000-8000-000000000003','70000000-0000-4000-8000-000000000004',
  7001,false,900,null);
do $$ begin
  if exists(select 1 from public.claim_due_data_source_syncs156('disabled',5,900,2,4,now())) then
    raise exception 'disabled schedule was claimed';end if;
end $$;
select public.configure_data_source_sync156(7001,'70000000-0000-4000-8000-000000000002',
  '70000000-0000-4000-8000-000000000003','70000000-0000-4000-8000-000000000004',
  7001,true,900,0);
SQL

docker exec "${CONTAINER_NAME}" psql -X -At -v ON_ERROR_STOP=1 -U postgres -c \
  "select schedule_id from public.claim_due_data_source_syncs156('dispatcher-a',1,60,1,1,now())" \
  >"/tmp/${CONTAINER_NAME}-claim-a" & CLAIM_A_PID=$!
docker exec "${CONTAINER_NAME}" psql -X -At -v ON_ERROR_STOP=1 -U postgres -c \
  "select schedule_id from public.claim_due_data_source_syncs156('dispatcher-b',1,60,1,1,now())" \
  >"/tmp/${CONTAINER_NAME}-claim-b" & CLAIM_B_PID=$!
wait "${CLAIM_A_PID}"
wait "${CLAIM_B_PID}"
CLAIM_COUNT="$(awk 'NF {n++} END {print n+0}' "/tmp/${CONTAINER_NAME}-claim-a" "/tmp/${CONTAINER_NAME}-claim-b")"
rm -f "/tmp/${CONTAINER_NAME}-claim-a" "/tmp/${CONTAINER_NAME}-claim-b"
test "${CLAIM_COUNT}" = "1"

docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres <<'SQL'
do $$
declare v_schedule public.data_source_sync_schedules;v_old uuid;v_new uuid;
begin
  select * into v_schedule from public.data_source_sync_schedules where tenant_id=7001;
  v_old:=v_schedule.lease_token;
  update public.data_source_sync_schedules set lease_expires_at=now()-interval '1 second'
  where id=v_schedule.id;
  perform * from public.reconcile_expired_source_syncs156('reconciler',10,now());
  update public.data_source_sync_schedules set next_due_at=now()-interval '180 days'
  where id=v_schedule.id;
  select lease_token into v_new from public.claim_due_data_source_syncs156('after-outage',5,900,2,4,now());
  if v_new is null or v_new=v_old then raise exception 'stale lease was not recovered';end if;
  if (select count(*) from public.data_source_sync_attempts where schedule_id=v_schedule.id)<>2 then
    raise exception 'extended outage created an unexpected backlog';end if;
  begin
    perform public.heartbeat_source_sync156(v_schedule.id,v_old,v_schedule.fence,900);
    raise exception 'stale worker remained authorized';
  exception when sqlstate 'P0001' then null;end;
end $$;
SQL

echo 'Disposable full schema136 -> 156 upgrade, rollback, migration locking, and dispatcher concurrency passed'

# Explicit disposable test opt-in only; no operational controller/authority.
if [[ "${MADAR_RECONCILED_INTEGRITY_TESTS:-false}" == true ]]; then
  docker exec "${CONTAINER_NAME}" psql -X -U postgres -v ON_ERROR_STOP=1 -q -c \
    "comment on database postgres is 'madar-notification-synthetic-rehearsal'"
  docker run --rm --read-only --memory=2g --cpus=1 --pids-limit=256 \
    --network "container:${CONTAINER_NAME}" --tmpfs /tmp:rw,noexec,nosuid,size=256m \
    --volume "${WEB_ROOT}/backend:/app:ro" --volume "${ROOT_DIR}:/release:ro" \
    --env PYTHONPATH=/app:/release/web --env PYTHONDONTWRITEBYTECODE=1 \
    --env SUPABASE_URL=http://127.0.0.1:54321 \
    --env APP_ENV=test --env SUPABASE_ANON_KEY=synthetic-placeholder-anon --env SUPABASE_SERVICE_KEY=synthetic-placeholder-service \
    --env RECONCILED_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=5432 dbname=postgres user=postgres' \
    --env RECONCILED_SOURCE_ROOT=/release \
    --env NOTIFICATION_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=5432 dbname=postgres user=postgres' \
    --env OUTBOX_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=5432 dbname=postgres user=postgres' \
    --env DELETION_FENCING_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=5432 dbname=postgres user=postgres' \
    --env BUSINESS_INTEGRITY_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=5432 dbname=postgres user=postgres' \
    --env DELIVERY_TEST_SCHEMA=160 --env OUTBOX_TEST_SCHEMA=160 \
    --entrypoint python "${BACKEND_TEST_IMAGE:-madar-backend-test}" -m unittest \
      tests.test_reconciled_history_database.TransitionTests \
      tests.test_reconciled_history_database.ReconciledDeliveryTests \
      tests.test_reconciled_history_database.ReconciledOutboxTests \
      tests.test_reconciled_history_database.ReconciledDeletionTests \
      tests.test_data_deletion_fencing_database.Deletion150WorkflowTests \
      tests.test_native_business_integrity_database -v
fi
