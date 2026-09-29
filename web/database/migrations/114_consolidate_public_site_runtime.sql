begin;

-- The service-role backend remains responsible for hostname validation, session
-- authentication, entitlement checks, and public-schema redaction. This function
-- only combines the current tenant, site binding, and published snapshot reads.
create or replace function public.get_public_site_runtime_context(
  p_identifier text,
  p_allow_legacy_alias boolean default false
)
returns table (
  settings jsonb,
  tenant_active boolean,
  project jsonb
)
language sql
stable
security invoker
set search_path = ''
as $function$
  with canonical as (
    select s.*
    from public.website_settings as s
    where s.subdomain = lower(p_identifier)
    limit 2
  ), matching as (
    select * from canonical
    union all
    select s.*
    from public.website_settings as s
    where p_allow_legacy_alias
      and not exists (select 1 from canonical)
      and lower(s.standard_path_slug) = lower(p_identifier)
    limit 2
  )
  select
    jsonb_build_object(
      'id', s.id,
      'tenant_id', s.tenant_id,
      'subdomain', s.subdomain,
      'standard_path_slug', s.standard_path_slug,
      'published_project_id', s.published_project_id,
      'user_id', to_jsonb(s)->'user_id',
      'brand', to_jsonb(s)->'brand',
      'footer_store_name', to_jsonb(s)->'footer_store_name',
      'logo_url', to_jsonb(s)->'logo_url',
      'loading_image_url', to_jsonb(s)->'loading_image_url',
      'contact_email', to_jsonb(s)->'contact_email',
      'phone', to_jsonb(s)->'phone',
      'description', to_jsonb(s)->'description',
      'ecommerce_theme', to_jsonb(s)->'ecommerce_theme'
    ),
    coalesce(t.lifecycle_state = 'active', false),
    case when p.id is not null then jsonb_build_object(
      'id', p.id,
      'tenant_id', p.tenant_id,
      'name', p.name,
      'slug', p.slug,
      'status', p.status,
      'published_schema', p.published_schema,
      'published_version', p.published_version,
      'published_revision', p.published_revision,
      'schema_version', p.schema_version,
      'last_published_at', p.last_published_at,
      'updated_at', p.updated_at
    ) end
  from matching as s
  left join public.tenants as t on t.tenant_id = s.tenant_id
  left join public.builder_projects as p
    on p.id = s.published_project_id
   and p.tenant_id = s.tenant_id
   and p.status = 'published'
   and p.published_schema is not null
  where p_identifier ~ '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$';
$function$;

revoke all on function public.get_public_site_runtime_context(text, boolean)
  from public, anon, authenticated;
grant execute on function public.get_public_site_runtime_context(text, boolean)
  to service_role;

do $$
declare
  v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version into v_schema_version
  from public.application_schema_state
  where contract_key = 'core'
  for update;
  if v_schema_version is null then
    raise exception using errcode = 'P0001',
      message = 'migration_114_schema_state_missing';
  end if;
  if v_schema_version <> 113 then
    raise exception using errcode = 'P0001',
      message = format('migration_114_expected_schema_113_got_%s', v_schema_version);
  end if;
  update public.application_schema_state
  set schema_version = 114, applied_at = now()
  where contract_key = 'core';
end;
$$;

notify pgrst, 'reload schema';
commit;
