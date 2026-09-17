insert into public.calendar_task_reminders (
  task_id,
  tenant_id,
  channel,
  minutes_before,
  scheduled_for,
  delivery_status
)
select
  task.id,
  task.tenant_id,
  'in_app',
  10,
  case when task.scheduled_start is not null then task.scheduled_start - interval '10 minutes' else null end,
  case when task.status in ('done', 'cancelled') then 'cancelled' else 'scheduled' end
from public.calendar_tasks as task
on conflict (task_id, channel) do nothing;
