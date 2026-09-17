/* ============================================================
   020_enforce_unique_users_identity.sql

   Purpose:
   - Enforce one local user per Supabase Auth user
   - Enforce one local user per email
   - Normalize existing user emails
   - Prevent duplicated / overlapping accounts

   Push this using your normal migration flow.
   ============================================================ */

begin;

-- Normalize existing emails before enforcing uniqueness.
update public.users
set email = lower(trim(email))
where email is not null;

-- Required identity fields.
alter table public.users
alter column email set not null;

alter table public.users
alter column auth_id set not null;

-- One auth account = one local user row.
create unique index if not exists users_auth_id_unique_idx
on public.users (auth_id);

-- One email = one local user row.
-- This is case-insensitive and ignores leading/trailing spaces.
create unique index if not exists users_email_normalized_unique_idx
on public.users (lower(trim(email)));

commit;