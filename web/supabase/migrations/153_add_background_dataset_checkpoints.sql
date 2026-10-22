begin;

do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version into v_schema_version
  from public.application_schema_state where contract_key = 'core' for update;
  if v_schema_version is null then
    raise exception using errcode = 'P0001', message = 'migration_153_schema_state_missing';
  end if;
  if v_schema_version <> 152 then
    raise exception using errcode = 'P0001',
      message = format('migration_153_expected_schema_152_got_%s', v_schema_version);
  end if;
end;
$$;

alter table public.data_dataset_checkpoints
  add column lease_owner text,
  add column lease_token uuid,
  add column lease_expires_at timestamptz,
  add column heartbeat_at timestamptz,
  add column attempt_count integer not null default 0,
  add column max_attempts integer not null default 3,
  add column next_attempt_at timestamptz not null default now(),
  add column storage_reservation_id uuid references public.storage_reservations(id) on delete restrict,
  add column storage_object_id uuid references public.storage_objects(id) on delete restrict,
  add column artifact_filename text,
  add column expected_record_count bigint,
  add column expected_state_hash text,
  add column last_reconciled_at timestamptz;

alter table public.data_dataset_checkpoints
  drop constraint data_dataset_checkpoints_status_check152,
  drop constraint data_dataset_checkpoints_terminal_check152,
  add constraint data_dataset_checkpoints_status_check153
    check(status in ('pending', 'materializing', 'ready', 'failed', 'ambiguous')),
  add constraint data_dataset_checkpoints_attempts_check153
    check(attempt_count between 0 and max_attempts and max_attempts between 1 and 10),
  add constraint data_dataset_checkpoints_expected_check153 check(
    expected_record_count is null or expected_record_count >= 0),
  add constraint data_dataset_checkpoints_expected_hash_check153 check(
    expected_state_hash is null or expected_state_hash ~ '^[0-9a-f]{64}$'),
  add constraint data_dataset_checkpoints_lease_check153 check(
    (status = 'materializing' and (
      (attempt_count = 0 and lease_owner is null and lease_token is null and lease_expires_at is null)
      or (attempt_count > 0 and lease_owner is not null and lease_token is not null
        and lease_expires_at is not null and heartbeat_at is not null)))
    or (status <> 'materializing' and lease_owner is null and lease_token is null
      and lease_expires_at is null)),
  add constraint data_dataset_checkpoints_terminal_check153 check(
    (status = 'pending' and completed_at is null and version_id is null)
    or (status = 'materializing' and completed_at is null and version_id is null)
    or (status = 'ready' and completed_at is not null and version_id is not null
      and record_count is not null and state_hash is not null and failure_code is null
      and (attempt_count = 0 or storage_object_id is not null))
    or (status = 'failed' and completed_at is not null and version_id is null
      and failure_code is not null)
    or (status = 'ambiguous' and completed_at is null and version_id is null
      and failure_code is not null));

create index data_dataset_checkpoints_claim153
on public.data_dataset_checkpoints(status, next_attempt_at, created_at)
where status = 'pending';
create index data_dataset_checkpoints_expired153
on public.data_dataset_checkpoints(lease_expires_at)
where status = 'materializing';

create or replace function public.request_dataset_checkpoint153(
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
    target_revision, requested_by_user_id, status, next_attempt_at
  ) values(
    p_tenant_id, p_project_id, p_source_id, p_resource_id, p_dataset_id,
    p_target_revision, p_user_id, 'pending', now()
  ) on conflict(dataset_id, target_revision) do nothing;
  select * into v_checkpoint from public.data_dataset_checkpoints c
  where c.dataset_id = p_dataset_id and c.target_revision = p_target_revision;
  return v_checkpoint;
end;
$$;

create function public.claim_dataset_checkpoints153(
  p_worker_id text, p_limit integer default 5, p_lease_seconds integer default 900
)
returns setof public.data_dataset_checkpoints
language plpgsql security definer set search_path = '' as $$
begin
  if p_worker_id !~ '^[A-Za-z0-9._:-]{1,120}$'
     or p_limit not between 1 and 20 or p_lease_seconds not between 60 and 3600 then
    raise exception using errcode = '22023', message = 'checkpoint_claim_invalid';
  end if;
  return query
  with candidates as (
    select c.id from public.data_dataset_checkpoints c
    where c.status = 'pending' and c.next_attempt_at <= now()
      and c.attempt_count < c.max_attempts
    order by c.next_attempt_at, c.created_at
    for update skip locked limit p_limit
  )
  update public.data_dataset_checkpoints c set
    status = 'materializing', lease_owner = p_worker_id,
    lease_token = gen_random_uuid(), lease_expires_at = now() + make_interval(secs => p_lease_seconds),
    heartbeat_at = now(), attempt_count = c.attempt_count + 1, failure_code = null
  from candidates q where c.id = q.id returning c.*;
end;
$$;

create function public.heartbeat_dataset_checkpoint153(
  p_checkpoint_id uuid, p_lease_token uuid, p_lease_seconds integer default 900
)
returns boolean language plpgsql security definer set search_path = '' as $$
begin
  if p_lease_seconds not between 60 and 3600 then
    raise exception using errcode = '22023', message = 'checkpoint_heartbeat_invalid';
  end if;
  update public.data_dataset_checkpoints set heartbeat_at = now(),
    lease_expires_at = now() + make_interval(secs => p_lease_seconds)
  where id = p_checkpoint_id and status = 'materializing'
    and lease_token = p_lease_token and lease_expires_at > now();
  return found;
end;
$$;

create function public.prepare_dataset_checkpoint153(
  p_checkpoint_id uuid, p_lease_token uuid, p_filename text,
  p_record_count bigint, p_state_hash text
)
returns boolean language plpgsql security definer set search_path = '' as $$
begin
  if btrim(p_filename) = '' or length(p_filename) > 255 or p_record_count < 0
     or p_state_hash !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = '22023', message = 'checkpoint_artifact_metadata_invalid';
  end if;
  update public.data_dataset_checkpoints set artifact_filename = btrim(p_filename),
    expected_record_count = p_record_count, expected_state_hash = p_state_hash,
    heartbeat_at = now()
  where id = p_checkpoint_id and status = 'materializing'
    and lease_token = p_lease_token and lease_expires_at > now();
  if not found then raise exception using errcode = 'P0001', message = 'checkpoint_lease_lost'; end if;
  return true;
end;
$$;

create function public.attach_dataset_checkpoint_storage153(
  p_checkpoint_id uuid, p_lease_token uuid, p_reservation_id uuid default null,
  p_storage_object_id uuid default null
)
returns boolean language plpgsql security definer set search_path = '' as $$
declare v_checkpoint public.data_dataset_checkpoints;
begin
  select * into v_checkpoint from public.data_dataset_checkpoints c
  where c.id = p_checkpoint_id for update;
  if not found or v_checkpoint.status <> 'materializing'
     or v_checkpoint.lease_token is distinct from p_lease_token
     or v_checkpoint.lease_expires_at <= now() then
    raise exception using errcode = 'P0001', message = 'checkpoint_lease_lost';
  end if;
  if p_reservation_id is not null and not exists(
    select 1 from public.storage_reservations r where r.id = p_reservation_id
      and r.tenant_id = v_checkpoint.tenant_id
      and r.user_id = v_checkpoint.requested_by_user_id and r.category = 'dataset') then
    raise exception using errcode = 'P0001', message = 'checkpoint_storage_reservation_invalid';
  end if;
  if p_storage_object_id is not null and not exists(
    select 1 from public.storage_objects o where o.id = p_storage_object_id
      and o.tenant_id = v_checkpoint.tenant_id
      and o.user_id = v_checkpoint.requested_by_user_id and o.category = 'dataset'
      and o.status = 'active') then
    raise exception using errcode = 'P0001', message = 'checkpoint_storage_object_invalid';
  end if;
  update public.data_dataset_checkpoints set
    storage_reservation_id = coalesce(p_reservation_id, storage_reservation_id),
    storage_object_id = coalesce(p_storage_object_id, storage_object_id),
    heartbeat_at = now() where id = p_checkpoint_id;
  return true;
end;
$$;

create function public.publish_dataset_checkpoint153(
  p_checkpoint_id uuid, p_lease_token uuid
)
returns table(dataset_id uuid, version_id uuid, version_number integer, target_revision bigint)
language plpgsql security definer set search_path = '' as $$
declare v_checkpoint public.data_dataset_checkpoints;
declare v_resource public.data_source_resources;
declare v_source public.data_sources;
declare v_storage public.storage_objects;
declare v_version public.data_dataset_versions;
declare v_version_number integer;
begin
  select * into v_checkpoint from public.data_dataset_checkpoints c
  where c.id = p_checkpoint_id for update;
  if not found then raise exception using errcode = 'P0001', message = 'checkpoint_not_found'; end if;
  if v_checkpoint.status = 'ready' then
    select * into v_version from public.data_dataset_versions v where v.id = v_checkpoint.version_id;
    return query select v_checkpoint.dataset_id, v_checkpoint.version_id,
      v_version.version_number, v_checkpoint.target_revision; return;
  end if;
  if v_checkpoint.status <> 'materializing'
     or v_checkpoint.lease_token is distinct from p_lease_token
     or v_checkpoint.lease_expires_at <= now() then
    raise exception using errcode = 'P0001', message = 'checkpoint_lease_lost';
  end if;
  select * into v_resource from public.data_source_resources r
  where r.id = v_checkpoint.source_resource_id for update;
  if not found or v_resource.dataset_id <> v_checkpoint.dataset_id
     or v_resource.committed_revision < v_checkpoint.target_revision then
    raise exception using errcode = 'P0001', message = 'checkpoint_lineage_invalid';
  end if;
  select * into v_source from public.data_sources s where s.id = v_checkpoint.source_id for update;
  select * into v_storage from public.storage_objects o
  where o.id = v_checkpoint.storage_object_id for update;
  if not found or v_storage.tenant_id <> v_checkpoint.tenant_id
     or v_storage.user_id is distinct from v_checkpoint.requested_by_user_id
     or v_storage.category <> 'dataset' or v_storage.status <> 'active'
     or v_checkpoint.expected_state_hash is null
     or v_checkpoint.expected_record_count is null
     or v_checkpoint.artifact_filename is null then
    raise exception using errcode = 'P0001', message = 'checkpoint_storage_invalid';
  end if;
  select coalesce(max(v.version_number), 0) + 1 into v_version_number
  from public.data_dataset_versions v where v.dataset_id = v_checkpoint.dataset_id;
  insert into public.data_dataset_versions(
    tenant_id,dataset_id,version_number,storage_object_id,created_by_user_id,
    version_kind,original_filename,content_type,file_extension,size_bytes,
    content_hash,file_metadata,provenance
  ) values(
    v_checkpoint.tenant_id,v_checkpoint.dataset_id,v_version_number,v_storage.id,
    v_checkpoint.requested_by_user_id,'checkpoint',v_checkpoint.artifact_filename,
    'text/csv','.csv',v_storage.size_bytes,v_storage.sha256,
    jsonb_build_object('rows',v_checkpoint.expected_record_count,'format','csv',
      'dataset_revision',v_checkpoint.target_revision,'state_hash',v_checkpoint.expected_state_hash),
    jsonb_build_object('kind','incremental_checkpoint','source_id',v_checkpoint.source_id,
      'source_resource_id',v_checkpoint.source_resource_id,
      'dataset_revision',v_checkpoint.target_revision)
  ) returning * into v_version;
  update public.data_dataset_checkpoints set status='ready',version_id=v_version.id,
    record_count=expected_record_count,state_hash=expected_state_hash,completed_at=now(),
    failure_code=null,lease_owner=null,lease_token=null,lease_expires_at=null
  where id=v_checkpoint.id;
  update public.data_source_resources set latest_checkpoint_version_id=v_version.id
  where id=v_resource.id and (latest_checkpoint_version_id is null or
    v_checkpoint.target_revision >= coalesce((select (v.file_metadata->>'dataset_revision')::bigint
      from public.data_dataset_versions v where v.id=latest_checkpoint_version_id),0));
  if v_resource.resource_key = v_source.resource_type then
    update public.data_sources set latest_dataset_id=v_checkpoint.dataset_id,
      latest_version_id=v_version.id where id=v_source.id
      and (latest_version_id is null or v_checkpoint.target_revision >= coalesce(
        (select (existing.file_metadata->>'dataset_revision')::bigint
         from public.data_dataset_versions existing where existing.id=latest_version_id),0));
  end if;
  return query select v_checkpoint.dataset_id,v_version.id,v_version.version_number,
    v_checkpoint.target_revision;
end;
$$;

create function public.settle_dataset_checkpoint153(
  p_checkpoint_id uuid, p_lease_token uuid, p_outcome text,
  p_failure_code text, p_retry_seconds integer default 60
)
returns public.data_dataset_checkpoints
language plpgsql security definer set search_path = '' as $$
declare v_checkpoint public.data_dataset_checkpoints;
begin
  select * into v_checkpoint from public.data_dataset_checkpoints c
  where c.id=p_checkpoint_id for update;
  if not found or v_checkpoint.status <> 'materializing'
     or v_checkpoint.lease_token is distinct from p_lease_token then
    raise exception using errcode='P0001',message='checkpoint_lease_lost';
  end if;
  if p_failure_code !~ '^[a-z0-9_]{1,120}$'
     or p_outcome not in ('retry','failed','ambiguous') then
    raise exception using errcode='22023',message='checkpoint_settlement_invalid';
  end if;
  if p_outcome='retry' and v_checkpoint.attempt_count < v_checkpoint.max_attempts then
    update public.data_dataset_checkpoints set status='pending',failure_code=p_failure_code,
      next_attempt_at=now()+make_interval(secs=>greatest(1,least(p_retry_seconds,3600))),
      lease_owner=null,lease_token=null,lease_expires_at=null,last_reconciled_at=now()
    where id=p_checkpoint_id returning * into v_checkpoint;
  elsif p_outcome='ambiguous' then
    update public.data_dataset_checkpoints set status='ambiguous',failure_code=p_failure_code,
      lease_owner=null,lease_token=null,lease_expires_at=null,last_reconciled_at=now()
    where id=p_checkpoint_id returning * into v_checkpoint;
  else
    update public.data_dataset_checkpoints set status='failed',failure_code=p_failure_code,
      completed_at=now(),lease_owner=null,lease_token=null,lease_expires_at=null,
      last_reconciled_at=now()
    where id=p_checkpoint_id returning * into v_checkpoint;
  end if;
  return v_checkpoint;
end;
$$;

create function public.claim_expired_dataset_checkpoints153(
  p_worker_id text, p_limit integer default 5, p_lease_seconds integer default 300
)
returns setof public.data_dataset_checkpoints
language plpgsql security definer set search_path = '' as $$
begin
  if p_worker_id !~ '^[A-Za-z0-9._:-]{1,120}$' or p_limit not between 1 and 20
     or p_lease_seconds not between 60 and 3600 then
    raise exception using errcode='22023',message='checkpoint_reconcile_claim_invalid';
  end if;
  return query with candidates as (
    select c.id from public.data_dataset_checkpoints c
    where c.status='materializing' and c.lease_expires_at <= now()
    order by c.lease_expires_at for update skip locked limit p_limit
  ) update public.data_dataset_checkpoints c set lease_owner=p_worker_id,
    lease_token=gen_random_uuid(),lease_expires_at=now()+make_interval(secs=>p_lease_seconds),
    heartbeat_at=now(),last_reconciled_at=now()
  from candidates q where c.id=q.id returning c.*;
end;
$$;

revoke all on function public.request_dataset_checkpoint153(integer,uuid,uuid,uuid,uuid,integer,bigint),
  public.claim_dataset_checkpoints153(text,integer,integer),
  public.heartbeat_dataset_checkpoint153(uuid,uuid,integer),
  public.prepare_dataset_checkpoint153(uuid,uuid,text,bigint,text),
  public.attach_dataset_checkpoint_storage153(uuid,uuid,uuid,uuid),
  public.publish_dataset_checkpoint153(uuid,uuid),
  public.settle_dataset_checkpoint153(uuid,uuid,text,text,integer),
  public.claim_expired_dataset_checkpoints153(text,integer,integer)
from public,anon,authenticated;
grant execute on function public.request_dataset_checkpoint153(integer,uuid,uuid,uuid,uuid,integer,bigint),
  public.claim_dataset_checkpoints153(text,integer,integer),
  public.heartbeat_dataset_checkpoint153(uuid,uuid,integer),
  public.prepare_dataset_checkpoint153(uuid,uuid,text,bigint,text),
  public.attach_dataset_checkpoint_storage153(uuid,uuid,uuid,uuid),
  public.publish_dataset_checkpoint153(uuid,uuid),
  public.settle_dataset_checkpoint153(uuid,uuid,text,text,integer),
  public.claim_expired_dataset_checkpoints153(text,integer,integer)
to service_role;

update public.application_schema_state set schema_version=153,applied_at=now()
where contract_key='core';
notify pgrst,'reload schema';
commit;
