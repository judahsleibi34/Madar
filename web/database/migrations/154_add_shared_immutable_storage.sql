begin;

-- Shared immutable Data Sources artifacts over the existing private Supabase Storage provider.

do $$
declare
  v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version into v_schema_version
  from public.application_schema_state
  where contract_key = 'core'
  for update;
  if v_schema_version is null then
    raise exception using errcode='P0001', message='schema154_requires_exact_schema153';
  end if;
  if v_schema_version <> 153 then
    raise exception using errcode='P0001', message='schema154_requires_exact_schema153';
  end if;
end;
$$;

alter table public.storage_reservations
  add column storage_backend text,
  add column storage_bucket text,
  add column provider_object_key text,
  add column expected_size_bytes bigint,
  add column expected_sha256 text,
  add column transfer_state text not null default 'none',
  add column transfer_updated_at timestamptz;

alter table public.storage_reservations
  add constraint storage_reservations_transfer_state154
    check(transfer_state in ('none','prepared','verified','ambiguous')),
  add constraint storage_reservations_expected_hash154
    check(expected_sha256 is null or expected_sha256 ~ '^[0-9a-f]{64}$'),
  add constraint storage_reservations_provider_shape154 check(
    (transfer_state='none' and storage_backend is null and storage_bucket is null
      and provider_object_key is null and expected_size_bytes is null and expected_sha256 is null)
    or
    (transfer_state<>'none' and storage_backend='supabase_private'
      and storage_bucket='madar-data-immutable'
      and provider_object_key is not null and expected_size_bytes=bytes
      and expected_sha256 ~ '^[0-9a-f]{64}$')
  );

alter table public.storage_objects
  add column storage_backend text not null default 'local_private',
  add column storage_bucket text,
  add column provider_object_key text,
  add column verified_size_bytes bigint,
  add column verified_sha256 text,
  add column integrity_verified_at timestamptz;

alter table public.storage_objects
  add constraint storage_objects_verified_hash154
    check(verified_sha256 is null or verified_sha256 ~ '^[0-9a-f]{64}$'),
  add constraint storage_objects_backend154 check(
    (storage_backend='local_private' and storage_bucket is null and provider_object_key is null
      and verified_size_bytes is null and verified_sha256 is null and integrity_verified_at is null)
    or
    (storage_backend='supabase_private' and storage_bucket='madar-data-immutable'
      and provider_object_key is not null and verified_size_bytes=size_bytes
      and verified_sha256=sha256 and integrity_verified_at is not null)
  );

create unique index storage_objects_provider_identity154
on public.storage_objects(storage_backend,storage_bucket,provider_object_key)
where storage_backend='supabase_private' and status='active';

create index storage_reservations_transfer_recovery154
on public.storage_reservations(status,transfer_state,expires_at)
where transfer_state<>'none';

create function public.prepare_immutable_storage154(
  p_reservation_id uuid, p_storage_bucket text, p_provider_object_key text,
  p_expected_size_bytes bigint, p_expected_sha256 text
)
returns public.storage_reservations
language plpgsql security definer set search_path='' as $$
declare v_reservation public.storage_reservations;
begin
  select * into v_reservation from public.storage_reservations r
  where r.id=p_reservation_id for update;
  if not found or v_reservation.status<>'reserved' then
    raise exception using errcode='P0001', message='storage_reservation_state_conflict';
  end if;
  if p_storage_bucket<>'madar-data-immutable'
     or p_expected_size_bytes<>v_reservation.bytes
     or p_expected_sha256 !~ '^[0-9a-f]{64}$'
     or p_provider_object_key<>(
       'tenant_'||v_reservation.tenant_id||'/dataset/'||v_reservation.id||'/'||
       p_expected_sha256||case
         when right(p_provider_object_key,4)='.csv' then '.csv'
         when right(p_provider_object_key,4)='.xls' then '.xls'
         when right(p_provider_object_key,5)='.xlsx' then '.xlsx'
         else '' end
     ) then
    raise exception using errcode='P0001', message='immutable_storage_identity_invalid';
  end if;
  if v_reservation.transfer_state<>'none' and (
    v_reservation.storage_bucket is distinct from p_storage_bucket
    or v_reservation.provider_object_key is distinct from p_provider_object_key
    or v_reservation.expected_size_bytes is distinct from p_expected_size_bytes
    or v_reservation.expected_sha256 is distinct from p_expected_sha256) then
    raise exception using errcode='P0001', message='immutable_storage_prepare_conflict';
  end if;
  update public.storage_reservations set
    storage_backend='supabase_private', storage_bucket=p_storage_bucket,
    provider_object_key=p_provider_object_key, expected_size_bytes=p_expected_size_bytes,
    expected_sha256=p_expected_sha256,
    transfer_state=case when transfer_state='verified' then 'verified' else 'prepared' end,
    transfer_updated_at=now()
  where id=p_reservation_id returning * into v_reservation;
  return v_reservation;
end;
$$;

create function public.verify_immutable_storage154(p_reservation_id uuid)
returns public.storage_reservations
language plpgsql security definer set search_path='' as $$
declare v_reservation public.storage_reservations;
begin
  select * into v_reservation from public.storage_reservations r
  where r.id=p_reservation_id for update;
  if not found or v_reservation.status<>'reserved'
     or v_reservation.transfer_state not in ('prepared','verified','ambiguous') then
    raise exception using errcode='P0001', message='immutable_storage_not_prepared';
  end if;
  update public.storage_reservations set transfer_state='verified',transfer_updated_at=now()
  where id=p_reservation_id returning * into v_reservation;
  return v_reservation;
end;
$$;

create function public.mark_immutable_storage_ambiguous154(p_reservation_id uuid)
returns public.storage_reservations
language plpgsql security definer set search_path='' as $$
declare v_reservation public.storage_reservations;
begin
  update public.storage_reservations set transfer_state='ambiguous',transfer_updated_at=now()
  where id=p_reservation_id and status='reserved' and transfer_state<>'none'
  returning * into v_reservation;
  if not found then
    raise exception using errcode='P0001', message='storage_reservation_state_conflict';
  end if;
  return v_reservation;
end;
$$;

create function public.finish_immutable_storage154(
  p_reservation_id uuid, p_storage_key text, p_retention_until timestamptz default null
)
returns uuid
language plpgsql security definer set search_path='' as $$
declare v_reservation public.storage_reservations; v_object public.storage_objects; v_object_id uuid;
begin
  select * into v_reservation from public.storage_reservations r
  where r.id=p_reservation_id for update;
  if not found then
    raise exception using errcode='P0001', message='storage_reservation_state_conflict';
  end if;
  if v_reservation.status='committed' then
    select * into v_object from public.storage_objects o
    where o.reservation_id=v_reservation.id;
    if not found or v_object.storage_key<>p_storage_key
       or v_object.storage_backend<>'supabase_private'
       or v_object.provider_object_key is distinct from v_reservation.provider_object_key then
      raise exception using errcode='P0001', message='immutable_storage_finish_conflict';
    end if;
    return v_object.id;
  end if;
  if v_reservation.status<>'reserved' or v_reservation.transfer_state<>'verified'
     or p_storage_key is null or length(p_storage_key)>500 then
    raise exception using errcode='P0001', message='immutable_storage_not_verified';
  end if;
  update public.storage_accounts set
    reserved_bytes=greatest(0,reserved_bytes-v_reservation.bytes),
    used_bytes=used_bytes+v_reservation.bytes,updated_at=now()
  where tenant_id=v_reservation.tenant_id
    and scope_key in ('tenant','user:'||coalesce(v_reservation.user_id::text,''));
  update public.storage_reservations set status='committed',finished_at=now()
  where id=v_reservation.id;
  insert into public.storage_objects(
    reservation_id,tenant_id,user_id,category,storage_key,size_bytes,sha256,
    retention_until,storage_backend,storage_bucket,provider_object_key,
    verified_size_bytes,verified_sha256,integrity_verified_at
  ) values(
    v_reservation.id,v_reservation.tenant_id,v_reservation.user_id,v_reservation.category,
    p_storage_key,v_reservation.bytes,v_reservation.expected_sha256,p_retention_until,
    'supabase_private',v_reservation.storage_bucket,v_reservation.provider_object_key,
    v_reservation.expected_size_bytes,v_reservation.expected_sha256,now()
  ) returning id into v_object_id;
  return v_object_id;
end;
$$;

create function public.require_shared_incremental_storage154()
returns trigger language plpgsql set search_path='' as $$
begin
  if not exists(select 1 from public.storage_objects o
    where o.id=new.storage_object_id and o.tenant_id=new.tenant_id
      and o.status='active' and o.storage_backend='supabase_private'
      and o.storage_bucket='madar-data-immutable'
      and o.verified_size_bytes=o.size_bytes and o.verified_sha256=o.sha256
      and o.integrity_verified_at is not null) then
    raise exception using errcode='P0001', message='incremental_history_storage_not_verified';
  end if;
  return new;
end;
$$;

create trigger require_shared_incremental_storage154
before insert on public.data_dataset_record_changes
for each row execute function public.require_shared_incremental_storage154();

create function public.require_shared_checkpoint_storage154()
returns trigger language plpgsql set search_path='' as $$
begin
  if new.version_kind='checkpoint' and not exists(select 1 from public.storage_objects o
    where o.id=new.storage_object_id and o.tenant_id=new.tenant_id
      and o.status='active' and o.storage_backend='supabase_private'
      and o.storage_bucket='madar-data-immutable'
      and o.verified_size_bytes=o.size_bytes and o.verified_sha256=o.sha256
      and o.integrity_verified_at is not null) then
    raise exception using errcode='P0001', message='checkpoint_storage_not_verified';
  end if;
  return new;
end;
$$;

create trigger require_shared_checkpoint_storage154
before insert on public.data_dataset_versions
for each row execute function public.require_shared_checkpoint_storage154();

create function public.protect_published_dataset_storage154()
returns trigger language plpgsql set search_path='' as $$
begin
  if old.status='active' and new.status<>'active'
     and exists(select 1 from public.data_dataset_versions v where v.storage_object_id=old.id) then
    raise exception using errcode='P0001', message='dataset_version_storage_referenced';
  end if;
  return new;
end;
$$;

create trigger protect_published_dataset_storage154
before update of status on public.storage_objects
for each row execute function public.protect_published_dataset_storage154();

revoke all on function public.prepare_immutable_storage154(uuid,text,text,bigint,text),
  public.verify_immutable_storage154(uuid),
  public.mark_immutable_storage_ambiguous154(uuid),
  public.finish_immutable_storage154(uuid,text,timestamptz)
from public,anon,authenticated;
grant execute on function public.prepare_immutable_storage154(uuid,text,text,bigint,text),
  public.verify_immutable_storage154(uuid),
  public.mark_immutable_storage_ambiguous154(uuid),
  public.finish_immutable_storage154(uuid,text,timestamptz)
to service_role;

update public.application_schema_state set schema_version=154,applied_at=now()
where contract_key = 'core' and schema_version=153;
do $$ begin
  if not exists(select 1 from public.application_schema_state
    where contract_key = 'core' and schema_version=154) then
    raise exception using errcode='P0001', message='schema154_state_transition_failed';
  end if;
end $$;

notify pgrst,'reload schema';
commit;
