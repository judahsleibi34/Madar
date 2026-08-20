/* ============================================================
   020_precheck_users_identity_duplicates.sql

   Purpose:
   - Stop migration if duplicated emails/auth_ids already exist.
   - Fix duplicates in seed/data before running the enforcement file.
   ============================================================ */

do $$
begin
  if exists (
    select 1
    from public.users
    where email is not null
    group by lower(trim(email))
    having count(*) > 1
  ) then
    raise exception 'Duplicate user emails exist in public.users. Clean them before adding unique email index.';
  end if;

  if exists (
    select 1
    from public.users
    where auth_id is not null
    group by auth_id
    having count(*) > 1
  ) then
    raise exception 'Duplicate auth_id values exist in public.users. Clean them before adding unique auth_id index.';
  end if;
end $$;