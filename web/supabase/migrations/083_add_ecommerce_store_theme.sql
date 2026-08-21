-- Tenant-owned storefront color theme.
begin;

alter table public.website_settings
  add column if not exists ecommerce_theme jsonb not null default '{"accent":"#2463eb","background":"#ffffff","surface":"#f7f8fa","text":"#151821","muted":"#697181"}'::jsonb;

alter table public.website_settings
  drop constraint if exists website_settings_ecommerce_theme_check;

alter table public.website_settings
  add constraint website_settings_ecommerce_theme_check
  check (jsonb_typeof(ecommerce_theme) = 'object');

commit;