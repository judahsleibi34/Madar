begin;

alter table public.calendar_tasks
  add column if not exists sync_connection_id uuid
    references public.calendar_sync_connections(id) on delete set null,
  add column if not exists sync_event_id uuid
    references public.calendar_events(id) on delete set null,
  add column if not exists sync_status text not null default 'not_synced',
  add column if not exists sync_error_code text;

alter table public.calendar_tasks
  drop constraint if exists calendar_tasks_sync_status_check;

alter table public.calendar_tasks
  add constraint calendar_tasks_sync_status_check
  check (sync_status in (
    'not_synced', 'pending', 'synced', 'failed', 'provider_removed'
  ));

create unique index if not exists calendar_tasks_sync_event_unique_idx
  on public.calendar_tasks (sync_event_id)
  where sync_event_id is not null;

create index if not exists calendar_tasks_sync_connection_idx
  on public.calendar_tasks (tenant_id, sync_connection_id, sync_status)
  where sync_connection_id is not null;

revoke all on table public.calendar_tasks from anon, authenticated;
grant select, insert, update, delete on table public.calendar_tasks to service_role;

notify pgrst, 'reload schema';

commit;
