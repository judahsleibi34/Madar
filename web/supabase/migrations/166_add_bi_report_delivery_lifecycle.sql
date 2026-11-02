begin;

do $$
declare v_schema_version public.application_schema_state.schema_version%type;
begin
  select schema_version into v_schema_version from public.application_schema_state
  where contract_key='core' for update;
  if v_schema_version is null then raise exception using errcode='P0001',message='migration_166_schema_state_missing';end if;
  if v_schema_version<>165 then raise exception using errcode='P0001',message=format('migration_166_expected_schema_165_got_%s',v_schema_version);end if;
end;$$;

alter table public.bi_report_schedules add constraint bi_report_schedules_owner_scope_unique166
  unique(id,tenant_id,project_id,creator_user_id);
alter table public.bi_report_runs add column artifact_deleted_at timestamptz;

create table public.bi_report_delivery_configs(
  schedule_id uuid primary key,
  tenant_id integer not null,
  project_id uuid not null,
  owner_user_id integer not null,
  enabled boolean not null default false,
  revision bigint not null default 1 check(revision>0),
  created_at timestamptz not null default now(),updated_at timestamptz not null default now(),
  foreign key(schedule_id,tenant_id,project_id,owner_user_id)
    references public.bi_report_schedules(id,tenant_id,project_id,creator_user_id) on delete cascade
);
create table public.bi_report_delivery_recipients(
  schedule_id uuid not null,tenant_id integer not null,project_id uuid not null,
  owner_user_id integer not null,member_user_id integer not null,
  created_at timestamptz not null default now(),
  primary key(schedule_id,member_user_id),
  foreign key(schedule_id) references public.bi_report_delivery_configs(schedule_id) on delete cascade,
  foreign key(member_user_id,tenant_id) references public.tenant_memberships(user_id,tenant_id) on delete cascade,
  check(member_user_id<>owner_user_id)
);
create table public.bi_report_lifecycle_settings(
  tenant_id integer not null,project_id uuid not null,owner_user_id integer not null,
  retention_days smallint not null default 90 check(retention_days between 7 and 365),
  cleanup_enabled boolean not null default false,
  revision bigint not null default 1 check(revision>0),
  created_at timestamptz not null default now(),updated_at timestamptz not null default now(),
  primary key(tenant_id,project_id,owner_user_id),
  foreign key(project_id,tenant_id) references public.builder_projects(id,tenant_id) on delete cascade,
  foreign key(owner_user_id,tenant_id) references public.users(id,tenant_id) on delete cascade
);
create table public.bi_report_deliveries(
  id uuid primary key default gen_random_uuid(),report_id uuid not null,tenant_id integer not null,
  project_id uuid not null,owner_user_id integer not null,recipient_user_id integer not null,
  channel text not null default 'email' check(channel='email'),
  status text not null default 'pending' check(status in ('pending','processing','retry_pending','sent','failed','revoked')),
  attempts smallint not null default 0 check(attempts between 0 and 3),max_attempts smallint not null default 3 check(max_attempts between 1 and 3),
  available_at timestamptz not null default now(),lease_owner text,lease_token uuid,lease_fence bigint not null default 0,
  lease_expires_at timestamptz,last_error_code text,provider_message_id text,sent_at timestamptz,
  created_at timestamptz not null default now(),updated_at timestamptz not null default now(),
  foreign key(report_id,tenant_id,project_id,owner_user_id)
    references public.bi_report_runs(id,tenant_id,project_id,creator_user_id) on delete cascade,
  foreign key(recipient_user_id,tenant_id) references public.tenant_memberships(user_id,tenant_id) on delete restrict,
  unique(report_id,recipient_user_id,channel),
  check((status='processing' and lease_owner is not null and lease_token is not null and lease_expires_at is not null) or status<>'processing')
);
create table public.bi_report_cleanup_jobs(
  id uuid primary key default gen_random_uuid(),report_id uuid not null unique,tenant_id integer not null,
  project_id uuid not null,owner_user_id integer not null,
  status text not null default 'pending' check(status in ('pending','processing','retry_pending','completed','failed','cancelled')),
  attempts smallint not null default 0 check(attempts between 0 and 3),max_attempts smallint not null default 3 check(max_attempts between 1 and 3),
  available_at timestamptz not null,lease_owner text,lease_token uuid,lease_fence bigint not null default 0,
  lease_expires_at timestamptz,last_error_code text,deleted_size_bytes integer,deleted_sha256 text,completed_at timestamptz,
  created_at timestamptz not null default now(),updated_at timestamptz not null default now(),
  foreign key(report_id,tenant_id,project_id,owner_user_id)
    references public.bi_report_runs(id,tenant_id,project_id,creator_user_id) on delete cascade,
  check((status='processing' and lease_owner is not null and lease_token is not null and lease_expires_at is not null) or status<>'processing')
);

create index bi_report_deliveries_claim166 on public.bi_report_deliveries(available_at,created_at,id) where status in('pending','retry_pending');
create index bi_report_deliveries_report166 on public.bi_report_deliveries(tenant_id,project_id,report_id,created_at desc);
create index bi_report_cleanup_claim166 on public.bi_report_cleanup_jobs(available_at,created_at,id) where status in('pending','retry_pending');
create trigger set_bi_report_delivery_configs_updated_at166 before update on public.bi_report_delivery_configs for each row execute function public.set_updated_at();
create trigger set_bi_report_lifecycle_settings_updated_at166 before update on public.bi_report_lifecycle_settings for each row execute function public.set_updated_at();
create trigger set_bi_report_deliveries_updated_at166 before update on public.bi_report_deliveries for each row execute function public.set_updated_at();
create trigger set_bi_report_cleanup_jobs_updated_at166 before update on public.bi_report_cleanup_jobs for each row execute function public.set_updated_at();

alter table public.bi_report_delivery_configs enable row level security;
alter table public.bi_report_delivery_recipients enable row level security;
alter table public.bi_report_lifecycle_settings enable row level security;
alter table public.bi_report_deliveries enable row level security;
alter table public.bi_report_cleanup_jobs enable row level security;
revoke all on public.bi_report_delivery_configs,public.bi_report_delivery_recipients,public.bi_report_lifecycle_settings,public.bi_report_deliveries,public.bi_report_cleanup_jobs from public,anon,authenticated;
grant select,insert,update,delete on public.bi_report_delivery_configs,public.bi_report_delivery_recipients,public.bi_report_lifecycle_settings,public.bi_report_deliveries,public.bi_report_cleanup_jobs to service_role;

create function public.configure_bi_report_delivery166(
 p_tenant_id integer,p_project_id uuid,p_owner_user_id integer,p_schedule_id uuid,
 p_expected_schedule_revision bigint,p_enabled boolean,p_recipient_user_ids integer[]
) returns jsonb language plpgsql security definer set search_path='' as $$
declare s public.bi_report_schedules;c public.bi_report_delivery_configs;recipient_count integer;
begin
  if cardinality(coalesce(p_recipient_user_ids,'{}'::integer[]))>25 then raise exception using errcode='54000',message='report_delivery_recipient_limit';end if;
  if p_enabled and cardinality(coalesce(p_recipient_user_ids,'{}'::integer[]))=0 then raise exception using errcode='22023',message='report_delivery_recipient_required';end if;
  if cardinality(coalesce(p_recipient_user_ids,'{}'::integer[]))<>(select count(distinct value) from unnest(coalesce(p_recipient_user_ids,'{}'::integer[])) value) then raise exception using errcode='22023',message='report_delivery_recipient_duplicate';end if;
  select * into s from public.bi_report_schedules where id=p_schedule_id and tenant_id=p_tenant_id and project_id=p_project_id and creator_user_id=p_owner_user_id for update;
  if not found then raise exception using errcode='P0001',message='report_schedule_not_found';end if;
  if s.revision<>p_expected_schedule_revision then raise exception using errcode='40001',message='report_schedule_revision_conflict';end if;
  select count(*) into recipient_count from unnest(coalesce(p_recipient_user_ids,'{}'::integer[])) value
    join public.tenant_memberships m on m.user_id=value and m.tenant_id=p_tenant_id and m.status='active'
    join public.users u on u.id=value and u.account_status='active'
    where value<>p_owner_user_id;
  if recipient_count<>cardinality(coalesce(p_recipient_user_ids,'{}'::integer[])) then raise exception using errcode='42501',message='report_delivery_recipient_forbidden';end if;
  insert into public.bi_report_delivery_configs(schedule_id,tenant_id,project_id,owner_user_id,enabled)
    values(p_schedule_id,p_tenant_id,p_project_id,p_owner_user_id,p_enabled)
    on conflict(schedule_id) do update set enabled=excluded.enabled,revision=public.bi_report_delivery_configs.revision+1 returning * into c;
  delete from public.bi_report_delivery_recipients where schedule_id=p_schedule_id;
  insert into public.bi_report_delivery_recipients(schedule_id,tenant_id,project_id,owner_user_id,member_user_id)
    select p_schedule_id,p_tenant_id,p_project_id,p_owner_user_id,value from unnest(coalesce(p_recipient_user_ids,'{}'::integer[])) value;
  update public.bi_report_deliveries d set status='revoked',last_error_code='delivery_configuration_revoked'
    from public.bi_report_runs r where r.id=d.report_id and r.schedule_id=p_schedule_id
    and d.status in('pending','retry_pending') and (not p_enabled or not(d.recipient_user_id=any(coalesce(p_recipient_user_ids,'{}'::integer[]))));
  update public.bi_report_schedules set revision=revision+1 where id=p_schedule_id returning * into s;
  return jsonb_build_object('schedule',to_jsonb(s),'config',to_jsonb(c));
end;$$;

create function public.configure_bi_report_lifecycle166(
 p_tenant_id integer,p_project_id uuid,p_owner_user_id integer,p_expected_revision bigint,
 p_retention_days smallint,p_cleanup_enabled boolean
) returns public.bi_report_lifecycle_settings language plpgsql security definer set search_path='' as $$
declare v public.bi_report_lifecycle_settings;
begin
  if p_retention_days not between 7 and 365 then raise exception using errcode='22023',message='report_retention_invalid';end if;
  if not exists(select 1 from public.builder_projects where id=p_project_id and tenant_id=p_tenant_id) then raise exception using errcode='P0001',message='project_not_found';end if;
  select * into v from public.bi_report_lifecycle_settings where tenant_id=p_tenant_id and project_id=p_project_id and owner_user_id=p_owner_user_id for update;
  if found and (p_expected_revision is null or v.revision<>p_expected_revision) then raise exception using errcode='40001',message='report_lifecycle_revision_conflict';end if;
  if not found and p_expected_revision is not null then raise exception using errcode='40001',message='report_lifecycle_revision_conflict';end if;
  insert into public.bi_report_lifecycle_settings(tenant_id,project_id,owner_user_id,retention_days,cleanup_enabled)
    values(p_tenant_id,p_project_id,p_owner_user_id,p_retention_days,p_cleanup_enabled)
    on conflict(tenant_id,project_id,owner_user_id) do update set retention_days=excluded.retention_days,
      cleanup_enabled=excluded.cleanup_enabled,revision=public.bi_report_lifecycle_settings.revision+1 returning * into v;
  if not p_cleanup_enabled then
    delete from public.bi_report_cleanup_jobs j using public.bi_report_runs r
      where r.id=j.report_id and r.tenant_id=p_tenant_id and r.project_id=p_project_id
      and r.creator_user_id=p_owner_user_id and j.status in('pending','retry_pending');
  else
    update public.bi_report_cleanup_jobs j set available_at=r.completed_at+make_interval(days=>p_retention_days)
      from public.bi_report_runs r where r.id=j.report_id and r.tenant_id=p_tenant_id
      and r.project_id=p_project_id and r.creator_user_id=p_owner_user_id
      and j.status in('pending','retry_pending');
  end if;
  return v;
end;$$;

create function public.enqueue_bi_report_lifecycle166(p_report_id uuid) returns jsonb
language plpgsql security definer set search_path='' as $$
declare r public.bi_report_runs;settings public.bi_report_lifecycle_settings;queued integer:=0;cleanup_queued boolean:=false;
begin
  select * into r from public.bi_report_runs where id=p_report_id and status='completed' and artifact_deleted_at is null for update;
  if not found then return jsonb_build_object('deliveries',0,'cleanup',false);end if;
  select * into settings from public.bi_report_lifecycle_settings where tenant_id=r.tenant_id and project_id=r.project_id and owner_user_id=r.creator_user_id;
  if found and settings.cleanup_enabled then
    insert into public.bi_report_cleanup_jobs(report_id,tenant_id,project_id,owner_user_id,available_at)
    values(r.id,r.tenant_id,r.project_id,r.creator_user_id,r.completed_at+make_interval(days=>settings.retention_days)) on conflict(report_id) do nothing;
    cleanup_queued:=true;
  end if;
  if r.schedule_id is not null and exists(select 1 from public.bi_report_delivery_configs where schedule_id=r.schedule_id and enabled) then
    insert into public.bi_report_shares(report_id,tenant_id,project_id,owner_user_id,member_user_id,permission)
      select r.id,r.tenant_id,r.project_id,r.creator_user_id,x.member_user_id,'viewer'
      from public.bi_report_delivery_recipients x join public.tenant_memberships m on m.user_id=x.member_user_id and m.tenant_id=r.tenant_id and m.status='active'
      join public.users u on u.id=x.member_user_id and u.account_status='active' where x.schedule_id=r.schedule_id
      on conflict(report_id,member_user_id) do nothing;
    insert into public.bi_report_deliveries(report_id,tenant_id,project_id,owner_user_id,recipient_user_id)
      select r.id,r.tenant_id,r.project_id,r.creator_user_id,x.member_user_id
      from public.bi_report_delivery_recipients x join public.bi_report_shares s on s.report_id=r.id and s.member_user_id=x.member_user_id
      where x.schedule_id=r.schedule_id on conflict(report_id,recipient_user_id,channel) do nothing;
    get diagnostics queued=row_count;
  end if;
  return jsonb_build_object('deliveries',queued,'cleanup',cleanup_queued);
end;$$;

create function public.complete_bi_report_run166(
 p_run_id uuid,p_lease_token uuid,p_lease_fence bigint,p_status text,p_result_snapshot jsonb,
 p_warnings jsonb,p_artifact_storage_key text,p_artifact_filename text,p_artifact_content_type text,
 p_artifact_size_bytes integer,p_artifact_sha256 text,p_now timestamptz
) returns boolean language plpgsql security definer set search_path='' as $$
declare completed boolean;
begin
  completed:=public.complete_bi_report_run164(p_run_id,p_lease_token,p_lease_fence,p_status,p_result_snapshot,p_warnings,
    p_artifact_storage_key,p_artifact_filename,p_artifact_content_type,p_artifact_size_bytes,p_artifact_sha256,p_now);
  if completed and p_status='completed' then perform public.enqueue_bi_report_lifecycle166(p_run_id);end if;
  return completed;
end;$$;

create function public.claim_bi_report_deliveries166(p_worker_id text,p_limit integer,p_lease_seconds integer,p_now timestamptz)
returns setof public.bi_report_deliveries language plpgsql security definer set search_path='' as $$
declare candidate public.bi_report_deliveries;claimed public.bi_report_deliveries;claimed_count integer:=0;
begin
  update public.bi_report_deliveries set status=case when attempts<max_attempts then 'retry_pending' else 'failed' end,
    available_at=p_now,lease_owner=null,lease_token=null,lease_expires_at=null,last_error_code='delivery_lease_expired'
    where status='processing' and lease_expires_at<=p_now;
  for candidate in select d.* from public.bi_report_deliveries d where d.status in('pending','retry_pending') and d.available_at<=p_now order by d.available_at,d.id for update skip locked loop
    exit when claimed_count>=least(greatest(p_limit,1),25);
    if not exists(select 1 from public.bi_report_shares s join public.tenant_memberships m on m.user_id=s.member_user_id and m.tenant_id=s.tenant_id and m.status='active'
      join public.users u on u.id=s.member_user_id and u.account_status='active' where s.report_id=candidate.report_id and s.member_user_id=candidate.recipient_user_id) then
      update public.bi_report_deliveries set status='revoked',last_error_code='recipient_access_revoked' where id=candidate.id;continue;end if;
    if not exists(select 1 from public.bi_report_runs r join public.bi_report_delivery_configs c on c.schedule_id=r.schedule_id and c.enabled
      join public.bi_report_delivery_recipients x on x.schedule_id=c.schedule_id and x.member_user_id=candidate.recipient_user_id where r.id=candidate.report_id) then
      update public.bi_report_deliveries set status='revoked',last_error_code='delivery_configuration_revoked' where id=candidate.id;continue;end if;
    update public.bi_report_deliveries set status='processing',attempts=attempts+1,lease_owner=left(p_worker_id,160),lease_token=gen_random_uuid(),
      lease_fence=lease_fence+1,lease_expires_at=p_now+make_interval(secs=>least(greatest(p_lease_seconds,30),1800)) where id=candidate.id returning * into claimed;
    claimed_count:=claimed_count+1;return next claimed;
  end loop;return;
end;$$;

create function public.authorize_bi_report_delivery166(p_delivery_id uuid,p_lease_token uuid,p_lease_fence bigint)
returns jsonb language plpgsql security definer set search_path='' as $$
declare d public.bi_report_deliveries;r public.bi_report_runs;recipient_email text;
begin
  select * into d from public.bi_report_deliveries where id=p_delivery_id and status='processing' and lease_token=p_lease_token and lease_fence=p_lease_fence and lease_expires_at>now() for update;
  if not found then raise exception using errcode='40001',message='report_delivery_claim_lost';end if;
  if not exists(select 1 from public.bi_report_shares s join public.tenant_memberships m on m.user_id=s.member_user_id and m.tenant_id=s.tenant_id and m.status='active'
    where s.report_id=d.report_id and s.member_user_id=d.recipient_user_id) then
    update public.bi_report_deliveries set status='revoked',lease_owner=null,lease_token=null,lease_expires_at=null,last_error_code='recipient_access_revoked' where id=d.id;
    raise exception using errcode='42501',message='report_delivery_access_revoked';end if;
  if not exists(select 1 from public.bi_report_runs rr join public.bi_report_delivery_configs c on c.schedule_id=rr.schedule_id and c.enabled
    join public.bi_report_delivery_recipients x on x.schedule_id=c.schedule_id and x.member_user_id=d.recipient_user_id where rr.id=d.report_id) then
    raise exception using errcode='42501',message='report_delivery_configuration_revoked';end if;
  select * into r from public.bi_report_runs where id=d.report_id and status='completed' and artifact_deleted_at is null;
  if not found then raise exception using errcode='55000',message='report_delivery_artifact_unavailable';end if;
  select email into recipient_email from public.users where id=d.recipient_user_id and account_status='active';
  if not found or recipient_email is null then raise exception using errcode='42501',message='report_delivery_recipient_unavailable';end if;
  return jsonb_build_object('delivery',to_jsonb(d),'report',to_jsonb(r),'recipient_email',recipient_email);
end;$$;

create function public.finish_bi_report_delivery166(p_delivery_id uuid,p_lease_token uuid,p_lease_fence bigint,p_outcome text,p_error_code text,p_provider_message_id text,p_now timestamptz)
returns public.bi_report_deliveries language plpgsql security definer set search_path='' as $$
declare d public.bi_report_deliveries;next_status text;
begin
  select * into d from public.bi_report_deliveries where id=p_delivery_id and status='processing' and lease_token=p_lease_token and lease_fence=p_lease_fence for update;
  if not found then raise exception using errcode='40001',message='report_delivery_claim_lost';end if;
  next_status:=case when p_outcome='sent' then 'sent' when p_outcome='revoked' then 'revoked' when p_outcome='retry' and d.attempts<d.max_attempts then 'retry_pending' else 'failed' end;
  update public.bi_report_deliveries set status=next_status,available_at=case when next_status='retry_pending' then p_now+make_interval(secs=>least(3600,60*d.attempts)) else available_at end,
    last_error_code=case when next_status='sent' then null else left(coalesce(p_error_code,'delivery_failed'),100) end,
    provider_message_id=case when next_status='sent' then left(p_provider_message_id,200) else null end,sent_at=case when next_status='sent' then p_now else null end,
    lease_owner=null,lease_token=null,lease_expires_at=null where id=d.id returning * into d;return d;
end;$$;

create function public.claim_bi_report_cleanup166(p_worker_id text,p_limit integer,p_lease_seconds integer,p_now timestamptz)
returns setof public.bi_report_cleanup_jobs language plpgsql security definer set search_path='' as $$
declare candidate public.bi_report_cleanup_jobs;claimed public.bi_report_cleanup_jobs;claimed_count integer:=0;
begin
  update public.bi_report_cleanup_jobs set status=case when attempts<max_attempts then 'retry_pending' else 'failed' end,available_at=p_now,
    lease_owner=null,lease_token=null,lease_expires_at=null,last_error_code='cleanup_lease_expired' where status='processing' and lease_expires_at<=p_now;
  for candidate in select j.* from public.bi_report_cleanup_jobs j where j.status in('pending','retry_pending') and j.available_at<=p_now
    and not exists(select 1 from public.bi_report_deliveries d where d.report_id=j.report_id and d.status in('pending','processing','retry_pending'))
    order by j.available_at,j.id for update skip locked loop
    exit when claimed_count>=least(greatest(p_limit,1),25);
    update public.bi_report_cleanup_jobs set status='processing',attempts=attempts+1,lease_owner=left(p_worker_id,160),lease_token=gen_random_uuid(),
      lease_fence=lease_fence+1,lease_expires_at=p_now+make_interval(secs=>least(greatest(p_lease_seconds,30),1800)) where id=candidate.id returning * into claimed;
    claimed_count:=claimed_count+1;return next claimed;
  end loop;return;
end;$$;

create function public.authorize_bi_report_cleanup166(p_job_id uuid,p_lease_token uuid,p_lease_fence bigint,p_now timestamptz)
returns jsonb language plpgsql security definer set search_path='' as $$
declare j public.bi_report_cleanup_jobs;r public.bi_report_runs;s public.bi_report_lifecycle_settings;due_at timestamptz;
begin
  select * into j from public.bi_report_cleanup_jobs where id=p_job_id and status='processing'
    and lease_token=p_lease_token and lease_fence=p_lease_fence and lease_expires_at>p_now for update;
  if not found then raise exception using errcode='40001',message='report_cleanup_claim_lost';end if;
  select * into r from public.bi_report_runs where id=j.report_id and tenant_id=j.tenant_id
    and project_id=j.project_id and creator_user_id=j.owner_user_id and artifact_deleted_at is null;
  select * into s from public.bi_report_lifecycle_settings where tenant_id=j.tenant_id
    and project_id=j.project_id and owner_user_id=j.owner_user_id;
  if not found or not s.cleanup_enabled then
    update public.bi_report_cleanup_jobs set status='cancelled',lease_owner=null,lease_token=null,
      lease_expires_at=null,last_error_code='cleanup_disabled' where id=j.id;
    return jsonb_build_object('authorized',false,'status','cancelled');
  end if;
  if r.id is null then return jsonb_build_object('authorized',true,'report',null);end if;
  due_at:=r.completed_at+make_interval(days=>s.retention_days);
  if due_at>p_now then
    update public.bi_report_cleanup_jobs set status='retry_pending',available_at=due_at,lease_owner=null,
      lease_token=null,lease_expires_at=null,last_error_code=null where id=j.id;
    return jsonb_build_object('authorized',false,'status','retry_pending');
  end if;
  return jsonb_build_object('authorized',true,'report',to_jsonb(r));
end;$$;

create function public.finish_bi_report_cleanup166(p_job_id uuid,p_lease_token uuid,p_lease_fence bigint,p_success boolean,p_error_code text,p_deleted_size_bytes integer,p_deleted_sha256 text,p_now timestamptz)
returns public.bi_report_cleanup_jobs language plpgsql security definer set search_path='' as $$
declare j public.bi_report_cleanup_jobs;next_status text;
begin
  select * into j from public.bi_report_cleanup_jobs where id=p_job_id and status='processing' and lease_token=p_lease_token and lease_fence=p_lease_fence for update;
  if not found then raise exception using errcode='40001',message='report_cleanup_claim_lost';end if;
  next_status:=case when p_success then 'completed' when j.attempts<j.max_attempts then 'retry_pending' else 'failed' end;
  update public.bi_report_cleanup_jobs set status=next_status,available_at=case when next_status='retry_pending' then p_now+make_interval(secs=>least(3600,60*j.attempts)) else available_at end,
    last_error_code=case when p_success then null else left(coalesce(p_error_code,'cleanup_failed'),100) end,
    deleted_size_bytes=case when p_success then p_deleted_size_bytes else null end,deleted_sha256=case when p_success then p_deleted_sha256 else null end,
    completed_at=case when p_success then p_now else null end,lease_owner=null,lease_token=null,lease_expires_at=null where id=j.id returning * into j;
  if p_success then update public.bi_report_runs set artifact_deleted_at=p_now where id=j.report_id and artifact_deleted_at is null;end if;
  return j;
end;$$;

revoke all on function public.configure_bi_report_delivery166(integer,uuid,integer,uuid,bigint,boolean,integer[]),public.configure_bi_report_lifecycle166(integer,uuid,integer,bigint,smallint,boolean),public.enqueue_bi_report_lifecycle166(uuid),public.complete_bi_report_run166(uuid,uuid,bigint,text,jsonb,jsonb,text,text,text,integer,text,timestamptz),public.claim_bi_report_deliveries166(text,integer,integer,timestamptz),public.authorize_bi_report_delivery166(uuid,uuid,bigint),public.finish_bi_report_delivery166(uuid,uuid,bigint,text,text,text,timestamptz),public.claim_bi_report_cleanup166(text,integer,integer,timestamptz),public.authorize_bi_report_cleanup166(uuid,uuid,bigint,timestamptz),public.finish_bi_report_cleanup166(uuid,uuid,bigint,boolean,text,integer,text,timestamptz) from public,anon,authenticated;
grant execute on function public.configure_bi_report_delivery166(integer,uuid,integer,uuid,bigint,boolean,integer[]),public.configure_bi_report_lifecycle166(integer,uuid,integer,bigint,smallint,boolean),public.enqueue_bi_report_lifecycle166(uuid),public.complete_bi_report_run166(uuid,uuid,bigint,text,jsonb,jsonb,text,text,text,integer,text,timestamptz),public.claim_bi_report_deliveries166(text,integer,integer,timestamptz),public.authorize_bi_report_delivery166(uuid,uuid,bigint),public.finish_bi_report_delivery166(uuid,uuid,bigint,text,text,text,timestamptz),public.claim_bi_report_cleanup166(text,integer,integer,timestamptz),public.authorize_bi_report_cleanup166(uuid,uuid,bigint,timestamptz),public.finish_bi_report_cleanup166(uuid,uuid,bigint,boolean,text,integer,text,timestamptz) to service_role;

update public.application_schema_state set schema_version=166,applied_at=now() where contract_key='core' and schema_version=165;
notify pgrst,'reload schema';
commit;
