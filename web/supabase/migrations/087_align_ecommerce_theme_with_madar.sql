-- Move untouched ecommerce themes from the retired blue default to Madar's
-- brand palette. Custom tenant themes are deliberately left unchanged.
update public.website_settings
set ecommerce_theme = '{"accent":"#852c21","background":"#ffffff","surface":"#f5f1eb","text":"#162033","muted":"#667085"}'::jsonb
where ecommerce_theme = '{"accent":"#2463eb","background":"#ffffff","surface":"#f7f8fa","text":"#151821","muted":"#697181"}'::jsonb;

alter table public.website_settings
  alter column ecommerce_theme
  set default '{"accent":"#852c21","background":"#ffffff","surface":"#f5f1eb","text":"#162033","muted":"#667085"}'::jsonb;
