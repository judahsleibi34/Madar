begin;

alter table public.builder_form_drafts
  add column if not exists draft_name text;

update public.builder_form_drafts
set draft_name = left(
  coalesce(nullif(btrim(form_title), ''), 'Incomplete form'),
  120
)
where draft_name is null or btrim(draft_name) = '';

alter table public.builder_form_drafts
  alter column draft_name set not null;

alter table public.builder_form_drafts
  drop constraint if exists builder_form_drafts_name_check;
alter table public.builder_form_drafts
  add constraint builder_form_drafts_name_check
  check (char_length(btrim(draft_name)) between 1 and 120);

create index if not exists builder_form_drafts_user_form_idx
  on public.builder_form_drafts (
    tenant_id,
    site_user_id,
    project_id,
    form_id,
    updated_at desc
  )
  where site_user_id is not null;

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
      message = 'migration_091_schema_state_missing';
  end if;

  if v_schema_version <> 90 then
    raise exception using
      errcode = 'P0001',
      message = format(
        'migration_091_expected_schema_90_got_%s',
        v_schema_version
      );
  end if;

  update public.application_schema_state
  set schema_version = 91,
      applied_at = now()
  where contract_key = 'core';
end;
$$;

notify pgrst, 'reload schema';
commit;
