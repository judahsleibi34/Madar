-- READ-ONLY public-site isolation diagnostic.
-- Run with a read-only database role:
-- psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
--   -v site_identifier='palcode-slug' \
--   -v project_id='22ca8aa2-a2f5-4ad0-97b5-a1709714f74c' \
--   -f database/verification/072_publication_isolation_diagnostic.sql
-- Do not paste page contents into tickets; this report returns identifiers and
-- structural hashes only.

begin transaction read only;

with params as (
  select lower(btrim(:'site_identifier')) identifier,
         nullif(btrim(:'project_id'), '')::uuid inspected_project_id
),
host_matches as (
  select
    settings.id website_settings_id,
    settings.tenant_id,
    settings.subdomain,
    settings.standard_path_slug,
    settings.published_project_id,
    case
      when lower(settings.subdomain) = params.identifier then 'subdomain'
      when lower(settings.standard_path_slug) = params.identifier then 'standard_path'
    end match_kind
  from public.website_settings settings
  cross join params
  where lower(settings.subdomain) = params.identifier
     or lower(settings.standard_path_slug) = params.identifier
)
select * from host_matches order by website_settings_id;

with params as (
  select lower(btrim(:'site_identifier')) identifier
),
resolved as (
  select settings.*
  from public.website_settings settings, params
  where lower(settings.subdomain) = params.identifier
     or lower(settings.standard_path_slug) = params.identifier
),
bound as (
  select
    settings.id website_settings_id,
    settings.tenant_id settings_tenant_id,
    settings.published_project_id,
    project.id project_id,
    project.tenant_id project_tenant_id,
    project.status,
    project.published_version,
    project.published_revision,
    project.last_published_at,
    public.builder_publication_integrity_error(project.published_schema) integrity_error,
    encode(digest(project.published_schema::text, 'sha256'), 'hex') schema_hash,
    project.published_schema ->> 'defaultPageId' homepage_id,
    project.published_schema #>> '{siteChrome,brand}' chrome_brand,
    project.published_schema #>> '{siteChrome,loadingImageUrl}' loading_asset
  from resolved settings
  left join public.builder_projects project on project.id = settings.published_project_id
)
select * from bound order by website_settings_id, project_id;

-- Every published snapshot owned by the resolved tenant. Only the exact
-- published_project_id is active for the site; the others are shown so an
-- operator can compare structural hashes without exposing page bodies.
with params as (
  select lower(btrim(:'site_identifier')) identifier
),
resolved as (
  select settings.*
  from public.website_settings settings, params
  where lower(settings.subdomain) = params.identifier
     or lower(settings.standard_path_slug) = params.identifier
)
select
  settings.id website_settings_id,
  project.tenant_id,
  project.id project_id,
  project.status,
  project.published_version,
  project.published_revision,
  project.last_published_at,
  (project.id = settings.published_project_id) as is_active_binding,
  project.published_schema ->> 'defaultPageId' homepage_id,
  encode(digest(project.published_schema::text, 'sha256'), 'hex') schema_hash
from resolved settings
join public.builder_projects project on project.tenant_id = settings.tenant_id
where project.status = 'published' and project.published_schema is not null
order by website_settings_id, is_active_binding desc, project.last_published_at desc nulls last, project_id;

with params as (
  select nullif(btrim(:'project_id'), '')::uuid inspected_project_id
),
pages as (
  select
    project.tenant_id,
    project.id project_id,
    project.published_version,
    project.published_schema ->> 'defaultPageId' configured_homepage_id,
    page ->> 'id' page_id,
    page ->> 'slug' page_slug,
    coalesce((page ->> 'isDefault')::boolean, (page ->> 'is_default')::boolean, false) homepage_flag,
    jsonb_array_length(coalesce(page -> 'sections', '[]'::jsonb)) section_count,
    encode(digest(page::text, 'sha256'), 'hex') page_hash
  from public.builder_projects project
  cross join lateral jsonb_array_elements(coalesce(project.published_schema -> 'pages', '[]'::jsonb)) page
  cross join params
  where project.id = params.inspected_project_id
)
select * from pages order by page_slug, page_id;

-- Duplicate page IDs, normalized slugs, and homepage candidates in every bound
-- published snapshot. Any returned row requires review; none is selected first.
with bound as (
  select settings.id website_settings_id, project.*
  from public.website_settings settings
  join public.builder_projects project on project.id = settings.published_project_id
),
pages as (
  select bound.website_settings_id, bound.tenant_id, bound.id project_id,
         bound.published_version, bound.published_schema ->> 'defaultPageId' default_page_id,
         page
  from bound
  cross join lateral jsonb_array_elements(coalesce(bound.published_schema -> 'pages', '[]'::jsonb)) page
)
select
  website_settings_id,
  tenant_id,
  project_id,
  'duplicate_page_id' issue,
  page ->> 'id' value,
  count(*) amount
from pages
group by website_settings_id, tenant_id, project_id, page ->> 'id'
having count(*) > 1
union all
select
  website_settings_id,
  tenant_id,
  project_id,
  'duplicate_page_slug',
  lower('/' || btrim(coalesce(page ->> 'slug', page ->> 'path', page ->> 'route', ''), '/')),
  count(*)
from pages
group by website_settings_id, tenant_id, project_id,
         lower('/' || btrim(coalesce(page ->> 'slug', page ->> 'path', page ->> 'route', ''), '/'))
having count(*) > 1
union all
select
  website_settings_id,
  tenant_id,
  project_id,
  'homepage_candidate_count',
  string_agg(coalesce(page ->> 'id', '<missing>'), ',' order by page ->> 'id'),
  count(*)
from pages
where page ->> 'id' = default_page_id
   or btrim(coalesce(page ->> 'slug', page ->> 'path', page ->> 'route', '')) = '/'
   or coalesce((page ->> 'isDefault')::boolean, (page ->> 'is_default')::boolean, false)
group by website_settings_id, tenant_id, project_id
having count(*) <> 1
order by project_id, issue, value;

-- Orphaned and cross-tenant bindings.
select
  settings.id website_settings_id,
  settings.tenant_id settings_tenant_id,
  settings.published_project_id,
  project.tenant_id project_tenant_id,
  project.status,
  case
    when project.id is null then 'orphaned_project'
    when project.tenant_id <> settings.tenant_id then 'cross_tenant_project'
    when project.status <> 'published' then 'not_published'
    when project.published_schema is null then 'missing_snapshot'
  end issue
from public.website_settings settings
left join public.builder_projects project on project.id = settings.published_project_id
where settings.published_project_id is not null
  and (
    project.id is null
    or project.tenant_id <> settings.tenant_id
    or project.status <> 'published'
    or project.published_schema is null
  );

-- Source-boundary inventory: header, footer, loading screen, body, forms and
-- reservations all resolve from this one project snapshot/version.
with params as (
  select nullif(btrim(:'project_id'), '')::uuid inspected_project_id
),
project as (
  select * from public.builder_projects, params where id = params.inspected_project_id
),
homepage as (
  select page
  from project
  cross join lateral jsonb_array_elements(coalesce(project.published_schema -> 'pages', '[]'::jsonb)) page
  where page ->> 'id' = project.published_schema ->> 'defaultPageId'
)
select
  project.tenant_id,
  project.id project_id,
  project.published_version,
  project.published_revision,
  project.published_schema ->> 'defaultPageId' homepage_id,
  encode(digest((project.published_schema -> 'siteChrome')::text, 'sha256'), 'hex') header_footer_loading_hash,
  encode(digest(homepage.page::text, 'sha256'), 'hex') homepage_body_hash,
  jsonb_array_length(coalesce(project.published_schema -> 'forms', '[]'::jsonb)) form_count,
  (
    select count(*)
    from jsonb_path_query(project.published_schema, '$.** ? (@.type == "reservationBlock")')
  ) reservation_block_count
from project
left join homepage on true;

rollback;
