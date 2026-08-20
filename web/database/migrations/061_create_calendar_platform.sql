-- Provider-neutral calendars, events, recurrence, reminders, tasks, and sync health.
begin;

create extension if not exists pgcrypto;

create table if not exists public.calendars (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  owner_user_id integer references public.users(id) on delete set null,
  name text not null,
  color text not null default '#5b7cfa',
  timezone text not null default 'UTC',
  visibility text not null default 'private',
  is_default boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint calendars_visibility_check check (visibility in ('private','team','organization','public')),
  constraint calendars_name_check check (char_length(name) between 1 and 120)
);
create unique index if not exists calendars_user_default_idx
  on public.calendars (tenant_id, owner_user_id) where is_default;
create index if not exists calendars_tenant_idx on public.calendars (tenant_id, created_at);

create table if not exists public.calendar_memberships (
  calendar_id uuid not null references public.calendars(id) on delete cascade,
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  user_id integer not null references public.users(id) on delete cascade,
  role text not null default 'viewer',
  created_at timestamptz not null default now(),
  primary key (calendar_id, user_id),
  constraint calendar_memberships_role_check check (role in ('availability','viewer','editor','owner'))
);

create table if not exists public.calendar_events (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  calendar_id uuid not null references public.calendars(id) on delete cascade,
  created_by integer references public.users(id) on delete set null,
  title text not null,
  description text not null default '',
  location text not null default '',
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  timezone text not null default 'UTC',
  all_day boolean not null default false,
  status text not null default 'confirmed',
  visibility text not null default 'calendar_default',
  transparency text not null default 'busy',
  recurrence_rule text,
  recurrence_parent_id uuid references public.calendar_events(id) on delete cascade,
  recurrence_original_start timestamptz,
  recurrence_exclusions jsonb not null default '[]'::jsonb,
  source_type text not null default 'madar',
  source_id text,
  external_etag text,
  last_synced_at timestamptz,
  project_id uuid references public.builder_projects(id) on delete set null,
  version integer not null default 1,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint calendar_events_time_check check (ends_at > starts_at),
  constraint calendar_events_status_check check (status in ('tentative','confirmed','cancelled')),
  constraint calendar_events_visibility_check check (visibility in ('calendar_default','private','team','organization','public')),
  constraint calendar_events_transparency_check check (transparency in ('busy','free')),
  constraint calendar_events_exclusions_check check (jsonb_typeof(recurrence_exclusions) = 'array'),
  constraint calendar_events_version_check check (version > 0)
);
create index if not exists calendar_events_tenant_range_idx
  on public.calendar_events (tenant_id, starts_at, ends_at) where deleted_at is null;
create index if not exists calendar_events_calendar_range_idx
  on public.calendar_events (calendar_id, starts_at, ends_at) where deleted_at is null;
create unique index if not exists calendar_events_source_unique_idx
  on public.calendar_events (tenant_id, source_type, source_id) where source_id is not null and deleted_at is null;

create table if not exists public.calendar_event_attendees (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.calendar_events(id) on delete cascade,
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  email text not null,
  display_name text not null default '',
  response_status text not null default 'needs_action',
  is_organizer boolean not null default false,
  is_external boolean not null default true,
  created_at timestamptz not null default now(),
  constraint calendar_attendee_response_check check (response_status in ('needs_action','accepted','declined','tentative')),
  unique (event_id, email)
);

create table if not exists public.calendar_event_reminders (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.calendar_events(id) on delete cascade,
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  channel text not null default 'in_app',
  minutes_before integer not null,
  scheduled_for timestamptz,
  delivery_status text not null default 'scheduled',
  delivered_at timestamptz,
  failure_code text,
  created_at timestamptz not null default now(),
  constraint calendar_reminder_channel_check check (channel in ('in_app','email','web_push')),
  constraint calendar_reminder_minutes_check check (minutes_before between 0 and 525600),
  constraint calendar_reminder_status_check check (delivery_status in ('scheduled','queued','sent','delivered','failed','cancelled')),
  unique (event_id, channel, minutes_before)
);
create index if not exists calendar_reminders_due_idx
  on public.calendar_event_reminders (delivery_status, scheduled_for) where delivery_status = 'scheduled';

create table if not exists public.calendar_event_changes (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  event_id uuid not null references public.calendar_events(id) on delete cascade,
  changed_by integer references public.users(id) on delete set null,
  action text not null,
  scope text not null default 'event',
  before_data jsonb,
  after_data jsonb,
  created_at timestamptz not null default now(),
  constraint calendar_event_changes_action_check check (action in ('created','updated','cancelled','deleted','restored')),
  constraint calendar_event_changes_scope_check check (scope in ('event','occurrence','future','series'))
);
create index if not exists calendar_event_changes_event_idx on public.calendar_event_changes (event_id, created_at desc);

create table if not exists public.calendar_tasks (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  calendar_id uuid references public.calendars(id) on delete set null,
  project_id uuid references public.builder_projects(id) on delete set null,
  owner_user_id integer references public.users(id) on delete set null,
  title text not null,
  description text not null default '',
  status text not null default 'todo',
  priority text not null default 'normal',
  estimate_minutes integer,
  due_at timestamptz,
  scheduled_start timestamptz,
  scheduled_end timestamptz,
  milestone boolean not null default false,
  version integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint calendar_tasks_status_check check (status in ('todo','in_progress','blocked','done','cancelled')),
  constraint calendar_tasks_priority_check check (priority in ('low','normal','high','urgent')),
  constraint calendar_tasks_estimate_check check (estimate_minutes is null or estimate_minutes between 1 and 525600),
  constraint calendar_tasks_schedule_check check (scheduled_end is null or scheduled_start is not null),
  constraint calendar_tasks_schedule_order_check check (scheduled_end is null or scheduled_end > scheduled_start)
);
create index if not exists calendar_tasks_tenant_due_idx on public.calendar_tasks (tenant_id, status, due_at);

create table if not exists public.calendar_task_dependencies (
  task_id uuid not null references public.calendar_tasks(id) on delete cascade,
  depends_on_task_id uuid not null references public.calendar_tasks(id) on delete cascade,
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  primary key (task_id, depends_on_task_id),
  constraint calendar_task_dependency_self_check check (task_id <> depends_on_task_id)
);

create table if not exists public.calendar_sync_connections (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  user_id integer not null references public.users(id) on delete cascade,
  local_calendar_id uuid references public.calendars(id) on delete cascade,
  provider text not null,
  account_label text not null default '',
  external_account_id text,
  direction text not null default 'read',
  status text not null default 'setup_required',
  encrypted_credentials text,
  cursor_data jsonb not null default '{}'::jsonb,
  last_success_at timestamptz,
  last_attempt_at timestamptz,
  last_error_code text,
  pending_changes integer not null default 0,
  failed_changes integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint calendar_sync_provider_check check (provider in ('google','microsoft','caldav','ics')),
  constraint calendar_sync_direction_check check (direction in ('read','two_way')),
  constraint calendar_sync_status_check check (status in ('setup_required','connected','degraded','disconnected')),
  unique (tenant_id, user_id, provider, external_account_id)
);

create table if not exists public.calendar_sync_conflicts (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  connection_id uuid not null references public.calendar_sync_connections(id) on delete cascade,
  event_id uuid references public.calendar_events(id) on delete cascade,
  external_event_id text,
  local_data jsonb not null default '{}'::jsonb,
  remote_data jsonb not null default '{}'::jsonb,
  status text not null default 'unresolved',
  resolution text,
  created_at timestamptz not null default now(),
  resolved_at timestamptz,
  constraint calendar_sync_conflict_status_check check (status in ('unresolved','resolved','ignored'))
);

create table if not exists public.calendar_invitation_reviews (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  event_id uuid references public.calendar_events(id) on delete cascade,
  sender_email text not null,
  trust_level text not null default 'unknown',
  reasons jsonb not null default '[]'::jsonb,
  disposition text not null default 'quarantined',
  created_at timestamptz not null default now(),
  constraint calendar_invitation_trust_check check (trust_level in ('trusted','unknown','suspicious')),
  constraint calendar_invitation_disposition_check check (disposition in ('allowed','quarantined','blocked','reported'))
);
create unique index if not exists calendar_invitation_review_sender_event_idx
  on public.calendar_invitation_reviews (tenant_id, event_id, sender_email);

do $$
declare table_name text;
begin
  foreach table_name in array array[
    'calendars','calendar_memberships','calendar_events','calendar_event_attendees',
    'calendar_event_reminders','calendar_event_changes','calendar_tasks',
    'calendar_task_dependencies','calendar_sync_connections','calendar_sync_conflicts',
    'calendar_invitation_reviews'
  ] loop
    execute format('alter table public.%I enable row level security', table_name);
    execute format('revoke all on table public.%I from anon, authenticated', table_name);
    execute format('grant select, insert, update, delete on table public.%I to service_role', table_name);
  end loop;
end $$;

drop trigger if exists set_calendars_updated_at on public.calendars;
create trigger set_calendars_updated_at before update on public.calendars
for each row execute function public.set_updated_at();
drop trigger if exists set_calendar_events_updated_at on public.calendar_events;
create trigger set_calendar_events_updated_at before update on public.calendar_events
for each row execute function public.set_updated_at();
drop trigger if exists set_calendar_tasks_updated_at on public.calendar_tasks;
create trigger set_calendar_tasks_updated_at before update on public.calendar_tasks
for each row execute function public.set_updated_at();
drop trigger if exists set_calendar_sync_connections_updated_at on public.calendar_sync_connections;
create trigger set_calendar_sync_connections_updated_at before update on public.calendar_sync_connections
for each row execute function public.set_updated_at();

notify pgrst, 'reload schema';
commit;
