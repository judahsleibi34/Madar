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
    raise exception using errcode = 'P0001', message = 'migration_156_schema_state_missing';
  end if;
  if v_schema_version <> 155 then
    raise exception using errcode = 'P0001',
      message = format('migration_156_expected_schema_155_got_%s', v_schema_version);
  end if;
end;
$$;

do $$
begin
  if exists(
    select 1 from public.data_source_ingestion_runs
    where ingestion_kind = 'incremental' and status = 'processing'
    group by source_resource_id having count(*) > 1
  ) then
    raise exception using errcode = 'P0001', message = 'migration_156_overlapping_incremental_runs';
  end if;
end;
$$;

create unique index data_source_ingestion_one_active_resource156
on public.data_source_ingestion_runs(source_resource_id)
where ingestion_kind = 'incremental' and status = 'processing';

create table public.data_source_sync_schedules (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  project_id uuid not null,
  source_id uuid not null,
  source_resource_id uuid not null,
  enabled boolean not null default false,
  interval_seconds integer not null default 3600,
  next_due_at timestamptz,
  last_attempt_at timestamptz,
  last_success_at timestamptz,
  status text not null default 'disabled',
  retry_count integer not null default 0,
  last_error_category text,
  diagnostic_metadata jsonb not null default '{}'::jsonb,
  credential_revision bigint not null default 0,
  lease_token uuid,
  lease_owner text,
  lease_expires_at timestamptz,
  fence bigint not null default 0,
  ingestion_run_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint data_source_sync_schedules_resource_fk156
    foreign key(source_resource_id, tenant_id, project_id, source_id)
    references public.data_source_resources(id, tenant_id, project_id, source_id)
    on delete restrict,
  constraint data_source_sync_schedules_run_fk156
    foreign key(ingestion_run_id) references public.data_source_ingestion_runs(id)
    on delete restrict,
  constraint data_source_sync_schedules_identity_unique156 unique(source_resource_id),
  constraint data_source_sync_schedules_scope_unique156
    unique(id, tenant_id, project_id, source_id, source_resource_id),
  constraint data_source_sync_schedules_interval_check156
    check(interval_seconds between 900 and 604800),
  constraint data_source_sync_schedules_status_check156
    check(status in ('disabled','idle','leased','backoff','credential_attention','permanent_failure')),
  constraint data_source_sync_schedules_retry_check156 check(retry_count between 0 and 8),
  constraint data_source_sync_schedules_error_check156
    check(last_error_category is null or last_error_category ~ '^[a-z][a-z0-9_]{1,79}$'),
  constraint data_source_sync_schedules_diagnostic_check156 check(
    jsonb_typeof(diagnostic_metadata) = 'object'
    and not diagnostic_metadata ?| array['credential','token','secret','authorization','headers','url']
  ),
  constraint data_source_sync_schedules_credential_check156 check(credential_revision >= 0),
  constraint data_source_sync_schedules_fence_check156 check(fence >= 0),
  constraint data_source_sync_schedules_state_check156 check(
    (status = 'leased' and enabled and lease_token is not null and lease_owner is not null
      and lease_expires_at is not null)
    or
    (status <> 'leased' and lease_token is null and lease_owner is null
      and lease_expires_at is null and ingestion_run_id is null)
  ),
  constraint data_source_sync_schedules_enabled_check156 check(
    (enabled and status <> 'disabled') or (not enabled and status = 'disabled')
  )
);

create index data_source_sync_schedules_due156
on public.data_source_sync_schedules(next_due_at, tenant_id, source_id)
where enabled and status in ('idle','backoff','credential_attention','permanent_failure');

create index data_source_sync_schedules_leases156
on public.data_source_sync_schedules(lease_expires_at)
where status = 'leased';

create trigger set_data_source_sync_schedules_updated_at156
before update on public.data_source_sync_schedules
for each row execute function public.set_updated_at();

create table public.data_source_sync_attempts (
  id uuid primary key default gen_random_uuid(),
  schedule_id uuid not null references public.data_source_sync_schedules(id) on delete restrict,
  tenant_id integer not null,
  project_id uuid not null,
  source_id uuid not null,
  source_resource_id uuid not null,
  fence bigint not null,
  credential_revision bigint not null,
  ingestion_run_id uuid references public.data_source_ingestion_runs(id) on delete restrict,
  status text not null default 'leased',
  error_category text,
  diagnostic_metadata jsonb not null default '{}'::jsonb,
  claimed_at timestamptz not null default now(),
  completed_at timestamptz,
  constraint data_source_sync_attempts_schedule_scope_fk156
    foreign key(schedule_id, tenant_id, project_id, source_id, source_resource_id)
    references public.data_source_sync_schedules(id, tenant_id, project_id, source_id, source_resource_id)
    on delete restrict,
  constraint data_source_sync_attempts_fence_unique156 unique(schedule_id, fence),
  constraint data_source_sync_attempts_status_check156
    check(status in ('leased','succeeded','failed','fenced')),
  constraint data_source_sync_attempts_error_check156
    check(error_category is null or error_category ~ '^[a-z][a-z0-9_]{1,79}$'),
  constraint data_source_sync_attempts_diagnostic_check156 check(
    jsonb_typeof(diagnostic_metadata) = 'object'
    and not diagnostic_metadata ?| array['credential','token','secret','authorization','headers','url']
  ),
  constraint data_source_sync_attempts_terminal_check156 check(
    (status = 'leased' and completed_at is null and error_category is null)
    or (status = 'succeeded' and completed_at is not null and error_category is null)
    or (status in ('failed','fenced') and completed_at is not null and error_category is not null)
  )
);

create index data_source_sync_attempts_scope156
on public.data_source_sync_attempts(tenant_id, project_id, source_id, claimed_at desc);

create function public.configure_data_source_sync156(
  p_tenant_id integer, p_project_id uuid, p_source_id uuid,
  p_source_resource_id uuid, p_actor_user_id integer, p_enabled boolean,
  p_interval_seconds integer, p_expected_fence bigint default null
)
returns public.data_source_sync_schedules
language plpgsql security definer set search_path = '' as $$
declare
  v_source public.data_sources;
  v_schedule public.data_source_sync_schedules;
begin
  if p_interval_seconds not between 900 and 604800 then
    raise exception using errcode = '22023', message = 'source_sync_interval_invalid';
  end if;
  select s.* into v_source from public.data_sources s
  join public.builder_projects p on p.id=s.project_id and p.tenant_id=s.tenant_id
  join public.data_source_resources r on r.source_id=s.id and r.tenant_id=s.tenant_id
    and r.project_id=s.project_id
  where s.id=p_source_id and s.tenant_id=p_tenant_id and s.project_id=p_project_id
    and r.id=p_source_resource_id and s.creator_user_id=p_actor_user_id
    and s.status='active' and s.source_type='api_provider'
    and p.status<>'archived' and p.draft_schema->>'workspaceKind'='data'
    and exists(select 1 from public.tenant_memberships m
      where m.tenant_id=p_tenant_id and m.user_id=p_actor_user_id
        and m.status='active' and m.role<>'learner')
  for update of s;
  if not found then
    raise exception using errcode='42501', message='source_sync_not_authorized';
  end if;
  select * into v_schedule from public.data_source_sync_schedules q
  where q.source_resource_id=p_source_resource_id for update;
  if found and p_expected_fence is not null and v_schedule.fence<>p_expected_fence then
    raise exception using errcode='40001', message='source_sync_configuration_conflict';
  end if;
  if found and v_schedule.status='leased' then
    raise exception using errcode='55006', message='source_sync_in_progress';
  end if;
  insert into public.data_source_sync_schedules(
    tenant_id,project_id,source_id,source_resource_id,enabled,interval_seconds,
    next_due_at,status,retry_count,last_error_category,diagnostic_metadata,
    credential_revision
  ) values(
    p_tenant_id,p_project_id,p_source_id,p_source_resource_id,p_enabled,
    p_interval_seconds,case when p_enabled then now() else null end,
    case when p_enabled then 'idle' else 'disabled' end,0,null,'{}'::jsonb,
    v_source.credential_revision
  ) on conflict(source_resource_id) do update set
    enabled=excluded.enabled, interval_seconds=excluded.interval_seconds,
    next_due_at=case when excluded.enabled then coalesce(public.data_source_sync_schedules.next_due_at,now()) else null end,
    status=case when excluded.enabled then 'idle' else 'disabled' end,
    retry_count=0,last_error_category=null,diagnostic_metadata='{}'::jsonb,
    credential_revision=excluded.credential_revision,
    lease_token=null,lease_owner=null,lease_expires_at=null,ingestion_run_id=null
  returning * into v_schedule;
  return v_schedule;
end;
$$;

create function public.reconcile_expired_source_syncs156(
  p_worker_id text, p_limit integer default 20, p_now timestamptz default now()
)
returns table(schedule_id uuid, outcome text)
language plpgsql security definer set search_path='' as $$
declare
  v_schedule public.data_source_sync_schedules;
  v_run public.data_source_ingestion_runs;
begin
  if length(p_worker_id) not between 3 and 200 or p_limit not between 1 and 100 then
    raise exception using errcode='22023',message='source_sync_reconcile_input_invalid';
  end if;
  for v_schedule in
    select * from public.data_source_sync_schedules q
    where q.status='leased' and q.lease_expires_at<=p_now
    order by q.lease_expires_at,q.id for update skip locked limit p_limit
  loop
    v_run := null;
    if v_schedule.ingestion_run_id is not null then
      select * into v_run from public.data_source_ingestion_runs r
      where r.id=v_schedule.ingestion_run_id;
    end if;
    if v_run.id is not null and v_run.status='succeeded' then
      update public.data_source_sync_schedules set status='idle',retry_count=0,
        last_success_at=coalesce(v_run.completed_at,p_now),last_error_category=null,
        diagnostic_metadata='{}'::jsonb,next_due_at=p_now+make_interval(secs=>interval_seconds),
        lease_token=null,lease_owner=null,lease_expires_at=null,ingestion_run_id=null
      where id=v_schedule.id;
      update public.data_source_sync_attempts a set status='succeeded',completed_at=p_now
      where a.schedule_id=v_schedule.id and a.fence=v_schedule.fence and a.status='leased';
      schedule_id:=v_schedule.id; outcome:='succeeded'; return next;
    else
      update public.data_source_sync_schedules set status='backoff',
        retry_count=least(retry_count+1,8),last_error_category='worker_lease_expired',
        diagnostic_metadata=jsonb_build_object('phase','recovery'),
        next_due_at=p_now+make_interval(secs=>least(3600,60*(2^least(retry_count,6))::integer)),
        lease_token=null,lease_owner=null,lease_expires_at=null,ingestion_run_id=null
      where id=v_schedule.id;
      update public.data_source_sync_attempts a set status='failed',completed_at=p_now,
        error_category='worker_lease_expired',diagnostic_metadata=jsonb_build_object('phase','recovery')
      where a.schedule_id=v_schedule.id and a.fence=v_schedule.fence and a.status='leased';
      schedule_id:=v_schedule.id; outcome:='backoff'; return next;
    end if;
  end loop;
end;
$$;

create function public.claim_due_data_source_syncs156(
  p_worker_id text, p_limit integer default 5, p_lease_seconds integer default 900,
  p_tenant_limit integer default 2, p_provider_limit integer default 4,
  p_now timestamptz default now()
)
returns table(
  schedule_id uuid,lease_token uuid,fence bigint,tenant_id integer,project_id uuid,
  source_id uuid,source_resource_id uuid,resource_key text,provider_key text,
  actor_user_id integer,credential_revision bigint,interval_seconds integer
)
language plpgsql security definer set search_path='' as $$
declare
  v_candidate record;
  v_schedule public.data_source_sync_schedules;
begin
  if length(p_worker_id) not between 3 and 200 or p_limit not between 1 and 50
     or p_lease_seconds not between 60 and 3600 or p_tenant_limit not between 1 and 20
     or p_provider_limit not between 1 and 50 then
    raise exception using errcode='22023',message='source_sync_claim_input_invalid';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('madar_source_sync_dispatch156',0));
  for v_candidate in
    with ranked as (
      select q.id,row_number() over(partition by q.tenant_id order by q.next_due_at,q.id) tenant_rank
      from public.data_source_sync_schedules q
      join public.data_sources s on s.id=q.source_id and s.tenant_id=q.tenant_id
        and s.project_id=q.project_id
      join public.builder_projects p on p.id=q.project_id and p.tenant_id=q.tenant_id
      join public.tenant_memberships m on m.tenant_id=q.tenant_id
        and m.user_id=s.creator_user_id and m.status='active' and m.role<>'learner'
      where q.enabled and q.status in ('idle','backoff','credential_attention','permanent_failure')
        and q.next_due_at<=p_now and s.status='active' and s.source_type='api_provider'
        and s.provider_key is not null and p.status<>'archived'
        and p.draft_schema->>'workspaceKind'='data'
        and not exists(select 1 from public.data_source_ingestion_runs r
          where r.source_resource_id=q.source_resource_id and r.status='processing')
        and (select count(*) from public.data_source_sync_schedules a
          where a.tenant_id=q.tenant_id and a.status='leased' and a.lease_expires_at>p_now)<p_tenant_limit
        and (select count(*) from public.data_source_sync_schedules a
          join public.data_sources x on x.id=a.source_id
          where x.provider_key=s.provider_key and a.status='leased' and a.lease_expires_at>p_now)<p_provider_limit
    )
    select q.id from ranked r join public.data_source_sync_schedules q on q.id=r.id
    where r.tenant_rank<=p_tenant_limit
    order by r.tenant_rank,q.next_due_at,q.tenant_id,q.id
    for update of q skip locked limit p_limit
  loop
    update public.data_source_sync_schedules q set
      status='leased',last_attempt_at=p_now,lease_token=gen_random_uuid(),
      lease_owner=p_worker_id,lease_expires_at=p_now+make_interval(secs=>p_lease_seconds),
      fence=q.fence+1,ingestion_run_id=null,diagnostic_metadata='{}'::jsonb
    where q.id=v_candidate.id
    returning * into v_schedule;
    insert into public.data_source_sync_attempts(
      schedule_id,tenant_id,project_id,source_id,source_resource_id,fence,credential_revision
    ) values(v_schedule.id,v_schedule.tenant_id,v_schedule.project_id,v_schedule.source_id,
      v_schedule.source_resource_id,v_schedule.fence,v_schedule.credential_revision);
    return query select v_schedule.id,v_schedule.lease_token,v_schedule.fence,
      v_schedule.tenant_id,v_schedule.project_id,v_schedule.source_id,
      v_schedule.source_resource_id,r.resource_key,s.provider_key,s.creator_user_id,
      s.credential_revision,v_schedule.interval_seconds
    from public.data_source_resources r join public.data_sources s on s.id=r.source_id
    where r.id=v_schedule.source_resource_id;
  end loop;
end;
$$;

create function public.attach_source_sync_ingestion156(
  p_schedule_id uuid,p_lease_token uuid,p_fence bigint,p_ingestion_run_id uuid
)
returns boolean language plpgsql security definer set search_path='' as $$
declare v_schedule public.data_source_sync_schedules;v_run public.data_source_ingestion_runs;
begin
  select * into v_schedule from public.data_source_sync_schedules q
  where q.id=p_schedule_id for update;
  if not found or v_schedule.status<>'leased' or v_schedule.lease_token is distinct from p_lease_token
     or v_schedule.fence<>p_fence or v_schedule.lease_expires_at<=now() then
    raise exception using errcode='P0001',message='source_sync_lease_lost';end if;
  select * into v_run from public.data_source_ingestion_runs r where r.id=p_ingestion_run_id;
  if not found or v_run.source_resource_id<>v_schedule.source_resource_id
     or v_run.tenant_id<>v_schedule.tenant_id or v_run.status<>'processing' then
    raise exception using errcode='P0001',message='source_sync_ingestion_invalid';end if;
  update public.data_source_sync_schedules set ingestion_run_id=v_run.id where id=v_schedule.id;
  update public.data_source_sync_attempts set ingestion_run_id=v_run.id
  where schedule_id=v_schedule.id and fence=v_schedule.fence and status='leased';
  return true;
end;
$$;

create function public.heartbeat_source_sync156(
  p_schedule_id uuid,p_lease_token uuid,p_fence bigint,p_lease_seconds integer default 900
)
returns boolean language plpgsql security definer set search_path='' as $$
begin
  if p_lease_seconds not between 60 and 3600 then
    raise exception using errcode='22023',message='source_sync_lease_invalid';end if;
  update public.data_source_sync_schedules set lease_expires_at=now()+make_interval(secs=>p_lease_seconds)
  where id=p_schedule_id and status='leased' and lease_token=p_lease_token and fence=p_fence
    and lease_expires_at>now();
  if not found then raise exception using errcode='P0001',message='source_sync_lease_lost';end if;
  return true;
end;
$$;

create function public.complete_source_sync156(
  p_schedule_id uuid,p_lease_token uuid,p_fence bigint,p_ingestion_run_id uuid,
  p_credential_revision bigint,p_now timestamptz default now()
)
returns public.data_source_sync_schedules
language plpgsql security definer set search_path='' as $$
declare v_schedule public.data_source_sync_schedules;v_run public.data_source_ingestion_runs;
declare v_source public.data_sources;
begin
  select * into v_schedule from public.data_source_sync_schedules q
  where q.id=p_schedule_id for update;
  if not found or v_schedule.status<>'leased' or v_schedule.lease_token is distinct from p_lease_token
     or v_schedule.fence<>p_fence or v_schedule.ingestion_run_id is distinct from p_ingestion_run_id then
    raise exception using errcode='P0001',message='source_sync_lease_lost';end if;
  select * into v_run from public.data_source_ingestion_runs r where r.id=p_ingestion_run_id for update;
  select * into v_source from public.data_sources s where s.id=v_schedule.source_id for update;
  if v_run.id is null or v_run.status<>'succeeded' or v_run.source_resource_id<>v_schedule.source_resource_id
     or v_source.credential_revision<>p_credential_revision then
    raise exception using errcode='P0001',message='source_sync_completion_invalid';end if;
  update public.data_source_sync_schedules set status='idle',retry_count=0,
    last_success_at=coalesce(v_run.completed_at,p_now),next_due_at=p_now+make_interval(secs=>interval_seconds),
    last_error_category=null,diagnostic_metadata='{}'::jsonb,
    credential_revision=v_source.credential_revision,lease_token=null,lease_owner=null,
    lease_expires_at=null,ingestion_run_id=null where id=v_schedule.id returning * into v_schedule;
  update public.data_source_sync_attempts set status='succeeded',completed_at=p_now
  where schedule_id=v_schedule.id and fence=v_schedule.fence and status='leased';
  return v_schedule;
end;
$$;

create function public.fail_source_sync156(
  p_schedule_id uuid,p_lease_token uuid,p_fence bigint,p_error_category text,
  p_transient boolean,p_credential_attention boolean default false,
  p_diagnostic_metadata jsonb default '{}'::jsonb,p_now timestamptz default now()
)
returns public.data_source_sync_schedules
language plpgsql security definer set search_path='' as $$
declare v_schedule public.data_source_sync_schedules;v_retry integer;v_status text;v_delay integer;
begin
  if p_error_category !~ '^[a-z][a-z0-9_]{1,79}$' or jsonb_typeof(p_diagnostic_metadata)<>'object'
     or p_diagnostic_metadata ?| array['credential','token','secret','authorization','headers','url'] then
    raise exception using errcode='22023',message='source_sync_failure_invalid';end if;
  select * into v_schedule from public.data_source_sync_schedules q
  where q.id=p_schedule_id for update;
  if not found or v_schedule.status<>'leased' or v_schedule.lease_token is distinct from p_lease_token
     or v_schedule.fence<>p_fence then
    raise exception using errcode='P0001',message='source_sync_lease_lost';end if;
  v_retry:=least(v_schedule.retry_count+1,8);
  if p_credential_attention then v_status:='credential_attention';v_delay:=86400;
  elsif p_transient and v_retry<8 then v_status:='backoff';v_delay:=least(3600,60*(2^least(v_retry-1,6))::integer);
  else v_status:='permanent_failure';v_delay:=86400;end if;
  update public.data_source_sync_schedules set status=v_status,retry_count=v_retry,
    last_error_category=p_error_category,diagnostic_metadata=p_diagnostic_metadata,
    next_due_at=p_now+make_interval(secs=>v_delay),lease_token=null,lease_owner=null,
    lease_expires_at=null,ingestion_run_id=null where id=v_schedule.id returning * into v_schedule;
  update public.data_source_sync_attempts set status='failed',completed_at=p_now,
    error_category=p_error_category,diagnostic_metadata=p_diagnostic_metadata
  where schedule_id=v_schedule.id and fence=v_schedule.fence and status='leased';
  return v_schedule;
end;
$$;

alter table public.data_source_sync_schedules enable row level security;
alter table public.data_source_sync_attempts enable row level security;
revoke all on public.data_source_sync_schedules,public.data_source_sync_attempts
from public,anon,authenticated;
grant select,insert,update on public.data_source_sync_schedules to service_role;
grant select,insert,update on public.data_source_sync_attempts to service_role;

do $$
declare v_signature text;
begin
  foreach v_signature in array array[
    'configure_data_source_sync156(integer,uuid,uuid,uuid,integer,boolean,integer,bigint)',
    'reconcile_expired_source_syncs156(text,integer,timestamp with time zone)',
    'claim_due_data_source_syncs156(text,integer,integer,integer,integer,timestamp with time zone)',
    'attach_source_sync_ingestion156(uuid,uuid,bigint,uuid)',
    'heartbeat_source_sync156(uuid,uuid,bigint,integer)',
    'complete_source_sync156(uuid,uuid,bigint,uuid,bigint,timestamp with time zone)',
    'fail_source_sync156(uuid,uuid,bigint,text,boolean,boolean,jsonb,timestamp with time zone)'
  ] loop
    execute format('revoke all on function public.%s from public,anon,authenticated',v_signature);
    execute format('grant execute on function public.%s to service_role',v_signature);
  end loop;
end;
$$;

update public.application_schema_state set schema_version=156,applied_at=now()
where contract_key='core';

do $$
begin
  if (select schema_version from public.application_schema_state where contract_key='core')<>156 then
    raise exception using errcode='P0001',message='migration_156_postcondition_failed';
  end if;
end;
$$;

notify pgrst,'reload schema';
commit;
