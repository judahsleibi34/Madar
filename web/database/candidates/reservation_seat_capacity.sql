-- LOCAL REVIEW CANDIDATE ONLY. Not a numbered/selected migration.
-- No schema-state, release-manifest or existing function replacement.
-- Installation requires separately reviewed release-lineage integration.
begin;

create function public.builder_reservation_group_capacity(p_snapshot jsonb)
returns integer language plpgsql immutable set search_path = pg_catalog as $$
declare v_config jsonb := coalesce(p_snapshot #> '{0,session}',p_snapshot #> '{0,reservation}'); v_capacity text;
begin
  if v_config ->> 'sessionType' is distinct from 'group'
    or v_config ->> 'bookingMode' = 'flexible' then return null; end if;
  v_capacity := v_config ->> 'seatCapacity';
  if jsonb_typeof(v_config -> 'seatCapacity') is distinct from 'number'
    or v_capacity !~ '^[0-9]{1,4}$' then
    raise exception using errcode='P0001',message='reservation_capacity_invalid';
  end if;
  if v_capacity::integer not between 2 and 1000 then
    raise exception using errcode='P0001',message='reservation_capacity_invalid';
  end if;
  return v_capacity::integer;
end;
$$;

create function public.builder_reservation_seats(p_payload jsonb, p_capacity integer)
returns integer language plpgsql immutable set search_path = pg_catalog as $$
declare v_seats text := coalesce(p_payload ->> 'guests','1');
begin
  if p_capacity is null then return 1; end if;
  if v_seats !~ '^[1-9][0-9]{0,3}$' then
    raise exception using errcode='P0001',message='reservation_seats_invalid';
  end if;
  if v_seats::integer > p_capacity then
    raise exception using errcode='P0001',message='reservation_seats_invalid';
  end if;
  return v_seats::integer;
end;
$$;

create function public.guard_builder_reservation_seats()
returns trigger language plpgsql security definer set search_path = pg_catalog, public as $$
declare v_capacity integer; v_other_capacity integer; v_seats integer; v_used bigint;
begin
  if new.status not in ('new','confirmed') then return new; end if;
  v_capacity := public.builder_reservation_group_capacity(new.field_snapshot);
  v_seats := public.builder_reservation_seats(new.payload,v_capacity);
  if new.exclusive_slot then v_capacity := 1; end if;
  -- Match the retained create/status functions' block namespace.
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtext(pg_catalog.concat_ws(
    ':','builder-reservation',new.tenant_id,new.project_id,new.block_id)));
  select coalesce(sum(public.builder_reservation_seats(other.payload,
           public.builder_reservation_group_capacity(other.field_snapshot))),0),
         min(case when other.exclusive_slot then 1
             else public.builder_reservation_group_capacity(other.field_snapshot) end)
    into v_used,v_other_capacity
  from public.builder_reservations other
  where other.tenant_id=new.tenant_id and other.project_id=new.project_id and other.block_id=new.block_id
    and other.id<>new.id and other.status in ('new','confirmed')
    and ((new.ends_at is null and
          (other.starts_at=new.starts_at or
           (other.ends_at is not null and other.starts_at<=new.starts_at and other.ends_at>new.starts_at)))
      or (new.ends_at is not null and
          ((other.ends_at is null and other.starts_at>=new.starts_at and other.starts_at<new.ends_at)
            or (other.ends_at is not null and other.starts_at<new.ends_at and other.ends_at>new.starts_at))));
  v_capacity := least(v_capacity,v_other_capacity);
  if v_capacity is null then return new; end if;
  -- Repeatable-read snapshots must not bypass a writer that won the block lock.
  if current_setting('transaction_isolation') <> 'read committed' then
    raise exception using errcode='40001',message='reservation_capacity_retry_required';
  end if;
  if new.starts_at is null then
    raise exception using errcode='P0001',message='reservation_time_required';
  end if;
  if v_seats+v_used>v_capacity then
    raise exception using errcode='P0001',message='reservation_slot_unavailable';
  end if;
  return new;
end;
$$;

create trigger guard_builder_reservation_seats
before insert or update of status,starts_at,ends_at,tenant_id,project_id,block_id,payload,field_snapshot,exclusive_slot
on public.builder_reservations for each row execute function public.guard_builder_reservation_seats();

-- Keep ownership, account fences, idempotency, cancellation and transactional
-- notification behavior in the existing installed RPC. The trigger above also
-- checks reactivation through retained status RPCs and rejects direct overflow.
create function public.create_builder_reservation_seated_safe(
  p_reservation jsonb, p_idempotency_key_hash text, p_request_hash text,
  p_exclusive_slot boolean, p_notification jsonb
) returns jsonb language plpgsql security definer set search_path = pg_catalog, public as $$
declare v_capacity integer;
begin
  v_capacity := public.builder_reservation_group_capacity(p_reservation -> 'field_snapshot');
  if v_capacity is null or p_exclusive_slot is distinct from true then
    raise exception using errcode='P0001',message='reservation_capacity_invalid';
  end if;
  perform public.builder_reservation_seats(p_reservation -> 'payload',v_capacity);
  return public.create_builder_reservation_notified_safe(
    p_reservation,p_idempotency_key_hash,p_request_hash,false,p_notification);
end;
$$;

revoke all on function public.builder_reservation_group_capacity(jsonb) from public,anon,authenticated;
revoke all on function public.builder_reservation_seats(jsonb,integer) from public,anon,authenticated;
revoke all on function public.guard_builder_reservation_seats() from public,anon,authenticated;
revoke all on function public.create_builder_reservation_seated_safe(jsonb,text,text,boolean,jsonb) from public,anon,authenticated;
grant execute on function public.create_builder_reservation_seated_safe(jsonb,text,text,boolean,jsonb) to service_role;
commit;
