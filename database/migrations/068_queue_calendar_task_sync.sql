-- Durable, idempotent task-to-provider synchronization work. Jobs contain
-- references and bounded error codes only; provider credentials and event
-- payloads remain in their existing protected stores.
begin;

alter table public.calendar_tasks
  drop constraint if exists calendar_tasks_sync_status_check;
alter table public.calendar_tasks
  add constraint calendar_tasks_sync_status_check
  check (sync_status in (
    'not_synced', 'pending', 'synced', 'failed',
    'provider_removed', 'reconciliation_required'
  ));

create table if not exists public.calendar_task_sync_jobs (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  task_id uuid references public.calendar_tasks(id) on delete set null,
  connection_id uuid not null references public.calendar_sync_connections(id) on delete cascade,
  operation text not null,
  task_version integer not null,
  status text not null default 'pending',
  attempts integer not null default 0,
  max_attempts integer not null default 6,
  next_attempt_at timestamptz not null default now(),
  leased_at timestamptz,
  lease_owner text,
  last_error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  constraint calendar_task_sync_jobs_operation_check
    check (operation in ('create', 'update', 'delete', 'reconcile')),
  constraint calendar_task_sync_jobs_status_check
    check (status in (
      'pending', 'processing', 'succeeded', 'failed',
      'reconciliation_required', 'superseded'
    )),
  constraint calendar_task_sync_jobs_attempts_check
    check (attempts >= 0 and max_attempts between 1 and 12),
  constraint calendar_task_sync_jobs_version_check check (task_version >= 1),
  constraint calendar_task_sync_jobs_active_task_check
    check (task_id is not null or status = 'succeeded'),
  constraint calendar_task_sync_jobs_error_code_check
    check (last_error_code is null or last_error_code ~ '^[a-z0-9_.-]{1,100}$')
);

create unique index if not exists calendar_task_sync_jobs_active_unique_idx
  on public.calendar_task_sync_jobs (tenant_id, task_id, connection_id)
  where status in ('pending', 'processing')
     or (status = 'failed' and completed_at is null);

create index if not exists calendar_task_sync_jobs_claim_idx
  on public.calendar_task_sync_jobs (status, next_attempt_at, leased_at, created_at)
  where status in ('pending', 'failed', 'processing');

create index if not exists calendar_task_sync_jobs_tenant_created_idx
  on public.calendar_task_sync_jobs (tenant_id, created_at desc);

drop trigger if exists set_calendar_task_sync_jobs_updated_at
  on public.calendar_task_sync_jobs;
create trigger set_calendar_task_sync_jobs_updated_at
before update on public.calendar_task_sync_jobs
for each row execute function public.set_updated_at();

alter table public.calendar_task_sync_jobs enable row level security;
revoke all on table public.calendar_task_sync_jobs from public, anon, authenticated;
grant select, insert, update, delete on table public.calendar_task_sync_jobs to service_role;

create or replace function public.enqueue_calendar_task_sync_job(
  p_tenant_id integer,
  p_task_id uuid,
  p_connection_id uuid,
  p_operation text,
  p_task_version integer
)
returns public.calendar_task_sync_jobs
language plpgsql
security definer
set search_path = public
as $$
declare
  job public.calendar_task_sync_jobs;
begin
  if p_operation not in ('create', 'update', 'delete', 'reconcile')
      or p_task_version < 1 then
    raise exception using errcode = '22023', message = 'invalid_calendar_task_sync_job';
  end if;

  select * into job
  from public.calendar_task_sync_jobs
  where tenant_id = p_tenant_id
    and task_id = p_task_id
    and connection_id = p_connection_id
    and (
      status in ('pending', 'processing')
      or (status = 'failed' and completed_at is null)
    )
  for update;

  if found then
    update public.calendar_task_sync_jobs
    set operation = p_operation,
        task_version = greatest(task_version, p_task_version),
        status = case when status = 'processing' then status else 'pending' end,
        next_attempt_at = case when status = 'processing' then next_attempt_at else now() end,
        last_error_code = null
    where id = job.id
    returning * into job;
    return job;
  end if;

  insert into public.calendar_task_sync_jobs (
    tenant_id, task_id, connection_id, operation, task_version
  ) values (
    p_tenant_id, p_task_id, p_connection_id, p_operation, p_task_version
  )
  returning * into job;
  return job;
exception
  when unique_violation then
    select * into job
    from public.calendar_task_sync_jobs
    where tenant_id = p_tenant_id
      and task_id = p_task_id
      and connection_id = p_connection_id
      and (
        status in ('pending', 'processing')
        or (status = 'failed' and completed_at is null)
      )
    limit 1;
    return job;
end;
$$;

create or replace function public.claim_calendar_task_sync_jobs(
  p_worker_id text,
  p_limit integer default 10,
  p_now timestamptz default now()
)
returns setof public.calendar_task_sync_jobs
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.calendar_task_sync_jobs job
  set status = 'failed',
      leased_at = null,
      lease_owner = null,
      next_attempt_at = p_now,
      last_error_code = coalesce(job.last_error_code, 'worker_lease_expired')
  where job.status = 'processing'
    and job.leased_at < p_now - interval '2 minutes'
    and job.attempts < job.max_attempts;

  update public.calendar_task_sync_jobs job
  set status = 'failed',
      leased_at = null,
      lease_owner = null,
      last_error_code = coalesce(job.last_error_code, 'sync_attempts_exhausted')
  where job.status = 'processing'
    and job.leased_at < p_now - interval '2 minutes'
    and job.attempts >= job.max_attempts;

  return query
  update public.calendar_task_sync_jobs job
  set status = 'processing',
      attempts = job.attempts + 1,
      leased_at = p_now,
      lease_owner = left(p_worker_id, 120),
      last_error_code = null
  where job.id in (
    select candidate.id
    from public.calendar_task_sync_jobs candidate
    where candidate.status in ('pending', 'failed')
      and candidate.next_attempt_at <= p_now
      and candidate.attempts < candidate.max_attempts
    order by candidate.next_attempt_at, candidate.created_at
    limit greatest(1, least(coalesce(p_limit, 10), 50))
    for update skip locked
  )
  returning job.*;
end;
$$;

create or replace function public.finish_calendar_task_sync_job(
  p_job_id uuid,
  p_status text,
  p_error_code text default null,
  p_next_attempt_at timestamptz default null,
  p_finished_at timestamptz default now()
)
returns public.calendar_task_sync_jobs
language plpgsql
security definer
set search_path = public
as $$
declare
  job public.calendar_task_sync_jobs;
begin
  if p_status not in (
    'succeeded', 'failed', 'reconciliation_required', 'superseded'
  ) then
    raise exception using errcode = '22023', message = 'invalid_calendar_task_sync_status';
  end if;

  update public.calendar_task_sync_jobs
  set status = p_status,
      last_error_code = case when p_status = 'succeeded' then null else p_error_code end,
      next_attempt_at = coalesce(p_next_attempt_at, next_attempt_at),
      leased_at = null,
      lease_owner = null,
      completed_at = case
        when p_status in ('succeeded', 'reconciliation_required', 'superseded')
          then p_finished_at
        when p_status = 'failed' and attempts >= max_attempts
          then p_finished_at
        else null
      end
  where id = p_job_id and status = 'processing'
  returning * into job;

  if not found then
    raise exception using errcode = 'P0001', message = 'calendar_task_sync_job_state_conflict';
  end if;
  return job;
end;
$$;

create or replace function public.complete_calendar_task_sync_delete(
  p_job_id uuid,
  p_finished_at timestamptz default now()
)
returns public.calendar_task_sync_jobs
language plpgsql
security definer
set search_path = public
as $$
declare
  job public.calendar_task_sync_jobs;
begin
  update public.calendar_task_sync_jobs
  set status = 'succeeded',
      last_error_code = null,
      leased_at = null,
      lease_owner = null,
      completed_at = p_finished_at
  where id = p_job_id
    and status = 'processing'
    and operation = 'delete'
  returning * into job;
  if not found then
    raise exception using errcode = 'P0001', message = 'calendar_task_sync_job_state_conflict';
  end if;
  delete from public.calendar_tasks
  where id = job.task_id and tenant_id = job.tenant_id;
  return job;
end;
$$;

revoke all on function public.enqueue_calendar_task_sync_job(integer, uuid, uuid, text, integer)
  from public, anon, authenticated;
revoke all on function public.claim_calendar_task_sync_jobs(text, integer, timestamptz)
  from public, anon, authenticated;
revoke all on function public.finish_calendar_task_sync_job(uuid, text, text, timestamptz, timestamptz)
  from public, anon, authenticated;
revoke all on function public.complete_calendar_task_sync_delete(uuid, timestamptz)
  from public, anon, authenticated;
grant execute on function public.enqueue_calendar_task_sync_job(integer, uuid, uuid, text, integer)
  to service_role;
grant execute on function public.claim_calendar_task_sync_jobs(text, integer, timestamptz)
  to service_role;
grant execute on function public.finish_calendar_task_sync_job(uuid, text, text, timestamptz, timestamptz)
  to service_role;
grant execute on function public.complete_calendar_task_sync_delete(uuid, timestamptz)
  to service_role;

notify pgrst, 'reload schema';
commit;
