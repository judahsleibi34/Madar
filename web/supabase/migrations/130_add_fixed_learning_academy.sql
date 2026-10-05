begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_130_schema_state_missing'; end if;
 if v_schema_version <> 129 then raise exception 'migration_130_expected_schema_129_got_%',v_schema_version; end if;
 update public.application_schema_state set schema_version = 130,applied_at=now() where contract_key = 'core';
end $$;

-- A storefront projection only. Existing access, progress and credential engines
-- remain authoritative. Null user means public, with no account joins or data.
create function public.get_elearning_academy(p_tenant_id integer,p_user_id integer default null,p_course_id uuid default null)
returns jsonb language plpgsql stable security definer set search_path='' as $$
declare cfg jsonb; course_row record; offering_row record; cards jsonb:='[]'; plans jsonb:='[]'; outline jsonb; instructors jsonb;
 state jsonb; runtime jsonb; progress jsonb; resume text; credential jsonb; available_plans jsonb; price jsonb;
begin
 select settings into cfg from public.elearning_settings where tenant_id=p_tenant_id;
 if not coalesce((cfg->>'enabled')::boolean,false) or not coalesce((cfg->>'academy_enabled')::boolean,false) then
  raise exception using errcode='P0002',message='academy_unavailable';
 end if;
 if p_user_id is not null then perform public.commerce_assert_member(p_tenant_id,p_user_id);end if;
 for offering_row in select o.*,p.translations,p.price,p.currency from public.ecommerce_offerings o
 join public.ecommerce_products p on(p.tenant_id,p.id)=(o.tenant_id,o.product_id)
 where o.tenant_id=p_tenant_id and p.status='active' and o.resource_type='elearning_course'
 and exists(select 1 from public.elearning_courses c where c.tenant_id=p_tenant_id
 and public.elearning_catalog_eligible(p_tenant_id,c.id) and(o.access_scope='all_courses' or exists(
 select 1 from public.elearning_offering_courses oc where oc.tenant_id=p_tenant_id and oc.offering_id=o.id and oc.course_id=c.id)))
 order by p.created_at,o.id loop
 plans:=plans||jsonb_build_array(jsonb_build_object('id',offering_row.id,'name',coalesce(offering_row.translations->'en'->>'name',''),
 'description',coalesce(offering_row.translations->'en'->>'description',''),'amount',offering_row.price,'currency',offering_row.currency,
 'billing_type',offering_row.billing_type,'access_scope',offering_row.access_scope));
 end loop;
 for course_row in select * from public.elearning_courses where tenant_id=p_tenant_id
 and public.elearning_catalog_eligible(p_tenant_id,id) and(p_course_id is null or id=p_course_id) order by name,id loop
 state:=public.elearning_course_cta(p_tenant_id,p_user_id,course_row.id);
 -- Never expose the internal enrollment/entitlement identifiers on cards.
 state:=state-'enrollment_id';
 if state ? 'included_in' then state:=state||jsonb_build_object('included_in',jsonb_build_object('name',state->'included_in'->>'name'));end if;
 progress:=null;resume:=null;credential:=null;
 if state->>'action'='continue' then
  runtime:=public.get_elearning_learner_course(p_tenant_id,p_user_id,course_row.id,null);
  progress:=runtime->'progress';
  resume:='/my-learning/courses/'||course_row.id;
  if runtime->>'continue_lesson_id' is not null then resume:=resume||'/lessons/'||(runtime->>'continue_lesson_id');
  elsif runtime->>'continue_assessment_id' is not null then resume:=resume||'/assessments/'||(runtime->>'continue_assessment_id');end if;
  credential:=runtime->'credential';
  if progress->'completion'->>'completed'='true' and credential->>'status'='active' then
   state:=state||jsonb_build_object('action','certificate');
  end if;
 end if;
 select coalesce(jsonb_agg(value),'[]') into available_plans from jsonb_array_elements(plans) where value->>'access_scope'='all_courses' or exists(
 select 1 from public.elearning_offering_courses oc where oc.tenant_id=p_tenant_id and oc.course_id=course_row.id and oc.offering_id=(value->>'id')::uuid);
 select value into price from jsonb_array_elements(available_plans) order by(value->>'amount')::numeric,value->>'id' limit 1;
 if state->>'action'='buy' and jsonb_array_length(available_plans)=0 then state:=jsonb_build_object('action','unavailable');end if;
 select coalesce(jsonb_agg(jsonb_build_object('name',s.name,'lesson_count',(select count(*) from public.elearning_lessons l
 where(l.tenant_id,l.course_id,l.section_id)=(s.tenant_id,s.course_id,s.id) and l.status='published')) order by s.position,s.id),'[]') into outline
 from public.elearning_sections s where s.tenant_id=p_tenant_id and s.course_id=course_row.id and s.status='published';
 select coalesce(jsonb_agg(jsonb_build_object('name',i.name) order by i.name,i.id),'[]') into instructors from public.elearning_instructors i
 join public.elearning_course_instructors ci on(ci.tenant_id,ci.instructor_id)=(i.tenant_id,i.id)
 where ci.tenant_id=p_tenant_id and ci.course_id=course_row.id and i.status='active';
 cards:=cards||jsonb_build_array(jsonb_build_object('id',course_row.id,'name',course_row.name,'description',course_row.description,'cover_asset',course_row.cover_asset,
 'access_type',course_row.access_type,'featured',coalesce(cfg->'academy_featured_courses','[]') @> jsonb_build_array(course_row.id::text),
 'cta',state,'plans',available_plans,'price',price,'progress',progress,'resume',resume,'credential',credential,
 'certificate_available',exists(select 1 from public.elearning_course_certificates cc join public.elearning_certificate_templates t on(t.tenant_id,t.id)=(cc.tenant_id,cc.template_id)
 where cc.tenant_id=p_tenant_id and cc.course_id=course_row.id and cc.enabled and t.status='active'),
 'outline',outline,'instructors',instructors));
 end loop;
 if p_course_id is not null and jsonb_array_length(cards)=0 then raise exception using errcode='P0002',message='academy_course_unavailable';end if;
 return jsonb_build_object('courses',cards,'plans',plans,'authenticated',p_user_id is not null);
end $$;
revoke all on function public.get_elearning_academy(integer,integer,uuid) from public,anon,authenticated,service_role;
grant execute on function public.get_elearning_academy(integer,integer,uuid) to service_role;
notify pgrst,'reload schema';
commit;
