#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WEB_ROOT="${ROOT_DIR}/web"
POSTGRES_IMAGE="${MADAR_DISPOSABLE_POSTGRES_IMAGE:-postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73}"
CONTAINER_NAME="madar-webhook162-${RANDOM}-$$"
TMP_DIR="$(mktemp -d /tmp/madar-webhook162-XXXXXX)"

cleanup() {
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

python3 "${WEB_ROOT}/scripts/webhook_candidate.py"
docker run -d --name "${CONTAINER_NAME}" --network none \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=2g \
  -e POSTGRES_HOST_AUTH_METHOD=trust "${POSTGRES_IMAGE}" >/dev/null
for _ in $(seq 1 90); do
  docker exec "${CONTAINER_NAME}" pg_isready -U postgres >/dev/null 2>&1 && break
  sleep 1
done
docker exec "${CONTAINER_NAME}" pg_isready -U postgres >/dev/null

docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres <<'SQL'
create role anon nologin;
create role authenticated nologin;
create role service_role nologin;
create schema auth;
create table auth.users(id uuid primary key,email_confirmed_at timestamptz,confirmed_at timestamptz);
create function auth.uid() returns uuid language sql stable as $$select null::uuid$$;
create schema storage;
create table storage.buckets(id text primary key,name text not null,public boolean not null default false,file_size_limit bigint,allowed_mime_types text[]);
create table storage.objects(id uuid primary key default gen_random_uuid(),bucket_id text references storage.buckets(id),name text);
alter table storage.objects enable row level security;
create schema extensions;
create extension pgcrypto schema extensions;
comment on database postgres is 'madar-webhook162-disposable';
SQL

apply_range() {
  local minimum="$1" maximum="$2" migration number
  for migration in "${WEB_ROOT}"/database/migrations/*.sql; do
    number="$(basename "${migration}" | cut -d_ -f1)"
    if ((10#${number}<minimum || 10#${number}>maximum || 10#${number}==142)); then continue; fi
    docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "${CONTAINER_NAME}" \
      psql -X -v ON_ERROR_STOP=1 -U postgres -q < "${migration}"
  done
}

apply_range 1 114
docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q -c 'alter table auth.users add column email text'
apply_range 115 161
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select schema_version from public.application_schema_state where contract_key='core'")" = 161

# Forced failure proves all schema162 DDL and version advancement are transactional.
{
  sed -e '/^begin;$/Id' -e '/^commit;$/Id' "${WEB_ROOT}/database/migrations/162_add_secure_webhook_ingestion.sql"
  printf '\nselect 1/0;\n'
} | if docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "${CONTAINER_NAME}" \
  psql -X -v ON_ERROR_STOP=1 -U postgres -1 -q; then
  echo 'Forced migration162 failure unexpectedly succeeded' >&2; exit 1
fi
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select schema_version from public.application_schema_state where contract_key='core'")" = 161
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select to_regclass('public.data_source_webhook_events') is null")" = t

# Two sessions contend for the locked transition. Exactly one can pass 161→162.
docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres \
  < "${WEB_ROOT}/database/migrations/162_add_secure_webhook_ingestion.sql" >"${TMP_DIR}/a.log" 2>&1 & A_PID=$!
docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres \
  < "${WEB_ROOT}/database/migrations/162_add_secure_webhook_ingestion.sql" >"${TMP_DIR}/b.log" 2>&1 & B_PID=$!
set +e
wait "${A_PID}"; A_STATUS=$?
wait "${B_PID}"; B_STATUS=$?
set -e
if ! { [[ "${A_STATUS}" -eq 0 && "${B_STATUS}" -ne 0 ]] || [[ "${B_STATUS}" -eq 0 && "${A_STATUS}" -ne 0 ]]; }; then
  cat "${TMP_DIR}/a.log" "${TMP_DIR}/b.log" >&2
  echo 'Competing migration162 sessions were not serialized' >&2; exit 1
fi
FAILED_LOG="${TMP_DIR}/a.log"; [[ "${A_STATUS}" -eq 0 ]] && FAILED_LOG="${TMP_DIR}/b.log"
grep -q 'migration_162_expected_schema_161_got_162' "${FAILED_LOG}"
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select schema_version from public.application_schema_state where contract_key='core'")" = 162

docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres <<'SQL'
do $$ begin
  if has_table_privilege('authenticated','public.data_source_webhook_endpoints','select')
     or has_table_privilege('authenticated','public.data_source_webhook_events','select') then
    raise exception 'authenticated role can read webhook state';end if;
  if not has_table_privilege('service_role','public.data_source_webhook_events','select') then
    raise exception 'service role lacks webhook inbox access';end if;
end $$;

insert into auth.users(id,email,email_confirmed_at,confirmed_at)
values('80000000-0000-4000-8000-000000000001','webhook@example.invalid',now(),now());
insert into public.tenants(tenant_id,brand_name,owner_name) values(8001,'Webhook','Owner');
insert into public.users(id,auth_id,first_name,last_name,email,tenant_id,account_kind,account_status)
overriding system value values(8001,'80000000-0000-4000-8000-000000000001','Webhook','Owner',
  'webhook@example.invalid',8001,'platform','active');
insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status)
values(8001,8001,'80000000-0000-4000-8000-000000000001','owner','active');
insert into public.builder_projects(id,tenant_id,owner_user_id,name,slug,status,draft_schema)
values('80000000-0000-4000-8000-000000000002',8001,8001,'Webhook project','webhook-project','draft','{"workspaceKind":"data"}');
insert into public.data_sources(id,tenant_id,project_id,creator_user_id,source_type,display_name,status,
  provider_key,resource_type,credential_revision)
values('80000000-0000-4000-8000-000000000003',8001,'80000000-0000-4000-8000-000000000002',8001,
  'api_provider','Webhook fixture','active','webhook_fixture','records',1);
insert into public.data_source_credentials(id,tenant_id,project_id,source_id,provider_key,credential_type,
  credential_version,source_revision,status,environment_binding,ciphertext,nonce,wrapped_data_key,key_name,
  key_version,aad_version,created_by_user_id)
values('80000000-0000-4000-8000-000000000004',8001,'80000000-0000-4000-8000-000000000002',
  '80000000-0000-4000-8000-000000000003','webhook_fixture','webhook_hmac',1,1,'active','test',
  repeat('a',24),repeat('b',16),'vault:v1:QUFBQQ==','fixture',1,1,8001);
update public.data_sources set active_credential_id='80000000-0000-4000-8000-000000000004'
where id='80000000-0000-4000-8000-000000000003';
select public.configure_data_source_webhook162(8001,'80000000-0000-4000-8000-000000000002',
  '80000000-0000-4000-8000-000000000003',null,8001,'webhook_fixture','records',true,
  '80000000-0000-4000-8000-000000000004',1,1,null);
SQL

ENDPOINT_ID="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc 'select id from public.data_source_webhook_endpoints')"
docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -c \
  "select * from public.accept_data_source_webhook_event162('${ENDPOINT_ID}',1,'80000000-0000-4000-8000-000000000004',1,1,'evt_disposable_0001','record.upsert','authoritative_record',now(),repeat('a',64),'{\"record\":{\"id\":\"A\",\"version\":1,\"data\":{\"amount\":1}}}');" >/dev/null

# Concurrent claims must yield one lease for one durable event.
docker exec "${CONTAINER_NAME}" psql -X -At -U postgres -c \
  "select id from public.claim_data_source_webhook_events162('worker-a',1,300,now())" >"${TMP_DIR}/claim-a" & C1=$!
docker exec "${CONTAINER_NAME}" psql -X -At -U postgres -c \
  "select id from public.claim_data_source_webhook_events162('worker-b',1,300,now())" >"${TMP_DIR}/claim-b" & C2=$!
wait "${C1}"; wait "${C2}"
test "$(awk 'NF{n++}END{print n+0}' "${TMP_DIR}/claim-a" "${TMP_DIR}/claim-b")" = 1

echo 'Disposable schema161 -> 162 rollback, lock, isolation, durable deduplication, and worker-claim concurrency passed'
