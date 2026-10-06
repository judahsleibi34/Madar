begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_125_schema_state_missing'; end if;
 if v_schema_version <> 124 then raise exception 'migration_125_expected_schema_124_got_%',v_schema_version; end if;
 update public.application_schema_state set schema_version=125,applied_at=now() where contract_key = 'core';
end;
$$;

-- Existing progress RPC is the single calculator. Return only this user's row.
create function public.get_elearning_learner_course(p_tenant_id integer,p_user_id integer,p_course_id uuid,p_lesson_id uuid default null)
returns jsonb language plpgsql stable security definer set search_path='' as $$
declare c public.elearning_courses%rowtype; e uuid; report jsonb; cfg jsonb; sec jsonb; lesson jsonb; sections jsonb:='[]'; lessons jsonb; first_incomplete uuid; previous_incomplete boolean:=false; selected jsonb; blocks jsonb;
begin
 select * into c from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id and status='published';
 if not found then raise exception using errcode='P0002',message='elearning_learning_not_found'; end if;
 select n.id into e from public.elearning_enrollments n
 join public.elearning_learners r on (r.tenant_id,r.id)=(n.tenant_id,n.learner_id)
 join public.tenant_memberships m on m.tenant_id=n.tenant_id and m.user_id=r.user_id and m.status='active'
 join public.users u on u.id=m.user_id and u.account_status='active'
 where n.tenant_id=p_tenant_id and n.course_id=c.id and n.status='active' and r.status='active' and r.user_id=p_user_id;
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

create function public.complete_elearning_learner_lesson(p_tenant_id integer,p_user_id integer,p_course_id uuid,p_lesson_id uuid)
returns jsonb language plpgsql security definer set search_path='' as $$
declare snapshot jsonb;
begin
 -- Serialize against enrollment/status/structure/content changes on this course.
 perform 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id for update;
 snapshot:=public.get_elearning_learner_course(p_tenant_id,p_user_id,p_course_id,p_lesson_id);
 insert into public.elearning_lesson_completions(tenant_id,course_id,enrollment_id,lesson_id,recorded_by)
 values(p_tenant_id,p_course_id,(snapshot->'progress'->>'id')::uuid,p_lesson_id,p_user_id) on conflict do nothing;
 return public.get_elearning_learner_course(p_tenant_id,p_user_id,p_course_id,p_lesson_id);
end;
$$;

create function public.get_elearning_my_learning(p_tenant_id integer,p_user_id integer,p_limit integer default 50,p_offset integer default 0)
returns jsonb language sql stable security definer set search_path='' as $$
 select coalesce(jsonb_agg(public.get_elearning_learner_course(p_tenant_id,p_user_id,id) order by name,id),'[]') from (
 select c.id,c.name from public.elearning_courses c
 join public.elearning_enrollments n on (n.tenant_id,n.course_id)=(c.tenant_id,c.id) and n.status='active'
 join public.elearning_learners r on (r.tenant_id,r.id)=(n.tenant_id,n.learner_id) and r.status='active' and r.user_id=p_user_id
 join public.tenant_memberships m on m.tenant_id=c.tenant_id and m.user_id=r.user_id and m.status='active'
 join public.users u on u.id=m.user_id and u.account_status='active'
 where c.tenant_id=p_tenant_id and c.status='published'
 order by c.name,c.id limit least(greatest(p_limit,1),101) offset greatest(p_offset,0)) courses;
$$;

-- Null preserves normal non-learning media rules. Learning attachments additionally
-- require an enrollment and an eligible, unlocked lesson; admin preview remains.
create function public.elearning_learner_media_access(p_tenant_id integer,p_user_id integer,p_storage_key text)
returns boolean language plpgsql stable security definer set search_path='' as $$
declare a public.builder_assets%rowtype; ref record; snapshot jsonb;
begin
 select * into a from public.builder_assets where tenant_id=p_tenant_id and storage_key=p_storage_key;
 if not found then return false; end if;
 if coalesce(a.metadata->>'usage','')<>'elearning_content' and not exists(select 1 from public.elearning_content_blocks where tenant_id=p_tenant_id and media_id=a.id) then return null; end if;
 if exists(select 1 from public.tenant_memberships m join public.users u on u.id=m.user_id and u.account_status='active' where m.tenant_id=p_tenant_id and m.user_id=p_user_id and m.status='active' and m.role in ('owner','admin')) then return true; end if;
 for ref in select distinct course_id,lesson_id from public.elearning_content_blocks where tenant_id=p_tenant_id and media_id=a.id and archived_at is null loop
  begin
   snapshot:=public.get_elearning_learner_course(p_tenant_id,p_user_id,ref.course_id,ref.lesson_id);
   return true;
  exception when no_data_found or insufficient_privilege then null;
  end;
 end loop;
 return false;
end;
$$;
revoke all on function public.get_elearning_learner_course(integer,integer,uuid,uuid),public.complete_elearning_learner_lesson(integer,integer,uuid,uuid),public.get_elearning_my_learning(integer,integer,integer,integer),public.elearning_learner_media_access(integer,integer,text) from public,anon,authenticated;
grant execute on function public.get_elearning_learner_course(integer,integer,uuid,uuid),public.complete_elearning_learner_lesson(integer,integer,uuid,uuid),public.get_elearning_my_learning(integer,integer,integer,integer),public.elearning_learner_media_access(integer,integer,text) to service_role;
notify pgrst,'reload schema';
commit;
