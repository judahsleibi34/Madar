#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POSTGRES_IMAGE="postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73"
CONTAINER_NAME="madar-migration-150-${RANDOM}-$$"

cleanup() {
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker run -d --name "${CONTAINER_NAME}" --network none \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=512m \
  -e POSTGRES_HOST_AUTH_METHOD=trust "${POSTGRES_IMAGE}" >/dev/null

for _ in $(seq 1 30); do
  if docker exec "${CONTAINER_NAME}" pg_isready -U postgres >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker exec "${CONTAINER_NAME}" pg_isready -U postgres >/dev/null

docker exec -i "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres <<'SQL'
create extension if not exists pgcrypto;
create role anon;
create role authenticated;
create role service_role;
create table public.application_schema_state(
  contract_key text primary key,
  schema_version integer not null,
  applied_at timestamptz not null default now()
);
insert into public.application_schema_state(contract_key, schema_version) values ('core', 146);
create table public.tenants(tenant_id integer primary key);
create table public.users(id integer primary key, tenant_id integer not null references public.tenants(tenant_id));
create table public.builder_projects(
  id uuid primary key,
  tenant_id integer not null references public.tenants(tenant_id),
  name text not null,
  status text not null,
  draft_schema jsonb not null default '{}'::jsonb
);
create table public.storage_accounts(
  tenant_id integer not null references public.tenants(tenant_id),
  scope_key text not null,
  user_id integer,
  used_bytes bigint not null default 0,
  reserved_bytes bigint not null default 0,
  quota_bytes bigint not null default 1000000,
  primary key(tenant_id, scope_key)
);
create table public.storage_reservations(
  id uuid primary key,
  tenant_id integer not null references public.tenants(tenant_id),
  user_id integer,
  category text not null,
  bytes bigint not null,
  status text not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default now() + interval '1 hour',
  finished_at timestamptz
);
create table public.storage_objects(
  id uuid primary key,
  reservation_id uuid unique references public.storage_reservations(id),
  tenant_id integer not null references public.tenants(tenant_id),
  user_id integer,
  category text not null,
  storage_key text not null,
  status text not null,
  size_bytes bigint not null,
  sha256 text
);
create function public.set_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end;
$$;
insert into public.tenants values (1), (2);
insert into public.users values (7, 1), (8, 1), (9, 2);
insert into public.builder_projects values
  ('11111111-1111-4111-8111-111111111111', 1, 'A', 'draft', '{"workspaceKind":"data"}'),
  ('22222222-2222-4222-8222-222222222222', 1, 'B', 'draft', '{"workspaceKind":"data"}'),
  ('99999999-9999-4999-8999-999999999999', 2, 'Other', 'draft', '{"workspaceKind":"data"}');
insert into public.storage_objects(id,tenant_id,user_id,category,storage_key,status,size_bytes,sha256) values
  ('55555555-5555-4555-8555-555555555551', 1, 7, 'dataset', 'tenant_1/user_7/one.csv', 'active', 18, repeat('a', 64)),
  ('55555555-5555-4555-8555-555555555552', 1, 7, 'dataset', 'tenant_1/user_7/two.csv', 'active', 18, repeat('b', 64));
SQL

for migration in 147_add_project_datasets.sql 148_add_project_data_sources.sql 149_add_source_ingestion_runs.sql 150_add_source_ingestion_recovery.sql; do
  docker exec -i "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres \
    < "${ROOT_DIR}/web/database/migrations/${migration}"
done

docker exec -i "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres <<'SQL'
insert into public.data_sources(
  id, tenant_id, project_id, creator_user_id, source_type, display_name
) values (
  '33333333-3333-4333-8333-333333333333', 1,
  '11111111-1111-4111-8111-111111111111', 7, 'spreadsheet_upload', 'Monthly sales'
);

select * from public.reserve_source_ingestion149(
  1, '11111111-1111-4111-8111-111111111111',
  '33333333-3333-4333-8333-333333333333', 7, 'upload-123456'
);

do $$
declare
  v_run_id uuid;
  v_disposition text;
  v_dataset_id uuid;
  v_version_id uuid;
begin
  select ingestion_run_id, disposition into v_run_id, v_disposition
  from public.reserve_source_ingestion149(
    1, '11111111-1111-4111-8111-111111111111',
    '33333333-3333-4333-8333-333333333333', 7, 'upload-123456'
  );
  if v_disposition <> 'in_progress' then
    raise exception 'duplicate processing reservation was not rejected';
  end if;

  select dataset_id, version_id into v_dataset_id, v_version_id
  from public.complete_source_ingestion149(
    1, '11111111-1111-4111-8111-111111111111',
    '33333333-3333-4333-8333-333333333333', 7, v_run_id,
    'sales.csv', '55555555-5555-4555-8555-555555555551', 'sales.csv',
    'text/csv', '.csv', 18, repeat('a', 64),
    '{"rows":1,"column_count":2}'::jsonb, '{"rows":1,"column_count":2}'::jsonb
  );

  select disposition into v_disposition
  from public.reserve_source_ingestion149(
    1, '11111111-1111-4111-8111-111111111111',
    '33333333-3333-4333-8333-333333333333', 7, 'upload-123456'
  );
  if v_disposition <> 'succeeded' then
    raise exception 'successful idempotent replay was not returned';
  end if;

  if (select count(*) from public.data_datasets) <> 1
     or (select count(*) from public.data_dataset_versions) <> 1
     or (select count(*) from public.data_source_ingestion_runs) <> 1 then
    raise exception 'idempotent completion created duplicate records';
  end if;
  if not exists(
    select 1 from public.data_sources s
    join public.data_datasets d on d.id = s.latest_dataset_id and d.source_id = s.id
    join public.data_dataset_versions v on v.id = s.latest_version_id and v.dataset_id = d.id
    join public.data_source_ingestion_runs r
      on r.result_dataset_id = d.id and r.result_version_id = v.id and r.status = 'succeeded'
    where s.id = '33333333-3333-4333-8333-333333333333'
  ) then
    raise exception 'source/dataset/version/run lineage is inconsistent';
  end if;

  begin
    perform public.reserve_source_ingestion149(
      2, '99999999-9999-4999-8999-999999999999',
      '33333333-3333-4333-8333-333333333333', 9, 'cross-tenant-123'
    );
    raise exception 'cross-tenant source reservation was accepted';
  exception when sqlstate 'P0001' then
    if sqlerrm <> 'data_source_not_available' then raise; end if;
  end;
end;
$$;

do $$
declare v_run_id uuid;
begin
  select ingestion_run_id into v_run_id
  from public.reserve_source_ingestion149(
    1, '11111111-1111-4111-8111-111111111111',
    '33333333-3333-4333-8333-333333333333', 7, 'upload-failure-123'
  );
  perform public.fail_source_ingestion149(
    1, '11111111-1111-4111-8111-111111111111',
    '33333333-3333-4333-8333-333333333333', 7, v_run_id, 'upload_rejected'
  );
  if not exists(
    select 1 from public.data_source_ingestion_runs
    where id = v_run_id and status = 'failed' and failure_code = 'upload_rejected'
  ) then
    raise exception 'failed run was not durable';
  end if;
  begin
    update public.data_source_ingestion_runs set status = 'processing' where id = v_run_id;
    raise exception 'terminal run transition was accepted';
  exception when sqlstate 'P0001' then
    if sqlerrm <> 'ingestion_run_transition_invalid' then raise; end if;
  end;
end;
$$;

do $$
declare
  v_run_id uuid;
  v_token uuid;
  v_new_token uuid;
  v_dataset_id uuid;
  v_count integer;
begin
  select ingestion_run_id, lease_token into v_run_id, v_token
  from public.reserve_source_ingestion150(
    1, '11111111-1111-4111-8111-111111111111',
    '33333333-3333-4333-8333-333333333333', 7, 'recovery-success-150', 7200
  );
  insert into public.storage_reservations(id,tenant_id,user_id,category,bytes,status)
  values('aaaaaaaa-0000-4000-8000-000000000001',1,7,'dataset',18,'committed');
  insert into public.storage_objects(
    id,reservation_id,tenant_id,user_id,category,storage_key,status,size_bytes,sha256
  ) values(
    'aaaaaaaa-0000-4000-8000-000000000002','aaaaaaaa-0000-4000-8000-000000000001',
    1,7,'dataset','tenant_1/user_7/recovery.csv','active',18,repeat('c',64)
  );
  perform public.attach_source_ingestion_reservation150(
    1,v_run_id,v_token,'aaaaaaaa-0000-4000-8000-000000000001'
  );
  perform public.attach_source_ingestion_storage150(
    1,v_run_id,v_token,'aaaaaaaa-0000-4000-8000-000000000002'
  );
  select dataset_id into v_dataset_id
  from public.complete_source_ingestion150(
    1,'11111111-1111-4111-8111-111111111111',
    '33333333-3333-4333-8333-333333333333',7,v_run_id,v_token,
    'recovery.csv','aaaaaaaa-0000-4000-8000-000000000002','recovery.csv',
    'text/csv','.csv',18,repeat('c',64),'{}'::jsonb,'{}'::jsonb
  );
  if v_dataset_id is null or not exists(
    select 1 from public.data_source_ingestion_runs
    where id=v_run_id and status='succeeded' and reconciliation_state='resolved'
  ) then raise exception 'fenced successful completion failed'; end if;

  select ingestion_run_id, lease_token into v_run_id, v_token
  from public.reserve_source_ingestion150(
    1,'11111111-1111-4111-8111-111111111111',
    '33333333-3333-4333-8333-333333333333',7,'recovery-stale-150',7200
  );
  insert into public.storage_reservations(id,tenant_id,user_id,category,bytes,status)
  values('bbbbbbbb-0000-4000-8000-000000000001',1,7,'dataset',18,'reserved');
  perform public.attach_source_ingestion_reservation150(
    1,v_run_id,v_token,'bbbbbbbb-0000-4000-8000-000000000001'
  );
  perform public.heartbeat_source_ingestion150(1,v_run_id,v_token,7200);
  select count(*) into v_count from public.claim_stale_source_ingestions150(
    'rehearsal',10,now()+interval '1 hour',900
  ) where id=v_run_id;
  if v_count <> 0 then raise exception 'active slow upload was reclaimed'; end if;

  select lease_token into v_new_token
  from public.claim_stale_source_ingestions150(
    'rehearsal',10,now()+interval '3 hours',900
  ) where id=v_run_id;
  if v_new_token is null or v_new_token=v_token then
    raise exception 'stale upload was not fenced';
  end if;
  begin
    perform public.heartbeat_source_ingestion150(1,v_run_id,v_token,7200);
    raise exception 'late original heartbeat was accepted';
  exception when sqlstate 'P0001' then
    if sqlerrm <> 'ingestion_lease_lost' then raise; end if;
  end;
  begin
    perform public.complete_source_ingestion150(
      1,'11111111-1111-4111-8111-111111111111',
      '33333333-3333-4333-8333-333333333333',7,v_run_id,v_token,
      'late.csv','55555555-5555-4555-8555-555555555552','late.csv',
      'text/csv','.csv',18,repeat('b',64),'{}'::jsonb,'{}'::jsonb
    );
    raise exception 'late original completion was accepted';
  exception when sqlstate 'P0001' then
    if sqlerrm <> 'ingestion_lease_lost' then raise; end if;
  end;
  update public.storage_reservations set status='released',finished_at=now()
  where id='bbbbbbbb-0000-4000-8000-000000000001';
  perform public.settle_source_ingestion_reconciliation150(
    v_run_id,v_new_token,'failed','abandoned_before_storage_commit',86400
  );
  if not exists(select 1 from public.data_source_ingestion_runs
    where id=v_run_id and status='failed' and failure_code='abandoned_ingestion') then
    raise exception 'reconciled failure was not durable';
  end if;
  select count(*) into v_count from public.claim_stale_source_ingestions150(
    'second-reconciler',10,now()+interval '4 hours',900
  ) where id=v_run_id;
  if v_count <> 0 then raise exception 'terminal reconciliation was repeated'; end if;

  select ingestion_run_id, lease_token into v_run_id, v_token
  from public.reserve_source_ingestion150(
    1,'11111111-1111-4111-8111-111111111111',
    '33333333-3333-4333-8333-333333333333',7,'recovery-ambiguous-150',7200
  );
  select lease_token into v_new_token
  from public.claim_stale_source_ingestions150(
    'rehearsal',10,now()+interval '3 hours',900
  ) where id=v_run_id;
  perform public.settle_source_ingestion_reconciliation150(
    v_run_id,v_new_token,'ambiguous','storage_reservation_untracked',86400
  );
  if not exists(select 1 from public.data_source_ingestion_runs
    where id=v_run_id and status='processing' and reconciliation_state='ambiguous') then
    raise exception 'ambiguous outcome was not preserved';
  end if;
end;
$$;

select case when schema_version = 150 then 'migration_150_rehearsal_passed'
            else 'migration_150_rehearsal_failed' end as result
from public.application_schema_state where contract_key = 'core';

do $$
declare v_run_id uuid;
begin
  select ingestion_run_id into v_run_id
  from public.reserve_source_ingestion150(
    1,'11111111-1111-4111-8111-111111111111',
    '33333333-3333-4333-8333-333333333333',7,'recovery-concurrent-150',7200
  );
  update public.data_source_ingestion_runs
  set lease_expires_at=now()-interval '1 minute'
  where id=v_run_id;
end;
$$;
SQL

RESULT_ONE="/tmp/${CONTAINER_NAME}-claim-one"
RESULT_TWO="/tmp/${CONTAINER_NAME}-claim-two"
docker exec "${CONTAINER_NAME}" psql -At -v ON_ERROR_STOP=1 -U postgres -c \
  "select id from public.claim_stale_source_ingestions150('race-one',1,now(),900)" >"${RESULT_ONE}" &
PID_ONE=$!
docker exec "${CONTAINER_NAME}" psql -At -v ON_ERROR_STOP=1 -U postgres -c \
  "select id from public.claim_stale_source_ingestions150('race-two',1,now(),900)" >"${RESULT_TWO}" &
PID_TWO=$!
wait "${PID_ONE}"
wait "${PID_TWO}"
CLAIM_COUNT="$(awk 'NF { count += 1 } END { print count + 0 }' "${RESULT_ONE}" "${RESULT_TWO}")"
rm -f "${RESULT_ONE}" "${RESULT_TWO}"
if [[ "${CLAIM_COUNT}" != "1" ]]; then
  echo "concurrent recovery claim failed: expected one claimant, got ${CLAIM_COUNT}" >&2
  exit 1
fi
echo "migration_150_concurrent_claim_passed"
