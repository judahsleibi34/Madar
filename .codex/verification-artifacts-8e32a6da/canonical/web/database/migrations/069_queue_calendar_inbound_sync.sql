-- Durable connection-level inbound synchronization. A connection maps one
-- explicitly enabled provider calendar (currently the provider primary
-- calendar) to its existing tenant-owned Madar calendar.
begin;

alter table public.calendar_sync_connections
  add column if not exists provider_calendar_id text not null default 'primary',
  add column if not exists inbound_sync_enabled boolean not null default true,
  add column if not exists inbound_sync_status text not null default 'idle',
  add column if not exists last_inbound_success_at timestamptz,
  add column if not exists inbound_sync_error_code text;

alter table public.calendar_sync_connections
  drop constraint if exists calendar_sync_inbound_status_check;
alter table public.calendar_sync_connections
  add constraint calendar_sync_inbound_status_check
  check (inbound_sync_status in (
    'idle', 'pending', 'syncing', 'synced', 'failed',
    'full_resync_required'
  ));
alter table public.calendar_sync_connections
  drop constraint if exists calendar_sync_provider_calendar_id_check;
alter table public.calendar_sync_connections
  add constraint calendar_sync_provider_calendar_id_check
  check (
    provider_calendar_id = 'primary'
    or provider_calendar_id ~ '^[A-Za-z0-9._@%-]{1,512}$'
  );
alter table public.calendar_sync_connections
  drop constraint if exists calendar_sync_inbound_error_code_check;
alter table public.calendar_sync_connections
  add constraint calendar_sync_inbound_error_code_check
  check (
    inbound_sync_error_code is null
    or inbound_sync_error_code ~ '^[a-z0-9_.-]{1,100}$'
  );

create unique index if not exists calendar_sync_connections_tenant_id_id_idx
  on public.calendar_sync_connections (tenant_id, id);

create table if not exists public.calendar_connection_sync_jobs (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  connection_id uuid not null,
  operation text not null default 'incremental',
  status text not null default 'pending',
  attempts integer not null default 0,
  max_attempts integer not null default 6,
  next_attempt_at timestamptz not null default now(),
  leased_at timestamptz,
  lease_owner text,
  last_error_code text,
  result_counts jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  constraint calendar_connection_sync_jobs_operation_check
    check (operation in ('incremental', 'full')),
  constraint calendar_connection_sync_jobs_status_check
    check (status in ('pending', 'processing', 'succeeded', 'failed')),
  constraint calendar_connection_sync_jobs_attempts_check
    check (attempts >= 0 and max_attempts between 1 and 12),
  constraint calendar_connection_sync_jobs_error_code_check
    check (last_error_code is null or last_error_code ~ '^[a-z0-9_.-]{1,100}$'),
  constraint calendar_connection_sync_jobs_result_counts_check
    check (jsonb_typeof(result_counts) = 'object'),
  constraint calendar_connection_sync_jobs_connection_tenant_fkey
    foreign key (tenant_id, connection_id)
    references public.calendar_sync_connections(tenant_id, id)
    on delete cascade
);

create unique index if not exists calendar_connection_sync_jobs_active_unique_idx
  on public.calendar_connection_sync_jobs (tenant_id, connection_id)
  where status in ('pending', 'processing')
     or (status = 'failed' and completed_at is null);
create index if not exists calendar_connection_sync_jobs_claim_idx
  on public.calendar_connection_sync_jobs
    (status, next_attempt_at, leased_at, created_at)
  where status in ('pending', 'failed', 'processing');

drop trigger if exists set_calendar_connection_sync_jobs_updated_at
  on public.calendar_connection_sync_jobs;
create trigger set_calendar_connection_sync_jobs_updated_at
before update on public.calendar_connection_sync_jobs
for each row execute function public.set_updated_at();

alter table public.calendar_connection_sync_jobs enable row level security;
revoke all on table public.calendar_connection_sync_jobs
  from public, anon, authenticated;
grant select, insert, update, delete on table public.calendar_connection_sync_jobs
  to service_role;

create or replace function public.enqueue_calendar_connection_sync_job(
  p_tenant_id integer,
  p_connection_id uuid,
  p_operation text default 'incremental'
)
returns public.calendar_connection_sync_jobs
language plpgsql
security definer
set search_path = public
as $$
declare
  job public.calendar_connection_sync_jobs;
begin
  if p_operation not in ('incremental', 'full') then
    raise exception using errcode = '22023', message = 'invalid_calendar_connection_sync_job';
  end if;
  select * into job
  from public.calendar_connection_sync_jobs
  where tenant_id = p_tenant_id
    and connection_id = p_connection_id
    and (
      status in ('pending', 'processing')
      or (status = 'failed' and completed_at is null)
    )
  for update;
  if found then
    update public.calendar_connection_sync_jobs
    set operation = case
          when operation = 'full' or p_operation = 'full' then 'full'
          else 'incremental'
        end,
        status = case when status = 'processing' then status else 'pending' end,
        next_attempt_at = case when status = 'processing' then next_attempt_at else now() end,
        last_error_code = null
    where id = job.id
    returning * into job;
    return job;
  end if;
  insert into public.calendar_connection_sync_jobs (
    tenant_id, connection_id, operation
  ) values (p_tenant_id, p_connection_id, p_operation)
  returning * into job;
  return job;
exception
  when unique_violation then
    select * into job
    from public.calendar_connection_sync_jobs
    where tenant_id = p_tenant_id
      and connection_id = p_connection_id
      and (
        status in ('pending', 'processing')
        or (status = 'failed' and completed_at is null)
      )
    limit 1;
    return job;
end;
$$;

create or replace function public.claim_calendar_connection_sync_jobs(
  p_worker_id text,
  p_limit integer default 2,
  p_now timestamptz default now()
)
returns setof public.calendar_connection_sync_jobs
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.calendar_connection_sync_jobs job
  set status = 'failed',
      leased_at = null,
      lease_owner = null,
      next_attempt_at = p_now,
      last_error_code = coalesce(job.last_error_code, 'worker_lease_expired')
  where job.status = 'processing'
    and job.leased_at < p_now - interval '3 minutes'
    and job.attempts < job.max_attempts;
  update public.calendar_connection_sync_jobs job
  set status = 'failed',
      leased_at = null,
      lease_owner = null,
      completed_at = p_now,
      last_error_code = coalesce(job.last_error_code, 'sync_attempts_exhausted')
  where job.status = 'processing'
    and job.leased_at < p_now - interval '3 minutes'
    and job.attempts >= job.max_attempts;
  return query
  update public.calendar_connection_sync_jobs job
  set status = 'processing',
      attempts = job.attempts + 1,
      leased_at = p_now,
      lease_owner = left(p_worker_id, 120),
      last_error_code = null
  where job.id in (
    select candidate.id
    from public.calendar_connection_sync_jobs candidate
    where candidate.status in ('pending', 'failed')
      and candidate.next_attempt_at <= p_now
      and candidate.attempts < candidate.max_attempts
    order by candidate.next_attempt_at, candidate.created_at
    limit greatest(1, least(coalesce(p_limit, 2), 10))
    for update skip locked
  )
  returning job.*;
end;
$$;

create or replace function public.finish_calendar_connection_sync_job(
  p_job_id uuid,
  p_succeeded boolean,
  p_error_code text default null,
  p_result_counts jsonb default '{}'::jsonb,
  p_next_attempt_at timestamptz default null,
  p_finished_at timestamptz default now()
)
returns public.calendar_connection_sync_jobs
language plpgsql
security definer
set search_path = public
as $$
declare
  job public.calendar_connection_sync_jobs;
begin
  update public.calendar_connection_sync_jobs
  set status = case when p_succeeded then 'succeeded' else 'failed' end,
      last_error_code = case when p_succeeded then null else p_error_code end,
      result_counts = coalesce(p_result_counts, '{}'::jsonb),
      next_attempt_at = coalesce(p_next_attempt_at, next_attempt_at),
      leased_at = null,
      lease_owner = null,
      completed_at = case
        when p_succeeded or attempts >= max_attempts then p_finished_at
        else null
      end
  where id = p_job_id and status = 'processing'
  returning * into job;
  if not found then
    raise exception using errcode = 'P0001', message = 'calendar_connection_sync_job_state_conflict';
  end if;
  return job;
end;
$$;

revoke all on function public.enqueue_calendar_connection_sync_job(integer, uuid, text)
  from public, anon, authenticated;
revoke all on function public.claim_calendar_connection_sync_jobs(text, integer, timestamptz)
  from public, anon, authenticated;
revoke all on function public.finish_calendar_connection_sync_job(uuid, boolean, text, jsonb, timestamptz, timestamptz)
  from public, anon, authenticated;
grant execute on function public.enqueue_calendar_connection_sync_job(integer, uuid, text)
  to service_role;
grant execute on function public.claim_calendar_connection_sync_jobs(text, integer, timestamptz)
  to service_role;
grant execute on function public.finish_calendar_connection_sync_job(uuid, boolean, text, jsonb, timestamptz, timestamptz)
  to service_role;

revoke all on table public.calendar_sync_connections from anon, authenticated;
grant select, insert, update, delete on table public.calendar_sync_connections
  to service_role;

notify pgrst, 'reload schema';
commit;
