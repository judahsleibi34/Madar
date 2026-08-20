alter table public.contacts
drop column if exists email;

notify pgrst, 'reload schema';