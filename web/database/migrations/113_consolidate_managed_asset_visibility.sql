begin;

-- This RPC supplies context, not an anonymous authorization decision. The
-- backend continues to filter the published schema for protected resources.
-- Its invoker is the backend service role; no browser role may execute it.
create or replace function public.get_managed_asset_visibility_context(
  p_tenant_id integer,
  p_storage_key text
)
returns table (
  asset_status text,
  metadata jsonb,
  settings jsonb,
  published_schema jsonb
)
language sql
stable
security invoker
set search_path = ''
as $function$
  select
    a.status,
    a.metadata,
    case when s.tenant_id is not null then jsonb_build_object(
      'subdomain', s.subdomain,
      'standard_path_slug', s.standard_path_slug,
      'logo_url', s.logo_url,
      'loading_image_url', to_jsonb(s)->'loading_image_url',
      'ecommerce_theme', s.ecommerce_theme
    ) end,
    publication.published_schema
  from public.builder_assets as a
  left join public.website_settings as s
    on s.tenant_id = a.tenant_id
  left join lateral (
    select p.published_schema
    from public.builder_projects as p
    where p.id = s.published_project_id
      and p.tenant_id = a.tenant_id
      and p.status = 'published'
      and p.published_schema is not null
      and (
        nullif(s.subdomain, '') is not null
        or nullif(s.standard_path_slug, '') is not null
      )
      and exists (
        select 1
        from public.builder_asset_references as r
        where r.asset_id = a.id
          and r.project_id = p.id
      )
    limit 1
  ) as publication on true
  where p_tenant_id > 0
    and a.tenant_id = p_tenant_id
    and a.storage_key = p_storage_key
    and left(p_storage_key, length('tenant_' || p_tenant_id::text || '/builder_assets/'))
      = 'tenant_' || p_tenant_id::text || '/builder_assets/'
    and a.status in ('active', 'unreferenced')
  limit 1;
$function$;

revoke all on function public.get_managed_asset_visibility_context(integer, text)
  from public, anon, authenticated;
grant execute on function public.get_managed_asset_visibility_context(integer, text)
  to service_role;

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
    raise exception using errcode = 'P0001',
      message = 'migration_113_schema_state_missing';
  end if;

  if v_schema_version <> 112 then
    raise exception using errcode = 'P0001',
      message = format('migration_113_expected_schema_112_got_%s', v_schema_version);
  end if;

  update public.application_schema_state
  set schema_version = 113,
      applied_at = now()
  where contract_key = 'core';
end;
$$;

notify pgrst, 'reload schema';

commit;
