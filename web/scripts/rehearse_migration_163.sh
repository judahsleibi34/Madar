#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WEB_ROOT="${ROOT_DIR}/web"
POSTGRES_IMAGE="${MADAR_DISPOSABLE_POSTGRES_IMAGE:-postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73}"
CONTAINER_NAME="madar-bi163-${RANDOM}-$$"
TMP_DIR="$(mktemp -d /tmp/madar-bi163-XXXXXX)"

cleanup() {
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

python3 "${WEB_ROOT}/scripts/bi_dashboard_candidate.py"
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
comment on database postgres is 'madar-bi163-disposable';
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
apply_range 115 162
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select schema_version from public.application_schema_state where contract_key='core'")" = 162

# A forced transactional error must leave both schema state and DDL at 162.
{
  sed -e '/^begin;$/Id' -e '/^commit;$/Id' "${WEB_ROOT}/database/migrations/163_add_bi_dashboards.sql"
  printf '\nselect 1/0;\n'
} | if docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "${CONTAINER_NAME}" \
  psql -X -v ON_ERROR_STOP=1 -U postgres -1 -q; then
  echo 'Forced migration163 failure unexpectedly succeeded' >&2; exit 1
fi
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select schema_version from public.application_schema_state where contract_key='core'")" = 162
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select to_regclass('public.bi_dashboards') is null")" = t

# The state-row lock permits exactly one concurrent 162 -> 163 transition.
docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres \
  < "${WEB_ROOT}/database/migrations/163_add_bi_dashboards.sql" >"${TMP_DIR}/a.log" 2>&1 & A_PID=$!
docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres \
  < "${WEB_ROOT}/database/migrations/163_add_bi_dashboards.sql" >"${TMP_DIR}/b.log" 2>&1 & B_PID=$!
set +e
wait "${A_PID}"; A_STATUS=$?
wait "${B_PID}"; B_STATUS=$?
set -e
if ! { [[ "${A_STATUS}" -eq 0 && "${B_STATUS}" -ne 0 ]] || [[ "${B_STATUS}" -eq 0 && "${A_STATUS}" -ne 0 ]]; }; then
  cat "${TMP_DIR}/a.log" "${TMP_DIR}/b.log" >&2
  echo 'Competing migration163 sessions were not serialized' >&2; exit 1
fi
FAILED_LOG="${TMP_DIR}/a.log"; [[ "${A_STATUS}" -eq 0 ]] && FAILED_LOG="${TMP_DIR}/b.log"
grep -q 'migration_163_expected_schema_162_got_163' "${FAILED_LOG}"
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select schema_version from public.application_schema_state where contract_key='core'")" = 163

docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres <<'SQL'
do $$ begin
  if has_table_privilege('authenticated','public.bi_dashboards','select')
     or has_table_privilege('authenticated','public.bi_dashboard_widgets','select') then
    raise exception 'authenticated role can read private BI state';end if;
  if not has_table_privilege('service_role','public.bi_dashboards','select')
     or not has_table_privilege('service_role','public.bi_dashboard_widgets','select') then
    raise exception 'service role lacks private BI state access';end if;
  if has_function_privilege('authenticated','public.create_bi_dashboard163(integer,uuid,integer,text,text)','execute') then
    raise exception 'authenticated role can call privileged BI RPC';end if;
end $$;

insert into auth.users(id,email,email_confirmed_at,confirmed_at)
values('90000000-0000-4000-8000-000000000001','bi@example.invalid',now(),now());
insert into public.tenants(tenant_id,brand_name,owner_name) values(9001,'BI','Owner');
insert into public.users(id,auth_id,first_name,last_name,email,tenant_id,account_kind,account_status)
overriding system value values(9001,'90000000-0000-4000-8000-000000000001','BI','Owner',
  'bi@example.invalid',9001,'platform','active');
insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status)
values(9001,9001,'90000000-0000-4000-8000-000000000001','owner','active');
insert into public.builder_projects(id,tenant_id,owner_user_id,name,slug,status,draft_schema)
values('90000000-0000-4000-8000-000000000002',9001,9001,'BI project','bi-project','draft','{"workspaceKind":"data"}');
insert into public.storage_objects(id,tenant_id,user_id,category,storage_key,status,size_bytes,sha256)
values('90000000-0000-4000-8000-000000000003',9001,9001,'dataset','tenant_9001/user_9001/bi.csv','active',18,repeat('a',64));
insert into public.data_datasets(id,tenant_id,project_id,creator_user_id,display_name)
values('90000000-0000-4000-8000-000000000004',9001,'90000000-0000-4000-8000-000000000002',9001,'BI data');
insert into public.data_dataset_versions(id,tenant_id,dataset_id,version_number,storage_object_id,
  created_by_user_id,version_kind,original_filename,content_type,file_extension,size_bytes,content_hash)
values('90000000-0000-4000-8000-000000000005',9001,'90000000-0000-4000-8000-000000000004',1,
  '90000000-0000-4000-8000-000000000003',9001,'original','bi.csv','text/csv','.csv',18,repeat('a',64));
select public.create_bi_dashboard163(9001,'90000000-0000-4000-8000-000000000002',9001,'Operations','Versioned metrics');
SQL

DASHBOARD_ID="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select id from public.bi_dashboards where tenant_id=9001")"
ADD_SQL="select public.add_bi_dashboard_widget163(9001,'90000000-0000-4000-8000-000000000002',9001,'${DASHBOARD_ID}',1,'kpi','Rows','90000000-0000-4000-8000-000000000004','90000000-0000-4000-8000-000000000005','pinned','{\"operation\":\"count\"}'::jsonb,'{}'::jsonb,'{}'::jsonb);"
docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -c "${ADD_SQL}" >"${TMP_DIR}/widget-a.log" 2>&1 & W1=$!
docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -c "${ADD_SQL}" >"${TMP_DIR}/widget-b.log" 2>&1 & W2=$!
set +e
wait "${W1}"; W1_STATUS=$?
wait "${W2}"; W2_STATUS=$?
set -e
if ! { [[ "${W1_STATUS}" -eq 0 && "${W2_STATUS}" -ne 0 ]] || [[ "${W2_STATUS}" -eq 0 && "${W1_STATUS}" -ne 0 ]]; }; then
  cat "${TMP_DIR}/widget-a.log" "${TMP_DIR}/widget-b.log" >&2
  echo 'Optimistic dashboard revision did not serialize concurrent writes' >&2; exit 1
fi
CONFLICT_LOG="${TMP_DIR}/widget-a.log"; [[ "${W1_STATUS}" -eq 0 ]] && CONFLICT_LOG="${TMP_DIR}/widget-b.log"
grep -q 'dashboard_revision_conflict' "${CONFLICT_LOG}"
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select count(*)||':'||max(revision) from public.bi_dashboards d join public.bi_dashboard_widgets w on w.dashboard_id=d.id where d.id='${DASHBOARD_ID}'")" = '1:2'

# A caller cannot smuggle an otherwise-valid dashboard through a different tenant scope.
if docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -c \
  "select public.update_bi_dashboard163(9002,'90000000-0000-4000-8000-000000000002',9001,'${DASHBOARD_ID}',2,'Wrong tenant','');" \
  >"${TMP_DIR}/cross-tenant.log" 2>&1; then
  echo 'Cross-tenant dashboard mutation unexpectedly succeeded' >&2; exit 1
fi
grep -q 'dashboard_not_found' "${TMP_DIR}/cross-tenant.log"

echo 'Disposable schema162 -> 163 rollback, lock, RLS, scoped CRUD, and optimistic concurrency passed'
