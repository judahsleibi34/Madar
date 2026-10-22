begin;

do $$
declare
  v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version into v_schema_version
  from public.application_schema_state
  where contract_key = 'core'
  for update;
  if v_schema_version is null then
    raise exception using errcode = 'P0001', message = 'migration_150_schema_state_missing';
  end if;
  if v_schema_version <> 149 then
    raise exception using errcode = 'P0001',
      message = format('migration_150_expected_schema_149_got_%s', v_schema_version);
  end if;
end;
$$;

alter table public.data_source_ingestion_runs
  add column lease_token uuid,
  add column heartbeat_at timestamptz,
  add column lease_expires_at timestamptz,
  add column lease_owner text,
  add column storage_reservation_id uuid,
  add column storage_object_id uuid,
  add column reconciliation_state text not null default 'active',
  add column reconciliation_attempts integer not null default 0,
  add column last_reconciled_at timestamptz,
  add column reconciliation_code text;

update public.data_source_ingestion_runs
set lease_token = gen_random_uuid(),
    heartbeat_at = coalesce(updated_at, attempt_started_at, created_at),
    lease_expires_at = greatest(coalesce(updated_at, now()), now()) + interval '2 hours'
where status = 'processing';

update public.data_source_ingestion_runs
set reconciliation_state = 'resolved', reconciliation_code = 'legacy_terminal'
where status in ('succeeded', 'failed');

alter table public.storage_reservations
  add constraint storage_reservations_id_tenant_user_unique150
    unique(id, tenant_id, user_id);

alter table public.data_source_ingestion_runs
  add constraint data_source_ingestion_runs_storage_reservation_fk150
    foreign key(storage_reservation_id, tenant_id, initiated_by_user_id)
    references public.storage_reservations(id, tenant_id, user_id)
    on delete restrict,
  add constraint data_source_ingestion_runs_storage_object_fk150
    foreign key(storage_object_id, tenant_id, initiated_by_user_id)
    references public.storage_objects(id, tenant_id, user_id)
    on delete restrict,
  add constraint data_source_ingestion_runs_storage_reservation_unique150
    unique(storage_reservation_id),
  add constraint data_source_ingestion_runs_storage_object_unique150
    unique(storage_object_id),
  add constraint data_source_ingestion_runs_reconciliation_state_check150
    check(reconciliation_state in ('active', 'investigating', 'ambiguous', 'resolved')),
  add constraint data_source_ingestion_runs_reconciliation_attempts_check150
    check(reconciliation_attempts >= 0),
  add constraint data_source_ingestion_runs_reconciliation_code_check150
    check(reconciliation_code is null or reconciliation_code ~ '^[a-z0-9_]{1,100}$');

create index data_source_ingestion_runs_recovery_claim150
on public.data_source_ingestion_runs(lease_expires_at, created_at)
where status = 'processing' and reconciliation_state in ('active', 'investigating', 'ambiguous');

create function public.reserve_source_ingestion150(
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
    set status = 'processing',
        attempt_started_at = v_now,
        heartbeat_at = v_now,
        lease_token = gen_random_uuid(),
        lease_expires_at = v_now + make_interval(secs => greatest(300, least(p_lease_seconds, 14400))),
        lease_owner = 'upload',
        reconciliation_state = 'active',
        reconciliation_code = null
    where id = v_run.id
    returning * into v_run;
    return query select v_run.id, v_run.status, 'reserved'::text,
      v_run.result_dataset_id, v_run.result_version_id, v_run.failure_code,
      v_run.lease_token, v_run.lease_expires_at;
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
    v_run.result_dataset_id, v_run.result_version_id, v_run.failure_code,
    case when v_run.status = 'processing' then null::uuid else v_run.lease_token end,
    v_run.lease_expires_at;
end;
$$;

create function public.heartbeat_source_ingestion150(
  p_tenant_id integer,
  p_ingestion_run_id uuid,
  p_lease_token uuid,
  p_lease_seconds integer default 7200
)
returns timestamptz
language plpgsql
security definer
set search_path = ''
as $$
declare v_expires timestamptz;
begin
  update public.data_source_ingestion_runs
  set heartbeat_at = now(),
      lease_expires_at = now() + make_interval(secs => greatest(300, least(p_lease_seconds, 14400)))
  where id = p_ingestion_run_id
    and tenant_id = p_tenant_id
    and status = 'processing'
    and reconciliation_state = 'active'
    and lease_token = p_lease_token
  returning lease_expires_at into v_expires;
  if not found then
    raise exception using errcode = 'P0001', message = 'ingestion_lease_lost';
  end if;
  return v_expires;
end;
$$;

create function public.attach_source_ingestion_reservation150(
  p_tenant_id integer,
  p_ingestion_run_id uuid,
  p_lease_token uuid,
  p_storage_reservation_id uuid
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare v_run public.data_source_ingestion_runs;
begin
  select * into v_run from public.data_source_ingestion_runs
  where id = p_ingestion_run_id and tenant_id = p_tenant_id for update;
  if not found or v_run.status <> 'processing'
     or v_run.reconciliation_state not in ('active', 'investigating')
     or v_run.lease_token is distinct from p_lease_token then
    raise exception using errcode = 'P0001', message = 'ingestion_lease_lost';
  end if;
  if not exists(
    select 1 from public.storage_reservations r
    where r.id = p_storage_reservation_id
      and r.tenant_id = v_run.tenant_id
      and r.user_id = v_run.initiated_by_user_id
      and r.category = 'dataset'
  ) then
    raise exception using errcode = 'P0001', message = 'ingestion_storage_reservation_invalid';
  end if;
  if v_run.storage_reservation_id is not null
     and v_run.storage_reservation_id <> p_storage_reservation_id then
    raise exception using errcode = 'P0001', message = 'ingestion_storage_reservation_conflict';
  end if;
  update public.data_source_ingestion_runs
  set storage_reservation_id = p_storage_reservation_id,
      heartbeat_at = now()
  where id = v_run.id;
  return true;
end;
$$;

create function public.attach_source_ingestion_storage150(
  p_tenant_id integer,
  p_ingestion_run_id uuid,
  p_lease_token uuid,
  p_storage_object_id uuid
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare v_run public.data_source_ingestion_runs;
declare v_object public.storage_objects;
begin
  select * into v_run from public.data_source_ingestion_runs
  where id = p_ingestion_run_id and tenant_id = p_tenant_id for update;
  if not found or v_run.status <> 'processing'
     or v_run.reconciliation_state not in ('active', 'investigating')
     or v_run.lease_token is distinct from p_lease_token then
    raise exception using errcode = 'P0001', message = 'ingestion_lease_lost';
  end if;
  select * into v_object from public.storage_objects o
  where o.id = p_storage_object_id
    and o.tenant_id = v_run.tenant_id
    and o.user_id = v_run.initiated_by_user_id
    and o.category = 'dataset'
    and o.status = 'active'
  for update;
  if not found or (v_run.storage_reservation_id is not null
      and v_object.reservation_id is distinct from v_run.storage_reservation_id) then
    raise exception using errcode = 'P0001', message = 'ingestion_storage_object_invalid';
  end if;
  if v_run.storage_object_id is not null and v_run.storage_object_id <> p_storage_object_id then
    raise exception using errcode = 'P0001', message = 'ingestion_storage_object_conflict';
  end if;
  update public.data_source_ingestion_runs
  set storage_reservation_id = coalesce(storage_reservation_id, v_object.reservation_id),
      storage_object_id = p_storage_object_id,
      heartbeat_at = now()
  where id = v_run.id;
  return true;
end;
$$;

create function public.complete_source_ingestion150(
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
    and r.initiated_by_user_id = p_user_id
  for update;
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
  if not found or v_source.status <> 'active' or v_source.source_type <> 'spreadsheet_upload' then
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
    jsonb_build_object('kind', 'source_upload', 'source_id', p_source_id,
      'ingestion_run_id', p_ingestion_run_id)
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

create function public.fail_source_ingestion150(
  p_tenant_id integer,
  p_project_id uuid,
  p_source_id uuid,
  p_user_id integer,
  p_ingestion_run_id uuid,
  p_lease_token uuid,
  p_failure_code text
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare v_run public.data_source_ingestion_runs;
begin
  select * into v_run from public.data_source_ingestion_runs r
  where r.id = p_ingestion_run_id and r.tenant_id = p_tenant_id
    and r.project_id = p_project_id and r.source_id = p_source_id
    and r.initiated_by_user_id = p_user_id for update;
  if not found or v_run.status <> 'processing' or v_run.reconciliation_state <> 'active'
     or v_run.lease_token is distinct from p_lease_token then
    raise exception using errcode = 'P0001', message = 'ingestion_lease_lost';
  end if;
  if v_run.storage_object_id is not null and exists(
    select 1 from public.storage_objects o where o.id = v_run.storage_object_id and o.status = 'active'
  ) then
    raise exception using errcode = 'P0001', message = 'ingestion_storage_cleanup_required';
  end if;
  update public.data_source_ingestion_runs
  set status = 'failed', completed_at = now(), failure_code = p_failure_code,
      lease_owner = null, lease_expires_at = null, reconciliation_state = 'resolved',
      reconciliation_code = 'request_failed', last_reconciled_at = now()
  where id = v_run.id;
  update public.data_sources
  set sync_state = 'error', last_error_code = p_failure_code
  where id = p_source_id and tenant_id = p_tenant_id and project_id = p_project_id
    and creator_user_id = p_user_id and status = 'active';
  return true;
end;
$$;

create function public.claim_stale_source_ingestions150(
  p_worker_id text,
  p_limit integer default 20,
  p_now timestamptz default now(),
  p_lease_seconds integer default 900
)
returns setof public.data_source_ingestion_runs
language plpgsql
security definer
set search_path = ''
as $$
begin
  return query
  update public.data_source_ingestion_runs r
  set lease_token = gen_random_uuid(),
      lease_owner = left(p_worker_id, 120),
      lease_expires_at = p_now + make_interval(secs => greatest(60, least(p_lease_seconds, 3600))),
      reconciliation_state = 'investigating',
      reconciliation_attempts = r.reconciliation_attempts + 1,
      last_reconciled_at = p_now,
      reconciliation_code = null
  where r.id in (
    select c.id from public.data_source_ingestion_runs c
    where c.status = 'processing'
      and c.lease_expires_at < p_now
      and c.reconciliation_state in ('active', 'investigating', 'ambiguous')
    order by c.lease_expires_at, c.created_at
    limit greatest(1, least(coalesce(p_limit, 20), 100))
    for update skip locked
  )
  returning r.*;
end;
$$;

create function public.settle_source_ingestion_reconciliation150(
  p_ingestion_run_id uuid,
  p_lease_token uuid,
  p_outcome text,
  p_code text,
  p_retry_seconds integer default 86400
)
returns public.data_source_ingestion_runs
language plpgsql
security definer
set search_path = ''
as $$
declare v_run public.data_source_ingestion_runs;
begin
  select * into v_run from public.data_source_ingestion_runs r
  where r.id = p_ingestion_run_id for update;
  if not found or v_run.status <> 'processing' or v_run.reconciliation_state <> 'investigating'
     or v_run.lease_token is distinct from p_lease_token then
    raise exception using errcode = 'P0001', message = 'ingestion_reconciliation_fence_lost';
  end if;
  if p_outcome = 'failed' then
    if v_run.storage_object_id is not null and exists(
      select 1 from public.storage_objects o where o.id = v_run.storage_object_id and o.status = 'active'
    ) then
      raise exception using errcode = 'P0001', message = 'ingestion_storage_cleanup_required';
    end if;
    update public.data_source_ingestion_runs
    set status = 'failed', completed_at = now(), failure_code = 'abandoned_ingestion',
        lease_owner = null, lease_expires_at = null, reconciliation_state = 'resolved',
        reconciliation_code = p_code, last_reconciled_at = now()
    where id = v_run.id returning * into v_run;
    update public.data_sources
    set sync_state = 'error', last_error_code = 'abandoned_ingestion'
    where id = v_run.source_id and tenant_id = v_run.tenant_id
      and project_id = v_run.project_id and creator_user_id = v_run.initiated_by_user_id
      and status = 'active';
  elsif p_outcome = 'ambiguous' then
    update public.data_source_ingestion_runs
    set lease_owner = null,
        lease_expires_at = now() + make_interval(secs => greatest(300, least(p_retry_seconds, 604800))),
        reconciliation_state = 'ambiguous', reconciliation_code = p_code,
        last_reconciled_at = now()
    where id = v_run.id returning * into v_run;
  else
    raise exception using errcode = '22023', message = 'ingestion_reconciliation_outcome_invalid';
  end if;
  return v_run;
end;
$$;

alter table public.data_source_ingestion_runs enable row level security;
revoke all on public.data_source_ingestion_runs from public, anon, authenticated;
grant select, insert, update, delete on public.data_source_ingestion_runs to service_role;

revoke all on function public.reserve_source_ingestion150(integer,uuid,uuid,integer,text,integer) from public,anon,authenticated;
revoke all on function public.heartbeat_source_ingestion150(integer,uuid,uuid,integer) from public,anon,authenticated;
revoke all on function public.attach_source_ingestion_reservation150(integer,uuid,uuid,uuid) from public,anon,authenticated;
revoke all on function public.attach_source_ingestion_storage150(integer,uuid,uuid,uuid) from public,anon,authenticated;
revoke all on function public.complete_source_ingestion150(integer,uuid,uuid,integer,uuid,uuid,text,uuid,text,text,text,bigint,text,jsonb,jsonb) from public,anon,authenticated;
revoke all on function public.fail_source_ingestion150(integer,uuid,uuid,integer,uuid,uuid,text) from public,anon,authenticated;
revoke all on function public.claim_stale_source_ingestions150(text,integer,timestamptz,integer) from public,anon,authenticated;
revoke all on function public.settle_source_ingestion_reconciliation150(uuid,uuid,text,text,integer) from public,anon,authenticated;
grant execute on function public.reserve_source_ingestion150(integer,uuid,uuid,integer,text,integer) to service_role;
grant execute on function public.heartbeat_source_ingestion150(integer,uuid,uuid,integer) to service_role;
grant execute on function public.attach_source_ingestion_reservation150(integer,uuid,uuid,uuid) to service_role;
grant execute on function public.attach_source_ingestion_storage150(integer,uuid,uuid,uuid) to service_role;
grant execute on function public.complete_source_ingestion150(integer,uuid,uuid,integer,uuid,uuid,text,uuid,text,text,text,bigint,text,jsonb,jsonb) to service_role;
grant execute on function public.fail_source_ingestion150(integer,uuid,uuid,integer,uuid,uuid,text) to service_role;
grant execute on function public.claim_stale_source_ingestions150(text,integer,timestamptz,integer) to service_role;
grant execute on function public.settle_source_ingestion_reconciliation150(uuid,uuid,text,text,integer) to service_role;

update public.application_schema_state set schema_version = 150, applied_at = now()
where contract_key = 'core';
notify pgrst, 'reload schema';
commit;
