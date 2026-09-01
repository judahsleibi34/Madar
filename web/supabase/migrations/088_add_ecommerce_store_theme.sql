begin;

-- Tenant-owned storefront color theme.
alter table public.website_settings
  add column if not exists ecommerce_theme jsonb not null default '{"accent":"#2463eb","background":"#ffffff","surface":"#f7f8fa","text":"#151821","muted":"#697181"}'::jsonb;

alter table public.website_settings
  drop constraint if exists website_settings_ecommerce_theme_check;

alter table public.website_settings
  add constraint website_settings_ecommerce_theme_check
  check (jsonb_typeof(ecommerce_theme) = 'object');

do $$
declare
  v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version
  into v_schema_version
  from public.application_schema_state
  where contract_key = 'core'
  for update;

  if v_schema_version is null then
    raise exception using
      errcode = 'P0001',
      message = 'migration_088_schema_state_missing';
  end if;

  if v_schema_version <> 87 then
    raise exception using
      errcode = 'P0001',
      message = format(
        'migration_088_expected_schema_87_got_%s',
        v_schema_version
      );
  end if;

  update public.application_schema_state
  set schema_version = 88,
      applied_at = now()
  where contract_key = 'core';
end;
$$;

notify pgrst, 'reload schema';
commit;
