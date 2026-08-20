-- Harden the public-site publication boundary and make republish/binding atomic.
begin;

create table if not exists public.publication_integrity_reviews (
  id bigint generated always as identity primary key,
  tenant_id integer references public.tenants(tenant_id) on delete cascade,
  website_settings_id bigint,
  project_id uuid references public.builder_projects(id) on delete cascade,
  issue_code text not null,
  source text not null default 'migration_072',
  details jsonb not null default '{}'::jsonb,
  review_status text not null default 'pending',
  created_at timestamptz not null default now(),
  resolved_at timestamptz,
  constraint publication_integrity_reviews_status_check
    check (review_status in ('pending', 'resolved', 'dismissed'))
);

create unique index if not exists publication_integrity_reviews_open_issue_unique
on public.publication_integrity_reviews (
  coalesce(website_settings_id, 0),
  coalesce(project_id, '00000000-0000-0000-0000-000000000000'::uuid),
  issue_code,
  source
)
where review_status = 'pending';

alter table public.publication_integrity_reviews enable row level security;
revoke all on public.publication_integrity_reviews from public, anon, authenticated;
grant select, insert, update, delete on public.publication_integrity_reviews to service_role;
grant usage, select on sequence public.publication_integrity_reviews_id_seq to service_role;

create or replace function public.builder_publication_integrity_error(p_schema jsonb)
returns text
language plpgsql
immutable
strict
set search_path = public
as $$
declare
  pages jsonb;
  default_page_id text;
  root_count integer;
  default_id_count integer;
  flagged_count integer;
  flagged_matching_count integer;
begin
  if jsonb_typeof(p_schema) <> 'object' then return 'schema_not_object'; end if;
  pages := p_schema -> 'pages';
  if jsonb_typeof(pages) <> 'array' or jsonb_array_length(pages) = 0 then
    return 'pages_missing';
  end if;
  if exists (
    select 1 from jsonb_array_elements(pages) page
    where jsonb_typeof(page) <> 'object' or btrim(page ->> 'id') = ''
  ) then return 'page_id_missing'; end if;
  if exists (
    select 1
    from (
      select btrim(page ->> 'id') id, count(*) amount
      from jsonb_array_elements(pages) page
      group by btrim(page ->> 'id')
      having count(*) <> 1
    ) duplicate
  ) then return 'page_id_duplicate'; end if;

  default_page_id := btrim(coalesce(p_schema ->> 'defaultPageId', ''));
  if default_page_id = '' then return 'homepage_id_missing'; end if;
  select count(*) into default_id_count
  from jsonb_array_elements(pages) page
  where btrim(page ->> 'id') = default_page_id;
  if default_id_count <> 1 then return 'homepage_id_invalid'; end if;

  select count(*) into root_count
  from jsonb_array_elements(pages) page
  where btrim(coalesce(page ->> 'slug', page ->> 'path', page ->> 'route', '')) = '/';
  if root_count <> 1 then return 'homepage_route_ambiguous'; end if;
  if not exists (
    select 1 from jsonb_array_elements(pages) page
    where btrim(page ->> 'id') = default_page_id
      and btrim(coalesce(page ->> 'slug', page ->> 'path', page ->> 'route', '')) = '/'
  ) then return 'homepage_route_mismatch'; end if;

  select
    count(*) filter (
      where coalesce((page ->> 'isDefault')::boolean, (page ->> 'is_default')::boolean, false)
    ),
    count(*) filter (
      where coalesce((page ->> 'isDefault')::boolean, (page ->> 'is_default')::boolean, false)
        and btrim(page ->> 'id') = default_page_id
    )
  into flagged_count, flagged_matching_count
  from jsonb_array_elements(pages) page;
  if flagged_count > 0 and (flagged_count <> 1 or flagged_matching_count <> 1) then
    return 'homepage_flag_mismatch';
  end if;

  if exists (
    select 1
    from (
      select lower('/' || btrim(coalesce(page ->> 'slug', page ->> 'path', page ->> 'route', ''), '/')) route,
             count(*) amount
      from jsonb_array_elements(pages) page
      group by 1
      having count(*) <> 1
    ) duplicate
  ) then return 'page_route_duplicate'; end if;

  if p_schema ? 'forms' then
    if coalesce(jsonb_typeof(p_schema -> 'forms'), 'null') <> 'array' then
      return 'forms_invalid';
    end if;
    if exists (
      select 1 from jsonb_array_elements(p_schema -> 'forms') form
      where jsonb_typeof(form) <> 'object' or btrim(coalesce(form ->> 'id', '')) = ''
    ) then return 'form_id_missing'; end if;
    if exists (
      select 1
      from (
        select btrim(form ->> 'id') id, count(*) amount
        from jsonb_array_elements(p_schema -> 'forms') form
        group by btrim(form ->> 'id')
        having count(*) <> 1
      ) duplicate
    ) then return 'form_id_duplicate'; end if;
  end if;
  return null;
exception
  when invalid_text_representation then return 'homepage_flag_invalid';
end;
$$;

revoke all on function public.builder_publication_integrity_error(jsonb)
from public, anon, authenticated;
grant execute on function public.builder_publication_integrity_error(jsonb) to service_role;

-- Repair only the unambiguous legacy case: no defaultPageId and exactly one
-- root page. This preserves the existing rendered homepage and increments the
-- publication version so every cache boundary changes.
with repairable as (
  select
    project.id,
    root_page ->> 'id' homepage_id
  from public.builder_projects project
  cross join lateral (
    select page root_page
    from jsonb_array_elements(project.published_schema -> 'pages') page
    where btrim(coalesce(page ->> 'slug', page ->> 'path', page ->> 'route', '')) = '/'
    limit 2
  ) root
  where project.published_schema is not null
    and jsonb_typeof(project.published_schema) = 'object'
    and jsonb_typeof(project.published_schema -> 'pages') = 'array'
    and btrim(coalesce(project.published_schema ->> 'defaultPageId', '')) = ''
    and (
      select count(*)
      from jsonb_array_elements(project.published_schema -> 'pages') page
      where btrim(coalesce(page ->> 'slug', page ->> 'path', page ->> 'route', '')) = '/'
    ) = 1
)
update public.builder_projects project
set published_schema = jsonb_set(project.published_schema, '{defaultPageId}', to_jsonb(repairable.homepage_id), true),
    published_version = project.published_version + 1,
    updated_at = now()
from repairable
where project.id = repairable.id;

insert into public.publication_integrity_reviews (
  tenant_id, website_settings_id, project_id, issue_code, details
)
select
  project.tenant_id,
  settings.id,
  project.id,
  public.builder_publication_integrity_error(project.published_schema),
  jsonb_build_object(
    'published_version', project.published_version,
    'published_revision', project.published_revision,
    'bound_project_id', settings.published_project_id
  )
from public.builder_projects project
left join public.website_settings settings
  on settings.tenant_id = project.tenant_id
 and settings.published_project_id = project.id
where project.published_schema is not null
  and public.builder_publication_integrity_error(project.published_schema) is not null
on conflict do nothing;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'builder_projects_publication_integrity_check'
      and conrelid = 'public.builder_projects'::regclass
  ) then
    alter table public.builder_projects
      add constraint builder_projects_publication_integrity_check
      check (
        published_schema is null
        or public.builder_publication_integrity_error(published_schema) is null
      ) not valid;
  end if;
end
$$;

-- Preserve the existing RPC signature while extending its transaction to lock
-- the site's binding and validate the complete immutable snapshot.
create or replace function public.publish_validated_builder_project_atomic(
  p_project_id uuid,
  p_tenant_id integer,
  p_expected_revision bigint,
  p_published_schema jsonb,
  p_published_at timestamptz,
  p_schema_version integer default 1,
  p_require_active_entitlement boolean default false
)
returns public.builder_projects
language plpgsql
security definer
set search_path = public
as $$
declare
  current_project public.builder_projects;
  current_settings public.website_settings;
begin
  select * into current_project
  from public.builder_projects
  where id = p_project_id and tenant_id = p_tenant_id
  for update;

  if not found or current_project.status = 'archived' then
    raise exception using errcode = 'P0002', message = 'builder_project_not_found';
  end if;
  if current_project.draft_revision <> p_expected_revision then
    raise exception using errcode = 'P0001', message = 'project_revision_conflict';
  end if;
  if public.builder_publication_integrity_error(p_published_schema) is not null then
    raise exception using
      errcode = 'P0001',
      message = 'publish_validation_failed',
      detail = public.builder_publication_integrity_error(p_published_schema);
  end if;
  if p_require_active_entitlement and not exists (
    select 1
    from public.features feature
    where feature.tenant_id = p_tenant_id
      and feature.payment_status = 'active'
      and (
        feature.subscription_type = 'full_platform'
        or (
          feature.subscription_type = 'individual_builder'
          and feature.builder_type = 'website'
        )
      )
  ) then
    raise exception using errcode = 'P0001', message = 'entitlement_inactive';
  end if;

  select * into current_settings
  from public.website_settings
  where tenant_id = p_tenant_id
  for update;

  update public.builder_projects
  set published_schema = p_published_schema,
      published_version = current_project.published_version + 1,
      published_revision = current_project.draft_revision,
      schema_version = p_schema_version,
      last_published_at = p_published_at,
      status = 'published'
  where id = p_project_id and tenant_id = p_tenant_id
  returning * into current_project;

  if current_settings.id is not null and (
    current_settings.published_project_id = p_project_id
    or (
      current_settings.published_project_id is null
      and not exists (
        select 1
        from public.builder_projects other
        where other.tenant_id = p_tenant_id
          and other.id <> p_project_id
          and other.status = 'published'
          and other.published_schema is not null
      )
    )
  ) then
    update public.website_settings
    set published_project_id = p_project_id
    where id = current_settings.id
      and tenant_id = p_tenant_id;
  end if;

  return current_project;
end;
$$;

revoke all on function public.publish_validated_builder_project_atomic(
  uuid, integer, bigint, jsonb, timestamptz, integer, boolean
) from public, anon, authenticated;
grant execute on function public.publish_validated_builder_project_atomic(
  uuid, integer, bigint, jsonb, timestamptz, integer, boolean
) to service_role;

notify pgrst, 'reload schema';
commit;
