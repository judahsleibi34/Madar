alter table public.contacts
alter column email drop not null;

notify pgrst, 'reload schema';