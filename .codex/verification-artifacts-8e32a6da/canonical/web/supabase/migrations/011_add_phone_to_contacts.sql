alter table public.contacts
add column if not exists phone text;

notify pgrst, 'reload schema';