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

-- Generic engine; the ordered lesson block is a placement, not the assessment itself.
create table public.elearning_assessments (
 id uuid primary key default gen_random_uuid(), tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
 title text not null check(char_length(btrim(title)) between 1 and 120),instructions text not null default '' check(char_length(instructions)<=10000),
 status text not null default 'draft' check(status in ('draft','published','archived')),
 passing_score numeric not null default 70 check(passing_score between 0 and 100),max_attempts integer check(max_attempts between 1 and 10000),
 revision integer not null default 1 check(revision>0),created_by integer references public.users(id) on delete set null,
 created_at timestamptz not null default now(),updated_at timestamptz not null default now(),archived_at timestamptz,
 unique(tenant_id,id)
);
create table public.elearning_assessment_questions (
 id uuid primary key default gen_random_uuid(),tenant_id integer not null,assessment_id uuid not null,
 type text not null check(type ~ '^[a-z][a-z0-9_]{0,49}$'),prompt text not null check(char_length(btrim(prompt)) between 1 and 10000),
 points numeric not null check(points>0 and points<=10000),position integer not null check(position>=0),config jsonb not null check(jsonb_typeof(config)='object'),
 created_at timestamptz not null default now(),updated_at timestamptz not null default now(),archived_at timestamptz,
 foreign key(tenant_id,assessment_id) references public.elearning_assessments(tenant_id,id) on delete cascade,
 unique(tenant_id,assessment_id,id),unique(tenant_id,assessment_id,position) deferrable initially deferred
);
alter table public.elearning_content_blocks add column assessment_id uuid;
alter table public.elearning_content_blocks add column required_for_completion boolean not null default false;
alter table public.elearning_content_blocks add constraint elearning_block_assessment_fk foreign key(tenant_id,assessment_id) references public.elearning_assessments(tenant_id,id) on delete restrict;
alter table public.elearning_content_blocks add constraint elearning_block_assessment_type check((type='assessment')=(assessment_id is not null));
alter table public.elearning_content_blocks add constraint elearning_block_assessment_required check(not required_for_completion or type='assessment');
create unique index elearning_lesson_assessment_placement on public.elearning_content_blocks(tenant_id,assessment_id) where assessment_id is not null;
alter table public.elearning_content_blocks add constraint elearning_block_placement_unique unique(tenant_id,course_id,lesson_id,id);
create table public.elearning_assessment_attempts (
 id uuid primary key default gen_random_uuid(),tenant_id integer not null,assessment_id uuid not null,user_id integer not null references public.users(id) on delete cascade,
 course_id uuid not null,lesson_id uuid not null,block_id uuid,enrollment_id uuid not null,
 attempt_number integer not null check(attempt_number>0),status text not null default 'in_progress' check(status in ('in_progress','submitted')),
 private_snapshot jsonb not null check(jsonb_typeof(private_snapshot)='object'),
 started_at timestamptz not null default now(),submitted_at timestamptz,earned_points numeric,total_points numeric,score_percentage numeric,passed boolean,
 foreign key(tenant_id,assessment_id) references public.elearning_assessments(tenant_id,id) on delete cascade,
 foreign key(tenant_id,course_id,enrollment_id) references public.elearning_enrollments(tenant_id,course_id,id) on delete cascade,
 foreign key(tenant_id,course_id,lesson_id) references public.elearning_lessons(tenant_id,course_id,id) on delete cascade,
 foreign key(tenant_id,course_id,lesson_id,block_id) references public.elearning_content_blocks(tenant_id,course_id,lesson_id,id) on delete set null(block_id),
 unique(tenant_id,id),unique(tenant_id,assessment_id,id),unique(tenant_id,assessment_id,enrollment_id,attempt_number),
 check((status='in_progress' and submitted_at is null and earned_points is null and total_points is null and score_percentage is null and passed is null) or
       (status='submitted' and submitted_at is not null and earned_points>=0 and total_points>0 and earned_points<=total_points and score_percentage between 0 and 100 and passed is not null))
);
create unique index elearning_one_open_assessment_attempt on public.elearning_assessment_attempts(tenant_id,assessment_id,enrollment_id) where status='in_progress';
create index elearning_assessment_results_idx on public.elearning_assessment_attempts(tenant_id,enrollment_id,assessment_id,status);
create table public.elearning_assessment_answers (
 tenant_id integer not null,attempt_id uuid not null,question_id uuid not null,response jsonb not null,earned_points numeric not null check(earned_points>=0),
 primary key(tenant_id,attempt_id,question_id),foreign key(tenant_id,attempt_id) references public.elearning_assessment_attempts(tenant_id,id) on delete cascade
);
-- Retain audio used by live/archived questions AND immutable historical snapshots.
create table public.elearning_assessment_media_refs (
 id uuid primary key default gen_random_uuid(),tenant_id integer not null,assessment_id uuid not null,question_id uuid,attempt_id uuid,media_id uuid not null,
 check((question_id is null)<>(attempt_id is null)),
 foreign key(tenant_id,assessment_id,question_id) references public.elearning_assessment_questions(tenant_id,assessment_id,id) on delete cascade,
 foreign key(tenant_id,assessment_id,attempt_id) references public.elearning_assessment_attempts(tenant_id,assessment_id,id) on delete cascade,
 foreign key(tenant_id,media_id) references public.builder_assets(tenant_id,id) on delete restrict
);
create index elearning_assessment_media_idx on public.elearning_assessment_media_refs(tenant_id,media_id);
create trigger elearning_assessment_updated before update on public.elearning_assessments for each row execute function public.set_updated_at();
create trigger elearning_question_updated before update on public.elearning_assessment_questions for each row execute function public.set_updated_at();

create function public.validate_elearning_assessment_question(p_tenant_id integer,p_question jsonb)
returns void language plpgsql security definer set search_path='' as $$
declare cfg jsonb; typ text; v jsonb; ids text[]; targets text[]; n integer; mid uuid;
begin
 typ:=p_question->>'type';cfg:=p_question->'config';
 if typ is null or typ not in ('multiple_choice','true_false','matching','listen_match') or jsonb_typeof(cfg) is distinct from 'object'
 or jsonb_typeof(p_question->'prompt') is distinct from 'string' or char_length(btrim(p_question->>'prompt')) not between 1 and 10000
 or jsonb_typeof(p_question->'points') is distinct from 'number' or (p_question->>'points')::numeric<=0 or (p_question->>'points')::numeric>10000
 or (p_question->>'points')::numeric<>round((p_question->>'points')::numeric,2)
 or exists(select 1 from jsonb_object_keys(p_question) k where k not in ('type','prompt','points','config')) then
 raise exception using errcode='22023',message='assessment_invalid_question';end if;
 if typ='true_false' then
  if jsonb_typeof(cfg->'correct_answer') is distinct from 'boolean' or cfg- 'correct_answer'<>'{}'::jsonb then raise exception using errcode='22023',message='assessment_invalid_true_false';end if;return;
 end if;
 if typ='multiple_choice' then
  if jsonb_typeof(cfg->'options') is distinct from 'array' or jsonb_array_length(cfg->'options') not between 2 and 20 or cfg - array['options','correct_option_id']<>'{}'::jsonb then raise exception using errcode='22023',message='assessment_invalid_options';end if;
  ids:=array[]::text[];
  for v in select value from jsonb_array_elements(cfg->'options') loop
   perform (v->>'id')::uuid;
   if v->>'id' is null or v->>'id'=any(ids) or jsonb_typeof(v->'label') is distinct from 'string' or char_length(btrim(v->>'label')) not between 1 and 2000 or v-array['id','label']<>'{}'::jsonb then raise exception using errcode='22023',message='assessment_invalid_options';end if;
   ids:=array_append(ids,v->>'id');
  end loop;
  if cfg->>'correct_option_id' is null or not(cfg->>'correct_option_id'=any(ids)) then raise exception using errcode='22023',message='assessment_correct_option_required';end if;return;
 end if;
 if jsonb_typeof(cfg->'prompts') is distinct from 'array' or jsonb_typeof(cfg->'targets') is distinct from 'array' or jsonb_typeof(cfg->'correct_pairs') is distinct from 'object'
 or jsonb_array_length(cfg->'prompts') not between 2 and 50 or jsonb_array_length(cfg->'targets')<>jsonb_array_length(cfg->'prompts') or cfg-array['prompts','targets','correct_pairs']<>'{}'::jsonb then raise exception using errcode='22023',message='assessment_invalid_pairs';end if;
 ids:=array[]::text[];targets:=array[]::text[];
 for v in select value from jsonb_array_elements(cfg->'targets') loop
  perform (v->>'id')::uuid;
  if v->>'id' is null or v->>'id'=any(targets) or jsonb_typeof(v->'label') is distinct from 'string' or char_length(btrim(v->>'label')) not between 1 and 2000 or v-array['id','label']<>'{}'::jsonb then raise exception using errcode='22023',message='assessment_invalid_pairs';end if;
  targets:=array_append(targets,v->>'id');
 end loop;
 for v in select value from jsonb_array_elements(cfg->'prompts') loop
  perform (v->>'id')::uuid;
  if v->>'id' is null or v->>'id'=any(ids) then raise exception using errcode='22023',message='assessment_invalid_pairs';end if;
  ids:=array_append(ids,v->>'id');
  if typ='matching' then
   if jsonb_typeof(v->'label') is distinct from 'string' or char_length(btrim(v->>'label')) not between 1 and 2000 or v-array['id','label']<>'{}'::jsonb then raise exception using errcode='22023',message='assessment_invalid_pairs';end if;
  else
   mid:=(v->>'media_id')::uuid;
   if mid is null or not exists(select 1 from public.builder_assets where tenant_id=p_tenant_id and id=mid and status in ('active','unreferenced') and mime_type in ('audio/mpeg','audio/wav'))
   or jsonb_typeof(v->'admin_label') is distinct from 'string' or char_length(v->>'admin_label')>120 or v-array['id','media_id','admin_label']<>'{}'::jsonb then raise exception using errcode='22023',message='assessment_invalid_audio';end if;
  end if;
  if jsonb_typeof(cfg->'correct_pairs'->(v->>'id')) is distinct from 'string' or not(cfg->'correct_pairs'->>(v->>'id')=any(targets)) then raise exception using errcode='22023',message='assessment_invalid_pairs';end if;
 end loop;
 select count(*) into n from jsonb_object_keys(cfg->'correct_pairs');
 if n<>cardinality(ids) or (select count(distinct value) from jsonb_each_text(cfg->'correct_pairs'))<>n then raise exception using errcode='22023',message='assessment_invalid_pairs';end if;
end $$;

create function public.elearning_question_guard() returns trigger language plpgsql security definer set search_path='' as $$
begin
 perform public.validate_elearning_assessment_question(new.tenant_id,jsonb_build_object('type',new.type,'prompt',new.prompt,'points',new.points,'config',new.config));return new;
end $$;
create trigger elearning_question_validate before insert or update of type,prompt,points,config on public.elearning_assessment_questions for each row execute function public.elearning_question_guard();
create function public.elearning_question_media_refs() returns trigger language plpgsql security definer set search_path='' as $$
begin
 delete from public.elearning_assessment_media_refs where tenant_id=new.tenant_id and question_id=new.id;
 if new.type='listen_match' then
 insert into public.elearning_assessment_media_refs(tenant_id,assessment_id,question_id,media_id)
 select new.tenant_id,new.assessment_id,new.id,(v->>'media_id')::uuid from jsonb_array_elements(new.config->'prompts') v;
 end if;return new;
end $$;
create trigger elearning_question_media after insert or update of config on public.elearning_assessment_questions for each row execute function public.elearning_question_media_refs();

create function public.validate_elearning_assessment_publish(p_tenant_id integer,p_assessment_id uuid) returns void language plpgsql security definer set search_path='' as $$
declare q record; n integer:=0;begin
 for q in select * from public.elearning_assessment_questions where tenant_id=p_tenant_id and assessment_id=p_assessment_id and archived_at is null loop
 n:=n+1;perform public.validate_elearning_assessment_question(p_tenant_id,jsonb_build_object('type',q.type,'prompt',q.prompt,'points',q.points,'config',q.config));end loop;
 if n=0 then raise exception using errcode='22023',message='assessment_questions_required';end if;
end $$;

create function public.clone_elearning_assessment(p_tenant_id integer,p_source uuid,p_actor integer) returns uuid language plpgsql security definer set search_path='' as $$
declare aid uuid;begin
 insert into public.elearning_assessments(tenant_id,title,instructions,passing_score,max_attempts,created_by)
 select tenant_id,title,instructions,passing_score,max_attempts,p_actor from public.elearning_assessments where tenant_id=p_tenant_id and id=p_source returning id into aid;
 if aid is null then raise exception using errcode='P0002',message='assessment_not_found';end if;
 insert into public.elearning_assessment_questions(tenant_id,assessment_id,type,prompt,points,position,config,archived_at)
 select tenant_id,aid,type,prompt,points,position,config,archived_at from public.elearning_assessment_questions where tenant_id=p_tenant_id and assessment_id=p_source order by position;
 return aid;
end $$;
create function public.elearning_assessment_placement_guard() returns trigger language plpgsql security definer set search_path='' as $$
begin
 if new.type='assessment' then
  if new.assessment_id is null then
   new.assessment_id:=public.clone_elearning_assessment(new.tenant_id,(new.content->>'assessment_id')::uuid,new.created_by);
  end if;
  new.required_for_completion:=coalesce((new.content->>'required_for_completion')::boolean,new.required_for_completion);
  new.content:=jsonb_build_object('version',1,'assessment_id',new.assessment_id,'required_for_completion',new.required_for_completion);
 end if;return new;
end $$;
create trigger elearning_assessment_placement before insert on public.elearning_content_blocks for each row execute function public.elearning_assessment_placement_guard();
create function public.elearning_assessment_placement_removed() returns trigger language plpgsql security definer set search_path='' as $$
begin
 if old.assessment_id is not null then
  if exists(select 1 from public.elearning_assessment_attempts where tenant_id=old.tenant_id and assessment_id=old.assessment_id) then
   update public.elearning_assessments set status='archived',archived_at=now() where tenant_id=old.tenant_id and id=old.assessment_id;
  else delete from public.elearning_assessments where tenant_id=old.tenant_id and id=old.assessment_id;end if;
 end if;return old;
end $$;
create trigger elearning_assessment_placement_delete after delete on public.elearning_content_blocks for each row execute function public.elearning_assessment_placement_removed();

-- Only whitelisted fields leave the engine. Target order is independent of the answer mapping.
create function public.elearning_safe_question(p_tenant_id integer,p_question jsonb) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare cfg jsonb:=p_question->'config'; prompts jsonb; targets jsonb; typ text:=p_question->>'type';begin
 if typ='multiple_choice' then cfg:=jsonb_build_object('options',cfg->'options');
 elsif typ='true_false' then cfg:='{}';
 else
  select coalesce(jsonb_agg(v order by v->>'id'),'[]') into targets from jsonb_array_elements(cfg->'targets') v;
  if typ='matching' then prompts:=cfg->'prompts';
  else
   select coalesce(jsonb_agg(jsonb_build_object('id',v->>'id','media',case when a.id is not null then jsonb_build_object('id',a.id,'url','/uploads/'||a.storage_key,'mime_type',a.mime_type) else null end) order by ord),'[]') into prompts
   from jsonb_array_elements(cfg->'prompts') with ordinality x(v,ord) left join public.builder_assets a on a.tenant_id=p_tenant_id and a.id=(v->>'media_id')::uuid and a.status in ('active','unreferenced');
  end if;
  cfg:=jsonb_build_object('prompts',prompts,'targets',targets);
 end if;
 return jsonb_build_object('id',p_question->>'id','type',typ,'prompt',p_question->>'prompt','points',p_question->'points','config',cfg);
end $$;
create function public.elearning_assessment_summary(p_tenant_id integer,p_assessment_id uuid) returns jsonb language sql stable security definer set search_path='' as $$
 select jsonb_build_object('id',a.id,'title',a.title,'instructions',a.instructions,'status',a.status,'passing_score',a.passing_score,'max_attempts',a.max_attempts,'revision',a.revision,'question_count',(select count(*) from public.elearning_assessment_questions q where q.tenant_id=a.tenant_id and q.assessment_id=a.id and q.archived_at is null))
 from public.elearning_assessments a where a.tenant_id=p_tenant_id and a.id=p_assessment_id;
$$;
create function public.get_elearning_assessment_author(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_block_id uuid) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare b public.elearning_content_blocks%rowtype;begin
 select * into b from public.elearning_content_blocks where tenant_id=p_tenant_id and course_id=p_course_id and lesson_id=p_lesson_id and id=p_block_id and type='assessment';
 if not found then raise exception using errcode='P0002',message='assessment_not_found';end if;
 return jsonb_build_object('block_id',b.id,'assessment',public.elearning_assessment_summary(p_tenant_id,b.assessment_id)||jsonb_build_object('required_for_completion',b.required_for_completion),'questions',coalesce((select jsonb_agg(to_jsonb(q) order by q.archived_at is not null,q.position,q.id) from public.elearning_assessment_questions q where q.tenant_id=p_tenant_id and q.assessment_id=b.assessment_id),'[]'));
end $$;

create function public.create_elearning_assessment(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_actor_id integer,p_expected_revision integer,p_details jsonb,p_questions jsonb) returns jsonb language plpgsql security definer set search_path='' as $$
declare aid uuid;bid uuid;v jsonb;pos integer:=0;begin
 perform pg_advisory_xact_lock(125,p_tenant_id);
 perform 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id and status<>'archived' for update;
 if not found then raise exception using errcode='P0002',message='assessment_not_found';end if;
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant_id and user_id=p_actor_id and role in ('owner','admin') and status='active') then raise exception using errcode='42501',message='assessment_author_forbidden';end if;
 perform 1 from public.elearning_lessons l join public.elearning_sections s on (s.tenant_id,s.course_id,s.id)=(l.tenant_id,l.course_id,l.section_id) where l.tenant_id=p_tenant_id and l.course_id=p_course_id and l.id=p_lesson_id and l.status<>'archived' and s.status<>'archived' and l.content_revision=p_expected_revision for update of l;
 if not found then raise exception using errcode='P0001',message='assessment_content_conflict';end if;
 if jsonb_typeof(p_questions) is distinct from 'array' or jsonb_array_length(p_questions)>200 then raise exception using errcode='22023',message='assessment_invalid_questions';end if;
 if p_details->>'status'='archived' then raise exception using errcode='22023',message='assessment_new_archived';end if;
 insert into public.elearning_assessments(tenant_id,title,instructions,passing_score,max_attempts,created_by) values(p_tenant_id,p_details->>'title',p_details->>'instructions',(p_details->>'passing_score')::numeric,(p_details->>'max_attempts')::integer,p_actor_id) returning id into aid;
 for v in select value from jsonb_array_elements(p_questions) loop
 perform public.validate_elearning_assessment_question(p_tenant_id,v);
 insert into public.elearning_assessment_questions(tenant_id,assessment_id,type,prompt,points,position,config) values(p_tenant_id,aid,v->>'type',v->>'prompt',(v->>'points')::numeric,pos,v->'config');pos:=pos+1;
 end loop;
 if p_details->>'status'='published' then perform public.validate_elearning_assessment_publish(p_tenant_id,aid);update public.elearning_assessments set status='published' where id=aid;end if;
 insert into public.elearning_content_blocks(tenant_id,course_id,lesson_id,type,title,content,assessment_id,required_for_completion,position,created_by)
 values(p_tenant_id,p_course_id,p_lesson_id,'assessment',p_details->>'title',jsonb_build_object('version',1,'assessment_id',aid,'required_for_completion',p_details->'required_for_completion'),aid,(p_details->>'required_for_completion')::boolean,(select coalesce(max(position),-1)+1 from public.elearning_content_blocks where tenant_id=p_tenant_id and lesson_id=p_lesson_id),p_actor_id) returning id into bid;
 update public.elearning_lessons set content_revision=content_revision+1 where id=p_lesson_id;update public.elearning_courses set structure_revision=structure_revision+1 where id=p_course_id;
 return public.get_elearning_assessment_author(p_tenant_id,p_course_id,p_lesson_id,bid)||jsonb_build_object('content',public.get_elearning_content(p_tenant_id,p_course_id,p_lesson_id));
end $$;

create function public.manage_elearning_assessment(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_block_id uuid,p_actor_id integer,p_expected_revision integer,p_action text,p_question_id uuid,p_payload jsonb) returns jsonb language plpgsql security definer set search_path='' as $$
declare b public.elearning_content_blocks%rowtype;a public.elearning_assessments%rowtype;q public.elearning_assessment_questions%rowtype;pos integer;swap uuid;begin
 perform pg_advisory_xact_lock(125,p_tenant_id);
 perform 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id and status<>'archived' for update;
 if not found then raise exception using errcode='P0002',message='assessment_not_found';end if;
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant_id and user_id=p_actor_id and role in ('owner','admin') and status='active') then raise exception using errcode='42501',message='assessment_author_forbidden';end if;
 select * into b from public.elearning_content_blocks where tenant_id=p_tenant_id and course_id=p_course_id and lesson_id=p_lesson_id and id=p_block_id and type='assessment' and archived_at is null for update;
 if not found or exists(select 1 from public.elearning_lessons l join public.elearning_sections s on (s.tenant_id,s.course_id,s.id)=(l.tenant_id,l.course_id,l.section_id) where l.tenant_id=p_tenant_id and l.id=p_lesson_id and (l.status='archived' or s.status='archived')) then raise exception using errcode='P0002',message='assessment_not_found';end if;
 select * into a from public.elearning_assessments where tenant_id=p_tenant_id and id=b.assessment_id for update;
 if a.revision is distinct from p_expected_revision then raise exception using errcode='P0001',message='assessment_conflict';end if;
 if p_action in ('settings','delete_assessment') then
  if p_question_id is not null then raise exception using errcode='22023',message='assessment_invalid_question';end if;
  if p_action='delete_assessment' then
   if p_payload->'confirmed' is distinct from 'true'::jsonb then raise exception using errcode='22023',message='assessment_confirmation_required';end if;
   perform public.manage_elearning_content(p_tenant_id,p_course_id,p_lesson_id,p_actor_id,(select content_revision from public.elearning_lessons where id=p_lesson_id),'delete',b.id,jsonb_build_object('confirmed',true));
   return jsonb_build_object('deleted',true,'content',public.get_elearning_content(p_tenant_id,p_course_id,p_lesson_id));
  end if;
  if p_payload->>'status'='published' then perform public.validate_elearning_assessment_publish(p_tenant_id,a.id);end if;
  update public.elearning_assessments set title=p_payload->>'title',instructions=p_payload->>'instructions',passing_score=(p_payload->>'passing_score')::numeric,max_attempts=(p_payload->>'max_attempts')::integer,status=p_payload->>'status',archived_at=case when p_payload->>'status'='archived' then now() else null end where id=a.id;
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
 return public.get_elearning_assessment_author(p_tenant_id,p_course_id,p_lesson_id,b.id);
end $$;

create function public.elearning_assessment_results(p_tenant_id integer,p_enrollment_id uuid) returns jsonb language sql stable security definer set search_path='' as $$
 select coalesce(jsonb_agg(to_jsonb(v) order by v.title,v.assessment_id),'[]') from (
 select a.id assessment_id,a.title,count(t.id) filter(where t.status='submitted') attempts,max(t.score_percentage) filter(where t.status='submitted') best_score,
 coalesce(bool_or(t.passed) filter(where t.status='submitted'),false) passed,max(t.submitted_at) last_attempt
 from public.elearning_assessments a join public.elearning_assessment_attempts t on (t.tenant_id,t.assessment_id)=(a.tenant_id,a.id)
 where t.tenant_id=p_tenant_id and t.enrollment_id=p_enrollment_id group by a.id,a.title) v;
$$;
create function public.elearning_required_assessments(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_enrollment_id uuid) returns jsonb language sql stable security definer set search_path='' as $$
 select coalesce(jsonb_agg(jsonb_build_object('id',a.id,'title',a.title,'passed',exists(select 1 from public.elearning_assessment_attempts t where t.tenant_id=p_tenant_id and t.assessment_id=a.id and t.enrollment_id=p_enrollment_id and t.status='submitted' and t.passed)) order by b.position,b.id),'[]')
 from public.elearning_content_blocks b join public.elearning_assessments a on(a.tenant_id,a.id)=(b.tenant_id,b.assessment_id)
 where b.tenant_id=p_tenant_id and b.course_id=p_course_id and b.lesson_id=p_lesson_id and b.archived_at is null and b.required_for_completion and a.status='published';
$$;

create function public.elearning_assessment_runtime(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_block_id uuid,p_user_id integer) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare s jsonb;b public.elearning_content_blocks%rowtype;a public.elearning_assessments%rowtype;e uuid;t public.elearning_assessment_attempts%rowtype;questions jsonb;submitted integer;best numeric;passed boolean;begin
 -- Reuse publication, section/lesson relationships, effective grants and sequential locks.
 s:=public.get_elearning_learner_course(p_tenant_id,p_user_id,p_course_id,p_lesson_id);e:=(s->'progress'->>'id')::uuid;
 select * into b from public.elearning_content_blocks where tenant_id=p_tenant_id and course_id=p_course_id and lesson_id=p_lesson_id and id=p_block_id and type='assessment' and archived_at is null;
 if not found then raise exception using errcode='P0002',message='assessment_not_found';end if;
 select * into a from public.elearning_assessments where tenant_id=p_tenant_id and id=b.assessment_id and status='published';
 if not found then raise exception using errcode='P0002',message='assessment_not_found';end if;
 select count(*) filter(where status='submitted'),max(score_percentage) filter(where status='submitted'),coalesce(bool_or(t2.passed) filter(where status='submitted'),false) into submitted,best,passed from public.elearning_assessment_attempts t2 where tenant_id=p_tenant_id and assessment_id=a.id and enrollment_id=e and user_id=p_user_id;
 select * into t from public.elearning_assessment_attempts where tenant_id=p_tenant_id and assessment_id=a.id and enrollment_id=e and user_id=p_user_id order by status='in_progress' desc,attempt_number desc limit 1;
 if t.id is not null then select coalesce(jsonb_agg(public.elearning_safe_question(p_tenant_id,v) order by ord),'[]') into questions from jsonb_array_elements(t.private_snapshot->'questions') with ordinality x(v,ord);end if;
 return jsonb_build_object('assessment',public.elearning_assessment_summary(p_tenant_id,a.id)||jsonb_build_object('required_for_completion',b.required_for_completion),
 'summary',jsonb_build_object('attempts',submitted,'best_score',best,'passed',passed,'remaining_attempts',case when a.max_attempts is null then null else greatest(a.max_attempts-submitted,0) end),
 'attempt',case when t.id is null then null else jsonb_build_object('id',t.id,'attempt_number',t.attempt_number,'status',t.status,'started_at',t.started_at,'submitted_at',t.submitted_at,'earned_points',t.earned_points,'total_points',t.total_points,'score_percentage',t.score_percentage,'passed',t.passed,'passing_score',t.private_snapshot->'assessment'->'passing_score','max_attempts',t.private_snapshot->'assessment'->'max_attempts','title',t.private_snapshot->'assessment'->'title','instructions',t.private_snapshot->'assessment'->'instructions','questions',questions) end);
end $$;

create function public.start_elearning_assessment_attempt(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_block_id uuid,p_user_id integer) returns jsonb language plpgsql security definer set search_path='' as $$
declare s jsonb;b public.elearning_content_blocks%rowtype;a public.elearning_assessments%rowtype;e uuid;tid uuid;used integer;qs jsonb;begin
 perform pg_advisory_xact_lock(125,p_tenant_id);perform 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id for update;
 s:=public.elearning_assessment_runtime(p_tenant_id,p_course_id,p_lesson_id,p_block_id,p_user_id);
 if s->'attempt'->>'status'='in_progress' then return s;end if;
 select * into b from public.elearning_content_blocks where tenant_id=p_tenant_id and id=p_block_id;
 select * into a from public.elearning_assessments where tenant_id=p_tenant_id and id=b.assessment_id;
 e:=(public.get_elearning_learner_course(p_tenant_id,p_user_id,p_course_id,p_lesson_id)->'progress'->>'id')::uuid;
 select count(*) into used from public.elearning_assessment_attempts where tenant_id=p_tenant_id and assessment_id=a.id and enrollment_id=e and status='submitted';
 if a.max_attempts is not null and used>=a.max_attempts then raise exception using errcode='42501',message='assessment_attempt_limit';end if;
 perform public.validate_elearning_assessment_publish(p_tenant_id,a.id);
 select jsonb_agg(jsonb_build_object('id',q.id,'type',q.type,'prompt',q.prompt,'points',q.points,'config',q.config,'position',q.position) order by q.position,q.id) into qs from public.elearning_assessment_questions q where tenant_id=p_tenant_id and assessment_id=a.id and archived_at is null;
 insert into public.elearning_assessment_attempts(tenant_id,assessment_id,user_id,course_id,lesson_id,block_id,enrollment_id,attempt_number,private_snapshot)
 values(p_tenant_id,a.id,p_user_id,p_course_id,p_lesson_id,p_block_id,e,used+1,jsonb_build_object('assessment',public.elearning_assessment_summary(p_tenant_id,a.id),'questions',qs)) returning id into tid;
 insert into public.elearning_assessment_media_refs(tenant_id,assessment_id,attempt_id,media_id)
 select p_tenant_id,a.id,tid,(prompt->>'media_id')::uuid from jsonb_array_elements(qs) question cross join lateral jsonb_array_elements(question->'config'->'prompts') prompt where question->>'type'='listen_match';
 return public.elearning_assessment_runtime(p_tenant_id,p_course_id,p_lesson_id,p_block_id,p_user_id);
end $$;

create function public.submit_elearning_assessment_attempt(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_block_id uuid,p_user_id integer,p_attempt_id uuid,p_answers jsonb) returns jsonb language plpgsql security definer set search_path='' as $$
declare s jsonb;t public.elearning_assessment_attempts%rowtype;q jsonb;r jsonb;cfg jsonb;earned numeric:=0;total numeric:=0;credit numeric;correct integer;n integer;score numeric;typ text;key text;ids text[];targets text[];begin
 perform pg_advisory_xact_lock(125,p_tenant_id);perform 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id for update;
 s:=public.elearning_assessment_runtime(p_tenant_id,p_course_id,p_lesson_id,p_block_id,p_user_id);
 select * into t from public.elearning_assessment_attempts where tenant_id=p_tenant_id and course_id=p_course_id and lesson_id=p_lesson_id and block_id=p_block_id and id=p_attempt_id and user_id=p_user_id and assessment_id=(s->'assessment'->>'id')::uuid for update;
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
 return public.elearning_assessment_runtime(p_tenant_id,p_course_id,p_lesson_id,p_block_id,p_user_id);
end $$;

create function public.get_elearning_assessment_preview(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_block_id uuid) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare s jsonb;qs jsonb;begin
 s:=public.get_elearning_assessment_author(p_tenant_id,p_course_id,p_lesson_id,p_block_id);
 select coalesce(jsonb_agg(public.elearning_safe_question(p_tenant_id,q) order by ord),'[]') into qs from jsonb_array_elements(s->'questions') with ordinality v(q,ord) where q->>'archived_at' is null;
 return jsonb_build_object('assessment',s->'assessment','questions',qs);
end $$;

alter function public.get_elearning_content(integer,uuid,uuid) rename to get_elearning_content_schema126;
create function public.get_elearning_content(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare s jsonb;blocks jsonb;begin
 s:=public.get_elearning_content_schema126(p_tenant_id,p_course_id,p_lesson_id);
 if s is null then return null;end if;
 select coalesce(jsonb_agg(v||case when v->>'type'='assessment' then jsonb_build_object('assessment',public.elearning_assessment_summary(p_tenant_id,(v->>'assessment_id')::uuid)) else '{}' end order by ord),'[]') into blocks from jsonb_array_elements(s->'blocks') with ordinality x(v,ord);
 return jsonb_set(s,'{blocks}',blocks);
end $$;
alter function public.manage_elearning_content(integer,uuid,uuid,integer,integer,text,uuid,jsonb) rename to manage_elearning_content_schema126;
create function public.manage_elearning_content(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_user_id integer,p_expected_revision integer,p_action text,p_entity_id uuid default null,p_payload jsonb default '{}'::jsonb) returns jsonb language plpgsql security definer set search_path='' as $$
begin
 perform pg_advisory_xact_lock(125,p_tenant_id);
 if p_action in ('create','update') and (p_payload->>'type'='assessment' or exists(select 1 from public.elearning_content_blocks where tenant_id=p_tenant_id and id=p_entity_id and type='assessment')) then raise exception using errcode='22023',message='assessment_use_builder';end if;
 return public.manage_elearning_content_schema126(p_tenant_id,p_course_id,p_lesson_id,p_user_id,p_expected_revision,p_action,p_entity_id,p_payload);
end $$;
alter function public.get_elearning_learner_course(integer,integer,uuid,uuid) rename to get_elearning_learner_course_schema126;
create function public.get_elearning_learner_course(p_tenant_id integer,p_user_id integer,p_course_id uuid,p_lesson_id uuid default null) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare s jsonb;blocks jsonb;requirements jsonb;begin
 s:=public.get_elearning_learner_course_schema126(p_tenant_id,p_user_id,p_course_id,p_lesson_id);
 select coalesce(jsonb_agg(v||case when v->>'type'='assessment' then jsonb_build_object('assessment',public.elearning_assessment_summary(p_tenant_id,(v->'content'->>'assessment_id')::uuid)) else '{}' end order by ord),'[]') into blocks
 from jsonb_array_elements(s->'blocks') with ordinality x(v,ord) where v->>'type'<>'assessment' or exists(select 1 from public.elearning_assessments a where a.tenant_id=p_tenant_id and a.id=(v->'content'->>'assessment_id')::uuid and a.status='published');
 s:=jsonb_set(s,'{blocks}',blocks);
 if p_lesson_id is not null then
 requirements:=public.elearning_required_assessments(p_tenant_id,p_course_id,p_lesson_id,(s->'progress'->>'id')::uuid);
 s:=s||jsonb_build_object('assessment_requirements',requirements);
 end if;return s;
end $$;
alter function public.complete_elearning_learner_lesson(integer,integer,uuid,uuid) rename to complete_elearning_learner_lesson_schema126;
create function public.complete_elearning_learner_lesson(p_tenant_id integer,p_user_id integer,p_course_id uuid,p_lesson_id uuid) returns jsonb language plpgsql security definer set search_path='' as $$
declare s jsonb;e uuid;begin
 perform pg_advisory_xact_lock(125,p_tenant_id);perform 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id for update;
 s:=public.get_elearning_learner_course(p_tenant_id,p_user_id,p_course_id,p_lesson_id);e:=(s->'progress'->>'id')::uuid;
 if not exists(select 1 from public.elearning_lesson_completions where tenant_id=p_tenant_id and enrollment_id=e and lesson_id=p_lesson_id)
 and exists(select 1 from jsonb_array_elements(s->'assessment_requirements') v where not(v->>'passed')::boolean) then raise exception using errcode='42501',message='elearning_assessment_required';end if;
 return public.complete_elearning_learner_lesson_schema126(p_tenant_id,p_user_id,p_course_id,p_lesson_id);
end $$;
alter function public.manage_elearning_participation(integer,uuid,integer,text,jsonb) rename to manage_elearning_participation_schema126;
create function public.manage_elearning_participation(p_tenant_id integer,p_course_id uuid,p_user_id integer,p_action text,p_payload jsonb) returns jsonb language plpgsql security definer set search_path='' as $$
begin
 perform pg_advisory_xact_lock(125,p_tenant_id);perform 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id for update;
 if p_action='complete_lesson' and not exists(select 1 from public.elearning_lesson_completions where tenant_id=p_tenant_id and enrollment_id=(p_payload->>'enrollment_id')::uuid and lesson_id=(p_payload->>'lesson_id')::uuid)
 and exists(select 1 from jsonb_array_elements(public.elearning_required_assessments(p_tenant_id,p_course_id,(p_payload->>'lesson_id')::uuid,(p_payload->>'enrollment_id')::uuid)) v where not(v->>'passed')::boolean) then raise exception using errcode='42501',message='elearning_assessment_required';end if;
 return public.manage_elearning_participation_schema126(p_tenant_id,p_course_id,p_user_id,p_action,p_payload);
end $$;
alter function public.elearning_learner_media_access(integer,integer,text) rename to elearning_learner_media_access_schema126;
create function public.elearning_learner_media_access(p_tenant_id integer,p_user_id integer,p_storage_key text) returns boolean language plpgsql stable security definer set search_path='' as $$
declare a uuid;r record;s jsonb;baseline boolean;begin
 baseline:=public.elearning_learner_media_access_schema126(p_tenant_id,p_user_id,p_storage_key);
 if baseline is true then return true;end if;
 select id into a from public.builder_assets where tenant_id=p_tenant_id and storage_key=p_storage_key and status in ('active','unreferenced');
 if a is null then return false;end if;
 if not exists(select 1 from public.elearning_assessment_media_refs where tenant_id=p_tenant_id and media_id=a) then return baseline;end if;
 if exists(select 1 from public.tenant_memberships m join public.users u on u.id=m.user_id and u.account_status='active' where m.tenant_id=p_tenant_id and m.user_id=p_user_id and m.status='active' and m.role in ('owner','admin')) then return true;end if;
 for r in select distinct b.course_id,b.lesson_id from public.elearning_content_blocks b join public.elearning_assessments ass on(ass.tenant_id,ass.id)=(b.tenant_id,b.assessment_id) join public.elearning_assessment_media_refs m on(m.tenant_id,m.assessment_id)=(ass.tenant_id,ass.id)
 where b.tenant_id=p_tenant_id and b.archived_at is null and ass.status='published' and m.media_id=a and (m.question_id is not null and exists(select 1 from public.elearning_assessment_questions q where q.id=m.question_id and q.archived_at is null) or m.attempt_id is not null and exists(select 1 from public.elearning_assessment_attempts t where t.id=m.attempt_id and t.user_id=p_user_id)) loop
  begin s:=public.get_elearning_learner_course(p_tenant_id,p_user_id,r.course_id,r.lesson_id);return true;exception when no_data_found or insufficient_privilege then null;end;
 end loop;return false;
end $$;

-- The existing report engine retains the same percentages; only summaries are attached.
create or replace function public.get_elearning_progress_records(p_tenant_id integer,p_course_id uuid,p_include_inactive boolean) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare s jsonb;rows jsonb;begin
 s:=public.get_elearning_progress_records(p_tenant_id,p_course_id,p_include_inactive,true);
 select coalesce(jsonb_agg(v||jsonb_build_object('assessment_results',public.elearning_assessment_results(p_tenant_id,(v->>'id')::uuid)) order by ord),'[]') into rows from jsonb_array_elements(s->'enrollments') with ordinality x(v,ord);
 return jsonb_set(s,'{enrollments}',rows);
end $$;
alter function public.delete_elearning_course(integer,uuid,integer,integer,integer,text,boolean) rename to delete_elearning_course_schema126;
create function public.delete_elearning_course(p_tenant_id integer,p_course_id uuid,p_user_id integer,p_expected_revision integer,p_expected_structure_revision integer,p_confirmation_name text,p_confirmed boolean) returns jsonb language plpgsql security definer set search_path='' as $$
declare ids uuid[];s jsonb;begin
 perform pg_advisory_xact_lock(125,p_tenant_id);
 select array_agg(assessment_id) into ids from public.elearning_content_blocks where tenant_id=p_tenant_id and course_id=p_course_id and assessment_id is not null;
 s:=public.delete_elearning_course_schema126(p_tenant_id,p_course_id,p_user_id,p_expected_revision,p_expected_structure_revision,p_confirmation_name,p_confirmed);
 delete from public.elearning_assessments a where tenant_id=p_tenant_id and id=any(ids) and not exists(select 1 from public.elearning_content_blocks b where b.tenant_id=a.tenant_id and b.assessment_id=a.id);
 return s;
end $$;

alter table public.elearning_assessments enable row level security;
revoke all on public.elearning_assessments from public,anon,authenticated,service_role;
grant select on public.elearning_assessments to service_role;

alter table public.elearning_assessment_questions enable row level security;
revoke all on public.elearning_assessment_questions from public,anon,authenticated,service_role;
grant select on public.elearning_assessment_questions to service_role;

alter table public.elearning_assessment_attempts enable row level security;
revoke all on public.elearning_assessment_attempts from public,anon,authenticated,service_role;

alter table public.elearning_assessment_answers enable row level security;
revoke all on public.elearning_assessment_answers from public,anon,authenticated,service_role;

alter table public.elearning_assessment_media_refs enable row level security;
revoke all on public.elearning_assessment_media_refs from public,anon,authenticated,service_role;
grant select on public.elearning_assessment_media_refs to service_role;

do $$ declare f record;begin
 for f in select p.oid::regprocedure signature from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname in ('clone_elearning_assessment','complete_elearning_learner_lesson','create_elearning_assessment','delete_elearning_course','elearning_assessment_placement_guard','elearning_assessment_placement_removed','elearning_assessment_results','elearning_assessment_runtime','elearning_assessment_summary','elearning_learner_media_access','elearning_question_guard','elearning_question_media_refs','elearning_required_assessments','elearning_safe_question','get_elearning_assessment_author','get_elearning_assessment_preview','get_elearning_content','get_elearning_learner_course','get_elearning_progress_records','manage_elearning_assessment','manage_elearning_content','manage_elearning_participation','start_elearning_assessment_attempt','submit_elearning_assessment_attempt','validate_elearning_assessment_publish','validate_elearning_assessment_question','get_elearning_content_schema126','manage_elearning_content_schema126','get_elearning_learner_course_schema126','complete_elearning_learner_lesson_schema126','manage_elearning_participation_schema126','elearning_learner_media_access_schema126','delete_elearning_course_schema126') loop
 execute 'revoke all on function '||f.signature||' from public,anon,authenticated,service_role';
 end loop;end $$;
do $$ declare f record;begin
 for f in select p.oid::regprocedure signature from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname in ('get_elearning_assessment_author','get_elearning_assessment_preview','create_elearning_assessment','manage_elearning_assessment','elearning_assessment_runtime','start_elearning_assessment_attempt','submit_elearning_assessment_attempt','get_elearning_content','manage_elearning_content','get_elearning_learner_course','complete_elearning_learner_lesson','manage_elearning_participation','elearning_learner_media_access','delete_elearning_course') or n.nspname='public' and p.proname='get_elearning_progress_records' and p.pronargs=3 loop
 execute 'grant execute on function '||f.signature||' to service_role';
 end loop;end $$;
notify pgrst,'reload schema';
commit;
