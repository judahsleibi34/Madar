begin;

-- Move untouched ecommerce themes from the retired blue default to Madar's
-- brand palette. Custom tenant themes are deliberately left unchanged.
update public.website_settings
set ecommerce_theme = '{"accent":"#852c21","background":"#ffffff","surface":"#f5f1eb","text":"#162033","muted":"#667085"}'::jsonb
where ecommerce_theme = '{"accent":"#2463eb","background":"#ffffff","surface":"#f7f8fa","text":"#151821","muted":"#697181"}'::jsonb;

alter table public.website_settings
  alter column ecommerce_theme
  set default '{"accent":"#852c21","background":"#ffffff","surface":"#f5f1eb","text":"#162033","muted":"#667085"}'::jsonb;

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
      message = 'migration_089_schema_state_missing';
  end if;

  if v_schema_version <> 88 then
    raise exception using
      errcode = 'P0001',
      message = format(
        'migration_089_expected_schema_88_got_%s',
        v_schema_version
      );
  end if;

  update public.application_schema_state
  set schema_version = 89,
      applied_at = now()
  where contract_key = 'core';
end;
$$;

notify pgrst, 'reload schema';
commit;
