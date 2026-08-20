-- Keep workflow status separate from whether a calendar task is archived.
begin;

alter table public.calendar_tasks
  add column if not exists archived_at timestamptz;

create index if not exists calendar_tasks_tenant_archived_idx
  on public.calendar_tasks (tenant_id, archived_at desc)
  where archived_at is not null;

notify pgrst, 'reload schema';
commit;
