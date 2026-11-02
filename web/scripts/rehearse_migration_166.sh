#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WEB_ROOT="${ROOT_DIR}/web"
POSTGRES_IMAGE="${MADAR_DISPOSABLE_POSTGRES_IMAGE:-postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73}"
CONTAINER_NAME="madar-report166-${RANDOM}-$$"
TMP_DIR="$(mktemp -d /tmp/madar-report166-XXXXXX)"
cleanup(){ docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true; rm -rf "${TMP_DIR}"; }
trap cleanup EXIT

python3 "${WEB_ROOT}/scripts/bi_report_delivery_lifecycle_candidate.py"
docker run -d --name "${CONTAINER_NAME}" --network none --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=2g \
  -e POSTGRES_HOST_AUTH_METHOD=trust "${POSTGRES_IMAGE}" >/dev/null
for _ in $(seq 1 90);do docker exec "${CONTAINER_NAME}" pg_isready -U postgres >/dev/null 2>&1&&break;sleep 1;done
docker exec "${CONTAINER_NAME}" pg_isready -U postgres >/dev/null
docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres <<'SQL'
create role anon nologin;create role authenticated nologin;create role service_role nologin bypassrls;
create schema auth;create table auth.users(id uuid primary key,email_confirmed_at timestamptz,confirmed_at timestamptz);
create function auth.uid() returns uuid language sql stable as $$select null::uuid$$;
create schema storage;create table storage.buckets(id text primary key,name text not null,public boolean not null default false,file_size_limit bigint,allowed_mime_types text[]);
create table storage.objects(id uuid primary key default gen_random_uuid(),bucket_id text references storage.buckets(id),name text);alter table storage.objects enable row level security;
create schema extensions;create extension pgcrypto schema extensions;
SQL
apply_range(){ local minimum="$1" maximum="$2" migration number;for migration in "${WEB_ROOT}"/database/migrations/*.sql;do number="$(basename "${migration}"|cut -d_ -f1)";if ((10#${number}<minimum||10#${number}>maximum||10#${number}==142));then continue;fi;docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q <"${migration}";done; }
apply_range 1 114
docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q -c 'alter table auth.users add column email text'
apply_range 115 165
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select schema_version from public.application_schema_state where contract_key='core'")" = 165

{ sed -e '/^begin;$/Id' -e '/^commit;$/Id' "${WEB_ROOT}/database/migrations/166_add_bi_report_delivery_lifecycle.sql";printf '\nselect 1/0;\n'; } |
if docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -1 -q;then echo 'Forced migration166 failure unexpectedly succeeded' >&2;exit 1;fi
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select schema_version from public.application_schema_state where contract_key='core'")" = 165
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select to_regclass('public.bi_report_deliveries') is null")" = t

docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres <"${WEB_ROOT}/database/migrations/166_add_bi_report_delivery_lifecycle.sql" >"${TMP_DIR}/a" 2>&1&A=$!
docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres <"${WEB_ROOT}/database/migrations/166_add_bi_report_delivery_lifecycle.sql" >"${TMP_DIR}/b" 2>&1&B=$!
set +e;wait "$A";AS=$?;wait "$B";BS=$?;set -e
if ! { [[ "$AS" -eq 0&&"$BS" -ne 0 ]]||[[ "$BS" -eq 0&&"$AS" -ne 0 ]];};then cat "${TMP_DIR}/a" "${TMP_DIR}/b" >&2;exit 1;fi
FAILED="${TMP_DIR}/a";[[ "$AS" -eq 0 ]]&&FAILED="${TMP_DIR}/b";grep -q 'migration_166_expected_schema_165_got_166' "$FAILED"

docker exec -i "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres <<'SQL'
do $$begin if has_table_privilege('authenticated','public.bi_report_deliveries','select')
 or has_table_privilege('authenticated','public.bi_report_cleanup_jobs','select')
 or has_function_privilege('authenticated','public.claim_bi_report_deliveries166(text,integer,integer,timestamptz)','execute')
 then raise exception 'client role gained report delivery access';end if;end$$;
insert into auth.users(id,email,email_confirmed_at,confirmed_at)values
('90000000-0000-4000-8000-000000000001','owner@example.invalid',now(),now()),
('90000000-0000-4000-8000-000000000002','member@example.invalid',now(),now()),
('90000000-0000-4000-8000-000000000003','other@example.invalid',now(),now());
insert into public.tenants(tenant_id,brand_name,owner_name)values(9001,'Delivery','Owner'),(9002,'Other','Owner');
insert into public.users(id,auth_id,first_name,last_name,email,tenant_id,account_kind,account_status)overriding system value values
(9001,'90000000-0000-4000-8000-000000000001','Report','Owner','owner@example.invalid',9001,'platform','active'),
(9002,'90000000-0000-4000-8000-000000000002','Report','Member','member@example.invalid',9001,'platform','active'),
(9003,'90000000-0000-4000-8000-000000000003','Other','Member','other@example.invalid',9002,'platform','active');
insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status)values
(9001,9001,'90000000-0000-4000-8000-000000000001','owner','active'),
(9001,9002,'90000000-0000-4000-8000-000000000002','member','active'),
(9002,9003,'90000000-0000-4000-8000-000000000003','member','active');
insert into public.builder_projects(id,tenant_id,owner_user_id,name,slug,status,draft_schema)
values('91000000-0000-4000-8000-000000000001',9001,9001,'Delivery project','delivery-project','draft','{"workspaceKind":"data"}');
select public.create_bi_dashboard163(9001,'91000000-0000-4000-8000-000000000001',9001,'Operations','Delivery');
SQL
DASHBOARD="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select id from public.bi_dashboards where tenant_id=9001")"
SCHEDULE="$(docker exec "${CONTAINER_NAME}" psql -X -q -U postgres -Atc "select (public.create_bi_report_schedule164(9001,'91000000-0000-4000-8000-000000000001',9001,'${DASHBOARD}','Daily','daily','UTC','09:00',null,null,true,false,now())).id")"
REPORT="$(docker exec "${CONTAINER_NAME}" psql -X -q -U postgres -Atc "insert into public.bi_report_runs(tenant_id,project_id,creator_user_id,dashboard_id,schedule_id,dashboard_revision,trigger_type,deduplication_key,status,definition_snapshot,version_vector,result_snapshot,warnings,artifact_storage_key,artifact_filename,artifact_content_type,artifact_size_bytes,artifact_sha256,completed_at)values(9001,'91000000-0000-4000-8000-000000000001',9001,'${DASHBOARD}','${SCHEDULE}',1,'scheduled',repeat('d',64),'completed','{}','[]','{}','[]','reports/tenant_9001/00000000-0000-4000-8000-000000000001/$(printf 'a%.0s' {1..64}).csv','report.csv','text/csv',10,'$(printf 'a%.0s' {1..64})',now())returning id")"

docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q -c "select public.configure_bi_report_lifecycle166(9001,'91000000-0000-4000-8000-000000000001',9001,null::bigint,30::smallint,true);select public.configure_bi_report_delivery166(9001,'91000000-0000-4000-8000-000000000001',9001,'${SCHEDULE}',1,true,array[9002]);select public.enqueue_bi_report_lifecycle166('${REPORT}');select public.enqueue_bi_report_lifecycle166('${REPORT}');"
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select count(*) from public.bi_report_deliveries where report_id='${REPORT}'")" = 1
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select count(*) from public.bi_report_cleanup_jobs where report_id='${REPORT}'")" = 1
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select count(*) from public.bi_report_shares where report_id='${REPORT}' and member_user_id=9002")" = 1

if docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -c "select public.configure_bi_report_delivery166(9001,'91000000-0000-4000-8000-000000000001',9001,'${SCHEDULE}',2,true,array[9003]);">"${TMP_DIR}/cross" 2>&1;then echo 'Cross-tenant recipient unexpectedly accepted' >&2;exit 1;fi
grep -q 'report_delivery_recipient_forbidden' "${TMP_DIR}/cross"

DELIVERY="$(docker exec "${CONTAINER_NAME}" psql -X -q -U postgres -Atc "select id from public.claim_bi_report_deliveries166('offline',1,300,now())")"
TOKEN="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select lease_token from public.bi_report_deliveries where id='${DELIVERY}'")"
FENCE="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select lease_fence from public.bi_report_deliveries where id='${DELIVERY}'")"
docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q -c "delete from public.bi_report_shares where report_id='${REPORT}' and member_user_id=9002"
if docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -c "select public.authorize_bi_report_delivery166('${DELIVERY}','${TOKEN}',${FENCE});">"${TMP_DIR}/revoked" 2>&1;then echo 'Revoked report delivery unexpectedly authorized' >&2;exit 1;fi
grep -q 'report_delivery_access_revoked' "${TMP_DIR}/revoked"
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select (public.finish_bi_report_delivery166('${DELIVERY}','${TOKEN}',${FENCE},'revoked','recipient_access_revoked',null,now())).status")" = revoked

docker exec "${CONTAINER_NAME}" psql -X -U postgres -q -c "update public.bi_report_cleanup_jobs set available_at=now()-interval '1 second' where report_id='${REPORT}'"
CLEANUP="$(docker exec "${CONTAINER_NAME}" psql -X -q -U postgres -Atc "select id from public.claim_bi_report_cleanup166('cleanup',1,300,now())")"
test -n "$CLEANUP"
CLEANUP_TOKEN="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select lease_token from public.bi_report_cleanup_jobs where id='${CLEANUP}'")"
CLEANUP_FENCE="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select lease_fence from public.bi_report_cleanup_jobs where id='${CLEANUP}'")"
docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q -c "select public.configure_bi_report_lifecycle166(9001,'91000000-0000-4000-8000-000000000001',9001,1,30::smallint,false)"
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select public.authorize_bi_report_cleanup166('${CLEANUP}','${CLEANUP_TOKEN}',${CLEANUP_FENCE},now())->>'authorized'")" = false
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select status from public.bi_report_cleanup_jobs where id='${CLEANUP}'")" = cancelled

docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q -c "select public.configure_bi_report_lifecycle166(9001,'91000000-0000-4000-8000-000000000001',9001,2,30::smallint,true)"
docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q -c "select public.configure_bi_report_delivery166(9001,'91000000-0000-4000-8000-000000000001',9001,'${SCHEDULE}',2,false,array[]::integer[])"
REPORT2="$(docker exec "${CONTAINER_NAME}" psql -X -q -U postgres -Atc "insert into public.bi_report_runs(tenant_id,project_id,creator_user_id,dashboard_id,schedule_id,dashboard_revision,trigger_type,deduplication_key,status,definition_snapshot,version_vector,result_snapshot,warnings,artifact_storage_key,artifact_filename,artifact_content_type,artifact_size_bytes,artifact_sha256,completed_at)values(9001,'91000000-0000-4000-8000-000000000001',9001,'${DASHBOARD}','${SCHEDULE}',1,'scheduled',repeat('e',64),'completed','{}','[]','{}','[]','reports/tenant_9001/00000000-0000-4000-8000-000000000002/$(printf 'b%.0s' {1..64}).csv','report.csv','text/csv',10,'$(printf 'b%.0s' {1..64})',now()-interval '31 days')returning id")"
docker exec "${CONTAINER_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q -c "select public.enqueue_bi_report_lifecycle166('${REPORT2}')"
CLEANUP2="$(docker exec "${CONTAINER_NAME}" psql -X -q -U postgres -Atc "select id from public.claim_bi_report_cleanup166('cleanup',1,300,now())")"
test -n "$CLEANUP2"
CLEANUP_TOKEN2="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select lease_token from public.bi_report_cleanup_jobs where id='${CLEANUP2}'")"
CLEANUP_FENCE2="$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select lease_fence from public.bi_report_cleanup_jobs where id='${CLEANUP2}'")"
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select public.authorize_bi_report_cleanup166('${CLEANUP2}','${CLEANUP_TOKEN2}',${CLEANUP_FENCE2},now())->>'authorized'")" = true
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select (public.finish_bi_report_cleanup166('${CLEANUP2}','${CLEANUP_TOKEN2}',${CLEANUP_FENCE2},true,null,10,repeat('b',64),now())).status")" = completed
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select artifact_deleted_at is not null from public.bi_report_runs where id='${REPORT2}'")" = t
test "$(docker exec "${CONTAINER_NAME}" psql -X -U postgres -Atc "select schema_version from public.application_schema_state where contract_key='core'")" = 166
echo 'Disposable schema165 -> 166 rollback, lock, RLS, dedupe, tenant isolation, revocation, retry fencing, and cleanup authorization passed'
