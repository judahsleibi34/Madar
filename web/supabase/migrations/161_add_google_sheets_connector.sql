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
    raise exception using errcode='P0001',message='migration_161_schema_state_missing';
  end if;
  if v_schema_version<>160 then
    raise exception using errcode='P0001',
      message=format('migration_161_expected_schema_160_got_%s',v_schema_version);
  end if;
end;
$$;

create table public.data_source_oauth_transactions (
  id uuid primary key default gen_random_uuid(),
  state_hash text not null,
  tenant_id integer not null,
  project_id uuid not null,
  source_id uuid not null,
  actor_user_id integer not null,
  provider_key text not null,
  redirect_uri text not null,
  expires_at timestamptz not null,
  consumed_at timestamptz,
  created_at timestamptz not null default now(),
  constraint data_source_oauth_transactions_source_fk161
    foreign key(source_id,tenant_id,project_id)
    references public.data_sources(id,tenant_id,project_id) on delete cascade,
  constraint data_source_oauth_transactions_actor_fk161
    foreign key(actor_user_id,tenant_id)
    references public.users(id,tenant_id) on delete restrict,
  constraint data_source_oauth_transactions_state_unique161 unique(state_hash),
  constraint data_source_oauth_transactions_hash_check161
    check(state_hash~'^[0-9a-f]{64}$'),
  constraint data_source_oauth_transactions_provider_check161
    check(provider_key='google_sheets'),
  constraint data_source_oauth_transactions_redirect_check161
    check(length(redirect_uri) between 12 and 2048),
  constraint data_source_oauth_transactions_expiry_check161
    check(expires_at>created_at and expires_at<=created_at+interval '15 minutes')
);

create unique index data_source_oauth_one_pending161
on public.data_source_oauth_transactions(source_id,provider_key)
where consumed_at is null;

create index data_source_oauth_expiry161
on public.data_source_oauth_transactions(expires_at)
where consumed_at is null;

create table public.google_sheets_source_mappings (
  source_id uuid primary key,
  tenant_id integer not null,
  project_id uuid not null,
  spreadsheet_id text not null,
  spreadsheet_title text not null default '',
  sheet_id bigint not null,
  sheet_title text not null,
  header_row integer not null default 1,
  selected_columns jsonb not null,
  record_id_column text not null,
  resource_key text not null,
  max_rows integer not null default 10000,
  max_columns integer not null default 128,
  mapping_revision bigint not null default 1,
  last_snapshot_fingerprint text,
  last_validated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint google_sheets_source_mappings_source_fk161
    foreign key(source_id,tenant_id,project_id)
    references public.data_sources(id,tenant_id,project_id) on delete cascade,
  constraint google_sheets_mapping_spreadsheet_check161
    check(spreadsheet_id~'^[A-Za-z0-9_-]{20,200}$'),
  constraint google_sheets_mapping_sheet_check161 check(sheet_id>=0),
  constraint google_sheets_mapping_header_check161 check(header_row between 1 and 1000),
  constraint google_sheets_mapping_columns_check161 check(
    jsonb_typeof(selected_columns)='array' and jsonb_array_length(selected_columns) between 1 and 128
  ),
  constraint google_sheets_mapping_names_check161 check(
    length(spreadsheet_title)<=255 and length(sheet_title) between 1 and 255
    and length(record_id_column) between 1 and 255
  ),
  constraint google_sheets_mapping_resource_check161
    check(resource_key~'^gs_[0-9a-f]{48}$'),
  constraint google_sheets_mapping_bounds_check161
    check(max_rows between 1 and 10000 and max_columns between 1 and 128),
  constraint google_sheets_mapping_revision_check161 check(mapping_revision>0),
  constraint google_sheets_mapping_fingerprint_check161 check(
    last_snapshot_fingerprint is null or last_snapshot_fingerprint~'^[0-9a-f]{64}$'
  )
);

create trigger set_google_sheets_source_mappings_updated_at161
before update on public.google_sheets_source_mappings
for each row execute function public.set_updated_at();

create function public.begin_data_source_oauth161(
  p_tenant_id integer,p_project_id uuid,p_source_id uuid,p_actor_user_id integer,
  p_provider_key text,p_state_hash text,p_redirect_uri text,p_expires_at timestamptz
) returns public.data_source_oauth_transactions
language plpgsql security definer set search_path='' as $$
declare v_source public.data_sources;v_result public.data_source_oauth_transactions;
begin
  if p_provider_key<>'google_sheets' or p_state_hash!~'^[0-9a-f]{64}$'
     or p_expires_at<=now() or p_expires_at>now()+interval '15 minutes' then
    raise exception using errcode='22023',message='data_source_oauth_request_invalid';end if;
  select s.* into v_source from public.data_sources s
  join public.builder_projects p on p.id=s.project_id and p.tenant_id=s.tenant_id
  where s.id=p_source_id and s.tenant_id=p_tenant_id and s.project_id=p_project_id
    and s.creator_user_id=p_actor_user_id and s.source_type='api_provider'
    and s.provider_key=p_provider_key and s.status='active' and p.status<>'archived'
    and p.draft_schema->>'workspaceKind'='data'
    and exists(select 1 from public.tenant_memberships m where m.tenant_id=p_tenant_id
      and m.user_id=p_actor_user_id and m.status='active' and m.role<>'learner')
  for update of s;
  if not found then raise exception using errcode='42501',message='data_source_oauth_not_authorized';end if;
  update public.data_source_oauth_transactions set consumed_at=now()
    where source_id=p_source_id and provider_key=p_provider_key and consumed_at is null;
  insert into public.data_source_oauth_transactions(
    state_hash,tenant_id,project_id,source_id,actor_user_id,provider_key,redirect_uri,expires_at
  ) values(p_state_hash,p_tenant_id,p_project_id,p_source_id,p_actor_user_id,p_provider_key,
    p_redirect_uri,p_expires_at) returning * into v_result;
  return v_result;
end;
$$;

create function public.consume_data_source_oauth161(
  p_state_hash text,p_provider_key text,p_redirect_uri text
) returns public.data_source_oauth_transactions
language plpgsql security definer set search_path='' as $$
declare v_result public.data_source_oauth_transactions;
begin
  update public.data_source_oauth_transactions set consumed_at=now()
  where state_hash=p_state_hash and provider_key=p_provider_key
    and redirect_uri=p_redirect_uri and consumed_at is null and expires_at>now()
  returning * into v_result;
  if not found then raise exception using errcode='P0001',message='data_source_oauth_state_invalid';end if;
  return v_result;
end;
$$;

create function public.save_google_sheets_mapping161(
  p_tenant_id integer,p_project_id uuid,p_source_id uuid,p_actor_user_id integer,
  p_spreadsheet_id text,p_spreadsheet_title text,p_sheet_id bigint,p_sheet_title text,
  p_header_row integer,p_selected_columns jsonb,p_record_id_column text,p_resource_key text,
  p_expected_revision bigint default null
) returns public.google_sheets_source_mappings
language plpgsql security definer set search_path='' as $$
declare v_source public.data_sources;v_existing public.google_sheets_source_mappings;
declare v_result public.google_sheets_source_mappings;
begin
  select s.* into v_source from public.data_sources s
  join public.builder_projects p on p.id=s.project_id and p.tenant_id=s.tenant_id
  where s.id=p_source_id and s.tenant_id=p_tenant_id and s.project_id=p_project_id
    and s.creator_user_id=p_actor_user_id and s.source_type='api_provider'
    and s.provider_key='google_sheets' and s.status='active' and p.status<>'archived'
    and p.draft_schema->>'workspaceKind'='data'
    and exists(select 1 from public.tenant_memberships m where m.tenant_id=p_tenant_id
      and m.user_id=p_actor_user_id and m.status='active' and m.role<>'learner')
  for update of s;
  if not found then raise exception using errcode='42501',message='google_sheets_mapping_not_authorized';end if;
  select * into v_existing from public.google_sheets_source_mappings where source_id=p_source_id for update;
  if found and p_expected_revision is not null and v_existing.mapping_revision<>p_expected_revision then
    raise exception using errcode='40001',message='google_sheets_mapping_conflict';end if;
  insert into public.google_sheets_source_mappings(
    source_id,tenant_id,project_id,spreadsheet_id,spreadsheet_title,sheet_id,sheet_title,
    header_row,selected_columns,record_id_column,resource_key
  ) values(p_source_id,p_tenant_id,p_project_id,p_spreadsheet_id,left(p_spreadsheet_title,255),
    p_sheet_id,p_sheet_title,p_header_row,p_selected_columns,p_record_id_column,p_resource_key)
  on conflict(source_id) do update set spreadsheet_id=excluded.spreadsheet_id,
    spreadsheet_title=excluded.spreadsheet_title,sheet_id=excluded.sheet_id,
    sheet_title=excluded.sheet_title,header_row=excluded.header_row,
    selected_columns=excluded.selected_columns,record_id_column=excluded.record_id_column,
    resource_key=excluded.resource_key,mapping_revision=google_sheets_source_mappings.mapping_revision+1,
    last_snapshot_fingerprint=null,last_validated_at=null
  returning * into v_result;
  return v_result;
end;
$$;

create function public.complete_noop_source_ingestion161(
  p_tenant_id integer,p_project_id uuid,p_source_id uuid,p_actor_user_id integer,
  p_ingestion_run_id uuid,p_lease_token uuid,p_next_cursor text,
  p_credential_id uuid,p_credential_version integer,p_credential_revision bigint
) returns table(dataset_id uuid,source_resource_id uuid,committed_revision bigint,
  ingestion_run_id uuid,ingestion_status text,noop boolean)
language plpgsql security definer set search_path='' as $$
declare v_run public.data_source_ingestion_runs;v_resource public.data_source_resources;
declare v_source public.data_sources;v_credential public.data_source_credentials;
begin
  select * into v_run from public.data_source_ingestion_runs r
  where r.id=p_ingestion_run_id and r.tenant_id=p_tenant_id and r.project_id=p_project_id
    and r.source_id=p_source_id and r.initiated_by_user_id=p_actor_user_id for update;
  if not found or v_run.status<>'processing' or v_run.ingestion_kind<>'incremental'
     or v_run.reconciliation_state<>'active' or v_run.lease_token is distinct from p_lease_token then
    raise exception using errcode='P0001',message='ingestion_lease_lost';end if;
  select * into v_resource from public.data_source_resources r
  where r.id=v_run.source_resource_id and r.tenant_id=p_tenant_id
    and r.project_id=p_project_id and r.source_id=p_source_id for update;
  if not found or v_resource.dataset_id is null
     or v_resource.committed_cursor is distinct from v_run.expected_cursor
     or p_next_cursor is null or length(p_next_cursor)>1024 then
    raise exception using errcode='P0001',message='google_sheets_noop_lineage_invalid';end if;
  select * into v_source from public.data_sources s where s.id=p_source_id
    and s.tenant_id=p_tenant_id and s.project_id=p_project_id for update;
  select * into v_credential from public.data_source_credentials c
  where c.id=p_credential_id and c.source_id=p_source_id and c.tenant_id=p_tenant_id
    and c.project_id=p_project_id and c.credential_version=p_credential_version
    and c.status='active';
  if v_source.credential_revision<>p_credential_revision
     or v_source.active_credential_id is distinct from p_credential_id
     or v_credential.id is null then
    raise exception using errcode='P0001',message='provider_credentials_revoked';end if;
  update public.data_source_resources set committed_cursor=p_next_cursor,updated_at=now()
  where id=v_resource.id;
  update public.data_source_ingestion_runs set status='succeeded',completed_at=now(),
    result_dataset_id=v_resource.dataset_id,committed_revision=v_resource.committed_revision,
    next_cursor=p_next_cursor,reconciliation_state='resolved',reconciliation_code='no_changes',
    lease_token=null,lease_owner=null,lease_expires_at=null,heartbeat_at=now()
  where id=v_run.id;
  return query select v_resource.dataset_id,v_resource.id,v_resource.committed_revision,
    v_run.id,'succeeded'::text,true;
end;
$$;

alter table public.data_source_oauth_transactions enable row level security;
alter table public.google_sheets_source_mappings enable row level security;
revoke all on public.data_source_oauth_transactions,public.google_sheets_source_mappings
from public,anon,authenticated;
grant select,insert,update on public.data_source_oauth_transactions to service_role;
grant select,insert,update on public.google_sheets_source_mappings to service_role;

do $$
declare v_signature text;
begin
  foreach v_signature in array array[
    'begin_data_source_oauth161(integer,uuid,uuid,integer,text,text,text,timestamp with time zone)',
    'consume_data_source_oauth161(text,text,text)',
    'save_google_sheets_mapping161(integer,uuid,uuid,integer,text,text,bigint,text,integer,jsonb,text,text,bigint)',
    'complete_noop_source_ingestion161(integer,uuid,uuid,integer,uuid,uuid,text,uuid,integer,bigint)'
  ] loop
    execute format('revoke all on function public.%s from public,anon,authenticated',v_signature);
    execute format('grant execute on function public.%s to service_role',v_signature);
  end loop;
end;
$$;

update public.application_schema_state set schema_version=161,applied_at=now()
where contract_key='core';

do $$
begin
  if (select schema_version from public.application_schema_state where contract_key='core')<>161 then
    raise exception using errcode='P0001',message='migration_161_postcondition_failed';
  end if;
end;
$$;

notify pgrst,'reload schema';
commit;
