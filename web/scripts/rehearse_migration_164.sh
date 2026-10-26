#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WEB_ROOT="${ROOT_DIR}/web"
POSTGRES_IMAGE="${MADAR_DISPOSABLE_POSTGRES_IMAGE:-postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73}"
CONTAINER_NAME="madar-report164-${RANDOM}-$$"
TMP_DIR="$(mktemp -d /tmp/madar-report164-XXXXXX)"

cleanup() {
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

python3 "${WEB_ROOT}/scripts/automated_reporting_candidate.py"
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
create role service_role nologin bypassrls;
create schema auth;
create table auth.users(id uuid primary key,email_confirmed_at timestamptz,confirmed_at timestamptz);
create function auth.uid() returns uuid language sql stable as $$select null::uuid$$;
create schema storage;
create table storage.buckets(id text primary key,name text not null,public boolean not null default false,file_size_limit bigint,allowed_mime_types text[]);
create table storage.objects(id uuid primary key default gen_random_uuid(),bucket_id text references storage.buckets(id),name text);
alter table storage.objects enable row level security;
create schema extensions;
create extension pgcrypto schema extensions;
comment on database postgres is 'madar-report164-disposable';
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
apply_range 115 163
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select schema_version from public.application_schema_state where contract_key='core'")" = 163

# A forced transactional error leaves schema state and DDL at 163.
{
  sed -e '/^begin;$/Id' -e '/^commit;$/Id' "${WEB_ROOT}/database/migrations/164_add_automated_reporting.sql"
  printf '\nselect 1/0;\n'
} | if docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "${CONTAINER_NAME}" \
  psql -X -v ON_ERROR_STOP=1 -U postgres -1 -q; then
  echo 'Forced migration164 failure unexpectedly succeeded' >&2; exit 1
fi
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select schema_version from public.application_schema_state where contract_key='core'")" = 163
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select to_regclass('public.bi_report_runs') is null")" = t

# The state-row lock permits exactly one concurrent 163 -> 164 transition.
docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres \
  < "${WEB_ROOT}/database/migrations/164_add_automated_reporting.sql" >"${TMP_DIR}/a.log" 2>&1 & A_PID=$!
docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres \
  < "${WEB_ROOT}/database/migrations/164_add_automated_reporting.sql" >"${TMP_DIR}/b.log" 2>&1 & B_PID=$!
set +e
wait "${A_PID}"; A_STATUS=$?
wait "${B_PID}"; B_STATUS=$?
set -e
if ! { [[ "${A_STATUS}" -eq 0 && "${B_STATUS}" -ne 0 ]] || [[ "${B_STATUS}" -eq 0 && "${A_STATUS}" -ne 0 ]]; }; then
  cat "${TMP_DIR}/a.log" "${TMP_DIR}/b.log" >&2
  echo 'Competing migration164 sessions were not serialized' >&2; exit 1
fi
FAILED_LOG="${TMP_DIR}/a.log"; [[ "${A_STATUS}" -eq 0 ]] && FAILED_LOG="${TMP_DIR}/b.log"
grep -q 'migration_164_expected_schema_163_got_164' "${FAILED_LOG}"
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select schema_version from public.application_schema_state where contract_key='core'")" = 164

docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres <<'SQL'
do $$ begin
  if has_table_privilege('authenticated','public.bi_report_schedules','select')
     or has_table_privilege('authenticated','public.bi_report_runs','select') then
    raise exception 'authenticated role can read private report state';end if;
  if not has_table_privilege('service_role','public.bi_report_schedules','select')
     or not has_table_privilege('service_role','public.bi_report_runs','select') then
    raise exception 'service role lacks report state access';end if;
  if has_function_privilege('authenticated','public.claim_bi_report_runs164(text,integer,integer,timestamptz)','execute') then
    raise exception 'authenticated role can claim report jobs';end if;
end $$;

insert into auth.users(id,email,email_confirmed_at,confirmed_at)
values('90000000-0000-4000-8000-000000000001','reports@example.invalid',now(),now());
insert into public.tenants(tenant_id,brand_name,owner_name) values(9001,'Reports','Owner');
insert into public.users(id,auth_id,first_name,last_name,email,tenant_id,account_kind,account_status)
overriding system value values(9001,'90000000-0000-4000-8000-000000000001','Report','Owner',
  'reports@example.invalid',9001,'platform','active');
insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status)
values(9001,9001,'90000000-0000-4000-8000-000000000001','owner','active');
insert into public.builder_projects(id,tenant_id,owner_user_id,name,slug,status,draft_schema)
values('90000000-0000-4000-8000-000000000002',9001,9001,'Report project','report-project','draft','{"workspaceKind":"data"}');
insert into public.storage_objects(id,tenant_id,user_id,category,storage_key,status,size_bytes,sha256) values
('90000000-0000-4000-8000-000000000003',9001,9001,'dataset','tenant_9001/user_9001/v1.csv','active',18,repeat('a',64)),
('90000000-0000-4000-8000-000000000006',9001,9001,'dataset','tenant_9001/user_9001/v2.csv','active',20,repeat('b',64));
insert into public.data_datasets(id,tenant_id,project_id,creator_user_id,display_name)
values('90000000-0000-4000-8000-000000000004',9001,'90000000-0000-4000-8000-000000000002',9001,'Operations');
insert into public.data_dataset_versions(id,tenant_id,dataset_id,version_number,storage_object_id,
  created_by_user_id,version_kind,original_filename,content_type,file_extension,size_bytes,content_hash) values
('90000000-0000-4000-8000-000000000005',9001,'90000000-0000-4000-8000-000000000004',1,
  '90000000-0000-4000-8000-000000000003',9001,'original','v1.csv','text/csv','.csv',18,repeat('a',64)),
('90000000-0000-4000-8000-000000000007',9001,'90000000-0000-4000-8000-000000000004',2,
  '90000000-0000-4000-8000-000000000006',9001,'derived','v2.csv','text/csv','.csv',20,repeat('b',64));
select public.create_bi_dashboard163(9001,'90000000-0000-4000-8000-000000000002',9001,'Operations','Recurring report');
SQL

DASHBOARD_ID="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select id from public.bi_dashboards where tenant_id=9001")"
docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q -c \
  "select public.add_bi_dashboard_widget163(9001,'90000000-0000-4000-8000-000000000002',9001,'${DASHBOARD_ID}',1,'kpi','Pinned rows','90000000-0000-4000-8000-000000000004','90000000-0000-4000-8000-000000000005','pinned','{\"operation\":\"count\"}'::jsonb,'{}'::jsonb,'{}'::jsonb);"
docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q -c \
  "select public.add_bi_dashboard_widget163(9001,'90000000-0000-4000-8000-000000000002',9001,'${DASHBOARD_ID}',2,'kpi','Latest rows','90000000-0000-4000-8000-000000000004','90000000-0000-4000-8000-000000000005','latest_committed','{\"operation\":\"count\"}'::jsonb,'{}'::jsonb,'{}'::jsonb);"

SCHEDULE_ID="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select (public.create_bi_report_schedule164(9001,'90000000-0000-4000-8000-000000000002',9001,'${DASHBOARD_ID}','Daily','daily','UTC','09:00',null,null,true,true,now())).id")"
ENQUEUE_SQL="select (public.enqueue_bi_report_run164(9001,'90000000-0000-4000-8000-000000000002',9001,'${DASHBOARD_ID}','${SCHEDULE_ID}','scheduled',date_trunc('hour',now()),repeat('d',64))).id;"
RUN_ONE="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "${ENQUEUE_SQL}")"
RUN_TWO="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "${ENQUEUE_SQL}")"
test "${RUN_ONE}" = "${RUN_TWO}"
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select string_agg(version_number::text,',' order by version_number) from (select (x->>'version_number')::int version_number from public.bi_report_runs r cross join lateral jsonb_array_elements(r.version_vector)x where r.id='${RUN_ONE}')q")" = '1,2'
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select definition_snapshot#>>'{report_policy,require_ready_checkpoints}' from public.bi_report_runs where id='${RUN_ONE}'")" = true

# Competing workers cannot own the same run.
CLAIM_SQL="select count(*) from public.claim_bi_report_runs164('worker',1,30,now());"
docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "${CLAIM_SQL}" >"${TMP_DIR}/claim-a" & C1=$!
docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "${CLAIM_SQL}" >"${TMP_DIR}/claim-b" & C2=$!
wait "${C1}"; wait "${C2}"
test "$(awk '{s+=$1} END{print s}' "${TMP_DIR}/claim-a" "${TMP_DIR}/claim-b")" = 1

OLD_TOKEN="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select lease_token from public.bi_report_runs where id='${RUN_ONE}'")"
OLD_FENCE="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select lease_fence from public.bi_report_runs where id='${RUN_ONE}'")"
docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q -c \
  "update public.bi_report_runs set lease_expires_at=now()-interval '1 second' where id='${RUN_ONE}';select public.recover_expired_bi_report_runs164(now(),10);select * from public.claim_bi_report_runs164('worker-new',1,30,now());"
NEW_TOKEN="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select lease_token from public.bi_report_runs where id='${RUN_ONE}'")"
NEW_FENCE="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select lease_fence from public.bi_report_runs where id='${RUN_ONE}'")"
test "${OLD_TOKEN}" != "${NEW_TOKEN}"
test "${OLD_FENCE}" -lt "${NEW_FENCE}"
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select public.complete_bi_report_run164('${RUN_ONE}','${OLD_TOKEN}',${OLD_FENCE},'needs_attention','{}','[]',null,null,null,null,null,now())")" = f
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select public.complete_bi_report_run164('${RUN_ONE}','${NEW_TOKEN}',${NEW_FENCE},'needs_attention','{}','[]',null,null,null,null,null,now())")" = t

# A valid bounded CSV artifact satisfies the completion constraint exactly.
ARTIFACT_RUN="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select (public.enqueue_bi_report_run164(9001,'90000000-0000-4000-8000-000000000002',9001,'${DASHBOARD_ID}',null,'manual',null,repeat('e',64))).id")"
docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q -c \
  "select * from public.claim_bi_report_runs164('artifact-worker',1,30,now());"
ARTIFACT_TOKEN="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select lease_token from public.bi_report_runs where id='${ARTIFACT_RUN}'")"
ARTIFACT_FENCE="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select lease_fence from public.bi_report_runs where id='${ARTIFACT_RUN}'")"
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select public.complete_bi_report_run164('${ARTIFACT_RUN}','${ARTIFACT_TOKEN}',${ARTIFACT_FENCE},'completed','{}','[]','reports/tenant_9001/${ARTIFACT_RUN}/$(printf 'a%.0s' {1..64}).csv','report.csv','text/csv',10,'$(printf 'a%.0s' {1..64})',now())")" = t
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select public.archive_bi_report_run164(9001,'90000000-0000-4000-8000-000000000002',9001,'${ARTIFACT_RUN}')")" = t
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select archived_at is not null from public.bi_report_runs where id='${ARTIFACT_RUN}'")" = t
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select public.archive_bi_report_run164(9001,'90000000-0000-4000-8000-000000000002',9002,'${ARTIFACT_RUN}')")" = f

if docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -c \
  "select public.enqueue_bi_report_run164(9002,'90000000-0000-4000-8000-000000000002',9001,'${DASHBOARD_ID}',null,'manual',null,repeat('x',64));" \
  >"${TMP_DIR}/cross-tenant.log" 2>&1; then
  echo 'Cross-tenant report enqueue unexpectedly succeeded' >&2; exit 1
fi
grep -q 'dashboard_not_found' "${TMP_DIR}/cross-tenant.log"

echo 'Disposable schema163 -> 164 rollback, lock, RLS, version-vector, dedupe, claim, recovery, fencing, and scoped archive passed'
