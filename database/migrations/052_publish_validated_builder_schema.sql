-- Publish the exact backend-validated schema under the locked draft revision.

revoke all on function public.publish_builder_project_atomic(
  uuid, integer, bigint, timestamptz, integer, boolean
) from service_role;

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
  if jsonb_typeof(p_published_schema) <> 'object' then
    raise exception using errcode = 'P0001', message = 'publish_validation_failed';
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

  update public.builder_projects
  set published_schema = p_published_schema,
      published_version = current_project.published_version + 1,
      published_revision = current_project.draft_revision,
      schema_version = p_schema_version,
      last_published_at = p_published_at,
      status = 'published'
  where id = p_project_id and tenant_id = p_tenant_id
  returning * into current_project;

  return current_project;
end;
$$;

revoke all on function public.publish_validated_builder_project_atomic(
  uuid, integer, bigint, jsonb, timestamptz, integer, boolean
) from public, anon, authenticated;
grant execute on function public.publish_validated_builder_project_atomic(
  uuid, integer, bigint, jsonb, timestamptz, integer, boolean
) to service_role;
