begin;
-- Reconciled forward migration; original architecture SQL is archived unchanged.

do $$
declare
  v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version into v_schema_version
  from public.application_schema_state where contract_key = 'core' for update;
  if v_schema_version is null then
    raise exception using errcode='P0001', message='migration_157_schema_state_missing';
  end if;
  if v_schema_version <> 156 then
    raise exception using errcode='P0001', message='migration_157_expected_schema_156';
  end if;
end;
$$;

-- A coordinated, drained upgrade: never reinterpret an in-flight legacy send
-- as a failed send. Operators must reconcile unknown provider outcomes first.
-- The lock also serializes a legacy claim that started just before this DDL.
lock table public.notification_deliveries in access exclusive mode;
do $$
begin
  if exists(select 1 from public.notification_deliveries where status='processing') then
    raise exception using errcode='P0001', message='migration_157_requires_drained_deliveries';
  end if;
end;
$$;

alter table public.notification_deliveries
  add column claim_generation bigint not null default 0,
  add constraint notification_deliveries_generation_check check (claim_generation >= 0);

-- No unfenced writer may mutate canonical queue state after the cutover.
-- Existing resolver/cleanup functions are SECURITY DEFINER and retain access.
revoke insert,update,delete,truncate,references,trigger
  on public.notification_deliveries from public,anon,authenticated,service_role;
grant select on public.notification_deliveries to service_role;

create or replace function public.claim_notification_deliveries(
  p_limit integer default 25, p_now timestamptz default now(), p_lease_seconds integer default 900
) returns setof public.notification_deliveries
language plpgsql security definer set search_path = '' as $$
begin
  raise exception using errcode='P0001',message='notification_delivery_fencing_required';
end;
$$;

create or replace function public.finish_notification_delivery(
  p_delivery_id uuid, p_outcome text, p_error_code text default null,
  p_error_detail_safe text default null, p_available_at timestamptz default null,
  p_provider_message_id text default null, p_finished_at timestamptz default now()
) returns public.notification_deliveries
language plpgsql security definer set search_path = '' as $$
begin
  raise exception using errcode='P0001',message='notification_delivery_fencing_required';
end;
$$;

revoke all on function public.claim_notification_deliveries(integer,timestamptz,integer)
  from public,anon,authenticated,service_role;
revoke all on function public.finish_notification_delivery(uuid,text,text,text,timestamptz,text,timestamptz)
  from public,anon,authenticated,service_role;

create function public.notification_delivery_protocol()
returns integer language sql stable security definer set search_path = ''
as $$ select 2 $$;

create function public.claim_notification_deliveries_v2(
  p_limit integer default 25, p_lease_seconds integer default 900
) returns setof public.notification_deliveries
language plpgsql security definer set search_path = '' as $$
declare
  v_now timestamptz := clock_timestamp();
  v_limit integer := greatest(1,least(coalesce(p_limit,25),100));
begin
  -- Bounded cleanup, without waiting on another claim/finish transaction.
  update public.notification_deliveries d
  set status='dead',dead_at=v_now,processing_started_at=null,processing_lease_until=null,
      last_error_code=coalesce(d.last_error_code,'delivery_attempts_exhausted'),
      retention_until=greatest(d.retention_until,v_now+interval '180 days')
  where d.id in (
    select q.id from public.notification_deliveries q
    where q.attempts>=q.max_attempts and
      ((q.status='processing' and q.processing_lease_until<=v_now)
       or (q.status='pending' and q.available_at<=v_now))
    order by q.available_at,q.created_at,q.id limit v_limit for update skip locked
  );
  return query
  update public.notification_deliveries d
  set status='processing',attempts=d.attempts+1,claim_generation=d.claim_generation+1,
      processing_started_at=v_now,
      processing_lease_until=v_now+make_interval(secs=>greatest(30,least(coalesce(p_lease_seconds,900),3600))),
      last_error_code=null,last_error_detail_safe=null
  where d.id in (
    select q.id from public.notification_deliveries q
    where q.attempts<q.max_attempts and
      ((q.status='pending' and q.available_at<=v_now)
       or (q.status='processing' and q.processing_lease_until<=v_now))
    order by q.available_at,q.created_at,q.id limit v_limit for update skip locked
  ) returning d.*;
end;
$$;

create function public.finish_notification_delivery_v2(
  p_delivery_id uuid, p_claim_generation bigint, p_outcome text,
  p_error_code text default null, p_error_detail_safe text default null,
  p_retry_after_seconds integer default 60, p_provider_message_id text default null
) returns public.notification_deliveries
language plpgsql security definer set search_path = '' as $$
declare
  delivery public.notification_deliveries;
  v_now timestamptz;
begin
  if p_outcome is null or p_outcome not in ('sent','retry','dead','revoked') then
    raise exception using errcode='P0001',message='notification_delivery_outcome_invalid';
  end if;
  if p_claim_generation is null or p_claim_generation<=0 then
    raise exception using errcode='P0001',message='notification_delivery_claim_invalid';
  end if;
  -- Lock first: clock_timestamp must be sampled AFTER any lock wait. An UPDATE
  -- predicate evaluated before waiting could otherwise admit an expired lease.
  perform 1 from public.notification_deliveries where id=p_delivery_id for update;
  v_now:=clock_timestamp();
  update public.notification_deliveries d
  set status=case when p_outcome='sent' then 'sent'
                  when p_outcome in ('dead','revoked') or (p_outcome='retry' and d.attempts>=d.max_attempts) then 'dead'
                  else 'pending' end,
      sent_at=case when p_outcome='sent' then v_now else null end,
      dead_at=case when p_outcome in ('dead','revoked') or (p_outcome='retry' and d.attempts>=d.max_attempts) then v_now else null end,
      available_at=case when p_outcome='retry' and d.attempts<d.max_attempts
                       then v_now+make_interval(secs=>greatest(1,least(coalesce(p_retry_after_seconds,60),86400)))
                       else d.available_at end,
      processing_started_at=null,processing_lease_until=null,
      last_error_code=case when p_outcome='sent' then null else p_error_code end,
      last_error_detail_safe=case when p_outcome='sent' then null else left(p_error_detail_safe,500) end,
      provider_message_id=case when p_outcome='sent' then left(p_provider_message_id,200) else d.provider_message_id end,
      retention_until=case when p_outcome in ('dead','revoked') or (p_outcome='retry' and d.attempts>=d.max_attempts)
                           then greatest(d.retention_until,v_now+interval '180 days') else d.retention_until end
  where d.id=p_delivery_id and d.status='processing'
    and d.claim_generation=p_claim_generation and d.processing_lease_until>v_now
  returning d.* into delivery;
  if not found then
    raise exception using errcode='P0001',message='notification_delivery_claim_lost';
  end if;
  return delivery;
end;
$$;

revoke all on function public.notification_delivery_protocol() from public,anon,authenticated;
revoke all on function public.claim_notification_deliveries_v2(integer,integer) from public,anon,authenticated;
revoke all on function public.finish_notification_delivery_v2(uuid,bigint,text,text,text,integer,text) from public,anon,authenticated;
grant execute on function public.notification_delivery_protocol() to service_role;
grant execute on function public.claim_notification_deliveries_v2(integer,integer) to service_role;
grant execute on function public.finish_notification_delivery_v2(uuid,bigint,text,text,text,integer,text) to service_role;

update public.application_schema_state set schema_version=157,applied_at=now()
where contract_key = 'core';
notify pgrst,'reload schema';
commit;
