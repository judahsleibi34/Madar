begin;

do $$
declare
  v_schema_version public.application_schema_state.schema_version%type;
begin
  select schema_version into v_schema_version
  from public.application_schema_state
  where contract_key='core'
  for update;
  if v_schema_version is null then
    raise exception using errcode='P0001',message='migration_165_schema_state_missing';
  end if;
  if v_schema_version<>164 then
    raise exception using errcode='P0001',
      message=format('migration_165_expected_schema_164_got_%s',v_schema_version);
  end if;
end;
$$;

alter table public.bi_dashboards
  add constraint bi_dashboards_owner_scope_unique165
  unique(id,tenant_id,project_id,creator_user_id);

alter table public.bi_report_runs
  add constraint bi_report_runs_owner_scope_unique165
  unique(id,tenant_id,project_id,creator_user_id);

create table public.bi_dashboard_shares (
  id uuid primary key default gen_random_uuid(),
  dashboard_id uuid not null,
  tenant_id integer not null,
  project_id uuid not null,
  owner_user_id integer not null,
  member_user_id integer not null,
  permission text not null,
  revision bigint not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint bi_dashboard_shares_dashboard_fk165
    foreign key(dashboard_id,tenant_id,project_id,owner_user_id)
    references public.bi_dashboards(id,tenant_id,project_id,creator_user_id) on delete cascade,
  constraint bi_dashboard_shares_member_fk165
    foreign key(member_user_id,tenant_id)
    references public.tenant_memberships(user_id,tenant_id) on delete cascade,
  constraint bi_dashboard_shares_permission_check165 check(permission in ('viewer','editor')),
  constraint bi_dashboard_shares_revision_check165 check(revision>0),
  constraint bi_dashboard_shares_not_owner_check165 check(member_user_id<>owner_user_id),
  constraint bi_dashboard_shares_member_unique165 unique(dashboard_id,member_user_id)
);

create table public.bi_report_shares (
  id uuid primary key default gen_random_uuid(),
  report_id uuid not null,
  tenant_id integer not null,
  project_id uuid not null,
  owner_user_id integer not null,
  member_user_id integer not null,
  permission text not null default 'viewer',
  revision bigint not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint bi_report_shares_report_fk165
    foreign key(report_id,tenant_id,project_id,owner_user_id)
    references public.bi_report_runs(id,tenant_id,project_id,creator_user_id) on delete cascade,
  constraint bi_report_shares_member_fk165
    foreign key(member_user_id,tenant_id)
    references public.tenant_memberships(user_id,tenant_id) on delete cascade,
  constraint bi_report_shares_permission_check165 check(permission='viewer'),
  constraint bi_report_shares_revision_check165 check(revision>0),
  constraint bi_report_shares_not_owner_check165 check(member_user_id<>owner_user_id),
  constraint bi_report_shares_member_unique165 unique(report_id,member_user_id)
);

create index bi_dashboard_shares_member165
  on public.bi_dashboard_shares(tenant_id,project_id,member_user_id,updated_at desc);
create index bi_report_shares_member165
  on public.bi_report_shares(tenant_id,project_id,member_user_id,updated_at desc);

create trigger set_bi_dashboard_shares_updated_at165
before update on public.bi_dashboard_shares
for each row execute function public.set_updated_at();
create trigger set_bi_report_shares_updated_at165
before update on public.bi_report_shares
for each row execute function public.set_updated_at();

alter table public.bi_dashboard_shares enable row level security;
alter table public.bi_report_shares enable row level security;
revoke all on public.bi_dashboard_shares,public.bi_report_shares from public,anon,authenticated;
grant select,insert,update,delete on public.bi_dashboard_shares,public.bi_report_shares to service_role;

create function public.set_bi_dashboard_share165(
  p_tenant_id integer,p_project_id uuid,p_owner_user_id integer,p_dashboard_id uuid,
  p_expected_dashboard_revision bigint,p_member_user_id integer,p_permission text
) returns jsonb language plpgsql security definer set search_path='' as $$
declare d public.bi_dashboards;s public.bi_dashboard_shares;
begin
  if p_permission not in ('viewer','editor') then
    raise exception using errcode='22023',message='dashboard_share_permission_invalid';end if;
  select * into d from public.bi_dashboards where id=p_dashboard_id and tenant_id=p_tenant_id
    and project_id=p_project_id and creator_user_id=p_owner_user_id for update;
  if not found then raise exception using errcode='P0001',message='dashboard_not_found';end if;
  if d.revision<>p_expected_dashboard_revision then
    raise exception using errcode='40001',message='dashboard_revision_conflict';end if;
  if p_member_user_id=p_owner_user_id or not exists(
    select 1 from public.tenant_memberships m join public.users u on u.id=m.user_id
    where m.tenant_id=p_tenant_id and m.user_id=p_member_user_id and m.status='active'
      and u.account_status='active') then
    raise exception using errcode='42501',message='dashboard_share_member_forbidden';end if;
  insert into public.bi_dashboard_shares(dashboard_id,tenant_id,project_id,owner_user_id,member_user_id,permission)
  values(p_dashboard_id,p_tenant_id,p_project_id,p_owner_user_id,p_member_user_id,p_permission)
  on conflict(dashboard_id,member_user_id) do update set permission=excluded.permission,
    revision=public.bi_dashboard_shares.revision+1
  returning * into s;
  update public.bi_dashboards set revision=revision+1 where id=p_dashboard_id returning * into d;
  return jsonb_build_object('dashboard',to_jsonb(d),'share',to_jsonb(s));
end;$$;

create function public.revoke_bi_dashboard_share165(
  p_tenant_id integer,p_project_id uuid,p_owner_user_id integer,p_dashboard_id uuid,
  p_expected_dashboard_revision bigint,p_member_user_id integer
) returns public.bi_dashboards language plpgsql security definer set search_path='' as $$
declare d public.bi_dashboards;
begin
  select * into d from public.bi_dashboards where id=p_dashboard_id and tenant_id=p_tenant_id
    and project_id=p_project_id and creator_user_id=p_owner_user_id for update;
  if not found then raise exception using errcode='P0001',message='dashboard_not_found';end if;
  if d.revision<>p_expected_dashboard_revision then
    raise exception using errcode='40001',message='dashboard_revision_conflict';end if;
  delete from public.bi_dashboard_shares where dashboard_id=p_dashboard_id and tenant_id=p_tenant_id
    and project_id=p_project_id and owner_user_id=p_owner_user_id and member_user_id=p_member_user_id;
  if not found then raise exception using errcode='P0001',message='dashboard_share_not_found';end if;
  update public.bi_dashboards set revision=revision+1 where id=p_dashboard_id returning * into d;
  return d;
end;$$;

create function public.set_bi_report_share165(
  p_tenant_id integer,p_project_id uuid,p_owner_user_id integer,p_report_id uuid,
  p_member_user_id integer,p_expected_share_revision bigint default null
) returns public.bi_report_shares language plpgsql security definer set search_path='' as $$
declare r public.bi_report_runs;s public.bi_report_shares;
begin
  select * into r from public.bi_report_runs where id=p_report_id and tenant_id=p_tenant_id
    and project_id=p_project_id and creator_user_id=p_owner_user_id and archived_at is null for share;
  if not found then raise exception using errcode='P0001',message='report_not_found';end if;
  if r.status not in ('completed','needs_attention') then
    raise exception using errcode='55000',message='report_share_not_ready';end if;
  if p_member_user_id=p_owner_user_id or not exists(
    select 1 from public.tenant_memberships m join public.users u on u.id=m.user_id
    where m.tenant_id=p_tenant_id and m.user_id=p_member_user_id and m.status='active'
      and u.account_status='active') then
    raise exception using errcode='42501',message='report_share_member_forbidden';end if;
  select * into s from public.bi_report_shares where report_id=p_report_id
    and member_user_id=p_member_user_id for update;
  if found then
    if p_expected_share_revision is null or s.revision<>p_expected_share_revision then
      raise exception using errcode='40001',message='report_share_revision_conflict';end if;
    update public.bi_report_shares set revision=revision+1 where id=s.id returning * into s;
  else
    if p_expected_share_revision is not null then
      raise exception using errcode='40001',message='report_share_revision_conflict';end if;
    insert into public.bi_report_shares(report_id,tenant_id,project_id,owner_user_id,member_user_id,permission)
    values(p_report_id,p_tenant_id,p_project_id,p_owner_user_id,p_member_user_id,'viewer') returning * into s;
  end if;
  return s;
end;$$;

create function public.revoke_bi_report_share165(
  p_tenant_id integer,p_project_id uuid,p_owner_user_id integer,p_report_id uuid,
  p_member_user_id integer,p_expected_share_revision bigint
) returns boolean language plpgsql security definer set search_path='' as $$
begin
  if not exists(select 1 from public.bi_report_runs where id=p_report_id and tenant_id=p_tenant_id
    and project_id=p_project_id and creator_user_id=p_owner_user_id) then
    raise exception using errcode='P0001',message='report_not_found';end if;
  delete from public.bi_report_shares where report_id=p_report_id and tenant_id=p_tenant_id
    and project_id=p_project_id and owner_user_id=p_owner_user_id and member_user_id=p_member_user_id
    and revision=p_expected_share_revision;
  if not found then raise exception using errcode='40001',message='report_share_revision_conflict';end if;
  return true;
end;$$;

revoke all on function public.set_bi_dashboard_share165(integer,uuid,integer,uuid,bigint,integer,text) from public,anon,authenticated;
revoke all on function public.revoke_bi_dashboard_share165(integer,uuid,integer,uuid,bigint,integer) from public,anon,authenticated;
revoke all on function public.set_bi_report_share165(integer,uuid,integer,uuid,integer,bigint) from public,anon,authenticated;
revoke all on function public.revoke_bi_report_share165(integer,uuid,integer,uuid,integer,bigint) from public,anon,authenticated;
grant execute on function public.set_bi_dashboard_share165(integer,uuid,integer,uuid,bigint,integer,text) to service_role;
grant execute on function public.revoke_bi_dashboard_share165(integer,uuid,integer,uuid,bigint,integer) to service_role;
grant execute on function public.set_bi_report_share165(integer,uuid,integer,uuid,integer,bigint) to service_role;
grant execute on function public.revoke_bi_report_share165(integer,uuid,integer,uuid,integer,bigint) to service_role;

update public.application_schema_state
set schema_version=165,applied_at=now()
where contract_key='core' and schema_version=164;

notify pgrst,'reload schema';
commit;
