begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_131_schema_state_missing'; end if;
 if v_schema_version <> 130 then raise exception 'migration_131_expected_schema_130_got_%',v_schema_version; end if;
end $$;

-- Academy pages remain ordinary Builder projects, with a constrained purpose.
alter table public.builder_projects add column usage_profile text not null default 'website'
 check (usage_profile in ('website','academy'));
create unique index builder_projects_id_tenant_profile_unique on public.builder_projects(id,tenant_id,usage_profile);
alter table public.website_settings add column academy_project_id uuid;
alter table public.website_settings add column academy_project_profile text not null default 'academy' check(academy_project_profile='academy');
alter table public.website_settings add constraint website_academy_project_tenant_fk
 foreign key(academy_project_id,tenant_id,academy_project_profile)
 references public.builder_projects(id,tenant_id,usage_profile);
alter table public.website_settings add column website_project_profile text not null default 'website' check(website_project_profile='website');
alter table public.website_settings add constraint website_main_project_profile_fk
 foreign key(published_project_id,tenant_id,website_project_profile)
 references public.builder_projects(id,tenant_id,usage_profile);
-- Registration uses existing identities and tenant memberships. Learners never
-- receive member/staff management permissions by registering publicly.
alter table public.tenant_memberships drop constraint tenant_memberships_role_check;
alter table public.tenant_memberships add constraint tenant_memberships_role_check
 check(role in ('owner','admin','member','learner'));

create function public.validate_academy_builder_schema(p_schema jsonb) returns boolean
language plpgsql immutable set search_path='' as $$
declare node jsonb; element jsonb;
begin
 if jsonb_typeof(p_schema) <> 'object' then return false; end if;
 if jsonb_array_length(coalesce(p_schema->'pages','[]'))<>1 then return false; end if;
 if coalesce(p_schema->'forms','[]')<>'[]' or coalesce(p_schema->'workflows','[]')<>'[]'
 or coalesce(p_schema->'collections','[]')<>'[]' or coalesce(p_schema->'users','[]')<>'[]'
 or coalesce(p_schema->'roles','[]')<>'[]' then return false; end if;
 -- Recursive inspection covers direct, free and legacy row/column elements.
 for node in select value from jsonb_path_query(p_schema,'$.**.elements') as q(value)
 union all select value from jsonb_path_query(p_schema,'$.**.freeElements') as q(value) loop
  if jsonb_typeof(node)<>'array' then return false;end if;
  for element in select value from jsonb_array_elements(node) loop
   if coalesce(element->>'type','') not in ('heading','text','button','image','imageButton','imageCardButton','card','carousel','logoSlider','list','divider','thinDivider','metric','academyFeaturedCourses','academyCourseCollection','academyPlans','academyContinueLearning') then return false;end if;
   if element->>'type' like 'academy%' then
    if element - array['id','type','name','content','mode','position','styles','action','connectedFormId','academy'] <> '{}' then return false;end if;
    if coalesce(element->'academy','{}') - array['heading','description','maxItems','courseIds','planIds','variant','featuredOnly'] <> '{}' then return false;end if;
   end if;
  end loop;
 end loop;
 return true;
end $$;
revoke all on function public.validate_academy_builder_schema(jsonb) from public,anon,authenticated;
grant execute on function public.validate_academy_builder_schema(jsonb) to service_role;
create function public.guard_academy_builder_profile() returns trigger language plpgsql set search_path='' as $$
begin
 if tg_op='UPDATE' and new.usage_profile<>old.usage_profile then raise exception 'builder_profile_immutable';end if;
 if new.usage_profile='academy' and (
 not public.validate_academy_builder_schema(new.draft_schema)
 or (new.published_schema is not null and not public.validate_academy_builder_schema(new.published_schema)))
 then raise exception 'academy_component_not_allowed' using errcode='23514';end if;
 return new;
end $$;
create trigger guard_academy_builder_profile before insert or update on public.builder_projects
for each row execute function public.guard_academy_builder_profile();
revoke all on function public.guard_academy_builder_profile() from public,anon,authenticated,service_role;

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

  if current_project.usage_profile <> 'academy' and current_settings.id is not null and (
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

  if current_project.usage_profile = 'academy' then
    update public.website_settings set academy_project_id=p_project_id where tenant_id=p_tenant_id;
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
      'academy_project_id', s.academy_project_id,
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




create or replace function public.provision_verified_account(p_auth_id uuid)
returns public.users
language plpgsql
security definer
set search_path = public
as $$
declare
  account_row public.users;
  pending_row public.pending_account_onboarding;
  provisioned_tenant_id integer;
  display_name text;
  subdomain_conflict boolean := false;
begin
  select * into account_row from public.users where auth_id = p_auth_id for update;
  if not found then
    raise exception using errcode = 'P0002', message = 'user_not_found';
  end if;
  if not coalesce(account_row.email_verified, false) then
    raise exception using errcode = 'P0001', message = 'email_verification_required';
  end if;

  if account_row.account_kind = 'site_visitor' then
    update public.users
    set account_status = 'active', pending_account_expires_at = null
    where id = account_row.id
    returning * into account_row;
    return account_row;
  end if;

  -- Academy verification activates the existing learner membership without
  -- provisioning an owner account or changing the tenant's website settings.
  if account_row.tenant_id is not null and exists(
    select 1 from public.tenant_memberships m where m.tenant_id=account_row.tenant_id
     and m.user_id=account_row.id and m.auth_id=p_auth_id and m.role='learner'
     and m.status='active'
  ) then
    update public.users set account_status='active',pending_account_expires_at=null
     where id=account_row.id returning * into account_row;
    return account_row;
  end if;

  select * into pending_row
  from public.pending_account_onboarding
  where auth_id = p_auth_id
  for update;

  provisioned_tenant_id := account_row.tenant_id;
  if provisioned_tenant_id is null and pending_row.tenant_id is not null then
    provisioned_tenant_id := pending_row.tenant_id;
  end if;

  if provisioned_tenant_id is null then
    display_name := trim(concat_ws(' ', account_row.first_name, account_row.last_name));
    insert into public.tenants (brand_name, owner_name, business_type)
    values (
      coalesce(pending_row.business_name, ''),
      coalesce(display_name, ''),
      pending_row.business_type
    )
    returning tenant_id into provisioned_tenant_id;

    if pending_row.id is not null then
      update public.pending_account_onboarding
      set tenant_id = provisioned_tenant_id, status = 'provisioning', last_error_code = null
      where id = pending_row.id;
    end if;
  end if;

  update public.users
  set tenant_id = provisioned_tenant_id,
      account_status = 'active',
      pending_account_expires_at = null
  where id = account_row.id
  returning * into account_row;

  insert into public.tenant_memberships (tenant_id, user_id, auth_id, role, status)
  values (provisioned_tenant_id, account_row.id, p_auth_id, 'owner', 'active')
  on conflict (user_id, tenant_id) do update
    set auth_id = excluded.auth_id, role = 'owner', status = 'active';

  begin
    insert into public.website_settings (user_id, tenant_id, subdomain, brand)
    values (
      account_row.id,
      provisioned_tenant_id,
      nullif(pending_row.requested_subdomain, ''),
      nullif(pending_row.business_name, '')
    )
    on conflict (user_id) do update
      set tenant_id = coalesce(public.website_settings.tenant_id, excluded.tenant_id);
  exception when unique_violation then
    -- A requested public subdomain may have been claimed while verification was
    -- pending. Account activation must still succeed; the user can choose a new
    -- subdomain after login.
    subdomain_conflict := true;
    insert into public.website_settings (user_id, tenant_id, subdomain, brand)
    values (
      account_row.id,
      provisioned_tenant_id,
      null,
      nullif(pending_row.business_name, '')
    )
    on conflict (user_id) do update
      set tenant_id = coalesce(public.website_settings.tenant_id, excluded.tenant_id);
  end;

  if pending_row.id is not null then
    update public.pending_account_onboarding
    set tenant_id = provisioned_tenant_id,
        status = 'provisioned',
        provisioned_at = coalesce(provisioned_at, now()),
        last_error_code = case
          when subdomain_conflict then 'subdomain_unavailable'
          else null
        end
    where id = pending_row.id;
  end if;

  return account_row;
end;
$$;

revoke all on function public.provision_verified_account(uuid) from public, anon, authenticated;
grant execute on function public.provision_verified_account(uuid) to service_role;


update public.application_schema_state set schema_version=131,applied_at=now() where contract_key = 'core';
notify pgrst, 'reload schema';
commit;
