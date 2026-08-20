begin;

-- Historical broad grants can leave non-DML privileges such as TRUNCATE,
-- TRIGGER, and REFERENCES behind. Reset these backend-owned tables completely
-- before restoring the one intentional authenticated privilege.
revoke all privileges on table public.users from authenticated;
revoke all privileges on table public.builder_projects from authenticated;
revoke all privileges on table public.website_settings from authenticated;

grant select on table public.users to authenticated;
grant select on table public.builder_projects to authenticated;
grant select on table public.website_settings to authenticated;

notify pgrst, 'reload schema';

commit;
