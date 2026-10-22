#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POSTGRES_IMAGE="postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73"
CONTAINER_NAME="madar-migration-149-${RANDOM}-$$"

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
create table public.storage_objects(
  id uuid primary key,
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
insert into public.storage_objects values
  ('55555555-5555-4555-8555-555555555551', 1, 7, 'dataset', 'tenant_1/user_7/one.csv', 'active', 18, repeat('a', 64)),
  ('55555555-5555-4555-8555-555555555552', 1, 7, 'dataset', 'tenant_1/user_7/two.csv', 'active', 18, repeat('b', 64));
SQL

for migration in 147_add_project_datasets.sql 148_add_project_data_sources.sql 149_add_source_ingestion_runs.sql; do
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

select case when schema_version = 149 then 'migration_149_rehearsal_passed'
            else 'migration_149_rehearsal_failed' end as result
from public.application_schema_state where contract_key = 'core';
SQL
