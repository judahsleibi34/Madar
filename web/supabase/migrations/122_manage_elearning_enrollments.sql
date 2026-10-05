begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_122_schema_state_missing'; end if;
 if v_schema_version <> 121 then raise exception 'migration_122_expected_schema_121_got_%',v_schema_version; end if;
 update public.application_schema_state set schema_version=122,applied_at=now() where contract_key = 'core';
end;
$$;
alter table public.elearning_learners add column user_id integer references public.users(id) on delete set null;
create unique index elearning_learners_tenant_user on public.elearning_learners(tenant_id,user_id) where user_id is not null;
alter table public.elearning_enrollments drop constraint elearning_enrollments_status_check;
alter table public.elearning_enrollments add constraint elearning_enrollments_status_check check(status in ('active','suspended','archived'));
create or replace function public.manage_elearning_participation(p_tenant_id integer,p_course_id uuid,p_user_id integer,p_action text,p_payload jsonb)
returns jsonb language plpgsql security definer set search_path='' as $$
declare c public.elearning_courses%rowtype; e public.elearning_enrollments%rowtype; result_id uuid; source text;
begin
 select * into c from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id for update;
 if not found then raise exception using errcode='P0002',message='elearning_course_not_found'; end if;
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant_id and user_id=p_user_id and role in ('owner','admin') and status='active') then
  raise exception using errcode='42501',message='elearning_participation_forbidden'; end if;
 if p_action is null or p_action not in ('enroll','archive_enrollment','complete_lesson','uncomplete_lesson') then
  raise exception using errcode='22023',message='elearning_participation_invalid_action'; end if;
 if p_action in ('enroll','complete_lesson') and c.status <> 'published' then
  raise exception using errcode='22023',message='elearning_course_not_published'; end if;
 if p_action='enroll' then
  if not exists(select 1 from public.elearning_learners where tenant_id=p_tenant_id and id=(p_payload->>'learner_id')::uuid and status='active') then
   raise exception using errcode='P0002',message='elearning_learner_not_found'; end if;
  if exists(select 1 from public.elearning_learners l where l.tenant_id=p_tenant_id and l.id=(p_payload->>'learner_id')::uuid and l.user_id is not null and not exists(select 1 from public.users u join public.tenant_memberships m on m.user_id=u.id and m.tenant_id=p_tenant_id and m.status='active' where u.id=l.user_id and u.account_status='active')) then raise exception using errcode='P0002',message='elearning_tenant_user_not_found'; end if;
  source:=p_payload->>'access_source';
  if source is null or source not in ('free','manual') or (source='free' and c.access_type <> 'free') then
   raise exception using errcode='22023',message='elearning_invalid_access_source'; end if;
  insert into public.elearning_enrollments(tenant_id,course_id,learner_id,access_source,created_by)
   values(p_tenant_id,p_course_id,(p_payload->>'learner_id')::uuid,source,p_user_id)
   on conflict(tenant_id,course_id,learner_id) do update set status='active',access_source=excluded.access_source
   returning id into result_id;
 else
  select * into e from public.elearning_enrollments where tenant_id=p_tenant_id and course_id=p_course_id and id=(p_payload->>'enrollment_id')::uuid for update;
  if not found then raise exception using errcode='P0002',message='elearning_enrollment_not_found'; end if;
  result_id:=e.id;
  if p_action='archive_enrollment' then
   update public.elearning_enrollments set status='archived' where id=e.id;
  elsif p_action='uncomplete_lesson' then
   delete from public.elearning_lesson_completions where tenant_id=p_tenant_id and course_id=p_course_id and enrollment_id=e.id and lesson_id=(p_payload->>'lesson_id')::uuid;
  else
   if e.status <> 'active' or not exists(select 1 from public.elearning_learners where tenant_id=p_tenant_id and id=e.learner_id and status='active') then
    raise exception using errcode='22023',message='elearning_enrollment_inactive'; end if;
   if exists(select 1 from public.elearning_learners l where l.tenant_id=p_tenant_id and l.id=e.learner_id and l.user_id is not null and not exists(select 1 from public.users u join public.tenant_memberships m on m.user_id=u.id and m.tenant_id=p_tenant_id and m.status='active' where u.id=l.user_id and u.account_status='active')) then raise exception using errcode='P0002',message='elearning_tenant_user_not_found'; end if;
   if not exists(select 1 from public.elearning_lessons l join public.elearning_sections s on(s.tenant_id,s.course_id,s.id)=(l.tenant_id,l.course_id,l.section_id)
    where l.tenant_id=p_tenant_id and l.course_id=p_course_id and l.id=(p_payload->>'lesson_id')::uuid and l.status='published' and s.status='published') then
    raise exception using errcode='P0002',message='elearning_published_lesson_not_found'; end if;
   insert into public.elearning_lesson_completions(tenant_id,course_id,enrollment_id,lesson_id,recorded_by)
    values(p_tenant_id,p_course_id,e.id,(p_payload->>'lesson_id')::uuid,p_user_id) on conflict do nothing;
  end if;
 end if;
 return jsonb_build_object('enrollment_id',result_id);
end;
$$;


create function public.get_elearning_progress_records(p_tenant_id integer,p_course_id uuid,p_include_inactive boolean)
returns jsonb language plpgsql stable security definer set search_path='' as $$
declare result jsonb;
begin
 if not exists(select 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id) then
  raise exception using errcode='P0002',message='elearning_course_not_found'; end if;
 with eligible as (
  select l.id,l.section_id,l.name,l.position from public.elearning_lessons l
  join public.elearning_sections s on(s.tenant_id,s.course_id,s.id)=(l.tenant_id,l.course_id,l.section_id)
  join public.elearning_courses c on(c.tenant_id,c.id)=(l.tenant_id,l.course_id)
  where l.tenant_id=p_tenant_id and l.course_id=p_course_id and l.status='published' and s.status='published' and c.status='published'
 ), totals as(select count(*)::integer n from eligible), participants as(
  select e.id,e.status enrollment_status,e.created_at enrolled_at,e.access_source,r.id learner_id,r.user_id,r.status learner_status,r.name,r.email,
   (select max(x.completed_at) from public.elearning_lesson_completions x where x.tenant_id=p_tenant_id and x.course_id=p_course_id and x.enrollment_id=e.id) last_activity,
   (select count(*)::integer from public.elearning_lesson_completions x join eligible l on l.id=x.lesson_id where x.tenant_id=p_tenant_id and x.enrollment_id=e.id) completed
  from public.elearning_enrollments e join public.elearning_learners r on(r.tenant_id,r.id)=(e.tenant_id,e.learner_id)
  where e.tenant_id=p_tenant_id and e.course_id=p_course_id and (p_include_inactive or (e.status='active' and r.status='active'))
 ), records as(
  select p.*,t.n total,coalesce(round(100.0*p.completed/nullif(t.n,0),2),0) progress_percent,
   case when p.completed=0 then 'not_started' when p.completed=t.n then 'completed' else 'active' end progress_status,
   (select coalesce(jsonb_agg(jsonb_build_object('id',s.id,'name',s.name,'status',s.status,
    'total_lessons',(select count(*) from eligible l where l.section_id=s.id),
    'completed_lessons',(select count(*) from eligible l join public.elearning_lesson_completions x on x.lesson_id=l.id and x.tenant_id=p_tenant_id and x.enrollment_id=p.id where l.section_id=s.id),
    'progress_percent',coalesce((select round(100.0*count(x.lesson_id)/nullif(count(l.id),0),2) from eligible l left join public.elearning_lesson_completions x on x.lesson_id=l.id and x.tenant_id=p_tenant_id and x.enrollment_id=p.id where l.section_id=s.id),0),
    'lessons',(select coalesce(jsonb_agg(jsonb_build_object('id',l.id,'name',l.name,'completed',x.lesson_id is not null) order by l.position,l.id),'[]'::jsonb) from eligible l left join public.elearning_lesson_completions x on x.lesson_id=l.id and x.tenant_id=p_tenant_id and x.enrollment_id=p.id where l.section_id=s.id)
   ) order by s.position,s.id),'[]'::jsonb) from public.elearning_sections s where s.tenant_id=p_tenant_id and s.course_id=p_course_id and s.status <> 'archived') sections
  from participants p cross join totals t
 ) select jsonb_build_object('available',true,'total_lessons',(select n from totals),'learner_count',count(*),
  'enrollment_active_count',count(*) filter(where enrollment_status='active' and learner_status='active'),
  'average_progress',coalesce(round(avg(progress_percent),2),0),
  'not_started_count',count(*) filter(where progress_status='not_started'),'active_count',count(*) filter(where progress_status='active'),'completed_count',count(*) filter(where progress_status='completed'),
  'enrollments',coalesce(jsonb_agg(jsonb_build_object('id',id,'learner_id',learner_id,'user_id',user_id,'enrollment_status',enrollment_status,'learner_status',learner_status,'enrolled_at',enrolled_at,'last_activity',last_activity,'group_id',null,'payment_status',null,'name',name,'email',email,'access_source',access_source,'completed_lessons',completed,'total_lessons',total,'progress_percent',progress_percent,'progress_status',progress_status,'sections',sections) order by name,id),'[]'::jsonb)) into result from records;
 return result;
end;
$$;

create or replace function public.get_elearning_progress(p_tenant_id integer,p_course_id uuid)
returns jsonb language sql stable security definer set search_path='' as $$
 select public.get_elearning_progress_records(p_tenant_id,p_course_id,false);
$$;
create function public.get_elearning_enrollment_report(p_tenant_id integer,p_course_id uuid)
returns jsonb language sql stable security definer set search_path='' as $$
 select public.get_elearning_progress_records(p_tenant_id,p_course_id,true);
$$;
create function public.get_elearning_enrollment_candidates(p_tenant_id integer,p_course_id uuid,p_query text,p_limit integer,p_offset integer)
returns jsonb language plpgsql stable security definer set search_path='' as $$
begin
 if not exists(select 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id) then raise exception using errcode='P0002',message='elearning_course_not_found'; end if;
 if p_limit not between 1 and 100 or p_offset < 0 or char_length(p_query)>120 then raise exception using errcode='22023',message='invalid_candidate_query'; end if;
 return (select coalesce(jsonb_agg(to_jsonb(u) order by u.name,u.id),'[]'::jsonb) from (
  select u.id,concat_ws(' ',u.first_name,u.last_name) name,u.email,
   exists(select 1 from public.elearning_learners l join public.elearning_enrollments e on e.tenant_id=l.tenant_id and e.learner_id=l.id where l.tenant_id=p_tenant_id and (l.user_id=u.id or (l.user_id is null and l.email=lower(btrim(u.email)))) and e.course_id=p_course_id and e.status='active') already_enrolled
  from public.users u join public.tenant_memberships m on m.user_id=u.id
  where m.tenant_id=p_tenant_id and m.status='active' and u.account_status='active'
   and (p_query='' or position(lower(p_query) in lower(concat_ws(' ',u.first_name,u.last_name,u.email)))>0)
  order by name,u.id limit p_limit+1 offset p_offset
 ) u);
end;
$$;
create function public.manage_elearning_enrollments(p_tenant_id integer,p_course_id uuid,p_actor_id integer,p_action text,p_user_ids integer[],p_enrollment_id uuid,p_expected_status text,p_access_source text,p_confirmed boolean)
returns jsonb language plpgsql security definer set search_path='' as $$
declare c public.elearning_courses%rowtype; e public.elearning_enrollments%rowtype; l public.elearning_learners%rowtype; u public.users%rowtype; v_id integer; v_learner uuid; v_results jsonb:='[]'::jsonb;
begin
 select * into c from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id for update;
 if not found then raise exception using errcode='P0002',message='elearning_course_not_found'; end if;
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant_id and user_id=p_actor_id and status='active' and role in ('owner','admin')) then raise exception using errcode='42501',message='elearning_enrollment_forbidden'; end if;
 if p_action='enroll_users' then
  if c.status<>'published' then raise exception using errcode='22023',message='elearning_course_not_published'; end if;
  if p_access_source is null or p_access_source not in ('manual','free') or (p_access_source='free' and c.access_type<>'free') then raise exception using errcode='22023',message='elearning_invalid_access_source'; end if;
  if coalesce(cardinality(p_user_ids),0) not between 1 and 100 or (select count(distinct x) from unnest(p_user_ids) x)<>cardinality(p_user_ids) then raise exception using errcode='22023',message='invalid_user_selection'; end if;
  if (select count(*) from public.users usr join public.tenant_memberships m on m.user_id=usr.id and m.tenant_id=p_tenant_id and m.status='active' where usr.id=any(p_user_ids) and usr.account_status='active')<>cardinality(p_user_ids) then raise exception using errcode='P0002',message='elearning_tenant_user_not_found'; end if;
  foreach v_id in array p_user_ids loop
   select * into u from public.users where id=v_id;
   select * into l from public.elearning_learners where tenant_id=p_tenant_id and (user_id=v_id or email=lower(btrim(u.email))) order by user_id nulls last limit 1 for update;
   if found then
    if l.status<>'active' or (l.user_id is not null and l.user_id<>v_id) then raise exception using errcode='22023',message='elearning_profile_unavailable'; end if;
    v_learner:=l.id;
    update public.elearning_learners set user_id=v_id where id=l.id and user_id is null;
   else
    insert into public.elearning_learners(tenant_id,user_id,name,email,created_by) values(p_tenant_id,v_id,left(concat_ws(' ',u.first_name,u.last_name),120),lower(btrim(u.email)),p_actor_id) returning id into v_learner;
   end if;
   if exists(select 1 from public.elearning_enrollments where tenant_id=p_tenant_id and course_id=p_course_id and learner_id=v_learner and status='active') then raise exception using errcode='23505',message='elearning_already_enrolled'; end if;
   v_results:=v_results||jsonb_build_array((public.manage_elearning_participation(p_tenant_id,p_course_id,p_actor_id,'enroll',jsonb_build_object('learner_id',v_learner,'access_source',p_access_source))->>'enrollment_id')::uuid);
  end loop;
  return jsonb_build_object('enrollment_ids',v_results);
 end if;
 if p_action is null or p_action not in ('suspend','reactivate','cancel') then raise exception using errcode='22023',message='invalid_enrollment_action'; end if;
 select * into e from public.elearning_enrollments where tenant_id=p_tenant_id and course_id=p_course_id and id=p_enrollment_id for update;
 if not found then raise exception using errcode='P0002',message='elearning_enrollment_not_found'; end if;
 if e.status is distinct from p_expected_status then raise exception using errcode='P0001',message='elearning_enrollment_conflict'; end if;
 if p_action in ('suspend','cancel') and p_confirmed is distinct from true then raise exception using errcode='22023',message='enrollment_confirmation_required'; end if;
 if p_action='suspend' and e.status<>'active' then raise exception using errcode='22023',message='enrollment_not_active'; end if;
 if p_action='reactivate' then
  if c.status<>'published' then raise exception using errcode='22023',message='elearning_course_not_published'; end if;
  select * into l from public.elearning_learners where tenant_id=p_tenant_id and id=e.learner_id;
  if l.status<>'active' or (l.user_id is not null and not exists(select 1 from public.users usr join public.tenant_memberships m on m.user_id=usr.id and m.tenant_id=p_tenant_id and m.status='active' where usr.id=l.user_id and usr.account_status='active')) then raise exception using errcode='22023',message='elearning_profile_unavailable'; end if;
 end if;
 update public.elearning_enrollments set status=case p_action when 'suspend' then 'suspended' when 'cancel' then 'archived' else 'active' end where id=e.id;
 return jsonb_build_object('enrollment_id',e.id);
end;
$$;
revoke all on function public.get_elearning_progress_records(integer,uuid,boolean) from public,anon,authenticated;
grant execute on function public.get_elearning_progress_records(integer,uuid,boolean) to service_role;
revoke all on function public.get_elearning_enrollment_report(integer,uuid) from public,anon,authenticated;
grant execute on function public.get_elearning_enrollment_report(integer,uuid) to service_role;
revoke all on function public.get_elearning_enrollment_candidates(integer,uuid,text,integer,integer) from public,anon,authenticated;
grant execute on function public.get_elearning_enrollment_candidates(integer,uuid,text,integer,integer) to service_role;
revoke all on function public.manage_elearning_enrollments(integer,uuid,integer,text,integer[],uuid,text,text,boolean) from public,anon,authenticated;
grant execute on function public.manage_elearning_enrollments(integer,uuid,integer,text,integer[],uuid,text,text,boolean) to service_role;
notify pgrst,'reload schema';
commit;
