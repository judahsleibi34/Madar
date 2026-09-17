-- ============================================================
-- Cleanup duplicate feature subscriptions and recreate indexes
-- Keeps the newest row for each duplicate group
-- ============================================================

-- Remove old indexes if they exist
drop index if exists public.features_unique_tenant_subscription_idx;
drop index if exists public.features_unique_full_platform_per_tenant_idx;
drop index if exists public.features_unique_individual_builder_per_tenant_idx;

-- Delete duplicate full_platform rows.
-- For each tenant, keep only the newest full_platform row.
delete from public.features f
using public.features newer
where f.subscription_type = 'full_platform'
  and newer.subscription_type = 'full_platform'
  and f.tenant_id = newer.tenant_id
  and f.id < newer.id;

-- Delete duplicate individual_builder rows.
-- For each tenant + builder_type, keep only the newest row.
delete from public.features f
using public.features newer
where f.subscription_type = 'individual_builder'
  and newer.subscription_type = 'individual_builder'
  and f.tenant_id = newer.tenant_id
  and f.builder_type = newer.builder_type
  and f.id < newer.id;

-- One full platform subscription per tenant
create unique index if not exists features_unique_full_platform_per_tenant_idx
on public.features (tenant_id)
where subscription_type = 'full_platform';

-- One individual builder subscription per tenant per builder
create unique index if not exists features_unique_individual_builder_per_tenant_idx
on public.features (tenant_id, builder_type)
where subscription_type = 'individual_builder';