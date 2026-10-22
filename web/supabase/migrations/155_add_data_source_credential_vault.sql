begin;

do $$
declare
  v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version into v_schema_version
  from public.application_schema_state
  where contract_key = 'core'
  for update;
  if v_schema_version is null then
    raise exception using errcode = 'P0001', message = 'migration_155_schema_state_missing';
  end if;
  if v_schema_version <> 154 then
    raise exception using errcode = 'P0001',
      message = format('migration_155_expected_schema_154_got_%s', v_schema_version);
  end if;
end;
$$;

alter table public.data_sources
  add column active_credential_id uuid,
  add column credential_revision bigint not null default 0,
  add constraint data_sources_credential_revision_check155
    check(credential_revision >= 0);

create table public.data_source_credentials (
  id uuid primary key,
  tenant_id integer not null,
  project_id uuid not null,
  source_id uuid not null,
  provider_key text not null,
  credential_type text not null,
  credential_version integer not null,
  source_revision bigint not null,
  status text not null,
  environment_binding text not null,
  ciphertext text not null,
  nonce text not null,
  wrapped_data_key text not null,
  key_name text not null,
  key_version integer not null,
  aad_version integer not null,
  expires_at timestamptz,
  created_by_user_id integer not null,
  created_at timestamptz not null default now(),
  activated_at timestamptz not null default now(),
  superseded_at timestamptz,
  revoked_at timestamptz,
  last_used_at timestamptz,
  rewrapped_at timestamptz,
  constraint data_source_credentials_source_fk155
    foreign key(source_id, tenant_id, project_id)
    references public.data_sources(id, tenant_id, project_id) on delete restrict,
  constraint data_source_credentials_creator_fk155
    foreign key(created_by_user_id, tenant_id)
    references public.users(id, tenant_id) on delete restrict,
  constraint data_source_credentials_provider_check155
    check(provider_key ~ '^[a-z][a-z0-9_]{1,79}$'),
  constraint data_source_credentials_type_check155
    check(credential_type ~ '^[a-z][a-z0-9_]{1,79}$'),
  constraint data_source_credentials_version_check155
    check(credential_version > 0 and source_revision > 0),
  constraint data_source_credentials_status_check155
    check(status in ('active','superseded','revoked')),
  constraint data_source_credentials_environment_check155
    check(environment_binding ~ '^[a-z][a-z0-9_-]{1,63}$'),
  constraint data_source_credentials_ciphertext_check155
    check(length(ciphertext) between 24 and 16384),
  constraint data_source_credentials_nonce_check155
    check(length(nonce) = 16),
  constraint data_source_credentials_wrapped_key_check155
    check(wrapped_data_key ~ '^vault:v[1-9][0-9]*:[A-Za-z0-9+/=]+$' and length(wrapped_data_key) <= 16384),
  constraint data_source_credentials_key_name_check155
    check(key_name ~ '^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$'),
  constraint data_source_credentials_key_version_check155
    check(key_version > 0 and aad_version = 1),
  constraint data_source_credentials_expiry_check155
    check(expires_at is null or expires_at > created_at),
  constraint data_source_credentials_state_time_check155 check(
    (status = 'active' and superseded_at is null and revoked_at is null)
    or (status = 'superseded' and superseded_at is not null and revoked_at is null)
    or (status = 'revoked' and revoked_at is not null)
  ),
  constraint data_source_credentials_source_version_unique155
    unique(tenant_id, source_id, credential_version),
  constraint data_source_credentials_identity_scope_unique155
    unique(id, source_id, tenant_id, project_id)
);

create unique index data_source_credentials_one_active155
on public.data_source_credentials(tenant_id, source_id, provider_key, credential_type)
where status = 'active';

create index data_source_credentials_scope155
on public.data_source_credentials(tenant_id, project_id, source_id, created_at desc);

alter table public.data_sources
  add constraint data_sources_active_credential_fk155
  foreign key(active_credential_id, id, tenant_id, project_id)
  references public.data_source_credentials(id, source_id, tenant_id, project_id)
  on delete restrict;

create table public.data_source_credential_events (
  id bigint generated always as identity primary key,
  tenant_id integer not null,
  project_id uuid not null,
  source_id uuid not null,
  credential_id uuid,
  credential_version integer,
  actor_user_id integer not null,
  event_type text not null,
  event_code text,
  created_at timestamptz not null default now(),
  constraint data_source_credential_events_source_fk155
    foreign key(source_id, tenant_id, project_id)
    references public.data_sources(id, tenant_id, project_id) on delete restrict,
  constraint data_source_credential_events_actor_fk155
    foreign key(actor_user_id, tenant_id)
    references public.users(id, tenant_id) on delete restrict,
  constraint data_source_credential_events_credential_fk155
    foreign key(credential_id, source_id, tenant_id, project_id)
    references public.data_source_credentials(id, source_id, tenant_id, project_id)
    on delete restrict,
  constraint data_source_credential_events_type_check155
    check(event_type in ('provisioned','rotated','resolved','revoked','rewrapped')),
  constraint data_source_credential_events_code_check155
    check(event_code is null or event_code ~ '^[a-z][a-z0-9_]{1,79}$'),
  constraint data_source_credential_events_version_check155
    check((credential_id is null) = (credential_version is null)
      and (credential_version is null or credential_version > 0))
);

create index data_source_credential_events_scope155
on public.data_source_credential_events(tenant_id, project_id, source_id, created_at desc);

create function public.reject_data_source_credential_event_mutation155()
returns trigger language plpgsql set search_path = '' as $$
begin
  raise exception using errcode = '42501', message = 'credential_events_are_append_only';
end;
$$;

create trigger reject_data_source_credential_event_update155
before update or delete on public.data_source_credential_events
for each row execute function public.reject_data_source_credential_event_mutation155();

create function public.prepare_data_source_credential155(
  p_tenant_id integer, p_project_id uuid, p_source_id uuid,
  p_actor_user_id integer, p_provider_key text, p_credential_type text
)
returns table(credential_id uuid, credential_version integer, source_revision bigint)
language plpgsql security definer set search_path = '' as $$
declare
  v_source public.data_sources;
  v_version integer;
begin
  select s.* into v_source from public.data_sources s
  join public.builder_projects p on p.id=s.project_id and p.tenant_id=s.tenant_id
  where s.id=p_source_id and s.tenant_id=p_tenant_id and s.project_id=p_project_id
    and s.creator_user_id=p_actor_user_id and s.status='active'
    and s.source_type='api_provider' and s.provider_key=p_provider_key
    and p.status<>'archived' and p.draft_schema->>'workspaceKind'='data'
    and exists(select 1 from public.tenant_memberships m
      where m.tenant_id=p_tenant_id and m.user_id=p_actor_user_id
        and m.status='active' and m.role<>'learner')
  for update of s;
  if not found or p_credential_type !~ '^[a-z][a-z0-9_]{1,79}$' then
    raise exception using errcode='42501', message='credential_source_not_authorized';
  end if;
  select coalesce(max(c.credential_version),0)+1 into v_version
  from public.data_source_credentials c
  where c.tenant_id=p_tenant_id and c.source_id=p_source_id;
  return query select gen_random_uuid(), v_version, v_source.credential_revision;
end;
$$;

create function public.activate_data_source_credential155(
  p_tenant_id integer, p_project_id uuid, p_source_id uuid,
  p_actor_user_id integer, p_provider_key text, p_credential_type text,
  p_credential_id uuid, p_credential_version integer,
  p_expected_source_revision bigint, p_environment_binding text,
  p_ciphertext text, p_nonce text, p_wrapped_data_key text,
  p_key_name text, p_key_version integer, p_aad_version integer,
  p_expires_at timestamptz default null
)
returns table(credential_id uuid, credential_version integer, source_revision bigint,
  status text, expires_at timestamptz, key_name text, key_version integer,
  created_at timestamptz)
language plpgsql security definer set search_path = '' as $$
declare
  v_source public.data_sources;
  v_old public.data_source_credentials;
  v_new public.data_source_credentials;
  v_next_version integer;
  v_event text;
begin
  select s.* into v_source from public.data_sources s
  join public.builder_projects p on p.id=s.project_id and p.tenant_id=s.tenant_id
  where s.id=p_source_id and s.tenant_id=p_tenant_id and s.project_id=p_project_id
    and s.creator_user_id=p_actor_user_id and s.status='active'
    and s.source_type='api_provider' and s.provider_key=p_provider_key
    and p.status<>'archived' and p.draft_schema->>'workspaceKind'='data'
    and exists(select 1 from public.tenant_memberships m
      where m.tenant_id=p_tenant_id and m.user_id=p_actor_user_id
        and m.status='active' and m.role<>'learner')
  for update of s;
  if not found then raise exception using errcode='42501',message='credential_source_not_authorized'; end if;
  if v_source.credential_revision<>p_expected_source_revision then
    raise exception using errcode='40001',message='credential_revision_conflict';
  end if;
  select coalesce(max(c.credential_version),0)+1 into v_next_version
  from public.data_source_credentials c where c.tenant_id=p_tenant_id and c.source_id=p_source_id;
  if p_credential_version<>v_next_version or p_credential_id is null
     or p_provider_key !~ '^[a-z][a-z0-9_]{1,79}$'
     or p_credential_type !~ '^[a-z][a-z0-9_]{1,79}$'
     or p_expires_at is not null and p_expires_at<=now() then
    raise exception using errcode='22023',message='credential_payload_invalid';
  end if;
  if v_source.active_credential_id is not null then
    select * into v_old from public.data_source_credentials c
    where c.id=v_source.active_credential_id and c.tenant_id=p_tenant_id for update;
    if not found or v_old.status<>'active' then
      raise exception using errcode='P0001',message='credential_active_state_invalid';
    end if;
    update public.data_source_credentials set status='superseded',superseded_at=now()
    where id=v_old.id;
    v_event := 'rotated';
  else v_event := 'provisioned'; end if;
  insert into public.data_source_credentials(
    id,tenant_id,project_id,source_id,provider_key,credential_type,
    credential_version,source_revision,status,environment_binding,ciphertext,nonce,
    wrapped_data_key,key_name,key_version,aad_version,expires_at,created_by_user_id
  ) values(
    p_credential_id,p_tenant_id,p_project_id,p_source_id,p_provider_key,p_credential_type,
    p_credential_version,p_expected_source_revision+1,'active',p_environment_binding,
    p_ciphertext,p_nonce,p_wrapped_data_key,p_key_name,p_key_version,p_aad_version,
    p_expires_at,p_actor_user_id
  ) returning * into v_new;
  update public.data_sources set active_credential_id=v_new.id,
    credential_revision=p_expected_source_revision+1 where id=p_source_id;
  insert into public.data_source_credential_events(
    tenant_id,project_id,source_id,credential_id,credential_version,
    actor_user_id,event_type,event_code
  ) values(p_tenant_id,p_project_id,p_source_id,v_new.id,v_new.credential_version,
    p_actor_user_id,v_event,'active_version_changed');
  return query select v_new.id,v_new.credential_version,v_new.source_revision,
    v_new.status,v_new.expires_at,v_new.key_name,v_new.key_version,v_new.created_at;
end;
$$;

create function public.resolve_data_source_credential155(
  p_tenant_id integer, p_project_id uuid, p_source_id uuid,
  p_actor_user_id integer, p_provider_key text, p_credential_type text
)
returns table(credential_id uuid,tenant_id integer,project_id uuid,source_id uuid,
  provider_key text,credential_type text,credential_version integer,source_revision bigint,
  environment_binding text,ciphertext text,nonce text,wrapped_data_key text,
  key_name text,key_version integer,aad_version integer,expires_at timestamptz)
language plpgsql security definer set search_path = '' as $$
begin
  return query select c.id,c.tenant_id,c.project_id,c.source_id,c.provider_key,
    c.credential_type,c.credential_version,s.credential_revision,
    c.environment_binding,c.ciphertext,c.nonce,c.wrapped_data_key,
    c.key_name,c.key_version,c.aad_version,c.expires_at
  from public.data_sources s
  join public.builder_projects p on p.id=s.project_id and p.tenant_id=s.tenant_id
  join public.data_source_credentials c on c.id=s.active_credential_id
    and c.source_id=s.id and c.tenant_id=s.tenant_id and c.project_id=s.project_id
  where s.id=p_source_id and s.tenant_id=p_tenant_id and s.project_id=p_project_id
    and s.creator_user_id=p_actor_user_id and s.status='active'
    and s.source_type='api_provider' and s.provider_key=p_provider_key
    and c.provider_key=p_provider_key and c.credential_type=p_credential_type
    and c.status='active' and (c.expires_at is null or c.expires_at>now())
    and p.status<>'archived' and p.draft_schema->>'workspaceKind'='data'
    and exists(select 1 from public.tenant_memberships m
      where m.tenant_id=p_tenant_id and m.user_id=p_actor_user_id
        and m.status='active' and m.role<>'learner');
end;
$$;

create function public.assert_data_source_credential155(
  p_tenant_id integer,p_project_id uuid,p_source_id uuid,p_actor_user_id integer,
  p_provider_key text,p_credential_id uuid,p_credential_version integer,
  p_source_revision bigint
)
returns boolean language sql security definer set search_path='' stable as $$
  select exists(
    select 1 from public.data_sources s
    join public.builder_projects p on p.id=s.project_id and p.tenant_id=s.tenant_id
    join public.data_source_credentials c on c.id=s.active_credential_id
    where s.id=p_source_id and s.tenant_id=p_tenant_id and s.project_id=p_project_id
      and s.creator_user_id=p_actor_user_id and s.status='active'
      and s.source_type='api_provider' and s.provider_key=p_provider_key
      and s.credential_revision=p_source_revision
      and c.id=p_credential_id and c.credential_version=p_credential_version
      and c.status='active' and (c.expires_at is null or c.expires_at>now())
      and p.status<>'archived' and p.draft_schema->>'workspaceKind'='data'
      and exists(select 1 from public.tenant_memberships m
        where m.tenant_id=p_tenant_id and m.user_id=p_actor_user_id
          and m.status='active' and m.role<>'learner')
  );
$$;

create function public.mark_data_source_credential_used155(
  p_tenant_id integer,p_project_id uuid,p_source_id uuid,p_actor_user_id integer,
  p_provider_key text,p_credential_id uuid,p_credential_version integer,
  p_source_revision bigint
)
returns boolean language plpgsql security definer set search_path='' as $$
begin
  if not public.assert_data_source_credential155(p_tenant_id,p_project_id,p_source_id,
      p_actor_user_id,p_provider_key,p_credential_id,p_credential_version,p_source_revision) then
    return false;
  end if;
  update public.data_source_credentials set last_used_at=now()
  where id=p_credential_id and tenant_id=p_tenant_id and status='active';
  insert into public.data_source_credential_events(
    tenant_id,project_id,source_id,credential_id,credential_version,
    actor_user_id,event_type,event_code
  ) values(p_tenant_id,p_project_id,p_source_id,p_credential_id,p_credential_version,
    p_actor_user_id,'resolved','provider_request_authorized');
  return true;
end;
$$;

create function public.revoke_data_source_credential155(
  p_tenant_id integer,p_project_id uuid,p_source_id uuid,p_actor_user_id integer,
  p_provider_key text,p_expected_source_revision bigint
)
returns table(credential_id uuid,credential_version integer,source_revision bigint,status text,revoked_at timestamptz)
language plpgsql security definer set search_path='' as $$
declare v_source public.data_sources;v_credential public.data_source_credentials;
begin
  select s.* into v_source from public.data_sources s
  where s.id=p_source_id and s.tenant_id=p_tenant_id and s.project_id=p_project_id
    and s.creator_user_id=p_actor_user_id and s.status='active'
    and s.source_type='api_provider' and s.provider_key=p_provider_key
    and exists(select 1 from public.tenant_memberships m where m.tenant_id=p_tenant_id
      and m.user_id=p_actor_user_id and m.status='active' and m.role<>'learner')
  for update;
  if not found then raise exception using errcode='42501',message='credential_source_not_authorized';end if;
  if v_source.credential_revision<>p_expected_source_revision then
    raise exception using errcode='40001',message='credential_revision_conflict';end if;
  select * into v_credential from public.data_source_credentials c
  where c.id=v_source.active_credential_id and c.tenant_id=p_tenant_id for update;
  if not found or v_credential.status<>'active' then
    raise exception using errcode='P0001',message='credential_active_state_invalid';end if;
  update public.data_source_credentials set status='revoked',revoked_at=now()
  where id=v_credential.id returning * into v_credential;
  update public.data_sources set active_credential_id=null,
    credential_revision=p_expected_source_revision+1 where id=p_source_id;
  insert into public.data_source_credential_events(
    tenant_id,project_id,source_id,credential_id,credential_version,
    actor_user_id,event_type,event_code
  ) values(p_tenant_id,p_project_id,p_source_id,v_credential.id,v_credential.credential_version,
    p_actor_user_id,'revoked','active_version_revoked');
  return query select v_credential.id,v_credential.credential_version,
    p_expected_source_revision+1,v_credential.status,v_credential.revoked_at;
end;
$$;

create function public.prepare_data_source_credential_rewrap155(
  p_tenant_id integer,p_project_id uuid,p_source_id uuid,p_actor_user_id integer,
  p_provider_key text,p_credential_id uuid
)
returns table(credential_id uuid,tenant_id integer,project_id uuid,source_id uuid,
  provider_key text,credential_type text,credential_version integer,source_revision bigint,
  environment_binding text,wrapped_data_key text,key_name text,key_version integer,
  aad_version integer)
language plpgsql security definer set search_path='' as $$
begin
  if not exists(select 1 from public.data_sources s
    join public.builder_projects p on p.id=s.project_id and p.tenant_id=s.tenant_id
    where s.id=p_source_id and s.tenant_id=p_tenant_id and s.project_id=p_project_id
      and s.creator_user_id=p_actor_user_id and s.provider_key=p_provider_key
      and p.status<>'archived' and p.draft_schema->>'workspaceKind'='data'
      and exists(select 1 from public.tenant_memberships m where m.tenant_id=p_tenant_id
        and m.user_id=p_actor_user_id and m.status='active' and m.role<>'learner')) then
    raise exception using errcode='42501',message='credential_source_not_authorized';end if;
  return query select c.id,c.tenant_id,c.project_id,c.source_id,c.provider_key,
    c.credential_type,c.credential_version,c.source_revision,c.environment_binding,
    c.wrapped_data_key,c.key_name,c.key_version,c.aad_version
  from public.data_source_credentials c where c.id=p_credential_id
    and c.tenant_id=p_tenant_id and c.project_id=p_project_id
    and c.source_id=p_source_id and c.provider_key=p_provider_key;
end;
$$;

create function public.complete_data_source_credential_rewrap155(
  p_tenant_id integer,p_project_id uuid,p_source_id uuid,p_actor_user_id integer,
  p_provider_key text,p_credential_id uuid,p_expected_wrapped_data_key text,
  p_expected_key_version integer,p_wrapped_data_key text,p_key_version integer
)
returns table(credential_id uuid,credential_version integer,status text,
  key_name text,key_version integer,rewrapped_at timestamptz)
language plpgsql security definer set search_path='' as $$
declare v_credential public.data_source_credentials;
begin
  if not exists(select 1 from public.data_sources s
    join public.builder_projects p on p.id=s.project_id and p.tenant_id=s.tenant_id
    where s.id=p_source_id and s.tenant_id=p_tenant_id and s.project_id=p_project_id
      and s.creator_user_id=p_actor_user_id and s.provider_key=p_provider_key
      and p.status<>'archived' and p.draft_schema->>'workspaceKind'='data'
      and exists(select 1 from public.tenant_memberships m where m.tenant_id=p_tenant_id
        and m.user_id=p_actor_user_id and m.status='active' and m.role<>'learner')) then
    raise exception using errcode='42501',message='credential_source_not_authorized';end if;
  select * into v_credential from public.data_source_credentials c
  where c.id=p_credential_id and c.tenant_id=p_tenant_id and c.project_id=p_project_id
    and c.source_id=p_source_id and c.provider_key=p_provider_key for update;
  if not found or v_credential.wrapped_data_key<>p_expected_wrapped_data_key
     or v_credential.key_version<>p_expected_key_version then
    raise exception using errcode='40001',message='credential_rewrap_conflict';end if;
  if p_wrapped_data_key !~ '^vault:v[1-9][0-9]*:[A-Za-z0-9+/=]+$'
     or p_key_version<=0 then
    raise exception using errcode='22023',message='credential_rewrap_invalid';end if;
  update public.data_source_credentials c set wrapped_data_key=p_wrapped_data_key,
    key_version=p_key_version,rewrapped_at=now() where c.id=v_credential.id
    returning * into v_credential;
  insert into public.data_source_credential_events(
    tenant_id,project_id,source_id,credential_id,credential_version,
    actor_user_id,event_type,event_code
  ) values(p_tenant_id,p_project_id,p_source_id,v_credential.id,
    v_credential.credential_version,p_actor_user_id,'rewrapped','data_key_rewrapped');
  return query select v_credential.id,v_credential.credential_version,
    v_credential.status,v_credential.key_name,v_credential.key_version,
    v_credential.rewrapped_at;
end;
$$;

create function public.list_data_source_credentials155(
  p_tenant_id integer,p_project_id uuid,p_source_id uuid,p_actor_user_id integer,p_provider_key text
)
returns table(credential_id uuid,credential_version integer,source_revision bigint,status text,
  credential_type text,expires_at timestamptz,key_name text,key_version integer,
  created_at timestamptz,activated_at timestamptz,superseded_at timestamptz,
  revoked_at timestamptz,last_used_at timestamptz,rewrapped_at timestamptz)
language plpgsql security definer set search_path='' as $$
begin
  if not exists(select 1 from public.data_sources s where s.id=p_source_id
    and s.tenant_id=p_tenant_id and s.project_id=p_project_id
    and s.creator_user_id=p_actor_user_id and s.provider_key=p_provider_key
    and exists(select 1 from public.tenant_memberships m where m.tenant_id=p_tenant_id
      and m.user_id=p_actor_user_id and m.status='active' and m.role<>'learner')) then
    raise exception using errcode='42501',message='credential_source_not_authorized';end if;
  return query select c.id,c.credential_version,c.source_revision,c.status,
    c.credential_type,c.expires_at,c.key_name,c.key_version,c.created_at,c.activated_at,
    c.superseded_at,c.revoked_at,c.last_used_at,c.rewrapped_at
  from public.data_source_credentials c where c.tenant_id=p_tenant_id
    and c.project_id=p_project_id and c.source_id=p_source_id
  order by c.credential_version desc;
end;
$$;

create function public.complete_incremental_ingestion155(
  p_tenant_id integer,p_project_id uuid,p_source_id uuid,p_user_id integer,
  p_ingestion_run_id uuid,p_lease_token uuid,p_storage_object_id uuid,
  p_change_count integer,p_manifest_hash text,p_next_cursor text,p_schema_fingerprint text,
  p_credential_id uuid,p_credential_version integer,p_credential_revision bigint
)
returns table(dataset_id uuid,source_resource_id uuid,committed_revision bigint,
  ingestion_run_id uuid,ingestion_status text,inserted_count integer,updated_count integer,
  deleted_count integer,duplicate_count integer,stale_count integer,
  latest_checkpoint_version_id uuid)
language plpgsql security definer set search_path='' as $$
declare v_source public.data_sources;v_credential public.data_source_credentials;
begin
  select * into v_source from public.data_sources s where s.id=p_source_id
    and s.tenant_id=p_tenant_id and s.project_id=p_project_id
    and s.creator_user_id=p_user_id and s.source_type='api_provider' for update;
  if not found or v_source.status<>'active' or v_source.active_credential_id is distinct from p_credential_id
     or v_source.credential_revision<>p_credential_revision then
    raise exception using errcode='P0001',message='credential_revision_lost';end if;
  select * into v_credential from public.data_source_credentials c
  where c.id=p_credential_id and c.tenant_id=p_tenant_id and c.project_id=p_project_id
    and c.source_id=p_source_id for update;
  if not found or v_credential.status<>'active'
     or v_credential.credential_version<>p_credential_version
     or v_credential.provider_key<>v_source.provider_key
     or v_credential.expires_at is not null and v_credential.expires_at<=now() then
    raise exception using errcode='P0001',message='credential_revision_lost';end if;
  return query select * from public.complete_incremental_ingestion152(
    p_tenant_id,p_project_id,p_source_id,p_user_id,p_ingestion_run_id,p_lease_token,
    p_storage_object_id,p_change_count,p_manifest_hash,p_next_cursor,p_schema_fingerprint
  );
end;
$$;

alter table public.data_source_credentials enable row level security;
alter table public.data_source_credential_events enable row level security;
revoke all on public.data_source_credentials,public.data_source_credential_events from public,anon,authenticated;
grant select,insert,update on public.data_source_credentials to service_role;
grant select,insert on public.data_source_credential_events to service_role;
revoke all on function public.reject_data_source_credential_event_mutation155() from public,anon,authenticated;

do $$
declare v_signature text;
begin
  foreach v_signature in array array[
    'prepare_data_source_credential155(integer,uuid,uuid,integer,text,text)',
    'activate_data_source_credential155(integer,uuid,uuid,integer,text,text,uuid,integer,bigint,text,text,text,text,text,integer,integer,timestamp with time zone)',
    'resolve_data_source_credential155(integer,uuid,uuid,integer,text,text)',
    'assert_data_source_credential155(integer,uuid,uuid,integer,text,uuid,integer,bigint)',
    'mark_data_source_credential_used155(integer,uuid,uuid,integer,text,uuid,integer,bigint)',
    'revoke_data_source_credential155(integer,uuid,uuid,integer,text,bigint)',
    'prepare_data_source_credential_rewrap155(integer,uuid,uuid,integer,text,uuid)',
    'complete_data_source_credential_rewrap155(integer,uuid,uuid,integer,text,uuid,text,integer,text,integer)',
    'list_data_source_credentials155(integer,uuid,uuid,integer,text)',
    'complete_incremental_ingestion155(integer,uuid,uuid,integer,uuid,uuid,uuid,integer,text,text,text,uuid,integer,bigint)'
  ] loop
    execute format('revoke all on function public.%s from public,anon,authenticated',v_signature);
    execute format('grant execute on function public.%s to service_role',v_signature);
  end loop;
end;
$$;

update public.application_schema_state set schema_version=155,applied_at=now()
where contract_key='core';
notify pgrst,'reload schema';
commit;
