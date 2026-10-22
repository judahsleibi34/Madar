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
    raise exception using errcode = 'P0001', message = 'migration_147_schema_state_missing';
  end if;
  if v_schema_version <> 146 then
    raise exception using errcode = 'P0001',
      message = format('migration_147_expected_schema_146_got_%s', v_schema_version);
  end if;
end;
$$;

create unique index if not exists builder_projects_id_tenant_unique147
on public.builder_projects(id, tenant_id);

create unique index if not exists users_id_tenant_unique147
on public.users(id, tenant_id);

create unique index if not exists storage_objects_id_tenant_user_unique147
on public.storage_objects(id, tenant_id, user_id);

create table public.data_datasets (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  project_id uuid not null,
  creator_user_id integer not null,
  display_name text not null,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint data_datasets_project_tenant_fk147
    foreign key(project_id, tenant_id)
    references public.builder_projects(id, tenant_id)
    on delete cascade,
  constraint data_datasets_creator_tenant_fk147
    foreign key(creator_user_id, tenant_id)
    references public.users(id, tenant_id)
    on delete restrict,
  constraint data_datasets_display_name_check147
    check(length(btrim(display_name)) between 1 and 255),
  constraint data_datasets_status_check147
    check(status in ('active', 'archived', 'deleted')),
  constraint data_datasets_id_tenant_unique147 unique(id, tenant_id)
);

create trigger set_data_datasets_updated_at147
before update on public.data_datasets
for each row execute function public.set_updated_at();

create index data_datasets_project_owner147
on public.data_datasets(tenant_id, project_id, creator_user_id, updated_at desc)
where status = 'active';

create table public.data_dataset_versions (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  dataset_id uuid not null,
  version_number integer not null,
  storage_object_id uuid not null,
  created_by_user_id integer not null,
  version_kind text not null default 'original',
  original_filename text not null,
  content_type text not null,
  file_extension text not null,
  size_bytes bigint not null,
  content_hash text,
  file_metadata jsonb not null default '{}'::jsonb,
  provenance jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint data_dataset_versions_dataset_tenant_fk147
    foreign key(dataset_id, tenant_id)
    references public.data_datasets(id, tenant_id)
    on delete cascade,
  constraint data_dataset_versions_creator_tenant_fk147
    foreign key(created_by_user_id, tenant_id)
    references public.users(id, tenant_id)
    on delete restrict,
  constraint data_dataset_versions_storage_tenant_user_fk147
    foreign key(storage_object_id, tenant_id, created_by_user_id)
    references public.storage_objects(id, tenant_id, user_id)
    on delete restrict,
  constraint data_dataset_versions_number_unique147 unique(dataset_id, version_number),
  constraint data_dataset_versions_storage_unique147 unique(storage_object_id),
  constraint data_dataset_versions_number_check147 check(version_number > 0),
  constraint data_dataset_versions_kind_check147 check(version_kind in ('original', 'derived')),
  constraint data_dataset_versions_filename_check147
    check(length(btrim(original_filename)) between 1 and 255),
  constraint data_dataset_versions_extension_check147
    check(file_extension in ('.csv', '.xls', '.xlsx')),
  constraint data_dataset_versions_size_check147 check(size_bytes > 0),
  constraint data_dataset_versions_hash_check147
    check(content_hash is null or content_hash ~ '^[0-9a-f]{64}$'),
  constraint data_dataset_versions_metadata_object147
    check(jsonb_typeof(file_metadata) = 'object'),
  constraint data_dataset_versions_provenance_object147
    check(jsonb_typeof(provenance) = 'object')
);

create index data_dataset_versions_latest147
on public.data_dataset_versions(tenant_id, dataset_id, version_number desc);

alter table public.data_datasets enable row level security;
alter table public.data_dataset_versions enable row level security;

revoke all on public.data_datasets, public.data_dataset_versions
from public, anon, authenticated;
grant select, insert, update, delete
on public.data_datasets, public.data_dataset_versions
to service_role;

create function public.create_project_dataset_with_version147(
  p_tenant_id integer,
  p_project_id uuid,
  p_creator_user_id integer,
  p_display_name text,
  p_storage_object_id uuid,
  p_original_filename text,
  p_content_type text,
  p_file_extension text,
  p_size_bytes bigint,
  p_content_hash text,
  p_file_metadata jsonb default '{}'::jsonb
)
returns table(dataset_id uuid, version_id uuid, version_number integer)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_dataset_id uuid;
  v_version_id uuid;
  v_storage public.storage_objects;
begin
  if not exists(
    select 1
    from public.builder_projects p
    where p.id = p_project_id
      and p.tenant_id = p_tenant_id
      and p.status <> 'archived'
      and p.draft_schema->>'workspaceKind' = 'data'
  ) then
    raise exception using errcode = 'P0001', message = 'data_project_not_found';
  end if;

  if not exists(
    select 1
    from public.users u
    where u.id = p_creator_user_id
      and u.tenant_id = p_tenant_id
  ) then
    raise exception using errcode = 'P0001', message = 'dataset_creator_not_found';
  end if;

  select *
  into v_storage
  from public.storage_objects o
  where o.id = p_storage_object_id
  for update;

  if not found
     or v_storage.tenant_id <> p_tenant_id
     or v_storage.user_id is distinct from p_creator_user_id
     or v_storage.category <> 'dataset'
     or v_storage.status <> 'active'
     or v_storage.size_bytes <> p_size_bytes
     or v_storage.sha256 is distinct from p_content_hash then
    raise exception using errcode = 'P0001', message = 'dataset_storage_object_invalid';
  end if;

  insert into public.data_datasets(
    tenant_id, project_id, creator_user_id, display_name
  ) values (
    p_tenant_id, p_project_id, p_creator_user_id, btrim(p_display_name)
  ) returning id into v_dataset_id;

  insert into public.data_dataset_versions(
    tenant_id,
    dataset_id,
    version_number,
    storage_object_id,
    created_by_user_id,
    version_kind,
    original_filename,
    content_type,
    file_extension,
    size_bytes,
    content_hash,
    file_metadata,
    provenance
  ) values (
    p_tenant_id,
    v_dataset_id,
    1,
    p_storage_object_id,
    p_creator_user_id,
    'original',
    btrim(p_original_filename),
    btrim(p_content_type),
    lower(btrim(p_file_extension)),
    p_size_bytes,
    p_content_hash,
    coalesce(p_file_metadata, '{}'::jsonb),
    jsonb_build_object('kind', 'upload')
  ) returning id into v_version_id;

  return query select v_dataset_id, v_version_id, 1;
end;
$$;

revoke all on function public.create_project_dataset_with_version147(
  integer, uuid, integer, text, uuid, text, text, text, bigint, text, jsonb
) from public, anon, authenticated;
grant execute on function public.create_project_dataset_with_version147(
  integer, uuid, integer, text, uuid, text, text, text, bigint, text, jsonb
) to service_role;

update public.application_schema_state
set schema_version = 147, applied_at = now()
where contract_key = 'core';

notify pgrst, 'reload schema';
commit;
