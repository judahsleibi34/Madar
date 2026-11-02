#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WEB_ROOT="${ROOT_DIR}/web"
POSTGRES_IMAGE="${MADAR_DISPOSABLE_POSTGRES_IMAGE:-postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73}"
CONTAINER_NAME="madar-sharing165-${RANDOM}-$$"
TMP_DIR="$(mktemp -d /tmp/madar-sharing165-XXXXXX)"

cleanup() {
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

python3 "${WEB_ROOT}/scripts/bi_team_sharing_candidate.py"
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
comment on database postgres is 'madar-sharing165-disposable';
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
apply_range 115 164
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select schema_version from public.application_schema_state where contract_key='core'")" = 164

{
  sed -e '/^begin;$/Id' -e '/^commit;$/Id' "${WEB_ROOT}/database/migrations/165_add_bi_team_sharing.sql"
  printf '\nselect 1/0;\n'
} | if docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "${CONTAINER_NAME}" \
  psql -X -v ON_ERROR_STOP=1 -U postgres -1 -q; then
  echo 'Forced migration165 failure unexpectedly succeeded' >&2; exit 1
fi
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select schema_version from public.application_schema_state where contract_key='core'")" = 164
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select to_regclass('public.bi_dashboard_shares') is null")" = t

docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres < "${WEB_ROOT}/database/migrations/165_add_bi_team_sharing.sql" >"${TMP_DIR}/a.log" 2>&1 & A_PID=$!
docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres < "${WEB_ROOT}/database/migrations/165_add_bi_team_sharing.sql" >"${TMP_DIR}/b.log" 2>&1 & B_PID=$!
set +e
wait "${A_PID}"; A_STATUS=$?
wait "${B_PID}"; B_STATUS=$?
set -e
if ! { [[ "${A_STATUS}" -eq 0 && "${B_STATUS}" -ne 0 ]] || [[ "${B_STATUS}" -eq 0 && "${A_STATUS}" -ne 0 ]]; }; then
  cat "${TMP_DIR}/a.log" "${TMP_DIR}/b.log" >&2
  echo 'Competing migration165 sessions were not serialized' >&2; exit 1
fi
FAILED_LOG="${TMP_DIR}/a.log"; [[ "${A_STATUS}" -eq 0 ]] && FAILED_LOG="${TMP_DIR}/b.log"
grep -q 'migration_165_expected_schema_164_got_165' "${FAILED_LOG}"
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select schema_version from public.application_schema_state where contract_key='core'")" = 165

docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres <<'SQL'
do $$ begin
  if has_table_privilege('authenticated','public.bi_dashboard_shares','select')
     or has_table_privilege('authenticated','public.bi_report_shares','select') then
    raise exception 'authenticated role can read private BI shares';end if;
  if has_function_privilege('authenticated','public.set_bi_dashboard_share165(integer,uuid,integer,uuid,bigint,integer,text)','execute') then
    raise exception 'authenticated role can mutate BI shares';end if;
end $$;

insert into auth.users(id,email,email_confirmed_at,confirmed_at) values
('90000000-0000-4000-8000-000000000001','owner@example.invalid',now(),now()),
('90000000-0000-4000-8000-000000000002','member@example.invalid',now(),now()),
('90000000-0000-4000-8000-000000000003','outsider@example.invalid',now(),now());
insert into public.tenants(tenant_id,brand_name,owner_name) values(9001,'Sharing','Owner'),(9002,'Outside','Owner');
insert into public.users(id,auth_id,first_name,last_name,email,tenant_id,account_kind,account_status)
overriding system value values
(9001,'90000000-0000-4000-8000-000000000001','Share','Owner','owner@example.invalid',9001,'platform','active'),
(9002,'90000000-0000-4000-8000-000000000002','Share','Member','member@example.invalid',9001,'platform','active'),
(9003,'90000000-0000-4000-8000-000000000003','Other','Tenant','outsider@example.invalid',9002,'platform','active');
insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values
(9001,9001,'90000000-0000-4000-8000-000000000001','owner','active'),
(9001,9002,'90000000-0000-4000-8000-000000000002','member','active'),
(9002,9003,'90000000-0000-4000-8000-000000000003','owner','active');
insert into public.builder_projects(id,tenant_id,owner_user_id,name,slug,status,draft_schema)
values('91000000-0000-4000-8000-000000000001',9001,9001,'Share project','share-project','draft','{"workspaceKind":"data"}');
select public.create_bi_dashboard163(9001,'91000000-0000-4000-8000-000000000001',9001,'Operations','Private team dashboard');
SQL

DASHBOARD_ID="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select id from public.bi_dashboards where tenant_id=9001")"
REPORT_ID="$(docker exec "${CONTAINER_NAME}" psql -X -q -U postgres -Atc \
  "insert into public.bi_report_runs(tenant_id,project_id,creator_user_id,dashboard_id,dashboard_revision,trigger_type,deduplication_key,status,definition_snapshot,version_vector,result_snapshot,warnings,completed_at) values(9001,'91000000-0000-4000-8000-000000000001',9001,'${DASHBOARD_ID}',1,'manual',repeat('r',64),'needs_attention','{}','[]','{}','[]',now()) returning id")"

test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select (public.set_bi_dashboard_share165(9001,'91000000-0000-4000-8000-000000000001',9001,'${DASHBOARD_ID}',1,9002,'editor')->'share'->>'permission')")" = editor
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select (public.set_bi_report_share165(9001,'91000000-0000-4000-8000-000000000001',9001,'${REPORT_ID}',9002,null)).permission")" = viewer

if docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -c \
  "select public.set_bi_dashboard_share165(9001,'91000000-0000-4000-8000-000000000001',9001,'${DASHBOARD_ID}',2,9003,'viewer');" >"${TMP_DIR}/cross-tenant.log" 2>&1; then
  echo 'Cross-tenant dashboard share unexpectedly succeeded' >&2; exit 1
fi
grep -q 'dashboard_share_member_forbidden' "${TMP_DIR}/cross-tenant.log"

test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select public.revoke_bi_dashboard_share165(9001,'91000000-0000-4000-8000-000000000001',9001,'${DASHBOARD_ID}',2,9002) is not null")" = t
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select public.revoke_bi_report_share165(9001,'91000000-0000-4000-8000-000000000001',9001,'${REPORT_ID}',9002,1)")" = t
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select count(*) from public.bi_dashboard_shares where member_user_id=9002")" = 0
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc \
  "select count(*) from public.bi_report_shares where member_user_id=9002")" = 0

echo 'Disposable schema164 -> 165 rollback, lock, RLS, tenant isolation, permissions, revision, and revocation passed'
