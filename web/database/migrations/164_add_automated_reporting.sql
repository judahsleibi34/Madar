begin;

do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version into v_schema_version from public.application_schema_state
  where contract_key='core' for update;
  if v_schema_version is null then
    raise exception using errcode='P0001',message='migration_164_schema_state_missing';
  end if;
  if v_schema_version<>163 then
    raise exception using errcode='P0001',message=format('migration_164_expected_schema_163_got_%s',v_schema_version);
  end if;
end;
$$;

alter table public.bi_dashboards
  add column auto_refresh_enabled boolean not null default false;

create table public.bi_report_schedules (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  project_id uuid not null,
  creator_user_id integer not null,
  dashboard_id uuid not null,
  name text not null,
  cadence text not null,
  timezone text not null,
  local_time time without time zone not null,
  weekday smallint,
  month_day smallint,
  enabled boolean not null default true,
  require_ready_checkpoints boolean not null default false,
  next_run_at timestamptz not null,
  last_attempted_at timestamptz,
  last_successful_at timestamptz,
  last_failure_code text,
  revision bigint not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint bi_report_schedules_project_fk164 foreign key(project_id,tenant_id)
    references public.builder_projects(id,tenant_id) on delete cascade,
  constraint bi_report_schedules_creator_fk164 foreign key(creator_user_id,tenant_id)
    references public.users(id,tenant_id) on delete restrict,
  constraint bi_report_schedules_dashboard_fk164 foreign key(dashboard_id,tenant_id,project_id)
    references public.bi_dashboards(id,tenant_id,project_id) on delete cascade,
  constraint bi_report_schedules_name_check160 check(length(btrim(name)) between 1 and 120),
  constraint bi_report_schedules_cadence_check160 check(cadence in ('daily','weekly','monthly')),
  constraint bi_report_schedules_timezone_check160 check(length(timezone) between 1 and 64 and timezone~'^[A-Za-z0-9_+./-]+$'),
  constraint bi_report_schedules_weekday_check160 check(
    (cadence='weekly' and weekday between 0 and 6) or (cadence<>'weekly' and weekday is null)),
  constraint bi_report_schedules_month_day_check160 check(
    (cadence='monthly' and month_day between 1 and 31) or (cadence<>'monthly' and month_day is null)),
  constraint bi_report_schedules_revision_check160 check(revision>0),
  constraint bi_report_schedules_scope_unique160 unique(id,tenant_id,project_id)
);

create index bi_report_schedules_due160 on public.bi_report_schedules(next_run_at,id) where enabled;
create index bi_report_schedules_project160 on public.bi_report_schedules(tenant_id,project_id,creator_user_id,updated_at desc);
create trigger set_bi_report_schedules_updated_at160 before update on public.bi_report_schedules
for each row execute function public.set_updated_at();

create table public.bi_report_runs (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  project_id uuid not null,
  creator_user_id integer not null,
  dashboard_id uuid,
  schedule_id uuid,
  dashboard_revision bigint not null,
  trigger_type text not null,
  due_slot timestamptz,
  deduplication_key text not null,
  status text not null default 'queued',
  definition_snapshot jsonb not null,
  version_vector jsonb not null,
  result_snapshot jsonb,
  warnings jsonb not null default '[]'::jsonb,
  artifact_storage_key text,
  artifact_filename text,
  artifact_content_type text,
  artifact_size_bytes integer,
  artifact_sha256 text,
  available_at timestamptz not null default now(),
  attempts smallint not null default 0,
  max_attempts smallint not null default 3,
  lease_owner text,
  lease_token uuid,
  lease_fence bigint not null default 0,
  lease_expires_at timestamptz,
  last_heartbeat_at timestamptz,
  error_code text,
  started_at timestamptz,
  completed_at timestamptz,
  archived_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint bi_report_runs_project_fk164 foreign key(project_id,tenant_id)
    references public.builder_projects(id,tenant_id) on delete cascade,
  constraint bi_report_runs_creator_fk164 foreign key(creator_user_id,tenant_id)
    references public.users(id,tenant_id) on delete restrict,
  constraint bi_report_runs_dashboard_fk164 foreign key(dashboard_id)
    references public.bi_dashboards(id) on delete set null,
  constraint bi_report_runs_schedule_fk164 foreign key(schedule_id)
    references public.bi_report_schedules(id) on delete set null,
  constraint bi_report_runs_trigger_check160 check(trigger_type in ('manual','scheduled','data_refresh')),
  constraint bi_report_runs_status_check160 check(status in
    ('queued','running','completed','failed','retry_pending','needs_attention','cancelled','skipped')),
  constraint bi_report_runs_dedupe_check160 check(length(deduplication_key) between 16 and 200),
  constraint bi_report_runs_snapshot_check160 check(
    jsonb_typeof(definition_snapshot)='object' and octet_length(definition_snapshot::text)<=262144
    and jsonb_typeof(version_vector)='array' and octet_length(version_vector::text)<=131072
    and (result_snapshot is null or jsonb_typeof(result_snapshot)='object' and octet_length(result_snapshot::text)<=524288)
    and jsonb_typeof(warnings)='array' and octet_length(warnings::text)<=65536),
  constraint bi_report_runs_attempt_check160 check(attempts between 0 and 3 and max_attempts between 1 and 3),
  constraint bi_report_runs_lease_check160 check(
    (status='running' and lease_owner is not null and lease_token is not null and lease_expires_at is not null)
    or (status<>'running')),
  constraint bi_report_runs_artifact_check160 check(
    (artifact_storage_key is null and artifact_filename is null and artifact_content_type is null
      and artifact_size_bytes is null and artifact_sha256 is null)
    or (artifact_storage_key~'^reports/tenant_[0-9]+/[0-9a-f-]{36}/[0-9a-f]{64}\.csv$'
      and artifact_filename~'^[A-Za-z0-9._-]{1,160}\.csv$'
      and artifact_content_type='text/csv'
      and artifact_size_bytes between 1 and 1048576
      and artifact_sha256~'^[0-9a-f]{64}$')),
  constraint bi_report_runs_completed_artifact160 check(status<>'completed' or artifact_storage_key is not null),
  constraint bi_report_runs_dedupe_unique160 unique(deduplication_key),
  constraint bi_report_runs_scope_unique160 unique(id,tenant_id,project_id)
);

create index bi_report_runs_claim160 on public.bi_report_runs(available_at,created_at,id)
where status in ('queued','retry_pending');
create index bi_report_runs_project160 on public.bi_report_runs(tenant_id,project_id,creator_user_id,created_at desc);
create index bi_report_runs_schedule160 on public.bi_report_runs(schedule_id,due_slot desc) where schedule_id is not null;
create trigger set_bi_report_runs_updated_at160 before update on public.bi_report_runs
for each row execute function public.set_updated_at();

alter table public.bi_report_schedules enable row level security;
alter table public.bi_report_runs enable row level security;
revoke all on public.bi_report_schedules,public.bi_report_runs from public,anon,authenticated;
grant select,insert,update,delete on public.bi_report_schedules,public.bi_report_runs to service_role;

create function public.configure_bi_dashboard_refresh164(
  p_tenant_id integer,p_project_id uuid,p_creator_user_id integer,p_dashboard_id uuid,
  p_expected_revision bigint,p_enabled boolean
) returns public.bi_dashboards language plpgsql security definer set search_path='' as $$
declare d public.bi_dashboards;
begin
  select * into d from public.bi_dashboards where id=p_dashboard_id and tenant_id=p_tenant_id
    and project_id=p_project_id and creator_user_id=p_creator_user_id for update;
  if not found then raise exception using errcode='P0001',message='dashboard_not_found';end if;
  if d.revision<>p_expected_revision then raise exception using errcode='40001',message='dashboard_revision_conflict';end if;
  update public.bi_dashboards set auto_refresh_enabled=p_enabled,revision=revision+1 where id=p_dashboard_id returning * into d;
  return d;
end;$$;

create function public.create_bi_report_schedule164(
  p_tenant_id integer,p_project_id uuid,p_creator_user_id integer,p_dashboard_id uuid,
  p_name text,p_cadence text,p_timezone text,p_local_time time,p_weekday smallint,
  p_month_day smallint,p_enabled boolean,p_require_ready_checkpoints boolean,p_next_run_at timestamptz
) returns public.bi_report_schedules language plpgsql security definer set search_path='' as $$
declare s public.bi_report_schedules;
begin
  if not exists(select 1 from public.bi_dashboards where id=p_dashboard_id and tenant_id=p_tenant_id
    and project_id=p_project_id and creator_user_id=p_creator_user_id) then
    raise exception using errcode='P0001',message='dashboard_not_found';end if;
  if (select count(*) from public.bi_report_schedules where tenant_id=p_tenant_id and project_id=p_project_id
      and creator_user_id=p_creator_user_id)>=20 then
    raise exception using errcode='54000',message='report_schedule_limit_exceeded';end if;
  insert into public.bi_report_schedules(tenant_id,project_id,creator_user_id,dashboard_id,name,cadence,
    timezone,local_time,weekday,month_day,enabled,require_ready_checkpoints,next_run_at)
  values(p_tenant_id,p_project_id,p_creator_user_id,p_dashboard_id,btrim(p_name),p_cadence,
    p_timezone,p_local_time,p_weekday,p_month_day,p_enabled,p_require_ready_checkpoints,p_next_run_at)
  returning * into s;return s;
end;$$;

create function public.update_bi_report_schedule164(
  p_tenant_id integer,p_project_id uuid,p_creator_user_id integer,p_schedule_id uuid,p_expected_revision bigint,
  p_dashboard_id uuid,p_name text,p_cadence text,p_timezone text,p_local_time time,p_weekday smallint,
  p_month_day smallint,p_enabled boolean,p_require_ready_checkpoints boolean,p_next_run_at timestamptz
) returns public.bi_report_schedules language plpgsql security definer set search_path='' as $$
declare s public.bi_report_schedules;
begin
  select * into s from public.bi_report_schedules where id=p_schedule_id and tenant_id=p_tenant_id
    and project_id=p_project_id and creator_user_id=p_creator_user_id for update;
  if not found then raise exception using errcode='P0001',message='report_schedule_not_found';end if;
  if s.revision<>p_expected_revision then raise exception using errcode='40001',message='report_schedule_revision_conflict';end if;
  if not exists(select 1 from public.bi_dashboards where id=p_dashboard_id and tenant_id=p_tenant_id
    and project_id=p_project_id and creator_user_id=p_creator_user_id) then
    raise exception using errcode='P0001',message='dashboard_not_found';end if;
  update public.bi_report_schedules set dashboard_id=p_dashboard_id,name=btrim(p_name),cadence=p_cadence,
    timezone=p_timezone,local_time=p_local_time,weekday=p_weekday,month_day=p_month_day,enabled=p_enabled,
    require_ready_checkpoints=p_require_ready_checkpoints,next_run_at=p_next_run_at,revision=revision+1
  where id=p_schedule_id returning * into s;return s;
end;$$;

create function public.delete_bi_report_schedule164(
  p_tenant_id integer,p_project_id uuid,p_creator_user_id integer,p_schedule_id uuid,p_expected_revision bigint
) returns boolean language plpgsql security definer set search_path='' as $$
declare s public.bi_report_schedules;
begin
  select * into s from public.bi_report_schedules where id=p_schedule_id and tenant_id=p_tenant_id
    and project_id=p_project_id and creator_user_id=p_creator_user_id for update;
  if not found then raise exception using errcode='P0001',message='report_schedule_not_found';end if;
  if s.revision<>p_expected_revision then raise exception using errcode='40001',message='report_schedule_revision_conflict';end if;
  delete from public.bi_report_schedules where id=p_schedule_id;return true;
end;$$;

create function public.enqueue_bi_report_run164(
  p_tenant_id integer,p_project_id uuid,p_creator_user_id integer,p_dashboard_id uuid,
  p_schedule_id uuid,p_trigger_type text,p_due_slot timestamptz,p_deduplication_key text
) returns public.bi_report_runs language plpgsql security definer set search_path='' as $$
declare d public.bi_dashboards;r public.bi_report_runs;definition jsonb;versions jsonb;
  require_ready boolean:=false;
begin
  select * into d from public.bi_dashboards where id=p_dashboard_id and tenant_id=p_tenant_id
    and project_id=p_project_id and creator_user_id=p_creator_user_id for share;
  if not found then raise exception using errcode='P0001',message='dashboard_not_found';end if;
  if p_schedule_id is not null then
    select s.require_ready_checkpoints into require_ready from public.bi_report_schedules s
    where s.id=p_schedule_id and s.tenant_id=p_tenant_id and s.project_id=p_project_id
      and s.creator_user_id=p_creator_user_id and s.dashboard_id=p_dashboard_id;
    if not found then raise exception using errcode='P0001',message='report_schedule_not_found';end if;
  end if;
  select jsonb_build_object('dashboard',jsonb_build_object('id',d.id,'name',d.name,'description',d.description,
      'revision',d.revision,'auto_refresh_enabled',d.auto_refresh_enabled),
      'report_policy',jsonb_build_object('require_ready_checkpoints',require_ready),
      'widgets',coalesce(jsonb_agg(to_jsonb(w) order by w.created_at,w.id),'[]'::jsonb))
    into definition from public.bi_dashboard_widgets w where w.dashboard_id=d.id;
  select coalesce(jsonb_agg(jsonb_build_object('widget_id',w.id,'dataset_id',w.dataset_id,
      'dataset_version_id',v.id,'version_number',v.version_number,'version_kind',v.version_kind,
      'content_hash',v.content_hash,'committed_at',v.created_at,'version_policy',w.version_policy)
      order by w.created_at,w.id),'[]'::jsonb) into versions
  from public.bi_dashboard_widgets w
  join lateral (select dv.* from public.data_dataset_versions dv where dv.dataset_id=w.dataset_id
      and dv.tenant_id=w.tenant_id and (w.version_policy='latest_committed' or dv.id=w.dataset_version_id)
      order by case when w.version_policy='pinned' and dv.id=w.dataset_version_id then 0 else 1 end,
        dv.version_number desc limit 1) v on true where w.dashboard_id=d.id;
  insert into public.bi_report_runs(tenant_id,project_id,creator_user_id,dashboard_id,schedule_id,
    dashboard_revision,trigger_type,due_slot,deduplication_key,definition_snapshot,version_vector)
  values(p_tenant_id,p_project_id,p_creator_user_id,p_dashboard_id,p_schedule_id,d.revision,p_trigger_type,
    p_due_slot,p_deduplication_key,definition,versions)
  on conflict(deduplication_key) do update set deduplication_key=excluded.deduplication_key
  returning * into r;return r;
end;$$;

create function public.advance_bi_report_schedule164(
  p_schedule_id uuid,p_expected_revision bigint,p_due_slot timestamptz,p_next_run_at timestamptz
) returns boolean language plpgsql security definer set search_path='' as $$
begin
  update public.bi_report_schedules set next_run_at=p_next_run_at,last_attempted_at=now(),revision=revision+1
  where id=p_schedule_id and revision=p_expected_revision and enabled and next_run_at=p_due_slot;
  return found;
end;$$;

create function public.claim_bi_report_runs164(
  p_worker_id text,p_limit integer,p_lease_seconds integer,p_now timestamptz
) returns setof public.bi_report_runs language plpgsql security definer set search_path='' as $$
declare candidate public.bi_report_runs;claimed public.bi_report_runs;claimed_count integer:=0;
begin
  if length(p_worker_id) not between 1 and 160 or p_limit not between 1 and 20 or p_lease_seconds not between 30 and 1800 then
    raise exception using errcode='22023',message='report_claim_bounds_invalid';end if;
  for candidate in select r.* from public.bi_report_runs r
    where r.status in ('queued','retry_pending') and r.available_at<=p_now and r.attempts<r.max_attempts
      and (select count(*) from public.bi_report_runs x where x.tenant_id=r.tenant_id and x.status='running')<2
    order by r.available_at,r.created_at,r.id for update skip locked limit p_limit
  loop
    update public.bi_report_runs set status='running',lease_owner=p_worker_id,lease_token=gen_random_uuid(),
      lease_fence=lease_fence+1,lease_expires_at=p_now+make_interval(secs=>p_lease_seconds),
      last_heartbeat_at=p_now,started_at=coalesce(started_at,p_now),attempts=attempts+1,error_code=null
      where id=candidate.id returning * into claimed;
    return next claimed;claimed_count:=claimed_count+1;
    exit when claimed_count>=p_limit;
  end loop;
end;$$;

create function public.heartbeat_bi_report_run164(
  p_run_id uuid,p_lease_token uuid,p_lease_fence bigint,p_lease_seconds integer,p_now timestamptz
) returns boolean language plpgsql security definer set search_path='' as $$
begin
  update public.bi_report_runs set lease_expires_at=p_now+make_interval(secs=>p_lease_seconds),last_heartbeat_at=p_now
  where id=p_run_id and status='running' and lease_token=p_lease_token and lease_fence=p_lease_fence
    and lease_expires_at>p_now;return found;
end;$$;

create function public.complete_bi_report_run164(
  p_run_id uuid,p_lease_token uuid,p_lease_fence bigint,p_status text,p_result_snapshot jsonb,
  p_warnings jsonb,p_artifact_storage_key text,p_artifact_filename text,p_artifact_content_type text,
  p_artifact_size_bytes integer,p_artifact_sha256 text,p_now timestamptz
) returns boolean language plpgsql security definer set search_path='' as $$
declare r public.bi_report_runs;
begin
  if p_status not in ('completed','needs_attention') then raise exception using errcode='22023',message='report_completion_status_invalid';end if;
  update public.bi_report_runs set status=p_status,result_snapshot=p_result_snapshot,warnings=coalesce(p_warnings,'[]'::jsonb),
    artifact_storage_key=p_artifact_storage_key,artifact_filename=p_artifact_filename,
    artifact_content_type=p_artifact_content_type,artifact_size_bytes=p_artifact_size_bytes,
    artifact_sha256=p_artifact_sha256,completed_at=p_now,lease_owner=null,lease_token=null,
    lease_expires_at=null,last_heartbeat_at=p_now,error_code=null
  where id=p_run_id and status='running' and lease_token=p_lease_token and lease_fence=p_lease_fence
    and lease_expires_at>p_now returning * into r;
  if not found then return false;end if;
  if r.schedule_id is not null then update public.bi_report_schedules set last_successful_at=case when p_status='completed' then p_now else last_successful_at end,
    last_failure_code=case when p_status='completed' then null else 'needs_attention' end where id=r.schedule_id;end if;
  return true;
end;$$;

create function public.fail_bi_report_run164(
  p_run_id uuid,p_lease_token uuid,p_lease_fence bigint,p_error_code text,p_retryable boolean,
  p_available_at timestamptz,p_now timestamptz
) returns text language plpgsql security definer set search_path='' as $$
declare r public.bi_report_runs;next_status text;
begin
  select * into r from public.bi_report_runs where id=p_run_id and status='running'
    and lease_token=p_lease_token and lease_fence=p_lease_fence for update;
  if not found then return 'stale';end if;
  next_status:=case when p_retryable and r.attempts<r.max_attempts then 'retry_pending' else 'failed' end;
  update public.bi_report_runs set status=next_status,error_code=left(p_error_code,100),available_at=p_available_at,
    lease_owner=null,lease_token=null,lease_expires_at=null,last_heartbeat_at=p_now,
    completed_at=case when next_status='failed' then p_now else null end where id=p_run_id;
  if r.schedule_id is not null then update public.bi_report_schedules set last_failure_code=left(p_error_code,100) where id=r.schedule_id;end if;
  return next_status;
end;$$;

create function public.recover_expired_bi_report_runs164(p_now timestamptz,p_limit integer)
returns integer language plpgsql security definer set search_path='' as $$
declare changed integer;
begin
  with candidates as (select id from public.bi_report_runs where status='running' and lease_expires_at<=p_now
    order by lease_expires_at,id for update skip locked limit greatest(1,least(p_limit,100)))
  update public.bi_report_runs r set status=case when attempts<max_attempts then 'retry_pending' else 'failed' end,
    available_at=p_now,lease_owner=null,lease_token=null,lease_expires_at=null,error_code='report_lease_expired',
    completed_at=case when attempts>=max_attempts then p_now else null end from candidates c where r.id=c.id;
  get diagnostics changed=row_count;return changed;
end;$$;

create function public.archive_bi_report_run164(
  p_tenant_id integer,p_project_id uuid,p_creator_user_id integer,p_run_id uuid
) returns boolean language plpgsql security definer set search_path='' as $$
begin
  update public.bi_report_runs set archived_at=now()
  where id=p_run_id and tenant_id=p_tenant_id and project_id=p_project_id
    and creator_user_id=p_creator_user_id and archived_at is null
    and status in ('completed','failed','needs_attention','cancelled','skipped');
  return found;
end;$$;

revoke all on function public.configure_bi_dashboard_refresh164(integer,uuid,integer,uuid,bigint,boolean),
  public.create_bi_report_schedule164(integer,uuid,integer,uuid,text,text,text,time,smallint,smallint,boolean,boolean,timestamptz),
  public.update_bi_report_schedule164(integer,uuid,integer,uuid,bigint,uuid,text,text,text,time,smallint,smallint,boolean,boolean,timestamptz),
  public.delete_bi_report_schedule164(integer,uuid,integer,uuid,bigint),
  public.enqueue_bi_report_run164(integer,uuid,integer,uuid,uuid,text,timestamptz,text),
  public.advance_bi_report_schedule164(uuid,bigint,timestamptz,timestamptz),
  public.claim_bi_report_runs164(text,integer,integer,timestamptz),
  public.heartbeat_bi_report_run164(uuid,uuid,bigint,integer,timestamptz),
  public.complete_bi_report_run164(uuid,uuid,bigint,text,jsonb,jsonb,text,text,text,integer,text,timestamptz),
  public.fail_bi_report_run164(uuid,uuid,bigint,text,boolean,timestamptz,timestamptz),
  public.recover_expired_bi_report_runs164(timestamptz,integer),
  public.archive_bi_report_run164(integer,uuid,integer,uuid)
from public,anon,authenticated;
grant execute on function public.configure_bi_dashboard_refresh164(integer,uuid,integer,uuid,bigint,boolean),
  public.create_bi_report_schedule164(integer,uuid,integer,uuid,text,text,text,time,smallint,smallint,boolean,boolean,timestamptz),
  public.update_bi_report_schedule164(integer,uuid,integer,uuid,bigint,uuid,text,text,text,time,smallint,smallint,boolean,boolean,timestamptz),
  public.delete_bi_report_schedule164(integer,uuid,integer,uuid,bigint),
  public.enqueue_bi_report_run164(integer,uuid,integer,uuid,uuid,text,timestamptz,text),
  public.advance_bi_report_schedule164(uuid,bigint,timestamptz,timestamptz),
  public.claim_bi_report_runs164(text,integer,integer,timestamptz),
  public.heartbeat_bi_report_run164(uuid,uuid,bigint,integer,timestamptz),
  public.complete_bi_report_run164(uuid,uuid,bigint,text,jsonb,jsonb,text,text,text,integer,text,timestamptz),
  public.fail_bi_report_run164(uuid,uuid,bigint,text,boolean,timestamptz,timestamptz),
  public.recover_expired_bi_report_runs164(timestamptz,integer),
  public.archive_bi_report_run164(integer,uuid,integer,uuid)
to service_role;

update public.application_schema_state set schema_version=164,applied_at=now() where contract_key='core';
notify pgrst,'reload schema';
commit;
