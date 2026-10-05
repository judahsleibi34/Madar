begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_120_schema_state_missing'; end if;
 if v_schema_version <> 119 then raise exception 'migration_120_expected_schema_119_got_%',v_schema_version; end if;
 update public.application_schema_state set schema_version = 120,applied_at=now() where contract_key = 'core';
end;
$$;
create table public.elearning_learners (
 id uuid primary key default gen_random_uuid(), tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
 name text not null check(char_length(btrim(name)) between 1 and 120),
 email text not null check(email=lower(btrim(email)) and char_length(email) between 3 and 254 and email like '%@%'),
 status text not null default 'active' check(status in ('active','archived')),
 created_by integer references public.users(id) on delete set null,
 revision integer not null default 1 check(revision>0),
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 unique(tenant_id,id), unique(tenant_id,email)
);
create table public.elearning_enrollments (
 id uuid primary key default gen_random_uuid(), tenant_id integer not null references public.tenants(tenant_id) on delete cascade, course_id uuid not null, learner_id uuid not null,
 status text not null default 'active' check(status in ('active','archived')),
 access_source text not null check(access_source in ('free','manual')),
 created_by integer references public.users(id) on delete set null,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 unique(tenant_id,course_id,id), unique(tenant_id,course_id,learner_id),
 foreign key(tenant_id,course_id) references public.elearning_courses(tenant_id,id),
 foreign key(tenant_id,learner_id) references public.elearning_learners(tenant_id,id)
);
create table public.elearning_lesson_completions (
 tenant_id integer not null references public.tenants(tenant_id) on delete cascade, course_id uuid not null, enrollment_id uuid not null, lesson_id uuid not null,
 completed_at timestamptz not null default now(), recorded_by integer references public.users(id) on delete set null,
 primary key(tenant_id,enrollment_id,lesson_id),
 foreign key(tenant_id,course_id,enrollment_id) references public.elearning_enrollments(tenant_id,course_id,id),
 foreign key(tenant_id,course_id,lesson_id) references public.elearning_lessons(tenant_id,course_id,id)
);
create trigger set_elearning_learners_updated_at before update on public.elearning_learners for each row execute function public.set_updated_at();
create trigger set_elearning_enrollments_updated_at before update on public.elearning_enrollments for each row execute function public.set_updated_at();
alter table public.elearning_learners enable row level security;
alter table public.elearning_enrollments enable row level security;
alter table public.elearning_lesson_completions enable row level security;
revoke all on public.elearning_learners,public.elearning_enrollments,public.elearning_lesson_completions from public,anon,authenticated,service_role;
grant select,insert,update on public.elearning_learners to service_role;
grant select on public.elearning_enrollments,public.elearning_lesson_completions to service_role;

create function public.manage_elearning_participation(p_tenant_id integer,p_course_id uuid,p_user_id integer,p_action text,p_payload jsonb)
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

create function public.get_elearning_progress(p_tenant_id integer,p_course_id uuid)
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
  select e.id,e.access_source,r.id learner_id,r.name,r.email,
   (select count(*)::integer from public.elearning_lesson_completions x join eligible l on l.id=x.lesson_id where x.tenant_id=p_tenant_id and x.enrollment_id=e.id) completed
  from public.elearning_enrollments e join public.elearning_learners r on(r.tenant_id,r.id)=(e.tenant_id,e.learner_id)
  where e.tenant_id=p_tenant_id and e.course_id=p_course_id and e.status='active' and r.status='active'
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
  'average_progress',coalesce(round(avg(progress_percent),2),0),
  'not_started_count',count(*) filter(where progress_status='not_started'),'active_count',count(*) filter(where progress_status='active'),'completed_count',count(*) filter(where progress_status='completed'),
  'enrollments',coalesce(jsonb_agg(jsonb_build_object('id',id,'learner_id',learner_id,'name',name,'email',email,'access_source',access_source,'completed_lessons',completed,'total_lessons',total,'progress_percent',progress_percent,'progress_status',progress_status,'sections',sections) order by name,id),'[]'::jsonb)) into result from records;
 return result;
end;
$$;
create function public.get_elearning_participation_counts(p_tenant_id integer,p_course_ids uuid[])
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
  where e.tenant_id=p_tenant_id and e.course_id=any(p_course_ids) and e.status='active' and r.status='active' group by e.course_id,e.id
 ), summaries as(select p.course_id,count(*) learner_count,coalesce(round(avg(coalesce(round(100.0*p.completed/nullif(t.total,0),2),0)),2),0) average_progress
  from participation p left join totals t on t.course_id=p.course_id group by p.course_id)
 select coalesce(jsonb_object_agg(c.id,jsonb_build_object('learner_count',coalesce(s.learner_count,0),'average_progress',coalesce(s.average_progress,0))),'{}'::jsonb)
 from public.elearning_courses c left join summaries s on s.course_id=c.id where c.tenant_id=p_tenant_id and c.id=any(p_course_ids);
$$;
revoke all on function public.manage_elearning_participation(integer,uuid,integer,text,jsonb) from public,anon,authenticated;
revoke all on function public.get_elearning_progress(integer,uuid) from public,anon,authenticated;
revoke all on function public.get_elearning_participation_counts(integer,uuid[]) from public,anon,authenticated;
grant execute on function public.manage_elearning_participation(integer,uuid,integer,text,jsonb) to service_role;
grant execute on function public.get_elearning_progress(integer,uuid) to service_role;
grant execute on function public.get_elearning_participation_counts(integer,uuid[]) to service_role;
notify pgrst,'reload schema';
commit;
