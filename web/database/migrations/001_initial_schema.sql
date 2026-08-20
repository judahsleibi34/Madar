CREATE TABLE IF NOT EXISTS public.users (
  id integer generated always as identity primary key,
  auth_id uuid unique references auth.users(id) on delete cascade,
  first_name text not null,
  last_name text not null,
  email text not null unique,
  phone text,
  avatar text,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_users_updated_at ON public.users;

CREATE TRIGGER set_users_updated_at
BEFORE UPDATE ON public.users
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE IF NOT EXISTS public.contacts (
  id integer generated always as identity primary key,
  name text not null,
  email text not null,
  message text not null,
  created_at timestamp with time zone default now()
);

ALTER TABLE public.users DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.contacts DISABLE ROW LEVEL SECURITY;

GRANT ALL ON public.users TO anon;
GRANT ALL ON public.users TO authenticated;
GRANT ALL ON public.users TO service_role;

GRANT ALL ON public.contacts TO anon;
GRANT ALL ON public.contacts TO authenticated;
GRANT ALL ON public.contacts TO service_role;