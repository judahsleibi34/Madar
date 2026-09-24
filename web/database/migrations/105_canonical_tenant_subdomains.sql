begin;

lock table public.website_settings in share row exclusive mode;

do $$
declare
  invalid_rows text;
  duplicate_rows text;
begin
  select string_agg(format('id=%s tenant_id=%s subdomain=%L', id, tenant_id, subdomain), '; ' order by id)
  into invalid_rows
  from public.website_settings
  where nullif(trim(subdomain), '') is not null
    and (
      lower(trim(subdomain)) !~ '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$'
      or lower(trim(subdomain)) in (
        'admin','api','app','auth','billing','cdn','dashboard','forms','health',
        'login','logout','mail','pricing','privacy-policy','public','signup',
        'site','static','terms-and-conditions','www'
      )
    );

  if invalid_rows is not null then
    raise exception using
      errcode = 'P0001',
      message = 'migration_105_invalid_or_reserved_subdomains',
      detail = invalid_rows,
      hint = 'Remediate the listed website_settings rows explicitly; migration 105 never invents replacement tenant identities.';
  end if;

  select string_agg(format('%s => [%s]', normalized, row_ids), '; ' order by normalized)
  into duplicate_rows
  from (
    select
      lower(trim(subdomain)) as normalized,
      string_agg(format('id=%s tenant_id=%s', id, tenant_id), ', ' order by id) as row_ids
    from public.website_settings
    where nullif(trim(subdomain), '') is not null
    group by lower(trim(subdomain))
    having count(*) > 1
  ) duplicates;

  if duplicate_rows is not null then
    raise exception using
      errcode = 'P0001',
      message = 'migration_105_duplicate_canonical_subdomains',
      detail = duplicate_rows,
      hint = 'Choose the canonical owner of each colliding hostname before retrying migration 105.';
  end if;

  select string_agg(format('id=%s tenant_id=%s standard_path_slug=%L', id, tenant_id, standard_path_slug), '; ' order by id)
  into invalid_rows
  from public.website_settings
  where nullif(trim(subdomain), '') is null
    and (
      nullif(trim(standard_path_slug), '') is null
      or lower(trim(standard_path_slug)) !~ '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$'
      or lower(trim(standard_path_slug)) in (
        'admin','api','app','auth','billing','cdn','dashboard','forms','health',
        'login','logout','mail','pricing','privacy-policy','public','signup',
        'site','static','terms-and-conditions','www'
      )
    );

  if invalid_rows is not null then
    raise exception using
      errcode = 'P0001',
      message = 'migration_105_invalid_subdomain_backfill_sources',
      detail = invalid_rows,
      hint = 'Assign a valid, nonreserved subdomain explicitly before retrying migration 105.';
  end if;

  select string_agg(format('%s => [%s]', normalized, row_ids), '; ' order by normalized)
  into duplicate_rows
  from (
    select
      lower(trim(coalesce(nullif(trim(subdomain), ''), standard_path_slug))) as normalized,
      string_agg(format('id=%s tenant_id=%s', id, tenant_id), ', ' order by id) as row_ids
    from public.website_settings
    group by lower(trim(coalesce(nullif(trim(subdomain), ''), standard_path_slug)))
    having count(*) > 1
  ) collisions;

  if duplicate_rows is not null then
    raise exception using
      errcode = 'P0001',
      message = 'migration_105_canonical_subdomain_backfill_collision',
      detail = duplicate_rows,
      hint = 'Resolve canonical hostname ownership explicitly; standard_path_slug remains legacy compatibility data.';
  end if;
end $$;

update public.website_settings
set subdomain = lower(trim(standard_path_slug))
where nullif(trim(subdomain), '') is null;

update public.website_settings
set subdomain = lower(trim(subdomain))
where subdomain is distinct from lower(trim(subdomain));

alter table public.website_settings
  alter column subdomain set not null;

alter table public.website_settings
  drop constraint if exists website_settings_canonical_subdomain_check;

alter table public.website_settings
  add constraint website_settings_canonical_subdomain_check check (
    subdomain = lower(trim(subdomain))
    and subdomain ~ '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$'
    and subdomain not in (
      'admin','api','app','auth','billing','cdn','dashboard','forms','health',
      'login','logout','mail','pricing','privacy-policy','public','signup',
      'site','static','terms-and-conditions','www'
    )
  ) not valid;

alter table public.website_settings
  validate constraint website_settings_canonical_subdomain_check;

create unique index if not exists website_settings_canonical_subdomain_unique_idx
  on public.website_settings (lower(subdomain));

create or replace function public.normalize_website_canonical_subdomain()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.subdomain := lower(trim(new.subdomain));
  return new;
end;
$$;

drop trigger if exists normalize_website_canonical_subdomain on public.website_settings;
create trigger normalize_website_canonical_subdomain
before insert or update of subdomain
on public.website_settings
for each row execute function public.normalize_website_canonical_subdomain();

do $$ declare v_schema_version public.application_schema_state.schema_version%TYPE; begin
  select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
  if v_schema_version is null then raise exception using errcode='P0001',message='migration_105_schema_state_missing'; end if;
  if v_schema_version <> 104 then raise exception using errcode='P0001',message=format('migration_105_expected_schema_104_got_%s',v_schema_version); end if;
  update public.application_schema_state set schema_version = 105,applied_at=now() where contract_key = 'core';
end $$;

notify pgrst,'reload schema';
commit;
