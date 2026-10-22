begin;

do $$
declare
  v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version
  into v_schema_version
  from public.application_schema_state
  where contract_key = 'core'
  for update;

  if v_schema_version is null then
    raise exception using errcode = 'P0001', message = 'migration_149_schema_state_missing';
  end if;
  if v_schema_version <> 148 then
    raise exception using errcode = 'P0001',
      message = format('migration_149_expected_schema_148_got_%s', v_schema_version);
  end if;
end;
$$;

alter table public.data_datasets
  add constraint data_datasets_id_tenant_project_source_unique149
    unique(id, tenant_id, project_id, source_id);

create table public.data_source_ingestion_runs (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  project_id uuid not null,
  source_id uuid not null,
  initiated_by_user_id integer not null,
  idempotency_key text not null,
  status text not null default 'pending',
  attempt_number integer not null default 1,
  attempt_started_at timestamptz,
  completed_at timestamptz,
  result_dataset_id uuid,
  result_version_id uuid,
  failure_code text,
  run_metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint data_source_ingestion_runs_source_fk149
    foreign key(source_id, tenant_id, project_id)
    references public.data_sources(id, tenant_id, project_id)
    on delete restrict,
  constraint data_source_ingestion_runs_user_fk149
    foreign key(initiated_by_user_id, tenant_id)
    references public.users(id, tenant_id)
    on delete restrict,
  constraint data_source_ingestion_runs_dataset_fk149
    foreign key(result_dataset_id, tenant_id, project_id, source_id)
    references public.data_datasets(id, tenant_id, project_id, source_id)
    on delete restrict,
  constraint data_source_ingestion_runs_version_fk149
    foreign key(result_version_id, result_dataset_id, tenant_id)
    references public.data_dataset_versions(id, dataset_id, tenant_id)
    on delete restrict,
  constraint data_source_ingestion_runs_idempotency_unique149
    unique(tenant_id, source_id, idempotency_key),
  constraint data_source_ingestion_runs_status_check149
    check(status in ('pending', 'processing', 'succeeded', 'failed')),
  constraint data_source_ingestion_runs_attempt_check149
    check(attempt_number > 0),
  constraint data_source_ingestion_runs_idempotency_check149
    check(length(idempotency_key) between 8 and 128 and idempotency_key ~ '^[A-Za-z0-9._:-]+$'),
  constraint data_source_ingestion_runs_failure_code_check149
    check(failure_code is null or (length(failure_code) between 1 and 120 and failure_code ~ '^[a-z0-9_]+$')),
  constraint data_source_ingestion_runs_metadata_check149
    check(jsonb_typeof(run_metadata) = 'object' and octet_length(run_metadata::text) <= 4096),
  constraint data_source_ingestion_runs_result_pair_check149
    check((result_dataset_id is null) = (result_version_id is null)),
  constraint data_source_ingestion_runs_terminal_check149
    check(
      (status in ('pending', 'processing') and completed_at is null and result_dataset_id is null and failure_code is null)
      or (status = 'succeeded' and completed_at is not null and result_dataset_id is not null and failure_code is null)
      or (status = 'failed' and completed_at is not null and result_dataset_id is null and failure_code is not null)
    )
);

create trigger set_data_source_ingestion_runs_updated_at149
before update on public.data_source_ingestion_runs
for each row execute function public.set_updated_at();

create index data_source_ingestion_runs_source_history149
on public.data_source_ingestion_runs(tenant_id, project_id, source_id, created_at desc);

create function public.enforce_data_source_ingestion_transition149()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.id <> old.id
     or new.tenant_id <> old.tenant_id
     or new.project_id <> old.project_id
     or new.source_id <> old.source_id
     or new.initiated_by_user_id <> old.initiated_by_user_id
     or new.idempotency_key <> old.idempotency_key
     or new.attempt_number <> old.attempt_number
     or new.created_at <> old.created_at then
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

create trigger enforce_data_source_ingestion_transition149
before update on public.data_source_ingestion_runs
for each row execute function public.enforce_data_source_ingestion_transition149();

create function public.reserve_source_ingestion149(
  p_tenant_id integer,
  p_project_id uuid,
  p_source_id uuid,
  p_user_id integer,
  p_idempotency_key text
)
returns table(
  ingestion_run_id uuid,
  run_status text,
  disposition text,
  result_dataset_id uuid,
  result_version_id uuid,
  failure_code text
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_run public.data_source_ingestion_runs;
begin
  if not exists(
    select 1
    from public.data_sources s
    join public.builder_projects p
      on p.id = s.project_id and p.tenant_id = s.tenant_id
    where s.id = p_source_id
      and s.tenant_id = p_tenant_id
      and s.project_id = p_project_id
      and s.creator_user_id = p_user_id
      and s.status = 'active'
      and s.source_type = 'spreadsheet_upload'
      and p.status <> 'archived'
      and p.draft_schema->>'workspaceKind' = 'data'
  ) then
    raise exception using errcode = 'P0001', message = 'data_source_not_available';
  end if;

  insert into public.data_source_ingestion_runs(
    tenant_id, project_id, source_id, initiated_by_user_id, idempotency_key
  ) values (
    p_tenant_id, p_project_id, p_source_id, p_user_id, p_idempotency_key
  )
  on conflict (tenant_id, source_id, idempotency_key) do nothing
  returning * into v_run;

  if found then
    update public.data_source_ingestion_runs
    set status = 'processing', attempt_started_at = now()
    where id = v_run.id
    returning * into v_run;
    return query select v_run.id, v_run.status, 'reserved'::text,
      v_run.result_dataset_id, v_run.result_version_id, v_run.failure_code;
    return;
  end if;

  select * into v_run
  from public.data_source_ingestion_runs r
  where r.tenant_id = p_tenant_id
    and r.source_id = p_source_id
    and r.idempotency_key = p_idempotency_key
  for update;

  return query select v_run.id, v_run.status,
    case
      when v_run.status = 'succeeded' then 'succeeded'
      when v_run.status = 'failed' then 'failed'
      else 'in_progress'
    end,
    v_run.result_dataset_id, v_run.result_version_id, v_run.failure_code;
end;
$$;

create function public.complete_source_ingestion149(
  p_tenant_id integer,
  p_project_id uuid,
  p_source_id uuid,
  p_user_id integer,
  p_ingestion_run_id uuid,
  p_display_name text,
  p_storage_object_id uuid,
  p_original_filename text,
  p_content_type text,
  p_file_extension text,
  p_size_bytes bigint,
  p_content_hash text,
  p_file_metadata jsonb default '{}'::jsonb,
  p_run_metadata jsonb default '{}'::jsonb
)
returns table(dataset_id uuid, version_id uuid, version_number integer, ingestion_run_id uuid, ingestion_status text)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_run public.data_source_ingestion_runs;
  v_source public.data_sources;
  v_storage public.storage_objects;
  v_dataset_id uuid;
  v_version_id uuid;
begin
  select * into v_run
  from public.data_source_ingestion_runs r
  where r.id = p_ingestion_run_id
    and r.tenant_id = p_tenant_id
    and r.project_id = p_project_id
    and r.source_id = p_source_id
    and r.initiated_by_user_id = p_user_id
  for update;

  if not found or v_run.status <> 'processing' then
    raise exception using errcode = 'P0001', message = 'ingestion_run_not_processing';
  end if;

  select * into v_source
  from public.data_sources s
  where s.id = p_source_id
    and s.tenant_id = p_tenant_id
    and s.project_id = p_project_id
    and s.creator_user_id = p_user_id
    and exists(
      select 1 from public.builder_projects p
      where p.id = s.project_id
        and p.tenant_id = s.tenant_id
        and p.status <> 'archived'
        and p.draft_schema->>'workspaceKind' = 'data'
    )
  for update;

  if not found or v_source.status <> 'active' or v_source.source_type <> 'spreadsheet_upload' then
    raise exception using errcode = 'P0001', message = 'data_source_not_available';
  end if;

  select * into v_storage
  from public.storage_objects o
  where o.id = p_storage_object_id
  for update;

  if not found
     or v_storage.tenant_id <> p_tenant_id
     or v_storage.user_id is distinct from p_user_id
     or v_storage.category <> 'dataset'
     or v_storage.status <> 'active'
     or v_storage.size_bytes <> p_size_bytes
     or v_storage.sha256 is distinct from p_content_hash then
    raise exception using errcode = 'P0001', message = 'dataset_storage_object_invalid';
  end if;

  insert into public.data_datasets(
    tenant_id, project_id, creator_user_id, display_name, source_id
  ) values (
    p_tenant_id, p_project_id, p_user_id, btrim(p_display_name), p_source_id
  ) returning id into v_dataset_id;

  insert into public.data_dataset_versions(
    tenant_id, dataset_id, version_number, storage_object_id, created_by_user_id,
    version_kind, original_filename, content_type, file_extension, size_bytes,
    content_hash, file_metadata, provenance
  ) values (
    p_tenant_id, v_dataset_id, 1, p_storage_object_id, p_user_id,
    'original', btrim(p_original_filename), btrim(p_content_type),
    lower(btrim(p_file_extension)), p_size_bytes, p_content_hash,
    coalesce(p_file_metadata, '{}'::jsonb),
    jsonb_build_object('kind', 'source_upload', 'source_id', p_source_id, 'ingestion_run_id', p_ingestion_run_id)
  ) returning id into v_version_id;

  update public.data_sources
  set latest_dataset_id = v_dataset_id,
      latest_version_id = v_version_id,
      last_ingested_at = now(),
      last_successful_sync_at = now(),
      last_error_code = null,
      sync_state = 'idle'
  where id = p_source_id;

  update public.data_source_ingestion_runs
  set status = 'succeeded',
      completed_at = now(),
      result_dataset_id = v_dataset_id,
      result_version_id = v_version_id,
      run_metadata = coalesce(p_run_metadata, '{}'::jsonb)
  where id = p_ingestion_run_id;

  return query select v_dataset_id, v_version_id, 1, p_ingestion_run_id, 'succeeded'::text;
end;
$$;

create function public.fail_source_ingestion149(
  p_tenant_id integer,
  p_project_id uuid,
  p_source_id uuid,
  p_user_id integer,
  p_ingestion_run_id uuid,
  p_failure_code text
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  update public.data_source_ingestion_runs
  set status = 'failed', completed_at = now(), failure_code = p_failure_code
  where id = p_ingestion_run_id
    and tenant_id = p_tenant_id
    and project_id = p_project_id
    and source_id = p_source_id
    and initiated_by_user_id = p_user_id
    and status = 'processing';

  if not found then
    raise exception using errcode = 'P0001', message = 'ingestion_run_not_processing';
  end if;

  update public.data_sources
  set sync_state = 'error', last_error_code = p_failure_code
  where id = p_source_id
    and tenant_id = p_tenant_id
    and project_id = p_project_id
    and creator_user_id = p_user_id
    and status = 'active';
end;
$$;

alter table public.data_source_ingestion_runs enable row level security;

revoke all on public.data_source_ingestion_runs from public, anon, authenticated;
grant select, insert, update, delete on public.data_source_ingestion_runs to service_role;

revoke all on function public.reserve_source_ingestion149(integer, uuid, uuid, integer, text)
from public, anon, authenticated;
grant execute on function public.reserve_source_ingestion149(integer, uuid, uuid, integer, text)
to service_role;

revoke all on function public.complete_source_ingestion149(
  integer, uuid, uuid, integer, uuid, text, uuid, text, text, text, bigint, text, jsonb, jsonb
) from public, anon, authenticated;
grant execute on function public.complete_source_ingestion149(
  integer, uuid, uuid, integer, uuid, text, uuid, text, text, text, bigint, text, jsonb, jsonb
) to service_role;

revoke all on function public.fail_source_ingestion149(integer, uuid, uuid, integer, uuid, text)
from public, anon, authenticated;
grant execute on function public.fail_source_ingestion149(integer, uuid, uuid, integer, uuid, text)
to service_role;

update public.application_schema_state
set schema_version = 149, applied_at = now()
where contract_key = 'core';

notify pgrst, 'reload schema';
commit;
