begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_135_schema_state_missing'; end if;
 if v_schema_version <> 134 then raise exception 'migration_135_expected_schema_134_got_%',v_schema_version; end if;
end $$;

create function public.delete_elearning_instructor(p_tenant_id integer,p_actor_id integer,p_instructor_id uuid,p_revision integer,p_confirmed boolean)
returns jsonb language plpgsql security definer set search_path='' as $$
declare item public.elearning_instructors;
begin
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant_id and user_id=p_actor_id and status='active' and role in ('owner','admin')) then
  raise exception using errcode='42501',message='elearning_instructor_forbidden';
 end if;
 if p_confirmed is distinct from true then raise exception using errcode='22023',message='elearning_confirmation_required'; end if;
 -- Same lock order as membership/course assignment mutations.
 perform pg_advisory_xact_lock(125,p_tenant_id);
 select * into item from public.elearning_instructors where tenant_id=p_tenant_id and id=p_instructor_id for update;
 if not found then raise exception using errcode='P0002',message='elearning_instructor_not_found'; end if;
 if p_revision is distinct from item.revision then raise exception using errcode='40001',message='elearning_instructor_revision_conflict'; end if;
 -- Existing FKs remove only course/group instructor assignments.
 -- Linked users, groups, courses, enrollments and progress remain intact.
 delete from public.elearning_instructors where tenant_id=p_tenant_id and id=p_instructor_id;
 return to_jsonb(item);
end $$;
revoke all on function public.delete_elearning_instructor(integer,integer,uuid,integer,boolean) from public,anon,authenticated;
grant execute on function public.delete_elearning_instructor(integer,integer,uuid,integer,boolean) to service_role;
update public.application_schema_state set schema_version=135,applied_at=now() where contract_key = 'core';
commit;
