-- Sparse tenant/user notification preference overrides. Missing rows mean enabled.
begin;

create table if not exists public.notification_preferences (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  user_id integer not null references public.users(id) on delete cascade,
  category text not null,
  channel text not null,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint notification_preferences_category_check
    check (category in ('calendar', 'reservations', 'forms', 'general')),
  constraint notification_preferences_channel_check
    check (channel in ('in_app', 'push', 'email')),
  constraint notification_preferences_supported_pair_check
    check (
      (category = 'calendar' and channel in ('in_app', 'push', 'email'))
      or (category in ('reservations', 'forms', 'general') and channel in ('in_app', 'push'))
    ),
  constraint notification_preferences_tenant_user_category_channel_unique
    unique (tenant_id, user_id, category, channel)
);

create index if not exists notification_preferences_tenant_user_idx
  on public.notification_preferences (tenant_id, user_id);

drop trigger if exists set_notification_preferences_updated_at on public.notification_preferences;
create trigger set_notification_preferences_updated_at
before update on public.notification_preferences
for each row execute function public.set_updated_at();

alter table public.notification_preferences enable row level security;
revoke all on public.notification_preferences from public, anon, authenticated;
grant select, insert, update, delete on public.notification_preferences to service_role;

notify pgrst, 'reload schema';
commit;
