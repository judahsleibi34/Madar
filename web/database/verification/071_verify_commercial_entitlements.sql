-- Read-only post-migration 071 verification. Every exception below is a
-- deployment blocker. Run with ON_ERROR_STOP against the target database only
-- after the migration transaction commits.

do $$
declare
  sequence_name text;
begin
  if exists (
    select 1
    from public.website_settings
    group by lower(standard_path_slug)
    having count(*) > 1
  ) then
    raise exception 'migration_071_duplicate_standard_path_slugs';
  end if;

  if exists (
    select 1
    from public.website_settings
    where standard_path_slug is null
      or standard_path_slug !~ '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$'
  ) then
    raise exception 'migration_071_invalid_or_null_standard_path_slug';
  end if;

  if exists (
    select 1
    from public.website_settings
    where standard_path_slug in (
      'api','admin','auth','billing','dashboard','forms','health','login','logout',
      'pricing','privacy-policy','public','signup','site','static',
      'terms-and-conditions','www'
    )
  ) then
    raise exception 'migration_071_reserved_standard_path_slug';
  end if;

  if not exists (
    select 1
    from pg_constraint
    where conrelid='public.website_settings'::regclass
      and conname='website_settings_standard_path_slug_check'
      and convalidated
  ) then
    raise exception 'migration_071_slug_constraint_not_validated';
  end if;

  if exists (
    select 1
    from public.website_settings
    where legacy_subdomain_routing_preserved
      and nullif(trim(subdomain),'') is null
  ) then
    raise exception 'migration_071_invalid_legacy_routing_compatibility';
  end if;

  if exists (
    select tenant_id
    from public.tenant_addons
    where state='active'
      and billing_interval='month'
      and addon_id in ('ai_analytics_starter','ai_analytics_plus')
    group by tenant_id
    having count(*) > 1
  ) then
    raise exception 'migration_071_multiple_active_ai_packages';
  end if;

  if exists (
    select 1
    from pg_class c
    join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='public'
      and c.relname in (
        'tenant_subscriptions','tenant_addons','billing_addon_requests',
        'legacy_billing_migration_reviews','hosted_address_migration_reviews',
        'commercial_usage_monthly','ai_token_model_multipliers',
        'ai_token_allocations','ai_token_reservations','ai_token_ledger'
      )
      and not c.relrowsecurity
  ) then
    raise exception 'migration_071_rls_not_enabled';
  end if;

  foreach sequence_name in array array[
    'tenant_subscriptions_id_seq','tenant_addons_id_seq',
    'billing_addon_requests_id_seq','hosted_address_migration_reviews_id_seq',
    'ai_token_allocations_id_seq','ai_token_ledger_id_seq'
  ] loop
    if not has_sequence_privilege(
      'service_role',
      'public.'||sequence_name,
      'USAGE'
    ) or not has_sequence_privilege(
      'service_role',
      'public.'||sequence_name,
      'SELECT'
    ) then
      raise exception 'migration_071_sequence_grant_missing: %', sequence_name;
    end if;
  end loop;
end
$$;

-- Human-readable review sets.
select
  settings.tenant_id,
  settings.subdomain,
  settings.standard_path_slug,
  settings.legacy_subdomain_routing_preserved,
  settings.branded_subdomain_commercial_status,
  project.status as project_status
from public.website_settings settings
left join public.builder_projects project
  on project.id=settings.published_project_id
where settings.legacy_subdomain_routing_preserved
order by settings.tenant_id;

select
  review.tenant_id,
  review.original_subdomain,
  review.normalized_standard_path_slug,
  review.material_change,
  review.collision_resolved,
  review.commercial_review_state,
  review.publication_state
from public.hosted_address_migration_reviews review
order by review.tenant_id;

-- Standard-path resolution must bind only to an existing settings row; runtime
-- code additionally requires a published, non-archived bound project.
select
  settings.standard_path_slug,
  settings.tenant_id,
  project.id as published_project_id,
  project.status,
  project.published_schema is not null as has_published_schema
from public.website_settings settings
left join public.builder_projects project
  on project.id=settings.published_project_id
order by settings.standard_path_slug;

-- RLS must be enabled for every new service-role-only table.
select c.relname, c.relrowsecurity
from pg_class c
join pg_namespace n on n.oid=c.relnamespace
where n.nspname='public'
  and c.relname in (
    'tenant_subscriptions','tenant_addons','billing_addon_requests',
    'legacy_billing_migration_reviews','hosted_address_migration_reviews',
    'commercial_usage_monthly','ai_token_model_multipliers',
    'ai_token_allocations','ai_token_reservations','ai_token_ledger'
  )
order by c.relname;

-- Migration 071 grants only its six identity sequences to service_role.
select object_name as sequence_name, grantee, privilege_type
from information_schema.role_usage_grants
where object_schema='public'
  and grantee='service_role'
  and object_name in (
    'tenant_subscriptions_id_seq','tenant_addons_id_seq',
    'billing_addon_requests_id_seq','hosted_address_migration_reviews_id_seq',
    'ai_token_allocations_id_seq','ai_token_ledger_id_seq'
  )
order by sequence_name, privilege_type;
