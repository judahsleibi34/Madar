begin;

alter table public.users
  add column if not exists terms_accepted_at timestamp with time zone;

alter table public.users
  add column if not exists terms_version text;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'users_terms_acceptance_complete_check'
      and conrelid = 'public.users'::regclass
  ) then
    alter table public.users
      add constraint users_terms_acceptance_complete_check
      check (
        (terms_accepted_at is null and terms_version is null)
        or (
          terms_accepted_at is not null
          and terms_version is not null
          and btrim(terms_version) <> ''
        )
      );
  end if;
end
$$;

comment on column public.users.terms_accepted_at is
  'Server-recorded timestamp when the user accepted the Terms and Conditions.';

comment on column public.users.terms_version is
  'Version identifier of the Terms and Conditions accepted by the user.';

notify pgrst, 'reload schema';

commit;
