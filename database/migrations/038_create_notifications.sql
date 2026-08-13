-- ============================================================
-- Tenant notifications and browser push subscriptions
-- ============================================================

begin;

create extension if not exists pgcrypto;

create table if not exists public.notification_events (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  event_type text not null,
  source_type text not null,
  source_id text,
  title text not null,
  body text not null,
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists notification_events_tenant_created_idx
on public.notification_events (tenant_id, created_at desc);

create table if not exists public.user_notifications (
  id uuid primary key default gen_random_uuid(),
  event_id uuid references public.notification_events(id) on delete cascade,
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  user_id integer not null references public.users(id) on delete cascade,
  event_type text not null,
  title text not null,
  body text not null,
  data jsonb not null default '{}'::jsonb,
  read_at timestamptz,
  created_at timestamptz not null default now(),
  constraint user_notifications_event_user_unique unique (event_id, user_id)
);

create index if not exists user_notifications_user_created_idx
on public.user_notifications (user_id, created_at desc);

create index if not exists user_notifications_user_unread_idx
on public.user_notifications (user_id, created_at desc)
where read_at is null;

create table if not exists public.web_push_subscriptions (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer references public.tenants(tenant_id) on delete cascade,
  user_id integer not null references public.users(id) on delete cascade,
  endpoint text not null unique,
  p256dh text not null,
  auth text not null,
  user_agent text,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  revoked_at timestamptz
);

create index if not exists web_push_subscriptions_user_active_idx
on public.web_push_subscriptions (user_id, last_seen_at desc)
where revoked_at is null;

alter table public.notification_events enable row level security;
alter table public.user_notifications enable row level security;
alter table public.web_push_subscriptions enable row level security;

revoke all on table public.notification_events from anon;
revoke all on table public.notification_events from authenticated;
revoke all on table public.user_notifications from anon;
revoke all on table public.user_notifications from authenticated;
revoke all on table public.web_push_subscriptions from anon;
revoke all on table public.web_push_subscriptions from authenticated;

grant select, insert, update, delete on table public.notification_events to service_role;
grant select, insert, update, delete on table public.user_notifications to service_role;
grant select, insert, update, delete on table public.web_push_subscriptions to service_role;

notify pgrst, 'reload schema';

commit;
