-- ============================================================
-- Create app-side MFA security settings
-- ============================================================

begin;

create table if not exists public.user_security_settings (
  user_id integer primary key references public.users(id) on delete cascade,
  auth_id uuid not null,
  mfa_required boolean not null default false,
  mfa_required_at timestamptz,
  mfa_grace_until timestamptz,
  last_aal2_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists user_security_settings_auth_id_idx
on public.user_security_settings (auth_id);

create index if not exists user_security_settings_mfa_required_idx
on public.user_security_settings (mfa_required)
where mfa_required = true;

insert into public.user_security_settings (
  user_id,
  auth_id,
  mfa_required,
  mfa_required_at
)
select
  users.id,
  users.auth_id,
  coalesce(users.user_type, 'user') = 'admin',
  case
    when coalesce(users.user_type, 'user') = 'admin' then now()
    else null
  end
from public.users users
where users.auth_id is not null
on conflict (user_id) do update
set
  auth_id = excluded.auth_id,
  mfa_required = public.user_security_settings.mfa_required or excluded.mfa_required,
  mfa_required_at = case
    when public.user_security_settings.mfa_required_at is not null then public.user_security_settings.mfa_required_at
    when excluded.mfa_required then excluded.mfa_required_at
    else null
  end,
  updated_at = now();

update public.user_security_settings settings
set
  mfa_required = true,
  mfa_required_at = coalesce(settings.mfa_required_at, now()),
  updated_at = now()
from public.users users
where settings.user_id = users.id
  and coalesce(users.user_type, 'user') = 'admin';

drop trigger if exists set_user_security_settings_updated_at on public.user_security_settings;

create trigger set_user_security_settings_updated_at
before update on public.user_security_settings
for each row
execute function public.set_updated_at();

alter table public.user_security_settings enable row level security;

revoke all on table public.user_security_settings from anon;
revoke all on table public.user_security_settings from authenticated;

grant select, insert, update, delete
on table public.user_security_settings
to service_role;

notify pgrst, 'reload schema';

commit;
