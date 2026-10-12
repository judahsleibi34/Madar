begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_143_schema_state_missing';end if;
 if v_schema_version <> 141 then raise exception 'migration_143_expected_schema_141_got_%',v_schema_version;end if;
 update public.application_schema_state set schema_version=143,applied_at=now() where contract_key='core';
end;
$$;
-- Learning branch intentionally excludes Exchange142. Historical results remain final.
alter table public.elearning_assessments add column activity_mode text not null default 'graded' check(activity_mode in ('graded','practice'));
alter table public.elearning_assessments add column pool_size integer check(pool_size between 1 and 200);
alter table public.elearning_assessments add column shuffle_questions boolean not null default false;
alter table public.elearning_assessments add column shuffle_options boolean not null default false;
alter table public.elearning_assessments add column practice_feedback boolean not null default true;
alter table public.elearning_assessment_attempts add column review_revision integer not null default 1 check(review_revision>0);
alter table public.elearning_assessment_answers alter column earned_points drop not null;
do $$ declare c record;begin
 for c in select conname from pg_constraint where conrelid='public.elearning_assessment_attempts'::regclass and contype='c' and (pg_get_constraintdef(oid) like '%status%' or pg_get_constraintdef(oid) like '%submitted_at%') loop
 execute format('alter table public.elearning_assessment_attempts drop constraint %I',c.conname);end loop;
end $$;
alter table public.elearning_assessment_attempts add constraint elearning_attempt_status143 check(status in ('in_progress','pending_review','submitted'));
alter table public.elearning_assessment_attempts add constraint elearning_attempt_result143 check(
 (status='in_progress' and submitted_at is null and earned_points is null and total_points is null and score_percentage is null and passed is null) or
 (status='pending_review' and submitted_at is not null and earned_points is null and total_points is not null and total_points>0 and score_percentage is null and passed is null) or
 (status='submitted' and submitted_at is not null and (
  (coalesce(private_snapshot->'assessment'->>'activity_mode','graded')='graded' and earned_points is not null and earned_points>=0 and total_points is not null and total_points>0 and earned_points<=total_points and score_percentage is not null and score_percentage between 0 and 100 and passed is not null) or
  (private_snapshot->'assessment'->>'activity_mode'='practice' and earned_points is null and total_points is null and score_percentage is null and passed is null))));
create index elearning_pending_review143 on public.elearning_assessment_attempts(tenant_id,course_id,submitted_at,id) where status='pending_review';
create index elearning_pending_order143 on public.elearning_assessment_attempts(tenant_id,submitted_at,id) where status='pending_review';
create index elearning_recording_gc143 on public.storage_objects(created_at,tenant_id,id) where category='elearning_assessment' and status='active';
create table public.elearning_assessment_recordings (
 id uuid primary key, tenant_id integer not null, attempt_id uuid not null,question_id uuid not null,
 storage_key text not null unique,sha256 text not null check(sha256 ~ '^[a-f0-9]{64}$'),
 size_bytes integer not null check(size_bytes between 45 and 10485760),duration_ms integer not null check(duration_ms between 1 and 300000),
 mime_type text not null check(mime_type='audio/wav'),created_at timestamptz not null default now(),
 foreign key(tenant_id,attempt_id) references public.elearning_assessment_attempts(tenant_id,id) on delete restrict,
 unique(tenant_id,attempt_id,question_id,id),unique(tenant_id,id));
create table public.elearning_assessment_reviews (
 id uuid primary key default gen_random_uuid(),tenant_id integer not null,attempt_id uuid not null,question_id uuid not null,
 reviewer_id integer not null references public.users(id) on delete restrict,points numeric not null check(points>=0),
 feedback text not null check(char_length(feedback)<=10000),created_at timestamptz not null default now(),
 foreign key(tenant_id,attempt_id,question_id) references public.elearning_assessment_answers(tenant_id,attempt_id,question_id) on delete restrict,
 unique(tenant_id,attempt_id,question_id));
create trigger elearning_review_immutable before update or delete on public.elearning_assessment_reviews for each row execute function public.elearning_immutable_completion();
alter table public.elearning_assessment_recordings enable row level security;
alter table public.elearning_assessment_reviews enable row level security;
revoke all on public.elearning_assessment_recordings,public.elearning_assessment_reviews from public,anon,authenticated,service_role;


create or replace function public.validate_elearning_assessment_question(p_tenant_id integer,p_question jsonb)
returns void language plpgsql security definer set search_path='' as $$
declare cfg jsonb; typ text; v jsonb; ids text[]; targets text[]; n integer; mid uuid;
begin
 typ:=p_question->>'type';cfg:=p_question->'config';
 if typ is null or typ not in ('multiple_choice','true_false','matching','listen_match','picture_listen','speaking','written','speaking_practice') or jsonb_typeof(cfg) is distinct from 'object'
 or jsonb_typeof(p_question->'prompt') is distinct from 'string' or char_length(btrim(p_question->>'prompt')) not between 1 and 10000
 or jsonb_typeof(p_question->'points') is distinct from 'number' or (p_question->>'points')::numeric<=0 or (p_question->>'points')::numeric>10000
 or (p_question->>'points')::numeric<>round((p_question->>'points')::numeric,2)
 or exists(select 1 from jsonb_object_keys(p_question) k where k not in ('type','prompt','points','config')) then
 raise exception using errcode='22023',message='assessment_invalid_question';end if;
 if typ in ('speaking','written','speaking_practice') then
  if cfg-array['rubric','max_characters','max_duration_seconds','max_size_bytes','media_id']<>'{}'::jsonb
   or jsonb_typeof(cfg->'rubric') is distinct from 'string' or char_length(cfg->>'rubric')>10000 then raise exception using errcode='22023',message='assessment_invalid_subjective';end if;
  if typ='written' and (jsonb_typeof(cfg->'max_characters') is distinct from 'number' or (cfg->>'max_characters')::integer not between 1 and 20000) then raise exception using errcode='22023',message='assessment_invalid_subjective';end if;
  if typ in ('speaking','speaking_practice') and ((cfg->>'max_duration_seconds')::integer not between 1 and 300 or (cfg->>'max_size_bytes')::integer not between 1024 and 10485760 or cfg->>'max_duration_seconds' is null or cfg->>'max_size_bytes' is null) then raise exception using errcode='22023',message='assessment_invalid_subjective';end if;
  if cfg->>'media_id' is not null and not exists(select 1 from public.builder_assets where tenant_id=p_tenant_id and id=(cfg->>'media_id')::uuid and status in ('active','unreferenced') and mime_type in ('audio/mpeg','audio/wav')) then raise exception using errcode='22023',message='assessment_invalid_audio';end if;
  return;
 end if;
 if typ='picture_listen' then
  if cfg-array['media_id','options','correct_option_id']<>'{}'::jsonb or jsonb_typeof(cfg->'options') is distinct from 'array' or jsonb_array_length(cfg->'options') not between 2 and 20 or not exists(select 1 from public.builder_assets where tenant_id=p_tenant_id and id=(cfg->>'media_id')::uuid and status in ('active','unreferenced') and mime_type in ('audio/mpeg','audio/wav')) then raise exception using errcode='22023',message='assessment_invalid_audio';end if;
  ids:=array[]::text[];
  for v in select value from jsonb_array_elements(cfg->'options') loop
   perform (v->>'id')::uuid;
   if v-array['id','media_id','alt']<>'{}'::jsonb or v->>'id' is null or v->>'id'=any(ids) or jsonb_typeof(v->'alt') is distinct from 'string' or char_length(btrim(v->>'alt')) not between 1 and 2000 or not exists(select 1 from public.builder_assets where tenant_id=p_tenant_id and id=(v->>'media_id')::uuid and status in ('active','unreferenced') and mime_type in ('image/png','image/jpeg','image/webp')) then raise exception using errcode='22023',message='assessment_invalid_image';end if;
   ids:=array_append(ids,v->>'id');
  end loop;
  if cfg->>'correct_option_id' is null or not(cfg->>'correct_option_id'=any(ids)) then raise exception using errcode='22023',message='assessment_correct_option_required';end if;
  return;
 end if;
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

create or replace function public.create_elearning_assessment(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_actor_id integer,p_expected_revision integer,p_details jsonb,p_questions jsonb) returns jsonb language plpgsql security definer set search_path='' as $$
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
 update public.elearning_assessments set activity_mode=coalesce(p_details->>'activity_mode','graded'),pool_size=(p_details->>'pool_size')::integer,shuffle_questions=coalesce((p_details->>'shuffle_questions')::boolean,false),shuffle_options=coalesce((p_details->>'shuffle_options')::boolean,false),practice_feedback=coalesce((p_details->>'practice_feedback')::boolean,true) where id=aid;
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

create or replace function public.create_elearning_placed_assessment(p_tenant_id integer,p_course_id uuid,p_section_id uuid,p_actor_id integer,p_expected_revision integer,p_details jsonb,p_questions jsonb,p_assessment_id uuid default null) returns jsonb language plpgsql security definer set search_path='' as $$
declare aid uuid:=p_assessment_id;pid uuid;v jsonb;pos integer:=0;begin
 perform pg_advisory_xact_lock(125,p_tenant_id);perform 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id and status<>'archived' and structure_revision=p_expected_revision for update;
 if not found then raise exception using errcode='P0001',message='assessment_content_conflict';end if;
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant_id and user_id=p_actor_id and status='active' and role in('owner','admin')) then raise exception using errcode='42501',message='assessment_author_forbidden';end if;
 if p_section_id is not null and not exists(select 1 from public.elearning_sections where tenant_id=p_tenant_id and course_id=p_course_id and id=p_section_id and status<>'archived') then raise exception using errcode='P0002',message='assessment_not_found';end if;
 if (aid is null and coalesce(p_details->>'activity_mode','graded')='practice') or (aid is not null and exists(select 1 from public.elearning_assessments where tenant_id=p_tenant_id and id=aid and activity_mode='practice')) then raise exception using errcode='22023',message='assessment_practice_requires_lesson';end if;
 if aid is null then
 if jsonb_typeof(p_questions) is distinct from 'array' or jsonb_array_length(p_questions)>200 or p_details->>'status'='archived' then raise exception using errcode='22023',message='assessment_invalid_questions';end if;
 insert into public.elearning_assessments(tenant_id,title,instructions,passing_score,max_attempts,created_by) values(p_tenant_id,p_details->>'title',p_details->>'instructions',(p_details->>'passing_score')::numeric,(p_details->>'max_attempts')::integer,p_actor_id) returning id into aid;
 update public.elearning_assessments set activity_mode=coalesce(p_details->>'activity_mode','graded'),pool_size=(p_details->>'pool_size')::integer,shuffle_questions=coalesce((p_details->>'shuffle_questions')::boolean,false),shuffle_options=coalesce((p_details->>'shuffle_options')::boolean,false),practice_feedback=coalesce((p_details->>'practice_feedback')::boolean,true) where id=aid;
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
  update public.elearning_assessments set title=p_payload->>'title',instructions=p_payload->>'instructions',passing_score=(p_payload->>'passing_score')::numeric,max_attempts=(p_payload->>'max_attempts')::integer,activity_mode=coalesce(p_payload->>'activity_mode','graded'),pool_size=(p_payload->>'pool_size')::integer,shuffle_questions=coalesce((p_payload->>'shuffle_questions')::boolean,false),shuffle_options=coalesce((p_payload->>'shuffle_options')::boolean,false),practice_feedback=coalesce((p_payload->>'practice_feedback')::boolean,true),status=p_payload->>'status',archived_at=case when p_payload->>'status'='archived' then now() else null end where id=a.id;
  if p_payload->>'status'='published' then perform public.validate_elearning_assessment_publish(p_tenant_id,a.id);end if;
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
 select count(*) filter(where status in ('submitted','pending_review')),max(score_percentage) filter(where status='submitted'),coalesce(bool_or(t2.passed) filter(where status='submitted'),false) into submitted,best,passed from public.elearning_assessment_attempts t2 where tenant_id=p_tenant_id and placement_id=b.id and enrollment_id=e and user_id=p_user_id;
 select * into t from public.elearning_assessment_attempts where tenant_id=p_tenant_id and placement_id=b.id and enrollment_id=e and user_id=p_user_id order by status='in_progress' desc,attempt_number desc limit 1;
 if t.id is not null then select coalesce(jsonb_agg(public.elearning_safe_question(p_tenant_id,v) order by ord),'[]') into questions from jsonb_array_elements(t.private_snapshot->'questions') with ordinality x(v,ord);end if;
 return jsonb_build_object('assessment',public.elearning_assessment_summary(p_tenant_id,a.id)||jsonb_build_object('required_for_completion',b.required_for_completion),
 'summary',jsonb_build_object('attempts',submitted,'best_score',best,'passed',passed,'remaining_attempts',case when a.max_attempts is null then null else greatest(a.max_attempts-submitted,0) end),
 'attempt',case when t.id is null then null else jsonb_build_object('id',t.id,'attempt_number',t.attempt_number,'status',t.status,'started_at',t.started_at,'submitted_at',t.submitted_at,'earned_points',t.earned_points,'total_points',t.total_points,'score_percentage',t.score_percentage,'passed',t.passed,'passing_score',t.private_snapshot->'assessment'->'passing_score','max_attempts',t.private_snapshot->'assessment'->'max_attempts','title',t.private_snapshot->'assessment'->'title','instructions',t.private_snapshot->'assessment'->'instructions','questions',questions,'review_revision',t.review_revision,'activity_mode',coalesce(t.private_snapshot->'assessment'->>'activity_mode','graded'),'recordings',case when t.status='in_progress' then (select coalesce(jsonb_object_agg(r.question_id,r.id),'{}') from (select distinct on(question_id) question_id,id from public.elearning_assessment_recordings where tenant_id=p_tenant_id and attempt_id=t.id order by question_id,created_at desc,id desc) r) else '{}'::jsonb end,'feedback',case when t.status='submitted' then (select coalesce(jsonb_agg(jsonb_build_object('question_id',ans.question_id,'points',case when q->>'type'='speaking_practice' then null else ans.earned_points end,'maximum',case when q->>'type'='speaking_practice' then null else (q->>'points')::numeric end,'correct',case when q->>'type' in ('speaking','written','speaking_practice') then null else ans.earned_points=(q->>'points')::numeric end,'feedback',r.feedback) order by ord),'[]') from jsonb_array_elements(t.private_snapshot->'questions') with ordinality x(q,ord) join public.elearning_assessment_answers ans on ans.tenant_id=t.tenant_id and ans.attempt_id=t.id and ans.question_id=(q->>'id')::uuid left join public.elearning_assessment_reviews r on r.tenant_id=ans.tenant_id and r.attempt_id=ans.attempt_id and r.question_id=ans.question_id where coalesce(t.private_snapshot->'assessment'->>'activity_mode','graded')='graded' or coalesce((t.private_snapshot->'assessment'->>'practice_feedback')::boolean,true)) else '[]'::jsonb end) end);
end $$;

create or replace function public.start_elearning_assessment_attempt(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_block_id uuid,p_user_id integer) returns jsonb language plpgsql security definer set search_path='' as $$
declare s jsonb;b public.elearning_assessment_placements%rowtype;a public.elearning_assessments%rowtype;e uuid;tid uuid;used integer;qs jsonb;begin
 perform pg_advisory_xact_lock(125,p_tenant_id);perform 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id for update;
 s:=public.elearning_assessment_runtime(p_tenant_id,p_course_id,p_lesson_id,p_block_id,p_user_id);
 if s->'attempt'->>'status' in ('in_progress','pending_review') then return s;end if;
 b:=public.elearning_resolve_placement(p_tenant_id,p_course_id,p_lesson_id,p_block_id);
 select * into a from public.elearning_assessments where tenant_id=p_tenant_id and id=b.assessment_id;
 e:=(public.get_elearning_learner_course(p_tenant_id,p_user_id,p_course_id,p_lesson_id)->'progress'->>'id')::uuid;
 select count(*) into used from public.elearning_assessment_attempts where tenant_id=p_tenant_id and placement_id=b.id and enrollment_id=e and status in ('submitted','pending_review');
 if a.max_attempts is not null and used>=a.max_attempts then raise exception using errcode='42501',message='assessment_attempt_limit';end if;
 perform public.validate_elearning_assessment_publish(p_tenant_id,a.id);
 select jsonb_agg(value order by ord) into qs from (
 select jsonb_build_object('id',q.id,'type',q.type,'prompt',q.prompt,'points',q.points,'config',q.config,'position',q.position) value,
 case when a.shuffle_questions or a.pool_size is not null then random() else q.position::double precision end ord
 from public.elearning_assessment_questions q where tenant_id=p_tenant_id and assessment_id=a.id and archived_at is null
 order by ord,q.id limit coalesce(a.pool_size,200)) selected;
 if a.shuffle_options then
 select jsonb_agg(case when v->'config' ? 'options' then jsonb_set(v,'{config,options}',(select jsonb_agg(o order by random()) from jsonb_array_elements(v->'config'->'options') o)) else v end order by ord) into qs from jsonb_array_elements(qs) with ordinality x(v,ord);
 end if;
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
 if t.status in ('submitted','pending_review') then
  if s->'attempt'->>'id'<>t.id::text then
   return jsonb_set(s,'{attempt}',jsonb_build_object('id',t.id,'attempt_number',t.attempt_number,'status',t.status,'earned_points',t.earned_points,'total_points',t.total_points,'score_percentage',t.score_percentage,'passed',t.passed,'passing_score',t.private_snapshot->'assessment'->'passing_score','max_attempts',t.private_snapshot->'assessment'->'max_attempts','submitted_at',t.submitted_at));
  end if;return s;
 end if;
 if jsonb_typeof(p_answers) is distinct from 'object' or (select count(*) from jsonb_object_keys(p_answers))<>jsonb_array_length(t.private_snapshot->'questions') then raise exception using errcode='22023',message='assessment_answers_required';end if;
 for q in select value from jsonb_array_elements(t.private_snapshot->'questions') loop
  typ:=q->>'type';cfg:=q->'config';r:=p_answers->(q->>'id');credit:=0;
  if r is null or jsonb_typeof(r) is distinct from 'object' then raise exception using errcode='22023',message='assessment_invalid_response';end if;
  if typ in ('multiple_choice','picture_listen') then
   if r-'option_id'<>'{}'::jsonb or jsonb_typeof(r->'option_id') is distinct from 'string' or not exists(select 1 from jsonb_array_elements(cfg->'options') v where v->>'id'=r->>'option_id') then raise exception using errcode='22023',message='assessment_invalid_response';end if;
   if r->>'option_id'=cfg->>'correct_option_id' then credit:=(q->>'points')::numeric;end if;
  elsif typ='true_false' then
   if r-'value'<>'{}'::jsonb or jsonb_typeof(r->'value') is distinct from 'boolean' then raise exception using errcode='22023',message='assessment_invalid_response';end if;
   if r->'value'=cfg->'correct_answer' then credit:=(q->>'points')::numeric;end if;
  elsif typ='written' then
   if r-'text'<>'{}'::jsonb or jsonb_typeof(r->'text') is distinct from 'string' or char_length(btrim(r->>'text')) not between 1 and (cfg->>'max_characters')::integer then raise exception using errcode='22023',message='assessment_invalid_response';end if;credit:=null;
  elsif typ='speaking' then
   if r-'recording_id'<>'{}'::jsonb or not exists(select 1 from public.elearning_assessment_recordings where tenant_id=p_tenant_id and attempt_id=t.id and question_id=(q->>'id')::uuid and id=(r->>'recording_id')::uuid) then raise exception using errcode='22023',message='assessment_invalid_recording';end if;credit:=null;
  elsif typ='speaking_practice' then
   if t.private_snapshot->'assessment'->>'activity_mode' is distinct from 'practice' or r is distinct from '{"finished":true}'::jsonb then raise exception using errcode='22023',message='assessment_invalid_response';end if;credit:=null;
  else
   if r-'matches' <>'{}'::jsonb or jsonb_typeof(r->'matches') is distinct from 'object' or (select count(*) from jsonb_object_keys(r->'matches'))<>jsonb_array_length(cfg->'prompts') then raise exception using errcode='22023',message='assessment_invalid_response';end if;
   correct:=0;n:=jsonb_array_length(cfg->'prompts');
   for key in select v->>'id' from jsonb_array_elements(cfg->'prompts') v loop
    if jsonb_typeof(r->'matches'->key) is distinct from 'string' or not exists(select 1 from jsonb_array_elements(cfg->'targets') v where v->>'id'=r->'matches'->>key) then raise exception using errcode='22023',message='assessment_invalid_response';end if;
    if r->'matches'->key=cfg->'correct_pairs'->key then correct:=correct+1;end if;
   end loop;
   -- One target per prompt; incorrect permutations earn deterministic partial points.
   if (select count(distinct value) from jsonb_each_text(r->'matches'))<>n then raise exception using errcode='22023',message='assessment_invalid_response';end if;
   credit:=(q->>'points')::numeric*correct/n;
  end if;
  total:=total+(q->>'points')::numeric;earned:=earned+coalesce(credit,0);
  insert into public.elearning_assessment_answers(tenant_id,attempt_id,question_id,response,earned_points) values(p_tenant_id,t.id,(q->>'id')::uuid,r,credit);
 end loop;
 if coalesce(t.private_snapshot->'assessment'->>'activity_mode','graded')<>'practice' and exists(select 1 from public.elearning_assessment_answers where tenant_id=p_tenant_id and attempt_id=t.id and earned_points is null) then
 update public.elearning_assessment_attempts set status='pending_review',submitted_at=now(),total_points=total where id=t.id;
 return public.elearning_assessment_runtime(p_tenant_id,p_course_id,p_lesson_id,p_block_id,p_user_id);
 end if;
 if t.private_snapshot->'assessment'->>'activity_mode'='practice' then
 update public.elearning_assessment_attempts set status='submitted',submitted_at=now() where id=t.id;
 else
 score:=100*earned/total;
 update public.elearning_assessment_attempts set status='submitted',submitted_at=now(),earned_points=earned,total_points=total,passed=case when t.private_snapshot->'assessment'->>'activity_mode'='practice' then null else score>=(t.private_snapshot->'assessment'->>'passing_score')::numeric end,score_percentage=case when t.private_snapshot->'assessment'->>'activity_mode'='practice' then null else round(score,2) end where id=t.id;
 end if;
 perform public.elearning_finalize_completion(p_tenant_id,p_course_id,t.enrollment_id);
 return public.elearning_assessment_runtime(p_tenant_id,p_course_id,p_lesson_id,p_block_id,p_user_id);
end $$;
create function public.elearning_can_review(p_tenant_id integer,p_actor_id integer,p_course_id uuid,p_student_id integer default null) returns boolean language sql stable security definer set search_path='' as $$
 select p_actor_id is distinct from p_student_id and exists(
 select 1 from public.tenant_memberships m join public.users u on u.id=m.user_id
 where m.tenant_id=p_tenant_id and m.user_id=p_actor_id and m.status='active' and u.account_status='active' and
 (m.role in ('owner','admin') or exists(select 1 from public.elearning_instructors i where i.tenant_id=p_tenant_id and i.user_id=p_actor_id and i.status='active' and
 (exists(select 1 from public.elearning_course_instructors c where c.tenant_id=p_tenant_id and c.course_id=p_course_id and c.instructor_id=i.id)
 or exists(select 1 from public.elearning_group_instructors g join public.elearning_group_courses c on (c.tenant_id,c.group_id)=(g.tenant_id,g.group_id) join public.elearning_groups gr on (gr.tenant_id,gr.id)=(g.tenant_id,g.group_id)
 where g.tenant_id=p_tenant_id and g.instructor_id=i.id and c.course_id=p_course_id and c.removed_at is null and gr.status='active' and
 (p_student_id is null or exists(select 1 from public.elearning_group_members gm where gm.tenant_id=g.tenant_id and gm.group_id=g.group_id and gm.user_id=p_student_id and gm.removed_at is null)))))));
$$;
create function public.get_elearning_pending_reviews(p_tenant_id integer,p_actor_id integer,p_limit integer default 50,p_offset integer default 0) returns jsonb language plpgsql stable security definer set search_path='' as $$
begin
 if p_limit is null or p_limit not between 1 and 100 or p_offset<0 or p_offset>100000 then raise exception using errcode='22023',message='assessment_invalid_pagination';end if;
 return (select coalesce(jsonb_agg(jsonb_build_object('id',t.id,'course_id',t.course_id,'title',t.private_snapshot->'assessment'->>'title','student_id',t.user_id,'student_name',(select l.name from public.elearning_enrollments e join public.elearning_learners l on (l.tenant_id,l.id)=(e.tenant_id,e.learner_id) where e.tenant_id=t.tenant_id and e.id=t.enrollment_id),'submitted_at',t.submitted_at,'review_revision',t.review_revision) order by t.submitted_at,t.id),'[]') from
 (select * from public.elearning_assessment_attempts a where a.tenant_id=p_tenant_id and a.status='pending_review' and public.elearning_can_review(p_tenant_id,p_actor_id,a.course_id,a.user_id) order by a.submitted_at,a.id limit p_limit offset p_offset) t);
end $$;
create function public.get_elearning_review(p_tenant_id integer,p_actor_id integer,p_attempt_id uuid) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare t public.elearning_assessment_attempts%rowtype;begin
 select * into t from public.elearning_assessment_attempts where tenant_id=p_tenant_id and id=p_attempt_id;
 if not found or t.status='in_progress' or coalesce(t.private_snapshot->'assessment'->>'activity_mode','graded')='practice' or not public.elearning_can_review(p_tenant_id,p_actor_id,t.course_id,t.user_id) then raise exception using errcode='42501',message='assessment_review_forbidden';end if;
 return jsonb_build_object('id',t.id,'status',t.status,'course_id',t.course_id,'student_id',t.user_id,'student_name',(select l.name from public.elearning_enrollments e join public.elearning_learners l on (l.tenant_id,l.id)=(e.tenant_id,e.learner_id) where e.tenant_id=t.tenant_id and e.id=t.enrollment_id),'review_revision',t.review_revision,'snapshot',t.private_snapshot,
 'answers',(select coalesce(jsonb_agg(jsonb_build_object('question_id',a.question_id,'response',a.response,'earned_points',a.earned_points,'review',(select to_jsonb(r) from public.elearning_assessment_reviews r where r.tenant_id=p_tenant_id and r.attempt_id=t.id and r.question_id=a.question_id))),'[]') from public.elearning_assessment_answers a where a.tenant_id=p_tenant_id and a.attempt_id=t.id));
end $$;
create function public.review_elearning_answer(p_tenant_id integer,p_actor_id integer,p_attempt_id uuid,p_question_id uuid,p_expected_revision integer,p_points numeric,p_feedback text) returns jsonb language plpgsql security definer set search_path='' as $$
declare t public.elearning_assessment_attempts%rowtype;q jsonb;prior public.elearning_assessment_reviews%rowtype;earned numeric;begin
 perform pg_advisory_xact_lock(125,p_tenant_id);
 select * into t from public.elearning_assessment_attempts where tenant_id=p_tenant_id and id=p_attempt_id for update;
 if not found then raise exception using errcode='42501',message='assessment_review_forbidden';end if;
 -- Serialize status/role revocation even when directory lifecycle updates do not take the assignment advisory lock.
 perform 1 from public.tenant_memberships where tenant_id=p_tenant_id and user_id=p_actor_id for share;
 perform 1 from public.users where id=p_actor_id for share;
 perform 1 from public.elearning_instructors where tenant_id=p_tenant_id and user_id=p_actor_id for share;
 perform 1 from public.elearning_groups g join public.elearning_group_instructors a on (a.tenant_id,a.group_id)=(g.tenant_id,g.id) join public.elearning_instructors i on (i.tenant_id,i.id)=(a.tenant_id,a.instructor_id) where i.tenant_id=p_tenant_id and i.user_id=p_actor_id for share of g;
 if not public.elearning_can_review(p_tenant_id,p_actor_id,t.course_id,t.user_id) then raise exception using errcode='42501',message='assessment_review_forbidden';end if;
 select * into prior from public.elearning_assessment_reviews where tenant_id=p_tenant_id and attempt_id=t.id and question_id=p_question_id;
 if found then
 if prior.reviewer_id=p_actor_id and prior.points=p_points and prior.feedback=p_feedback then return public.get_elearning_review(p_tenant_id,p_actor_id,t.id);end if;
 raise exception using errcode='P0001',message='assessment_review_conflict';end if;
 if t.status<>'pending_review' or t.review_revision is distinct from p_expected_revision then raise exception using errcode='P0001',message='assessment_review_conflict';end if;
 select v into q from jsonb_array_elements(t.private_snapshot->'questions') v where v->>'id'=p_question_id::text;
 if q is null or q->>'type' not in ('written','speaking') or p_points is null or p_points<0 or p_points>(q->>'points')::numeric or p_points<>round(p_points,2) or p_feedback is null or char_length(p_feedback)>10000 then raise exception using errcode='22023',message='assessment_invalid_review';end if;
 insert into public.elearning_assessment_reviews(tenant_id,attempt_id,question_id,reviewer_id,points,feedback) values(p_tenant_id,t.id,p_question_id,p_actor_id,p_points,p_feedback);
 update public.elearning_assessment_answers set earned_points=p_points where tenant_id=p_tenant_id and attempt_id=t.id and question_id=p_question_id and earned_points is null;
 if not found then raise exception using errcode='P0001',message='assessment_review_conflict';end if;
 update public.elearning_assessment_attempts set review_revision=review_revision+1 where id=t.id;
 if not exists(select 1 from public.elearning_assessment_answers where tenant_id=p_tenant_id and attempt_id=t.id and earned_points is null) then
 select sum(earned_points) into earned from public.elearning_assessment_answers where tenant_id=p_tenant_id and attempt_id=t.id;
 update public.elearning_assessment_attempts set status='submitted',earned_points=earned,score_percentage=round(100*earned/t.total_points,2),passed=100*earned/t.total_points>=(t.private_snapshot->'assessment'->>'passing_score')::numeric where id=t.id;
 if public.elearning_enrollment_has_access(p_tenant_id,t.enrollment_id) then perform public.elearning_finalize_completion(p_tenant_id,t.course_id,t.enrollment_id);end if;
 end if;
 return public.get_elearning_review(p_tenant_id,p_actor_id,t.id);
end $$;
create function public.register_elearning_recording(p_tenant_id integer,p_user_id integer,p_attempt_id uuid,p_question_id uuid,p_id uuid,p_size integer,p_duration integer,p_sha256 text) returns jsonb language plpgsql security definer set search_path='' as $$
declare t public.elearning_assessment_attempts%rowtype;q jsonb;key text;begin
 perform pg_advisory_xact_lock(125,p_tenant_id);
 select * into t from public.elearning_assessment_attempts where tenant_id=p_tenant_id and id=p_attempt_id and user_id=p_user_id for update;
 if not found or t.status<>'in_progress' or not public.elearning_enrollment_has_access(p_tenant_id,t.enrollment_id) then raise exception using errcode='42501',message='assessment_recording_forbidden';end if;
 perform public.elearning_assert_placement_eligible(p_tenant_id,p_user_id,t.course_id,t.placement_id);
 select v into q from jsonb_array_elements(t.private_snapshot->'questions') v where v->>'id'=p_question_id::text and v->>'type'='speaking';
 if exists(select 1 from public.elearning_recording_cleanup where tenant_id=p_tenant_id and recording_id=p_id) then raise exception using errcode='42501',message='assessment_recording_expired';end if;
 if q is null or p_size>(q->'config'->>'max_size_bytes')::integer or p_duration>(q->'config'->>'max_duration_seconds')::integer*1000 then raise exception using errcode='22023',message='assessment_recording_limits';end if;
 key:='elearning-assessments/tenant_'||p_tenant_id||'/attempt_'||t.id||'/'||p_id||'.wav';
 if exists(select 1 from public.elearning_assessment_recordings where tenant_id=p_tenant_id and id=p_id) then
 if not exists(select 1 from public.elearning_assessment_recordings where tenant_id=p_tenant_id and id=p_id and attempt_id=t.id and question_id=p_question_id and sha256=p_sha256 and size_bytes=p_size and duration_ms=p_duration) then raise exception using errcode='P0001',message='assessment_recording_conflict';end if;
 else
 if (select count(*) from public.elearning_assessment_recordings where tenant_id=p_tenant_id and attempt_id=t.id and question_id=p_question_id)>=5 then raise exception using errcode='42501',message='assessment_recording_limit';end if;
 key:='elearning-assessments/tenant_'||p_tenant_id||'/attempt_'||t.id||'/'||p_id||'.wav';
 insert into public.elearning_assessment_recordings(id,tenant_id,attempt_id,question_id,storage_key,sha256,size_bytes,duration_ms,mime_type) values(p_id,p_tenant_id,t.id,p_question_id,key,p_sha256,p_size,p_duration,'audio/wav');
 end if;
 return jsonb_build_object('id',p_id,'storage_key',key);
end $$;
create function public.get_elearning_recording(p_tenant_id integer,p_user_id integer,p_id uuid) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare t public.elearning_assessment_attempts%rowtype;r public.elearning_assessment_recordings%rowtype;begin
 select * into r from public.elearning_assessment_recordings where tenant_id=p_tenant_id and id=p_id;
 if not found then raise exception using errcode='P0002',message='assessment_recording_not_found';end if;
 select * into t from public.elearning_assessment_attempts where tenant_id=p_tenant_id and id=r.attempt_id;
 if not (t.user_id=p_user_id and public.elearning_enrollment_has_access(p_tenant_id,t.enrollment_id)) and not (t.status in ('pending_review','submitted') and exists(select 1 from public.elearning_assessment_answers a where a.tenant_id=r.tenant_id and a.attempt_id=t.id and a.response->>'recording_id'=r.id::text) and public.elearning_can_review(p_tenant_id,p_user_id,t.course_id,t.user_id)) then raise exception using errcode='42501',message='assessment_recording_forbidden';end if;
 return to_jsonb(r);
end $$;

create or replace function public.elearning_safe_question(p_tenant_id integer,p_question jsonb) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare cfg jsonb:=p_question->'config'; prompts jsonb; targets jsonb; typ text:=p_question->>'type';begin
 if typ in ('speaking','written','speaking_practice') then
  cfg:=cfg-'media_id'||jsonb_build_object('media',case when cfg->>'media_id' is null then null else (select jsonb_build_object('id',id,'url','/uploads/'||storage_key,'mime_type',mime_type) from public.builder_assets where tenant_id=p_tenant_id and id=(cfg->>'media_id')::uuid and status in ('active','unreferenced')) end);
 elsif typ='picture_listen' then
  cfg:=jsonb_build_object('media',(select jsonb_build_object('id',id,'url','/uploads/'||storage_key,'mime_type',mime_type) from public.builder_assets where tenant_id=p_tenant_id and id=(cfg->>'media_id')::uuid and status in ('active','unreferenced')),
  'options',(select jsonb_agg(jsonb_build_object('id',v->'id','alt',v->'alt','media',(select jsonb_build_object('id',id,'url','/uploads/'||storage_key,'mime_type',mime_type) from public.builder_assets where tenant_id=p_tenant_id and id=(v->>'media_id')::uuid and status in ('active','unreferenced'))) order by ord) from jsonb_array_elements(cfg->'options') with ordinality x(v,ord)));
 elsif typ='multiple_choice' then cfg:=jsonb_build_object('options',cfg->'options');
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
 return jsonb_build_object('id',p_question->>'id','type',typ,'prompt',p_question->>'prompt','points',case when typ='speaking_practice' then null else p_question->'points' end,'config',cfg);
end $$;
create or replace function public.elearning_assessment_summary(p_tenant_id integer,p_assessment_id uuid) returns jsonb language sql stable security definer set search_path='' as $$
 select jsonb_build_object('id',a.id,'title',a.title,'instructions',a.instructions,'status',a.status,'passing_score',a.passing_score,'max_attempts',a.max_attempts,'revision',a.revision,'activity_mode',a.activity_mode,'pool_size',a.pool_size,'shuffle_questions',a.shuffle_questions,'shuffle_options',a.shuffle_options,'practice_feedback',a.practice_feedback,'question_count',(select count(*) from public.elearning_assessment_questions q where q.tenant_id=a.tenant_id and q.assessment_id=a.id and q.archived_at is null))
 from public.elearning_assessments a where a.tenant_id=p_tenant_id and a.id=p_assessment_id;
$$;
create or replace function public.validate_elearning_assessment_publish(p_tenant_id integer,p_assessment_id uuid) returns void language plpgsql security definer set search_path='' as $$
declare q record; n integer:=0;begin
 for q in select * from public.elearning_assessment_questions where tenant_id=p_tenant_id and assessment_id=p_assessment_id and archived_at is null loop
 n:=n+1;perform public.validate_elearning_assessment_question(p_tenant_id,jsonb_build_object('type',q.type,'prompt',q.prompt,'points',q.points,'config',q.config));end loop;
 if exists(select 1 from public.elearning_assessments where tenant_id=p_tenant_id and id=p_assessment_id and pool_size>n) then raise exception using errcode='22023',message='assessment_pool_too_small';end if;
 if exists(select 1 from public.elearning_assessments a join public.elearning_assessment_questions bankq on (bankq.tenant_id,bankq.assessment_id)=(a.tenant_id,a.id) where a.tenant_id=p_tenant_id and a.id=p_assessment_id and bankq.archived_at is null and ((a.activity_mode='practice' and bankq.type in ('speaking','written')) or (a.activity_mode='graded' and bankq.type='speaking_practice'))) then raise exception using errcode='22023',message='assessment_invalid_mode';end if;
 if exists(select 1 from public.elearning_assessments a join public.elearning_assessment_placements p on (p.tenant_id,p.assessment_id)=(a.tenant_id,a.id) where a.tenant_id=p_tenant_id and a.id=p_assessment_id and a.activity_mode='practice' and p.placement_type<>'lesson' and p.archived_at is null) then raise exception using errcode='22023',message='assessment_practice_requires_lesson';end if;
 if n=0 then raise exception using errcode='22023',message='assessment_questions_required';end if;
end $$;
create function public.elearning_question_media_ids(p_question jsonb) returns setof uuid language sql immutable set search_path='' as $$
 select (v->>'media_id')::uuid from (
 select p_question->'config' v
 union all select value from jsonb_array_elements(coalesce(p_question->'config'->'options','[]'))
 union all select value from jsonb_array_elements(coalesce(p_question->'config'->'prompts','[]'))) refs where v->>'media_id' is not null;
$$;
create or replace function public.elearning_question_media_refs() returns trigger language plpgsql security definer set search_path='' as $$
begin
 delete from public.elearning_assessment_media_refs where tenant_id=new.tenant_id and question_id=new.id;
 insert into public.elearning_assessment_media_refs(tenant_id,assessment_id,question_id,media_id)
 select new.tenant_id,new.assessment_id,new.id,id from public.elearning_question_media_ids(jsonb_build_object('config',new.config)) id;
 return new;
end $$;
create function public.elearning_snapshot_media_refs143() returns trigger language plpgsql security definer set search_path='' as $$
begin
 insert into public.elearning_assessment_media_refs(tenant_id,assessment_id,attempt_id,media_id)
 select new.tenant_id,new.assessment_id,new.id,id from jsonb_array_elements(new.private_snapshot->'questions') q cross join lateral public.elearning_question_media_ids(q) id;
 return new;
end $$;
create trigger elearning_snapshot_media143 after insert on public.elearning_assessment_attempts for each row execute function public.elearning_snapshot_media_refs143();

create function public.get_elearning_recording_admission(p_tenant_id integer,p_user_id integer,p_attempt_id uuid,p_question_id uuid,p_id uuid) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare t public.elearning_assessment_attempts%rowtype;q jsonb;r public.elearning_assessment_recordings%rowtype;begin
 select * into t from public.elearning_assessment_attempts where tenant_id=p_tenant_id and id=p_attempt_id and user_id=p_user_id;
 if not found or not public.elearning_enrollment_has_access(p_tenant_id,t.enrollment_id) then raise exception using errcode='42501',message='assessment_recording_forbidden';end if;
 perform public.elearning_assert_placement_eligible(p_tenant_id,p_user_id,t.course_id,t.placement_id);
 select v into q from jsonb_array_elements(t.private_snapshot->'questions') v where v->>'id'=p_question_id::text and v->>'type'='speaking';
 if q is null then raise exception using errcode='42501',message='assessment_recording_forbidden';end if;
 select * into r from public.elearning_assessment_recordings where tenant_id=p_tenant_id and id=p_id and attempt_id=t.id and question_id=p_question_id;
 if exists(select 1 from public.elearning_recording_cleanup where tenant_id=p_tenant_id and recording_id=p_id) then raise exception using errcode='42501',message='assessment_recording_expired';end if;
 if r.id is null and (select count(*) from public.elearning_assessment_recordings where tenant_id=p_tenant_id and attempt_id=t.id and question_id=p_question_id)>=5 then raise exception using errcode='42501',message='assessment_recording_limit';end if;
 if t.status<>'in_progress' and r.id is null then raise exception using errcode='42501',message='assessment_recording_forbidden';end if;
 return jsonb_build_object('config',q->'config','existing',case when r.id is null then null else to_jsonb(r) end,'storage_key','elearning-assessments/tenant_'||p_tenant_id||'/attempt_'||t.id||'/'||p_id||'.wav');
end $$;

do $$ declare f record;begin
 for f in select p.oid::regprocedure signature from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname in ('elearning_can_review','get_elearning_pending_reviews','get_elearning_review','review_elearning_answer','register_elearning_recording','get_elearning_recording','get_elearning_recording_admission','elearning_question_media_ids','elearning_snapshot_media_refs143') loop
 execute format('revoke all on function %s from public,anon,authenticated,service_role',f.signature);
 if f.signature::text like '%get_elearning_%' or f.signature::text like '%review_elearning_answer%' or f.signature::text like '%register_elearning_recording%' then execute format('grant execute on function %s to service_role',f.signature);end if;
 end loop;
end $$;
create or replace function public.clone_elearning_assessment(p_tenant_id integer,p_source uuid,p_actor integer) returns uuid language plpgsql security definer set search_path='' as $$
declare aid uuid;begin
 insert into public.elearning_assessments(tenant_id,title,instructions,passing_score,max_attempts,activity_mode,pool_size,shuffle_questions,shuffle_options,practice_feedback,created_by)
 select tenant_id,title,instructions,passing_score,max_attempts,activity_mode,pool_size,shuffle_questions,shuffle_options,practice_feedback,p_actor from public.elearning_assessments where tenant_id=p_tenant_id and id=p_source returning id into aid;
 if aid is null then raise exception using errcode='P0002',message='assessment_not_found';end if;
 insert into public.elearning_assessment_questions(tenant_id,assessment_id,type,prompt,points,position,config,archived_at)
 select tenant_id,aid,type,prompt,points,position,config,archived_at from public.elearning_assessment_questions where tenant_id=p_tenant_id and assessment_id=p_source order by position;
 return aid;
end $$;
create or replace function public.elearning_required_assessments(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_enrollment_id uuid) returns jsonb language sql stable security definer set search_path='' as $$
 select coalesce(jsonb_agg(jsonb_build_object('id',a.id,'title',a.title,'passed',exists(select 1 from public.elearning_assessment_attempts t where t.tenant_id=p_tenant_id and t.placement_id=p.id and t.enrollment_id=p_enrollment_id and t.status='submitted' and (t.passed or t.private_snapshot->'assessment'->>'activity_mode'='practice'))) order by p.position,p.id),'[]')
 from public.elearning_assessment_placements p join public.elearning_assessments a on a.id=p.assessment_id where p.tenant_id=p_tenant_id and p.course_id=p_course_id and p.lesson_id=p_lesson_id and p.placement_type='lesson' and p.archived_at is null and p.required_for_completion and a.status='published';
$$;
create or replace function public.elearning_assessment_results(p_tenant_id integer,p_enrollment_id uuid) returns jsonb language sql stable security definer set search_path='' as $$
 select coalesce(jsonb_agg(to_jsonb(v) order by v.placement_type,v.title,v.placement_id),'[]') from(
 select a.id assessment_id,p.id placement_id,p.placement_type,p.section_id,a.title,count(t.id) filter(where t.status='submitted') attempts,max(t.score_percentage) filter(where t.status='submitted') best_score,coalesce(bool_or(t.passed) filter(where t.status='submitted'),false) passed,max(t.submitted_at) last_attempt
 from public.elearning_assessment_placements p join public.elearning_assessments a on a.id=p.assessment_id join public.elearning_assessment_attempts t on t.placement_id=p.id
 where t.tenant_id=p_tenant_id and t.enrollment_id=p_enrollment_id and coalesce(t.private_snapshot->'assessment'->>'activity_mode','graded')='graded' group by a.id,p.id,p.placement_type,p.section_id,a.title) v;
$$;
create function public.learning_assessment_notification143() returns trigger language plpgsql security definer set search_path='' as $$
declare actor integer;mode text:=coalesce(new.private_snapshot->'assessment'->>'activity_mode','graded');begin
 if mode='practice' or new.status is not distinct from old.status then return new;end if;
 if old.status='in_progress' and new.status in ('pending_review','submitted') then
 perform public.enqueue_learning_notification(new.tenant_id,new.user_id,'learning_exam_submitted','elearning_assessment_attempts',new.id::text,'Exam submitted','/my-learning/courses/'||new.course_id);
 end if;
 if new.status='pending_review' then
 perform public.enqueue_learning_notification(new.tenant_id,new.user_id,'learning_exam_pending_review','elearning_assessment_attempts',new.id::text,'Your exam is awaiting review','/my-learning/courses/'||new.course_id);
 for actor in select user_id from public.tenant_memberships where tenant_id=new.tenant_id and status='active' and public.elearning_can_review(new.tenant_id,user_id,new.course_id,new.user_id) loop
 perform public.enqueue_learning_notification(new.tenant_id,actor,'learning_review_requested','elearning_assessment_attempts',new.id::text,'An exam is ready for your review','/my-learning/assessment-reviews/'||new.id);
 end loop;
 elsif new.status='submitted' then
 perform public.enqueue_learning_notification(new.tenant_id,new.user_id,'learning_exam_result','elearning_assessment_attempts',new.id::text,'Your exam result is available','/my-learning/courses/'||new.course_id);
 end if;return new;
end $$;
drop trigger learning_notification on public.elearning_assessment_attempts;
create trigger learning_notification after update of status on public.elearning_assessment_attempts for each row execute function public.learning_assessment_notification143();
revoke all on function public.learning_assessment_notification143() from public,anon,authenticated,service_role;

-- Reviewer visibility uses the same course/group assignment authority as grading.
create function public.get_elearning_assessment_capabilities(p_tenant_id integer,p_actor_id integer) returns jsonb language sql stable security definer set search_path='' as $$
 select jsonb_build_object('available',true,'can_review',exists(select 1 from public.elearning_courses c where c.tenant_id=p_tenant_id and public.elearning_can_review(p_tenant_id,p_actor_id,c.id)));
$$;
revoke all on function public.get_elearning_assessment_capabilities(integer,integer) from public,anon,authenticated;
grant execute on function public.get_elearning_assessment_capabilities(integer,integer) to service_role;

-- Durable deletion fencing: queued objects can never subsequently become answers.
-- Selected recordings remain assessment evidence, irrespective of age or grading state.
create table public.elearning_recording_cleanup (
 tenant_id integer not null references public.tenants(tenant_id),storage_key text not null,
 recording_id uuid not null,created_at timestamptz not null default now(),completed_at timestamptz,
 primary key(tenant_id,storage_key));
alter table public.elearning_recording_cleanup enable row level security;
revoke all on public.elearning_recording_cleanup from public,anon,authenticated,service_role;
create function public.prepare_elearning_recording_cleanup(p_limit integer default 100,p_apply boolean default false) returns jsonb language plpgsql security definer set search_path='' as $$
declare candidate record;items jsonb:='[]';begin
 if p_limit is null or p_limit not between 1 and 500 then raise exception using errcode='22023',message='assessment_invalid_pagination';end if;
 for candidate in select o.tenant_id,o.storage_key,o.sha256,substring(o.storage_key from '/([0-9a-f-]{36})[.]wav$')::uuid recording_id
 from public.storage_objects o left join public.elearning_recording_cleanup d on (d.tenant_id,d.storage_key)=(o.tenant_id,o.storage_key)
 where o.category='elearning_assessment' and o.status='active' and o.created_at<now()-interval '24 hours'
 and o.storage_key ~ ('^elearning-assessments/tenant_'||o.tenant_id||'/attempt_[0-9a-f-]{36}/[0-9a-f-]{36}[.]wav$')
 and (d.completed_at is null) and not exists(select 1 from public.elearning_assessment_recordings r join public.elearning_assessment_attempts t on (t.tenant_id,t.id)=(r.tenant_id,r.attempt_id)
 where r.tenant_id=o.tenant_id and r.storage_key=o.storage_key and (t.status='in_progress' or exists(select 1 from public.elearning_assessment_answers a where a.tenant_id=r.tenant_id and a.attempt_id=r.attempt_id and a.response->>'recording_id'=r.id::text)))
 order by o.created_at,o.id limit p_limit loop
 perform pg_advisory_xact_lock(125,candidate.tenant_id);
 -- Recheck after the same lock used by recording registration/submission.
 if exists(select 1 from public.elearning_assessment_recordings r join public.elearning_assessment_attempts t on (t.tenant_id,t.id)=(r.tenant_id,r.attempt_id) where r.tenant_id=candidate.tenant_id and r.storage_key=candidate.storage_key and (t.status='in_progress' or exists(select 1 from public.elearning_assessment_answers a where a.tenant_id=r.tenant_id and a.attempt_id=r.attempt_id and a.response->>'recording_id'=r.id::text))) then continue;end if;
 if p_apply then insert into public.elearning_recording_cleanup(tenant_id,storage_key,recording_id) values(candidate.tenant_id,candidate.storage_key,candidate.recording_id) on conflict do nothing;end if;
 items:=items||jsonb_build_array(to_jsonb(candidate));
 end loop;return items;
end $$;
create function public.finish_elearning_recording_cleanup(p_tenant_id integer,p_storage_key text) returns void language plpgsql security definer set search_path='' as $$
begin
 perform pg_advisory_xact_lock(125,p_tenant_id);
 if not exists(select 1 from public.elearning_recording_cleanup where tenant_id=p_tenant_id and storage_key=p_storage_key and completed_at is null) then return;end if;
 if exists(select 1 from public.elearning_assessment_recordings r join public.elearning_assessment_answers a on a.tenant_id=r.tenant_id and a.attempt_id=r.attempt_id and a.response->>'recording_id'=r.id::text where r.tenant_id=p_tenant_id and r.storage_key=p_storage_key) then raise exception using errcode='42501',message='assessment_evidence_protected';end if;
 delete from public.elearning_assessment_recordings where tenant_id=p_tenant_id and storage_key=p_storage_key;
 perform public.release_storage_object(p_tenant_id,'elearning_assessment',p_storage_key);
 update public.elearning_recording_cleanup set completed_at=now() where tenant_id=p_tenant_id and storage_key=p_storage_key;
end $$;
revoke all on function public.prepare_elearning_recording_cleanup(integer,boolean),public.finish_elearning_recording_cleanup(integer,text) from public,anon,authenticated;
grant execute on function public.prepare_elearning_recording_cleanup(integer,boolean),public.finish_elearning_recording_cleanup(integer,text) to service_role;

create or replace function public.configure_elearning_cefr(p_tenant integer,p_admin integer,p_course uuid,p_section uuid,p_level text,p_template uuid,p_enabled boolean)
returns void language plpgsql security definer set search_path='' as $$ begin
 perform public.commerce_assert_member(p_tenant,p_admin,true);
 perform pg_advisory_xact_lock(125,p_tenant);
 if p_enabled and not exists(select 1 from public.elearning_assessment_placements p join public.elearning_assessments a on(a.tenant_id,a.id)=(p.tenant_id,p.assessment_id) where p.tenant_id=p_tenant and p.course_id=p_course and p.section_id=p_section and p.placement_type='section' and p.required_for_completion and p.archived_at is null and a.status='published' and a.activity_mode='graded') then raise exception using errcode='22023',message='cefr_final_exam_required';end if;
 insert into public.elearning_section_certificates(tenant_id,course_id,section_id,cefr_level,template_id,enabled) values(p_tenant,p_course,p_section,p_level,p_template,p_enabled)
 on conflict(tenant_id,course_id,section_id) do update set cefr_level=excluded.cefr_level,template_id=excluded.template_id,enabled=excluded.enabled;
 insert into public.audit_logs(tenant_id,actor_user_id,action,target_type,target_id,metadata) values(p_tenant,p_admin,'elearning.cefr.configured','elearning_section',p_section::text,jsonb_build_object('course_id',p_course,'cefr_level',p_level,'enabled',p_enabled));
end $$;
-- Author edits cannot rewrite an attempt's frozen evidence or finalized grade.
create function public.elearning_attempt_evidence143() returns trigger language plpgsql set search_path='' as $$
begin
 if (new.id,new.tenant_id,new.assessment_id,new.user_id,new.course_id,new.lesson_id,new.enrollment_id,new.attempt_number,new.started_at,new.private_snapshot) is distinct from
 (old.id,old.tenant_id,old.assessment_id,old.user_id,old.course_id,old.lesson_id,old.enrollment_id,old.attempt_number,old.started_at,old.private_snapshot)
 or (old.status='submitted' and (new.status,new.submitted_at,new.earned_points,new.total_points,new.score_percentage,new.passed,new.review_revision) is distinct from (old.status,old.submitted_at,old.earned_points,old.total_points,old.score_percentage,old.passed,old.review_revision))
 or (old.status='pending_review' and (new.status not in ('pending_review','submitted') or new.submitted_at is distinct from old.submitted_at or new.total_points is distinct from old.total_points)) then
 raise exception using errcode='42501',message='assessment_evidence_immutable';end if;
 return new;
end $$;
create trigger elearning_attempt_evidence143 before update on public.elearning_assessment_attempts for each row execute function public.elearning_attempt_evidence143();
create function public.elearning_answer_evidence143() returns trigger language plpgsql set search_path='' as $$
begin
 if (new.tenant_id,new.attempt_id,new.question_id,new.response) is distinct from (old.tenant_id,old.attempt_id,old.question_id,old.response)
 or old.earned_points is not null then raise exception using errcode='42501',message='assessment_answer_immutable';end if;
 return new;
end $$;
create trigger elearning_answer_evidence143 before update on public.elearning_assessment_answers for each row execute function public.elearning_answer_evidence143();
revoke all on function public.elearning_attempt_evidence143(),public.elearning_answer_evidence143() from public,anon,authenticated,service_role;

notify pgrst,'reload schema';
commit;
