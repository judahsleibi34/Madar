begin;
-- Reconciled forward migration; original architecture SQL is archived unchanged.
-- Coordinated forward-only deletion ownership protocol. No production selection.
do $$ declare v_schema_version public.application_schema_state.schema_version%TYPE; begin
  select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
  if v_schema_version is null or v_schema_version<>159 then raise exception 'migration_160_expected_schema_159'; end if;
end $$;
lock table public.data_deletion_requests,public.data_deletion_steps,
  public.data_deletion_subjects,public.data_deletion_resources in access exclusive mode;
do $$ begin
  -- Expired claims and uncertain external effects require explicit reconciliation.
  if exists(select 1 from public.data_deletion_requests where state='in_progress' or lease_owner is not null or lease_until is not null)
     or exists(select 1 from public.data_deletion_steps where state='processing') then
    raise exception 'migration_160_requires_reconciled_deletion_work';
  end if;
end $$;
alter table public.data_deletion_requests add column claim_generation bigint not null default 0 check(claim_generation>=0);
alter table public.data_deletion_steps add column claim_generation bigint not null default 0 check(claim_generation>=0),
  add column local_applied_generation bigint;
create table public.data_deletion_effects (
  request_id uuid not null references public.data_deletion_requests(id) on delete cascade,
  step_id bigint not null references public.data_deletion_steps(id) on delete cascade,
  effect_key text not null check(length(effect_key) between 1 and 160),
  claim_generation bigint not null,
  step_attempt integer not null,
  state text not null check(state in ('intent','confirmed','uncertain')),
  outcome text check(outcome in ('deleted','absent','provider_revoked','local_credentials_removed')),
  created_at timestamptz not null default clock_timestamp(),
  confirmed_at timestamptz,
  primary key(request_id,step_id,effect_key)
);
alter table public.data_deletion_effects enable row level security;
-- Runtime reads remain available for status/metrics; writes only through fixed RPCs.
do $$ declare t text; begin
  foreach t in array array['data_deletion_requests','data_deletion_steps','data_deletion_subjects','data_deletion_resources','data_deletion_effects'] loop
    execute format('revoke all on public.%I from public,anon,authenticated,service_role',t);
    execute format('grant select on public.%I to service_role',t);
  end loop;
end $$;
revoke all on function public.claim_data_deletion_requests(text,integer,timestamptz,integer) from public,anon,authenticated,service_role;
revoke all on function public.stop_deletion_notification_work(uuid,text,integer) from public,anon,authenticated,service_role;

-- Preserve original per-user freeze preimages for atomic cancellation.
create or replace function public.create_data_deletion_request(
  p_request_type text,p_target_user_id integer,p_target_tenant_id integer,
  p_requested_by_user_id integer,p_retention_until timestamptz default null
) returns public.data_deletion_requests
language plpgsql security definer set search_path='' as $$
declare request_row public.data_deletion_requests; target_user public.users; target_tenant public.tenants;
begin
  -- Enrollment is rare: serialize deletion-vs-deletion owner/freeze decisions
  -- across primary tenants and multi-tenant owner memberships.
  perform pg_advisory_xact_lock(hashtextextended('data-deletion-enrollment-150',0));
  if p_request_type='user' then
    if p_target_user_id is null or p_target_tenant_id is not null then
      raise exception using errcode='22023',message='deletion_target_invalid'; end if;
    select * into target_user from public.users where id=p_target_user_id;
    if not found then raise exception 'deletion_target_not_found'; end if;
    perform pg_advisory_xact_lock(hashtextextended('data-deletion-scope:'||coalesce(target_user.tenant_id::text,'user:'||target_user.id),0));
    select * into target_user from public.users where id=p_target_user_id for update;
    if exists(select 1 from public.data_deletion_requests where state not in ('completed','completed_with_retained_records','cancelled_before_execution') and
      ((request_type='user' and target_user_id_snapshot=p_target_user_id) or
       (request_type='tenant' and target_tenant_id_snapshot=target_user.tenant_id))) then raise exception 'deletion_scope_already_requested'; end if;
    if p_requested_by_user_id is distinct from p_target_user_id and not exists(select 1 from public.users where id=p_requested_by_user_id and user_type='admin' and account_status='active') then raise exception 'deletion_request_unauthorized'; end if;
    if not found then raise exception using errcode='P0002',message='deletion_target_not_found'; end if;
    if target_user.user_type='admin' and target_user.account_status='active' and not exists (
      select 1 from public.users other
      where other.user_type='admin' and other.account_status='active' and other.id<>target_user.id
    ) then raise exception using errcode='P0001',message='last_system_admin_required'; end if;
    if exists (
      select 1 from public.tenant_memberships m where m.user_id=target_user.id and m.role='owner' and m.status='active'
      and not exists (select 1 from public.tenant_memberships other where other.tenant_id=m.tenant_id and other.user_id<>m.user_id and other.role='owner' and other.status='active'
        and exists(select 1 from public.users remaining where remaining.id=other.user_id and remaining.account_status='active')
        and not exists(select 1 from public.data_deletion_requests pending where pending.target_user_id_snapshot=other.user_id and pending.state not in ('completed','completed_with_retained_records','cancelled_before_execution')))
    ) then raise exception using errcode='P0001',message='tenant_owner_requires_tenant_deletion'; end if;
    insert into public.data_deletion_requests(request_type,target_user_id,target_user_id_snapshot,target_tenant_id_snapshot,requested_by_user_id,state,retry_after,retention_until,freeze_snapshot)
    values('user',target_user.id,target_user.id,target_user.tenant_id,p_requested_by_user_id,
      case when p_retention_until>now() then 'waiting_retention' else 'pending' end,
      case when p_retention_until>now() then p_retention_until else null end,p_retention_until,
      jsonb_build_object('account_status',target_user.account_status)) returning * into request_row;
    update public.users set account_status='deletion_pending' where id=target_user.id;
    insert into public.data_deletion_subjects(request_id,user_id_snapshot,auth_id,subject_kind,account_status_snapshot)
    values(request_row.id,target_user.id,target_user.auth_id,'primary_user',target_user.account_status);
  elsif p_request_type='tenant' then
    if p_target_tenant_id is null or p_target_user_id is not null then
      raise exception using errcode='22023',message='deletion_target_invalid'; end if;
    perform pg_advisory_xact_lock(hashtextextended('data-deletion-scope:'||p_target_tenant_id,0));
    select * into target_tenant from public.tenants where tenant_id=p_target_tenant_id for update;
    if exists(select 1 from public.data_deletion_requests where target_tenant_id_snapshot=p_target_tenant_id and state not in ('completed','completed_with_retained_records','cancelled_before_execution')) then raise exception 'deletion_scope_already_requested'; end if;
    if not exists(select 1 from public.users where id=p_requested_by_user_id and account_status='active' and user_type='admin') and not exists(
      select 1 from public.tenant_memberships m join public.users u on u.id=m.user_id where m.tenant_id=p_target_tenant_id and m.user_id=p_requested_by_user_id and m.role='owner' and m.status='active' and u.account_status='active') then raise exception 'deletion_request_unauthorized'; end if;
    if not found then raise exception using errcode='P0002',message='deletion_target_not_found'; end if;
    if exists (select 1 from public.users where tenant_id=target_tenant.tenant_id and user_type='admin') then
      raise exception using errcode='P0001',message='admin_deletion_requires_break_glass'; end if;
    insert into public.data_deletion_requests(request_type,target_tenant_id,target_tenant_id_snapshot,requested_by_user_id,state,retry_after,retention_until,freeze_snapshot)
    values('tenant',target_tenant.tenant_id,target_tenant.tenant_id,p_requested_by_user_id,
      case when p_retention_until>now() then 'waiting_retention' else 'pending' end,
      case when p_retention_until>now() then p_retention_until else null end,p_retention_until,
      jsonb_build_object('lifecycle_state',target_tenant.lifecycle_state)) returning * into request_row;
    update public.tenants set lifecycle_state='deletion_pending',deletion_requested_at=now() where tenant_id=target_tenant.tenant_id;
    insert into public.data_deletion_subjects(request_id,user_id_snapshot,auth_id,subject_kind,account_status_snapshot)
    select request_row.id,id,auth_id,'tenant_platform_user',account_status from public.users where tenant_id=target_tenant.tenant_id;
    update public.users set account_status='deletion_pending' where tenant_id=target_tenant.tenant_id;
  else raise exception using errcode='22023',message='deletion_request_type_invalid';
  end if;

  insert into public.data_deletion_steps(request_id,step_key,step_order,max_attempts) values
    (request_row.id,'freeze',10,1),(request_row.id,'revoke_sessions',20,6),
    (request_row.id,'revoke_integrations',30,8),(request_row.id,'stop_queued_work',40,4),
    (request_row.id,'delete_provider_objects',50,8),(request_row.id,'delete_host_files',60,8),
    (request_row.id,'delete_application_data',70,4),(request_row.id,'delete_auth_identities',80,8),
    (request_row.id,'verify',90,8),(request_row.id,'finalize',100,2);

  insert into public.data_deletion_resources(request_id,resource_kind,resource_key)
  select request_row.id,
    case category when 'avatar' then 'supabase_avatar' when 'builder_asset' then 'supabase_builder_asset'
      when 'dataset' then 'host_dataset' when 'generated_artifact' then 'host_generated_artifact' else 'unknown_storage' end,
    storage_key from public.storage_objects
  where status='active' and (
    (p_request_type='tenant' and tenant_id=p_target_tenant_id)
    or (p_request_type='user' and user_id=p_target_user_id)
  ) on conflict do nothing;
  if p_request_type='tenant' then
    insert into public.data_deletion_resources(request_id,resource_kind,resource_key)
    select request_row.id,'supabase_builder_asset',storage_key from public.builder_assets
    where tenant_id=p_target_tenant_id and deleted_at is null on conflict do nothing;
  else
    insert into public.data_deletion_resources(request_id,resource_kind,resource_key)
    select request_row.id,'supabase_builder_asset',storage_key from public.builder_assets
    where uploader_user_id=p_target_user_id and deleted_at is null on conflict do nothing;
  end if;
  return request_row;
end; $$;


-- All helpers lock request BEFORE step/effect/resource. They are owner-only.
create function public.deletion_owned_150(p_id uuid,p_owner text,p_generation bigint,p_attempt integer)
returns public.data_deletion_requests language plpgsql security definer set search_path='' as $$
declare r public.data_deletion_requests;
begin
  select * into r from public.data_deletion_requests where id=p_id for update;
  if not found or r.state<>'in_progress' or p_owner is null or p_owner='' or r.lease_owner is distinct from p_owner
    or p_generation is null or p_generation<=0 or r.claim_generation<>p_generation
    or p_attempt is null or p_attempt<=0 or r.attempt_count<>p_attempt
    or r.lease_until is null or r.lease_until<=clock_timestamp() then raise exception 'deletion_claim_lost'; end if;
  return r;
end $$;
create function public.deletion_step_owned_150(p_id uuid,p_generation bigint,p_step bigint,p_step_attempt integer)
returns public.data_deletion_steps language plpgsql security definer set search_path='' as $$
declare s public.data_deletion_steps;
begin
  select * into s from public.data_deletion_steps where id=p_step and request_id=p_id for update;
  if not found or s.state<>'processing' or s.claim_generation is distinct from p_generation
     or p_step_attempt is null or s.attempts<>p_step_attempt then raise exception 'deletion_step_claim_lost'; end if;
  return s;
end $$;
create function public.claim_data_deletion_requests_v2(p_worker_id text,p_limit integer default 5,p_lease_seconds integer default 300)
returns setof public.data_deletion_requests language plpgsql security definer set search_path='' as $$
declare r public.data_deletion_requests; v_now timestamptz;
begin
  if p_worker_id is null or length(p_worker_id) not between 1 and 120 or p_lease_seconds is null or p_lease_seconds not between 30 and 3600 then raise exception 'deletion_claim_invalid'; end if;
  for r in select * from public.data_deletion_requests q
    where (q.state in ('pending','waiting_retry','waiting_retention') and coalesce(q.retry_after,'-infinity')<=clock_timestamp())
       or (q.state='in_progress' and q.lease_until<=clock_timestamp())
    order by q.created_at,q.id limit greatest(1,least(coalesce(p_limit,5),25)) for update skip locked
  loop
    v_now:=clock_timestamp();
    if r.attempt_count>=r.max_attempts or exists(select 1 from public.data_deletion_effects where request_id=r.id and state in ('intent','uncertain')) then
      update public.data_deletion_requests set state='failed_manual_intervention',lease_owner=null,lease_until=null,
        claim_generation=claim_generation+1,last_error_code=case when r.attempt_count>=r.max_attempts then 'deletion_attempts_exhausted' else 'deletion_external_outcome_uncertain' end where id=r.id;
      update public.data_deletion_steps set state='manual_intervention',last_error_code='deletion_external_outcome_uncertain' where request_id=r.id and state='processing';
      continue;
    end if;
    update public.data_deletion_requests set state='in_progress',started_at=coalesce(started_at,v_now),attempt_count=attempt_count+1,
      claim_generation=claim_generation+1,lease_owner=p_worker_id,lease_until=v_now+make_interval(secs=>p_lease_seconds),last_error_code=null
      where id=r.id returning * into r;
    return next r;
  end loop;
end $$;

-- One narrow state-transition API. No arbitrary table names/columns/SQL supplied.
create function public.transition_data_deletion_v2(
  p_request_id uuid,p_owner text,p_generation bigint,p_attempt integer,p_action text,
  p_step_id bigint default null,p_step_attempt integer default null,p_data jsonb default '{}'::jsonb
) returns jsonb language plpgsql security definer set search_path='' as $$
declare r public.data_deletion_requests; s public.data_deletion_steps; v_now timestamptz; terminal boolean; result jsonb;
begin
  r:=public.deletion_owned_150(p_request_id,p_owner,p_generation,p_attempt);
  if jsonb_typeof(p_data) is distinct from 'object' or octet_length(p_data::text)>32768 then raise exception 'deletion_transition_invalid'; end if;
  if p_action='renew' then
    update public.data_deletion_requests set lease_until=clock_timestamp()+interval '5 minutes' where id=r.id returning to_jsonb(data_deletion_requests.*) into result;
  elsif p_action='begin' then
    select * into s from public.data_deletion_steps where request_id=r.id and state not in ('completed','skipped') order by step_order limit 1 for update;
    if not found or s.state='manual_intervention' then raise exception 'deletion_step_plan_incomplete'; end if;
    if s.state='processing' and s.claim_generation=r.claim_generation then
      result:=to_jsonb(s); -- Idempotent acknowledgement of an already committed begin.
    elsif s.attempts>=s.max_attempts and not (s.state='processing' and s.claim_generation<>r.claim_generation
      and s.step_key in ('freeze','revoke_sessions','stop_queued_work','delete_application_data')) then
      update public.data_deletion_steps set state='manual_intervention',last_error_code='deletion_step_attempts_exhausted' where id=s.id;
      update public.data_deletion_requests set state='failed_manual_intervention',last_error_code='deletion_step_attempts_exhausted',lease_owner=null,lease_until=null where id=r.id;
      result:=jsonb_build_object('blocked',true);
    else
      update public.data_deletion_steps set state='processing',attempts=attempts+1,claim_generation=r.claim_generation,
        started_at=coalesce(started_at,clock_timestamp()),last_error_code=null where id=s.id returning to_jsonb(data_deletion_steps.*) into result;
      update public.data_deletion_requests set current_phase=s.step_key where id=r.id;
    end if;
  else
    s:=public.deletion_step_owned_150(r.id,r.claim_generation,p_step_id,p_step_attempt);
    if p_action='complete' then
      if exists(select 1 from public.data_deletion_effects where request_id=r.id and step_id=s.id and state<>'confirmed') then raise exception 'deletion_external_outcome_uncertain'; end if;
      if s.step_key in ('freeze','revoke_sessions','stop_queued_work','delete_application_data')
        and s.local_applied_generation is distinct from r.claim_generation then raise exception 'deletion_local_step_not_applied'; end if;
      if (s.step_key='delete_provider_objects' and exists(select 1 from public.data_deletion_resources where request_id=r.id and resource_kind in ('supabase_avatar','supabase_builder_asset') and state not in ('deleted','absent')))
        or (s.step_key='delete_host_files' and exists(select 1 from public.data_deletion_resources where request_id=r.id and resource_kind in ('host_dataset','host_generated_artifact','unknown_storage') and state not in ('deleted','absent')))
        or (s.step_key='delete_auth_identities' and exists(select 1 from public.data_deletion_subjects where request_id=r.id and provider_state not in ('deleted','absent')))
        or (s.step_key='revoke_integrations' and exists(select 1 from public.calendar_sync_connections where
          ((r.request_type='tenant' and tenant_id=r.target_tenant_id_snapshot) or (r.request_type='user' and user_id=r.target_user_id_snapshot))
          and (status<>'disconnected' or encrypted_credentials is not null))) then raise exception 'deletion_required_effects_unconfirmed'; end if;
      -- External absence checks are recorded only under the original live claim.
      if s.step_key='verify' then
        if p_data->'verified' is distinct from 'true'::jsonb
          or exists(select 1 from public.data_deletion_resources where request_id=r.id and state not in ('deleted','absent'))
          or exists(select 1 from public.data_deletion_subjects where request_id=r.id and provider_state not in ('deleted','absent'))
          or (r.request_type='user' and exists(select 1 from public.users where id=r.target_user_id_snapshot))
          or (r.request_type='tenant' and exists(select 1 from public.tenants where tenant_id=r.target_tenant_id_snapshot)) then raise exception 'deletion_verification_required'; end if;
        update public.data_deletion_requests set verification_status='verified_with_retained_records',
          retained_classes=case when r.request_type='tenant' then '["security_audit_metadata","billing_webhook_replay_metadata","deletion_workflow_evidence"]'::jsonb else '["security_audit_metadata","deletion_workflow_evidence"]'::jsonb end,
          completion_report=p_data where id=r.id;
      elsif s.step_key='finalize' then
        if r.verification_status not in ('verified','verified_with_retained_records') or exists(select 1 from public.data_deletion_steps where request_id=r.id and id<>s.id and state not in ('completed','skipped'))
          or (select jsonb_agg(jsonb_build_array(step_key,step_order) order by step_order) from public.data_deletion_steps where request_id=r.id) is distinct from
          '[["freeze",10],["revoke_sessions",20],["revoke_integrations",30],["stop_queued_work",40],["delete_provider_objects",50],["delete_host_files",60],["delete_application_data",70],["delete_auth_identities",80],["verify",90],["finalize",100]]'::jsonb
          then raise exception 'deletion_verification_required'; end if;
        update public.data_deletion_requests set state=case when jsonb_array_length(retained_classes)>0 then 'completed_with_retained_records' else 'completed' end,
          current_phase='completed',completed_at=clock_timestamp(),lease_owner=null,lease_until=null,retry_after=null,last_error_code=null where id=r.id;
      end if;
      update public.data_deletion_steps set state='completed',completed_at=clock_timestamp(),last_error_code=null,output_safe=p_data where id=s.id;
    elsif p_action='fail' then
      if coalesce(p_data->>'code','') !~ '^[a-z0-9_.-]{1,100}$' then raise exception 'deletion_failure_code_invalid'; end if;
      terminal:=p_data->'retryable' is distinct from 'true'::jsonb or s.attempts>=s.max_attempts or r.attempt_count>=r.max_attempts
        or exists(select 1 from public.data_deletion_effects where request_id=r.id and state in ('intent','uncertain'));
      update public.data_deletion_steps set state=case when terminal then 'manual_intervention' else 'waiting_retry' end,last_error_code=p_data->>'code' where id=s.id;
      update public.data_deletion_requests set state=case when terminal then 'failed_manual_intervention' else 'waiting_retry' end,
        retry_after=case when terminal then null else clock_timestamp()+make_interval(secs=>least(3600,30*(2^least(s.attempts-1,7))::integer)) end,
        lease_owner=null,lease_until=null,last_error_code=p_data->>'code',
        verification_status=case when p_data->>'code'='deletion_verification_mismatch' then 'mismatch' else verification_status end where id=r.id;
    else raise exception 'deletion_transition_invalid'; end if;
    result:=jsonb_build_object('accepted',true);
  end if;
  -- The lock may have waited for step/effect/business rows: sample DB time again.
  if r.lease_until<=clock_timestamp() then raise exception 'deletion_claim_lost'; end if;
  return result;
end $$;

create function public.run_data_deletion_local_step_v2(
  p_request_id uuid,p_owner text,p_generation bigint,p_attempt integer,p_step_id bigint,p_step_attempt integer
) returns jsonb language plpgsql security definer set search_path='' as $$
declare r public.data_deletion_requests; s public.data_deletion_steps; n integer:=0;
begin
  r:=public.deletion_owned_150(p_request_id,p_owner,p_generation,p_attempt);
  s:=public.deletion_step_owned_150(r.id,r.claim_generation,p_step_id,p_step_attempt);
  if s.step_key in ('freeze','revoke_sessions') then
    -- create_data_deletion_request atomically froze the subject already.
    if (r.request_type='user' and exists(select 1 from public.users where id=r.target_user_id_snapshot and account_status<>'deletion_pending'))
      or (r.request_type='tenant' and exists(select 1 from public.tenants where tenant_id=r.target_tenant_id_snapshot and lifecycle_state<>'deletion_pending')) then raise exception 'deletion_target_not_frozen'; end if;
  elsif s.step_key='stop_queued_work' then
    n:=public.stop_deletion_notification_work(r.id,r.lease_owner,r.attempt_count);
    update public.calendar_task_sync_jobs j set status='failed',last_error_code='deletion_pending',completed_at=clock_timestamp()
      where status in ('pending','processing') and ((r.request_type='tenant' and j.tenant_id=r.target_tenant_id_snapshot) or
       (r.request_type='user' and j.connection_id in (select id from public.calendar_sync_connections where user_id=r.target_user_id_snapshot)));
    update public.calendar_connection_sync_jobs j set status='failed',last_error_code='deletion_pending',completed_at=clock_timestamp()
      where status in ('pending','processing') and ((r.request_type='tenant' and j.tenant_id=r.target_tenant_id_snapshot) or
       (r.request_type='user' and j.connection_id in (select id from public.calendar_sync_connections where user_id=r.target_user_id_snapshot)));
  elsif s.step_key='delete_application_data' then
    if r.request_type='tenant' then
      if exists(select 1 from public.users u join public.data_deletion_subjects x on x.user_id_snapshot=u.id where x.request_id=r.id and u.tenant_id is distinct from r.target_tenant_id_snapshot) then raise exception 'deletion_subject_scope_changed'; end if;
      delete from public.users where id in(select user_id_snapshot from public.data_deletion_subjects where request_id=r.id);
      delete from public.tenants where tenant_id=r.target_tenant_id_snapshot;
    else delete from public.users where id=r.target_user_id_snapshot; end if;
  else raise exception 'deletion_local_step_invalid'; end if;
  update public.data_deletion_steps set local_applied_generation=r.claim_generation where id=s.id;
  if r.lease_until<=clock_timestamp() then raise exception 'deletion_claim_lost'; end if;
  return jsonb_build_object('applied',true,'queued_records_stopped',n);
end $$;

-- Durable external intent. Re-entry of an unconfirmed intent requires reviewed
-- reconciliation; never automatically repeat a potentially accepted operation.
create function public.data_deletion_effect_v2(
  p_request_id uuid,p_owner text,p_generation bigint,p_attempt integer,p_step_id bigint,p_step_attempt integer,
  p_kind text,p_target text,p_action text,p_outcome text default null
) returns jsonb language plpgsql security definer set search_path='' as $$
declare r public.data_deletion_requests; s public.data_deletion_steps; e public.data_deletion_effects;
  resource public.data_deletion_resources; subject public.data_deletion_subjects;
  connection public.calendar_sync_connections; accounted public.storage_objects; k text; result jsonb;
begin
  r:=public.deletion_owned_150(p_request_id,p_owner,p_generation,p_attempt);
  s:=public.deletion_step_owned_150(r.id,r.claim_generation,p_step_id,p_step_attempt);

  if p_kind='resource' and s.step_key in ('delete_provider_objects','delete_host_files') then
    select * into resource from public.data_deletion_resources where id=p_target::bigint and request_id=r.id for update;
    if not found or (s.step_key='delete_provider_objects' and resource.resource_kind not in ('supabase_avatar','supabase_builder_asset'))
      or (s.step_key='delete_host_files' and resource.resource_kind not in ('host_dataset','host_generated_artifact')) then raise exception 'deletion_effect_scope_invalid'; end if;
    -- A reused live key must never authorize deleting a different tenant/user's object.
    if exists(select 1 from public.storage_objects o where o.storage_key=resource.resource_key and
      ((r.request_type='tenant' and o.tenant_id is distinct from r.target_tenant_id_snapshot) or
       (r.request_type='user' and o.user_id is distinct from r.target_user_id_snapshot))) then raise exception 'deletion_effect_scope_changed'; end if;
    if exists(select 1 from public.builder_assets b where b.storage_key=resource.resource_key and
       ((r.request_type='tenant' and b.tenant_id is distinct from r.target_tenant_id_snapshot) or
        (r.request_type='user' and b.uploader_user_id is distinct from r.target_user_id_snapshot))) then raise exception 'deletion_effect_scope_changed'; end if;
    if resource.resource_kind in ('host_dataset','host_generated_artifact') and
       (resource.resource_key !~ '^tenant_[1-9][0-9]*/user_[1-9][0-9]*/[A-Za-z0-9_.-]+$'
        or split_part(resource.resource_key,'/',1) is distinct from 'tenant_'||r.target_tenant_id_snapshot
        or (r.request_type='user' and split_part(resource.resource_key,'/',2) is distinct from 'user_'||r.target_user_id_snapshot)) then raise exception 'deletion_effect_scope_invalid'; end if;
    if resource.resource_kind='supabase_builder_asset' and split_part(resource.resource_key,'/',1) is distinct from 'tenant_'||r.target_tenant_id_snapshot then raise exception 'deletion_effect_scope_invalid'; end if;
    if resource.resource_kind='supabase_avatar' and
      (split_part(resource.resource_key,'/',1)<>'users' or not exists(select 1 from public.data_deletion_subjects x
        where x.request_id=r.id and x.auth_id::text=split_part(resource.resource_key,'/',2))) then raise exception 'deletion_effect_scope_invalid'; end if;
    if resource.resource_kind='supabase_builder_asset' and exists(
      select 1 from public.builder_assets b join public.builder_asset_references ref on ref.asset_id=b.id
        join public.builder_projects project on project.id=ref.project_id where b.storage_key=resource.resource_key
        and (r.request_type='user' or project.tenant_id is distinct from r.target_tenant_id_snapshot)) then
      raise exception 'deletion_shared_asset_requires_review'; end if;
    k:='resource:'||resource.id;
    result:=to_jsonb(resource);
  elsif p_kind='subject' and s.step_key='delete_auth_identities' then
    select * into subject from public.data_deletion_subjects where request_id=r.id and user_id_snapshot=p_target::integer for update;
    if not found then raise exception 'deletion_effect_scope_invalid'; end if;
    k:='subject:'||subject.user_id_snapshot;
    result:=to_jsonb(subject);
  elsif p_kind='connection' and s.step_key='revoke_integrations' then
    select * into connection from public.calendar_sync_connections where id=p_target::uuid and
      ((r.request_type='tenant' and tenant_id=r.target_tenant_id_snapshot) or (r.request_type='user' and user_id=r.target_user_id_snapshot)) for update;
    if not found then raise exception 'deletion_effect_scope_invalid'; end if;
    k:='connection:'||connection.id;
    result:=to_jsonb(connection);
  else raise exception 'deletion_effect_scope_invalid'; end if;
  select * into e from public.data_deletion_effects where request_id=r.id and step_id=s.id and effect_key=k for update;
  if p_action='intent' then
    if found then
      if e.state='confirmed' then
        if r.lease_until<=clock_timestamp() then raise exception 'deletion_claim_lost'; end if;
        return jsonb_build_object('already_confirmed',true,'outcome',e.outcome); end if;
      raise exception 'deletion_external_outcome_uncertain';
    end if;
    if r.lease_until<=clock_timestamp()+interval '30 seconds' then raise exception 'deletion_lease_too_short'; end if;
    insert into public.data_deletion_effects(request_id,step_id,effect_key,claim_generation,step_attempt,state)
      values(r.id,s.id,k,r.claim_generation,s.attempts,'intent');
    result:=jsonb_build_object('target',result,'idempotency_key',r.id||':'||s.id||':'||k);
  elsif p_action='confirm' then
    if not found or e.state<>'intent' or e.claim_generation<>r.claim_generation or e.step_attempt<>s.attempts then raise exception 'deletion_effect_claim_lost'; end if;
    if p_kind in ('resource','subject') and p_outcome in ('deleted','absent') then
      if p_kind='resource' then
        -- Confirm deletion and metering/registry cleanup in the SAME fenced
        -- transaction. The retained release RPC is idempotent under row locks.
        for accounted in select * from public.storage_objects o where o.storage_key=resource.resource_key and o.status='active' and
          ((r.request_type='tenant' and o.tenant_id=r.target_tenant_id_snapshot) or
           (r.request_type='user' and o.user_id=r.target_user_id_snapshot)) order by o.id for update loop
          perform public.release_storage_object(accounted.tenant_id,accounted.category,accounted.storage_key);
        end loop;
        if resource.resource_kind='supabase_builder_asset' then
          update public.builder_assets set status='soft_deleted',deleted_at=clock_timestamp(),reference_count=0 where storage_key=resource.resource_key and
            ((r.request_type='tenant' and tenant_id=r.target_tenant_id_snapshot) or (r.request_type='user' and uploader_user_id=r.target_user_id_snapshot));
        end if;
        update public.data_deletion_resources set state=p_outcome,attempts=attempts+1,last_error_code=null where id=resource.id;
      else update public.data_deletion_subjects set provider_state=p_outcome,last_error_code=null where request_id=r.id and user_id_snapshot=subject.user_id_snapshot; end if;
    elsif p_kind='connection' and p_outcome in ('provider_revoked','local_credentials_removed') then
      update public.calendar_sync_connections set status='disconnected',encrypted_credentials=null,cursor_data='{}',last_error_code=null,inbound_sync_enabled=false where id=connection.id;
    else raise exception 'deletion_effect_outcome_invalid'; end if;
    update public.data_deletion_effects set state='confirmed',outcome=p_outcome,confirmed_at=clock_timestamp() where request_id=r.id and step_id=s.id and effect_key=k;
    result:=jsonb_build_object('accepted',true);
  else raise exception 'deletion_effect_action_invalid'; end if;
  if r.lease_until<=clock_timestamp() then raise exception 'deletion_claim_lost'; end if;
  return result;
end $$;

create function public.cancel_data_deletion_request_v2(p_request_id uuid)
returns public.data_deletion_requests language plpgsql security definer set search_path='' as $$
declare r public.data_deletion_requests;
begin
  select * into r from public.data_deletion_requests where id=p_request_id for update;
  if not found then raise exception 'deletion_target_not_found'; end if;
  if r.state not in ('pending','waiting_retention') or r.attempt_count<>0
    or exists(select 1 from public.data_deletion_steps where request_id=r.id and (state<>'pending' or attempts<>0))
    or exists(select 1 from public.data_deletion_effects where request_id=r.id) then raise exception 'deletion_cannot_be_cancelled'; end if;
  if r.request_type='tenant' then
    update public.tenants set lifecycle_state=case when r.freeze_snapshot->>'lifecycle_state'='active' then 'active' else 'deletion_pending' end,deletion_requested_at=null where tenant_id=r.target_tenant_id and lifecycle_state='deletion_pending';
  end if;
  update public.users u set account_status=case when x.account_status_snapshot in ('pending_verification','active','disabled','expired_pending') then x.account_status_snapshot else 'disabled' end
    from public.data_deletion_subjects x where x.request_id=r.id and u.id=x.user_id_snapshot and u.account_status='deletion_pending';
  update public.data_deletion_requests set state='cancelled_before_execution',cancellation_requested_at=clock_timestamp(),lease_owner=null,lease_until=null where id=r.id returning * into r;
  return r;
end $$;

create function public.data_deletion_ownership_protocol() returns integer language sql stable security definer set search_path='' as $$ select case when (select schema_version from public.application_schema_state where contract_key = 'core')=160 then 2 else 0 end $$;
do $$ declare f regprocedure; begin
  for f in select p.oid::regprocedure from pg_proc p join pg_namespace n on p.pronamespace=n.oid where n.nspname='public' and p.proname in
    ('deletion_owned_150','deletion_step_owned_150','claim_data_deletion_requests_v2','transition_data_deletion_v2','run_data_deletion_local_step_v2','data_deletion_effect_v2','cancel_data_deletion_request_v2','data_deletion_ownership_protocol') loop
    execute format('revoke all on function %s from public,anon,authenticated,service_role',f);
    if f::text not like 'deletion_owned_150(%' and f::text not like 'deletion_step_owned_150(%' then execute format('grant execute on function %s to service_role',f); end if;
  end loop;
end $$;
revoke all on function public.deletion_owned_150(uuid,text,bigint,integer),public.deletion_step_owned_150(uuid,bigint,bigint,integer) from public,anon,authenticated,service_role;
update public.application_schema_state set schema_version=160,applied_at=clock_timestamp() where contract_key = 'core';
notify pgrst,'reload schema';
commit;
