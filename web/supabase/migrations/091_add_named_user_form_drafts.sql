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

insert into public.application_schema_state(contract_key, schema_version, applied_at)
values ('core', 91, now())
on conflict(contract_key) do update
set schema_version = excluded.schema_version,
    applied_at = excluded.applied_at;

notify pgrst, 'reload schema';
commit;
