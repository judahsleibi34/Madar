begin;

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
    raise exception using errcode = 'P0001', message = 'migration_148_schema_state_missing';
  end if;
  if v_schema_version <> 147 then
    raise exception using errcode = 'P0001',
      message = format('migration_148_expected_schema_147_got_%s', v_schema_version);
  end if;
end;
$$;

create table public.data_sources (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  project_id uuid not null,
  creator_user_id integer not null,
  source_type text not null,
  display_name text not null,
  display_name_key text generated always as (lower(btrim(display_name))) stored,
  status text not null default 'active',
  sync_mode text not null default 'manual',
  sync_state text not null default 'idle',
  latest_dataset_id uuid,
  latest_version_id uuid,
  last_ingested_at timestamptz,
  last_successful_sync_at timestamptz,
  last_error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint data_sources_project_tenant_fk148
    foreign key(project_id, tenant_id)
    references public.builder_projects(id, tenant_id)
    on delete cascade,
  constraint data_sources_creator_tenant_fk148
    foreign key(creator_user_id, tenant_id)
    references public.users(id, tenant_id)
    on delete restrict,
  constraint data_sources_type_check148
    check(source_type in ('spreadsheet_upload')),
  constraint data_sources_name_check148
    check(length(btrim(display_name)) between 1 and 255),
  constraint data_sources_status_check148
    check(status in ('active', 'archived')),
  constraint data_sources_sync_mode_check148
    check(sync_mode in ('manual')),
  constraint data_sources_sync_state_check148
    check(sync_state in ('idle', 'disabled', 'error')),
  constraint data_sources_last_error_code_check148
    check(last_error_code is null or length(last_error_code) between 1 and 120),
  constraint data_sources_latest_pair_check148
    check((latest_dataset_id is null) = (latest_version_id is null)),
  constraint data_sources_id_tenant_unique148 unique(id, tenant_id),
  constraint data_sources_id_tenant_project_unique148 unique(id, tenant_id, project_id)
);

create trigger set_data_sources_updated_at148
before update on public.data_sources
for each row execute function public.set_updated_at();

create unique index data_sources_active_name_unique148
on public.data_sources(tenant_id, project_id, source_type, display_name_key)
where status = 'active';

create index data_sources_project_active148
on public.data_sources(tenant_id, project_id, creator_user_id, updated_at desc)
where status = 'active';

alter table public.data_datasets
  add column source_id uuid;

alter table public.data_datasets
  add constraint data_datasets_id_tenant_project_unique148
    unique(id, tenant_id, project_id),
  add constraint data_datasets_source_project_tenant_fk148
    foreign key(source_id, tenant_id, project_id)
    references public.data_sources(id, tenant_id, project_id)
    on delete restrict;

alter table public.data_dataset_versions
  add constraint data_dataset_versions_id_dataset_tenant_unique148
    unique(id, dataset_id, tenant_id);

alter table public.data_sources
  add constraint data_sources_latest_dataset_fk148
    foreign key(latest_dataset_id, tenant_id, project_id)
    references public.data_datasets(id, tenant_id, project_id)
    on delete restrict,
  add constraint data_sources_latest_version_fk148
    foreign key(latest_version_id, latest_dataset_id, tenant_id)
    references public.data_dataset_versions(id, dataset_id, tenant_id)
    on delete restrict;

alter table public.data_sources enable row level security;

revoke all on public.data_sources from public, anon, authenticated;
grant select, insert, update, delete on public.data_sources to service_role;

update public.application_schema_state
set schema_version = 148, applied_at = now()
where contract_key = 'core';

notify pgrst, 'reload schema';
commit;
