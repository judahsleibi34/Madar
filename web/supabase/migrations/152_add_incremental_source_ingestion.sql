begin;

do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version into v_schema_version
  from public.application_schema_state where contract_key = 'core' for update;
  if v_schema_version is null then
    raise exception using errcode = 'P0001', message = 'migration_152_schema_state_missing';
  end if;
  if v_schema_version <> 151 then
    raise exception using errcode = 'P0001',
      message = format('migration_152_expected_schema_151_got_%s', v_schema_version);
  end if;
end;
$$;

create table public.data_source_resources (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  project_id uuid not null,
  source_id uuid not null,
  resource_key text not null,
  dataset_id uuid,
  committed_revision bigint not null default 0,
  committed_cursor text,
  schema_fingerprint text,
  latest_checkpoint_version_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint data_source_resources_source_fk152
    foreign key(source_id, tenant_id, project_id)
    references public.data_sources(id, tenant_id, project_id) on delete restrict,
  constraint data_source_resources_key_check152
    check(resource_key ~ '^[a-z][a-z0-9_]{1,79}$'),
  constraint data_source_resources_revision_check152 check(committed_revision >= 0),
  constraint data_source_resources_cursor_check152
    check(committed_cursor is null or length(committed_cursor) between 1 and 1024),
  constraint data_source_resources_schema_check152
    check(schema_fingerprint is null or schema_fingerprint ~ '^[0-9a-f]{64}$'),
  constraint data_source_resources_identity_unique152
    unique(tenant_id, project_id, source_id, resource_key),
  constraint data_source_resources_id_tenant_project_source_unique152
    unique(id, tenant_id, project_id, source_id)
);

create unique index storage_objects_id_tenant_unique152
on public.storage_objects(id, tenant_id);

create trigger set_data_source_resources_updated_at152
before update on public.data_source_resources
for each row execute function public.set_updated_at();

alter table public.data_datasets
  add column dataset_mode text not null default 'file_snapshot',
  add column source_resource_id uuid,
  add column committed_revision bigint not null default 0,
  add constraint data_datasets_mode_check152
    check(dataset_mode in ('file_snapshot', 'incremental_records')),
  add constraint data_datasets_revision_check152 check(committed_revision >= 0),
  add constraint data_datasets_resource_fk152
    foreign key(source_resource_id, tenant_id, project_id, source_id)
    references public.data_source_resources(id, tenant_id, project_id, source_id)
    on delete restrict,
  add constraint data_datasets_source_resource_unique152 unique(source_resource_id),
  add constraint data_datasets_incremental_shape_check152 check(
    (dataset_mode = 'file_snapshot' and source_resource_id is null and committed_revision = 0)
    or
    (dataset_mode = 'incremental_records' and source_id is not null and source_resource_id is not null)
  );

alter table public.data_source_resources
  add constraint data_source_resources_dataset_fk152
    foreign key(dataset_id, tenant_id, project_id, source_id)
    references public.data_datasets(id, tenant_id, project_id, source_id)
    on delete restrict;

alter table public.data_dataset_versions
  drop constraint data_dataset_versions_kind_check147,
  add constraint data_dataset_versions_kind_check152
    check(version_kind in ('original', 'derived', 'checkpoint'));

alter table public.data_source_ingestion_runs
  add column ingestion_kind text not null default 'snapshot',
  add column source_resource_id uuid,
  add column expected_cursor text,
  add column next_cursor text,
  add column committed_revision bigint,
  add column manifest_hash text,
  add column staged_change_count integer,
  add constraint data_source_ingestion_runs_kind_check152
    check(ingestion_kind in ('snapshot', 'incremental')),
  add constraint data_source_ingestion_runs_resource_fk152
    foreign key(source_resource_id, tenant_id, project_id, source_id)
    references public.data_source_resources(id, tenant_id, project_id, source_id)
    on delete restrict,
  add constraint data_source_ingestion_runs_cursor_check152 check(
    (expected_cursor is null or length(expected_cursor) between 1 and 1024)
    and (next_cursor is null or length(next_cursor) between 1 and 1024)
  ),
  add constraint data_source_ingestion_runs_revision_check152
    check(committed_revision is null or committed_revision > 0),
  add constraint data_source_ingestion_runs_manifest_check152
    check(manifest_hash is null or manifest_hash ~ '^[0-9a-f]{64}$'),
  add constraint data_source_ingestion_runs_staged_count_check152
    check(staged_change_count is null or staged_change_count between 1 and 10000);

alter table public.data_source_ingestion_runs
  drop constraint data_source_ingestion_runs_result_pair_check149,
  drop constraint data_source_ingestion_runs_terminal_check149,
  add constraint data_source_ingestion_runs_result_shape_check152 check(
    result_version_id is null or result_dataset_id is not null
  ),
  add constraint data_source_ingestion_runs_terminal_check152 check(
    (status in ('pending', 'processing') and completed_at is null
      and result_dataset_id is null and result_version_id is null
      and committed_revision is null and failure_code is null)
    or
    (status = 'succeeded' and completed_at is not null and failure_code is null and (
      (ingestion_kind = 'snapshot' and result_dataset_id is not null
        and result_version_id is not null and committed_revision is null)
      or
      (ingestion_kind = 'incremental' and result_dataset_id is not null
        and committed_revision is not null)
    ))
    or
    (status = 'failed' and completed_at is not null and result_dataset_id is null
      and result_version_id is null and committed_revision is null
      and failure_code is not null)
  ),
  add constraint data_source_ingestion_runs_incremental_shape_check152 check(
    (ingestion_kind = 'snapshot' and source_resource_id is null
      and expected_cursor is null and next_cursor is null
      and manifest_hash is null and staged_change_count is null)
    or
    (ingestion_kind = 'incremental' and source_resource_id is not null)
  );

create table public.data_ingestion_staged_changes (
  id bigint generated always as identity primary key,
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  ingestion_run_id uuid not null references public.data_source_ingestion_runs(id) on delete cascade,
  source_resource_id uuid not null references public.data_source_resources(id) on delete cascade,
  row_ordinal integer not null,
  source_record_id text not null,
  operation text not null,
  source_order bigint,
  source_event_id text,
  payload jsonb,
  content_hash text not null,
  schema_fingerprint text not null,
  created_at timestamptz not null default now(),
  constraint data_ingestion_staged_ordinal_check152 check(row_ordinal between 1 and 10000),
  constraint data_ingestion_staged_record_check152
    check(length(source_record_id) between 1 and 255),
  constraint data_ingestion_staged_operation_check152 check(operation in ('upsert', 'delete')),
  constraint data_ingestion_staged_payload_check152 check(
    (operation = 'upsert' and jsonb_typeof(payload) = 'object')
    or (operation = 'delete' and payload is null)
  ),
  constraint data_ingestion_staged_event_check152
    check(source_event_id is null or length(source_event_id) between 1 and 255),
  constraint data_ingestion_staged_hash_check152 check(content_hash ~ '^[0-9a-f]{64}$'),
  constraint data_ingestion_staged_schema_check152 check(schema_fingerprint ~ '^[0-9a-f]{64}$'),
  constraint data_ingestion_staged_run_ordinal_unique152 unique(ingestion_run_id, row_ordinal),
  constraint data_ingestion_staged_run_record_unique152 unique(ingestion_run_id, source_record_id)
);

create index data_ingestion_staged_run152
on public.data_ingestion_staged_changes(tenant_id, ingestion_run_id, row_ordinal);

create table public.data_dataset_current_records (
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  dataset_id uuid not null,
  source_record_id text not null,
  payload jsonb,
  content_hash text not null,
  source_order bigint,
  is_deleted boolean not null default false,
  schema_fingerprint text not null,
  last_committed_revision bigint not null,
  last_ingestion_run_id uuid not null references public.data_source_ingestion_runs(id) on delete restrict,
  updated_at timestamptz not null default now(),
  primary key(tenant_id, dataset_id, source_record_id),
  constraint data_dataset_current_dataset_fk152
    foreign key(dataset_id, tenant_id)
    references public.data_datasets(id, tenant_id) on delete cascade,
  constraint data_dataset_current_record_check152
    check(length(source_record_id) between 1 and 255),
  constraint data_dataset_current_payload_check152 check(
    (not is_deleted and jsonb_typeof(payload) = 'object')
    or (is_deleted and payload is null)
  ),
  constraint data_dataset_current_hash_check152 check(content_hash ~ '^[0-9a-f]{64}$'),
  constraint data_dataset_current_schema_check152 check(schema_fingerprint ~ '^[0-9a-f]{64}$'),
  constraint data_dataset_current_revision_check152 check(last_committed_revision > 0)
);

create index data_dataset_current_active152
on public.data_dataset_current_records(tenant_id, dataset_id, source_record_id)
where not is_deleted;

create table public.data_dataset_record_changes (
  id bigint generated always as identity primary key,
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  project_id uuid not null,
  source_id uuid not null,
  source_resource_id uuid not null,
  dataset_id uuid not null,
  committed_revision bigint not null,
  ingestion_run_id uuid not null references public.data_source_ingestion_runs(id) on delete restrict,
  storage_object_id uuid not null,
  row_ordinal integer not null,
  source_record_id text not null,
  operation text not null,
  outcome text not null,
  source_order bigint,
  source_event_id text,
  content_hash text not null,
  schema_fingerprint text not null,
  created_at timestamptz not null default now(),
  constraint data_dataset_changes_dataset_fk152
    foreign key(dataset_id, tenant_id, project_id, source_id)
    references public.data_datasets(id, tenant_id, project_id, source_id) on delete restrict,
  constraint data_dataset_changes_resource_fk152
    foreign key(source_resource_id, tenant_id, project_id, source_id)
    references public.data_source_resources(id, tenant_id, project_id, source_id) on delete restrict,
  constraint data_dataset_changes_storage_fk152
    foreign key(storage_object_id, tenant_id)
    references public.storage_objects(id, tenant_id) on delete restrict,
  constraint data_dataset_changes_revision_check152 check(committed_revision > 0),
  constraint data_dataset_changes_ordinal_check152 check(row_ordinal between 1 and 10000),
  constraint data_dataset_changes_record_check152 check(length(source_record_id) between 1 and 255),
  constraint data_dataset_changes_operation_check152 check(operation in ('upsert', 'delete')),
  constraint data_dataset_changes_outcome_check152
    check(outcome in ('inserted', 'updated', 'deleted', 'duplicate', 'stale_ignored')),
  constraint data_dataset_changes_hash_check152 check(content_hash ~ '^[0-9a-f]{64}$'),
  constraint data_dataset_changes_schema_check152 check(schema_fingerprint ~ '^[0-9a-f]{64}$'),
  constraint data_dataset_changes_run_ordinal_unique152 unique(ingestion_run_id, row_ordinal),
  constraint data_dataset_changes_revision_ordinal_unique152
    unique(dataset_id, committed_revision, row_ordinal)
);

create index data_dataset_changes_reconstruct152
on public.data_dataset_record_changes(tenant_id, dataset_id, committed_revision, row_ordinal);
create index data_dataset_changes_record_history152
on public.data_dataset_record_changes(tenant_id, dataset_id, source_record_id, committed_revision);

create function public.protect_incremental_history_storage152()
returns trigger language plpgsql set search_path = '' as $$
begin
  if old.status = 'active' and new.status <> 'active'
     and exists(select 1 from public.data_dataset_record_changes c
       where c.storage_object_id = old.id) then
    raise exception using errcode = 'P0001', message = 'incremental_history_storage_referenced';
  end if;
  return new;
end;
$$;

create trigger protect_incremental_history_storage152
before update of status on public.storage_objects
for each row execute function public.protect_incremental_history_storage152();

create table public.data_dataset_checkpoints (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  project_id uuid not null,
  source_id uuid not null,
  source_resource_id uuid not null,
  dataset_id uuid not null,
  target_revision bigint not null,
  requested_by_user_id integer not null,
  status text not null default 'pending',
  version_id uuid,
  record_count bigint,
  state_hash text,
  failure_code text,
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  constraint data_dataset_checkpoints_dataset_fk152
    foreign key(dataset_id, tenant_id, project_id, source_id)
    references public.data_datasets(id, tenant_id, project_id, source_id) on delete restrict,
  constraint data_dataset_checkpoints_resource_fk152
    foreign key(source_resource_id, tenant_id, project_id, source_id)
    references public.data_source_resources(id, tenant_id, project_id, source_id) on delete restrict,
  constraint data_dataset_checkpoints_user_fk152
    foreign key(requested_by_user_id, tenant_id)
    references public.users(id, tenant_id) on delete restrict,
  constraint data_dataset_checkpoints_version_fk152
    foreign key(version_id, dataset_id, tenant_id)
    references public.data_dataset_versions(id, dataset_id, tenant_id) on delete restrict,
  constraint data_dataset_checkpoints_revision_check152 check(target_revision > 0),
  constraint data_dataset_checkpoints_status_check152
    check(status in ('pending', 'materializing', 'ready', 'failed')),
  constraint data_dataset_checkpoints_hash_check152
    check(state_hash is null or state_hash ~ '^[0-9a-f]{64}$'),
  constraint data_dataset_checkpoints_failure_check152
    check(failure_code is null or failure_code ~ '^[a-z0-9_]{1,120}$'),
  constraint data_dataset_checkpoints_terminal_check152 check(
    (status in ('pending', 'materializing') and completed_at is null and version_id is null)
    or (status = 'ready' and completed_at is not null and version_id is not null
      and record_count is not null and state_hash is not null and failure_code is null)
    or (status = 'failed' and completed_at is not null and version_id is null
      and failure_code is not null)
  ),
  constraint data_dataset_checkpoints_revision_unique152 unique(dataset_id, target_revision)
);

create index data_dataset_checkpoints_latest152
on public.data_dataset_checkpoints(tenant_id, dataset_id, target_revision desc);

alter table public.data_source_resources
  add constraint data_source_resources_checkpoint_fk152
    foreign key(latest_checkpoint_version_id, dataset_id, tenant_id)
    references public.data_dataset_versions(id, dataset_id, tenant_id) on delete restrict;

create or replace function public.enforce_data_source_ingestion_transition149()
returns trigger language plpgsql set search_path = '' as $$
begin
  if new.id <> old.id or new.tenant_id <> old.tenant_id
     or new.project_id <> old.project_id or new.source_id <> old.source_id
     or new.initiated_by_user_id <> old.initiated_by_user_id
     or new.idempotency_key <> old.idempotency_key
     or new.attempt_number <> old.attempt_number or new.created_at <> old.created_at
     or new.ingestion_kind <> old.ingestion_kind
     or new.source_resource_id is distinct from old.source_resource_id
     or new.expected_cursor is distinct from old.expected_cursor then
    raise exception using errcode = 'P0001', message = 'ingestion_run_identity_immutable';
  end if;
  if new.status <> old.status and not (
    (old.status = 'pending' and new.status in ('processing', 'failed'))
    or (old.status = 'processing' and new.status in ('succeeded', 'failed'))
  ) then
    raise exception using errcode = 'P0001', message = 'ingestion_run_transition_invalid';
  end if;
  if old.status in ('succeeded', 'failed') then
    raise exception using errcode = 'P0001', message = 'ingestion_run_terminal_immutable';
  end if;
  return new;
end;
$$;

create function public.cleanup_failed_incremental_staging152()
returns trigger language plpgsql set search_path = '' as $$
begin
  if old.status = 'processing' and new.status = 'failed'
     and new.ingestion_kind = 'incremental' then
    delete from public.data_ingestion_staged_changes
    where ingestion_run_id = new.id;
  end if;
  return new;
end;
$$;

create trigger cleanup_failed_incremental_staging152
after update of status on public.data_source_ingestion_runs
for each row execute function public.cleanup_failed_incremental_staging152();

create function public.reserve_incremental_source_ingestion152(
  p_tenant_id integer, p_project_id uuid, p_source_id uuid, p_user_id integer,
  p_resource_key text, p_idempotency_key text, p_display_name text,
  p_lease_seconds integer default 7200
)
returns table(
  ingestion_run_id uuid, run_status text, disposition text,
  result_dataset_id uuid, result_version_id uuid, committed_revision bigint,
  failure_code text, lease_token uuid, lease_expires_at timestamptz,
  source_resource_id uuid, expected_cursor text
)
language plpgsql security definer set search_path = '' as $$
declare
  v_source public.data_sources;
  v_resource public.data_source_resources;
  v_dataset_id uuid;
  v_run public.data_source_ingestion_runs;
  v_now timestamptz := now();
begin
  if p_resource_key !~ '^[a-z][a-z0-9_]{1,79}$'
     or length(p_idempotency_key) not between 8 and 128
     or p_idempotency_key !~ '^[A-Za-z0-9._:-]+$' then
    raise exception using errcode = '22023', message = 'incremental_ingestion_input_invalid';
  end if;
  select * into v_source from public.data_sources s
  where s.id = p_source_id and s.tenant_id = p_tenant_id
    and s.project_id = p_project_id and s.creator_user_id = p_user_id
    and s.status = 'active' and s.source_type = 'api_provider'
    and exists(select 1 from public.builder_projects p
      where p.id = s.project_id and p.tenant_id = s.tenant_id
        and p.status <> 'archived' and p.draft_schema->>'workspaceKind' = 'data')
  for update;
  if not found then
    raise exception using errcode = 'P0001', message = 'data_source_not_available';
  end if;

  insert into public.data_source_resources(tenant_id, project_id, source_id, resource_key)
  values(p_tenant_id, p_project_id, p_source_id, p_resource_key)
  on conflict (tenant_id, project_id, source_id, resource_key) do nothing;
  select * into v_resource from public.data_source_resources r
  where r.tenant_id = p_tenant_id and r.project_id = p_project_id
    and r.source_id = p_source_id and r.resource_key = p_resource_key for update;

  if v_resource.dataset_id is null then
    insert into public.data_datasets(
      tenant_id, project_id, creator_user_id, display_name, source_id,
      dataset_mode, source_resource_id
    ) values(
      p_tenant_id, p_project_id, p_user_id, btrim(p_display_name), p_source_id,
      'incremental_records', v_resource.id
    ) returning id into v_dataset_id;
    update public.data_source_resources set dataset_id = v_dataset_id
    where id = v_resource.id returning * into v_resource;
  end if;

  insert into public.data_source_ingestion_runs(
    tenant_id, project_id, source_id, initiated_by_user_id, idempotency_key,
    ingestion_kind, source_resource_id, expected_cursor
  ) values(
    p_tenant_id, p_project_id, p_source_id, p_user_id, p_idempotency_key,
    'incremental', v_resource.id, v_resource.committed_cursor
  ) on conflict (tenant_id, source_id, idempotency_key) do nothing
  returning * into v_run;
  if found then
    update public.data_source_ingestion_runs
    set status = 'processing', attempt_started_at = v_now, heartbeat_at = v_now,
        lease_token = gen_random_uuid(),
        lease_expires_at = v_now + make_interval(secs => greatest(300, least(p_lease_seconds, 14400))),
        lease_owner = 'incremental_ingestion', reconciliation_state = 'active',
        reconciliation_code = null
    where id = v_run.id returning * into v_run;
    return query select v_run.id, v_run.status, 'reserved'::text,
      v_run.result_dataset_id, v_run.result_version_id, v_run.committed_revision,
      v_run.failure_code, v_run.lease_token, v_run.lease_expires_at,
      v_run.source_resource_id, v_run.expected_cursor;
    return;
  end if;
  select * into v_run from public.data_source_ingestion_runs r
  where r.tenant_id = p_tenant_id and r.source_id = p_source_id
    and r.idempotency_key = p_idempotency_key for update;
  if v_run.ingestion_kind <> 'incremental' or v_run.source_resource_id <> v_resource.id then
    raise exception using errcode = 'P0001', message = 'ingestion_idempotency_scope_conflict';
  end if;
  return query select v_run.id, v_run.status,
    case when v_run.status = 'succeeded' then 'succeeded'
      when v_run.status = 'failed' then 'failed' else 'in_progress' end,
    v_run.result_dataset_id, v_run.result_version_id, v_run.committed_revision,
    v_run.failure_code,
    case when v_run.status = 'processing' then null::uuid else v_run.lease_token end,
    v_run.lease_expires_at, v_run.source_resource_id, v_run.expected_cursor;
end;
$$;

create function public.stage_incremental_changes152(
  p_tenant_id integer, p_ingestion_run_id uuid, p_lease_token uuid,
  p_changes jsonb
)
returns integer language plpgsql security definer set search_path = '' as $$
declare v_run public.data_source_ingestion_runs;
declare v_count integer;
begin
  select * into v_run from public.data_source_ingestion_runs r
  where r.id = p_ingestion_run_id and r.tenant_id = p_tenant_id for update;
  if not found or v_run.status <> 'processing' or v_run.ingestion_kind <> 'incremental'
     or v_run.reconciliation_state <> 'active'
     or v_run.lease_token is distinct from p_lease_token then
    raise exception using errcode = 'P0001', message = 'ingestion_lease_lost';
  end if;
  if jsonb_typeof(p_changes) <> 'array' or jsonb_array_length(p_changes) not between 1 and 500 then
    raise exception using errcode = '22023', message = 'incremental_stage_batch_invalid';
  end if;
  insert into public.data_ingestion_staged_changes(
    tenant_id, ingestion_run_id, source_resource_id, row_ordinal,
    source_record_id, operation, source_order, source_event_id, payload,
    content_hash, schema_fingerprint
  )
  select p_tenant_id, v_run.id, v_run.source_resource_id,
    (item->>'ordinal')::integer, item->>'source_record_id', item->>'operation',
    case when item->>'source_order' is null then null else (item->>'source_order')::bigint end,
    nullif(item->>'source_event_id', ''), item->'payload',
    item->>'content_hash', item->>'schema_fingerprint'
  from jsonb_array_elements(p_changes) item;
  select count(*) into v_count from public.data_ingestion_staged_changes
  where ingestion_run_id = v_run.id;
  if v_count > 10000 then
    raise exception using errcode = '22023', message = 'incremental_stage_limit_exceeded';
  end if;
  update public.data_source_ingestion_runs set heartbeat_at = now()
  where id = v_run.id;
  return v_count;
end;
$$;

create function public.complete_incremental_ingestion152(
  p_tenant_id integer, p_project_id uuid, p_source_id uuid, p_user_id integer,
  p_ingestion_run_id uuid, p_lease_token uuid, p_storage_object_id uuid,
  p_change_count integer, p_manifest_hash text, p_next_cursor text,
  p_schema_fingerprint text
)
returns table(
  dataset_id uuid, source_resource_id uuid, committed_revision bigint,
  ingestion_run_id uuid, ingestion_status text, inserted_count integer,
  updated_count integer, deleted_count integer, duplicate_count integer,
  stale_count integer, latest_checkpoint_version_id uuid
)
language plpgsql security definer set search_path = '' as $$
declare
  v_run public.data_source_ingestion_runs;
  v_resource public.data_source_resources;
  v_dataset public.data_datasets;
  v_storage public.storage_objects;
  v_change public.data_ingestion_staged_changes;
  v_current public.data_dataset_current_records;
  v_revision bigint;
  v_outcome text;
  v_inserted integer := 0; v_updated integer := 0; v_deleted integer := 0;
  v_duplicate integer := 0; v_stale integer := 0;
  v_count integer; v_min integer; v_max integer;
begin
  select * into v_run from public.data_source_ingestion_runs r
  where r.id = p_ingestion_run_id and r.tenant_id = p_tenant_id
    and r.project_id = p_project_id and r.source_id = p_source_id
    and r.initiated_by_user_id = p_user_id for update;
  if not found or v_run.status <> 'processing' or v_run.ingestion_kind <> 'incremental'
     or v_run.reconciliation_state <> 'active'
     or v_run.lease_token is distinct from p_lease_token then
    raise exception using errcode = 'P0001', message = 'ingestion_lease_lost';
  end if;
  if v_run.storage_object_id is distinct from p_storage_object_id then
    raise exception using errcode = 'P0001', message = 'ingestion_storage_object_not_attached';
  end if;
  select * into v_storage from public.storage_objects o
  where o.id = p_storage_object_id for update;
  if not found or v_storage.tenant_id <> p_tenant_id
     or v_storage.user_id is distinct from p_user_id
     or v_storage.category <> 'dataset' or v_storage.status <> 'active'
     or v_storage.sha256 is distinct from p_manifest_hash then
    raise exception using errcode = 'P0001', message = 'incremental_storage_object_invalid';
  end if;
  select * into v_resource from public.data_source_resources r
  where r.id = v_run.source_resource_id and r.tenant_id = p_tenant_id
    and r.project_id = p_project_id and r.source_id = p_source_id for update;
  if not found or v_resource.committed_cursor is distinct from v_run.expected_cursor then
    raise exception using errcode = 'P0001', message = 'incremental_cursor_conflict';
  end if;
  select * into v_dataset from public.data_datasets d
  where d.id = v_resource.dataset_id and d.tenant_id = p_tenant_id
    and d.project_id = p_project_id and d.source_id = p_source_id
    and d.source_resource_id = v_resource.id and d.dataset_mode = 'incremental_records'
    and d.status = 'active' for update;
  if not found or v_dataset.committed_revision <> v_resource.committed_revision then
    raise exception using errcode = 'P0001', message = 'incremental_dataset_lineage_invalid';
  end if;
  select count(*), min(s.row_ordinal), max(s.row_ordinal)
  into v_count, v_min, v_max from public.data_ingestion_staged_changes s
  where s.tenant_id = p_tenant_id and s.ingestion_run_id = v_run.id;
  if v_count <> p_change_count or v_count not between 1 and 10000
     or v_min <> 1 or v_max <> v_count
     or p_schema_fingerprint !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = 'P0001', message = 'incremental_stage_manifest_invalid';
  end if;
  if exists(select 1 from public.data_ingestion_staged_changes s
    where s.ingestion_run_id = v_run.id and s.schema_fingerprint <> p_schema_fingerprint) then
    raise exception using errcode = 'P0001', message = 'incremental_schema_mismatch';
  end if;
  if v_resource.schema_fingerprint is not null
     and v_resource.schema_fingerprint <> p_schema_fingerprint then
    raise exception using errcode = 'P0001', message = 'incremental_schema_evolution_required';
  end if;
  v_revision := v_resource.committed_revision + 1;

  for v_change in select * from public.data_ingestion_staged_changes s
    where s.ingestion_run_id = v_run.id order by s.row_ordinal
  loop
    select * into v_current from public.data_dataset_current_records c
    where c.tenant_id = p_tenant_id and c.dataset_id = v_dataset.id
      and c.source_record_id = v_change.source_record_id for update;
    if not found then
      if v_change.operation = 'delete' then
        v_outcome := 'duplicate'; v_duplicate := v_duplicate + 1;
      else
        insert into public.data_dataset_current_records(
          tenant_id, dataset_id, source_record_id, payload, content_hash,
          source_order, is_deleted, schema_fingerprint, last_committed_revision,
          last_ingestion_run_id
        ) values(
          p_tenant_id, v_dataset.id, v_change.source_record_id, v_change.payload,
          v_change.content_hash, v_change.source_order, false,
          v_change.schema_fingerprint, v_revision, v_run.id
        );
        v_outcome := 'inserted'; v_inserted := v_inserted + 1;
      end if;
    elsif v_change.source_order is null or v_current.source_order is null then
      if v_change.content_hash = v_current.content_hash
         and (v_change.operation = 'delete') = v_current.is_deleted then
        v_outcome := 'duplicate'; v_duplicate := v_duplicate + 1;
      else
        raise exception using errcode = 'P0001', message = 'incremental_ordering_required';
      end if;
    elsif v_change.source_order < v_current.source_order then
      v_outcome := 'stale_ignored'; v_stale := v_stale + 1;
    elsif v_change.source_order = v_current.source_order then
      if v_change.content_hash = v_current.content_hash
         and (v_change.operation = 'delete') = v_current.is_deleted then
        v_outcome := 'duplicate'; v_duplicate := v_duplicate + 1;
      else
        raise exception using errcode = 'P0001', message = 'incremental_equal_revision_conflict';
      end if;
    elsif v_change.operation = 'delete' then
      update public.data_dataset_current_records c set
        payload = null, content_hash = v_change.content_hash,
        source_order = v_change.source_order, is_deleted = true,
        schema_fingerprint = v_change.schema_fingerprint,
        last_committed_revision = v_revision, last_ingestion_run_id = v_run.id,
        updated_at = now()
      where c.tenant_id = p_tenant_id and c.dataset_id = v_dataset.id
        and c.source_record_id = v_change.source_record_id;
      v_outcome := 'deleted'; v_deleted := v_deleted + 1;
    else
      update public.data_dataset_current_records c set
        payload = v_change.payload, content_hash = v_change.content_hash,
        source_order = v_change.source_order, is_deleted = false,
        schema_fingerprint = v_change.schema_fingerprint,
        last_committed_revision = v_revision, last_ingestion_run_id = v_run.id,
        updated_at = now()
      where c.tenant_id = p_tenant_id and c.dataset_id = v_dataset.id
        and c.source_record_id = v_change.source_record_id;
      v_outcome := case when v_current.is_deleted then 'inserted' else 'updated' end;
      if v_outcome = 'inserted' then v_inserted := v_inserted + 1;
      else v_updated := v_updated + 1; end if;
    end if;
    insert into public.data_dataset_record_changes(
      tenant_id, project_id, source_id, source_resource_id, dataset_id,
      committed_revision, ingestion_run_id, storage_object_id, row_ordinal,
      source_record_id, operation, outcome, source_order, source_event_id,
      content_hash, schema_fingerprint
    ) values(
      p_tenant_id, p_project_id, p_source_id, v_resource.id, v_dataset.id,
      v_revision, v_run.id, p_storage_object_id, v_change.row_ordinal,
      v_change.source_record_id, v_change.operation, v_outcome,
      v_change.source_order, v_change.source_event_id,
      v_change.content_hash, v_change.schema_fingerprint
    );
  end loop;

  update public.data_datasets set committed_revision = v_revision
  where id = v_dataset.id;
  update public.data_source_resources set
    committed_revision = v_revision, committed_cursor = nullif(p_next_cursor, ''),
    schema_fingerprint = coalesce(schema_fingerprint, p_schema_fingerprint)
  where id = v_resource.id;
  update public.data_source_ingestion_runs set
    status = 'succeeded', completed_at = now(), result_dataset_id = v_dataset.id,
    result_version_id = null, committed_revision = v_revision,
    next_cursor = nullif(p_next_cursor, ''), manifest_hash = p_manifest_hash,
    staged_change_count = p_change_count,
    run_metadata = jsonb_build_object(
      'inserted', v_inserted, 'updated', v_updated, 'deleted', v_deleted,
      'duplicates', v_duplicate, 'stale_ignored', v_stale,
      'resource_key', v_resource.resource_key
    ), lease_owner = null, lease_expires_at = null,
    reconciliation_state = 'resolved', reconciliation_code = 'incremental_committed',
    last_reconciled_at = now()
  where id = v_run.id;
  update public.data_sources set sync_state = 'idle', last_ingested_at = now(),
    last_successful_sync_at = now(), last_error_code = null
  where id = p_source_id;
  delete from public.data_ingestion_staged_changes s where s.ingestion_run_id = v_run.id;
  return query select v_dataset.id, v_resource.id, v_revision, v_run.id,
    'succeeded'::text, v_inserted, v_updated, v_deleted, v_duplicate, v_stale,
    v_resource.latest_checkpoint_version_id;
end;
$$;

create function public.request_dataset_checkpoint152(
  p_tenant_id integer, p_project_id uuid, p_source_id uuid, p_resource_id uuid,
  p_dataset_id uuid, p_user_id integer, p_target_revision bigint
)
returns public.data_dataset_checkpoints
language plpgsql security definer set search_path = '' as $$
declare v_resource public.data_source_resources;
declare v_checkpoint public.data_dataset_checkpoints;
begin
  select * into v_resource from public.data_source_resources r
  where r.id = p_resource_id and r.tenant_id = p_tenant_id
    and r.project_id = p_project_id and r.source_id = p_source_id
    and r.dataset_id = p_dataset_id
    and exists(select 1 from public.data_sources s
      where s.id = r.source_id and s.tenant_id = r.tenant_id
        and s.project_id = r.project_id and s.creator_user_id = p_user_id
        and s.status = 'active') for update;
  if not found or p_target_revision < 1 or p_target_revision > v_resource.committed_revision then
    raise exception using errcode = 'P0001', message = 'checkpoint_target_invalid';
  end if;
  insert into public.data_dataset_checkpoints(
    tenant_id, project_id, source_id, source_resource_id, dataset_id,
    target_revision, requested_by_user_id, status
  ) values(
    p_tenant_id, p_project_id, p_source_id, p_resource_id, p_dataset_id,
    p_target_revision, p_user_id, 'materializing'
  ) on conflict(dataset_id, target_revision) do update
    set status = case when public.data_dataset_checkpoints.status = 'failed'
      then 'materializing' else public.data_dataset_checkpoints.status end,
        completed_at = case when public.data_dataset_checkpoints.status = 'failed'
          then null else public.data_dataset_checkpoints.completed_at end,
        failure_code = case when public.data_dataset_checkpoints.status = 'failed'
          then null else public.data_dataset_checkpoints.failure_code end
  returning * into v_checkpoint;
  return v_checkpoint;
end;
$$;

create function public.publish_dataset_checkpoint152(
  p_checkpoint_id uuid, p_storage_object_id uuid, p_original_filename text,
  p_size_bytes bigint, p_content_hash text, p_record_count bigint,
  p_state_hash text
)
returns table(dataset_id uuid, version_id uuid, version_number integer, target_revision bigint)
language plpgsql security definer set search_path = '' as $$
declare
  v_checkpoint public.data_dataset_checkpoints;
  v_resource public.data_source_resources;
  v_source public.data_sources;
  v_storage public.storage_objects;
  v_version_id uuid; v_version_number integer;
begin
  select * into v_checkpoint from public.data_dataset_checkpoints c
  where c.id = p_checkpoint_id for update;
  if not found or v_checkpoint.status <> 'materializing' then
    raise exception using errcode = 'P0001', message = 'checkpoint_not_materializing';
  end if;
  select * into v_resource from public.data_source_resources r
  where r.id = v_checkpoint.source_resource_id for update;
  if not found or v_resource.dataset_id <> v_checkpoint.dataset_id
     or v_resource.committed_revision < v_checkpoint.target_revision then
    raise exception using errcode = 'P0001', message = 'checkpoint_lineage_invalid';
  end if;
  select * into v_source from public.data_sources s
  where s.id = v_checkpoint.source_id for update;
  select * into v_storage from public.storage_objects o
  where o.id = p_storage_object_id for update;
  if not found or v_storage.tenant_id <> v_checkpoint.tenant_id
     or v_storage.user_id is distinct from v_checkpoint.requested_by_user_id
     or v_storage.category <> 'dataset' or v_storage.status <> 'active'
     or v_storage.size_bytes <> p_size_bytes or v_storage.sha256 is distinct from p_content_hash
     or p_state_hash !~ '^[0-9a-f]{64}$' or p_record_count < 0 then
    raise exception using errcode = 'P0001', message = 'checkpoint_storage_invalid';
  end if;
  select coalesce(max(v.version_number), 0) + 1 into v_version_number
  from public.data_dataset_versions v where v.dataset_id = v_checkpoint.dataset_id;
  insert into public.data_dataset_versions(
    tenant_id, dataset_id, version_number, storage_object_id, created_by_user_id,
    version_kind, original_filename, content_type, file_extension, size_bytes,
    content_hash, file_metadata, provenance
  ) values(
    v_checkpoint.tenant_id, v_checkpoint.dataset_id, v_version_number,
    p_storage_object_id, v_checkpoint.requested_by_user_id, 'checkpoint',
    btrim(p_original_filename), 'text/csv', '.csv', p_size_bytes, p_content_hash,
    jsonb_build_object('rows', p_record_count, 'format', 'csv',
      'dataset_revision', v_checkpoint.target_revision, 'state_hash', p_state_hash),
    jsonb_build_object('kind', 'incremental_checkpoint',
      'source_id', v_checkpoint.source_id,
      'source_resource_id', v_checkpoint.source_resource_id,
      'dataset_revision', v_checkpoint.target_revision)
  ) returning id into v_version_id;
  update public.data_dataset_checkpoints set status = 'ready', version_id = v_version_id,
    record_count = p_record_count, state_hash = p_state_hash, completed_at = now()
  where id = v_checkpoint.id;
  update public.data_source_resources set latest_checkpoint_version_id = v_version_id
  where id = v_resource.id;
  if v_resource.resource_key = v_source.resource_type then
    update public.data_sources set latest_dataset_id = v_checkpoint.dataset_id,
      latest_version_id = v_version_id where id = v_source.id;
  end if;
  return query select v_checkpoint.dataset_id, v_version_id, v_version_number,
    v_checkpoint.target_revision;
end;
$$;

create function public.fail_dataset_checkpoint152(
  p_checkpoint_id uuid, p_user_id integer, p_failure_code text
)
returns boolean language plpgsql security definer set search_path = '' as $$
declare v_checkpoint public.data_dataset_checkpoints;
begin
  select * into v_checkpoint from public.data_dataset_checkpoints c
  where c.id = p_checkpoint_id and c.requested_by_user_id = p_user_id for update;
  if not found then
    raise exception using errcode = 'P0001', message = 'checkpoint_not_found';
  end if;
  if v_checkpoint.status = 'ready' then return false; end if;
  if v_checkpoint.status <> 'materializing'
     or p_failure_code !~ '^[a-z0-9_]{1,120}$' then
    raise exception using errcode = 'P0001', message = 'checkpoint_failure_invalid';
  end if;
  update public.data_dataset_checkpoints set status = 'failed',
    failure_code = p_failure_code, completed_at = now()
  where id = v_checkpoint.id;
  return true;
end;
$$;

alter table public.data_source_resources enable row level security;
alter table public.data_ingestion_staged_changes enable row level security;
alter table public.data_dataset_current_records enable row level security;
alter table public.data_dataset_record_changes enable row level security;
alter table public.data_dataset_checkpoints enable row level security;

revoke all on public.data_source_resources, public.data_ingestion_staged_changes,
  public.data_dataset_current_records, public.data_dataset_record_changes,
  public.data_dataset_checkpoints from public, anon, authenticated;
grant select, insert, update, delete on public.data_source_resources,
  public.data_ingestion_staged_changes, public.data_dataset_current_records,
  public.data_dataset_record_changes, public.data_dataset_checkpoints to service_role;
grant usage, select on sequence public.data_ingestion_staged_changes_id_seq,
  public.data_dataset_record_changes_id_seq to service_role;

revoke all on function public.reserve_incremental_source_ingestion152(integer,uuid,uuid,integer,text,text,text,integer),
  public.stage_incremental_changes152(integer,uuid,uuid,jsonb),
  public.complete_incremental_ingestion152(integer,uuid,uuid,integer,uuid,uuid,uuid,integer,text,text,text),
  public.request_dataset_checkpoint152(integer,uuid,uuid,uuid,uuid,integer,bigint),
  public.publish_dataset_checkpoint152(uuid,uuid,text,bigint,text,bigint,text),
  public.fail_dataset_checkpoint152(uuid,integer,text)
from public, anon, authenticated;
grant execute on function public.reserve_incremental_source_ingestion152(integer,uuid,uuid,integer,text,text,text,integer),
  public.stage_incremental_changes152(integer,uuid,uuid,jsonb),
  public.complete_incremental_ingestion152(integer,uuid,uuid,integer,uuid,uuid,uuid,integer,text,text,text),
  public.request_dataset_checkpoint152(integer,uuid,uuid,uuid,uuid,integer,bigint),
  public.publish_dataset_checkpoint152(uuid,uuid,text,bigint,text,bigint,text),
  public.fail_dataset_checkpoint152(uuid,integer,text)
to service_role;

update public.application_schema_state set schema_version = 152, applied_at = now()
where contract_key = 'core';
notify pgrst, 'reload schema';
commit;
