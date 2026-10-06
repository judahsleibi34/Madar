begin;

do $$
declare
  v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version into v_schema_version from public.application_schema_state
  where contract_key = 'core' for update;
  if v_schema_version is null then
    raise exception 'migration_120_schema_state_missing';
  end if;
  if v_schema_version <> 119 then
    raise exception 'migration_120_expected_schema_119_got_%', v_schema_version;
  end if;
  update public.application_schema_state set schema_version = 120, applied_at = now()
  where contract_key = 'core';
end;
$$;

alter table public.elearning_courses add column structure_revision integer not null default 1 check (structure_revision > 0);

create table public.elearning_sections (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null,
  course_id uuid not null,
  name text not null check (char_length(btrim(name)) between 1 and 120),
  description text not null default '' check (char_length(description) <= 4000),
  status text not null default 'draft' check (status in ('draft','published','archived')),
  position integer not null check (position >= 0),
  created_by integer references public.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  archived_at timestamptz,
  foreign key (tenant_id, course_id) references public.elearning_courses(tenant_id,id) on delete cascade,
  unique (tenant_id,course_id,id),
  unique (tenant_id,course_id,position) deferrable initially deferred,
  check ((status = 'archived') = (archived_at is not null))
);
create table public.elearning_lessons (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null,
  course_id uuid not null,
  section_id uuid not null,
  name text not null check (char_length(btrim(name)) between 1 and 120),
  description text not null default '' check (char_length(description) <= 4000),
  status text not null default 'draft' check (status in ('draft','published','archived')),
  position integer not null check (position >= 0),
  created_by integer references public.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  archived_at timestamptz,
  foreign key (tenant_id,course_id,section_id) references public.elearning_sections(tenant_id,course_id,id) on delete cascade,
  unique (tenant_id,course_id,id),
  unique (tenant_id,course_id,section_id,position) deferrable initially deferred,
  check ((status = 'archived') = (archived_at is not null))
);
create trigger set_elearning_sections_updated_at before update on public.elearning_sections
for each row execute function public.set_updated_at();
create trigger set_elearning_lessons_updated_at before update on public.elearning_lessons
for each row execute function public.set_updated_at();
alter table public.elearning_sections enable row level security;
alter table public.elearning_lessons enable row level security;
-- Mutations go exclusively through the serializing, revision-checked RPC below.
revoke all on public.elearning_sections, public.elearning_lessons from public, anon, authenticated, service_role;
grant select on public.elearning_sections, public.elearning_lessons to service_role;

create function public.get_elearning_structure(p_tenant_id integer, p_course_id uuid)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  result jsonb;
begin
  select jsonb_build_object(
    'available', true, 'revision', c.structure_revision,
    'sections', coalesce((select jsonb_agg(to_jsonb(s) || jsonb_build_object(
      'lessons', coalesce((select jsonb_agg(to_jsonb(l) order by l.position,l.id)
        from public.elearning_lessons l where l.tenant_id = p_tenant_id and l.course_id = c.id and l.section_id = s.id), '[]'::jsonb)
    ) order by s.position,s.id) from public.elearning_sections s where s.tenant_id = p_tenant_id and s.course_id = c.id), '[]'::jsonb),
    'section_count', (select count(*) from public.elearning_sections s where s.tenant_id = p_tenant_id and s.course_id = c.id and s.status <> 'archived'),
    'lesson_count', (select count(*) from public.elearning_lessons l join public.elearning_sections s on (s.tenant_id,s.course_id,s.id) = (l.tenant_id,l.course_id,l.section_id) where l.tenant_id = p_tenant_id and l.course_id = c.id and l.status <> 'archived' and s.status <> 'archived'),
    'published_count', (select count(*) from public.elearning_lessons l join public.elearning_sections s on (s.tenant_id,s.course_id,s.id) = (l.tenant_id,l.course_id,l.section_id) where l.tenant_id = p_tenant_id and l.course_id = c.id and l.status = 'published' and s.status <> 'archived'),
    'draft_count', (select count(*) from public.elearning_lessons l join public.elearning_sections s on (s.tenant_id,s.course_id,s.id) = (l.tenant_id,l.course_id,l.section_id) where l.tenant_id = p_tenant_id and l.course_id = c.id and l.status = 'draft' and s.status <> 'archived')
  ) into result from public.elearning_courses c where c.tenant_id = p_tenant_id and c.id = p_course_id;
  if result is null then raise exception using errcode = 'P0002', message = 'elearning_structure_not_found'; end if;
  return result;
end;
$$;

create function public.get_elearning_course_counts(p_tenant_id integer, p_course_ids uuid[])
returns jsonb language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_object_agg(c.id, jsonb_build_object(
    'section_count', (select count(*) from public.elearning_sections s where s.tenant_id = p_tenant_id and s.course_id = c.id and s.status <> 'archived'),
    'lesson_count', (select count(*) from public.elearning_lessons l join public.elearning_sections s on (s.tenant_id,s.course_id,s.id) = (l.tenant_id,l.course_id,l.section_id) where l.tenant_id = p_tenant_id and l.course_id = c.id and l.status <> 'archived' and s.status <> 'archived')
  )), '{}'::jsonb) from public.elearning_courses c where c.tenant_id = p_tenant_id and c.id = any(p_course_ids);
$$;

create function public.manage_elearning_structure(
  p_tenant_id integer, p_course_id uuid, p_user_id integer,
  p_expected_revision integer, p_action text, p_entity_id uuid default null,
  p_payload jsonb default '{}'::jsonb
) returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  course_row public.elearning_courses%rowtype;
  section_row public.elearning_sections%rowtype;
  lesson_row public.elearning_lessons%rowtype;
  destination uuid;
  new_id uuid;
  swap_id uuid;
  next_position integer;
  details_status text;
begin
  select * into course_row from public.elearning_courses where tenant_id = p_tenant_id and id = p_course_id for update;
  if not found then raise exception using errcode = 'P0002', message = 'elearning_structure_not_found'; end if;
  if p_expected_revision is null or p_expected_revision <> course_row.structure_revision then
    raise exception using errcode = 'P0001', message = 'elearning_structure_conflict';
  end if;
  if not exists (select 1 from public.tenant_memberships where tenant_id = p_tenant_id and user_id = p_user_id and role in ('owner','admin') and status = 'active') then
    raise exception using errcode = '42501', message = 'elearning_structure_forbidden';
  end if;
  if p_action is null or p_action not in ('create_section','update_section','duplicate_section','archive_section','delete_section','reorder_section','create_lesson','update_lesson','duplicate_lesson','archive_lesson','delete_lesson','reorder_lesson','move_lesson') then
    raise exception using errcode = '22023', message = 'elearning_structure_invalid_action';
  end if;

  if p_action like '%section' and p_action <> 'create_section' then
    select * into section_row from public.elearning_sections where tenant_id = p_tenant_id and course_id = p_course_id and id = p_entity_id;
    if not found then raise exception using errcode = 'P0002', message = 'elearning_structure_not_found'; end if;
  elsif p_action like '%lesson' and p_action <> 'create_lesson' then
    select * into lesson_row from public.elearning_lessons where tenant_id = p_tenant_id and course_id = p_course_id and id = p_entity_id;
    if not found then raise exception using errcode = 'P0002', message = 'elearning_structure_not_found'; end if;
  end if;
  if p_action in ('create_section','update_section','create_lesson','update_lesson') then
    details_status := coalesce(p_payload->>'status','draft');
    if details_status not in ('draft','published','archived') or (p_action like 'create_%' and details_status = 'archived') then
      raise exception using errcode = '22023', message = 'elearning_structure_invalid_status';
    end if;
  end if;

  if p_action = 'create_section' then
    select coalesce(max(position),-1)+1 into next_position from public.elearning_sections where tenant_id = p_tenant_id and course_id = p_course_id;
    insert into public.elearning_sections(tenant_id,course_id,name,description,status,position,created_by)
    values(p_tenant_id,p_course_id,p_payload->>'name',coalesce(p_payload->>'description',''),details_status,next_position,p_user_id);
  elsif p_action = 'update_section' then
    update public.elearning_sections set name = p_payload->>'name', description = coalesce(p_payload->>'description',''), status = details_status,
      archived_at = case when details_status = 'archived' then coalesce(archived_at,now()) else null end where id = section_row.id;
  elsif p_action = 'archive_section' then
    update public.elearning_sections set status = 'archived', archived_at = coalesce(archived_at,now()) where id = section_row.id;
  elsif p_action = 'delete_section' then
    if p_payload->'confirmed' is distinct from 'true'::jsonb then raise exception using errcode = '22023', message = 'elearning_structure_confirmation_required'; end if;
    if exists(select 1 from public.elearning_lessons where tenant_id = p_tenant_id and course_id = p_course_id and section_id = section_row.id) then
      raise exception using errcode = 'P0001', message = 'elearning_section_not_empty';
    end if;
    delete from public.elearning_sections where id = section_row.id;
  elsif p_action = 'duplicate_section' then
    select coalesce(max(position),-1)+1 into next_position from public.elearning_sections where tenant_id = p_tenant_id and course_id = p_course_id;
    insert into public.elearning_sections(tenant_id,course_id,name,description,position,created_by)
      values(p_tenant_id,p_course_id,left('Copy of ' || section_row.name,120),section_row.description,next_position,p_user_id) returning id into new_id;
    insert into public.elearning_lessons(tenant_id,course_id,section_id,name,description,position,created_by)
      select p_tenant_id,p_course_id,new_id,name,description,(row_number() over(order by position,id)-1)::integer,p_user_id
      from public.elearning_lessons where tenant_id = p_tenant_id and course_id = p_course_id and section_id = section_row.id order by position,id;
  elsif p_action = 'reorder_section' then
    if p_payload->>'direction' is null or p_payload->>'direction' not in ('up','down') then raise exception using errcode = '22023', message = 'elearning_structure_invalid_direction'; end if;
    next_position := section_row.position + case when p_payload->>'direction' = 'up' then -1 else 1 end;
    select id into swap_id from public.elearning_sections where tenant_id = p_tenant_id and course_id = p_course_id and position = next_position;
    if swap_id is not null then
      update public.elearning_sections set position = section_row.position where id = swap_id;
      update public.elearning_sections set position = next_position where id = section_row.id;
    end if;
  elsif p_action in ('create_lesson','move_lesson') then
    destination := (p_payload->>'section_id')::uuid;
    if not exists(select 1 from public.elearning_sections where tenant_id = p_tenant_id and course_id = p_course_id and id = destination and status <> 'archived') then
      raise exception using errcode = 'P0002', message = 'elearning_structure_destination_not_found';
    end if;
    select coalesce(max(position),-1)+1 into next_position from public.elearning_lessons where tenant_id = p_tenant_id and course_id = p_course_id and section_id = destination;
    if p_action = 'create_lesson' then
      insert into public.elearning_lessons(tenant_id,course_id,section_id,name,description,status,position,created_by)
      values(p_tenant_id,p_course_id,destination,p_payload->>'name',coalesce(p_payload->>'description',''),details_status,next_position,p_user_id);
    elsif destination <> lesson_row.section_id then
      update public.elearning_lessons set section_id = destination, position = next_position where id = lesson_row.id;
    end if;
  elsif p_action = 'update_lesson' then
    update public.elearning_lessons set name = p_payload->>'name', description = coalesce(p_payload->>'description',''), status = details_status,
      archived_at = case when details_status = 'archived' then coalesce(archived_at,now()) else null end where id = lesson_row.id;
  elsif p_action = 'archive_lesson' then
    update public.elearning_lessons set status = 'archived', archived_at = coalesce(archived_at,now()) where id = lesson_row.id;
  elsif p_action = 'delete_lesson' then
    if p_payload->'confirmed' is distinct from 'true'::jsonb then raise exception using errcode = '22023', message = 'elearning_structure_confirmation_required'; end if;
    -- Generic lessons currently contain summary metadata only. Future block FKs
    -- must restrict deletion until their own explicit safe deletion policy exists.
    delete from public.elearning_lessons where id = lesson_row.id;
  elsif p_action = 'duplicate_lesson' then
    if exists(select 1 from public.elearning_sections where id = lesson_row.section_id and status = 'archived') then
      raise exception using errcode = '22023', message = 'elearning_structure_parent_archived';
    end if;
    select coalesce(max(position),-1)+1 into next_position from public.elearning_lessons where tenant_id = p_tenant_id and course_id = p_course_id and section_id = lesson_row.section_id;
    insert into public.elearning_lessons(tenant_id,course_id,section_id,name,description,position,created_by)
    values(p_tenant_id,p_course_id,lesson_row.section_id,left('Copy of ' || lesson_row.name,120),lesson_row.description,next_position,p_user_id);
  elsif p_action = 'reorder_lesson' then
    if p_payload->>'direction' is null or p_payload->>'direction' not in ('up','down') then raise exception using errcode = '22023', message = 'elearning_structure_invalid_direction'; end if;
    next_position := lesson_row.position + case when p_payload->>'direction' = 'up' then -1 else 1 end;
    select id into swap_id from public.elearning_lessons where tenant_id = p_tenant_id and course_id = p_course_id and section_id = lesson_row.section_id and position = next_position;
    if swap_id is not null then
      update public.elearning_lessons set position = lesson_row.position where id = swap_id;
      update public.elearning_lessons set position = next_position where id = lesson_row.id;
    end if;
  end if;

  -- Renumber after move/delete so all siblings retain unique contiguous positions.
  with positions as (select id,(row_number() over(order by position,id)-1)::integer as position
    from public.elearning_sections where tenant_id = p_tenant_id and course_id = p_course_id)
  update public.elearning_sections s set position = p.position from positions p where s.id = p.id and s.position <> p.position;
  with positions as (select id,(row_number() over(partition by section_id order by position,id)-1)::integer as position
    from public.elearning_lessons where tenant_id = p_tenant_id and course_id = p_course_id)
  update public.elearning_lessons l set position = p.position from positions p where l.id = p.id and l.position <> p.position;
  update public.elearning_courses set structure_revision = structure_revision + 1 where tenant_id = p_tenant_id and id = p_course_id;
  return public.get_elearning_structure(p_tenant_id,p_course_id);
end;
$$;

revoke all on function public.get_elearning_structure(integer,uuid) from public,anon,authenticated;
revoke all on function public.get_elearning_course_counts(integer,uuid[]) from public,anon,authenticated;
revoke all on function public.manage_elearning_structure(integer,uuid,integer,integer,text,uuid,jsonb) from public,anon,authenticated;
grant execute on function public.get_elearning_structure(integer,uuid) to service_role;
grant execute on function public.get_elearning_course_counts(integer,uuid[]) to service_role;
grant execute on function public.manage_elearning_structure(integer,uuid,integer,integer,text,uuid,jsonb) to service_role;
notify pgrst, 'reload schema';
commit;
