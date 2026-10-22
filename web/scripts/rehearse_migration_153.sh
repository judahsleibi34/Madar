#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POSTGRES_IMAGE="postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73"
CONTAINER_NAME="madar-migration-153-${RANDOM}-$$"

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
create table public.users(
  id integer primary key,
  tenant_id integer not null references public.tenants(tenant_id),
  unique(id,tenant_id)
);
create table public.tenant_memberships(
  tenant_id integer not null references public.tenants(tenant_id),
  user_id integer not null,
  auth_id uuid not null,
  role text not null,
  status text not null,
  primary key(tenant_id,user_id),
  foreign key(user_id,tenant_id) references public.users(id,tenant_id)
);
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
  updated_at timestamptz not null default now(),
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
  id uuid primary key default gen_random_uuid(),
  reservation_id uuid unique references public.storage_reservations(id),
  tenant_id integer not null references public.tenants(tenant_id),
  user_id integer,
  category text not null,
  storage_key text not null,
  status text not null default 'active',
  size_bytes bigint not null,
  sha256 text,
  retention_until timestamptz
);
create function public.set_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end;
$$;
insert into public.tenants values (1), (2);
insert into public.users values (7, 1), (8, 1), (9, 2);
insert into public.tenant_memberships values
  (1,7,'77777777-7777-4777-8777-777777777777','owner','active'),
  (1,8,'88888888-8888-4888-8888-888888888888','member','active'),
  (2,9,'99999999-9999-4999-8999-999999999999','owner','active');
insert into public.builder_projects values
  ('11111111-1111-4111-8111-111111111111', 1, 'A', 'draft', '{"workspaceKind":"data"}'),
  ('22222222-2222-4222-8222-222222222222', 1, 'B', 'draft', '{"workspaceKind":"data"}'),
  ('99999999-9999-4999-8999-999999999999', 2, 'Other', 'draft', '{"workspaceKind":"data"}');
insert into public.storage_objects(id,tenant_id,user_id,category,storage_key,status,size_bytes,sha256) values
  ('55555555-5555-4555-8555-555555555551', 1, 7, 'dataset', 'tenant_1/user_7/one.csv', 'active', 18, repeat('a', 64)),
  ('55555555-5555-4555-8555-555555555552', 1, 7, 'dataset', 'tenant_1/user_7/two.csv', 'active', 18, repeat('b', 64));
SQL

for migration in 147_add_project_datasets.sql 148_add_project_data_sources.sql 149_add_source_ingestion_runs.sql 150_add_source_ingestion_recovery.sql 151_add_api_source_ingestion.sql 152_add_incremental_source_ingestion.sql 153_add_background_dataset_checkpoints.sql; do
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

insert into public.data_sources(
  id,tenant_id,project_id,creator_user_id,source_type,display_name,provider_key,resource_type
) values(
  'cccccccc-0000-4000-8000-000000000001',1,
  '11111111-1111-4111-8111-111111111111',7,'api_provider','Synthetic orders',
  'synthetic_orders','orders'
);

do $$
declare
  v_run_id uuid;
  v_token uuid;
  v_dataset_id uuid;
  v_version_id uuid;
  v_disposition text;
begin
  select ingestion_run_id,lease_token into v_run_id,v_token
  from public.reserve_source_ingestion151(
    1,'11111111-1111-4111-8111-111111111111',
    'cccccccc-0000-4000-8000-000000000001',7,'api-orders-151',7200
  );
  insert into public.storage_reservations(id,tenant_id,user_id,category,bytes,status)
  values('cccccccc-0000-4000-8000-000000000002',1,7,'dataset',18,'committed');
  insert into public.storage_objects(
    id,reservation_id,tenant_id,user_id,category,storage_key,status,size_bytes,sha256
  ) values(
    'cccccccc-0000-4000-8000-000000000003','cccccccc-0000-4000-8000-000000000002',
    1,7,'dataset','tenant_1/user_7/api-orders.csv','active',18,repeat('d',64)
  );
  perform public.attach_source_ingestion_reservation150(
    1,v_run_id,v_token,'cccccccc-0000-4000-8000-000000000002'
  );
  perform public.attach_source_ingestion_storage150(
    1,v_run_id,v_token,'cccccccc-0000-4000-8000-000000000003'
  );
  select dataset_id,version_id into v_dataset_id,v_version_id
  from public.complete_source_ingestion151(
    1,'11111111-1111-4111-8111-111111111111',
    'cccccccc-0000-4000-8000-000000000001',7,v_run_id,v_token,
    'Synthetic orders','cccccccc-0000-4000-8000-000000000003','orders.csv',
    'text/csv','.csv',18,repeat('d',64),
    '{"rows":3,"provider":{"provider_key":"synthetic_orders","resource_type":"orders"}}'::jsonb,
    '{"record_count":3,"page_count":2}'::jsonb
  );
  if v_dataset_id is null or v_version_id is null then
    raise exception 'API ingestion did not create lineage';
  end if;
  if not exists(
    select 1 from public.data_dataset_versions v
    where v.id=v_version_id
      and v.provenance->>'kind'='source_api_snapshot'
      and v.provenance->>'provider_key'='synthetic_orders'
  ) then raise exception 'API provenance was not persisted'; end if;
  if not exists(
    select 1 from public.data_sources s
    join public.data_datasets d on d.id=s.latest_dataset_id and d.source_id=s.id
    join public.data_dataset_versions v on v.id=s.latest_version_id and v.dataset_id=d.id
    where s.id='cccccccc-0000-4000-8000-000000000001'
      and d.id=v_dataset_id and v.id=v_version_id
  ) then raise exception 'API source latest pointers are inconsistent'; end if;
  select disposition into v_disposition from public.reserve_source_ingestion151(
    1,'11111111-1111-4111-8111-111111111111',
    'cccccccc-0000-4000-8000-000000000001',7,'api-orders-151',7200
  );
  if v_disposition <> 'succeeded' then raise exception 'API replay was not idempotent'; end if;
  if (select count(*) from public.data_source_ingestion_runs
      where source_id='cccccccc-0000-4000-8000-000000000001') <> 1 then
    raise exception 'API replay duplicated run';
  end if;
  begin
    perform public.reserve_source_ingestion151(
      2,'99999999-9999-4999-8999-999999999999',
      'cccccccc-0000-4000-8000-000000000001',9,'api-cross-tenant',7200
    );
    raise exception 'cross-tenant API source was accepted';
  exception when sqlstate 'P0001' then
    if sqlerrm <> 'data_source_not_available' then raise; end if;
  end;
end;
$$;

select case when schema_version = 153 then 'migration_151_compatibility_passed'
            else 'migration_151_compatibility_failed' end as result
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

echo "migration_151_concurrent_claim_passed"

RESERVE_ONE="/tmp/${CONTAINER_NAME}-reserve-one"
RESERVE_TWO="/tmp/${CONTAINER_NAME}-reserve-two"
docker exec "${CONTAINER_NAME}" psql -At -v ON_ERROR_STOP=1 -U postgres -c \
  "select disposition from public.reserve_source_ingestion151(1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',7,'api-concurrent-151',7200)" >"${RESERVE_ONE}" &
RESERVE_PID_ONE=$!
docker exec "${CONTAINER_NAME}" psql -At -v ON_ERROR_STOP=1 -U postgres -c \
  "select disposition from public.reserve_source_ingestion151(1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',7,'api-concurrent-151',7200)" >"${RESERVE_TWO}" &
RESERVE_PID_TWO=$!
wait "${RESERVE_PID_ONE}"
wait "${RESERVE_PID_TWO}"
if [[ "$(sort "${RESERVE_ONE}" "${RESERVE_TWO}" | tr '\n' ' ')" != "in_progress reserved " ]]; then
  echo "concurrent API reservation did not serialize safely" >&2
  exit 1
fi
RUN_COUNT="$(docker exec "${CONTAINER_NAME}" psql -At -v ON_ERROR_STOP=1 -U postgres -c \
  "select count(*) from public.data_source_ingestion_runs where source_id='cccccccc-0000-4000-8000-000000000001' and idempotency_key='api-concurrent-151'")"
rm -f "${RESERVE_ONE}" "${RESERVE_TWO}"
if [[ "${RUN_COUNT}" != "1" ]]; then
  echo "concurrent API reservation duplicated a run" >&2
  exit 1
fi
echo "migration_151_concurrent_reservation_passed"

docker exec -i "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres <<'SQL'
do $$
declare
  v_run_id uuid;
  v_old_token uuid;
  v_new_token uuid;
begin
  select id,lease_token into v_run_id,v_old_token
  from public.data_source_ingestion_runs
  where source_id='cccccccc-0000-4000-8000-000000000001'
    and idempotency_key='api-concurrent-151';
  update public.data_source_ingestion_runs set lease_expires_at=now()-interval '1 minute'
  where id=v_run_id;
  select lease_token into v_new_token
  from public.claim_stale_source_ingestions150('api-recovery',1,now(),900)
  where id=v_run_id;
  if v_new_token is null or v_new_token=v_old_token then
    raise exception 'API ingestion was not fenced after expiry';
  end if;
  begin
    perform public.complete_source_ingestion151(
      1,'11111111-1111-4111-8111-111111111111',
      'cccccccc-0000-4000-8000-000000000001',7,v_run_id,v_old_token,
      'Late API data','55555555-5555-4555-8555-555555555552','late-api.csv',
      'text/csv','.csv',18,repeat('b',64),'{}'::jsonb,'{}'::jsonb
    );
    raise exception 'late API completion was accepted';
  exception when sqlstate 'P0001' then
    if sqlerrm <> 'ingestion_lease_lost' then raise; end if;
  end;
  perform public.settle_source_ingestion_reconciliation150(
    v_run_id,v_new_token,'ambiguous','storage_reservation_untracked',86400
  );
end;
$$;
SQL
echo "migration_151_late_api_completion_fenced"

docker exec -i "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres <<'SQL'
insert into public.storage_reservations(id,tenant_id,user_id,category,bytes,status) values
  ('15200000-0000-4000-8000-000000000001',1,7,'dataset',100,'committed'),
  ('15200000-0000-4000-8000-000000000002',1,7,'dataset',100,'committed'),
  ('15200000-0000-4000-8000-000000000003',1,7,'dataset',100,'committed'),
  ('15200000-0000-4000-8000-000000000004',1,7,'dataset',100,'committed'),
  ('15200000-0000-4000-8000-000000000005',1,7,'dataset',100,'committed'),
  ('15200000-0000-4000-8000-000000000006',1,7,'dataset',500000,'committed'),
  ('15200000-0000-4000-8000-000000000007',1,7,'dataset',100,'committed'),
  ('15200000-0000-4000-8000-000000000008',1,7,'dataset',100,'committed');
insert into public.storage_objects(
  id,reservation_id,tenant_id,user_id,category,storage_key,status,size_bytes,sha256
) values
  ('15210000-0000-4000-8000-000000000001','15200000-0000-4000-8000-000000000001',1,7,'dataset','tenant_1/user_7/inc1.csv','active',100,repeat('a',64)),
  ('15210000-0000-4000-8000-000000000002','15200000-0000-4000-8000-000000000002',1,7,'dataset','tenant_1/user_7/inc2.csv','active',100,repeat('b',64)),
  ('15210000-0000-4000-8000-000000000003','15200000-0000-4000-8000-000000000003',1,7,'dataset','tenant_1/user_7/inc3.csv','active',100,repeat('c',64)),
  ('15210000-0000-4000-8000-000000000004','15200000-0000-4000-8000-000000000004',1,7,'dataset','tenant_1/user_7/customers.csv','active',100,repeat('d',64)),
  ('15210000-0000-4000-8000-000000000005','15200000-0000-4000-8000-000000000005',1,7,'dataset','tenant_1/user_7/checkpoint.csv','active',100,repeat('e',64)),
  ('15210000-0000-4000-8000-000000000006','15200000-0000-4000-8000-000000000006',1,7,'dataset','tenant_1/user_7/benchmark.csv','active',500000,repeat('0',64)),
  ('15210000-0000-4000-8000-000000000007','15200000-0000-4000-8000-000000000007',1,7,'dataset','tenant_1/user_7/conflict-a.csv','active',100,repeat('7',64)),
  ('15210000-0000-4000-8000-000000000008','15200000-0000-4000-8000-000000000008',1,7,'dataset','tenant_1/user_7/conflict-b.csv','active',100,repeat('8',64));

do $$
declare
  v_run uuid; v_token uuid; v_resource uuid; v_dataset uuid; v_revision bigint;
  v_first_dataset uuid; v_customer_dataset uuid;
begin
  select ingestion_run_id,lease_token,source_resource_id into v_run,v_token,v_resource
  from public.reserve_incremental_source_ingestion152(
    1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',7,
    'orders','incremental-orders-1','Orders',7200);
  perform public.attach_source_ingestion_reservation150(1,v_run,v_token,'15200000-0000-4000-8000-000000000001');
  perform public.attach_source_ingestion_storage150(1,v_run,v_token,'15210000-0000-4000-8000-000000000001');
  perform public.stage_incremental_changes152(1,v_run,v_token,jsonb_build_array(
    jsonb_build_object('ordinal',1,'source_record_id','A','operation','upsert','source_order',1,'payload',jsonb_build_object('amount',10),'content_hash',repeat('1',64),'schema_fingerprint',repeat('f',64)),
    jsonb_build_object('ordinal',2,'source_record_id','B','operation','upsert','source_order',1,'payload',jsonb_build_object('amount',20),'content_hash',repeat('2',64),'schema_fingerprint',repeat('f',64)),
    jsonb_build_object('ordinal',3,'source_record_id','C','operation','upsert','source_order',1,'payload',jsonb_build_object('amount',30),'content_hash',repeat('3',64),'schema_fingerprint',repeat('f',64))
  ));
  select dataset_id,committed_revision into v_first_dataset,v_revision
  from public.complete_incremental_ingestion152(
    1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',7,
    v_run,v_token,'15210000-0000-4000-8000-000000000001',3,repeat('a',64),'orders:1',repeat('f',64));
  if v_revision <> 1 then raise exception 'first revision incorrect'; end if;

  select ingestion_run_id,lease_token into v_run,v_token
  from public.reserve_incremental_source_ingestion152(
    1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',7,
    'orders','incremental-orders-2','Orders',7200);
  perform public.attach_source_ingestion_reservation150(1,v_run,v_token,'15200000-0000-4000-8000-000000000002');
  perform public.attach_source_ingestion_storage150(1,v_run,v_token,'15210000-0000-4000-8000-000000000002');
  perform public.stage_incremental_changes152(1,v_run,v_token,jsonb_build_array(
    jsonb_build_object('ordinal',1,'source_record_id','B','operation','upsert','source_order',2,'payload',jsonb_build_object('amount',25),'content_hash',repeat('4',64),'schema_fingerprint',repeat('f',64)),
    jsonb_build_object('ordinal',2,'source_record_id','D','operation','upsert','source_order',1,'payload',jsonb_build_object('amount',40),'content_hash',repeat('5',64),'schema_fingerprint',repeat('f',64))
  ));
  select dataset_id,committed_revision into v_dataset,v_revision
  from public.complete_incremental_ingestion152(
    1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',7,
    v_run,v_token,'15210000-0000-4000-8000-000000000002',2,repeat('b',64),'orders:2',repeat('f',64));
  if v_dataset <> v_first_dataset or v_revision <> 2 then
    raise exception 'stable dataset or second revision incorrect';
  end if;

  select ingestion_run_id,lease_token into v_run,v_token
  from public.reserve_incremental_source_ingestion152(
    1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',7,
    'orders','incremental-orders-3','Orders',7200);
  perform public.attach_source_ingestion_reservation150(1,v_run,v_token,'15200000-0000-4000-8000-000000000003');
  perform public.attach_source_ingestion_storage150(1,v_run,v_token,'15210000-0000-4000-8000-000000000003');
  perform public.stage_incremental_changes152(1,v_run,v_token,jsonb_build_array(
    jsonb_build_object('ordinal',1,'source_record_id','D','operation','upsert','source_order',1,'payload',jsonb_build_object('amount',40),'content_hash',repeat('5',64),'schema_fingerprint',repeat('f',64)),
    jsonb_build_object('ordinal',2,'source_record_id','A','operation','delete','source_order',2,'content_hash',repeat('6',64),'schema_fingerprint',repeat('f',64)),
    jsonb_build_object('ordinal',3,'source_record_id','B','operation','upsert','source_order',1,'payload',jsonb_build_object('amount',21),'content_hash',repeat('7',64),'schema_fingerprint',repeat('f',64))
  ));
  select dataset_id,committed_revision into v_dataset,v_revision
  from public.complete_incremental_ingestion152(
    1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',7,
    v_run,v_token,'15210000-0000-4000-8000-000000000003',3,repeat('c',64),'orders:3',repeat('f',64));
  if v_dataset <> v_first_dataset or v_revision <> 3 then
    raise exception 'stable dataset or third revision incorrect';
  end if;
  if (select count(*) from public.data_dataset_current_records
      where dataset_id=v_first_dataset and not is_deleted) <> 3
     or exists(select 1 from public.data_dataset_current_records
       where dataset_id=v_first_dataset and source_record_id='A' and not is_deleted)
     or (select payload->>'amount' from public.data_dataset_current_records
       where dataset_id=v_first_dataset and source_record_id='B') <> '25'
     or not exists(select 1 from public.data_dataset_record_changes
       where dataset_id=v_first_dataset and committed_revision=3
         and source_record_id='D' and outcome='duplicate')
     or not exists(select 1 from public.data_dataset_record_changes
       where dataset_id=v_first_dataset and committed_revision=3
         and source_record_id='B' and outcome='stale_ignored') then
    raise exception 'incremental current state or history incorrect';
  end if;

  select ingestion_run_id,lease_token,source_resource_id into v_run,v_token,v_resource
  from public.reserve_incremental_source_ingestion152(
    1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',7,
    'customers','incremental-customers-1','Customers',7200);
  perform public.attach_source_ingestion_reservation150(1,v_run,v_token,'15200000-0000-4000-8000-000000000004');
  perform public.attach_source_ingestion_storage150(1,v_run,v_token,'15210000-0000-4000-8000-000000000004');
  perform public.stage_incremental_changes152(1,v_run,v_token,jsonb_build_array(
    jsonb_build_object('ordinal',1,'source_record_id','customer-A','operation','upsert','source_order',1,'payload',jsonb_build_object('name','Ada'),'content_hash',repeat('8',64),'schema_fingerprint',repeat('9',64))
  ));
  select dataset_id into v_customer_dataset
  from public.complete_incremental_ingestion152(
    1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',7,
    v_run,v_token,'15210000-0000-4000-8000-000000000004',1,repeat('d',64),'customers:1',repeat('9',64));
  if v_customer_dataset = v_first_dataset then
    raise exception 'source resources shared one dataset';
  end if;

  begin
    update public.storage_objects set status='deleted'
    where id='15210000-0000-4000-8000-000000000001';
    raise exception 'referenced incremental history was deletable';
  exception when sqlstate 'P0001' then
    if sqlerrm <> 'incremental_history_storage_referenced' then raise; end if;
  end;

  begin
    perform public.reserve_incremental_source_ingestion152(
      2,'99999999-9999-4999-8999-999999999999','cccccccc-0000-4000-8000-000000000001',9,
      'orders','cross-tenant-152','Orders',7200);
    raise exception 'cross-tenant incremental reservation accepted';
  exception when sqlstate 'P0001' then
    if sqlerrm <> 'data_source_not_available' then raise; end if;
  end;
end;
$$;

do $$
begin
  if (select schema_version from public.application_schema_state where contract_key='core') <> 153 then
    raise exception 'schema153 was not recorded';
  end if;
  if (select count(*) from public.data_source_resources
      where source_id='cccccccc-0000-4000-8000-000000000001') <> 2 then
    raise exception 'source resource separation incorrect';
  end if;
end;
$$;

do $$
declare
  v_resource uuid; v_dataset uuid; v_checkpoint uuid; v_version uuid;
  v_version_number integer; v_target bigint;
begin
  select id,dataset_id into v_resource,v_dataset from public.data_source_resources
  where source_id='cccccccc-0000-4000-8000-000000000001' and resource_key='orders';
  select id into v_checkpoint from public.request_dataset_checkpoint152(
    1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',
    v_resource,v_dataset,7,2
  );
  select version_id,version_number,target_revision into v_version,v_version_number,v_target
  from public.publish_dataset_checkpoint152(
    v_checkpoint,'15210000-0000-4000-8000-000000000005','orders-revision-2.csv',
    100,repeat('e',64),4,repeat('a',64)
  );
  if v_version is null or v_version_number <> 1 or v_target <> 2 then
    raise exception 'sparse checkpoint publication failed';
  end if;
  if not exists(select 1 from public.data_dataset_versions
    where id=v_version and version_kind='checkpoint'
      and provenance->>'dataset_revision'='2') then
    raise exception 'checkpoint revision provenance missing';
  end if;
  if (select committed_revision from public.data_source_resources where id=v_resource) <> 3 then
    raise exception 'older checkpoint changed committed resource revision';
  end if;
end;
$$;

create temporary table incremental_benchmark152(
  elapsed_ms numeric, records_per_second numeric, database_growth_bytes bigint,
  current_rows bigint, history_rows bigint, accounted_chunk_bytes bigint
);
do $$
declare
  v_run uuid; v_token uuid; v_start timestamptz; v_elapsed numeric;
  v_before bigint; v_after bigint; v_start_ordinal integer;
begin
  select coalesce(sum(pg_total_relation_size(name::regclass)),0) into v_before
  from unnest(array[
    'public.data_dataset_current_records',
    'public.data_dataset_record_changes',
    'public.data_ingestion_staged_changes'
  ]) name;
  select ingestion_run_id,lease_token into v_run,v_token
  from public.reserve_incremental_source_ingestion152(
    1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',7,
    'benchmark','incremental-benchmark-5000','Benchmark',7200);
  perform public.attach_source_ingestion_reservation150(
    1,v_run,v_token,'15200000-0000-4000-8000-000000000006');
  perform public.attach_source_ingestion_storage150(
    1,v_run,v_token,'15210000-0000-4000-8000-000000000006');
  v_start := clock_timestamp();
  for v_start_ordinal in 0..9 loop
    perform public.stage_incremental_changes152(
      1,v_run,v_token,
      (select jsonb_agg(jsonb_build_object(
        'ordinal',i,'source_record_id',format('bench-%s',i),'operation','upsert',
        'source_order',1,'payload',jsonb_build_object('value',i),
        'content_hash',md5(i::text)||md5(i::text),
        'schema_fingerprint',repeat('b',64)
      ) order by i)
      from generate_series(v_start_ordinal*500+1,v_start_ordinal*500+500) i)
    );
  end loop;
  perform * from public.complete_incremental_ingestion152(
    1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',7,
    v_run,v_token,'15210000-0000-4000-8000-000000000006',5000,repeat('0',64),
    'benchmark:5000',repeat('b',64));
  v_elapsed := extract(epoch from clock_timestamp()-v_start)*1000;
  select coalesce(sum(pg_total_relation_size(name::regclass)),0) into v_after
  from unnest(array[
    'public.data_dataset_current_records',
    'public.data_dataset_record_changes',
    'public.data_ingestion_staged_changes'
  ]) name;
  insert into incremental_benchmark152 values(
    round(v_elapsed,2),round(5000000/v_elapsed,2),v_after-v_before,
    (select count(*) from public.data_dataset_current_records c
      join public.data_datasets d on d.id=c.dataset_id
      where d.display_name='Benchmark'),
    (select count(*) from public.data_dataset_record_changes c
      join public.data_datasets d on d.id=c.dataset_id
      where d.display_name='Benchmark'),500000
  );
end;
$$;
select json_build_object(
  'elapsed_ms',elapsed_ms,'records_per_second',records_per_second,
  'database_growth_bytes',database_growth_bytes,'current_rows',current_rows,
  'history_rows',history_rows,'accounted_chunk_bytes',accounted_chunk_bytes
) as migration_152_benchmark from incremental_benchmark152;

do $$
declare v_run_a uuid; v_run_b uuid; v_token_a uuid; v_token_b uuid;
begin
  select ingestion_run_id,lease_token into v_run_a,v_token_a
  from public.reserve_incremental_source_ingestion152(
    1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',7,
    'benchmark','incremental-conflict-a','Benchmark',7200);
  select ingestion_run_id,lease_token into v_run_b,v_token_b
  from public.reserve_incremental_source_ingestion152(
    1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',7,
    'benchmark','incremental-conflict-b','Benchmark',7200);
  perform public.attach_source_ingestion_reservation150(1,v_run_a,v_token_a,'15200000-0000-4000-8000-000000000007');
  perform public.attach_source_ingestion_storage150(1,v_run_a,v_token_a,'15210000-0000-4000-8000-000000000007');
  perform public.attach_source_ingestion_reservation150(1,v_run_b,v_token_b,'15200000-0000-4000-8000-000000000008');
  perform public.attach_source_ingestion_storage150(1,v_run_b,v_token_b,'15210000-0000-4000-8000-000000000008');
  perform public.stage_incremental_changes152(1,v_run_a,v_token_a,jsonb_build_array(
    jsonb_build_object('ordinal',1,'source_record_id','bench-1','operation','upsert',
      'source_order',1,'payload',jsonb_build_object('value',1),
      'content_hash',md5('1')||md5('1'),'schema_fingerprint',repeat('b',64))));
  perform public.stage_incremental_changes152(1,v_run_b,v_token_b,jsonb_build_array(
    jsonb_build_object('ordinal',1,'source_record_id','bench-1','operation','upsert',
      'source_order',1,'payload',jsonb_build_object('value',1),
      'content_hash',md5('1')||md5('1'),'schema_fingerprint',repeat('b',64))));
  perform * from public.complete_incremental_ingestion152(
    1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',7,
    v_run_a,v_token_a,'15210000-0000-4000-8000-000000000007',1,repeat('7',64),
    'benchmark:5001',repeat('b',64));
  begin
    perform * from public.complete_incremental_ingestion152(
      1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',7,
      v_run_b,v_token_b,'15210000-0000-4000-8000-000000000008',1,repeat('8',64),
      'benchmark:5001',repeat('b',64));
    raise exception 'stale cursor completion was accepted';
  exception when sqlstate 'P0001' then
    if sqlerrm <> 'incremental_cursor_conflict' then raise; end if;
  end;
  update public.storage_objects set status='deleted' where id='15210000-0000-4000-8000-000000000008';
  update public.storage_reservations set status='released',finished_at=now()
  where id='15200000-0000-4000-8000-000000000008';
  perform public.fail_source_ingestion150(
    1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',7,
    v_run_b,v_token_b,'abandoned_ingestion');
  if exists(select 1 from public.data_ingestion_staged_changes where ingestion_run_id=v_run_b) then
    raise exception 'failed incremental staging was not cleaned';
  end if;
end;
$$;
SQL
echo "migration_152_incremental_three_batch_passed"

docker exec -i "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres <<'SQL'
insert into public.storage_reservations(id,tenant_id,user_id,category,bytes,status) values
  ('15300000-0000-4000-8000-000000000001',1,7,'dataset',100,'committed');
insert into public.storage_objects(
  id,reservation_id,tenant_id,user_id,category,storage_key,status,size_bytes,sha256
) values(
  '15310000-0000-4000-8000-000000000001','15300000-0000-4000-8000-000000000001',
  1,7,'dataset','tenant_1/user_7/background-checkpoint.csv','active',100,repeat('f',64)
);

do $$
declare v_checkpoint uuid; v_duplicate uuid; v_token uuid; v_version uuid; v_count integer;
declare v_benchmark_dataset uuid; v_benchmark_resource uuid; v_retry uuid; v_old_token uuid; v_new_token uuid;
begin
  select id into v_checkpoint from public.request_dataset_checkpoint153(
    1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',
    (select id from public.data_source_resources where resource_key='orders'),
    (select dataset_id from public.data_source_resources where resource_key='orders'),7,3);
  select id into v_duplicate from public.request_dataset_checkpoint153(
    1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',
    (select id from public.data_source_resources where resource_key='orders'),
    (select dataset_id from public.data_source_resources where resource_key='orders'),7,3);
  if v_checkpoint <> v_duplicate then raise exception 'duplicate checkpoint job created'; end if;
  select lease_token into v_token from public.claim_dataset_checkpoints153('worker-a',1,900);
  select count(*) into v_count from public.claim_dataset_checkpoints153('worker-b',1,900);
  if v_count <> 0 then raise exception 'competing worker claimed active checkpoint'; end if;
  perform public.prepare_dataset_checkpoint153(v_checkpoint,v_token,'orders-revision-3.csv',3,repeat('e',64));
  perform public.attach_dataset_checkpoint_storage153(
    v_checkpoint,v_token,'15300000-0000-4000-8000-000000000001',null);
  perform public.attach_dataset_checkpoint_storage153(
    v_checkpoint,v_token,null,'15310000-0000-4000-8000-000000000001');
  select version_id into v_version from public.publish_dataset_checkpoint153(v_checkpoint,v_token);
  if v_version is null then raise exception 'background checkpoint not published'; end if;
  perform * from public.publish_dataset_checkpoint153(v_checkpoint,v_token);

  select dataset_id,id into v_benchmark_dataset,v_benchmark_resource
  from public.data_source_resources where resource_key='benchmark';
  select id into v_retry from public.request_dataset_checkpoint153(
    1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',
    v_benchmark_resource,v_benchmark_dataset,7,1);
  select lease_token into v_old_token from public.claim_dataset_checkpoints153('worker-old',1,60);
  update public.data_dataset_checkpoints set lease_expires_at=now()-interval '1 second' where id=v_retry;
  select lease_token into v_new_token from public.claim_expired_dataset_checkpoints153('reconciler',1,300);
  begin
    perform public.prepare_dataset_checkpoint153(v_retry,v_old_token,'stale.csv',1,repeat('a',64));
    raise exception 'expired checkpoint worker was not fenced';
  exception when sqlstate 'P0001' then
    if sqlerrm <> 'checkpoint_lease_lost' then raise; end if;
  end;
  perform public.settle_dataset_checkpoint153(v_retry,v_new_token,'retry','checkpoint_worker_abandoned',1);
  update public.data_dataset_checkpoints set next_attempt_at=now()-interval '1 second' where id=v_retry;
  select lease_token into v_new_token from public.claim_dataset_checkpoints153('worker-2',1,60);
  perform public.settle_dataset_checkpoint153(v_retry,v_new_token,'retry','checkpoint_worker_abandoned',1);
  update public.data_dataset_checkpoints set next_attempt_at=now()-interval '1 second' where id=v_retry;
  select lease_token into v_new_token from public.claim_dataset_checkpoints153('worker-3',1,60);
  perform public.settle_dataset_checkpoint153(v_retry,v_new_token,'retry','checkpoint_worker_abandoned',1);
  if not exists(select 1 from public.data_dataset_checkpoints where id=v_retry and status='failed' and attempt_count=3) then
    raise exception 'checkpoint retries were not bounded';
  end if;
  begin
    perform public.request_dataset_checkpoint153(
      2,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',
      v_benchmark_resource,v_benchmark_dataset,9,1);
    raise exception 'cross-tenant checkpoint request accepted';
  exception when sqlstate 'P0001' then
    if sqlerrm <> 'checkpoint_target_invalid' then raise; end if;
  end;
end;
$$;
select 'migration_153_background_checkpoint_passed' as result;
SQL

if [[ "${RUN_MIGRATION_154:-0}" == "1" ]]; then
  MIGRATION_154="${ROOT_DIR}/web/database/migrations/154_add_shared_immutable_storage.sql"
  REHEARSAL_TMP="$(mktemp -d)"

  # Prove that an error before COMMIT rolls back every schema154 mutation.
  set +e
  {
    sed '$d' "${MIGRATION_154}"
    printf '\nselect 1 / 0;\ncommit;\n'
  } | docker exec -i "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres \
      >"${REHEARSAL_TMP}/rollback.log" 2>&1
  ROLLBACK_STATUS=$?
  set -e
  if [[ "${ROLLBACK_STATUS}" -eq 0 ]]; then
    echo "migration154 rollback probe unexpectedly committed" >&2
    exit 1
  fi
  docker exec -i "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres <<'SQL'
do $$
begin
  if (select schema_version from public.application_schema_state where contract_key='core') <> 153 then
    raise exception 'failed schema154 transaction advanced schema state';
  end if;
  if exists(select 1 from information_schema.columns
    where table_schema='public' and table_name='storage_reservations'
      and column_name='storage_backend')
     or exists(select 1 from information_schema.columns
    where table_schema='public' and table_name='storage_objects'
      and column_name='storage_backend')
     or to_regprocedure('public.prepare_immutable_storage154(uuid,text,text,bigint,text)') is not null then
    raise exception 'failed schema154 transaction left partial schema changes';
  end if;
end;
$$;
SQL
  echo "migration_154_transactional_rollback_passed"

  # Hold the schema-state row, then start two complete migration sessions. Once
  # released, exactly one may advance 153→154; the other must observe 154 and
  # fail in the guarded block before reaching DDL.
  docker exec "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres -c \
    "begin; select schema_version from public.application_schema_state where contract_key='core' for update; select pg_sleep(2); commit;" \
    >"${REHEARSAL_TMP}/blocker.log" 2>&1 &
  BLOCKER_PID=$!
  BLOCKER_READY=0
  for _ in $(seq 1 20); do
    if docker exec "${CONTAINER_NAME}" psql -At -U postgres -c \
      "select count(*) from pg_stat_activity where query like '%select pg_sleep(2)%' and state='active'" \
      | grep -qx '1'; then
      BLOCKER_READY=1
      break
    fi
    sleep 0.1
  done
  if [[ "${BLOCKER_READY}" -ne 1 ]]; then
    echo "migration154 concurrency blocker did not acquire schema-state lock" >&2
    wait "${BLOCKER_PID}" || true
    exit 1
  fi

  docker exec -i "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres \
    < "${MIGRATION_154}" >"${REHEARSAL_TMP}/session-a.log" 2>&1 &
  SESSION_A_PID=$!
  docker exec -i "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres \
    < "${MIGRATION_154}" >"${REHEARSAL_TMP}/session-b.log" 2>&1 &
  SESSION_B_PID=$!
  set +e
  wait "${SESSION_A_PID}"
  SESSION_A_STATUS=$?
  wait "${SESSION_B_PID}"
  SESSION_B_STATUS=$?
  wait "${BLOCKER_PID}"
  BLOCKER_STATUS=$?
  set -e
  if [[ "${BLOCKER_STATUS}" -ne 0 ]] \
     || ! { [[ "${SESSION_A_STATUS}" -eq 0 && "${SESSION_B_STATUS}" -ne 0 ]] \
          || [[ "${SESSION_B_STATUS}" -eq 0 && "${SESSION_A_STATUS}" -ne 0 ]]; }; then
    echo "migration154 competing sessions were not serialized" >&2
    cat "${REHEARSAL_TMP}/session-a.log" >&2
    cat "${REHEARSAL_TMP}/session-b.log" >&2
    exit 1
  fi
  if [[ "${SESSION_A_STATUS}" -ne 0 ]]; then
    FAILED_SESSION_LOG="${REHEARSAL_TMP}/session-a.log"
  else
    FAILED_SESSION_LOG="${REHEARSAL_TMP}/session-b.log"
  fi
  if ! grep -q 'schema154_requires_exact_schema153' "${FAILED_SESSION_LOG}"; then
    echo "migration154 competing session did not fail at predecessor guard" >&2
    cat "${FAILED_SESSION_LOG}" >&2
    exit 1
  fi
  docker exec -i "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres <<'SQL'
do $$
begin
  if (select schema_version from public.application_schema_state where contract_key='core') <> 154 then
    raise exception 'competing schema154 migration did not finish at schema154';
  end if;
  if (select count(*) from information_schema.columns
    where table_schema='public' and table_name='storage_objects'
      and column_name='storage_backend') <> 1 then
    raise exception 'competing schema154 migration produced duplicate or missing DDL';
  end if;
end;
$$;
SQL
  echo "migration_154_two_session_locking_passed"

  docker exec -i "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres \
    < "${ROOT_DIR}/web/scripts/rehearse_migration_154.sql"
  rm -rf "${REHEARSAL_TMP}"
fi

if [[ "${RUN_MIGRATION_155:-0}" == "1" ]]; then
  if [[ "${RUN_MIGRATION_154:-0}" != "1" ]]; then
    echo "migration155 rehearsal requires schema154 rehearsal" >&2
    exit 1
  fi
  MIGRATION_155="${ROOT_DIR}/web/database/migrations/155_add_data_source_credential_vault.sql"
  REHEARSAL_155_TMP="$(mktemp -d)"

  set +e
  {
    sed '$d' "${MIGRATION_155}"
    printf '\nselect 1 / 0;\ncommit;\n'
  } | docker exec -i "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres \
      >"${REHEARSAL_155_TMP}/rollback.log" 2>&1
  ROLLBACK_155_STATUS=$?
  set -e
  if [[ "${ROLLBACK_155_STATUS}" -eq 0 ]]; then
    echo "migration155 rollback probe unexpectedly committed" >&2
    exit 1
  fi
  docker exec -i "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres <<'SQL'
do $$ begin
  if (select schema_version from public.application_schema_state where contract_key='core')<>154
     or to_regclass('public.data_source_credentials') is not null
     or exists(select 1 from information_schema.columns where table_schema='public'
       and table_name='data_sources' and column_name='credential_revision') then
    raise exception 'failed schema155 transaction left partial changes';
  end if;
end $$;
SQL
  echo "migration_155_transactional_rollback_passed"

  docker exec "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres -c \
    "begin; select schema_version from public.application_schema_state where contract_key='core' for update; select pg_sleep(2); commit;" \
    >"${REHEARSAL_155_TMP}/blocker.log" 2>&1 &
  BLOCKER_155_PID=$!
  BLOCKER_155_READY=0
  for _ in $(seq 1 20); do
    if docker exec "${CONTAINER_NAME}" psql -At -U postgres -c \
      "select count(*) from pg_stat_activity where query like '%select pg_sleep(2)%' and state='active'" \
      | grep -qx '1'; then BLOCKER_155_READY=1; break; fi
    sleep 0.1
  done
  if [[ "${BLOCKER_155_READY}" -ne 1 ]]; then
    echo "migration155 concurrency blocker did not acquire schema-state lock" >&2
    wait "${BLOCKER_155_PID}" || true
    exit 1
  fi
  docker exec -i "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres \
    <"${MIGRATION_155}" >"${REHEARSAL_155_TMP}/session-a.log" 2>&1 &
  SESSION_155_A_PID=$!
  docker exec -i "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres \
    <"${MIGRATION_155}" >"${REHEARSAL_155_TMP}/session-b.log" 2>&1 &
  SESSION_155_B_PID=$!
  set +e
  wait "${SESSION_155_A_PID}"; SESSION_155_A_STATUS=$?
  wait "${SESSION_155_B_PID}"; SESSION_155_B_STATUS=$?
  wait "${BLOCKER_155_PID}"; BLOCKER_155_STATUS=$?
  set -e
  if [[ "${BLOCKER_155_STATUS}" -ne 0 ]] \
     || ! { [[ "${SESSION_155_A_STATUS}" -eq 0 && "${SESSION_155_B_STATUS}" -ne 0 ]] \
          || [[ "${SESSION_155_B_STATUS}" -eq 0 && "${SESSION_155_A_STATUS}" -ne 0 ]]; }; then
    echo "migration155 competing sessions were not serialized" >&2
    cat "${REHEARSAL_155_TMP}/session-a.log" >&2
    cat "${REHEARSAL_155_TMP}/session-b.log" >&2
    exit 1
  fi
  FAILED_155_LOG="${REHEARSAL_155_TMP}/session-a.log"
  [[ "${SESSION_155_A_STATUS}" -eq 0 ]] && FAILED_155_LOG="${REHEARSAL_155_TMP}/session-b.log"
  grep -q 'migration_155_expected_schema_154_got_155' "${FAILED_155_LOG}"
  echo "migration_155_two_session_locking_passed"

  CREDENTIAL_ONE="${REHEARSAL_155_TMP}/credential-one.log"
  CREDENTIAL_TWO="${REHEARSAL_155_TMP}/credential-two.log"
  ACTIVATE_ONE="select * from public.activate_data_source_credential155(1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',7,'synthetic_orders','bearer','15500000-0000-4000-8000-000000000001',1,0,'test','AAAAAAAAAAAAAAAAAAAAAAAA','MTIzNDU2Nzg5MDEy','vault:v1:YWJj','madar-data-sources',1,1,null);"
  ACTIVATE_TWO="select * from public.activate_data_source_credential155(1,'11111111-1111-4111-8111-111111111111','cccccccc-0000-4000-8000-000000000001',7,'synthetic_orders','bearer','15500000-0000-4000-8000-000000000002',1,0,'test','BBBBBBBBBBBBBBBBBBBBBBBB','MTIzNDU2Nzg5MDEy','vault:v1:ZGVm','madar-data-sources',1,1,null);"
  set +e
  docker exec "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres -c "${ACTIVATE_ONE}" >"${CREDENTIAL_ONE}" 2>&1 & CREDENTIAL_ONE_PID=$!
  docker exec "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres -c "${ACTIVATE_TWO}" >"${CREDENTIAL_TWO}" 2>&1 & CREDENTIAL_TWO_PID=$!
  wait "${CREDENTIAL_ONE_PID}"; CREDENTIAL_ONE_STATUS=$?
  wait "${CREDENTIAL_TWO_PID}"; CREDENTIAL_TWO_STATUS=$?
  set -e
  if ! { [[ "${CREDENTIAL_ONE_STATUS}" -eq 0 && "${CREDENTIAL_TWO_STATUS}" -ne 0 ]] \
       || [[ "${CREDENTIAL_TWO_STATUS}" -eq 0 && "${CREDENTIAL_ONE_STATUS}" -ne 0 ]]; }; then
    echo "concurrent credential activation did not serialize" >&2
    exit 1
  fi

  docker exec -i "${CONTAINER_NAME}" psql -v ON_ERROR_STOP=1 -U postgres <<'SQL'
do $$ declare v_id uuid;v_version integer;v_revision bigint;v_active uuid;
declare v_wrapped text;v_ciphertext text;
begin
  if (select schema_version from public.application_schema_state where contract_key='core')<>155
     or (select count(*) from public.data_source_credentials where status='active')<>1 then
    raise exception 'schema155 activation state invalid';end if;
  select active_credential_id,credential_revision into v_active,v_revision
  from public.data_sources where id='cccccccc-0000-4000-8000-000000000001';
  if v_active is null or v_revision<>1 then raise exception 'active credential reference invalid';end if;
  select credential_id,credential_version,source_revision into v_id,v_version,v_revision
  from public.prepare_data_source_credential155(1,'11111111-1111-4111-8111-111111111111',
    'cccccccc-0000-4000-8000-000000000001',7,'synthetic_orders','bearer');
  if v_version<>2 or v_revision<>1 or v_id is null then raise exception 'rotation preparation invalid';end if;
  begin
    perform public.prepare_data_source_credential155(2,'99999999-9999-4999-8999-999999999999',
      'cccccccc-0000-4000-8000-000000000001',9,'synthetic_orders','bearer');
    raise exception 'cross-tenant credential preparation accepted';
  exception when sqlstate '42501' then null;end;
  if has_table_privilege('authenticated','public.data_source_credentials','select')
     or has_function_privilege('authenticated','public.resolve_data_source_credential155(integer,uuid,uuid,integer,text,text)','execute') then
    raise exception 'browser credential privileges granted';end if;
  begin
    update public.data_source_credential_events set event_code='changed' where id=(select min(id) from public.data_source_credential_events);
    raise exception 'credential audit mutation accepted';
  exception when sqlstate '42501' then null;end;
  select wrapped_data_key,ciphertext into v_wrapped,v_ciphertext
  from public.data_source_credentials where id=v_active;
  perform public.complete_data_source_credential_rewrap155(
    1,'11111111-1111-4111-8111-111111111111',
    'cccccccc-0000-4000-8000-000000000001',7,'synthetic_orders',v_active,
    v_wrapped,1,'vault:v2:cmV3cmFwcGVk',2);
  if not exists(select 1 from public.data_source_credentials where id=v_active
      and wrapped_data_key='vault:v2:cmV3cmFwcGVk' and key_version=2
      and ciphertext=v_ciphertext and rewrapped_at is not null)
     or not exists(select 1 from public.data_source_credential_events
      where credential_id=v_active and event_type='rewrapped') then
    raise exception 'credential rewrap was not immutable and audited';end if;
  perform public.revoke_data_source_credential155(1,'11111111-1111-4111-8111-111111111111',
    'cccccccc-0000-4000-8000-000000000001',7,'synthetic_orders',1);
  if public.assert_data_source_credential155(1,'11111111-1111-4111-8111-111111111111',
    'cccccccc-0000-4000-8000-000000000001',7,'synthetic_orders',v_active,1,1) then
    raise exception 'revoked credential remained valid';end if;
end $$;
select 'migration_155_credential_isolation_passed' as result;
SQL
fi
