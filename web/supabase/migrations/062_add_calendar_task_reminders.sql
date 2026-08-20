create table if not exists public.calendar_task_reminders (
  id uuid primary key default gen_random_uuid(),
  task_id uuid not null references public.calendar_tasks(id) on delete cascade,
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  channel text not null default 'in_app',
  minutes_before integer not null default 10,
  scheduled_for timestamptz,
  delivery_status text not null default 'scheduled',
  delivered_at timestamptz,
  failure_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint calendar_task_reminder_channel_check check (channel in ('in_app','email','web_push')),
  constraint calendar_task_reminder_minutes_check check (minutes_before between 0 and 525600),
  constraint calendar_task_reminder_status_check check (delivery_status in ('scheduled','queued','sent','delivered','failed','cancelled')),
  unique (task_id, channel)
);

create index if not exists calendar_task_reminders_due_idx
  on public.calendar_task_reminders (delivery_status, scheduled_for)
  where delivery_status = 'scheduled';

alter table public.calendar_task_reminders enable row level security;
revoke all on table public.calendar_task_reminders from anon, authenticated;
grant select, insert, update, delete on table public.calendar_task_reminders to service_role;

drop trigger if exists set_calendar_task_reminders_updated_at on public.calendar_task_reminders;
create trigger set_calendar_task_reminders_updated_at
before update on public.calendar_task_reminders
for each row execute function public.set_updated_at();
