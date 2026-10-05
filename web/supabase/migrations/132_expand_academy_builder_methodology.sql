begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_132_schema_state_missing';end if;
 if v_schema_version<>131 then raise exception 'migration_132_expected_schema_131_got_%',v_schema_version;end if;
end $$;

-- The published binding remains independent from the durable editor binding.
-- Deleting an unpublished editor project clears its FK; published deletion stays restricted.
alter table public.website_settings add column academy_editor_project_id uuid;
alter table public.website_settings add constraint website_academy_editor_project_tenant_fk
 foreign key(academy_editor_project_id,tenant_id,academy_project_profile)
 references public.builder_projects(id,tenant_id,usage_profile) on delete set null (academy_editor_project_id);
update public.website_settings set academy_editor_project_id=academy_project_id where academy_project_id is not null;

create or replace function public.validate_academy_builder_schema(p_schema jsonb) returns boolean
language plpgsql immutable set search_path='' as $$
declare node jsonb; element jsonb; page jsonb; slugs text[]:=array[]::text[]; ids text[]:=array[]::text[]; slug text; config jsonb; selected_id jsonb; field text;
begin
 if jsonb_typeof(p_schema) <> 'object' then return false; end if;
 if jsonb_typeof(p_schema->'pages') is distinct from 'array' or jsonb_array_length(p_schema->'pages') not between 1 and 50 then return false; end if;
 for page in select value from jsonb_array_elements(p_schema->'pages') loop
  if jsonb_typeof(page)<>'object' or jsonb_typeof(page->'id') is distinct from 'string' or coalesce(page->>'id','')='' or coalesce(page->>'access','public')<>'public' then return false;end if;
  slug:=page->>'slug';
  if slug is null or slug !~ '^/([a-z0-9-]+(/[a-z0-9-]+)*)?$' or slug like '%..%' or slug=any(slugs) or (page->>'id')=any(ids) then return false;end if;
  if split_part(trim(both '/' from slug),'/',1) in ('courses','plans','login','signup','auth','my-learning','account','checkout','assessments','api','admin','dashboard','settings','builder','page-builder') then return false;end if;
  slugs:=array_append(slugs,slug);ids:=array_append(ids,page->>'id');
 end loop;
 if not '/'=any(slugs) then return false;end if;
 if coalesce(p_schema->'forms','[]')<>'[]' or coalesce(p_schema->'workflows','[]')<>'[]'
 or coalesce(p_schema->'collections','[]')<>'[]' or coalesce(p_schema->'users','[]')<>'[]'
 or coalesce(p_schema->'roles','[]')<>'[]' then return false; end if;
 -- Recursive inspection covers direct, free and legacy row/column elements.
 for node in select value from jsonb_path_query(p_schema,'$.**.elements') as q(value)
 union all select value from jsonb_path_query(p_schema,'$.**.freeElements') as q(value) loop
  if jsonb_typeof(node)<>'array' then return false;end if;
  for element in select value from jsonb_array_elements(node) loop
   if coalesce(element->>'type','') not in ('heading','text','button','image','imageButton','imageCardButton','card','carousel','logoSlider','list','divider','thinDivider','metric','academyFeaturedCourses','academyCourseCollection','academyPlans','academyContinueLearning','academyInstructors') then return false;end if;
   if coalesce(element->>'connectedFormId','')<>'' then return false;end if;
   if element ? 'action' and jsonb_typeof(element->'action') not in ('object','null') then return false;end if;
   if coalesce(element->'action'->>'type','none') not in ('none','openUrl','scrollToSection','goToPage') then return false;end if;
   if element->>'type' like 'academy%' then
    if element - array['id','type','name','content','mode','position','styles','action','connectedFormId','academy'] <> '{}' then return false;end if;
    config:=coalesce(element->'academy','{}');
    if jsonb_typeof(config)<>'object' or config - array['heading','description','maxItems','courseIds','planIds','variant','featuredOnly','instructorIds'] <> '{}' then return false;end if;
    if coalesce(config->>'variant','grid') not in ('grid','compact') then return false;end if;
    foreach field in array array['heading','description'] loop
     if config ? field and (jsonb_typeof(config->field)<>'string' or length(config->>field)>case when field='heading' then 160 else 1200 end) then return false;end if;
    end loop;
    if config ? 'featuredOnly' and jsonb_typeof(config->'featuredOnly')<>'boolean' then return false;end if;
    if config ? 'maxItems' and (jsonb_typeof(config->'maxItems')<>'number' or (config->>'maxItems') !~ '^[0-9]+$' or (config->>'maxItems')::int not between 1 and 24) then return false;end if;
    foreach field in array array['courseIds','planIds','instructorIds'] loop
     if config ? field then
      if jsonb_typeof(config->field)<>'array' or jsonb_array_length(config->field)>24 then return false;end if;
      for selected_id in select value from jsonb_array_elements(config->field) loop
       if jsonb_typeof(selected_id)<>'string' then return false;end if;
       perform (selected_id#>>'{}')::uuid;
      end loop;
     end if;
    end loop;
   end if;
  end loop;
 end loop;
 return true;
exception when others then return false;
end $$;

create function public.ensure_academy_builder_project(p_tenant_id integer,p_user_id integer,p_initial_schema jsonb)
returns public.builder_projects language plpgsql security definer set search_path='' as $$
declare settings public.website_settings%rowtype;project public.builder_projects%rowtype;
begin
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant_id and user_id=p_user_id and role in ('owner','admin') and status='active') then raise exception using errcode='42501',message='academy_management_forbidden';end if;
 select * into settings from public.website_settings where tenant_id=p_tenant_id for update;
 if not found or coalesce(settings.subdomain,'')='' then raise exception using errcode='P0002',message='academy_address_required';end if;
 select * into project from public.builder_projects where tenant_id=p_tenant_id and usage_profile='academy' and status<>'archived'
 order by (id=settings.academy_editor_project_id) desc nulls last,(id=settings.academy_project_id) desc nulls last,created_at,id limit 1;
 if project.id is null then
  if not public.validate_academy_builder_schema(p_initial_schema) then raise exception using errcode='23514',message='academy_component_not_allowed';end if;
  insert into public.builder_projects(tenant_id,owner_user_id,name,slug,usage_profile,status,draft_schema,draft_revision,schema_version)
  values(p_tenant_id,p_user_id,'Academy','academy-'||gen_random_uuid()::text,'academy','draft',p_initial_schema,0,1) returning * into project;
 end if;
 update public.website_settings set academy_editor_project_id=project.id where id=settings.id and tenant_id=p_tenant_id;
 return project;
end $$;
revoke all on function public.ensure_academy_builder_project(integer,integer,jsonb) from public,anon,authenticated;
grant execute on function public.ensure_academy_builder_project(integer,integer,jsonb) to service_role;

-- Only identities assigned to currently public catalog courses are projected.
-- Email/user references remain private; no second instructor store is introduced.
create function public.get_academy_public_instructors(p_tenant_id integer,p_course_ids uuid[])
returns jsonb language sql stable security definer set search_path='' as $$
 select coalesce(jsonb_agg(to_jsonb(projected) order by projected.name,projected.id),'[]'::jsonb) from (
 select i.id,i.name,i.description, array_agg(distinct ci.course_id) as course_ids
 from public.elearning_instructors i join public.elearning_course_instructors ci on (ci.tenant_id,ci.instructor_id)=(i.tenant_id,i.id)
 join public.elearning_courses c on (c.tenant_id,c.id)=(ci.tenant_id,ci.course_id)
 where i.tenant_id=p_tenant_id and i.status='active' and c.id=any(p_course_ids) and c.status='published' and c.access_type<>'private' and c.catalog_visible
 group by i.id,i.name,i.description) projected;
$$;
revoke all on function public.get_academy_public_instructors(integer,uuid[]) from public,anon,authenticated;
grant execute on function public.get_academy_public_instructors(integer,uuid[]) to service_role;

update public.application_schema_state set schema_version=132,applied_at=now() where contract_key = 'core';
notify pgrst,'reload schema';
commit;
