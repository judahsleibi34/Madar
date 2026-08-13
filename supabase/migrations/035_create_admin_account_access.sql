-- ============================================================
-- Admin account access permission codes and temporary sessions
-- ============================================================

begin;

create extension if not exists pgcrypto;

create table if not exists public.admin_account_access_requests (
  id uuid primary key default gen_random_uuid(),
  admin_user_id integer not null references public.users(id) on delete cascade,
  target_user_id integer not null references public.users(id) on delete cascade,
  target_email text not null,
  code_hash text,
  attempts integer not null default 0,
  expires_at timestamptz not null,
  used_at timestamptz,
  revoked_at timestamptz,
  revoked_reason text,
  user_agent_hash text,
  created_at timestamptz not null default now(),
  constraint admin_account_access_attempts_nonnegative check (attempts >= 0)
);

create index if not exists admin_account_access_requests_lookup_idx
on public.admin_account_access_requests (admin_user_id, target_user_id, created_at desc);

create index if not exists admin_account_access_requests_expires_idx
on public.admin_account_access_requests (expires_at);

create table if not exists public.admin_account_access_sessions (
  id uuid primary key default gen_random_uuid(),
  access_request_id uuid references public.admin_account_access_requests(id) on delete set null,
  admin_user_id integer not null references public.users(id) on delete cascade,
  target_user_id integer not null references public.users(id) on delete cascade,
  session_token_hash text,
  expires_at timestamptz not null,
  ended_at timestamptz,
  ended_reason text,
  user_agent_hash text,
  created_at timestamptz not null default now()
);

create index if not exists admin_account_access_sessions_admin_active_idx
on public.admin_account_access_sessions (admin_user_id, created_at desc);

create index if not exists admin_account_access_sessions_target_idx
on public.admin_account_access_sessions (target_user_id, created_at desc);

create index if not exists admin_account_access_sessions_token_hash_idx
on public.admin_account_access_sessions (session_token_hash)
where session_token_hash is not null;

create index if not exists admin_account_access_sessions_expires_idx
on public.admin_account_access_sessions (expires_at);

alter table public.admin_account_access_requests enable row level security;
alter table public.admin_account_access_sessions enable row level security;

revoke all on table public.admin_account_access_requests from anon;
revoke all on table public.admin_account_access_requests from authenticated;
revoke all on table public.admin_account_access_sessions from anon;
revoke all on table public.admin_account_access_sessions from authenticated;

grant select, insert, update, delete
on table public.admin_account_access_requests
to service_role;

grant select, insert, update, delete
on table public.admin_account_access_sessions
to service_role;

notify pgrst, 'reload schema';

commit;
