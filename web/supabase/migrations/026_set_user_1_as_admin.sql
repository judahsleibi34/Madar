update public.users
set user_type = 'admin'
where id = 1;

update public.users
set user_type = 'user'
where id <> 1
  and user_type is distinct from 'user';