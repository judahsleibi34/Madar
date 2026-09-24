begin;

alter table public.ecommerce_categories
  add column image_url text;

alter table public.ecommerce_categories
  add constraint ecommerce_categories_image_url_check
  check (
    image_url is null
    or (
      image_url = btrim(image_url)
      and char_length(image_url) between 1 and 2048
      and (
        image_url ~ '^/uploads/tenant_[1-9][0-9]*/builder_assets/[a-f0-9]{32}[.](png|jpg|webp)$'
        or image_url ~* '^https://'
      )
    )
  );

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
      message = 'migration_107_schema_state_missing';
  end if;

  if v_schema_version <> 106 then
    raise exception using
      errcode = 'P0001',
      message = format('migration_107_expected_schema_106_got_%s', v_schema_version);
  end if;

  update public.application_schema_state
  set schema_version = 107,
      applied_at = now()
  where contract_key = 'core';
end;
$$;

notify pgrst, 'reload schema';

commit;
