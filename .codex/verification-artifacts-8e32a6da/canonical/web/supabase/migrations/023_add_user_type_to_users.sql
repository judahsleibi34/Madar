alter table public.users
add column if not exists user_type text not null default 'user';

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'users_user_type_check'
  ) then
    alter table public.users
    add constraint users_user_type_check
    check (user_type in ('admin', 'user'));
  end if;
end $$;

update public.users
set user_type = 'admin'
where lower(email) = lower('judahsleibi34@gmail.com');

update public.users
set user_type = 'user'
where lower(email) <> lower('judahsleibi34@gmail.com')
  and user_type is distinct from 'user';