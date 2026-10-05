begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_133_schema_state_missing'; end if;
 if v_schema_version <> 132 then raise exception 'migration_133_expected_schema_132_got_%',v_schema_version; end if;
end $$;

-- Preserve legacy duplicates and their relationships. New names may not collide,
-- including with archived groups. Existing duplicates can be renamed or deleted.
create function public.elearning_group_name_key(p_name text) returns text
language sql immutable set search_path='' as $$
 select lower(btrim(regexp_replace(p_name,'[[:space:]]+',' ','g')));
$$;
create index elearning_group_name_lookup on public.elearning_groups(tenant_id, public.elearning_group_name_key(name));
create function public.guard_elearning_group_name() returns trigger
language plpgsql security definer set search_path='' as $$
begin
 if tg_op='UPDATE' then
  if new.tenant_id=old.tenant_id and public.elearning_group_name_key(new.name)=public.elearning_group_name_key(old.name) then return new; end if;
 end if;
 perform pg_advisory_xact_lock(133,new.tenant_id);
 if exists(select 1 from public.elearning_groups g where g.tenant_id=new.tenant_id and g.id<>new.id
   and public.elearning_group_name_key(g.name)=public.elearning_group_name_key(new.name)) then
  raise exception using errcode='23505',message='elearning_group_name_exists';
 end if;
 return new;
end $$;
create trigger guard_elearning_group_name before insert or update of name,tenant_id on public.elearning_groups
for each row execute function public.guard_elearning_group_name();

create function public.delete_elearning_group(p_tenant_id integer,p_actor_id integer,p_group_id uuid,p_revision integer,p_confirmed boolean)
returns jsonb language plpgsql security definer set search_path='' as $$
declare item public.elearning_groups;
begin
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant_id and user_id=p_actor_id and status='active' and role in ('owner','admin')) then
  raise exception using errcode='42501',message='elearning_group_forbidden';
 end if;
 if p_confirmed is distinct from true then raise exception using errcode='22023',message='elearning_confirmation_required'; end if;
 -- Same lock order as membership/course assignment mutations.
 perform pg_advisory_xact_lock(125,p_tenant_id);
 select * into item from public.elearning_groups where tenant_id=p_tenant_id and id=p_group_id for update;
 if not found then raise exception using errcode='P0002',message='elearning_group_not_found'; end if;
 if p_revision is distinct from item.revision then raise exception using errcode='40001',message='elearning_group_revision_conflict'; end if;
 -- Existing FKs remove only this group's memberships/assignments/access grants.
 -- Enrollments, user identities and completion history remain intact.
 delete from public.elearning_groups where tenant_id=p_tenant_id and id=p_group_id;
 return to_jsonb(item);
end $$;
revoke all on function public.elearning_group_name_key(text),public.guard_elearning_group_name(),public.delete_elearning_group(integer,integer,uuid,integer,boolean) from public,anon,authenticated;
grant execute on function public.elearning_group_name_key(text),public.delete_elearning_group(integer,integer,uuid,integer,boolean) to service_role;
update public.application_schema_state set schema_version=133,applied_at=now() where contract_key = 'core';
commit;
