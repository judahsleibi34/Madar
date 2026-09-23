do $$
begin
  if (select schema_version from public.application_schema_state where contract_key = 'core') <> 105 then
    raise exception 'migration_105_schema_state_not_105';
  end if;
  if exists (
    select 1 from public.website_settings
    where subdomain is null
       or subdomain <> lower(trim(subdomain))
       or subdomain !~ '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$'
       or subdomain in (
         'admin','api','app','auth','billing','cdn','dashboard','forms','health',
         'login','logout','mail','pricing','privacy-policy','public','signup',
         'site','static','terms-and-conditions','www'
       )
  ) then
    raise exception 'migration_105_invalid_canonical_subdomain';
  end if;
  if exists (
    select lower(subdomain) from public.website_settings
    group by lower(subdomain) having count(*) > 1
  ) then
    raise exception 'migration_105_duplicate_canonical_subdomain';
  end if;
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.website_settings'::regclass
      and conname = 'website_settings_canonical_subdomain_check'
      and convalidated
  ) then
    raise exception 'migration_105_constraint_missing_or_unvalidated';
  end if;
  if not exists (
    select 1 from pg_indexes
    where schemaname = 'public'
      and tablename = 'website_settings'
      and indexname = 'website_settings_canonical_subdomain_unique_idx'
  ) then
    raise exception 'migration_105_unique_index_missing';
  end if;
end $$;
