alter table public.users
add column if not exists password_reset_requested_at timestamp with time zone;

comment on column public.users.password_reset_requested_at is
  'Timestamp of the latest password reset email request. Used to enforce the app reset window.';
