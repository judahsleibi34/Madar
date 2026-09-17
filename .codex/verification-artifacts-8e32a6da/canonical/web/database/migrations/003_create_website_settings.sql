CREATE TABLE IF NOT EXISTS public.website_settings (
  id integer generated always as identity primary key,
  user_id integer not null unique references public.users(id) on delete cascade,
  subdomain text unique,
  brand text,
  footer_store_name text,
  logo_url text,
  contact_email text,
  phone text,
  description text,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

DROP TRIGGER IF EXISTS set_website_settings_updated_at ON public.website_settings;

CREATE TRIGGER set_website_settings_updated_at
BEFORE UPDATE ON public.website_settings
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.website_settings DISABLE ROW LEVEL SECURITY;

GRANT ALL ON public.website_settings TO anon;
GRANT ALL ON public.website_settings TO authenticated;
GRANT ALL ON public.website_settings TO service_role;
