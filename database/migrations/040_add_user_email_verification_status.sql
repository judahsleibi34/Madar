alter table public.users
add column if not exists email_verified boolean not null default false;

alter table public.users
add column if not exists email_verified_at timestamp with time zone;

update public.users u
set
  email_verified = true,
  email_verified_at = coalesce(u.email_verified_at, au.email_confirmed_at, au.confirmed_at)
from auth.users au
where u.auth_id = au.id
  and (au.email_confirmed_at is not null or au.confirmed_at is not null);

comment on column public.users.email_verified is
  'True only after the account email has been verified.';

comment on column public.users.email_verified_at is
  'Timestamp when the local user email verification status was confirmed.';
