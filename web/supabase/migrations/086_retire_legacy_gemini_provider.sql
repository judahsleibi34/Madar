begin;

-- Retire the legacy Gemini AI-provider pricing metadata.
--
-- Migration 071 remains immutable because it records the historical schema
-- transition that originally introduced this catalog row. Madar no longer
-- supports Gemini at runtime, so the historical multiplier must not remain
-- eligible for new token-metering decisions.

update public.ai_token_model_multipliers
set active = false
where lower(provider) = 'gemini'
  and active is distinct from false;

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
      message = 'migration_086_schema_state_missing';
  end if;

  if v_schema_version <> 85 then
    raise exception using
      errcode = 'P0001',
      message = format(
        'migration_086_expected_schema_85_got_%s',
        v_schema_version
      );
  end if;

  update public.application_schema_state
  set schema_version = 86,
      applied_at = now()
  where contract_key = 'core';
end;
$$;

commit;
