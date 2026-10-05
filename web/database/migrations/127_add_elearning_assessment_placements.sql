begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_127_schema_state_missing'; end if;
 if v_schema_version <> 126 then raise exception 'migration_127_expected_schema_126_got_%',v_schema_version; end if;
 update public.application_schema_state set schema_version=127,applied_at=now() where contract_key = 'core';
end;
$$;


-- One engine, explicit placements. Lesson placement identity remains its block ID.
create table public.elearning_assessment_placements (
 id uuid primary key default gen_random_uuid(), tenant_id integer not null, course_id uuid not null,
 assessment_id uuid not null, placement_type text not null check(placement_type in ('lesson','section','course')),
 section_id uuid, lesson_id uuid, block_id uuid, position integer not null default 0 check(position>=0),
 required_for_completion boolean not null default false, archived_at timestamptz,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 unique(tenant_id,course_id,id), unique(tenant_id,assessment_id,id),
 foreign key(tenant_id,course_id) references public.elearning_courses(tenant_id,id) on delete cascade,
 foreign key(tenant_id,course_id,section_id) references public.elearning_sections(tenant_id,course_id,id) on delete cascade,
 foreign key(tenant_id,course_id,lesson_id) references public.elearning_lessons(tenant_id,course_id,id) on delete cascade,
 foreign key(tenant_id,assessment_id) references public.elearning_assessments(tenant_id,id) on delete restrict,
 check((placement_type='course' and section_id is null and lesson_id is null and block_id is null) or
       (placement_type='section' and section_id is not null and lesson_id is null and block_id is null) or
       (placement_type='lesson' and section_id is not null and lesson_id is not null))
);
create unique index elearning_placement_active_target on public.elearning_assessment_placements(tenant_id,course_id,placement_type,coalesce(section_id,'00000000-0000-0000-0000-000000000000'::uuid),coalesce(lesson_id,'00000000-0000-0000-0000-000000000000'::uuid),assessment_id) where archived_at is null;
create index elearning_placement_outline on public.elearning_assessment_placements(tenant_id,course_id,section_id,position);
insert into public.elearning_assessment_placements(id,tenant_id,course_id,assessment_id,placement_type,section_id,lesson_id,block_id,position,required_for_completion,archived_at)
select b.id,b.tenant_id,b.course_id,b.assessment_id,'lesson',l.section_id,b.lesson_id,b.id,b.position,b.required_for_completion,b.archived_at
from public.elearning_content_blocks b join public.elearning_lessons l on l.id=b.lesson_id where b.type='assessment';
-- Preserve attempts whose lesson block was previously removed.
insert into public.elearning_assessment_placements(tenant_id,course_id,assessment_id,placement_type,section_id,lesson_id,archived_at)
select distinct t.tenant_id,t.course_id,t.assessment_id,'lesson',l.section_id,t.lesson_id,now()
from public.elearning_assessment_attempts t join public.elearning_lessons l on l.id=t.lesson_id where t.block_id is null;
alter table public.elearning_assessment_attempts add column placement_id uuid;
update public.elearning_assessment_attempts t set placement_id=p.id from public.elearning_assessment_placements p
where (t.tenant_id,t.course_id,t.assessment_id,t.lesson_id)=(p.tenant_id,p.course_id,p.assessment_id,p.lesson_id) and (t.block_id=p.block_id or t.block_id is null and p.block_id is null);
alter table public.elearning_assessment_attempts alter column placement_id set not null;
alter table public.elearning_assessment_attempts alter column lesson_id drop not null;
alter table public.elearning_assessment_attempts add foreign key(tenant_id,course_id,placement_id) references public.elearning_assessment_placements(tenant_id,course_id,id) on delete cascade;
alter table public.elearning_assessment_attempts add constraint elearning_attempt_placement_fk foreign key(tenant_id,assessment_id,placement_id) references public.elearning_assessment_placements(tenant_id,assessment_id,id) on delete cascade;
do $$ declare c record;begin
 for c in select conname from pg_constraint where conrelid='public.elearning_assessment_attempts'::regclass and contype='u' and pg_get_constraintdef(oid) like '%assessment_id, enrollment_id, attempt_number%' loop
 execute format('alter table public.elearning_assessment_attempts drop constraint %I',c.conname);end loop;
end $$;
drop index public.elearning_one_open_assessment_attempt;
alter table public.elearning_assessment_attempts add unique(tenant_id,placement_id,enrollment_id,attempt_number);
create unique index elearning_one_open_assessment_attempt on public.elearning_assessment_attempts(tenant_id,placement_id,enrollment_id) where status='in_progress';

create table public.elearning_completion_events (
 id uuid primary key default gen_random_uuid(),tenant_id integer not null,course_id uuid not null,enrollment_id uuid not null,
 scope text not null check(scope in ('section','course')),section_id uuid,completed_at timestamptz not null default now(),
 completion_snapshot jsonb not null check(jsonb_typeof(completion_snapshot)='object'),
 foreign key(tenant_id,course_id,enrollment_id) references public.elearning_enrollments(tenant_id,course_id,id) on delete cascade,
 foreign key(tenant_id,course_id,section_id) references public.elearning_sections(tenant_id,course_id,id) on delete cascade,
 check((scope='course' and section_id is null) or(scope='section' and section_id is not null))
);
create unique index elearning_completion_once on public.elearning_completion_events(tenant_id,enrollment_id,scope,coalesce(section_id,'00000000-0000-0000-0000-000000000000'::uuid));
-- Prospective requirements: retain the completion already implied by schema 126.
insert into public.elearning_completion_events(tenant_id,course_id,enrollment_id,scope,section_id,completed_at,completion_snapshot)
select e.tenant_id,e.course_id,e.id,'section',s.id,max(x.completed_at),jsonb_build_object('schema',126,'historical',true,'course_id',e.course_id,'section_id',s.id,'learner_id',e.learner_id,'lessons',jsonb_agg(jsonb_build_object('id',l.id,'completed_at',x.completed_at) order by l.position,l.id))
from public.elearning_enrollments e join public.elearning_sections s on(s.tenant_id,s.course_id)=(e.tenant_id,e.course_id) and s.status='published'
join public.elearning_lessons l on(l.tenant_id,l.course_id,l.section_id)=(s.tenant_id,s.course_id,s.id) and l.status='published'
left join public.elearning_lesson_completions x on(x.tenant_id,x.enrollment_id,x.lesson_id)=(e.tenant_id,e.id,l.id)
group by e.tenant_id,e.course_id,e.id,e.learner_id,s.id having count(*)=count(x.lesson_id);
insert into public.elearning_completion_events(tenant_id,course_id,enrollment_id,scope,completed_at,completion_snapshot)
select e.tenant_id,e.course_id,e.id,'course',max(x.completed_at),jsonb_build_object('schema',126,'historical',true,'course_id',e.course_id,'learner_id',e.learner_id,'course_name',c.name,'structure_revision',c.structure_revision,'lessons',jsonb_agg(jsonb_build_object('id',l.id,'completed_at',x.completed_at) order by s.position,l.position,l.id))
from public.elearning_enrollments e join public.elearning_courses c on(c.tenant_id,c.id)=(e.tenant_id,e.course_id)
join public.elearning_sections s on(s.tenant_id,s.course_id)=(c.tenant_id,c.id) and s.status='published'
join public.elearning_lessons l on(l.tenant_id,l.course_id,l.section_id)=(s.tenant_id,s.course_id,s.id) and l.status='published'
left join public.elearning_lesson_completions x on(x.tenant_id,x.enrollment_id,x.lesson_id)=(e.tenant_id,e.id,l.id)
group by e.tenant_id,e.course_id,e.id,e.learner_id,c.name,c.structure_revision having count(*)=count(x.lesson_id);

create function public.elearning_sync_lesson_placement() returns trigger language plpgsql security definer set search_path='' as $$
begin
 if new.type='assessment' then
 insert into public.elearning_assessment_placements(id,tenant_id,course_id,assessment_id,placement_type,section_id,lesson_id,block_id,position,required_for_completion,archived_at)
 select new.id,new.tenant_id,new.course_id,new.assessment_id,'lesson',l.section_id,new.lesson_id,new.id,new.position,new.required_for_completion,new.archived_at from public.elearning_lessons l where l.id=new.lesson_id
 on conflict(id) do update set assessment_id=excluded.assessment_id,position=excluded.position,required_for_completion=excluded.required_for_completion,archived_at=excluded.archived_at,updated_at=now();
 end if;return new;
end $$;
create trigger elearning_sync_lesson_placement after insert or update on public.elearning_content_blocks for each row execute function public.elearning_sync_lesson_placement();
create function public.elearning_sync_placement_section() returns trigger language plpgsql security definer set search_path='' as $$
begin update public.elearning_assessment_placements set section_id=new.section_id where lesson_id=new.id and placement_type='lesson';return new;end $$;
create trigger elearning_sync_placement_section after update of section_id on public.elearning_lessons for each row execute function public.elearning_sync_placement_section();
create or replace function public.elearning_assessment_placement_removed() returns trigger language plpgsql security definer set search_path='' as $$
begin
 if old.assessment_id is not null then
 if exists(select 1 from public.elearning_assessment_attempts where placement_id=old.id) then
 update public.elearning_assessment_placements set block_id=null,archived_at=now() where id=old.id;
 else delete from public.elearning_assessment_placements where id=old.id;end if;
 if not exists(select 1 from public.elearning_assessment_placements where assessment_id=old.assessment_id) then delete from public.elearning_assessments where id=old.assessment_id;
 elsif not exists(select 1 from public.elearning_assessment_placements where assessment_id=old.assessment_id and archived_at is null) then update public.elearning_assessments set status='archived',archived_at=now() where id=old.assessment_id;end if;
 end if;return old;
end $$;

-- Every engine entry point resolves this placement; NULL lesson means section/course.
create function public.elearning_resolve_placement(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_placement_id uuid) returns public.elearning_assessment_placements language plpgsql stable security definer set search_path='' as $$
declare p public.elearning_assessment_placements%rowtype;begin
 select * into p from public.elearning_assessment_placements where tenant_id=p_tenant_id and course_id=p_course_id and id=p_placement_id and lesson_id is not distinct from p_lesson_id;
 if not found then raise exception using errcode='P0002',message='assessment_not_found';end if;return p;
end $$;
create function public.elearning_placement_requirements(p_tenant_id integer,p_course_id uuid,p_enrollment_id uuid,p_section_id uuid default null) returns jsonb language sql stable security definer set search_path='' as $$
 select coalesce(jsonb_agg(jsonb_build_object('id',p.id,'assessment_id',a.id,'title',a.title,'placement_type',p.placement_type,'required_for_completion',p.required_for_completion,'passing_score',a.passing_score,'passing_attempt',(select jsonb_build_object('id',t.id,'score_percentage',t.score_percentage,'passing_score',t.private_snapshot->'assessment'->'passing_score','submitted_at',t.submitted_at) from public.elearning_assessment_attempts t where t.tenant_id=p_tenant_id and t.placement_id=p.id and t.enrollment_id=p_enrollment_id and t.status='submitted' and t.passed order by t.submitted_at,t.id limit 1),'passed',exists(select 1 from public.elearning_assessment_attempts t where t.tenant_id=p_tenant_id and t.course_id=p_course_id and t.enrollment_id=p_enrollment_id and t.placement_id=p.id and t.status='submitted' and t.passed)) order by p.position,p.id),'[]')
 from public.elearning_assessment_placements p join public.elearning_assessments a on(a.tenant_id,a.id)=(p.tenant_id,p.assessment_id)
 where p.tenant_id=p_tenant_id and p.course_id=p_course_id and p.archived_at is null and a.status='published' and p.placement_type=case when p_section_id is null then 'course' else 'section' end and p.section_id is not distinct from p_section_id;
$$;
create function public.elearning_completion_state(p_tenant_id integer,p_course_id uuid,p_enrollment_id uuid,p_section_id uuid default null) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare event public.elearning_completion_events%rowtype;requirements jsonb;lessons_done boolean;requirements_done boolean;sections_done boolean:=true;sec record;begin
 if not exists(select 1 from public.elearning_enrollments where tenant_id=p_tenant_id and course_id=p_course_id and id=p_enrollment_id) or p_section_id is not null and not exists(select 1 from public.elearning_sections where tenant_id=p_tenant_id and course_id=p_course_id and id=p_section_id) then raise exception using errcode='P0002',message='elearning_learning_not_found';end if;
 select * into event from public.elearning_completion_events where tenant_id=p_tenant_id and course_id=p_course_id and enrollment_id=p_enrollment_id and section_id is not distinct from p_section_id;
 requirements:=public.elearning_placement_requirements(p_tenant_id,p_course_id,p_enrollment_id,p_section_id);
 select not exists(select 1 from public.elearning_lessons l join public.elearning_sections s on(s.tenant_id,s.course_id,s.id)=(l.tenant_id,l.course_id,l.section_id)
 where l.tenant_id=p_tenant_id and l.course_id=p_course_id and l.status='published' and s.status='published' and(p_section_id is null or l.section_id=p_section_id)
 and not exists(select 1 from public.elearning_lesson_completions x where x.tenant_id=p_tenant_id and x.enrollment_id=p_enrollment_id and x.lesson_id=l.id)) into lessons_done;
 if p_section_id is null then
 lessons_done:=lessons_done and exists(select 1 from public.elearning_lessons l join public.elearning_sections s on s.id=l.section_id where l.tenant_id=p_tenant_id and l.course_id=p_course_id and l.status='published' and s.status='published');
 if exists(select 1 from public.elearning_assessment_placements p join public.elearning_assessments a on a.id=p.assessment_id where p.tenant_id=p_tenant_id and p.course_id=p_course_id and p.placement_type='section' and p.archived_at is null and p.required_for_completion and a.status='published') then
 for sec in select id from public.elearning_sections where tenant_id=p_tenant_id and course_id=p_course_id and status='published' loop
 if not (public.elearning_completion_state(p_tenant_id,p_course_id,p_enrollment_id,sec.id)->>'completed')::boolean then sections_done:=false;end if;end loop;end if;
 end if;
 requirements_done:=not exists(select 1 from jsonb_array_elements(requirements) r where (r->>'required_for_completion')::boolean and not(r->>'passed')::boolean);
 return jsonb_build_object('completed',event.id is not null or lessons_done and requirements_done and sections_done,'eligible',lessons_done and requirements_done and sections_done,'historical',event.id is not null,'completed_at',event.completed_at,'completion_id',event.id,'lessons_complete',lessons_done,'requirements',requirements,'requirements_satisfied',requirements_done and sections_done);
end $$;
create function public.elearning_finalize_completion(p_tenant_id integer,p_course_id uuid,p_enrollment_id uuid) returns void language plpgsql security definer set search_path='' as $$
declare sec record;state jsonb;c public.elearning_courses%rowtype;begin
 perform pg_advisory_xact_lock(125,p_tenant_id);select * into c from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id and status='published' for update;
 if not found or not exists(select 1 from public.elearning_enrollments where tenant_id=p_tenant_id and course_id=p_course_id and id=p_enrollment_id) then return;end if;
 for sec in select id from public.elearning_sections where tenant_id=p_tenant_id and course_id=p_course_id and status='published' order by position,id loop
 state:=public.elearning_completion_state(p_tenant_id,p_course_id,p_enrollment_id,sec.id);
 if(state->>'completed')::boolean or(state->>'eligible')::boolean then
 insert into public.elearning_completion_events(tenant_id,course_id,enrollment_id,scope,section_id,completion_snapshot)
 values(p_tenant_id,p_course_id,p_enrollment_id,'section',sec.id,jsonb_build_object('schema',127,'course_id',c.id,'course_name',c.name,'structure_revision',c.structure_revision,'enrollment_id',p_enrollment_id,'learner_id',(select learner_id from public.elearning_enrollments where id=p_enrollment_id),'section_id',sec.id,'requirements',state->'requirements','lessons',(select coalesce(jsonb_agg(jsonb_build_object('id',l.id,'completed_at',x.completed_at) order by l.position,l.id),'[]') from public.elearning_lessons l join public.elearning_lesson_completions x on x.lesson_id=l.id and x.enrollment_id=p_enrollment_id where l.section_id=sec.id and l.status='published'))) on conflict do nothing;end if;end loop;
 state:=public.elearning_completion_state(p_tenant_id,p_course_id,p_enrollment_id);
 if(state->>'completed')::boolean or(state->>'eligible')::boolean then
 insert into public.elearning_completion_events(tenant_id,course_id,enrollment_id,scope,completion_snapshot)
 values(p_tenant_id,p_course_id,p_enrollment_id,'course',jsonb_build_object('schema',127,'course_id',c.id,'course_name',c.name,'structure_revision',c.structure_revision,'enrollment_id',p_enrollment_id,'learner_id',(select learner_id from public.elearning_enrollments where id=p_enrollment_id),'requirements',state->'requirements','sections',(select jsonb_agg(jsonb_build_object('section_id',e.section_id,'completion_id',e.id,'completed_at',e.completed_at,'requirements',e.completion_snapshot->'requirements')) from public.elearning_completion_events e where e.tenant_id=p_tenant_id and e.enrollment_id=p_enrollment_id and e.scope='section'),'lessons',(select jsonb_agg(jsonb_build_object('id',l.id,'completed_at',x.completed_at)) from public.elearning_lessons l join public.elearning_sections s on s.id=l.section_id join public.elearning_lesson_completions x on x.lesson_id=l.id and x.enrollment_id=p_enrollment_id where l.course_id=c.id and l.status='published' and s.status='published'))) on conflict do nothing;end if;
end $$;


create function public.elearning_finalize_course_enrollments(p_tenant_id integer,p_course_id uuid) returns void language plpgsql security definer set search_path='' as $$
declare e record;begin
 for e in select id from public.elearning_enrollments where tenant_id=p_tenant_id and course_id=p_course_id loop
 perform public.elearning_finalize_completion(p_tenant_id,p_course_id,e.id);end loop;
end $$;

-- Keep the existing percentage engine; add authoritative completion to its result.
alter function public.get_elearning_progress_records(integer,uuid,boolean,boolean) rename to get_elearning_progress_records_schema126;
create function public.get_elearning_progress_records(p_tenant_id integer,p_course_id uuid,p_include_inactive boolean,p_include_details boolean) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare s jsonb;r jsonb;sec jsonb;state jsonb;rows jsonb:='[]';sections jsonb;completed integer:=0;active integer:=0;begin
 s:=public.get_elearning_progress_records_schema126(p_tenant_id,p_course_id,p_include_inactive,p_include_details);
 for r in select value from jsonb_array_elements(s->'enrollments') loop
 state:=public.elearning_completion_state(p_tenant_id,p_course_id,(r->>'id')::uuid);sections:='[]';
 for sec in select value from jsonb_array_elements(coalesce(r->'sections','[]')) loop
 sections:=sections||jsonb_build_array(sec||jsonb_build_object('completion',public.elearning_completion_state(p_tenant_id,p_course_id,(r->>'id')::uuid,(sec->>'id')::uuid)));end loop;
 r:=r||jsonb_build_object('completion',state,'completed_at',state->'completed_at','progress_status',case when(state->>'completed')::boolean then 'completed' when(r->>'completed_lessons')::integer>0 then 'active' else 'not_started' end,'sections',sections);
 if r->>'progress_status'='completed' then completed:=completed+1;elsif r->>'progress_status'='active' then active:=active+1;end if;
 rows:=rows||jsonb_build_array(r);end loop;
 return s||jsonb_build_object('enrollments',rows,'completed_count',completed,'active_count',active,'not_started_count',jsonb_array_length(rows)-completed-active);
end $$;
create or replace function public.get_elearning_assessment_author(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_block_id uuid) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare b public.elearning_assessment_placements%rowtype;begin
 b:=public.elearning_resolve_placement(p_tenant_id,p_course_id,p_lesson_id,p_block_id);

 return jsonb_build_object('block_id',b.id,'placement',to_jsonb(b),'assessment',public.elearning_assessment_summary(p_tenant_id,b.assessment_id)||jsonb_build_object('required_for_completion',b.required_for_completion),'questions',coalesce((select jsonb_agg(to_jsonb(q) order by q.archived_at is not null,q.position,q.id) from public.elearning_assessment_questions q where q.tenant_id=p_tenant_id and q.assessment_id=b.assessment_id),'[]'));
end $$;
create or replace function public.manage_elearning_assessment(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_block_id uuid,p_actor_id integer,p_expected_revision integer,p_action text,p_question_id uuid,p_payload jsonb) returns jsonb language plpgsql security definer set search_path='' as $$
declare b public.elearning_assessment_placements%rowtype;a public.elearning_assessments%rowtype;q public.elearning_assessment_questions%rowtype;pos integer;swap uuid;affected record;begin
 perform pg_advisory_xact_lock(125,p_tenant_id);
 perform 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id and status<>'archived' for update;
 if not found then raise exception using errcode='P0002',message='assessment_not_found';end if;
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant_id and user_id=p_actor_id and role in ('owner','admin') and status='active') then raise exception using errcode='42501',message='assessment_author_forbidden';end if;
 b:=public.elearning_resolve_placement(p_tenant_id,p_course_id,p_lesson_id,p_block_id);
 if b.archived_at is not null then raise exception using errcode='P0002',message='assessment_not_found';end if;
 if exists(select 1 from public.elearning_lessons l join public.elearning_sections s on (s.tenant_id,s.course_id,s.id)=(l.tenant_id,l.course_id,l.section_id) where l.tenant_id=p_tenant_id and l.id=p_lesson_id and (l.status='archived' or s.status='archived')) then raise exception using errcode='P0002',message='assessment_not_found';end if;
 select * into a from public.elearning_assessments where tenant_id=p_tenant_id and id=b.assessment_id for update;
 if a.revision is distinct from p_expected_revision then raise exception using errcode='P0001',message='assessment_conflict';end if;
 if p_action in ('settings','delete_assessment') then
  if p_question_id is not null then raise exception using errcode='22023',message='assessment_invalid_question';end if;
  if p_action='delete_assessment' then
   if p_payload->'confirmed' is distinct from 'true'::jsonb then raise exception using errcode='22023',message='assessment_confirmation_required';end if;
   if b.placement_type<>'lesson' then update public.elearning_assessment_placements set archived_at=now() where id=b.id;update public.elearning_courses set structure_revision=structure_revision+1 where id=p_course_id;perform public.elearning_finalize_course_enrollments(p_tenant_id,p_course_id);return jsonb_build_object('deleted',true);end if;
   perform public.manage_elearning_content(p_tenant_id,p_course_id,p_lesson_id,p_actor_id,(select content_revision from public.elearning_lessons where id=p_lesson_id),'delete',b.id,jsonb_build_object('confirmed',true));
   return jsonb_build_object('deleted',true,'content',public.get_elearning_content(p_tenant_id,p_course_id,p_lesson_id));
  end if;
  if p_payload->>'status'='published' then perform public.validate_elearning_assessment_publish(p_tenant_id,a.id);end if;
  update public.elearning_assessments set title=p_payload->>'title',instructions=p_payload->>'instructions',passing_score=(p_payload->>'passing_score')::numeric,max_attempts=(p_payload->>'max_attempts')::integer,status=p_payload->>'status',archived_at=case when p_payload->>'status'='archived' then now() else null end where id=a.id;
  update public.elearning_assessment_placements set required_for_completion=(p_payload->>'required_for_completion')::boolean,updated_at=now() where id=b.id;
  update public.elearning_content_blocks set title=p_payload->>'title',required_for_completion=(p_payload->>'required_for_completion')::boolean,content=jsonb_build_object('version',1,'assessment_id',a.id,'required_for_completion',p_payload->'required_for_completion') where id=b.id;
 else
  if p_action not in ('create_question','update_question','duplicate_question','reorder_question','archive_question','restore_question','delete_question') then raise exception using errcode='22023',message='assessment_invalid_action';end if;
  if p_action<>'create_question' then
   select * into q from public.elearning_assessment_questions where tenant_id=p_tenant_id and assessment_id=a.id and id=p_question_id for update;
   if not found then raise exception using errcode='P0002',message='assessment_question_not_found';end if;
   if q.archived_at is not null and p_action not in ('restore_question','delete_question') then raise exception using errcode='22023',message='assessment_question_archived';end if;
  elsif p_question_id is not null then raise exception using errcode='22023',message='assessment_invalid_question';end if;
  if p_action in ('create_question','update_question') then
   perform public.validate_elearning_assessment_question(p_tenant_id,p_payload);
   if p_action='create_question' then
    if (select count(*) from public.elearning_assessment_questions where assessment_id=a.id)>=200 then raise exception using errcode='22023',message='assessment_question_limit';end if;
    insert into public.elearning_assessment_questions(tenant_id,assessment_id,type,prompt,points,position,config) values(p_tenant_id,a.id,p_payload->>'type',p_payload->>'prompt',(p_payload->>'points')::numeric,(select coalesce(max(position),-1)+1 from public.elearning_assessment_questions where assessment_id=a.id),p_payload->'config');
   else update public.elearning_assessment_questions set type=p_payload->>'type',prompt=p_payload->>'prompt',points=(p_payload->>'points')::numeric,config=p_payload->'config' where id=q.id;end if;
  elsif p_action='duplicate_question' then
   if (select count(*) from public.elearning_assessment_questions where assessment_id=a.id)>=200 then raise exception using errcode='22023',message='assessment_question_limit';end if;
   update public.elearning_assessment_questions set position=position+1 where assessment_id=a.id and position>q.position;
   insert into public.elearning_assessment_questions(tenant_id,assessment_id,type,prompt,points,position,config) values(p_tenant_id,a.id,q.type,q.prompt,q.points,q.position+1,q.config);
  elsif p_action='reorder_question' then
   if p_payload->>'direction' not in ('up','down') or p_payload->>'direction' is null then raise exception using errcode='22023',message='assessment_invalid_direction';end if;
   if p_payload->>'direction'='up' then select id,position into swap,pos from public.elearning_assessment_questions where assessment_id=a.id and archived_at is null and position<q.position order by position desc limit 1;
   else select id,position into swap,pos from public.elearning_assessment_questions where assessment_id=a.id and archived_at is null and position>q.position order by position limit 1;end if;
   if swap is not null then update public.elearning_assessment_questions set position=case when id=q.id then pos else q.position end where id in(q.id,swap);end if;
  elsif p_action in ('archive_question','delete_question') then
   if p_payload->'confirmed' is distinct from 'true'::jsonb then raise exception using errcode='22023',message='assessment_confirmation_required';end if;
   if p_action='archive_question' then update public.elearning_assessment_questions set archived_at=now() where id=q.id;else delete from public.elearning_assessment_questions where id=q.id;end if;
  else update public.elearning_assessment_questions set archived_at=null where id=q.id;end if;
  with ranked as(select id,(row_number() over(order by archived_at is not null,position,id)-1)::integer pos from public.elearning_assessment_questions where assessment_id=a.id)
  update public.elearning_assessment_questions x set position=r.pos from ranked r where x.id=r.id and x.position<>r.pos;
  update public.elearning_assessments set status='draft',archived_at=null where id=a.id;
 end if;
 update public.elearning_assessments set revision=revision+1 where id=a.id;update public.elearning_lessons set content_revision=content_revision+1 where id=p_lesson_id;update public.elearning_courses set structure_revision=structure_revision+1 where id=p_course_id;
 if p_action='settings' then for affected in select distinct course_id from public.elearning_assessment_placements where tenant_id=p_tenant_id and assessment_id=a.id loop perform public.elearning_finalize_course_enrollments(p_tenant_id,affected.course_id);end loop;end if;
 return public.get_elearning_assessment_author(p_tenant_id,p_course_id,p_lesson_id,b.id);
end $$;
create or replace function public.elearning_assessment_runtime(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_block_id uuid,p_user_id integer) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare s jsonb;b public.elearning_assessment_placements%rowtype;a public.elearning_assessments%rowtype;e uuid;t public.elearning_assessment_attempts%rowtype;questions jsonb;submitted integer;best numeric;passed boolean;begin
 -- Reuse publication, section/lesson relationships, effective grants and sequential locks.
 s:=public.get_elearning_learner_course(p_tenant_id,p_user_id,p_course_id,p_lesson_id);e:=(s->'progress'->>'id')::uuid;
 b:=public.elearning_resolve_placement(p_tenant_id,p_course_id,p_lesson_id,p_block_id);
 if b.archived_at is not null then raise exception using errcode='P0002',message='assessment_not_found';end if;
 perform public.elearning_assert_placement_eligible(p_tenant_id,p_user_id,p_course_id,b.id);
 if not found then raise exception using errcode='P0002',message='assessment_not_found';end if;
 select * into a from public.elearning_assessments where tenant_id=p_tenant_id and id=b.assessment_id and status='published';
 if not found then raise exception using errcode='P0002',message='assessment_not_found';end if;
 select count(*) filter(where status='submitted'),max(score_percentage) filter(where status='submitted'),coalesce(bool_or(t2.passed) filter(where status='submitted'),false) into submitted,best,passed from public.elearning_assessment_attempts t2 where tenant_id=p_tenant_id and placement_id=b.id and enrollment_id=e and user_id=p_user_id;
 select * into t from public.elearning_assessment_attempts where tenant_id=p_tenant_id and placement_id=b.id and enrollment_id=e and user_id=p_user_id order by status='in_progress' desc,attempt_number desc limit 1;
 if t.id is not null then select coalesce(jsonb_agg(public.elearning_safe_question(p_tenant_id,v) order by ord),'[]') into questions from jsonb_array_elements(t.private_snapshot->'questions') with ordinality x(v,ord);end if;
 return jsonb_build_object('assessment',public.elearning_assessment_summary(p_tenant_id,a.id)||jsonb_build_object('required_for_completion',b.required_for_completion),
 'summary',jsonb_build_object('attempts',submitted,'best_score',best,'passed',passed,'remaining_attempts',case when a.max_attempts is null then null else greatest(a.max_attempts-submitted,0) end),
 'attempt',case when t.id is null then null else jsonb_build_object('id',t.id,'attempt_number',t.attempt_number,'status',t.status,'started_at',t.started_at,'submitted_at',t.submitted_at,'earned_points',t.earned_points,'total_points',t.total_points,'score_percentage',t.score_percentage,'passed',t.passed,'passing_score',t.private_snapshot->'assessment'->'passing_score','max_attempts',t.private_snapshot->'assessment'->'max_attempts','title',t.private_snapshot->'assessment'->'title','instructions',t.private_snapshot->'assessment'->'instructions','questions',questions) end);
end $$;
create or replace function public.start_elearning_assessment_attempt(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_block_id uuid,p_user_id integer) returns jsonb language plpgsql security definer set search_path='' as $$
declare s jsonb;b public.elearning_assessment_placements%rowtype;a public.elearning_assessments%rowtype;e uuid;tid uuid;used integer;qs jsonb;begin
 perform pg_advisory_xact_lock(125,p_tenant_id);perform 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id for update;
 s:=public.elearning_assessment_runtime(p_tenant_id,p_course_id,p_lesson_id,p_block_id,p_user_id);
 if s->'attempt'->>'status'='in_progress' then return s;end if;
 b:=public.elearning_resolve_placement(p_tenant_id,p_course_id,p_lesson_id,p_block_id);
 select * into a from public.elearning_assessments where tenant_id=p_tenant_id and id=b.assessment_id;
 e:=(public.get_elearning_learner_course(p_tenant_id,p_user_id,p_course_id,p_lesson_id)->'progress'->>'id')::uuid;
 select count(*) into used from public.elearning_assessment_attempts where tenant_id=p_tenant_id and placement_id=b.id and enrollment_id=e and status='submitted';
 if a.max_attempts is not null and used>=a.max_attempts then raise exception using errcode='42501',message='assessment_attempt_limit';end if;
 perform public.validate_elearning_assessment_publish(p_tenant_id,a.id);
 select jsonb_agg(jsonb_build_object('id',q.id,'type',q.type,'prompt',q.prompt,'points',q.points,'config',q.config,'position',q.position) order by q.position,q.id) into qs from public.elearning_assessment_questions q where tenant_id=p_tenant_id and assessment_id=a.id and archived_at is null;
 insert into public.elearning_assessment_attempts(tenant_id,assessment_id,user_id,course_id,lesson_id,block_id,placement_id,enrollment_id,attempt_number,private_snapshot)
 values(p_tenant_id,a.id,p_user_id,p_course_id,p_lesson_id,b.block_id,b.id,e,used+1,jsonb_build_object('assessment',public.elearning_assessment_summary(p_tenant_id,a.id),'questions',qs)) returning id into tid;
 insert into public.elearning_assessment_media_refs(tenant_id,assessment_id,attempt_id,media_id)
 select p_tenant_id,a.id,tid,(prompt->>'media_id')::uuid from jsonb_array_elements(qs) question cross join lateral jsonb_array_elements(question->'config'->'prompts') prompt where question->>'type'='listen_match';
 return public.elearning_assessment_runtime(p_tenant_id,p_course_id,p_lesson_id,p_block_id,p_user_id);
end $$;
create or replace function public.submit_elearning_assessment_attempt(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_block_id uuid,p_user_id integer,p_attempt_id uuid,p_answers jsonb) returns jsonb language plpgsql security definer set search_path='' as $$
declare s jsonb;t public.elearning_assessment_attempts%rowtype;q jsonb;r jsonb;cfg jsonb;earned numeric:=0;total numeric:=0;credit numeric;correct integer;n integer;score numeric;typ text;key text;ids text[];targets text[];begin
 perform pg_advisory_xact_lock(125,p_tenant_id);perform 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id for update;
 s:=public.elearning_assessment_runtime(p_tenant_id,p_course_id,p_lesson_id,p_block_id,p_user_id);
 select * into t from public.elearning_assessment_attempts where tenant_id=p_tenant_id and course_id=p_course_id and lesson_id is not distinct from p_lesson_id and placement_id=p_block_id and id=p_attempt_id and user_id=p_user_id and assessment_id=(s->'assessment'->>'id')::uuid for update;
 if not found then raise exception using errcode='P0002',message='assessment_attempt_not_found';end if;
 -- A repeated submission returns the original result even if the caller changes answers.
 if t.status='submitted' then
  if s->'attempt'->>'id'<>t.id::text then
   return jsonb_set(s,'{attempt}',jsonb_build_object('id',t.id,'attempt_number',t.attempt_number,'status',t.status,'earned_points',t.earned_points,'total_points',t.total_points,'score_percentage',t.score_percentage,'passed',t.passed,'passing_score',t.private_snapshot->'assessment'->'passing_score','max_attempts',t.private_snapshot->'assessment'->'max_attempts','submitted_at',t.submitted_at));
  end if;return s;
 end if;
 if jsonb_typeof(p_answers) is distinct from 'object' or (select count(*) from jsonb_object_keys(p_answers))<>jsonb_array_length(t.private_snapshot->'questions') then raise exception using errcode='22023',message='assessment_answers_required';end if;
 for q in select value from jsonb_array_elements(t.private_snapshot->'questions') loop
  typ:=q->>'type';cfg:=q->'config';r:=p_answers->(q->>'id');credit:=0;
  if r is null or jsonb_typeof(r) is distinct from 'object' then raise exception using errcode='22023',message='assessment_invalid_response';end if;
  if typ='multiple_choice' then
   if r-'option_id'<>'{}'::jsonb or jsonb_typeof(r->'option_id') is distinct from 'string' or not exists(select 1 from jsonb_array_elements(cfg->'options') v where v->>'id'=r->>'option_id') then raise exception using errcode='22023',message='assessment_invalid_response';end if;
   if r->>'option_id'=cfg->>'correct_option_id' then credit:=(q->>'points')::numeric;end if;
  elsif typ='true_false' then
   if r-'value'<>'{}'::jsonb or jsonb_typeof(r->'value') is distinct from 'boolean' then raise exception using errcode='22023',message='assessment_invalid_response';end if;
   if r->'value'=cfg->'correct_answer' then credit:=(q->>'points')::numeric;end if;
  else
   if r-'matches'<>'{}'::jsonb or jsonb_typeof(r->'matches') is distinct from 'object' or (select count(*) from jsonb_object_keys(r->'matches'))<>jsonb_array_length(cfg->'prompts') then raise exception using errcode='22023',message='assessment_invalid_response';end if;
   correct:=0;n:=jsonb_array_length(cfg->'prompts');
   for key in select v->>'id' from jsonb_array_elements(cfg->'prompts') v loop
    if jsonb_typeof(r->'matches'->key) is distinct from 'string' or not exists(select 1 from jsonb_array_elements(cfg->'targets') v where v->>'id'=r->'matches'->>key) then raise exception using errcode='22023',message='assessment_invalid_response';end if;
    if r->'matches'->key=cfg->'correct_pairs'->key then correct:=correct+1;end if;
   end loop;
   -- One target per prompt; incorrect permutations earn deterministic partial points.
   if (select count(distinct value) from jsonb_each_text(r->'matches'))<>n then raise exception using errcode='22023',message='assessment_invalid_response';end if;
   credit:=(q->>'points')::numeric*correct/n;
  end if;
  total:=total+(q->>'points')::numeric;earned:=earned+credit;
  insert into public.elearning_assessment_answers(tenant_id,attempt_id,question_id,response,earned_points) values(p_tenant_id,t.id,(q->>'id')::uuid,r,credit);
 end loop;
 score:=100*earned/total;
 update public.elearning_assessment_attempts set status='submitted',submitted_at=now(),earned_points=earned,total_points=total,score_percentage=round(score,2),passed=score>=(t.private_snapshot->'assessment'->>'passing_score')::numeric where id=t.id;
 perform public.elearning_finalize_completion(p_tenant_id,p_course_id,t.enrollment_id);
 return public.elearning_assessment_runtime(p_tenant_id,p_course_id,p_lesson_id,p_block_id,p_user_id);
end $$;

create function public.elearning_assert_placement_eligible(p_tenant_id integer,p_user_id integer,p_course_id uuid,p_placement_id uuid) returns void language plpgsql stable security definer set search_path='' as $$
declare p public.elearning_assessment_placements%rowtype;s jsonb;sec jsonb;state jsonb;begin
 s:=public.get_elearning_learner_course(p_tenant_id,p_user_id,p_course_id,null);
 select * into p from public.elearning_assessment_placements where tenant_id=p_tenant_id and course_id=p_course_id and id=p_placement_id and archived_at is null;
 if not found or not exists(select 1 from public.elearning_assessments where tenant_id=p_tenant_id and id=p.assessment_id and status='published') then raise exception using errcode='P0002',message='assessment_not_found';end if;
 if p.placement_type='lesson' then perform public.get_elearning_learner_course(p_tenant_id,p_user_id,p_course_id,p.lesson_id);return;end if;
 if p.placement_type='section' then
 select value into sec from jsonb_array_elements(s->'sections') where value->>'id'=p.section_id::text;
 if sec is null then raise exception using errcode='P0002',message='assessment_not_found';end if;
 if(sec->>'locked')::boolean or p.required_for_completion and not(sec->'completion'->>'lessons_complete')::boolean then raise exception using errcode='42501',message='assessment_prerequisites';end if;
 elsif p.required_for_completion then
 state:=s->'progress'->'completion';
 if not(state->>'lessons_complete')::boolean or exists(select 1 from jsonb_array_elements(s->'sections') x where not(x->'completion'->>'completed')::boolean) then raise exception using errcode='42501',message='assessment_prerequisites';end if;
 end if;
end $$;

create function public.elearning_placement_outline(p_tenant_id integer,p_course_id uuid,p_enrollment_id uuid,p_section_id uuid,p_locked boolean,p_lessons_complete boolean) returns jsonb language sql stable security definer set search_path='' as $$
 select coalesce(jsonb_agg(public.elearning_assessment_summary(p_tenant_id,a.id)||jsonb_build_object('placement_id',p.id,'placement_type',p.placement_type,'required_for_completion',p.required_for_completion,'locked',p_locked or(p.required_for_completion and not p_lessons_complete),'attempts',(select count(*) from public.elearning_assessment_attempts t where t.placement_id=p.id and t.enrollment_id=p_enrollment_id and t.status='submitted'),'passed',exists(select 1 from public.elearning_assessment_attempts t where t.placement_id=p.id and t.enrollment_id=p_enrollment_id and t.status='submitted' and t.passed),'best_score',(select max(score_percentage) from public.elearning_assessment_attempts t where t.placement_id=p.id and t.enrollment_id=p_enrollment_id and t.status='submitted')) order by p.position,p.id),'[]')
 from public.elearning_assessment_placements p join public.elearning_assessments a on(a.tenant_id,a.id)=(p.tenant_id,p.assessment_id)
 where p.tenant_id=p_tenant_id and p.course_id=p_course_id and p.archived_at is null and a.status='published' and p.placement_type=case when p_section_id is null then 'course' else 'section' end and p.section_id is not distinct from p_section_id;
$$;
alter function public.get_elearning_learner_course(integer,integer,uuid,uuid) rename to get_elearning_learner_course_schema126;
create function public.get_elearning_learner_course(p_tenant_id integer,p_user_id integer,p_course_id uuid,p_lesson_id uuid default null) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare s jsonb;sec jsonb;lesson jsonb;sections jsonb:='[]';lessons jsonb;selected jsonb;enrollment uuid;sequential boolean;previous_incomplete boolean:=false;pending uuid;continue_id uuid;begin
 s:=public.get_elearning_learner_course_schema126(p_tenant_id,p_user_id,p_course_id,p_lesson_id);enrollment:=(s->'progress'->>'id')::uuid;
 select coalesce((settings->>'sequential_progression')::boolean,false) into sequential from public.elearning_settings where tenant_id=p_tenant_id;
 sequential:=coalesce(sequential,false);
 for sec in select value from jsonb_array_elements(s->'sections') loop
 sec:=sec||jsonb_build_object('locked',sequential and previous_incomplete,'assessments',public.elearning_placement_outline(p_tenant_id,p_course_id,enrollment,(sec->>'id')::uuid,sequential and previous_incomplete,(sec->'completion'->>'lessons_complete')::boolean));
 lessons:='[]';
 for lesson in select value from jsonb_array_elements(sec->'lessons') loop
 lesson:=lesson||jsonb_build_object('locked',(lesson->>'locked')::boolean or(sequential and previous_incomplete));
 if lesson->>'id'=p_lesson_id::text then selected:=s->'lesson'||jsonb_build_object('locked',lesson->'locked');end if;
 if continue_id is null and not(lesson->>'completed')::boolean and not(lesson->>'locked')::boolean then continue_id:=(lesson->>'id')::uuid;end if;
 lessons:=lessons||jsonb_build_array(lesson);end loop;
 if pending is null then select (v->>'placement_id')::uuid into pending from jsonb_array_elements(sec->'assessments') v where(v->>'required_for_completion')::boolean and not(v->>'passed')::boolean and not(v->>'locked')::boolean limit 1;end if;
 if not(sec->'completion'->>'completed')::boolean then previous_incomplete:=true;end if;
 sections:=sections||jsonb_build_array(sec||jsonb_build_object('lessons',lessons));end loop;
 if p_lesson_id is not null and(selected->>'locked')::boolean then raise exception using errcode='42501',message='elearning_lesson_locked';end if;
 s:=s||jsonb_build_object('sections',sections,'lesson',selected,'continue_lesson_id',continue_id,'assessments',public.elearning_placement_outline(p_tenant_id,p_course_id,enrollment,null,false,(s->'progress'->'completion'->>'lessons_complete')::boolean and not previous_incomplete));
 if pending is null then select (v->>'placement_id')::uuid into pending from jsonb_array_elements(s->'assessments') v where(v->>'required_for_completion')::boolean and not(v->>'passed')::boolean and not(v->>'locked')::boolean limit 1;end if;
 return s||jsonb_build_object('continue_assessment_id',pending);
end $$;

alter function public.complete_elearning_learner_lesson(integer,integer,uuid,uuid) rename to complete_elearning_learner_lesson_schema126;
create function public.complete_elearning_learner_lesson(p_tenant_id integer,p_user_id integer,p_course_id uuid,p_lesson_id uuid) returns jsonb language plpgsql security definer set search_path='' as $$
declare s jsonb;begin
 s:=public.complete_elearning_learner_lesson_schema126(p_tenant_id,p_user_id,p_course_id,p_lesson_id);
 perform public.elearning_finalize_completion(p_tenant_id,p_course_id,(s->'progress'->>'id')::uuid);
 return public.get_elearning_learner_course(p_tenant_id,p_user_id,p_course_id,p_lesson_id);
end $$;
alter function public.manage_elearning_participation(integer,uuid,integer,text,jsonb) rename to manage_elearning_participation_schema126;
create function public.manage_elearning_participation(p_tenant_id integer,p_course_id uuid,p_user_id integer,p_action text,p_payload jsonb) returns jsonb language plpgsql security definer set search_path='' as $$
declare s jsonb;begin
 s:=public.manage_elearning_participation_schema126(p_tenant_id,p_course_id,p_user_id,p_action,p_payload);
 if p_action='complete_lesson' then perform public.elearning_finalize_completion(p_tenant_id,p_course_id,(p_payload->>'enrollment_id')::uuid);return public.get_elearning_enrollment_report(p_tenant_id,p_course_id);end if;return s;
end $$;

create or replace function public.elearning_assessment_results(p_tenant_id integer,p_enrollment_id uuid) returns jsonb language sql stable security definer set search_path='' as $$
 select coalesce(jsonb_agg(to_jsonb(v) order by v.placement_type,v.title,v.placement_id),'[]') from(
 select a.id assessment_id,p.id placement_id,p.placement_type,p.section_id,a.title,count(t.id) filter(where t.status='submitted') attempts,max(t.score_percentage) filter(where t.status='submitted') best_score,coalesce(bool_or(t.passed) filter(where t.status='submitted'),false) passed,max(t.submitted_at) last_attempt
 from public.elearning_assessment_placements p join public.elearning_assessments a on a.id=p.assessment_id join public.elearning_assessment_attempts t on t.placement_id=p.id
 where t.tenant_id=p_tenant_id and t.enrollment_id=p_enrollment_id group by a.id,p.id,p.placement_type,p.section_id,a.title) v;
$$;
-- Independent lesson requirements continue to use lesson placements and placement-scoped results.
create or replace function public.elearning_required_assessments(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_enrollment_id uuid) returns jsonb language sql stable security definer set search_path='' as $$
 select coalesce(jsonb_agg(jsonb_build_object('id',a.id,'title',a.title,'passed',exists(select 1 from public.elearning_assessment_attempts t where t.tenant_id=p_tenant_id and t.placement_id=p.id and t.enrollment_id=p_enrollment_id and t.status='submitted' and t.passed)) order by p.position,p.id),'[]')
 from public.elearning_assessment_placements p join public.elearning_assessments a on a.id=p.assessment_id where p.tenant_id=p_tenant_id and p.course_id=p_course_id and p.lesson_id=p_lesson_id and p.placement_type='lesson' and p.archived_at is null and p.required_for_completion and a.status='published';
$$;

create function public.get_elearning_placements(p_tenant_id integer,p_course_id uuid,p_section_id uuid default null) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare c public.elearning_courses%rowtype;begin
 select * into c from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id;
 if not found or p_section_id is not null and not exists(select 1 from public.elearning_sections where tenant_id=p_tenant_id and course_id=p_course_id and id=p_section_id) then raise exception using errcode='P0002',message='assessment_not_found';end if;
 return jsonb_build_object('revision',c.structure_revision,'placements',coalesce((select jsonb_agg(to_jsonb(p)||jsonb_build_object('assessment',public.elearning_assessment_summary(p_tenant_id,p.assessment_id),'attempts',(select count(*) from public.elearning_assessment_attempts t where t.placement_id=p.id and t.status='submitted')) order by p.archived_at is not null,p.position,p.id) from public.elearning_assessment_placements p where p.tenant_id=p_tenant_id and p.course_id=p_course_id and p.placement_type=case when p_section_id is null then 'course' else 'section' end and p.section_id is not distinct from p_section_id),'[]'),
 'available_assessments',coalesce((select jsonb_agg(public.elearning_assessment_summary(p_tenant_id,id) order by title,id) from public.elearning_assessments a where a.tenant_id=p_tenant_id and a.status<>'archived'),'[]'));
end $$;

create function public.create_elearning_placed_assessment(p_tenant_id integer,p_course_id uuid,p_section_id uuid,p_actor_id integer,p_expected_revision integer,p_details jsonb,p_questions jsonb,p_assessment_id uuid default null) returns jsonb language plpgsql security definer set search_path='' as $$
declare aid uuid:=p_assessment_id;pid uuid;v jsonb;pos integer:=0;begin
 perform pg_advisory_xact_lock(125,p_tenant_id);perform 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id and status<>'archived' and structure_revision=p_expected_revision for update;
 if not found then raise exception using errcode='P0001',message='assessment_content_conflict';end if;
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant_id and user_id=p_actor_id and status='active' and role in('owner','admin')) then raise exception using errcode='42501',message='assessment_author_forbidden';end if;
 if p_section_id is not null and not exists(select 1 from public.elearning_sections where tenant_id=p_tenant_id and course_id=p_course_id and id=p_section_id and status<>'archived') then raise exception using errcode='P0002',message='assessment_not_found';end if;
 if aid is null then
 if jsonb_typeof(p_questions) is distinct from 'array' or jsonb_array_length(p_questions)>200 or p_details->>'status'='archived' then raise exception using errcode='22023',message='assessment_invalid_questions';end if;
 insert into public.elearning_assessments(tenant_id,title,instructions,passing_score,max_attempts,created_by) values(p_tenant_id,p_details->>'title',p_details->>'instructions',(p_details->>'passing_score')::numeric,(p_details->>'max_attempts')::integer,p_actor_id) returning id into aid;
 for v in select value from jsonb_array_elements(p_questions) loop
 perform public.validate_elearning_assessment_question(p_tenant_id,v);
 insert into public.elearning_assessment_questions(tenant_id,assessment_id,type,prompt,points,position,config) values(p_tenant_id,aid,v->>'type',v->>'prompt',(v->>'points')::numeric,pos,v->'config');pos:=pos+1;end loop;
 if p_details->>'status'='published' then perform public.validate_elearning_assessment_publish(p_tenant_id,aid);update public.elearning_assessments set status='published' where id=aid;end if;
 elsif not exists(select 1 from public.elearning_assessments where tenant_id=p_tenant_id and id=aid and status<>'archived') then raise exception using errcode='P0002',message='assessment_not_found';end if;
 insert into public.elearning_assessment_placements(tenant_id,course_id,section_id,assessment_id,placement_type,required_for_completion,position)
 values(p_tenant_id,p_course_id,p_section_id,aid,case when p_section_id is null then 'course' else 'section' end,coalesce((p_details->>'required_for_completion')::boolean,false),(select coalesce(max(position),-1)+1 from public.elearning_assessment_placements where tenant_id=p_tenant_id and course_id=p_course_id and section_id is not distinct from p_section_id and placement_type<>'lesson')) returning id into pid;
 update public.elearning_courses set structure_revision=structure_revision+1 where id=p_course_id;
 return public.get_elearning_assessment_author(p_tenant_id,p_course_id,null,pid);
end $$;
create function public.manage_elearning_placement(p_tenant_id integer,p_course_id uuid,p_placement_id uuid,p_actor_id integer,p_expected_revision integer,p_action text,p_confirmed boolean default false) returns jsonb language plpgsql security definer set search_path='' as $$
declare p public.elearning_assessment_placements%rowtype;aid uuid;begin
 perform pg_advisory_xact_lock(125,p_tenant_id);perform 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id and status<>'archived' and structure_revision=p_expected_revision for update;
 if not found then raise exception using errcode='P0001',message='assessment_content_conflict';end if;
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant_id and user_id=p_actor_id and role in('owner','admin') and status='active') then raise exception using errcode='42501',message='assessment_author_forbidden';end if;
 p:=public.elearning_resolve_placement(p_tenant_id,p_course_id,null,p_placement_id);
 if p_action='duplicate' then aid:=public.clone_elearning_assessment(p_tenant_id,p.assessment_id,p_actor_id);insert into public.elearning_assessment_placements(tenant_id,course_id,section_id,assessment_id,placement_type,position,required_for_completion) values(p.tenant_id,p.course_id,p.section_id,aid,p.placement_type,(select coalesce(max(position),-1)+1 from public.elearning_assessment_placements where course_id=p.course_id and section_id is not distinct from p.section_id),p.required_for_completion);
 elsif p_action='remove' and p_confirmed then update public.elearning_assessment_placements set archived_at=now(),updated_at=now() where id=p.id;
 elsif p_action='restore' then update public.elearning_assessment_placements set archived_at=null,updated_at=now() where id=p.id;
 else raise exception using errcode='22023',message='assessment_confirmation_required';end if;
 update public.elearning_courses set structure_revision=structure_revision+1 where id=p_course_id;
 perform public.elearning_finalize_course_enrollments(p_tenant_id,p_course_id);
 return public.get_elearning_placements(p_tenant_id,p_course_id,p.section_id);
end $$;

alter function public.elearning_learner_media_access(integer,integer,text) rename to elearning_learner_media_access_schema126;
create function public.elearning_learner_media_access(p_tenant_id integer,p_user_id integer,p_storage_key text) returns boolean language plpgsql stable security definer set search_path='' as $$
declare baseline boolean;ref record;begin
 baseline:=public.elearning_learner_media_access_schema126(p_tenant_id,p_user_id,p_storage_key);if baseline is true then return true;end if;
 for ref in select distinct p.id,p.course_id from public.elearning_assessment_placements p join public.elearning_assessment_media_refs m on m.assessment_id=p.assessment_id join public.builder_assets a on a.id=m.media_id
 where p.tenant_id=p_tenant_id and p.placement_type<>'lesson' and p.archived_at is null and a.storage_key=p_storage_key and a.tenant_id=p_tenant_id and a.status in('active','unreferenced') and(m.question_id is not null and exists(select 1 from public.elearning_assessment_questions q where q.id=m.question_id and q.archived_at is null) or m.attempt_id is not null and exists(select 1 from public.elearning_assessment_attempts t where t.id=m.attempt_id and t.user_id=p_user_id and t.placement_id=p.id)) loop
 begin perform public.elearning_assert_placement_eligible(p_tenant_id,p_user_id,ref.course_id,ref.id);return true;exception when no_data_found or insufficient_privilege then null;end;end loop;
 if exists(select 1 from public.builder_assets a join public.elearning_assessment_media_refs m on m.media_id=a.id where a.tenant_id=p_tenant_id and a.storage_key=p_storage_key) then return false;end if;return baseline;
end $$;

-- Course purge includes all placements and historical evidence, retaining managed media.
alter function public.delete_elearning_course(integer,uuid,integer,integer,integer,text,boolean) rename to delete_elearning_course_schema126;
create function public.delete_elearning_course(p_tenant_id integer,p_course_id uuid,p_user_id integer,p_expected_revision integer,p_expected_structure_revision integer,p_confirmation_name text,p_confirmed boolean) returns jsonb language plpgsql security definer set search_path='' as $$
declare ids uuid[];s jsonb;begin
 perform pg_advisory_xact_lock(125,p_tenant_id);select array_agg(assessment_id) into ids from public.elearning_assessment_placements where tenant_id=p_tenant_id and course_id=p_course_id;
 s:=public.delete_elearning_course_schema126(p_tenant_id,p_course_id,p_user_id,p_expected_revision,p_expected_structure_revision,p_confirmation_name,p_confirmed);
 delete from public.elearning_assessments a where tenant_id=p_tenant_id and id=any(ids) and not exists(select 1 from public.elearning_assessment_placements p where p.assessment_id=a.id);
 return s;
end $$;

create or replace function public.delete_elearning_course_schema126(p_tenant_id integer,p_course_id uuid,p_user_id integer,p_expected_revision integer,p_expected_structure_revision integer,p_confirmation_name text,p_confirmed boolean) returns jsonb language plpgsql security definer set search_path='' as $$
declare ids uuid[];s jsonb;begin
 perform pg_advisory_xact_lock(125,p_tenant_id);
 select array_agg(assessment_id) into ids from public.elearning_content_blocks where tenant_id=p_tenant_id and course_id=p_course_id and assessment_id is not null;
 s:=public.delete_elearning_course_schema125(p_tenant_id,p_course_id,p_user_id,p_expected_revision,p_expected_structure_revision,p_confirmation_name,p_confirmed);
 delete from public.elearning_assessments a where tenant_id=p_tenant_id and id=any(ids) and not exists(select 1 from public.elearning_assessment_placements b where b.tenant_id=a.tenant_id and b.assessment_id=a.id);
 return s;
end $$;

alter table public.elearning_assessment_placements enable row level security;
alter table public.elearning_completion_events enable row level security;
revoke all on public.elearning_assessment_placements,public.elearning_completion_events from public,anon,authenticated,service_role;
grant select on public.elearning_assessment_placements to service_role;
-- Completion evidence is immutable; only finalized RPCs insert it.
create function public.elearning_immutable_completion() returns trigger language plpgsql set search_path='' as $$ begin raise exception using errcode='42501',message='elearning_completion_immutable';end $$;
create trigger elearning_completion_immutable before update on public.elearning_completion_events for each row execute function public.elearning_immutable_completion();

do $$ declare f record;begin
 for f in select p.oid::regprocedure signature from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and(p.proname in('elearning_sync_lesson_placement','elearning_sync_placement_section','elearning_resolve_placement','elearning_placement_requirements','elearning_completion_state','elearning_finalize_completion','elearning_finalize_course_enrollments','elearning_assert_placement_eligible','elearning_placement_outline','get_elearning_progress_records_schema126','get_elearning_learner_course_schema126','complete_elearning_learner_lesson_schema126','manage_elearning_participation_schema126','elearning_learner_media_access_schema126','delete_elearning_course_schema126','elearning_immutable_completion','get_elearning_placements','create_elearning_placed_assessment','manage_elearning_placement','get_elearning_progress_records','get_elearning_learner_course','complete_elearning_learner_lesson','manage_elearning_participation','elearning_learner_media_access','delete_elearning_course')) loop
 execute 'revoke all on function '||f.signature||' from public,anon,authenticated,service_role';end loop;
 grant execute on function public.get_elearning_placements(integer,uuid,uuid),public.create_elearning_placed_assessment(integer,uuid,uuid,integer,integer,jsonb,jsonb,uuid),public.manage_elearning_placement(integer,uuid,uuid,integer,integer,text,boolean) to service_role;
 grant execute on function public.get_elearning_progress_records(integer,uuid,boolean),public.get_elearning_learner_course(integer,integer,uuid,uuid),public.complete_elearning_learner_lesson(integer,integer,uuid,uuid),public.manage_elearning_participation(integer,uuid,integer,text,jsonb),public.elearning_learner_media_access(integer,integer,text),public.delete_elearning_course(integer,uuid,integer,integer,integer,text,boolean) to service_role;
end $$;
notify pgrst,'reload schema';
commit;
