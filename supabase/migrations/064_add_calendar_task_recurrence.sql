alter table public.calendar_tasks
  add column if not exists recurrence_rule text;

alter table public.calendar_tasks
  drop constraint if exists calendar_tasks_recurrence_rule_check;

alter table public.calendar_tasks
  add constraint calendar_tasks_recurrence_rule_check
  check (
    recurrence_rule is null
    or recurrence_rule in ('FREQ=DAILY', 'FREQ=WEEKLY', 'FREQ=MONTHLY')
  );
