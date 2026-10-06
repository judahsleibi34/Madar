begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_126_schema_state_missing'; end if;
 if v_schema_version <> 125 then raise exception 'migration_126_expected_schema_125_got_%',v_schema_version; end if;
 update public.application_schema_state set schema_version=126,applied_at=now() where contract_key = 'core';
end;
$$;

alter table public.elearning_instructors add column user_id integer references public.users(id) on delete set null;
create unique index elearning_instructor_user_unique on public.elearning_instructors(tenant_id,user_id) where user_id is not null;
alter table public.elearning_enrollments drop constraint elearning_enrollments_access_source_check;
alter table public.elearning_enrollments add constraint elearning_enrollments_access_source_check check(access_source in ('manual','free','group'));

create table public.elearning_group_members (
 tenant_id integer not null references public.tenants(tenant_id) on delete cascade, group_id uuid not null, user_id integer not null,
 created_at timestamptz not null default now(), removed_at timestamptz,
 primary key(tenant_id,group_id,user_id),
 foreign key(tenant_id,group_id) references public.elearning_groups(tenant_id,id) on delete cascade,
 foreign key(tenant_id,user_id) references public.tenant_memberships(tenant_id,user_id) on delete cascade
);
create table public.elearning_group_courses (
 tenant_id integer not null references public.tenants(tenant_id) on delete cascade, group_id uuid not null, course_id uuid not null,
 created_at timestamptz not null default now(), removed_at timestamptz,
 primary key(tenant_id,group_id,course_id),
 foreign key(tenant_id,group_id) references public.elearning_groups(tenant_id,id) on delete cascade,
 foreign key(tenant_id,course_id) references public.elearning_courses(tenant_id,id) on delete cascade
);
create table public.elearning_course_instructors (
 tenant_id integer not null references public.tenants(tenant_id) on delete cascade, course_id uuid not null,instructor_id uuid not null,
 created_at timestamptz not null default now(),
 primary key(tenant_id,course_id,instructor_id),
 foreign key(tenant_id,course_id) references public.elearning_courses(tenant_id,id) on delete cascade,
 foreign key(tenant_id,instructor_id) references public.elearning_instructors(tenant_id,id) on delete cascade
);
create table public.elearning_group_instructors (
 tenant_id integer not null references public.tenants(tenant_id) on delete cascade, group_id uuid not null,instructor_id uuid not null,
 created_at timestamptz not null default now(),
 primary key(tenant_id,group_id,instructor_id),
 foreign key(tenant_id,group_id) references public.elearning_groups(tenant_id,id) on delete cascade,
 foreign key(tenant_id,instructor_id) references public.elearning_instructors(tenant_id,id) on delete cascade
);
create table public.elearning_access_grants (
 id uuid primary key default gen_random_uuid(), tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
 course_id uuid not null,enrollment_id uuid not null,
 grant_type text not null check(grant_type in ('manual','free','group','purchase')),
 source_group_id uuid, created_at timestamptz not null default now(), revoked_at timestamptz,
 constraint elearning_purchase_reserved check(grant_type<>'purchase'),
 check((grant_type='group')=(source_group_id is not null)),
 foreign key(tenant_id,course_id,enrollment_id) references public.elearning_enrollments(tenant_id,course_id,id) on delete cascade,
 foreign key(tenant_id,source_group_id,course_id) references public.elearning_group_courses(tenant_id,group_id,course_id) on delete cascade
);
create unique index elearning_individual_grant_unique on public.elearning_access_grants(tenant_id,enrollment_id,grant_type) where source_group_id is null;
create unique index elearning_group_grant_unique on public.elearning_access_grants(tenant_id,enrollment_id,source_group_id) where source_group_id is not null;
create index elearning_grants_course_idx on public.elearning_access_grants(tenant_id,course_id,enrollment_id);
insert into public.elearning_access_grants(tenant_id,course_id,enrollment_id,grant_type,created_at)
 select tenant_id,course_id,id,access_source,created_at from public.elearning_enrollments;

create function public.elearning_initial_individual_grant() returns trigger language plpgsql security definer set search_path='' as $$
begin
 if new.access_source in ('manual','free') then
 insert into public.elearning_access_grants(tenant_id,course_id,enrollment_id,grant_type) values(new.tenant_id,new.course_id,new.id,new.access_source) on conflict do nothing;
 end if;
 return new;
end;
$$;
create trigger elearning_initial_grant after insert on public.elearning_enrollments for each row execute function public.elearning_initial_individual_grant();

create function public.elearning_valid_grants(p_tenant_id integer,p_enrollment_id uuid)
returns jsonb language sql stable security definer set search_path='' as $$
 select coalesce(jsonb_agg(jsonb_build_object('id',a.id,'type',a.grant_type,'group_id',a.source_group_id,'group_name',g.name,'created_at',a.created_at) order by a.grant_type,g.name,a.id),'[]')
 from public.elearning_access_grants a
 join public.elearning_enrollments e on (e.tenant_id,e.id)=(a.tenant_id,a.enrollment_id)
 join public.elearning_learners l on (l.tenant_id,l.id)=(e.tenant_id,e.learner_id)
 left join public.elearning_groups g on(g.tenant_id,g.id)=(a.tenant_id,a.source_group_id)
 where a.tenant_id=p_tenant_id and a.enrollment_id=p_enrollment_id and a.revoked_at is null and
 (a.grant_type<>'group' or (g.status='active' and exists(select 1 from public.elearning_group_members m where m.tenant_id=a.tenant_id and m.group_id=a.source_group_id and m.user_id=l.user_id and m.removed_at is null)
 and exists(select 1 from public.elearning_group_courses c where c.tenant_id=a.tenant_id and c.group_id=a.source_group_id and c.course_id=a.course_id and c.removed_at is null)));
$$;
create function public.elearning_enrollment_has_access(p_tenant_id integer,p_enrollment_id uuid)
returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.elearning_enrollments e join public.elearning_learners l on (l.tenant_id,l.id)=(e.tenant_id,e.learner_id)
 where e.tenant_id=p_tenant_id and e.id=p_enrollment_id and e.status='active' and l.status='active'
 and (l.user_id is null or exists(select 1 from public.users u join public.tenant_memberships m on m.user_id=u.id and m.tenant_id=e.tenant_id and m.status='active' where u.id=l.user_id and u.account_status='active'))
 and jsonb_array_length(public.elearning_valid_grants(p_tenant_id,e.id))>0);
$$;

-- Legacy enrollment APIs remain available, but their source column is descriptive
-- only. Grants are additive and granting never overrides suspension/cancellation.
alter function public.manage_elearning_participation(integer,uuid,integer,text,jsonb) rename to manage_elearning_participation_schema125;
revoke all on function public.manage_elearning_participation_schema125(integer,uuid,integer,text,jsonb) from public,anon,authenticated,service_role;
create function public.manage_elearning_participation(p_tenant_id integer,p_course_id uuid,p_user_id integer,p_action text,p_payload jsonb)
returns jsonb language plpgsql security definer set search_path='' as $$
declare result jsonb; prior_status text; eid uuid;
begin
 perform pg_advisory_xact_lock(125,p_tenant_id);
 perform 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id for update;
 if p_action='enroll' then select status into prior_status from public.elearning_enrollments where tenant_id=p_tenant_id and course_id=p_course_id and learner_id=(p_payload->>'learner_id')::uuid; end if;
 if p_action='complete_lesson' and not public.elearning_enrollment_has_access(p_tenant_id,(p_payload->>'enrollment_id')::uuid) then raise exception using errcode='22023',message='elearning_access_unavailable'; end if;
 result:=public.manage_elearning_participation_schema125(p_tenant_id,p_course_id,p_user_id,p_action,p_payload);
 if p_action='enroll' then
  eid:=(result->>'enrollment_id')::uuid;
  if prior_status in ('suspended','archived') then update public.elearning_enrollments set status=prior_status where id=eid; end if;
  insert into public.elearning_access_grants(tenant_id,course_id,enrollment_id,grant_type) values(p_tenant_id,p_course_id,eid,p_payload->>'access_source')
   on conflict(tenant_id,enrollment_id,grant_type) where source_group_id is null do update set revoked_at=null;
 end if;
 return result;
end;
$$;

create function public.get_elearning_progress_records(p_tenant_id integer,p_course_id uuid,p_include_inactive boolean,p_include_details boolean)
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
  where e.tenant_id=p_tenant_id and e.course_id=p_course_id and (p_include_inactive or public.elearning_enrollment_has_access(p_tenant_id,e.id))
 ), records as(
  select p.*,t.n total,coalesce(round(100.0*p.completed/nullif(t.n,0),2),0) progress_percent,
   case when p.completed=0 then 'not_started' when p.completed=t.n then 'completed' else 'active' end progress_status,
   case when p_include_details then (select coalesce(jsonb_agg(jsonb_build_object('id',s.id,'name',s.name,'status',s.status,
    'total_lessons',(select count(*) from eligible l where l.section_id=s.id),
    'completed_lessons',(select count(*) from eligible l join public.elearning_lesson_completions x on x.lesson_id=l.id and x.tenant_id=p_tenant_id and x.enrollment_id=p.id where l.section_id=s.id),
    'progress_percent',coalesce((select round(100.0*count(x.lesson_id)/nullif(count(l.id),0),2) from eligible l left join public.elearning_lesson_completions x on x.lesson_id=l.id and x.tenant_id=p_tenant_id and x.enrollment_id=p.id where l.section_id=s.id),0),
    'lessons',(select coalesce(jsonb_agg(jsonb_build_object('id',l.id,'name',l.name,'completed',x.lesson_id is not null) order by l.position,l.id),'[]'::jsonb) from eligible l left join public.elearning_lesson_completions x on x.lesson_id=l.id and x.tenant_id=p_tenant_id and x.enrollment_id=p.id where l.section_id=s.id)
   ) order by s.position,s.id),'[]'::jsonb) from public.elearning_sections s where s.tenant_id=p_tenant_id and s.course_id=p_course_id and s.status <> 'archived') else '[]'::jsonb end sections
  from participants p cross join totals t
 ) select jsonb_build_object('available',true,'total_lessons',(select n from totals),'learner_count',count(*),
  'enrollment_active_count',count(*) filter(where public.elearning_enrollment_has_access(p_tenant_id,id)),
  'average_progress',coalesce(round(avg(progress_percent),2),0),
  'not_started_count',count(*) filter(where progress_status='not_started'),'active_count',count(*) filter(where progress_status='active'),'completed_count',count(*) filter(where progress_status='completed'),
  'enrollments',coalesce(jsonb_agg(jsonb_build_object('id',id,'learner_id',learner_id,'user_id',user_id,'enrollment_status',enrollment_status,'learner_status',learner_status,'enrolled_at',enrolled_at,'last_activity',last_activity,'group_id',null,'payment_status',null,'name',name,'email',email,'access_source',access_source,'access_sources',public.elearning_valid_grants(p_tenant_id,id),'effective_access',public.elearning_enrollment_has_access(p_tenant_id,id),'completed_lessons',completed,'total_lessons',total,'progress_percent',progress_percent,'progress_status',progress_status,'sections',sections) order by name,id),'[]'::jsonb)) into result from records;
 return result;
end;
$$;
-- Keep the existing report contract and percentage engine; summaries skip lesson-level JSON.
create or replace function public.get_elearning_progress_records(p_tenant_id integer,p_course_id uuid,p_include_inactive boolean)
returns jsonb language sql stable security definer set search_path='' as $$
 select public.get_elearning_progress_records(p_tenant_id,p_course_id,p_include_inactive,true);
$$;
revoke all on function public.get_elearning_progress_records(integer,uuid,boolean,boolean) from public,anon,authenticated,service_role;
create or replace function public.get_elearning_participation_counts(p_tenant_id integer,p_course_ids uuid[])
returns jsonb language sql stable security definer set search_path='' as $$
 with eligible as (
  select l.course_id,l.id from public.elearning_lessons l join public.elearning_sections s on(s.tenant_id,s.course_id,s.id)=(l.tenant_id,l.course_id,l.section_id)
  join public.elearning_courses c on(c.tenant_id,c.id)=(l.tenant_id,l.course_id)
  where l.tenant_id=p_tenant_id and l.course_id=any(p_course_ids) and l.status='published' and s.status='published' and c.status='published'
 ), totals as(select course_id,count(*) total from eligible group by course_id), participation as(
  select e.course_id,e.id,count(l.id) completed from public.elearning_enrollments e
  join public.elearning_learners r on(r.tenant_id,r.id)=(e.tenant_id,e.learner_id)
  left join public.elearning_lesson_completions x on x.tenant_id=e.tenant_id and x.course_id=e.course_id and x.enrollment_id=e.id
  left join eligible l on l.id=x.lesson_id and l.course_id=e.course_id
  where e.tenant_id=p_tenant_id and e.course_id=any(p_course_ids) and public.elearning_enrollment_has_access(p_tenant_id,e.id) group by e.course_id,e.id
 ), summaries as(select p.course_id,count(*) learner_count,coalesce(round(avg(coalesce(round(100.0*p.completed/nullif(t.total,0),2),0)),2),0) average_progress
  from participation p left join totals t on t.course_id=p.course_id group by p.course_id)
 select coalesce(jsonb_object_agg(c.id,jsonb_build_object('learner_count',coalesce(s.learner_count,0),'average_progress',coalesce(s.average_progress,0))),'{}'::jsonb)
 from public.elearning_courses c left join summaries s on s.course_id=c.id where c.tenant_id=p_tenant_id and c.id=any(p_course_ids);
$$;
create or replace function public.get_elearning_learner_course(p_tenant_id integer,p_user_id integer,p_course_id uuid,p_lesson_id uuid default null)
returns jsonb language plpgsql stable security definer set search_path='' as $$
declare c public.elearning_courses%rowtype; e uuid; report jsonb; cfg jsonb; sec jsonb; lesson jsonb; sections jsonb:='[]'; lessons jsonb; first_incomplete uuid; previous_incomplete boolean:=false; selected jsonb; blocks jsonb;
begin
 select * into c from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id and status='published';
 if not found then raise exception using errcode='P0002',message='elearning_learning_not_found'; end if;
 select n.id into e from public.elearning_enrollments n
 join public.elearning_learners r on (r.tenant_id,r.id)=(n.tenant_id,n.learner_id)
 join public.tenant_memberships m on m.tenant_id=n.tenant_id and m.user_id=r.user_id and m.status='active'
 join public.users u on u.id=m.user_id and u.account_status='active'
 where n.tenant_id=p_tenant_id and n.course_id=c.id and public.elearning_enrollment_has_access(p_tenant_id,n.id) and r.user_id=p_user_id;
 if e is null then raise exception using errcode='P0002',message='elearning_learning_not_found'; end if;
 select coalesce(settings,'{}') into cfg from public.elearning_settings where tenant_id=p_tenant_id;
 cfg:=coalesce(cfg,'{}');
 select item into report from jsonb_array_elements(public.get_elearning_progress(p_tenant_id,c.id)->'enrollments') item where item->>'id'=e::text;
 for sec in select value from jsonb_array_elements(report->'sections') where value->>'status'='published' loop
  lessons:='[]';
  for lesson in select value from jsonb_array_elements(sec->'lessons') loop
   lesson:=lesson || jsonb_build_object('locked',coalesce((cfg->>'sequential_progression')::boolean,false) and previous_incomplete);
   if lesson->>'id'=p_lesson_id::text then selected:=lesson || jsonb_build_object('section_id',sec->>'id','section_name',sec->>'name'); end if;
   if not (lesson->>'completed')::boolean then
    if first_incomplete is null then first_incomplete:=(lesson->>'id')::uuid; end if;
    previous_incomplete:=true;
   end if;
   lessons:=lessons || jsonb_build_array(lesson);
  end loop;
  sections:=sections || jsonb_build_array(sec || jsonb_build_object('lessons',lessons));
 end loop;
 if p_lesson_id is not null then
  if selected is null then raise exception using errcode='P0002',message='elearning_learning_not_found'; end if;
  if (selected->>'locked')::boolean then raise exception using errcode='42501',message='elearning_lesson_locked'; end if;
  select coalesce(jsonb_agg(jsonb_build_object('id',b.id,'type',b.type,'title',b.title,'content',b.content,'position',b.position,'media_id',b.media_id,
   'media',case when a.id is not null then jsonb_build_object('id',a.id,'url','/uploads/'||a.storage_key,'filename',a.original_filename,'mime_type',a.mime_type) else null end) order by b.position,b.id),'[]') into blocks
  from public.elearning_content_blocks b left join public.builder_assets a on (a.tenant_id,a.id)=(b.tenant_id,b.media_id) and a.status in ('active','unreferenced')
  where b.tenant_id=p_tenant_id and b.course_id=c.id and b.lesson_id=p_lesson_id and b.archived_at is null;
 end if;
 return jsonb_build_object('course',jsonb_build_object('id',c.id,'name',c.name,'description',c.description,'cover_url',c.cover_asset),
 'progress',report - 'sections' - 'name' - 'email' - 'learner_id' - 'access_source', 'sections',sections,'continue_lesson_id',first_incomplete,
 'lesson',selected,'blocks',coalesce(blocks,'[]'));
end;
$$;
create or replace function public.get_elearning_my_learning(p_tenant_id integer,p_user_id integer,p_limit integer default 50,p_offset integer default 0)
returns jsonb language sql stable security definer set search_path='' as $$
 select coalesce(jsonb_agg(public.get_elearning_learner_course(p_tenant_id,p_user_id,id) order by name,id),'[]') from (
 select c.id,c.name from public.elearning_courses c
 join public.elearning_enrollments n on (n.tenant_id,n.course_id)=(c.tenant_id,c.id) and public.elearning_enrollment_has_access(p_tenant_id,n.id)
 join public.elearning_learners r on (r.tenant_id,r.id)=(n.tenant_id,n.learner_id) and r.status='active' and r.user_id=p_user_id
 join public.tenant_memberships m on m.tenant_id=c.tenant_id and m.user_id=r.user_id and m.status='active'
 join public.users u on u.id=m.user_id and u.account_status='active'
 where c.tenant_id=p_tenant_id and c.status='published'
 order by c.name,c.id limit least(greatest(p_limit,1),101) offset greatest(p_offset,0)) courses;
$$;
create or replace function public.manage_elearning_enrollments(p_tenant_id integer,p_course_id uuid,p_actor_id integer,p_action text,p_user_ids integer[],p_enrollment_id uuid,p_expected_status text,p_access_source text,p_confirmed boolean)
returns jsonb language plpgsql security definer set search_path='' as $$
declare c public.elearning_courses%rowtype; e public.elearning_enrollments%rowtype; l public.elearning_learners%rowtype; u public.users%rowtype; v_id integer; v_learner uuid; v_results jsonb:='[]'::jsonb;
begin
 perform pg_advisory_xact_lock(125,p_tenant_id);
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
   if exists(select 1 from public.elearning_enrollments enr join public.elearning_access_grants a on(a.tenant_id,a.enrollment_id)=(enr.tenant_id,enr.id) where enr.tenant_id=p_tenant_id and enr.course_id=p_course_id and enr.learner_id=v_learner and enr.status='active' and a.grant_type=p_access_source and a.revoked_at is null) then raise exception using errcode='23505',message='elearning_already_enrolled'; end if;
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
  if jsonb_array_length(public.elearning_valid_grants(p_tenant_id,e.id))=0 then raise exception using errcode='22023',message='elearning_no_valid_grants'; end if;
  if c.status<>'published' then raise exception using errcode='22023',message='elearning_course_not_published'; end if;
  select * into l from public.elearning_learners where tenant_id=p_tenant_id and id=e.learner_id;
  if l.status<>'active' or (l.user_id is not null and not exists(select 1 from public.users usr join public.tenant_memberships m on m.user_id=usr.id and m.tenant_id=p_tenant_id and m.status='active' where usr.id=l.user_id and usr.account_status='active')) then raise exception using errcode='22023',message='elearning_profile_unavailable'; end if;
 end if;
 update public.elearning_enrollments set status=case p_action when 'suspend' then 'suspended' when 'cancel' then 'archived' else 'active' end where id=e.id;
 return jsonb_build_object('enrollment_id',e.id);
end;
$$;
create or replace function public.get_elearning_enrollment_candidates(p_tenant_id integer,p_course_id uuid,p_query text,p_limit integer,p_offset integer)
returns jsonb language plpgsql stable security definer set search_path='' as $$
begin
 if not exists(select 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id) then raise exception using errcode='P0002',message='elearning_course_not_found'; end if;
 if p_limit not between 1 and 100 or p_offset < 0 or char_length(p_query)>120 then raise exception using errcode='22023',message='invalid_candidate_query'; end if;
 return (select coalesce(jsonb_agg(to_jsonb(u) order by u.name,u.id),'[]'::jsonb) from (
  select u.id,concat_ws(' ',u.first_name,u.last_name) name,u.email,
   exists(select 1 from public.elearning_learners l join public.elearning_enrollments e on e.tenant_id=l.tenant_id and e.learner_id=l.id where l.tenant_id=p_tenant_id and (l.user_id=u.id or (l.user_id is null and l.email=lower(btrim(u.email)))) and e.course_id=p_course_id and exists(select 1 from public.elearning_access_grants a where a.tenant_id=e.tenant_id and a.enrollment_id=e.id and a.source_group_id is null and a.revoked_at is null)) already_enrolled,
   (select coalesce(jsonb_agg(a.grant_type order by a.grant_type),'[]'::jsonb) from public.elearning_learners l join public.elearning_enrollments e on e.tenant_id=l.tenant_id and e.learner_id=l.id join public.elearning_access_grants a on (a.tenant_id,a.enrollment_id)=(e.tenant_id,e.id) where l.tenant_id=p_tenant_id and (l.user_id=u.id or (l.user_id is null and l.email=lower(btrim(u.email)))) and e.course_id=p_course_id and a.source_group_id is null and a.revoked_at is null) individual_sources
  from public.users u join public.tenant_memberships m on m.user_id=u.id
  where m.tenant_id=p_tenant_id and m.status='active' and u.account_status='active'
   and (p_query='' or position(lower(p_query) in lower(concat_ws(' ',u.first_name,u.last_name,u.email)))>0)
  order by name,u.id limit p_limit+1 offset p_offset
 ) u);
end;
$$;

create function public.elearning_ensure_group_enrollment(p_tenant_id integer,p_course_id uuid,p_user_id integer,p_actor_id integer)
returns uuid language plpgsql security definer set search_path='' as $$
declare u public.users%rowtype; l public.elearning_learners%rowtype; eid uuid;
begin
 -- Publication gates runtime access; retain membership-derived grants while a course is unpublished.
 perform 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id for update;
 if not found then raise exception using errcode='P0002',message='elearning_course_not_found'; end if;
 select usr.* into u from public.users usr join public.tenant_memberships m on m.user_id=usr.id and m.tenant_id=p_tenant_id and m.status='active' where usr.id=p_user_id and usr.account_status='active';
 if not found then raise exception using errcode='P0002',message='elearning_tenant_user_not_found'; end if;
 select * into l from public.elearning_learners where tenant_id=p_tenant_id and (user_id=u.id or email=lower(btrim(u.email))) order by user_id nulls last limit 1 for update;
 if found then
  if l.status<>'active' or (l.user_id is not null and l.user_id<>u.id) then raise exception using errcode='22023',message='elearning_profile_unavailable'; end if;
  update public.elearning_learners set user_id=u.id where id=l.id and user_id is null;
 else
  insert into public.elearning_learners(tenant_id,user_id,name,email,created_by) values(p_tenant_id,u.id,left(concat_ws(' ',u.first_name,u.last_name),120),lower(btrim(u.email)),p_actor_id) returning * into l;
 end if;
 insert into public.elearning_enrollments(tenant_id,course_id,learner_id,access_source,created_by) values(p_tenant_id,p_course_id,l.id,'group',p_actor_id) on conflict(tenant_id,course_id,learner_id) do nothing;
 select id into eid from public.elearning_enrollments where tenant_id=p_tenant_id and course_id=p_course_id and learner_id=l.id;
 return eid;
end;
$$;

create function public.manage_elearning_relationships(p_tenant_id integer,p_actor_id integer,p_kind text,p_entity_id uuid,p_action text,p_target_id uuid default null,p_user_ids integer[] default null,p_confirmed boolean default false)
returns jsonb language plpgsql security definer set search_path='' as $$
declare gid uuid; cid uuid; iid uuid; uid integer; eid uuid; member record; assignment record;
begin
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant_id and user_id=p_actor_id and role in ('owner','admin') and status='active') then raise exception using errcode='42501',message='elearning_relationship_forbidden'; end if;
 perform pg_advisory_xact_lock(125,p_tenant_id);
 if p_kind='group' then
  select id into gid from public.elearning_groups where tenant_id=p_tenant_id and id=p_entity_id for update;
 elsif p_kind='course' then
  select id into cid from public.elearning_courses where tenant_id=p_tenant_id and id=p_entity_id for update;
 elsif p_kind='instructor' then
  select id into iid from public.elearning_instructors where tenant_id=p_tenant_id and id=p_entity_id for update;
 else raise exception using errcode='22023',message='elearning_invalid_kind'; end if;
 if not found then raise exception using errcode='P0002',message='elearning_relationship_not_found'; end if;
 if p_action like 'remove_%' or p_action like 'revoke_%' then
  if p_confirmed is distinct from true then raise exception using errcode='22023',message='elearning_confirmation_required'; end if;
 end if;
 if p_action in ('add_members','remove_member') and p_kind='group' then
  if coalesce(cardinality(p_user_ids),0) not between 1 and 100 or (select count(distinct v) from unnest(p_user_ids) v)<>cardinality(p_user_ids) then raise exception using errcode='22023',message='elearning_invalid_users'; end if;
  if p_action='add_members' and not exists(select 1 from public.elearning_groups where id=gid and status='active') then raise exception using errcode='22023',message='elearning_group_archived'; end if;
  if p_action='add_members' and (select count(*) from public.users u join public.tenant_memberships m on m.user_id=u.id and m.tenant_id=p_tenant_id and m.status='active' where u.id=any(p_user_ids) and u.account_status='active')<>cardinality(p_user_ids) then raise exception using errcode='P0002',message='elearning_tenant_user_not_found'; end if;
  foreach uid in array p_user_ids loop
   if p_action='remove_member' then
    if not exists(select 1 from public.elearning_group_members where tenant_id=p_tenant_id and group_id=gid and user_id=uid) then raise exception using errcode='P0002',message='elearning_member_not_found'; end if;
    update public.elearning_group_members set removed_at=coalesce(removed_at,now()) where tenant_id=p_tenant_id and group_id=gid and user_id=uid;
    update public.elearning_access_grants a set revoked_at=coalesce(a.revoked_at,now()) from public.elearning_enrollments e join public.elearning_learners l on(l.tenant_id,l.id)=(e.tenant_id,e.learner_id)
     where a.tenant_id=p_tenant_id and a.source_group_id=gid and (a.tenant_id,a.enrollment_id)=(e.tenant_id,e.id) and l.user_id=uid;
   else
    insert into public.elearning_group_members(tenant_id,group_id,user_id) values(p_tenant_id,gid,uid) on conflict(tenant_id,group_id,user_id) do update set removed_at=null;
    for assignment in select course_id from public.elearning_group_courses gc join public.elearning_courses c on(c.tenant_id,c.id)=(gc.tenant_id,gc.course_id) where gc.tenant_id=p_tenant_id and gc.group_id=gid and gc.removed_at is null order by gc.course_id loop
     eid:=public.elearning_ensure_group_enrollment(p_tenant_id,assignment.course_id,uid,p_actor_id);
     insert into public.elearning_access_grants(tenant_id,course_id,enrollment_id,grant_type,source_group_id) values(p_tenant_id,assignment.course_id,eid,'group',gid)
      on conflict(tenant_id,enrollment_id,source_group_id) where source_group_id is not null do update set revoked_at=null;
    end loop;
   end if;
  end loop;
 elsif (p_kind='group' and p_action in ('assign_course','remove_course')) or (p_kind='course' and p_action in ('assign_group','remove_group')) then
  if p_kind='group' then cid:=p_target_id; else gid:=p_target_id; end if;
  if not exists(select 1 from public.elearning_groups where tenant_id=p_tenant_id and id=gid) or not exists(select 1 from public.elearning_courses where tenant_id=p_tenant_id and id=cid) then raise exception using errcode='P0002',message='elearning_assignment_not_found'; end if;
  perform 1 from public.elearning_courses where tenant_id=p_tenant_id and id=cid for update;
  if p_action like 'remove_%' then
   update public.elearning_group_courses set removed_at=coalesce(removed_at,now()) where tenant_id=p_tenant_id and group_id=gid and course_id=cid;
   update public.elearning_access_grants set revoked_at=coalesce(revoked_at,now()) where tenant_id=p_tenant_id and source_group_id=gid and course_id=cid;
  else
   if not exists(select 1 from public.elearning_groups where id=gid and status='active') or not exists(select 1 from public.elearning_courses where id=cid and status='published') then raise exception using errcode='22023',message='elearning_assignment_inactive'; end if;
   insert into public.elearning_group_courses(tenant_id,group_id,course_id) values(p_tenant_id,gid,cid) on conflict(tenant_id,group_id,course_id) do update set removed_at=null;
   for member in select m.user_id from public.elearning_group_members m join public.users u on u.id=m.user_id and u.account_status='active' join public.tenant_memberships t on t.tenant_id=m.tenant_id and t.user_id=m.user_id and t.status='active' where m.tenant_id=p_tenant_id and m.group_id=gid and m.removed_at is null order by m.user_id loop
    eid:=public.elearning_ensure_group_enrollment(p_tenant_id,cid,member.user_id,p_actor_id);
    insert into public.elearning_access_grants(tenant_id,course_id,enrollment_id,grant_type,source_group_id) values(p_tenant_id,cid,eid,'group',gid)
     on conflict(tenant_id,enrollment_id,source_group_id) where source_group_id is not null do update set revoked_at=null;
   end loop;
  end if;
 elsif (p_action in ('assign_instructor','remove_instructor') and p_kind in ('course','group')) or (p_kind='instructor' and p_action in ('assign_course','remove_course','assign_group','remove_group')) then
  if p_kind<>'instructor' then iid:=p_target_id; elsif p_action like '%course' then cid:=p_target_id; else gid:=p_target_id; end if;
  if not exists(select 1 from public.elearning_instructors where tenant_id=p_tenant_id and id=iid) or (cid is not null and not exists(select 1 from public.elearning_courses where tenant_id=p_tenant_id and id=cid)) or (gid is not null and not exists(select 1 from public.elearning_groups where tenant_id=p_tenant_id and id=gid)) then raise exception using errcode='P0002',message='elearning_instructor_assignment_not_found'; end if;
  if p_action like 'assign_%' and (not exists(select 1 from public.elearning_instructors where id=iid and status='active') or (gid is not null and not exists(select 1 from public.elearning_groups where id=gid and status='active')) or (cid is not null and exists(select 1 from public.elearning_courses where id=cid and status='archived'))) then raise exception using errcode='22023',message='elearning_assignment_inactive'; end if;
  if cid is not null then
   if p_action like 'remove_%' then delete from public.elearning_course_instructors where tenant_id=p_tenant_id and course_id=cid and instructor_id=iid;
   else insert into public.elearning_course_instructors values(p_tenant_id,cid,iid,now()) on conflict do nothing; end if;
  else
   if p_action like 'remove_%' then delete from public.elearning_group_instructors where tenant_id=p_tenant_id and group_id=gid and instructor_id=iid;
   else insert into public.elearning_group_instructors values(p_tenant_id,gid,iid,now()) on conflict do nothing; end if;
  end if;
 elsif p_kind='instructor' and p_action='link_user' then
  if cardinality(p_user_ids) is distinct from 1 then raise exception using errcode='22023',message='elearning_select_one_user'; end if;
  uid:=p_user_ids[1];
  if not exists(select 1 from public.users u join public.tenant_memberships m on m.user_id=u.id and m.tenant_id=p_tenant_id and m.status='active' where u.id=uid and u.account_status='active') then raise exception using errcode='P0002',message='elearning_tenant_user_not_found'; end if;
  update public.elearning_instructors set user_id=uid,revision=revision+1 where id=iid;
 elsif p_kind='course' and p_action in ('revoke_manual','revoke_free') then
  if not exists(select 1 from public.elearning_enrollments where tenant_id=p_tenant_id and course_id=cid and id=p_target_id) then raise exception using errcode='P0002',message='elearning_enrollment_not_found'; end if;
  update public.elearning_access_grants set revoked_at=coalesce(revoked_at,now()) where tenant_id=p_tenant_id and course_id=cid and enrollment_id=p_target_id and grant_type=substr(p_action,8) and source_group_id is null;
 else raise exception using errcode='22023',message='elearning_invalid_action'; end if;
 return jsonb_build_object('saved',true);
end;
$$;
create or replace function public.complete_elearning_learner_lesson(p_tenant_id integer,p_user_id integer,p_course_id uuid,p_lesson_id uuid)
returns jsonb language plpgsql security definer set search_path='' as $$
declare snapshot jsonb;
begin
 perform pg_advisory_xact_lock(125,p_tenant_id);
 -- Serialize against enrollment/status/structure/content changes on this course.
 perform 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id for update;
 snapshot:=public.get_elearning_learner_course(p_tenant_id,p_user_id,p_course_id,p_lesson_id);
 insert into public.elearning_lesson_completions(tenant_id,course_id,enrollment_id,lesson_id,recorded_by)
 values(p_tenant_id,p_course_id,(snapshot->'progress'->>'id')::uuid,p_lesson_id,p_user_id) on conflict do nothing;
 return public.get_elearning_learner_course(p_tenant_id,p_user_id,p_course_id,p_lesson_id);
end;
$$;
alter table public.elearning_group_members enable row level security;
revoke all on public.elearning_group_members from public,anon,authenticated,service_role;
grant select on public.elearning_group_members to service_role;
alter table public.elearning_group_courses enable row level security;
revoke all on public.elearning_group_courses from public,anon,authenticated,service_role;
grant select on public.elearning_group_courses to service_role;
alter table public.elearning_course_instructors enable row level security;
revoke all on public.elearning_course_instructors from public,anon,authenticated,service_role;
grant select on public.elearning_course_instructors to service_role;
alter table public.elearning_group_instructors enable row level security;
revoke all on public.elearning_group_instructors from public,anon,authenticated,service_role;
grant select on public.elearning_group_instructors to service_role;
alter table public.elearning_access_grants enable row level security;
revoke all on public.elearning_access_grants from public,anon,authenticated,service_role;
grant select on public.elearning_access_grants to service_role;
revoke all on function public.elearning_initial_individual_grant() from public,anon,authenticated,service_role;
revoke all on function public.elearning_ensure_group_enrollment(integer,uuid,integer,integer) from public,anon,authenticated,service_role;
revoke all on function public.elearning_valid_grants(integer,uuid) from public,anon,authenticated;
grant execute on function public.elearning_valid_grants(integer,uuid) to service_role;
revoke all on function public.elearning_enrollment_has_access(integer,uuid) from public,anon,authenticated;
grant execute on function public.elearning_enrollment_has_access(integer,uuid) to service_role;
revoke all on function public.manage_elearning_participation(integer,uuid,integer,text,jsonb) from public,anon,authenticated;
grant execute on function public.manage_elearning_participation(integer,uuid,integer,text,jsonb) to service_role;
revoke all on function public.manage_elearning_relationships(integer,integer,text,uuid,text,uuid,integer[],boolean) from public,anon,authenticated;
grant execute on function public.manage_elearning_relationships(integer,integer,text,uuid,text,uuid,integer[],boolean) to service_role;

create function public.get_elearning_relationships(p_tenant_id integer,p_kind text,p_entity_id uuid,p_member_query text default '',p_member_offset integer default 0)
returns jsonb language plpgsql stable security definer set search_path='' as $$
declare entity jsonb; members jsonb:='[]'; courses jsonb:='[]'; groups jsonb:='[]'; instructors jsonb:='[]'; item record; progress jsonb; summary jsonb; member_count integer:=0;
begin
 if p_kind='group' then
  select to_jsonb(g) into entity from public.elearning_groups g where tenant_id=p_tenant_id and id=p_entity_id;
  select count(*) into member_count from public.elearning_group_members where tenant_id=p_tenant_id and group_id=p_entity_id and removed_at is null;
  select coalesce(jsonb_agg(to_jsonb(v) order by v.name,v.id),'[]') into members from (
   select u.id,concat_ws(' ',u.first_name,u.last_name) name,u.email,u.account_status,m.created_at,
   coalesce(tm.status,'disabled') membership_status
   from public.elearning_group_members m join public.users u on u.id=m.user_id left join public.tenant_memberships tm on (tm.tenant_id,tm.user_id)=(m.tenant_id,m.user_id)
   where m.tenant_id=p_tenant_id and m.group_id=p_entity_id and m.removed_at is null and (p_member_query='' or position(lower(p_member_query) in lower(concat_ws(' ',u.first_name,u.last_name,u.email)))>0) order by name,u.id limit 51 offset greatest(p_member_offset,0)) v;
  for item in select c.id,c.name,c.status from public.elearning_group_courses a join public.elearning_courses c on(c.tenant_id,c.id)=(a.tenant_id,a.course_id) where a.tenant_id=p_tenant_id and a.group_id=p_entity_id and a.removed_at is null order by c.name,c.id loop
   progress:=public.get_elearning_progress_records(p_tenant_id,item.id,false,false);
   select jsonb_build_object('learner_count',count(*),'average_progress',coalesce(round(avg((r->>'progress_percent')::numeric),2),0),'completed_count',count(*) filter(where r->>'progress_status'='completed'),'active_count',count(*) filter(where r->>'progress_status'='active'),'not_started_count',count(*) filter(where r->>'progress_status'='not_started')) into summary
    from jsonb_array_elements(progress->'enrollments') r where exists(select 1 from public.elearning_group_members m where m.tenant_id=p_tenant_id and m.group_id=p_entity_id and m.removed_at is null and m.user_id=(r->>'user_id')::integer);
   courses:=courses || jsonb_build_array(to_jsonb(item)||summary);
  end loop;
  select coalesce(jsonb_agg(jsonb_build_object('id',i.id,'name',i.name,'email',i.email,'status',i.status) order by i.name,i.id),'[]') into instructors from public.elearning_group_instructors a join public.elearning_instructors i on(i.tenant_id,i.id)=(a.tenant_id,a.instructor_id) where a.tenant_id=p_tenant_id and a.group_id=p_entity_id;
 elsif p_kind='course' then
  select to_jsonb(c) into entity from public.elearning_courses c where tenant_id=p_tenant_id and id=p_entity_id;
  select coalesce(jsonb_agg(jsonb_build_object('id',g.id,'name',g.name,'status',g.status,'member_count',(select count(*) from public.elearning_group_members m where m.tenant_id=g.tenant_id and m.group_id=g.id and m.removed_at is null)) order by g.name,g.id),'[]') into groups from public.elearning_group_courses a join public.elearning_groups g on(g.tenant_id,g.id)=(a.tenant_id,a.group_id) where a.tenant_id=p_tenant_id and a.course_id=p_entity_id and a.removed_at is null;
  select coalesce(jsonb_agg(jsonb_build_object('id',i.id,'name',i.name,'email',i.email,'status',i.status) order by i.name,i.id),'[]') into instructors from public.elearning_course_instructors a join public.elearning_instructors i on(i.tenant_id,i.id)=(a.tenant_id,a.instructor_id) where a.tenant_id=p_tenant_id and a.course_id=p_entity_id;
 elsif p_kind='instructor' then
  select to_jsonb(i)||jsonb_build_object('user_name',concat_ws(' ',u.first_name,u.last_name),'user_email',u.email) into entity from public.elearning_instructors i left join public.users u on u.id=i.user_id where i.tenant_id=p_tenant_id and i.id=p_entity_id;
  select coalesce(jsonb_agg(jsonb_build_object('id',c.id,'name',c.name,'status',c.status) order by c.name,c.id),'[]') into courses from public.elearning_course_instructors a join public.elearning_courses c on(c.tenant_id,c.id)=(a.tenant_id,a.course_id) where a.tenant_id=p_tenant_id and a.instructor_id=p_entity_id;
  select coalesce(jsonb_agg(jsonb_build_object('id',g.id,'name',g.name,'status',g.status) order by g.name,g.id),'[]') into groups from public.elearning_group_instructors a join public.elearning_groups g on(g.tenant_id,g.id)=(a.tenant_id,a.group_id) where a.tenant_id=p_tenant_id and a.instructor_id=p_entity_id;
 else raise exception using errcode='22023',message='elearning_invalid_kind'; end if;
 if entity is null then raise exception using errcode='P0002',message='elearning_relationship_not_found'; end if;
 return jsonb_build_object('entity',entity,'members',(select coalesce(jsonb_agg(value),'[]') from jsonb_array_elements(members) with ordinality v(value,ord) where ord<=50),'member_count',member_count,'members_has_more',jsonb_array_length(members)>50,'courses',courses,'groups',groups,'instructors',instructors);
end;
$$;

create function public.get_elearning_relationship_candidates(p_tenant_id integer,p_kind text,p_query text,p_limit integer,p_offset integer)
returns jsonb language plpgsql stable security definer set search_path='' as $$
declare result jsonb;
begin
 if p_kind='users' then
  select coalesce(jsonb_agg(to_jsonb(v) order by v.name,v.id),'[]') into result from (select u.id,concat_ws(' ',u.first_name,u.last_name) name,u.email from public.users u join public.tenant_memberships m on m.user_id=u.id and m.tenant_id=p_tenant_id and m.status='active' where u.account_status='active' and (p_query='' or position(lower(p_query) in lower(concat_ws(' ',u.first_name,u.last_name,u.email)))>0) order by name,u.id limit least(greatest(p_limit,1),101) offset greatest(p_offset,0)) v;
 elsif p_kind='courses' then
  select coalesce(jsonb_agg(to_jsonb(v) order by v.name,v.id),'[]') into result from (select id,name,status from public.elearning_courses where tenant_id=p_tenant_id and status='published' and (p_query='' or position(lower(p_query) in lower(name))>0) order by name,id limit least(greatest(p_limit,1),101) offset greatest(p_offset,0)) v;
 elsif p_kind='groups' then
  select coalesce(jsonb_agg(to_jsonb(v) order by v.name,v.id),'[]') into result from (select id,name,status from public.elearning_groups where tenant_id=p_tenant_id and status='active' and (p_query='' or position(lower(p_query) in lower(name))>0) order by name,id limit least(greatest(p_limit,1),101) offset greatest(p_offset,0)) v;
 elsif p_kind='instructors' then
  select coalesce(jsonb_agg(to_jsonb(v) order by v.name,v.id),'[]') into result from (select id,name,email,status from public.elearning_instructors where tenant_id=p_tenant_id and status='active' and (p_query='' or position(lower(p_query) in lower(name||' '||email))>0) order by name,id limit least(greatest(p_limit,1),101) offset greatest(p_offset,0)) v;
 else raise exception using errcode='22023',message='elearning_invalid_kind'; end if;
 return result;
end;
$$;
create function public.get_elearning_directory_summary(p_tenant_id integer,p_kind text)
returns jsonb language sql stable security definer set search_path='' as $$
 select case when p_kind='groups' then (select coalesce(jsonb_object_agg(g.id,jsonb_build_object('members',(select count(*) from public.elearning_group_members m where m.tenant_id=g.tenant_id and m.group_id=g.id and m.removed_at is null),'courses',(select count(*) from public.elearning_group_courses c where c.tenant_id=g.tenant_id and c.group_id=g.id and c.removed_at is null),'instructors',(select count(*) from public.elearning_group_instructors i where i.tenant_id=g.tenant_id and i.group_id=g.id))),'{}') from public.elearning_groups g where g.tenant_id=p_tenant_id)
 else (select coalesce(jsonb_object_agg(i.id,jsonb_build_object('courses',(select count(*) from public.elearning_course_instructors c where c.tenant_id=i.tenant_id and c.instructor_id=i.id),'groups',(select count(*) from public.elearning_group_instructors g where g.tenant_id=i.tenant_id and g.instructor_id=i.id))),'{}') from public.elearning_instructors i where i.tenant_id=p_tenant_id) end;
$$;
alter table public.elearning_instructors add constraint elearning_instructor_membership_fk foreign key(tenant_id,user_id) references public.tenant_memberships(tenant_id,user_id) on delete set null (user_id);
revoke all on function public.get_elearning_relationships(integer,text,uuid,text,integer),public.get_elearning_relationship_candidates(integer,text,text,integer,integer),public.get_elearning_directory_summary(integer,text) from public,anon,authenticated;
grant execute on function public.get_elearning_relationships(integer,text,uuid,text,integer),public.get_elearning_relationship_candidates(integer,text,text,integer,integer),public.get_elearning_directory_summary(integer,text) to service_role;
notify pgrst,'reload schema';
commit;
