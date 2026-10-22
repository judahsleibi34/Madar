begin;

do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version into v_schema_version
  from public.application_schema_state where contract_key = 'core' for update;
  if v_schema_version is null then
    raise exception using errcode = 'P0001', message = 'migration_151_schema_state_missing';
  end if;
  if v_schema_version <> 150 then
    raise exception using errcode = 'P0001',
      message = format('migration_151_expected_schema_150_got_%s', v_schema_version);
  end if;
end;
$$;

alter table public.data_sources
  drop constraint data_sources_type_check148,
  add column provider_key text,
  add column resource_type text,
  add constraint data_sources_type_check151
    check(source_type in ('spreadsheet_upload', 'api_provider')),
  add constraint data_sources_provider_shape_check151 check(
    (source_type = 'spreadsheet_upload' and provider_key is null and resource_type is null)
    or
    (source_type = 'api_provider'
      and provider_key ~ '^[a-z][a-z0-9_]{1,79}$'
      and resource_type ~ '^[a-z][a-z0-9_]{1,79}$')
  );

create function public.reserve_source_ingestion151(
  p_tenant_id integer,
  p_project_id uuid,
  p_source_id uuid,
  p_user_id integer,
  p_idempotency_key text,
  p_lease_seconds integer default 7200
)
returns table(
  ingestion_run_id uuid,
  run_status text,
  disposition text,
  result_dataset_id uuid,
  result_version_id uuid,
  failure_code text,
  lease_token uuid,
  lease_expires_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_run public.data_source_ingestion_runs;
  v_now timestamptz := now();
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
      and s.source_type in ('spreadsheet_upload', 'api_provider')
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
    set status = 'processing', attempt_started_at = v_now, heartbeat_at = v_now,
        lease_token = gen_random_uuid(),
        lease_expires_at = v_now + make_interval(secs => greatest(300, least(p_lease_seconds, 14400))),
        lease_owner = 'source_ingestion', reconciliation_state = 'active',
        reconciliation_code = null
    where id = v_run.id
    returning * into v_run;
    return query select v_run.id, v_run.status, 'reserved'::text,
      v_run.result_dataset_id, v_run.result_version_id, v_run.failure_code,
      v_run.lease_token, v_run.lease_expires_at;
    return;
  end if;

  select * into v_run from public.data_source_ingestion_runs r
  where r.tenant_id = p_tenant_id and r.source_id = p_source_id
    and r.idempotency_key = p_idempotency_key for update;
  return query select v_run.id, v_run.status,
    case when v_run.status = 'succeeded' then 'succeeded'
         when v_run.status = 'failed' then 'failed' else 'in_progress' end,
    v_run.result_dataset_id, v_run.result_version_id, v_run.failure_code,
    case when v_run.status = 'processing' then null::uuid else v_run.lease_token end,
    v_run.lease_expires_at;
end;
$$;

create function public.complete_source_ingestion151(
  p_tenant_id integer,
  p_project_id uuid,
  p_source_id uuid,
  p_user_id integer,
  p_ingestion_run_id uuid,
  p_lease_token uuid,
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
  select * into v_run from public.data_source_ingestion_runs r
  where r.id = p_ingestion_run_id and r.tenant_id = p_tenant_id
    and r.project_id = p_project_id and r.source_id = p_source_id
    and r.initiated_by_user_id = p_user_id for update;
  if not found or v_run.status <> 'processing' or v_run.reconciliation_state <> 'active'
     or v_run.lease_token is distinct from p_lease_token then
    raise exception using errcode = 'P0001', message = 'ingestion_lease_lost';
  end if;
  if v_run.storage_object_id is distinct from p_storage_object_id then
    raise exception using errcode = 'P0001', message = 'ingestion_storage_object_not_attached';
  end if;

  select * into v_source from public.data_sources s
  where s.id = p_source_id and s.tenant_id = p_tenant_id
    and s.project_id = p_project_id and s.creator_user_id = p_user_id
    and exists(select 1 from public.builder_projects p
      where p.id = s.project_id and p.tenant_id = s.tenant_id
        and p.status <> 'archived' and p.draft_schema->>'workspaceKind' = 'data')
  for update;
  if not found or v_source.status <> 'active'
     or v_source.source_type not in ('spreadsheet_upload', 'api_provider') then
    raise exception using errcode = 'P0001', message = 'data_source_not_available';
  end if;

  select * into v_storage from public.storage_objects o
  where o.id = p_storage_object_id for update;
  if not found or v_storage.tenant_id <> p_tenant_id
     or v_storage.user_id is distinct from p_user_id or v_storage.category <> 'dataset'
     or v_storage.status <> 'active' or v_storage.size_bytes <> p_size_bytes
     or v_storage.sha256 is distinct from p_content_hash then
    raise exception using errcode = 'P0001', message = 'dataset_storage_object_invalid';
  end if;

  insert into public.data_datasets(tenant_id, project_id, creator_user_id, display_name, source_id)
  values(p_tenant_id, p_project_id, p_user_id, btrim(p_display_name), p_source_id)
  returning id into v_dataset_id;
  insert into public.data_dataset_versions(
    tenant_id, dataset_id, version_number, storage_object_id, created_by_user_id,
    version_kind, original_filename, content_type, file_extension, size_bytes,
    content_hash, file_metadata, provenance
  ) values(
    p_tenant_id, v_dataset_id, 1, p_storage_object_id, p_user_id,
    'original', btrim(p_original_filename), btrim(p_content_type),
    lower(btrim(p_file_extension)), p_size_bytes, p_content_hash,
    coalesce(p_file_metadata, '{}'::jsonb),
    jsonb_strip_nulls(jsonb_build_object(
      'kind', case when v_source.source_type = 'api_provider' then 'source_api_snapshot' else 'source_upload' end,
      'source_id', p_source_id, 'ingestion_run_id', p_ingestion_run_id,
      'provider_key', v_source.provider_key, 'resource_type', v_source.resource_type
    ))
  ) returning id into v_version_id;
  update public.data_sources
  set latest_dataset_id = v_dataset_id, latest_version_id = v_version_id,
      sync_state = 'idle', last_ingested_at = now(),
      last_successful_sync_at = now(), last_error_code = null
  where id = p_source_id;
  update public.data_source_ingestion_runs
  set status = 'succeeded', completed_at = now(), result_dataset_id = v_dataset_id,
      result_version_id = v_version_id, run_metadata = coalesce(p_run_metadata, '{}'::jsonb),
      lease_owner = null, lease_expires_at = null, reconciliation_state = 'resolved',
      reconciliation_code = 'committed', last_reconciled_at = now()
  where id = p_ingestion_run_id;
  return query select v_dataset_id, v_version_id, 1, p_ingestion_run_id, 'succeeded'::text;
end;
$$;

revoke all on function public.reserve_source_ingestion151(integer,uuid,uuid,integer,text,integer)
from public,anon,authenticated;
revoke all on function public.complete_source_ingestion151(integer,uuid,uuid,integer,uuid,uuid,text,uuid,text,text,text,bigint,text,jsonb,jsonb)
from public,anon,authenticated;
grant execute on function public.reserve_source_ingestion151(integer,uuid,uuid,integer,text,integer) to service_role;
grant execute on function public.complete_source_ingestion151(integer,uuid,uuid,integer,uuid,uuid,text,uuid,text,text,text,bigint,text,jsonb,jsonb) to service_role;

update public.application_schema_state set schema_version = 151, applied_at = now()
where contract_key = 'core';
notify pgrst, 'reload schema';
commit;
