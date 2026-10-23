begin;
-- Reconciled forward migration; original architecture SQL is archived unchanged.

do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version into v_schema_version from public.application_schema_state
  where contract_key = 'core' for update;
  if v_schema_version is null then
    raise exception using errcode='P0001',message='migration_159_schema_state_missing';
  end if;
  if v_schema_version <> 158 then
    raise exception using errcode='P0001',message='migration_159_expected_schema_158';
  end if;
end;
$$;

-- Resolver materialization is a transaction, not an external provider send.
-- Nonetheless do not silently reinterpret another resolver's processing claim.
lock table public.notification_outbox in access exclusive mode;
do $$
begin
  if exists(select 1 from public.notification_outbox where status='processing') then
    raise exception using errcode='P0001',message='migration_159_requires_drained_outbox';
  end if;
end;
$$;

alter table public.notification_outbox
  add column claim_generation bigint not null default 0,
  add column processing_lease_until timestamptz,
  add constraint notification_outbox_generation_check check(claim_generation>=0);

-- Enqueuers retain INSERT/SELECT. Existing SECURITY DEFINER transactional
-- enqueuers and retention cleanup retain their owner privileges. No runtime
-- direct UPDATE/DELETE may bypass the fenced RPCs.
revoke update,delete,truncate,references,trigger on public.notification_outbox
  from public,anon,authenticated,service_role;
revoke all on function public.claim_notification_outbox(integer,timestamptz)
  from public,anon,authenticated,service_role;
revoke all on function public.finish_notification_outbox(uuid,boolean,text,timestamptz,timestamptz)
  from public,anon,authenticated,service_role;
revoke all on function public.resolve_notification_outbox(uuid,timestamptz)
  from public,anon,authenticated,service_role;
revoke all on function public.resolve_notification_outbox_v2(uuid,timestamptz,boolean,boolean)
  from public,anon,authenticated,service_role;

-- Retain the reviewed materialization implementation as an owner-only helper.
-- The legacy public name becomes a rejection stub, including for accidental
-- calls from an old SECURITY DEFINER wrapper.
alter function public.resolve_notification_outbox_v2(uuid,timestamptz,boolean,boolean)
  rename to notification_outbox_materialize_149;
create function public.resolve_notification_outbox_v2(
  p_outbox_id uuid,p_now timestamptz default now(),
  p_email_enabled boolean default true,p_web_push_enabled boolean default true
) returns integer language plpgsql set search_path='' as $$
begin
  raise exception using errcode='P0001',message='notification_outbox_fenced_protocol_required';
end;
$$;
revoke all on function public.resolve_notification_outbox_v2(uuid,timestamptz,boolean,boolean)
  from public,anon,authenticated,service_role;

create function public.notification_outbox_protocol()
returns integer language sql stable security definer set search_path=''
as $$ select 2 $$;

create function public.claim_notification_outbox_v2(
  p_limit integer default 25,p_lease_seconds integer default 900
) returns setof public.notification_outbox
language plpgsql security definer set search_path='' as $$
declare
  v_now timestamptz:=clock_timestamp();
  v_limit integer:=greatest(1,least(coalesce(p_limit,25),100));
begin
  update public.notification_outbox o
  set status='dead',processing_started_at=null,processing_lease_until=null,
      last_error_code=coalesce(o.last_error_code,'resolution_attempts_exhausted')
  where o.id in (
    select q.id from public.notification_outbox q
    where q.attempts>=q.max_attempts and
      ((q.status='processing' and q.processing_lease_until<=v_now)
        or (q.status in ('pending','failed') and q.available_at<=v_now))
    order by q.available_at,q.created_at,q.id limit v_limit for update skip locked
  );
  return query
  update public.notification_outbox o
  set status='processing',attempts=o.attempts+1,claim_generation=o.claim_generation+1,
      processing_started_at=v_now,
      processing_lease_until=v_now+make_interval(secs=>greatest(30,least(coalesce(p_lease_seconds,900),3600))),
      last_error_code=null
  where o.id in (
    select q.id from public.notification_outbox q
    where q.attempts<q.max_attempts and
      ((q.status in ('pending','failed') and q.available_at<=v_now)
        or (q.status='processing' and q.processing_lease_until<=v_now))
    order by q.available_at,q.created_at,q.id limit v_limit for update skip locked
  ) returning o.*;
end;
$$;

create function public.finish_notification_outbox_v2(
  p_outbox_id uuid,p_claim_generation bigint,p_outcome text,
  p_failure_code text default null,p_retry_after_seconds integer default 60
) returns public.notification_outbox
language plpgsql security definer set search_path='' as $$
declare
  v_now timestamptz;
  result public.notification_outbox;
begin
  if p_outcome is null or p_outcome not in ('sent','retry','dead','revoked') then
    raise exception using errcode='P0001',message='notification_outbox_outcome_invalid';
  end if;
  if p_claim_generation is null or p_claim_generation<=0 then
    raise exception using errcode='P0001',message='notification_outbox_claim_invalid';
  end if;
  perform 1 from public.notification_outbox where id=p_outbox_id for update;
  v_now:=clock_timestamp();
  update public.notification_outbox o
  set status=case when p_outcome='sent' then 'sent'
                  when p_outcome in ('dead','revoked') or o.attempts>=o.max_attempts then 'dead'
                  else 'failed' end,
      sent_at=case when p_outcome='sent' then v_now else null end,
      available_at=case when p_outcome='retry' and o.attempts<o.max_attempts
                       then v_now+make_interval(secs=>greatest(1,least(coalesce(p_retry_after_seconds,60),86400)))
                       else o.available_at end,
      last_error_code=case when p_outcome='sent' then null else p_failure_code end,
      processing_started_at=null,processing_lease_until=null
  where o.id=p_outbox_id and o.status='processing'
    and o.claim_generation=p_claim_generation and o.processing_lease_until>v_now
  returning o.* into result;
  if not found then
    raise exception using errcode='P0001',message='notification_outbox_claim_lost';
  end if;
  return result;
end;
$$;

create function public.resolve_notification_outbox_v3(
  p_outbox_id uuid,p_claim_generation bigint,p_email_enabled boolean,p_web_push_enabled boolean
) returns integer
language plpgsql security definer set search_path='' as $$
declare
  work public.notification_outbox;
  inserted_count integer;
  v_now timestamptz;
begin
  if p_claim_generation is null or p_claim_generation<=0 then
    raise exception using errcode='P0001',message='notification_outbox_claim_invalid';
  end if;
  select * into work from public.notification_outbox where id=p_outbox_id for update;
  v_now:=clock_timestamp();
  if not found or work.status<>'processing' or work.claim_generation<>p_claim_generation
     or work.processing_lease_until is null or work.processing_lease_until<=v_now then
    raise exception using errcode='P0001',message='notification_outbox_claim_lost';
  end if;
  -- Reuse the unchanged, reviewed materializer under the same row lock and
  -- transaction. Runtime callers no longer have EXECUTE on that legacy RPC.
  inserted_count:=public.notification_outbox_materialize_149(
    p_outbox_id,v_now,p_email_enabled,p_web_push_enabled);
  -- Sample the database clock again after materialization/lock waits. If the
  -- lease expired meanwhile, raising rolls back BOTH delivery inserts and the
  -- legacy internal sent update. No application pre-read is trusted.
  update public.notification_outbox o
  set processing_started_at=null,processing_lease_until=null
  where o.id=p_outbox_id and o.status='sent' and o.claim_generation=p_claim_generation
    and o.processing_lease_until>clock_timestamp();
  if not found then
    raise exception using errcode='P0001',message='notification_outbox_claim_lost';
  end if;
  return inserted_count;
end;
$$;

revoke all on function public.notification_outbox_protocol() from public,anon,authenticated;
revoke all on function public.claim_notification_outbox_v2(integer,integer) from public,anon,authenticated;
revoke all on function public.finish_notification_outbox_v2(uuid,bigint,text,text,integer) from public,anon,authenticated;
revoke all on function public.resolve_notification_outbox_v3(uuid,bigint,boolean,boolean) from public,anon,authenticated;
grant execute on function public.notification_outbox_protocol() to service_role;
grant execute on function public.claim_notification_outbox_v2(integer,integer) to service_role;
grant execute on function public.finish_notification_outbox_v2(uuid,bigint,text,text,integer) to service_role;
grant execute on function public.resolve_notification_outbox_v3(uuid,bigint,boolean,boolean) to service_role;

-- Dedicated cancellation authority for the retained deletion workflow.147
-- removed direct delivery UPDATE and149 removes outbox UPDATE; do not restore
-- blanket privileges merely to let this authorized maintenance step work.
create function public.stop_deletion_notification_work(
  p_request_id uuid,p_lease_owner text,p_claim_attempt integer
) returns integer language plpgsql security definer set search_path='' as $$
declare
  request public.data_deletion_requests;
  stopped integer:=0;
  changed integer;
begin
  select * into request from public.data_deletion_requests where id=p_request_id for update;
  if not found or request.state<>'in_progress' or p_lease_owner is null
     or request.lease_owner is distinct from p_lease_owner
     or p_claim_attempt is null or p_claim_attempt<=0 or request.attempt_count<>p_claim_attempt
     or request.lease_until is null or request.lease_until<=clock_timestamp() then
    raise exception using errcode='P0001',message='deletion_notification_authority_lost';
  end if;
  if (request.request_type='user' and not exists(
        select 1 from public.users where id=request.target_user_id_snapshot and account_status='deletion_pending'))
     or (request.request_type='tenant' and not exists(
        select 1 from public.tenants where tenant_id=request.target_tenant_id_snapshot and lifecycle_state='deletion_pending')) then
    raise exception using errcode='P0001',message='deletion_notification_target_not_frozen';
  end if;
  update public.notification_outbox set status='dead',last_error_code='deletion_pending',
      processing_started_at=null,processing_lease_until=null
  where status in ('pending','processing','failed') and
    ((request.request_type='user' and user_id=request.target_user_id_snapshot)
      or (request.request_type='tenant' and tenant_id=request.target_tenant_id_snapshot));
  get diagnostics changed=row_count;
  stopped:=stopped+changed;
  update public.notification_deliveries set status='dead',last_error_code='deletion_pending',
      dead_at=clock_timestamp(),processing_started_at=null,processing_lease_until=null
  where status in ('pending','processing') and
    ((request.request_type='user' and user_id=request.target_user_id_snapshot)
      or (request.request_type='tenant' and tenant_id=request.target_tenant_id_snapshot));
  get diagnostics changed=row_count;
  -- Recheck after any queue-lock waits. An expired request must roll back all
  -- cancellation effects rather than complete under another worker's lease.
  if request.lease_until<=clock_timestamp() then
    raise exception using errcode='P0001',message='deletion_notification_authority_lost';
  end if;
  return stopped+changed;
end;
$$;
revoke all on function public.stop_deletion_notification_work(uuid,text,integer) from public,anon,authenticated;
grant execute on function public.stop_deletion_notification_work(uuid,text,integer) to service_role;

update public.application_schema_state set schema_version=159,applied_at=now() where contract_key = 'core';
notify pgrst,'reload schema';
commit;
