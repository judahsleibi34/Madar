begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_124_schema_state_missing'; end if;
 if v_schema_version <> 123 then raise exception 'migration_124_expected_schema_123_got_%',v_schema_version; end if;
 update public.application_schema_state set schema_version = 124, applied_at=now() where contract_key = 'core';
end;
$$;

-- Extend the shared registry rather than introduce a learning upload store.
alter table public.builder_assets drop constraint builder_assets_storage_key_check;
alter table public.builder_assets add constraint builder_assets_storage_key_check
 check (storage_key ~ '^tenant_[1-9][0-9]*/builder_assets/[a-f0-9]{32}\.(png|jpg|webp|mp4|webm|pdf|doc|docx|mp3|wav)$');
alter table public.builder_assets drop constraint builder_assets_managed_filename_check;
alter table public.builder_assets add constraint builder_assets_managed_filename_check
 check (managed_filename ~ '^[a-f0-9]{32}\.(png|jpg|webp|mp4|webm|pdf|doc|docx|mp3|wav)$');
alter table public.builder_assets add constraint builder_assets_tenant_id_id_key unique(tenant_id,id);
alter table public.elearning_lessons add column content_revision integer not null default 1 check(content_revision>0);

create table public.elearning_content_blocks (
 id uuid primary key default gen_random_uuid(),
 tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
 course_id uuid not null,
 lesson_id uuid not null,
 type text not null check(type ~ '^[a-z][a-z0-9_]{0,49}$'),
 title text not null default '' check(char_length(title)<=120),
 content jsonb not null check(jsonb_typeof(content)='object'),
 media_id uuid,
 position integer not null check(position>=0),
 created_by integer references public.users(id) on delete set null,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 archived_at timestamptz,
 foreign key(tenant_id,course_id,lesson_id) references public.elearning_lessons(tenant_id,course_id,id) on delete no action deferrable initially deferred,
 foreign key(tenant_id,media_id) references public.builder_assets(tenant_id,id) on delete restrict,
 unique(tenant_id,lesson_id,position) deferrable initially deferred
);
-- section_id is derived from the lesson so moves cannot leave a stale attachment.
create index elearning_content_media_idx on public.elearning_content_blocks(tenant_id,media_id) where media_id is not null;
create trigger set_elearning_content_updated_at before update on public.elearning_content_blocks
 for each row execute function public.set_updated_at();
alter table public.elearning_content_blocks enable row level security;
revoke all on public.elearning_content_blocks from public,anon,authenticated,service_role;
grant select on public.elearning_content_blocks to service_role;

create function public.get_elearning_content(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid)
returns jsonb language sql stable security definer set search_path='' as $$
 select jsonb_build_object('revision',l.content_revision,'lesson',to_jsonb(l),'section',to_jsonb(s),
 'editable',c.status<>'archived' and s.status<>'archived' and l.status<>'archived',
 'blocks',coalesce((select jsonb_agg(to_jsonb(b) || jsonb_build_object('media',case when a.id is not null and a.status in ('active','unreferenced') then
 jsonb_build_object('id',a.id,'url','/uploads/'||a.storage_key,'filename',a.original_filename,'mime_type',a.mime_type) else null end)
 order by b.position,b.id) from public.elearning_content_blocks b left join public.builder_assets a on (a.tenant_id,a.id)=(b.tenant_id,b.media_id)
 where b.tenant_id=p_tenant_id and b.course_id=p_course_id and b.lesson_id=l.id),'[]'::jsonb))
 from public.elearning_lessons l join public.elearning_sections s on(s.tenant_id,s.course_id,s.id)=(l.tenant_id,l.course_id,l.section_id)
 join public.elearning_courses c on(c.tenant_id,c.id)=(l.tenant_id,l.course_id)
 where l.tenant_id=p_tenant_id and l.course_id=p_course_id and l.id=p_lesson_id;
$$;

create function public.manage_elearning_content(p_tenant_id integer,p_course_id uuid,p_lesson_id uuid,p_user_id integer,p_expected_revision integer,p_action text,p_entity_id uuid default null,p_payload jsonb default '{}'::jsonb)
returns jsonb language plpgsql security definer set search_path='' as $$
declare
 c public.elearning_courses%rowtype;
 l public.elearning_lessons%rowtype;
 b public.elearning_content_blocks%rowtype;
 a public.builder_assets%rowtype;
 v_type text; v_content jsonb; v_media uuid; v_position integer; v_swap uuid;
begin
 -- Same lock order as structure, enrollment and confirmed course deletion.
 select * into c from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id for update;
 if not found then raise exception using errcode='P0002',message='elearning_content_not_found'; end if;
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant_id and user_id=p_user_id and role in ('owner','admin') and status='active') then
  raise exception using errcode='42501',message='elearning_content_forbidden'; end if;
 select * into l from public.elearning_lessons where tenant_id=p_tenant_id and course_id=p_course_id and id=p_lesson_id for update;
 if not found then raise exception using errcode='P0002',message='elearning_content_not_found'; end if;
 if l.content_revision is distinct from p_expected_revision then raise exception using errcode='P0001',message='elearning_content_conflict'; end if;
 if c.status='archived' or l.status='archived' or exists(select 1 from public.elearning_sections where tenant_id=p_tenant_id and course_id=p_course_id and id=l.section_id and status='archived') then
  raise exception using errcode='P0001',message='elearning_content_parent_archived'; end if;
 if p_action is null or p_action not in ('create','update','duplicate','reorder','archive','restore','delete') then raise exception using errcode='22023',message='elearning_content_invalid_action'; end if;
 if p_action<>'create' then
  select * into b from public.elearning_content_blocks where tenant_id=p_tenant_id and course_id=p_course_id and lesson_id=p_lesson_id and id=p_entity_id;
  if not found then raise exception using errcode='P0002',message='elearning_content_not_found'; end if;
  if b.archived_at is not null and p_action not in ('restore','delete') then raise exception using errcode='22023',message='elearning_content_archived'; end if;
 elsif p_entity_id is not null then raise exception using errcode='22023',message='elearning_content_invalid_entity';
 end if;
 if p_action in ('create','update') then
  v_type:=p_payload->>'type'; v_content:=p_payload->'content';
  if v_type is null or v_type not in ('text','audio','video') or jsonb_typeof(v_content) is distinct from 'object' or v_content->'version' is distinct from '1'::jsonb or char_length(v_content::text)>200000 then
   raise exception using errcode='22023',message='elearning_content_invalid_type'; end if;
  if v_type='text' then
   if jsonb_typeof(v_content->'body') is distinct from 'string' or char_length(btrim(v_content->>'body')) not between 1 and 50000 or p_payload->>'media_id' is not null then
    raise exception using errcode='22023',message='elearning_content_invalid_text'; end if;
  else
   v_media:=(p_payload->>'media_id')::uuid;
   select * into a from public.builder_assets where tenant_id=p_tenant_id and id=v_media and status in ('active','unreferenced') for update;
   if not found or (v_type='audio' and a.mime_type not in ('audio/mpeg','audio/wav')) or (v_type='video' and a.mime_type not in ('video/mp4','video/webm')) then
    raise exception using errcode='22023',message='elearning_content_invalid_media'; end if;
  end if;
 elsif p_action in ('duplicate','restore') and b.media_id is not null then
  select * into a from public.builder_assets where tenant_id=p_tenant_id and id=b.media_id and status in ('active','unreferenced') for update;
  if not found then raise exception using errcode='22023',message='elearning_content_invalid_media'; end if;
 end if;
 if p_action='create' then
  select coalesce(max(position),-1)+1 into v_position from public.elearning_content_blocks where tenant_id=p_tenant_id and lesson_id=p_lesson_id;
  insert into public.elearning_content_blocks(tenant_id,course_id,lesson_id,type,title,content,media_id,position,created_by)
   values(p_tenant_id,p_course_id,p_lesson_id,v_type,coalesce(p_payload->>'title',''),v_content,v_media,v_position,p_user_id);
 elsif p_action='update' then
  if v_type is distinct from b.type then raise exception using errcode='22023',message='elearning_content_type_immutable'; end if;
  update public.elearning_content_blocks set title=coalesce(p_payload->>'title',''),content=v_content,media_id=v_media where id=b.id;
 elsif p_action='duplicate' then
  update public.elearning_content_blocks set position=position+1 where tenant_id=p_tenant_id and lesson_id=p_lesson_id and position>b.position;
  insert into public.elearning_content_blocks(tenant_id,course_id,lesson_id,type,title,content,media_id,position,created_by)
   values(p_tenant_id,p_course_id,p_lesson_id,b.type,b.title,b.content,b.media_id,b.position+1,p_user_id);
 elsif p_action='reorder' then
  if p_payload->>'direction' is null or p_payload->>'direction' not in ('up','down') then raise exception using errcode='22023',message='elearning_content_invalid_direction'; end if;
  if p_payload->>'direction'='up' then
   select id,position into v_swap,v_position from public.elearning_content_blocks where tenant_id=p_tenant_id and lesson_id=p_lesson_id and archived_at is null and position<b.position order by position desc limit 1;
  else
   select id,position into v_swap,v_position from public.elearning_content_blocks where tenant_id=p_tenant_id and lesson_id=p_lesson_id and archived_at is null and position>b.position order by position limit 1;
  end if;
  if v_swap is not null then
   update public.elearning_content_blocks set position=b.position where id=v_swap;
   update public.elearning_content_blocks set position=v_position where id=b.id;
  end if;
 elsif p_action in ('archive','delete') then
  if p_payload->'confirmed' is distinct from 'true'::jsonb then raise exception using errcode='22023',message='elearning_content_confirmation_required'; end if;
  if p_action='archive' then update public.elearning_content_blocks set archived_at=now() where id=b.id;
  else delete from public.elearning_content_blocks where id=b.id; end if;
 elsif p_action='restore' then update public.elearning_content_blocks set archived_at=null where id=b.id;
 end if;
 -- Archived blocks retain content/media and occupy the tail; live order is contiguous.
 with ranked as(select id,(row_number() over(order by archived_at is not null,position,id)-1)::integer pos from public.elearning_content_blocks where tenant_id=p_tenant_id and lesson_id=p_lesson_id)
 update public.elearning_content_blocks x set position=r.pos from ranked r where x.id=r.id and x.position<>r.pos;
 update public.elearning_lessons set content_revision=content_revision+1 where id=l.id;
 -- Structure revision includes content mutations so confirmed course deletion cannot
 -- discard content saved after its confirmation snapshot.
 update public.elearning_courses set structure_revision=structure_revision+1 where id=c.id;
 return public.get_elearning_content(p_tenant_id,p_course_id,p_lesson_id);
end;
$$;

-- A parent delete is explicitly confirmed by the existing course RPC. Ordinary
-- lesson deletes are blocked while blocks (including archived ones) remain.
-- The restrictive FK above deliberately preserves that safety boundary.
-- Course deletion RPC deletes lessons before courses, so wrap it at the same
-- authorized boundary rather than cascade away lesson content implicitly.
alter function public.delete_elearning_course(integer,uuid,integer,integer,integer,text,boolean) rename to delete_elearning_course_before_content;
revoke all on function public.delete_elearning_course_before_content(integer,uuid,integer,integer,integer,text,boolean) from service_role;
create function public.delete_elearning_course(p_tenant_id integer,p_course_id uuid,p_user_id integer,p_expected_revision integer,p_expected_structure_revision integer,p_confirmation_name text,p_confirmed boolean)
returns jsonb language plpgsql security definer set search_path='' as $$
declare c public.elearning_courses%rowtype;
begin
 select * into c from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id for update;
 if not found then raise exception using errcode='P0002',message='elearning_course_not_found'; end if;
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant_id and user_id=p_user_id and role in ('owner','admin') and status='active') then raise exception using errcode='42501',message='elearning_course_delete_forbidden'; end if;
 if p_confirmed is distinct from true or p_confirmation_name is distinct from c.name then raise exception using errcode='22023',message='elearning_course_delete_confirmation_required'; end if;
 if p_expected_revision is distinct from c.revision or p_expected_structure_revision is distinct from c.structure_revision then raise exception using errcode='P0001',message='elearning_course_delete_conflict'; end if;
 delete from public.elearning_content_blocks where tenant_id=p_tenant_id and course_id=p_course_id;
 return public.delete_elearning_course_before_content(p_tenant_id,p_course_id,p_user_id,p_expected_revision,p_expected_structure_revision,p_confirmation_name,p_confirmed);
end;
$$;
revoke all on function public.get_elearning_content(integer,uuid,uuid) from public,anon,authenticated;
revoke all on function public.manage_elearning_content(integer,uuid,uuid,integer,integer,text,uuid,jsonb) from public,anon,authenticated;
revoke all on function public.delete_elearning_course(integer,uuid,integer,integer,integer,text,boolean) from public,anon,authenticated;
grant execute on function public.get_elearning_content(integer,uuid,uuid) to service_role;
grant execute on function public.manage_elearning_content(integer,uuid,uuid,integer,integer,text,uuid,jsonb) to service_role;
grant execute on function public.delete_elearning_course(integer,uuid,integer,integer,integer,text,boolean) to service_role;
-- Preserve content when existing structure duplication is used.
create or replace function public.manage_elearning_structure(
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
    with sources as (select id,(row_number() over(order by position,id)-1)::integer pos from public.elearning_lessons
      where tenant_id=p_tenant_id and course_id=p_course_id and section_id=section_row.id)
    insert into public.elearning_content_blocks(tenant_id,course_id,lesson_id,type,title,content,media_id,position,created_by,archived_at)
    select b.tenant_id,b.course_id,d.id,b.type,b.title,b.content,b.media_id,b.position,p_user_id,b.archived_at
    from sources x join public.elearning_lessons d on d.tenant_id=p_tenant_id and d.course_id=p_course_id and d.section_id=new_id and d.position=x.pos
    join public.elearning_content_blocks b on b.tenant_id=p_tenant_id and b.course_id=p_course_id and b.lesson_id=x.id;
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
    -- Content/history FKs preserve learning content until explicitly removed.
    delete from public.elearning_lessons where id = lesson_row.id;
  elsif p_action = 'duplicate_lesson' then
    if exists(select 1 from public.elearning_sections where id = lesson_row.section_id and status = 'archived') then
      raise exception using errcode = '22023', message = 'elearning_structure_parent_archived';
    end if;
    select coalesce(max(position),-1)+1 into next_position from public.elearning_lessons where tenant_id = p_tenant_id and course_id = p_course_id and section_id = lesson_row.section_id;
    insert into public.elearning_lessons(tenant_id,course_id,section_id,name,description,position,created_by)
    values(p_tenant_id,p_course_id,lesson_row.section_id,left('Copy of ' || lesson_row.name,120),lesson_row.description,next_position,p_user_id) returning id into new_id;
    insert into public.elearning_content_blocks(tenant_id,course_id,lesson_id,type,title,content,media_id,position,created_by,archived_at)
    select tenant_id,course_id,new_id,type,title,content,media_id,position,p_user_id,archived_at
    from public.elearning_content_blocks where tenant_id=p_tenant_id and course_id=p_course_id and lesson_id=lesson_row.id;
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

notify pgrst,'reload schema';
commit;
