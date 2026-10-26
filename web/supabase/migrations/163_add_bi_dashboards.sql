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
    raise exception using errcode='P0001',message='migration_163_schema_state_missing';
  end if;
  if v_schema_version<>162 then
    raise exception using errcode='P0001',
      message=format('migration_163_expected_schema_162_got_%s',v_schema_version);
  end if;
end;
$$;

create table public.bi_dashboards (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
  project_id uuid not null,
  creator_user_id integer not null,
  name text not null,
  description text not null default '',
  revision bigint not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint bi_dashboards_project_fk163
    foreign key(project_id,tenant_id) references public.builder_projects(id,tenant_id) on delete cascade,
  constraint bi_dashboards_creator_fk163
    foreign key(creator_user_id,tenant_id) references public.users(id,tenant_id) on delete restrict,
  constraint bi_dashboards_name_check163 check(length(btrim(name)) between 1 and 120),
  constraint bi_dashboards_description_check163 check(length(description)<=1000),
  constraint bi_dashboards_revision_check163 check(revision>0),
  constraint bi_dashboards_scope_unique163 unique(id,tenant_id,project_id)
);

create index bi_dashboards_project163
on public.bi_dashboards(tenant_id,project_id,creator_user_id,updated_at desc);

create trigger set_bi_dashboards_updated_at163
before update on public.bi_dashboards
for each row execute function public.set_updated_at();

create table public.bi_dashboard_widgets (
  id uuid primary key default gen_random_uuid(),
  dashboard_id uuid not null,
  tenant_id integer not null,
  project_id uuid not null,
  creator_user_id integer not null,
  widget_type text not null,
  title text not null,
  dataset_id uuid not null,
  dataset_version_id uuid not null,
  version_policy text not null default 'pinned',
  analysis_spec jsonb not null,
  layout_config jsonb not null default '{}'::jsonb,
  display_options jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint bi_dashboard_widgets_dashboard_fk163
    foreign key(dashboard_id,tenant_id,project_id)
    references public.bi_dashboards(id,tenant_id,project_id) on delete cascade,
  constraint bi_dashboard_widgets_creator_fk163
    foreign key(creator_user_id,tenant_id) references public.users(id,tenant_id) on delete restrict,
  constraint bi_dashboard_widgets_dataset_fk163
    foreign key(dataset_id,tenant_id,project_id)
    references public.data_datasets(id,tenant_id,project_id) on delete restrict,
  constraint bi_dashboard_widgets_version_fk163
    foreign key(dataset_version_id,dataset_id,tenant_id)
    references public.data_dataset_versions(id,dataset_id,tenant_id) on delete restrict,
  constraint bi_dashboard_widgets_type_check163 check(widget_type in ('kpi','table','bar','line')),
  constraint bi_dashboard_widgets_title_check163 check(length(btrim(title)) between 1 and 160),
  constraint bi_dashboard_widgets_policy_check163 check(version_policy in ('pinned','latest_committed')),
  constraint bi_dashboard_widgets_spec_check163 check(
    jsonb_typeof(analysis_spec)='object' and octet_length(analysis_spec::text)<=8192
    and not analysis_spec ?| array['secret','token','authorization','headers','url','input_path','code','sql']
  ),
  constraint bi_dashboard_widgets_layout_check163 check(
    jsonb_typeof(layout_config)='object' and octet_length(layout_config::text)<=2048
  ),
  constraint bi_dashboard_widgets_display_check163 check(
    jsonb_typeof(display_options)='object' and octet_length(display_options::text)<=4096
  ),
  constraint bi_dashboard_widgets_scope_unique163 unique(id,dashboard_id,tenant_id,project_id)
);

create index bi_dashboard_widgets_dashboard163
on public.bi_dashboard_widgets(tenant_id,project_id,dashboard_id,created_at,id);

create trigger set_bi_dashboard_widgets_updated_at163
before update on public.bi_dashboard_widgets
for each row execute function public.set_updated_at();

alter table public.bi_dashboards enable row level security;
alter table public.bi_dashboard_widgets enable row level security;
revoke all on public.bi_dashboards,public.bi_dashboard_widgets from public,anon,authenticated;
grant select,insert,update,delete on public.bi_dashboards,public.bi_dashboard_widgets to service_role;

create function public.create_bi_dashboard163(
  p_tenant_id integer,p_project_id uuid,p_creator_user_id integer,
  p_name text,p_description text default ''
) returns public.bi_dashboards
language plpgsql security definer set search_path='' as $$
declare v_dashboard public.bi_dashboards;
begin
  if not exists(select 1 from public.builder_projects p
    where p.id=p_project_id and p.tenant_id=p_tenant_id and p.status<>'archived'
      and p.draft_schema->>'workspaceKind'='data') then
    raise exception using errcode='P0001',message='data_project_not_found';
  end if;
  if not exists(select 1 from public.users u
    where u.id=p_creator_user_id and u.tenant_id=p_tenant_id) then
    raise exception using errcode='P0001',message='dashboard_creator_not_found';
  end if;
  insert into public.bi_dashboards(tenant_id,project_id,creator_user_id,name,description)
  values(p_tenant_id,p_project_id,p_creator_user_id,btrim(p_name),coalesce(p_description,''))
  returning * into v_dashboard;
  return v_dashboard;
end;
$$;

create function public.update_bi_dashboard163(
  p_tenant_id integer,p_project_id uuid,p_creator_user_id integer,p_dashboard_id uuid,
  p_expected_revision bigint,p_name text,p_description text
) returns public.bi_dashboards
language plpgsql security definer set search_path='' as $$
declare v_dashboard public.bi_dashboards;
begin
  select * into v_dashboard from public.bi_dashboards d
  where d.id=p_dashboard_id and d.tenant_id=p_tenant_id and d.project_id=p_project_id
    and d.creator_user_id=p_creator_user_id for update;
  if not found then raise exception using errcode='P0001',message='dashboard_not_found';end if;
  if v_dashboard.revision<>p_expected_revision then
    raise exception using errcode='40001',message='dashboard_revision_conflict';end if;
  update public.bi_dashboards set name=btrim(p_name),description=coalesce(p_description,''),
    revision=revision+1 where id=p_dashboard_id returning * into v_dashboard;
  return v_dashboard;
end;
$$;

create function public.add_bi_dashboard_widget163(
  p_tenant_id integer,p_project_id uuid,p_creator_user_id integer,p_dashboard_id uuid,
  p_expected_revision bigint,p_widget_type text,p_title text,p_dataset_id uuid,
  p_dataset_version_id uuid,p_version_policy text,p_analysis_spec jsonb,
  p_layout_config jsonb default '{}'::jsonb,p_display_options jsonb default '{}'::jsonb
) returns jsonb
language plpgsql security definer set search_path='' as $$
declare v_dashboard public.bi_dashboards;v_widget public.bi_dashboard_widgets;
begin
  select * into v_dashboard from public.bi_dashboards d
  where d.id=p_dashboard_id and d.tenant_id=p_tenant_id and d.project_id=p_project_id
    and d.creator_user_id=p_creator_user_id for update;
  if not found then raise exception using errcode='P0001',message='dashboard_not_found';end if;
  if v_dashboard.revision<>p_expected_revision then
    raise exception using errcode='40001',message='dashboard_revision_conflict';end if;
  if not exists(select 1 from public.data_datasets d join public.data_dataset_versions v
    on v.dataset_id=d.id and v.tenant_id=d.tenant_id
    where d.id=p_dataset_id and d.tenant_id=p_tenant_id and d.project_id=p_project_id
      and d.creator_user_id=p_creator_user_id and d.status='active' and v.id=p_dataset_version_id) then
    raise exception using errcode='P0001',message='dataset_version_not_found';end if;
  insert into public.bi_dashboard_widgets(dashboard_id,tenant_id,project_id,creator_user_id,
    widget_type,title,dataset_id,dataset_version_id,version_policy,analysis_spec,layout_config,display_options)
  values(p_dashboard_id,p_tenant_id,p_project_id,p_creator_user_id,p_widget_type,btrim(p_title),
    p_dataset_id,p_dataset_version_id,p_version_policy,p_analysis_spec,
    coalesce(p_layout_config,'{}'::jsonb),coalesce(p_display_options,'{}'::jsonb))
  returning * into v_widget;
  update public.bi_dashboards set revision=revision+1 where id=p_dashboard_id returning * into v_dashboard;
  return jsonb_build_object('dashboard',to_jsonb(v_dashboard),'widget',to_jsonb(v_widget));
end;
$$;

create function public.update_bi_dashboard_widget163(
  p_tenant_id integer,p_project_id uuid,p_creator_user_id integer,p_dashboard_id uuid,
  p_widget_id uuid,p_expected_revision bigint,p_widget_type text,p_title text,p_dataset_id uuid,
  p_dataset_version_id uuid,p_version_policy text,p_analysis_spec jsonb,
  p_layout_config jsonb,p_display_options jsonb
) returns jsonb
language plpgsql security definer set search_path='' as $$
declare v_dashboard public.bi_dashboards;v_widget public.bi_dashboard_widgets;
begin
  select * into v_dashboard from public.bi_dashboards d
  where d.id=p_dashboard_id and d.tenant_id=p_tenant_id and d.project_id=p_project_id
    and d.creator_user_id=p_creator_user_id for update;
  if not found then raise exception using errcode='P0001',message='dashboard_not_found';end if;
  if v_dashboard.revision<>p_expected_revision then
    raise exception using errcode='40001',message='dashboard_revision_conflict';end if;
  if not exists(select 1 from public.data_datasets d join public.data_dataset_versions v
    on v.dataset_id=d.id and v.tenant_id=d.tenant_id
    where d.id=p_dataset_id and d.tenant_id=p_tenant_id and d.project_id=p_project_id
      and d.creator_user_id=p_creator_user_id and d.status='active' and v.id=p_dataset_version_id) then
    raise exception using errcode='P0001',message='dataset_version_not_found';end if;
  update public.bi_dashboard_widgets set widget_type=p_widget_type,title=btrim(p_title),
    dataset_id=p_dataset_id,dataset_version_id=p_dataset_version_id,version_policy=p_version_policy,
    analysis_spec=p_analysis_spec,layout_config=p_layout_config,display_options=p_display_options
  where id=p_widget_id and dashboard_id=p_dashboard_id and tenant_id=p_tenant_id
    and project_id=p_project_id and creator_user_id=p_creator_user_id returning * into v_widget;
  if not found then raise exception using errcode='P0001',message='dashboard_widget_not_found';end if;
  update public.bi_dashboards set revision=revision+1 where id=p_dashboard_id returning * into v_dashboard;
  return jsonb_build_object('dashboard',to_jsonb(v_dashboard),'widget',to_jsonb(v_widget));
end;
$$;

create function public.delete_bi_dashboard_widget163(
  p_tenant_id integer,p_project_id uuid,p_creator_user_id integer,p_dashboard_id uuid,
  p_widget_id uuid,p_expected_revision bigint
) returns public.bi_dashboards
language plpgsql security definer set search_path='' as $$
declare v_dashboard public.bi_dashboards;
begin
  select * into v_dashboard from public.bi_dashboards d
  where d.id=p_dashboard_id and d.tenant_id=p_tenant_id and d.project_id=p_project_id
    and d.creator_user_id=p_creator_user_id for update;
  if not found then raise exception using errcode='P0001',message='dashboard_not_found';end if;
  if v_dashboard.revision<>p_expected_revision then
    raise exception using errcode='40001',message='dashboard_revision_conflict';end if;
  delete from public.bi_dashboard_widgets where id=p_widget_id and dashboard_id=p_dashboard_id
    and tenant_id=p_tenant_id and project_id=p_project_id and creator_user_id=p_creator_user_id;
  if not found then raise exception using errcode='P0001',message='dashboard_widget_not_found';end if;
  update public.bi_dashboards set revision=revision+1 where id=p_dashboard_id returning * into v_dashboard;
  return v_dashboard;
end;
$$;

create function public.delete_bi_dashboard163(
  p_tenant_id integer,p_project_id uuid,p_creator_user_id integer,p_dashboard_id uuid,
  p_expected_revision bigint
) returns boolean
language plpgsql security definer set search_path='' as $$
declare v_dashboard public.bi_dashboards;
begin
  select * into v_dashboard from public.bi_dashboards d
  where d.id=p_dashboard_id and d.tenant_id=p_tenant_id and d.project_id=p_project_id
    and d.creator_user_id=p_creator_user_id for update;
  if not found then raise exception using errcode='P0001',message='dashboard_not_found';end if;
  if v_dashboard.revision<>p_expected_revision then
    raise exception using errcode='40001',message='dashboard_revision_conflict';end if;
  delete from public.bi_dashboards where id=p_dashboard_id;
  return true;
end;
$$;

revoke all on function public.create_bi_dashboard163(integer,uuid,integer,text,text),
  public.update_bi_dashboard163(integer,uuid,integer,uuid,bigint,text,text),
  public.add_bi_dashboard_widget163(integer,uuid,integer,uuid,bigint,text,text,uuid,uuid,text,jsonb,jsonb,jsonb),
  public.update_bi_dashboard_widget163(integer,uuid,integer,uuid,uuid,bigint,text,text,uuid,uuid,text,jsonb,jsonb,jsonb),
  public.delete_bi_dashboard_widget163(integer,uuid,integer,uuid,uuid,bigint),
  public.delete_bi_dashboard163(integer,uuid,integer,uuid,bigint)
from public,anon,authenticated;
grant execute on function public.create_bi_dashboard163(integer,uuid,integer,text,text),
  public.update_bi_dashboard163(integer,uuid,integer,uuid,bigint,text,text),
  public.add_bi_dashboard_widget163(integer,uuid,integer,uuid,bigint,text,text,uuid,uuid,text,jsonb,jsonb,jsonb),
  public.update_bi_dashboard_widget163(integer,uuid,integer,uuid,uuid,bigint,text,text,uuid,uuid,text,jsonb,jsonb,jsonb),
  public.delete_bi_dashboard_widget163(integer,uuid,integer,uuid,uuid,bigint),
  public.delete_bi_dashboard163(integer,uuid,integer,uuid,bigint)
to service_role;

update public.application_schema_state set schema_version=163,applied_at=now()
where contract_key='core';
notify pgrst,'reload schema';
commit;
