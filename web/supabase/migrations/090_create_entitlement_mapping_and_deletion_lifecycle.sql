-- Canonical entitlement decisions and durable cross-provider deletion saga.
-- Additive/expand migration. No existing tenant or user is queued for deletion.
begin;

create extension if not exists pgcrypto;

-- The application already treats trial and grace as entitlement-bearing. Make
-- the database contract match it and make every entitlement-bearing state
-- mutually exclusive for a tenant.
alter table public.tenant_subscriptions
  drop constraint if exists tenant_subscriptions_state_check;
alter table public.tenant_subscriptions
  add constraint tenant_subscriptions_state_check check (state in (
    'requested','pending_review','active','trial','grace','scheduled_change',
    'past_due','suspended','canceled','expired','review_required'
  ));
drop index if exists public.tenant_subscriptions_one_active_idx;
create unique index if not exists tenant_subscriptions_one_entitled_idx
  on public.tenant_subscriptions (tenant_id)
  where state in ('active','trial','grace');
alter table public.tenant_subscriptions add column if not exists mapping_key text;
create unique index if not exists tenant_subscriptions_mapping_key_idx
  on public.tenant_subscriptions (mapping_key) where mapping_key is not null;

create table if not exists public.tenant_entitlement_decisions (
  tenant_id integer primary key references public.tenants(tenant_id) on delete cascade,
  target_state text not null,
  plan_id text,
  grace_until timestamptz,
  grandfather_reason text,
  approved_by text not null,
  approved_at timestamptz not null,
  notes text,
  mapping_id text not null unique,
  applied_subscription_id bigint references public.tenant_subscriptions(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint tenant_entitlement_decisions_state_check check (
    target_state in ('active','trial','grace','grandfathered','inactive')
  ),
  constraint tenant_entitlement_decisions_plan_check check (
    (target_state = 'inactive' and plan_id is null)
    or (target_state <> 'inactive' and plan_id in ('forms','website','business','business_plus'))
  ),
  constraint tenant_entitlement_decisions_grace_check check (
    target_state not in ('grace','grandfathered') or grace_until is not null
  ),
  constraint tenant_entitlement_decisions_grandfather_check check (
    target_state <> 'grandfathered' or nullif(btrim(grandfather_reason),'') is not null
  )
);
drop trigger if exists set_tenant_entitlement_decisions_updated_at on public.tenant_entitlement_decisions;
create trigger set_tenant_entitlement_decisions_updated_at before update on public.tenant_entitlement_decisions
for each row execute function public.set_updated_at();
alter table public.tenant_entitlement_decisions enable row level security;
revoke all on public.tenant_entitlement_decisions from public, anon, authenticated;
grant select, insert, update, delete on public.tenant_entitlement_decisions to service_role;

create or replace function public.apply_tenant_entitlement_mapping_batch(p_mappings jsonb)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  item jsonb;
  addon jsonb;
  v_tenant_id integer;
  v_state text;
  v_db_state text;
  v_plan text;
  v_mapping_id text;
  v_subscription_id bigint;
  v_price integer;
  v_count integer := 0;
begin
  if jsonb_typeof(p_mappings) <> 'array' or jsonb_array_length(p_mappings) = 0 then
    raise exception using errcode='22023', message='entitlement_mapping_invalid';
  end if;
  if jsonb_array_length(p_mappings) <> (select count(*) from public.tenants) then
    raise exception using errcode='P0001', message='entitlement_mapping_incomplete';
  end if;
  if (select count(distinct (value->>'tenant_id')::integer) from jsonb_array_elements(p_mappings))
      <> jsonb_array_length(p_mappings) then
    raise exception using errcode='P0001', message='entitlement_mapping_duplicate_tenant';
  end if;

  -- Validate the whole document before the first write. The function call is a
  -- single database transaction, so any later exception rolls everything back.
  for item in select value from jsonb_array_elements(p_mappings) loop
    v_tenant_id := (item->>'tenant_id')::integer;
    v_state := lower(btrim(coalesce(item->>'target_state','')));
    v_plan := nullif(lower(btrim(coalesce(item->>'plan_id',''))),'');
    v_mapping_id := btrim(coalesce(item->>'mapping_id',''));
    if not exists (select 1 from public.tenants where tenant_id=v_tenant_id)
      or v_state not in ('active','trial','grace','grandfathered','inactive')
      or (v_state='inactive' and v_plan is not null)
      or (v_state<>'inactive' and v_plan not in ('forms','website','business','business_plus'))
      or nullif(v_mapping_id,'') is null or length(v_mapping_id)>120
      or nullif(btrim(coalesce(item->>'approved_by','')),'') is null
      or nullif(item->>'approved_at','') is null
      or (v_state in ('grace','grandfathered') and nullif(item->>'grace_until','') is null)
      or (v_state='grandfathered' and nullif(btrim(coalesce(item->>'grandfather_reason','')),'') is null)
      or jsonb_typeof(coalesce(item->'addons','[]'::jsonb)) <> 'array'
    then
      raise exception using errcode='22023', message='entitlement_mapping_record_invalid';
    end if;
    if exists (
      select 1 from jsonb_array_elements(coalesce(item->'addons','[]'::jsonb)) a
      where a->>'addon_id' not in (
        'branded_madar_subdomain','additional_storage_5gb','additional_workspace_seat',
        'workspace_seat_pack_5','ai_analytics_starter','ai_analytics_plus',
        'ai_token_pack_750k','google_drive_private','ocr','hosted_email_mailbox','custom_domain'
      ) or coalesce((a->>'quantity')::integer,0) not between 1 and 1000
    ) then
      raise exception using errcode='22023', message='entitlement_mapping_addon_invalid';
    end if;
  end loop;

  for item in select value from jsonb_array_elements(p_mappings) loop
    v_tenant_id := (item->>'tenant_id')::integer;
    v_state := lower(btrim(item->>'target_state'));
    v_plan := nullif(lower(btrim(coalesce(item->>'plan_id',''))),'');
    v_mapping_id := btrim(item->>'mapping_id');
    perform pg_advisory_xact_lock(hashtextextended('entitlement-map:'||v_tenant_id,0));

    update public.tenant_subscriptions set state='canceled', updated_at=now()
    where tenant_id=v_tenant_id and state in ('active','trial','grace')
      and mapping_key is distinct from v_mapping_id;
    update public.tenant_addons set state='canceled', updated_at=now()
    where tenant_id=v_tenant_id and state='active';

    v_subscription_id := null;
    if v_state <> 'inactive' then
      v_db_state := case when v_state='grandfathered' then 'grace' else v_state end;
      v_price := case v_plan when 'forms' then 1500 when 'website' then 2000
        when 'business' then 2500 when 'business_plus' then 3000 end;
      insert into public.tenant_subscriptions (
        tenant_id,plan_id,state,catalog_version,currency,price_minor,billing_interval,
        period_start,period_end,source,migration_provenance,mapping_key
      ) values (
        v_tenant_id,v_plan,v_db_state,'2026-07-30','USD',v_price,'month',
        now(),case when v_state in ('grace','grandfathered') then (item->>'grace_until')::timestamptz else null end,
        case when v_state='grandfathered' then 'grandfathered_mapping' else 'operator_mapping' end,
        jsonb_build_object('mapping_id',v_mapping_id,'approved_by',left(item->>'approved_by',120),
          'approved_at',item->>'approved_at','notes',left(coalesce(item->>'notes',''),1000),
          'grandfather_reason',left(coalesce(item->>'grandfather_reason',''),500)),v_mapping_id
      ) on conflict (mapping_key) where mapping_key is not null do update
        set tenant_id=excluded.tenant_id,plan_id=excluded.plan_id,state=excluded.state,
          catalog_version=excluded.catalog_version,currency=excluded.currency,
          price_minor=excluded.price_minor,billing_interval=excluded.billing_interval,
          period_start=excluded.period_start,period_end=excluded.period_end,
          source=excluded.source,migration_provenance=excluded.migration_provenance,
          updated_at=excluded.updated_at
      returning id into v_subscription_id;
    end if;

    for addon in select value from jsonb_array_elements(coalesce(item->'addons','[]'::jsonb)) loop
      insert into public.tenant_addons (
        tenant_id,addon_id,quantity,state,catalog_version,price_minor,currency,
        billing_interval,period_start,source,idempotency_key
      ) values (
        v_tenant_id,addon->>'addon_id',(addon->>'quantity')::integer,'active','2026-07-30',
        null,'USD',case when addon->>'addon_id'='ai_token_pack_750k' then 'one_time' else 'month' end,
        now(),'operator_mapping',v_mapping_id||':'||(addon->>'addon_id')
      ) on conflict (tenant_id,idempotency_key) where idempotency_key is not null do update
        set state='active',quantity=excluded.quantity,updated_at=now();
    end loop;

    insert into public.tenant_entitlement_decisions (
      tenant_id,target_state,plan_id,grace_until,grandfather_reason,approved_by,
      approved_at,notes,mapping_id,applied_subscription_id
    ) values (
      v_tenant_id,v_state,v_plan,
      case when v_state in ('grace','grandfathered') then (item->>'grace_until')::timestamptz else null end,
      nullif(left(coalesce(item->>'grandfather_reason',''),500),''),left(item->>'approved_by',120),
      (item->>'approved_at')::timestamptz,nullif(left(coalesce(item->>'notes',''),1000),''),
      v_mapping_id,v_subscription_id
    ) on conflict (tenant_id) do update set
      target_state=excluded.target_state,plan_id=excluded.plan_id,grace_until=excluded.grace_until,
      grandfather_reason=excluded.grandfather_reason,approved_by=excluded.approved_by,
      approved_at=excluded.approved_at,notes=excluded.notes,mapping_id=excluded.mapping_id,
      applied_subscription_id=excluded.applied_subscription_id,updated_at=now();
    v_count := v_count + 1;
  end loop;
  return jsonb_build_object('applied',v_count,'transactional',true);
end;
$$;
revoke all on function public.apply_tenant_entitlement_mapping_batch(jsonb) from public,anon,authenticated;
grant execute on function public.apply_tenant_entitlement_mapping_batch(jsonb) to service_role;

-- Freeze gates. Account and tenant creation remain unchanged.
alter table public.users drop constraint if exists users_account_status_check;
alter table public.users add constraint users_account_status_check check (
  account_status in ('pending_verification','active','disabled','expired_pending','deletion_pending')
);
alter table public.tenants add column if not exists lifecycle_state text not null default 'active';
alter table public.tenants add column if not exists deletion_requested_at timestamptz;
alter table public.tenants drop constraint if exists tenants_lifecycle_state_check;
alter table public.tenants add constraint tenants_lifecycle_state_check check (
  lifecycle_state in ('active','deletion_pending')
);
create index if not exists tenants_lifecycle_state_idx on public.tenants(lifecycle_state);

create table if not exists public.data_deletion_requests (
  id uuid primary key default gen_random_uuid(),
  request_type text not null check (request_type in ('user','tenant')),
  target_user_id integer references public.users(id) on delete set null,
  target_tenant_id integer references public.tenants(tenant_id) on delete set null,
  target_user_id_snapshot integer,
  target_tenant_id_snapshot integer,
  requested_by_user_id integer references public.users(id) on delete set null,
  state text not null default 'pending' check (state in (
    'pending','in_progress','waiting_retry','waiting_retention','completed',
    'completed_with_retained_records','failed_manual_intervention','cancelled_before_execution'
  )),
  current_phase text not null default 'freeze',
  attempt_count integer not null default 0 check (attempt_count >= 0),
  max_attempts integer not null default 12 check (max_attempts between 1 and 50),
  retry_after timestamptz,
  retention_until timestamptz,
  lease_owner text,
  lease_until timestamptz,
  last_error_code text,
  cancellation_requested_at timestamptz,
  verification_status text not null default 'pending' check (
    verification_status in ('pending','verified','mismatch','verified_with_retained_records')
  ),
  retained_classes jsonb not null default '[]'::jsonb check (jsonb_typeof(retained_classes)='array'),
  completion_report jsonb not null default '{}'::jsonb check (jsonb_typeof(completion_report)='object'),
  freeze_snapshot jsonb not null default '{}'::jsonb check (jsonb_typeof(freeze_snapshot)='object'),
  policy_version text not null default 'technical-v1-policy-gaps-explicit',
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  updated_at timestamptz not null default now(),
  constraint data_deletion_target_check check (
    (request_type='user' and target_user_id_snapshot is not null)
    or (request_type='tenant' and target_tenant_id_snapshot is not null)
  ),
  constraint data_deletion_error_code_check check (
    last_error_code is null or last_error_code ~ '^[a-z0-9_.-]{1,100}$'
  )
);
create unique index if not exists data_deletion_active_user_idx
  on public.data_deletion_requests(target_user_id_snapshot)
  where request_type='user' and state not in ('completed','completed_with_retained_records','failed_manual_intervention','cancelled_before_execution');
create unique index if not exists data_deletion_active_tenant_idx
  on public.data_deletion_requests(target_tenant_id_snapshot)
  where request_type='tenant' and state not in ('completed','completed_with_retained_records','failed_manual_intervention','cancelled_before_execution');
create index if not exists data_deletion_claim_idx on public.data_deletion_requests(state,retry_after,lease_until,created_at);

create table if not exists public.data_deletion_steps (
  id bigint generated by default as identity primary key,
  request_id uuid not null references public.data_deletion_requests(id) on delete cascade,
  step_key text not null,
  step_order integer not null check (step_order between 1 and 100),
  state text not null default 'pending' check (state in ('pending','processing','waiting_retry','completed','skipped','manual_intervention')),
  attempts integer not null default 0 check (attempts >= 0),
  max_attempts integer not null default 6 check (max_attempts between 1 and 20),
  last_error_code text,
  output_safe jsonb not null default '{}'::jsonb check (jsonb_typeof(output_safe)='object'),
  started_at timestamptz,
  completed_at timestamptz,
  updated_at timestamptz not null default now(),
  unique(request_id,step_key),
  unique(request_id,step_order),
  constraint data_deletion_step_key_check check (step_key ~ '^[a-z][a-z0-9_]{1,79}$'),
  constraint data_deletion_step_error_check check (last_error_code is null or last_error_code ~ '^[a-z0-9_.-]{1,100}$')
);
create index if not exists data_deletion_steps_request_state_idx on public.data_deletion_steps(request_id,state,step_order);

create table if not exists public.data_deletion_subjects (
  request_id uuid not null references public.data_deletion_requests(id) on delete cascade,
  user_id_snapshot integer not null,
  auth_id uuid,
  subject_kind text not null check (subject_kind in ('primary_user','tenant_platform_user')),
  account_status_snapshot text,
  provider_state text not null default 'pending' check (provider_state in ('pending','deleted','absent','manual_intervention')),
  last_error_code text,
  primary key(request_id,user_id_snapshot)
);

create table if not exists public.data_deletion_resources (
  id bigint generated by default as identity primary key,
  request_id uuid not null references public.data_deletion_requests(id) on delete cascade,
  resource_kind text not null check (resource_kind in ('supabase_avatar','supabase_builder_asset','host_dataset','host_generated_artifact','unknown_storage')),
  resource_key text not null,
  state text not null default 'pending' check (state in ('pending','deleted','absent','manual_intervention')),
  attempts integer not null default 0,
  last_error_code text,
  unique(request_id,resource_kind,resource_key),
  constraint data_deletion_resource_key_check check (length(resource_key) between 1 and 1024)
);

do $$ declare name text; begin
  foreach name in array array['data_deletion_requests','data_deletion_steps','data_deletion_subjects','data_deletion_resources'] loop
    execute format('alter table public.%I enable row level security',name);
    execute format('revoke all on public.%I from public,anon,authenticated',name);
    execute format('grant select,insert,update,delete on public.%I to service_role',name);
  end loop;
end $$;
drop trigger if exists set_data_deletion_requests_updated_at on public.data_deletion_requests;
create trigger set_data_deletion_requests_updated_at before update on public.data_deletion_requests
for each row execute function public.set_updated_at();

create or replace function public.create_data_deletion_request(
  p_request_type text,p_target_user_id integer,p_target_tenant_id integer,
  p_requested_by_user_id integer,p_retention_until timestamptz default null
) returns public.data_deletion_requests
language plpgsql security definer set search_path=public as $$
declare request_row public.data_deletion_requests; target_user public.users; target_tenant public.tenants;
begin
  if p_request_type='user' then
    if p_target_user_id is null or p_target_tenant_id is not null then
      raise exception using errcode='22023',message='deletion_target_invalid'; end if;
    select * into target_user from public.users where id=p_target_user_id for update;
    if not found then raise exception using errcode='P0002',message='deletion_target_not_found'; end if;
    if target_user.user_type='admin' and target_user.account_status='active' and not exists (
      select 1 from public.users other
      where other.user_type='admin' and other.account_status='active' and other.id<>target_user.id
    ) then raise exception using errcode='P0001',message='last_system_admin_required'; end if;
    if exists (
      select 1 from public.tenant_memberships m where m.user_id=target_user.id and m.role='owner' and m.status='active'
      and not exists (select 1 from public.tenant_memberships other where other.tenant_id=m.tenant_id and other.user_id<>m.user_id and other.role='owner' and other.status='active')
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
    select * into target_tenant from public.tenants where tenant_id=p_target_tenant_id for update;
    if not found then raise exception using errcode='P0002',message='deletion_target_not_found'; end if;
    if exists (select 1 from public.users where tenant_id=target_tenant.tenant_id and user_type='admin') then
      raise exception using errcode='P0001',message='admin_deletion_requires_break_glass'; end if;
    insert into public.data_deletion_requests(request_type,target_tenant_id,target_tenant_id_snapshot,requested_by_user_id,state,retry_after,retention_until,freeze_snapshot)
    values('tenant',target_tenant.tenant_id,target_tenant.tenant_id,p_requested_by_user_id,
      case when p_retention_until>now() then 'waiting_retention' else 'pending' end,
      case when p_retention_until>now() then p_retention_until else null end,p_retention_until,
      jsonb_build_object('lifecycle_state',target_tenant.lifecycle_state)) returning * into request_row;
    update public.tenants set lifecycle_state='deletion_pending',deletion_requested_at=now() where tenant_id=target_tenant.tenant_id;
    update public.users set account_status='deletion_pending' where tenant_id=target_tenant.tenant_id;
    insert into public.data_deletion_subjects(request_id,user_id_snapshot,auth_id,subject_kind,account_status_snapshot)
    select request_row.id,id,auth_id,'tenant_platform_user',account_status from public.users where tenant_id=target_tenant.tenant_id;
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

create or replace function public.claim_data_deletion_requests(
  p_worker_id text,p_limit integer default 5,p_now timestamptz default now(),p_lease_seconds integer default 300
) returns setof public.data_deletion_requests
language plpgsql security definer set search_path=public as $$
begin
  update public.data_deletion_requests set state='failed_manual_intervention',lease_owner=null,lease_until=null,
    last_error_code=coalesce(last_error_code,'deletion_attempts_exhausted')
  where state='in_progress' and lease_until<p_now and attempt_count>=max_attempts;
  return query update public.data_deletion_requests r set state='in_progress',
    started_at=coalesce(r.started_at,p_now),attempt_count=r.attempt_count+1,
    lease_owner=left(p_worker_id,120),lease_until=p_now+make_interval(secs=>greatest(30,least(p_lease_seconds,3600))),
    last_error_code=null
  where r.id in (
    select c.id from public.data_deletion_requests c
    where ((c.state in ('pending','waiting_retry','waiting_retention') and coalesce(c.retry_after,p_now)<=p_now)
      or (c.state='in_progress' and c.lease_until<p_now))
      and c.attempt_count<c.max_attempts
    order by c.created_at limit greatest(1,least(coalesce(p_limit,5),25)) for update skip locked
  ) returning r.*;
end; $$;

revoke all on function public.create_data_deletion_request(text,integer,integer,integer,timestamptz) from public,anon,authenticated;
revoke all on function public.claim_data_deletion_requests(text,integer,timestamptz,integer) from public,anon,authenticated;
grant execute on function public.create_data_deletion_request(text,integer,integer,integer,timestamptz) to service_role;
grant execute on function public.claim_data_deletion_requests(text,integer,timestamptz,integer) to service_role;

insert into public.application_schema_state(contract_key,schema_version,applied_at)
values('core',90,now()) on conflict(contract_key) do update
set schema_version=excluded.schema_version,applied_at=excluded.applied_at;

notify pgrst,'reload schema';
commit;
