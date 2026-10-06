begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_122_schema_state_missing'; end if;
 if v_schema_version <> 121 then raise exception 'migration_122_expected_schema_121_got_%',v_schema_version; end if;
 update public.application_schema_state set schema_version = 122,applied_at=now() where contract_key = 'core';
end;
$$;
create function public.delete_elearning_course(p_tenant_id integer,p_course_id uuid,p_user_id integer,p_expected_revision integer,p_expected_structure_revision integer,p_confirmation_name text,p_confirmed boolean)
returns jsonb language plpgsql security definer set search_path='' as $$
declare c public.elearning_courses%rowtype;
begin
 select * into c from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id for update;
 if not found then raise exception using errcode='P0002',message='elearning_course_not_found'; end if;
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant_id and user_id=p_user_id and role in ('owner','admin') and status='active') then
  raise exception using errcode='42501',message='elearning_course_delete_forbidden'; end if;
 if p_confirmed is distinct from true or p_confirmation_name is distinct from c.name then
  raise exception using errcode='22023',message='elearning_course_delete_confirmation_required'; end if;
 if p_expected_revision is distinct from c.revision or p_expected_structure_revision is distinct from c.structure_revision then
  raise exception using errcode='P0001',message='elearning_course_delete_conflict'; end if;
 -- Delete explicitly so completion history cannot be removed through ordinary
 -- lesson deletion. Learner contact profiles remain tenant-owned and reusable.
 delete from public.elearning_lesson_completions where tenant_id=p_tenant_id and course_id=p_course_id;
 delete from public.elearning_enrollments where tenant_id=p_tenant_id and course_id=p_course_id;
 delete from public.elearning_lessons where tenant_id=p_tenant_id and course_id=p_course_id;
 delete from public.elearning_sections where tenant_id=p_tenant_id and course_id=p_course_id;
 delete from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id;
 return jsonb_build_object('id',p_course_id,'deleted',true);
end;
$$;
revoke all on function public.delete_elearning_course(integer,uuid,integer,integer,integer,text,boolean) from public,anon,authenticated;
grant execute on function public.delete_elearning_course(integer,uuid,integer,integer,integer,text,boolean) to service_role;
notify pgrst,'reload schema';
commit;
