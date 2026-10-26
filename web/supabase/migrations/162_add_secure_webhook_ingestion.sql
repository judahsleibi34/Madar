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
    raise exception using errcode='P0001',message='migration_162_schema_state_missing';
  end if;
  if v_schema_version<>161 then
    raise exception using errcode='P0001',
      message=format('migration_162_expected_schema_161_got_%s',v_schema_version);
  end if;
end;
$$;

create table public.data_source_webhook_endpoints (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  project_id uuid not null,
  source_id uuid not null,
  source_resource_id uuid not null,
  actor_user_id integer not null,
  provider_key text not null,
  resource_type text not null,
  status text not null default 'disabled',
  credential_id uuid not null,
  credential_version integer not null,
  credential_revision bigint not null,
  fence bigint not null default 1,
  last_received_at timestamptz,
  last_processed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint data_source_webhook_endpoints_source_fk162
    foreign key(source_id,tenant_id,project_id)
    references public.data_sources(id,tenant_id,project_id) on delete restrict,
  constraint data_source_webhook_endpoints_resource_fk162
    foreign key(source_resource_id,tenant_id,project_id,source_id)
    references public.data_source_resources(id,tenant_id,project_id,source_id) on delete restrict,
  constraint data_source_webhook_endpoints_actor_fk162
    foreign key(actor_user_id,tenant_id) references public.users(id,tenant_id) on delete restrict,
  constraint data_source_webhook_endpoints_credential_fk162
    foreign key(credential_id,source_id,tenant_id,project_id)
    references public.data_source_credentials(id,source_id,tenant_id,project_id) on delete restrict,
  constraint data_source_webhook_endpoints_identity_unique162 unique(source_resource_id),
  constraint data_source_webhook_endpoints_scope_unique162
    unique(id,tenant_id,project_id,source_id,source_resource_id),
  constraint data_source_webhook_endpoints_provider_check162
    check(provider_key~'^[a-z][a-z0-9_]{1,79}$' and resource_type~'^[a-z][a-z0-9_]{1,79}$'),
  constraint data_source_webhook_endpoints_status_check162
    check(status in ('disabled','enabled','revoked')),
  constraint data_source_webhook_endpoints_credential_check162
    check(credential_version>0 and credential_revision>0 and fence>0)
);

create index data_source_webhook_endpoints_source162
on public.data_source_webhook_endpoints(tenant_id,project_id,source_id);

create trigger set_data_source_webhook_endpoints_updated_at162
before update on public.data_source_webhook_endpoints
for each row execute function public.set_updated_at();

create table public.data_source_webhook_events (
  id uuid primary key default gen_random_uuid(),
  endpoint_id uuid not null,
  tenant_id integer not null,
  project_id uuid not null,
  source_id uuid not null,
  source_resource_id uuid not null,
  actor_user_id integer not null,
  provider_key text not null,
  resource_type text not null,
  endpoint_fence bigint not null,
  credential_id uuid not null,
  credential_version integer not null,
  credential_revision bigint not null,
  provider_event_id text not null,
  event_type text not null,
  delivery_kind text not null,
  occurred_at timestamptz not null,
  received_at timestamptz not null default now(),
  payload_hash text not null,
  normalized_payload jsonb not null,
  status text not null default 'pending',
  attempts integer not null default 0,
  next_attempt_at timestamptz not null default now(),
  lease_token uuid,
  lease_owner text,
  lease_expires_at timestamptz,
  lease_fence bigint not null default 0,
  ingestion_run_id uuid references public.data_source_ingestion_runs(id) on delete restrict,
  result_revision bigint,
  error_category text,
  diagnostic_metadata jsonb not null default '{}'::jsonb,
  processed_at timestamptz,
  retention_until timestamptz not null default now()+interval '30 days',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint data_source_webhook_events_endpoint_fk162
    foreign key(endpoint_id,tenant_id,project_id,source_id,source_resource_id)
    references public.data_source_webhook_endpoints(id,tenant_id,project_id,source_id,source_resource_id)
    on delete restrict,
  constraint data_source_webhook_events_provider_identity162
    unique(endpoint_id,provider_event_id),
  constraint data_source_webhook_events_actor_fk162
    foreign key(actor_user_id,tenant_id) references public.users(id,tenant_id) on delete restrict,
  constraint data_source_webhook_events_provider_check162
    check(provider_key~'^[a-z][a-z0-9_]{1,79}$' and resource_type~'^[a-z][a-z0-9_]{1,79}$'),
  constraint data_source_webhook_events_ids_check162 check(
    length(provider_event_id) between 8 and 255 and length(event_type) between 3 and 80
  ),
  constraint data_source_webhook_events_kind_check162
    check(delivery_kind in ('authoritative_record','change_notification')),
  constraint data_source_webhook_events_hash_check162 check(payload_hash~'^[0-9a-f]{64}$'),
  constraint data_source_webhook_events_payload_check162 check(
    jsonb_typeof(normalized_payload)='object'
    and octet_length(normalized_payload::text)<=65536
    and not normalized_payload ?| array['secret','authorization','headers','credential']
  ),
  constraint data_source_webhook_events_status_check162
    check(status in ('pending','leased','retry','processed','dead_letter')),
  constraint data_source_webhook_events_attempt_check162 check(attempts between 0 and 8),
  constraint data_source_webhook_events_fence_check162
    check(endpoint_fence>0 and credential_version>0 and credential_revision>0 and lease_fence>=0),
  constraint data_source_webhook_events_error_check162
    check(error_category is null or error_category~'^[a-z][a-z0-9_]{1,79}$'),
  constraint data_source_webhook_events_diagnostic_check162 check(
    jsonb_typeof(diagnostic_metadata)='object'
    and not diagnostic_metadata ?| array['credential','token','secret','authorization','headers','url','payload']
  ),
  constraint data_source_webhook_events_state_check162 check(
    (status='leased' and lease_token is not null and lease_owner is not null
      and lease_expires_at is not null and processed_at is null)
    or (status in ('pending','retry') and lease_token is null and lease_owner is null
      and lease_expires_at is null and processed_at is null)
    or (status in ('processed','dead_letter') and lease_token is null and lease_owner is null
      and lease_expires_at is null and processed_at is not null)
  ),
  constraint data_source_webhook_events_result_check162
    check(result_revision is null or result_revision>=0),
  constraint data_source_webhook_events_retention_check162
    check(retention_until>=received_at+interval '1 day')
);

create index data_source_webhook_events_due162
on public.data_source_webhook_events(next_attempt_at,received_at)
where status in ('pending','retry');
create index data_source_webhook_events_lease162
on public.data_source_webhook_events(lease_expires_at) where status='leased';
create index data_source_webhook_events_scope162
on public.data_source_webhook_events(tenant_id,project_id,source_id,received_at desc);

create trigger set_data_source_webhook_events_updated_at162
before update on public.data_source_webhook_events
for each row execute function public.set_updated_at();

alter table public.data_source_resources
  add column reconciliation_requested_at timestamptz,
  add column reconciliation_reason text,
  add constraint data_source_resources_reconciliation_reason_check162
    check(reconciliation_reason is null or reconciliation_reason in ('webhook_notification'));

create function public.configure_data_source_webhook162(
  p_tenant_id integer,p_project_id uuid,p_source_id uuid,p_source_resource_id uuid,
  p_actor_user_id integer,p_provider_key text,p_resource_type text,p_enabled boolean,
  p_credential_id uuid,p_credential_version integer,p_credential_revision bigint,
  p_expected_fence bigint default null
) returns public.data_source_webhook_endpoints
language plpgsql security definer set search_path='' as $$
declare v_source public.data_sources;v_resource public.data_source_resources;
declare v_credential public.data_source_credentials;v_endpoint public.data_source_webhook_endpoints;
begin
  select s.* into v_source from public.data_sources s
  join public.builder_projects p on p.id=s.project_id and p.tenant_id=s.tenant_id
  where s.id=p_source_id and s.tenant_id=p_tenant_id and s.project_id=p_project_id
    and s.creator_user_id=p_actor_user_id and s.status='active' and s.source_type='api_provider'
    and s.provider_key=p_provider_key and s.resource_type=p_resource_type
    and p.status<>'archived' and p.draft_schema->>'workspaceKind'='data'
    and exists(select 1 from public.tenant_memberships m where m.tenant_id=p_tenant_id
      and m.user_id=p_actor_user_id and m.status='active' and m.role<>'learner')
  for update of s;
  if not found then raise exception using errcode='42501',message='webhook_source_not_authorized';end if;
  select * into v_resource from public.data_source_resources r
  where (p_source_resource_id is null or r.id=p_source_resource_id)
    and r.tenant_id=p_tenant_id and r.project_id=p_project_id
    and r.source_id=p_source_id and r.resource_key=p_resource_type for update;
  if not found then
    if p_source_resource_id is not null then
      raise exception using errcode='42501',message='webhook_resource_not_authorized';end if;
    insert into public.data_source_resources(tenant_id,project_id,source_id,resource_key)
    values(p_tenant_id,p_project_id,p_source_id,p_resource_type)
    on conflict(tenant_id,project_id,source_id,resource_key) do update set updated_at=now()
    returning * into v_resource;
  end if;
  select * into v_credential from public.data_source_credentials c
  where c.id=p_credential_id and c.tenant_id=p_tenant_id and c.project_id=p_project_id
    and c.source_id=p_source_id and c.provider_key=p_provider_key
    and c.credential_type='webhook_hmac' and c.credential_version=p_credential_version
    and c.source_revision=p_credential_revision and c.status='active'
    and (c.expires_at is null or c.expires_at>now());
  if not found or v_source.active_credential_id<>p_credential_id
     or v_source.credential_revision<>p_credential_revision then
    raise exception using errcode='42501',message='webhook_credential_not_authorized';end if;
  select * into v_endpoint from public.data_source_webhook_endpoints e
    where e.source_resource_id=v_resource.id for update;
  if found then
    if p_expected_fence is null or v_endpoint.fence<>p_expected_fence then
      raise exception using errcode='40001',message='webhook_endpoint_fence_conflict';end if;
    update public.data_source_webhook_endpoints set
      status=case when p_enabled then 'enabled' else 'disabled' end,
      credential_id=p_credential_id,credential_version=p_credential_version,
      credential_revision=p_credential_revision,actor_user_id=p_actor_user_id,fence=fence+1
    where id=v_endpoint.id returning * into v_endpoint;
    update public.data_source_webhook_events set status='dead_letter',processed_at=now(),
      error_category='webhook_endpoint_fenced',lease_token=null,lease_owner=null,lease_expires_at=null
    where endpoint_id=v_endpoint.id and status in ('pending','retry');
  else
    if p_expected_fence is not null then
      raise exception using errcode='40001',message='webhook_endpoint_fence_conflict';end if;
    insert into public.data_source_webhook_endpoints(
      tenant_id,project_id,source_id,source_resource_id,provider_key,resource_type,
      actor_user_id,status,credential_id,credential_version,credential_revision
    ) values(p_tenant_id,p_project_id,p_source_id,v_resource.id,p_provider_key,
      p_resource_type,p_actor_user_id,case when p_enabled then 'enabled' else 'disabled' end,
      p_credential_id,p_credential_version,p_credential_revision) returning * into v_endpoint;
  end if;
  return v_endpoint;
end;
$$;

create function public.get_data_source_webhook_status162(
  p_tenant_id integer,p_project_id uuid,p_source_id uuid,p_actor_user_id integer
) returns table(
  endpoint_id uuid,source_resource_id uuid,status text,fence bigint,
  credential_id uuid,credential_version integer,credential_revision bigint,
  last_received_at timestamptz,last_processed_at timestamptz,
  pending_count bigint,failed_count bigint
) language plpgsql security definer set search_path='' as $$
begin
  if not exists(select 1 from public.data_sources s join public.builder_projects p
    on p.id=s.project_id and p.tenant_id=s.tenant_id
    where s.id=p_source_id and s.tenant_id=p_tenant_id and s.project_id=p_project_id
      and s.creator_user_id=p_actor_user_id and p.status<>'archived'
      and exists(select 1 from public.tenant_memberships m where m.tenant_id=p_tenant_id
        and m.user_id=p_actor_user_id and m.status='active' and m.role<>'learner')) then
    raise exception using errcode='42501',message='webhook_source_not_authorized';end if;
  return query select e.id,e.source_resource_id,e.status,e.fence,e.credential_id,
    e.credential_version,e.credential_revision,
    e.last_received_at,e.last_processed_at,
    count(v.id) filter(where v.status in ('pending','leased','retry')),
    count(v.id) filter(where v.status='dead_letter')
  from public.data_source_webhook_endpoints e left join public.data_source_webhook_events v
    on v.endpoint_id=e.id
  where e.tenant_id=p_tenant_id and e.project_id=p_project_id and e.source_id=p_source_id
  group by e.id;
end;
$$;

create function public.resolve_data_source_webhook162(p_endpoint_id uuid)
returns table(
  endpoint_id uuid,tenant_id integer,project_id uuid,source_id uuid,source_resource_id uuid,
  actor_user_id integer,provider_key text,resource_type text,endpoint_fence bigint,
  credential_id uuid,credential_version integer,credential_revision bigint
) language sql security definer set search_path='' stable as $$
  select e.id,e.tenant_id,e.project_id,e.source_id,e.source_resource_id,e.actor_user_id,
    e.provider_key,e.resource_type,e.fence,e.credential_id,e.credential_version,e.credential_revision
  from public.data_source_webhook_endpoints e join public.data_sources s
    on s.id=e.source_id and s.tenant_id=e.tenant_id and s.project_id=e.project_id
  join public.data_source_credentials c on c.id=e.credential_id and c.source_id=e.source_id
    and c.tenant_id=e.tenant_id and c.project_id=e.project_id
  where e.id=p_endpoint_id and e.status='enabled' and s.status='active'
    and s.active_credential_id=e.credential_id and s.credential_revision=e.credential_revision
    and c.status='active' and c.credential_version=e.credential_version
    and c.source_revision=e.credential_revision and (c.expires_at is null or c.expires_at>now());
$$;

create function public.accept_data_source_webhook_event162(
  p_endpoint_id uuid,p_endpoint_fence bigint,p_credential_id uuid,p_credential_version integer,
  p_credential_revision bigint,p_provider_event_id text,p_event_type text,p_delivery_kind text,
  p_occurred_at timestamptz,p_payload_hash text,p_normalized_payload jsonb
) returns table(event_id uuid,disposition text)
language plpgsql security definer set search_path='' as $$
declare v_endpoint public.data_source_webhook_endpoints;v_event public.data_source_webhook_events;
begin
  select * into v_endpoint from public.data_source_webhook_endpoints e
  where e.id=p_endpoint_id and e.status='enabled' for update;
  if not found or v_endpoint.fence<>p_endpoint_fence or v_endpoint.credential_id<>p_credential_id
     or v_endpoint.credential_version<>p_credential_version
     or v_endpoint.credential_revision<>p_credential_revision then
    raise exception using errcode='42501',message='webhook_endpoint_fenced';end if;
  select * into v_event from public.data_source_webhook_events v
    where v.endpoint_id=p_endpoint_id and v.provider_event_id=p_provider_event_id;
  if found then
    if v_event.payload_hash<>p_payload_hash or v_event.event_type<>p_event_type then
      raise exception using errcode='23505',message='webhook_event_identity_conflict';end if;
    return query select v_event.id,'duplicate'::text;return;
  end if;
  insert into public.data_source_webhook_events(
    endpoint_id,tenant_id,project_id,source_id,source_resource_id,actor_user_id,
    provider_key,resource_type,endpoint_fence,
    credential_id,credential_version,credential_revision,provider_event_id,event_type,
    delivery_kind,occurred_at,payload_hash,normalized_payload
  ) values(v_endpoint.id,v_endpoint.tenant_id,v_endpoint.project_id,v_endpoint.source_id,
    v_endpoint.source_resource_id,v_endpoint.actor_user_id,v_endpoint.provider_key,
    v_endpoint.resource_type,v_endpoint.fence,p_credential_id,p_credential_version,
    p_credential_revision,p_provider_event_id,p_event_type,p_delivery_kind,p_occurred_at,
    p_payload_hash,p_normalized_payload) returning * into v_event;
  update public.data_source_webhook_endpoints set last_received_at=now() where id=v_endpoint.id;
  return query select v_event.id,'accepted'::text;
end;
$$;

create function public.reconcile_expired_webhook_events162(
  p_limit integer default 100,p_now timestamptz default now()
) returns integer language plpgsql security definer set search_path='' as $$
declare v_count integer;
begin
  with expired as (select id from public.data_source_webhook_events
    where status='leased' and lease_expires_at<=p_now order by lease_expires_at
    for update skip locked limit greatest(1,least(p_limit,500)))
  update public.data_source_webhook_events e set status=case
      when attempts>=8 or not exists(select 1 from public.data_source_webhook_endpoints w
        where w.id=e.endpoint_id and w.status='enabled' and w.fence=e.endpoint_fence
          and w.credential_id=e.credential_id and w.credential_revision=e.credential_revision)
      then 'dead_letter' else 'retry' end,
    next_attempt_at=p_now+make_interval(secs=>least(3600,30*(2^least(e.attempts,7)))),
    error_category=case when not exists(select 1 from public.data_source_webhook_endpoints w
      where w.id=e.endpoint_id and w.status='enabled' and w.fence=e.endpoint_fence
        and w.credential_id=e.credential_id and w.credential_revision=e.credential_revision)
      then 'webhook_endpoint_fenced' else 'worker_lease_expired' end,
    processed_at=case when attempts>=8 or not exists(select 1 from public.data_source_webhook_endpoints w
      where w.id=e.endpoint_id and w.status='enabled' and w.fence=e.endpoint_fence
        and w.credential_id=e.credential_id and w.credential_revision=e.credential_revision)
      then p_now else null end,
    lease_token=null,lease_owner=null,lease_expires_at=null where e.id in(select id from expired);
  get diagnostics v_count=row_count;return v_count;
end;
$$;

create function public.claim_data_source_webhook_events162(
  p_worker_id text,p_limit integer default 10,p_lease_seconds integer default 300,
  p_now timestamptz default now()
) returns setof public.data_source_webhook_events
language plpgsql security definer set search_path='' as $$
begin
  return query with candidates as (
    select e.id from public.data_source_webhook_events e
    join public.data_source_webhook_endpoints w on w.id=e.endpoint_id
    join public.data_sources s on s.id=e.source_id and s.tenant_id=e.tenant_id
    join public.data_source_credentials c on c.id=e.credential_id and c.source_id=e.source_id
      and c.tenant_id=e.tenant_id and c.project_id=e.project_id
    where e.status in ('pending','retry') and e.next_attempt_at<=p_now
      and w.status='enabled' and w.fence=e.endpoint_fence and s.status='active'
      and w.credential_id=e.credential_id and w.credential_revision=e.credential_revision
      and s.active_credential_id=e.credential_id and s.credential_revision=e.credential_revision
      and c.status='active' and c.credential_version=e.credential_version
      and c.source_revision=e.credential_revision and (c.expires_at is null or c.expires_at>p_now)
      and not exists(select 1 from public.data_source_webhook_events a
        where a.source_resource_id=e.source_resource_id and a.status='leased')
    order by e.received_at for update of e skip locked limit greatest(1,least(p_limit,50))
  ) update public.data_source_webhook_events e set status='leased',attempts=attempts+1,
      lease_token=gen_random_uuid(),lease_owner=left(p_worker_id,200),
      lease_expires_at=p_now+make_interval(secs=>greatest(60,least(p_lease_seconds,1800))),
      lease_fence=lease_fence+1,error_category=null,diagnostic_metadata='{}'::jsonb
    from candidates c where e.id=c.id returning e.*;
end;
$$;

create function public.heartbeat_data_source_webhook_event162(
  p_event_id uuid,p_lease_token uuid,p_lease_fence bigint,p_lease_seconds integer default 300
) returns boolean language plpgsql security definer set search_path='' as $$
begin
  update public.data_source_webhook_events set lease_expires_at=now()+
    make_interval(secs=>greatest(60,least(p_lease_seconds,1800)))
  where id=p_event_id and status='leased' and lease_token=p_lease_token and lease_fence=p_lease_fence;
  return found;
end;
$$;

create function public.attach_webhook_event_ingestion162(
  p_event_id uuid,p_lease_token uuid,p_lease_fence bigint,p_ingestion_run_id uuid
) returns boolean language plpgsql security definer set search_path='' as $$
begin
  update public.data_source_webhook_events e set ingestion_run_id=p_ingestion_run_id
  where e.id=p_event_id and e.status='leased' and e.lease_token=p_lease_token
    and e.lease_fence=p_lease_fence and (e.ingestion_run_id is null or e.ingestion_run_id=p_ingestion_run_id)
    and exists(select 1 from public.data_source_ingestion_runs r where r.id=p_ingestion_run_id
      and r.tenant_id=e.tenant_id and r.project_id=e.project_id and r.source_id=e.source_id
      and r.source_resource_id=e.source_resource_id);
  return found;
end;
$$;

create function public.complete_data_source_webhook_event162(
  p_event_id uuid,p_lease_token uuid,p_lease_fence bigint,p_result_revision bigint
) returns boolean language plpgsql security definer set search_path='' as $$
declare v_endpoint_id uuid;
begin
  update public.data_source_webhook_events e set status='processed',result_revision=p_result_revision,
    processed_at=now(),lease_token=null,lease_owner=null,lease_expires_at=null
  where e.id=p_event_id and e.status='leased' and e.lease_token=p_lease_token
    and e.lease_fence=p_lease_fence and exists(select 1 from public.data_source_webhook_endpoints w
      join public.data_sources s on s.id=w.source_id and s.tenant_id=w.tenant_id
      where w.id=e.endpoint_id and w.status='enabled' and w.fence=e.endpoint_fence
        and w.credential_id=e.credential_id and w.credential_revision=e.credential_revision
        and s.status='active' and s.active_credential_id=e.credential_id
        and s.credential_revision=e.credential_revision)
  returning endpoint_id into v_endpoint_id;
  if not found then return false;end if;
  update public.data_source_webhook_endpoints set last_processed_at=now() where id=v_endpoint_id;
  return true;
end;
$$;

create function public.fail_data_source_webhook_event162(
  p_event_id uuid,p_lease_token uuid,p_lease_fence bigint,p_error_category text,
  p_transient boolean,p_diagnostic_metadata jsonb default '{}'::jsonb
) returns boolean language plpgsql security definer set search_path='' as $$
begin
  if p_error_category!~'^[a-z][a-z0-9_]{1,79}$' or jsonb_typeof(p_diagnostic_metadata)<>'object'
     or p_diagnostic_metadata ?| array['credential','token','secret','authorization','headers','url','payload'] then
    raise exception using errcode='22023',message='webhook_failure_metadata_invalid';end if;
  update public.data_source_webhook_events set
    status=case when p_transient and attempts<8 then 'retry' else 'dead_letter' end,
    next_attempt_at=now()+make_interval(secs=>least(3600,30*(2^least(attempts,7)))),
    error_category=p_error_category,diagnostic_metadata=p_diagnostic_metadata,
    processed_at=case when p_transient and attempts<8 then null else now() end,
    lease_token=null,lease_owner=null,lease_expires_at=null
  where id=p_event_id and status='leased' and lease_token=p_lease_token and lease_fence=p_lease_fence;
  return found;
end;
$$;

create function public.request_webhook_reconciliation162(
  p_event_id uuid,p_lease_token uuid,p_lease_fence bigint
) returns bigint language plpgsql security definer set search_path='' as $$
declare v_event public.data_source_webhook_events;v_revision bigint;
begin
  select * into v_event from public.data_source_webhook_events where id=p_event_id
    and status='leased' and lease_token=p_lease_token and lease_fence=p_lease_fence for update;
  if not found then raise exception using errcode='40001',message='webhook_event_lease_lost';end if;
  update public.data_source_resources set reconciliation_requested_at=coalesce(reconciliation_requested_at,now()),
    reconciliation_reason='webhook_notification' where id=v_event.source_resource_id
    returning committed_revision into v_revision;
  update public.data_source_sync_schedules set next_due_at=least(coalesce(next_due_at,now()),now()),
    status=case when enabled and status<>'leased' then 'idle' else status end
    where source_resource_id=v_event.source_resource_id and enabled;
  return v_revision;
end;
$$;

create function public.retry_data_source_webhook_event162(
  p_tenant_id integer,p_project_id uuid,p_source_id uuid,p_event_id uuid,p_actor_user_id integer
) returns boolean language plpgsql security definer set search_path='' as $$
begin
  if not exists(select 1 from public.data_sources s join public.builder_projects p
    on p.id=s.project_id and p.tenant_id=s.tenant_id where s.id=p_source_id
    and s.tenant_id=p_tenant_id and s.project_id=p_project_id and s.creator_user_id=p_actor_user_id
    and exists(select 1 from public.tenant_memberships m where m.tenant_id=p_tenant_id
      and m.user_id=p_actor_user_id and m.status='active' and m.role<>'learner')) then
    raise exception using errcode='42501',message='webhook_source_not_authorized';end if;
  update public.data_source_webhook_events set status='retry',next_attempt_at=now(),processed_at=null,
    error_category=null,diagnostic_metadata='{}'::jsonb where id=p_event_id and tenant_id=p_tenant_id
    and project_id=p_project_id and source_id=p_source_id and status='dead_letter' and attempts<8;
  return found;
end;
$$;

create function public.revoke_data_source_webhook162(
  p_tenant_id integer,p_project_id uuid,p_source_id uuid,p_actor_user_id integer,
  p_expected_fence bigint
) returns public.data_source_webhook_endpoints
language plpgsql security definer set search_path='' as $$
declare v_endpoint public.data_source_webhook_endpoints;
begin
  if not exists(select 1 from public.data_sources s where s.id=p_source_id
    and s.tenant_id=p_tenant_id and s.project_id=p_project_id and s.creator_user_id=p_actor_user_id
    and exists(select 1 from public.tenant_memberships m where m.tenant_id=p_tenant_id
      and m.user_id=p_actor_user_id and m.status='active' and m.role<>'learner')) then
    raise exception using errcode='42501',message='webhook_source_not_authorized';end if;
  update public.data_source_webhook_endpoints set status='revoked',fence=fence+1
  where tenant_id=p_tenant_id and project_id=p_project_id and source_id=p_source_id
    and fence=p_expected_fence returning * into v_endpoint;
  if not found then raise exception using errcode='40001',message='webhook_endpoint_fence_conflict';end if;
  update public.data_source_webhook_events set status='dead_letter',processed_at=now(),
    error_category='webhook_endpoint_fenced',lease_token=null,lease_owner=null,lease_expires_at=null
  where endpoint_id=v_endpoint.id and status in ('pending','retry');
  return v_endpoint;
end;
$$;

create function public.cleanup_data_source_webhook_events162(
  p_limit integer default 1000,p_now timestamptz default now()
) returns integer language plpgsql security definer set search_path='' as $$
declare v_count integer;
begin
  with doomed as(select id from public.data_source_webhook_events
    where status in ('processed','dead_letter') and retention_until<=p_now
    order by retention_until limit greatest(1,least(p_limit,5000)))
  delete from public.data_source_webhook_events where id in(select id from doomed);
  get diagnostics v_count=row_count;return v_count;
end;
$$;

alter table public.data_source_webhook_endpoints enable row level security;
alter table public.data_source_webhook_events enable row level security;

revoke all on public.data_source_webhook_endpoints from public,anon,authenticated;
revoke all on public.data_source_webhook_events from public,anon,authenticated;
revoke all on function public.configure_data_source_webhook162(integer,uuid,uuid,uuid,integer,text,text,boolean,uuid,integer,bigint,bigint) from public,anon,authenticated;
revoke all on function public.get_data_source_webhook_status162(integer,uuid,uuid,integer) from public,anon,authenticated;
revoke all on function public.resolve_data_source_webhook162(uuid) from public,anon,authenticated;
revoke all on function public.accept_data_source_webhook_event162(uuid,bigint,uuid,integer,bigint,text,text,text,timestamptz,text,jsonb) from public,anon,authenticated;
revoke all on function public.reconcile_expired_webhook_events162(integer,timestamptz) from public,anon,authenticated;
revoke all on function public.claim_data_source_webhook_events162(text,integer,integer,timestamptz) from public,anon,authenticated;
revoke all on function public.heartbeat_data_source_webhook_event162(uuid,uuid,bigint,integer) from public,anon,authenticated;
revoke all on function public.attach_webhook_event_ingestion162(uuid,uuid,bigint,uuid) from public,anon,authenticated;
revoke all on function public.complete_data_source_webhook_event162(uuid,uuid,bigint,bigint) from public,anon,authenticated;
revoke all on function public.fail_data_source_webhook_event162(uuid,uuid,bigint,text,boolean,jsonb) from public,anon,authenticated;
revoke all on function public.request_webhook_reconciliation162(uuid,uuid,bigint) from public,anon,authenticated;
revoke all on function public.retry_data_source_webhook_event162(integer,uuid,uuid,uuid,integer) from public,anon,authenticated;
revoke all on function public.revoke_data_source_webhook162(integer,uuid,uuid,integer,bigint) from public,anon,authenticated;
revoke all on function public.cleanup_data_source_webhook_events162(integer,timestamptz) from public,anon,authenticated;

grant select,insert,update,delete on public.data_source_webhook_endpoints to service_role;
grant select,insert,update,delete on public.data_source_webhook_events to service_role;
grant execute on function public.configure_data_source_webhook162(integer,uuid,uuid,uuid,integer,text,text,boolean,uuid,integer,bigint,bigint) to service_role;
grant execute on function public.get_data_source_webhook_status162(integer,uuid,uuid,integer) to service_role;
grant execute on function public.resolve_data_source_webhook162(uuid) to service_role;
grant execute on function public.accept_data_source_webhook_event162(uuid,bigint,uuid,integer,bigint,text,text,text,timestamptz,text,jsonb) to service_role;
grant execute on function public.reconcile_expired_webhook_events162(integer,timestamptz) to service_role;
grant execute on function public.claim_data_source_webhook_events162(text,integer,integer,timestamptz) to service_role;
grant execute on function public.heartbeat_data_source_webhook_event162(uuid,uuid,bigint,integer) to service_role;
grant execute on function public.attach_webhook_event_ingestion162(uuid,uuid,bigint,uuid) to service_role;
grant execute on function public.complete_data_source_webhook_event162(uuid,uuid,bigint,bigint) to service_role;
grant execute on function public.fail_data_source_webhook_event162(uuid,uuid,bigint,text,boolean,jsonb) to service_role;
grant execute on function public.request_webhook_reconciliation162(uuid,uuid,bigint) to service_role;
grant execute on function public.retry_data_source_webhook_event162(integer,uuid,uuid,uuid,integer) to service_role;
grant execute on function public.revoke_data_source_webhook162(integer,uuid,uuid,integer,bigint) to service_role;
grant execute on function public.cleanup_data_source_webhook_events162(integer,timestamptz) to service_role;

update public.application_schema_state
set schema_version=162,applied_at=now()
where contract_key='core' and schema_version=161;

do $$
begin
  if not exists(select 1 from public.application_schema_state
    where contract_key='core' and schema_version=162) then
    raise exception using errcode='P0001',message='migration_162_schema_transition_failed';
  end if;
end;
$$;

notify pgrst,'reload schema';
commit;
