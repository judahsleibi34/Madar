begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_140_schema_state_missing';end if;
 if v_schema_version <> 139 then raise exception 'migration_140_expected_schema_139_got_%',v_schema_version;end if;
end $$;

-- Private metadata only; bytes reuse Madar's private Supabase asset storage.
create table public.academy_application_documents (
 id uuid primary key,tenant_id integer not null,application_id uuid not null,
 uploaded_by integer not null,storage_key text not null unique,
 filename text not null check(length(filename) between 1 and 160),
 mime_type text not null check(mime_type in ('application/pdf','image/png','image/jpeg')),
 size_bytes integer not null check(size_bytes between 1 and 5242880),
 sha256 text not null check(sha256 ~ '^[a-f0-9]{64}$'),
 created_at timestamptz not null default now(),removed_at timestamptz,
 unique(tenant_id,id),
 foreign key(tenant_id,application_id) references public.academy_applications(tenant_id,id) on delete restrict,
 foreign key(tenant_id,uploaded_by) references public.tenant_memberships(tenant_id,user_id) on delete restrict,
 check(storage_key='academy-private/tenant_'||tenant_id||'/application_'||application_id||'/'||id)
);
create index academy_document_application on public.academy_application_documents(tenant_id,application_id,created_at) where removed_at is null;

create table public.academy_exchange_opportunities (
 id uuid primary key default gen_random_uuid(),tenant_id integer not null references public.tenants(tenant_id) on delete restrict,
 title text not null check(length(btrim(title)) between 1 and 160),
 short_description text not null default '' check(length(short_description)<=1200),description text not null default '' check(length(description)<=12000),
 host_institution text not null default '' check(length(host_institution)<=200),location text not null default '' check(length(location)<=200),
 start_date date,end_date date,deadline timestamptz,requirements text not null default '' check(length(requirements)<=8000),
 capacity integer check(capacity between 1 and 100000),
 status text not null default 'draft' check(status in ('draft','published','closed','archived')),
 revision integer not null default 1 check(revision>0),created_by integer not null,updated_at timestamptz not null default now(),
 unique(tenant_id,id),foreign key(tenant_id,created_by) references public.tenant_memberships(tenant_id,user_id) on delete restrict,
 check(end_date is null or start_date is null or end_date>=start_date)
);
create index academy_opportunity_visibility on public.academy_exchange_opportunities(tenant_id,status,deadline);
alter table public.academy_applications add column opportunity_id uuid;
alter table public.academy_applications add constraint academy_application_opportunity_fk foreign key(tenant_id,opportunity_id) references public.academy_exchange_opportunities(tenant_id,id) on delete restrict;
alter table public.academy_applications add constraint academy_application_opportunity_kind check(opportunity_id is null or kind='exchange');
-- Preserve legacy general-exchange applications, but scope new opportunity
-- applications individually rather than blocking all future opportunities.
drop index public.academy_application_open;
create unique index academy_application_open on public.academy_applications(tenant_id,user_id,kind) where opportunity_id is null and status in ('submitted','under_review','approved','suspended');
create unique index academy_opportunity_application_open on public.academy_applications(tenant_id,user_id,opportunity_id) where opportunity_id is not null and status in ('submitted','under_review','approved','suspended');

-- Extend the existing contact mechanism; historical platform contacts stay NULL.
alter table public.contacts add column tenant_id integer references public.tenants(tenant_id) on delete restrict,
 add column project_id uuid,add column project_profile text not null default 'academy' check(project_profile='academy'),add column email text,add column subject text not null default '',
 add column read_at timestamptz,
 add constraint contact_project_tenant_fk foreign key(project_id,tenant_id,project_profile) references public.builder_projects(id,tenant_id,usage_profile) on delete restrict,
 add constraint contact_scope_pair check((tenant_id is null)=(project_id is null));
create index academy_contact_inbox on public.contacts(tenant_id,project_id,created_at desc) where tenant_id is not null;

create function public.manage_academy_opportunity(p_tenant integer,p_admin integer,p_id uuid,p_revision integer,p_data jsonb)
returns jsonb language plpgsql security definer set search_path='' as $$ declare result public.academy_exchange_opportunities;begin
 perform public.academy_assert_enabled(p_tenant,p_admin,true);
 if not coalesce((select (settings->>'exchange_programme_enabled')::boolean from public.elearning_settings where tenant_id=p_tenant),false) then raise exception using errcode='42501',message='exchange_disabled';end if;
 if p_id is null then
  insert into public.academy_exchange_opportunities(tenant_id,created_by,title) values(p_tenant,p_admin,p_data->>'title') returning * into result;
 else
  select * into result from public.academy_exchange_opportunities where tenant_id=p_tenant and id=p_id for update;
  if not found then raise exception using errcode='P0002',message='opportunity_not_found';end if;
  if result.revision<>p_revision then raise exception using errcode='40001',message='opportunity_revision_conflict';end if;
  if result.status='archived' then raise exception using errcode='22023',message='opportunity_archived';end if;
 end if;
 update public.academy_exchange_opportunities set title=p_data->>'title',short_description=coalesce(p_data->>'short_description',''),description=coalesce(p_data->>'description',''),host_institution=coalesce(p_data->>'host_institution',''),location=coalesce(p_data->>'location',''),start_date=(p_data->>'start_date')::date,end_date=(p_data->>'end_date')::date,deadline=(p_data->>'deadline')::timestamptz,requirements=coalesce(p_data->>'requirements',''),capacity=(p_data->>'capacity')::integer,status=p_data->>'status',revision=case when p_id is null then 1 else revision+1 end,updated_at=now() where tenant_id=p_tenant and id=result.id returning * into result;
 return to_jsonb(result);
end $$;

create function public.manage_academy_document(p_tenant integer,p_user integer,p_application uuid,p_id uuid,p_data jsonb)
returns jsonb language plpgsql security definer set search_path='' as $$ declare app public.academy_applications;doc public.academy_application_documents;begin
 perform public.academy_assert_enabled(p_tenant,p_user);
 select * into app from public.academy_applications where tenant_id=p_tenant and id=p_application for update;
 if not found or app.user_id<>p_user or app.kind<>'tuition' then raise exception using errcode='42501',message='document_forbidden';end if;
 if app.status not in ('submitted','under_review') then raise exception using errcode='42501',message='documents_locked';end if;
 if p_data is null then
  update public.academy_application_documents set removed_at=now() where tenant_id=p_tenant and application_id=p_application and id=p_id and removed_at is null returning * into doc;
  if not found then raise exception using errcode='P0002',message='document_not_found';end if;
 else
  if (select count(*) from public.academy_application_documents where tenant_id=p_tenant and application_id=p_application and removed_at is null)>=10 then raise exception using errcode='22023',message='document_limit';end if;
  insert into public.academy_application_documents(id,tenant_id,application_id,uploaded_by,storage_key,filename,mime_type,size_bytes,sha256) values(p_id,p_tenant,p_application,p_user,p_data->>'storage_key',p_data->>'filename',p_data->>'mime_type',(p_data->>'size_bytes')::integer,p_data->>'sha256') returning * into doc;
 end if;
 return to_jsonb(doc);
end $$;

create function public.academy_owner_dashboard(p_tenant integer,p_admin integer) returns jsonb
language plpgsql stable security definer set search_path='' as $$begin
 perform public.commerce_assert_member(p_tenant,p_admin,true);
 return jsonb_build_object(
 'total_learners',(select count(*) from public.elearning_learners where tenant_id=p_tenant),
 'active_learners',(select count(*) from public.elearning_learners where tenant_id=p_tenant and status='active'),
 'enrollments',(select count(*) from public.elearning_enrollments where tenant_id=p_tenant),
 'certificates',(select count(*) from public.elearning_credentials where tenant_id=p_tenant ),
 'affiliates',(select count(*) from public.academy_applications where tenant_id=p_tenant and kind='affiliate' and status='approved'),
 'support_eligible',(select count(*) from public.tenant_memberships where tenant_id=p_tenant and status='active' and coalesce((public.academy_wallet_values(p_tenant,user_id)->>'tuition_eligible')::boolean,false)),
 'applications',(select coalesce(jsonb_agg(to_jsonb(s)),'[]') from(select kind,status,count(*) as count from public.academy_applications where tenant_id=p_tenant group by kind,status)s),
 'purchases',(select count(*) from public.ecommerce_checkouts where tenant_id=p_tenant and state='paid' and provider<>'local_test'),
 'revenue',(select coalesce(jsonb_agg(to_jsonb(s)),'[]') from(select terms->>'currency' as currency,sum((terms->>'amount')::numeric) as amount from public.ecommerce_checkouts where tenant_id=p_tenant and state='paid' and provider<>'local_test' group by terms->>'currency')s),
 'withdrawals',(select coalesce(jsonb_agg(to_jsonb(s)),'[]') from(select currency,status,count(*) as count,sum(amount) as amount from public.academy_withdrawals where tenant_id=p_tenant group by currency,status)s),
 'rewards',(select coalesce(jsonb_agg(to_jsonb(s)),'[]') from(select r.currency,w.status,count(*) as sales,sum(r.amount) as amount from public.academy_referrals r join public.academy_referral_rewards w on(w.tenant_id,w.referral_id)=(r.tenant_id,r.id) join public.ecommerce_checkouts c on(c.tenant_id,c.id)=(w.tenant_id,w.checkout_id) where r.tenant_id=p_tenant and c.provider<>'local_test' group by r.currency,w.status)s),
 'wallets',(select coalesce(jsonb_agg(to_jsonb(s)),'[]') from(select currency,sum(available) as available,sum(pending) as pending from(select v->>'currency' as currency,(v->>'available')::numeric as available,(v->>'pending')::numeric as pending from public.tenant_memberships m cross join lateral(select public.academy_wallet_values(p_tenant,m.user_id) as v)x where m.tenant_id=p_tenant)s group by currency)s),
 'recent_activity',(select coalesce(jsonb_agg(to_jsonb(s)),'[]') from(select event_type,created_at from public.notification_events where tenant_id=p_tenant order by created_at desc limit 20)s));
end $$;

do $$declare tbl text;begin
 foreach tbl in array array['academy_application_documents','academy_exchange_opportunities'] loop
  execute format('alter table public.%I enable row level security',tbl);
  execute format('revoke all on public.%I from public,anon,authenticated,service_role',tbl);
  execute format('grant select on public.%I to service_role',tbl);
 end loop;
end $$;
revoke all on function public.manage_academy_opportunity(integer,integer,uuid,integer,jsonb),public.manage_academy_document(integer,integer,uuid,uuid,jsonb),public.academy_owner_dashboard(integer,integer) from public,anon,authenticated;
grant execute on function public.manage_academy_opportunity(integer,integer,uuid,integer,jsonb),public.manage_academy_document(integer,integer,uuid,uuid,jsonb),public.academy_owner_dashboard(integer,integer) to service_role;

create or replace function public.academy_submit_application(p_tenant integer,p_user integer,p_kind text,p_details jsonb,p_key uuid)
returns uuid language plpgsql security definer set search_path='' as $$ declare cfg jsonb; result uuid; field text; fields text[]; opportunity uuid; opp public.academy_exchange_opportunities; begin
 cfg:=public.academy_assert_enabled(p_tenant,p_user);
 perform pg_advisory_xact_lock(p_tenant,p_user);
 select id into result from public.academy_applications where tenant_id=p_tenant and user_id=p_user and kind=p_kind and idempotency_key=p_key;
 if result is not null then
  if not exists(select 1 from public.academy_applications where id=result and details=p_details) then raise exception using errcode='40001',message='application_idempotency_conflict';end if;
  return result;
 end if;
 if coalesce((cfg->>(p_kind||'_applications_enabled'))::boolean,true) is false then raise exception using errcode='42501',message='applications_disabled';end if;
 if p_kind='exchange' then
  opportunity:=nullif(p_details->>'opportunity_id','')::uuid;
  if opportunity is null and coalesce((cfg->>'exchange_opportunities_enabled')::boolean,false) then raise exception using errcode='22023',message='opportunity_required';end if;
  if opportunity is not null then
   select * into opp from public.academy_exchange_opportunities where tenant_id=p_tenant and id=opportunity for update;
   if not found or opp.status<>'published' or (opp.deadline is not null and opp.deadline<=now()) then raise exception using errcode='42501',message='opportunity_closed';end if;
   if opp.capacity is not null and (select count(*) from public.academy_applications where tenant_id=p_tenant and opportunity_id=opportunity and status='approved')>=opp.capacity then raise exception using errcode='42501',message='opportunity_full';end if;
  end if;
 end if;
 if p_key is null or p_kind is null or p_kind not in ('affiliate','tuition','exchange') or jsonb_typeof(p_details) is distinct from 'object' or octet_length(p_details::text)>20000 or p_details->>'terms_accepted' is distinct from 'true' then raise exception using errcode='22023',message='academy_application_invalid'; end if;
 if p_kind='affiliate' then
  if not coalesce((cfg->>'affiliates_enabled')::boolean,false) then raise exception using errcode='42501',message='affiliates_disabled';end if;
  fields:=array['full_name','email','country','experience','promotion_plan'];
 elsif p_kind='tuition' then
  if not coalesce((public.academy_wallet(p_tenant,p_user)->>'tuition_eligible')::boolean,false) then raise exception using errcode='42501',message='tuition_sales_required';end if;
  fields:=array['full_name','university','student_number','contact','tuition_fee','financial_difficulty','requested_amount'];
  if coalesce((cfg->>'tuition_support_information_required')::boolean,false) then fields:=fields||array['supporting_information'];end if;
 else
  if not coalesce((cfg->>'exchange_programme_enabled')::boolean,false) or not exists(select 1 from public.elearning_learners l join public.elearning_enrollments e on(e.tenant_id,e.learner_id)=(l.tenant_id,l.id) where l.tenant_id=p_tenant and l.user_id=p_user and l.status='active' and e.status='active' and public.elearning_enrollment_has_access(p_tenant,e.id)) then raise exception using errcode='42501',message='active_learner_required';end if;
  fields:=array['full_name','email','university','country','education','english_background','motivation','experience'];
 end if;
 foreach field in array fields loop if length(btrim(coalesce(p_details->>field,''))) not between 1 and 4000 then raise exception using errcode='22023',message='academy_application_required_fields';end if; end loop;
 if p_kind='tuition' and (coalesce(p_details->>'requested_amount','') !~ '^[0-9]{1,12}(\.[0-9]{1,2})?$' or coalesce(p_details->>'tuition_fee','') !~ '^[0-9]{1,12}(\.[0-9]{1,2})?$') then raise exception using errcode='22023',message='academy_application_invalid_amount';end if;
 if p_kind='tuition' and ((p_details->>'requested_amount')::numeric<=0 or (p_details->>'tuition_fee')::numeric<=0) then raise exception using errcode='22023',message='academy_application_invalid_amount';end if;
 insert into public.academy_applications(tenant_id,user_id,kind,details,terms_snapshot,idempotency_key,opportunity_id) values(p_tenant,p_user,p_kind,p_details,coalesce(cfg->>(p_kind||'_terms'),'')||case when opportunity is null then '' else E'\n'||opp.title||E'\n'||opp.requirements end,p_key,opportunity) returning id into result;
 insert into public.academy_workflow_history(tenant_id,entity_type,entity_id,actor_id,new_status) values(p_tenant,'application',result,p_user,'submitted');
 perform public.enqueue_learning_notification(p_tenant,p_user,'learning_'||p_kind||'_submitted','academy_application',result::text,'Application submitted','/my-learning/programmes');
 perform public.learning_notify_owners(p_tenant,'learning_'||p_kind||'_application','academy_application',result::text,'New programme application','/e-learning/programmes');
 return result;
end $$;


create function public.academy_opportunity_review_guard() returns trigger language plpgsql set search_path='' as $$declare limit_places integer;begin
 if new.opportunity_id is distinct from old.opportunity_id then raise exception using errcode='42501',message='opportunity_immutable';end if;
 if new.opportunity_id is not null and new.status='approved' and old.status<>'approved' then
  select capacity into limit_places from public.academy_exchange_opportunities where tenant_id=new.tenant_id and id=new.opportunity_id for update;
  if limit_places is not null and (select count(*) from public.academy_applications where tenant_id=new.tenant_id and opportunity_id=new.opportunity_id and status='approved')>=limit_places then raise exception using errcode='42501',message='opportunity_full';end if;
 end if;return new;
end $$;
create trigger academy_opportunity_review_guard before update on public.academy_applications for each row execute function public.academy_opportunity_review_guard();
revoke all on function public.academy_opportunity_review_guard() from public,anon,authenticated,service_role;

create or replace function public.validate_academy_builder_schema(p_schema jsonb) returns boolean
language plpgsql immutable set search_path='' as $$
declare node jsonb; element jsonb; page jsonb; slugs text[]:=array[]::text[]; ids text[]:=array[]::text[]; slug text; config jsonb; selected_id jsonb; field text;
begin
 if jsonb_typeof(p_schema) <> 'object' then return false; end if;
 if jsonb_typeof(p_schema->'pages') is distinct from 'array' or jsonb_array_length(p_schema->'pages') not between 1 and 50 then return false; end if;
 for page in select value from jsonb_array_elements(p_schema->'pages') loop
  if jsonb_typeof(page)<>'object' or jsonb_typeof(page->'id') is distinct from 'string' or coalesce(page->>'id','')='' or coalesce(page->>'access','public')<>'public' then return false;end if;
  slug:=page->>'slug';
  if slug is null or slug !~ '^/([a-z0-9-]+(/[a-z0-9-]+)*)?$' or slug like '%..%' or slug=any(slugs) or (page->>'id')=any(ids) then return false;end if;
  if split_part(trim(both '/' from slug),'/',1) in ('courses','plans','login','signup','auth','my-learning','account','checkout','assessments','api','admin','dashboard','settings','builder','page-builder') then return false;end if;
  slugs:=array_append(slugs,slug);ids:=array_append(ids,page->>'id');
 end loop;
 if not '/'=any(slugs) then return false;end if;
 if coalesce(p_schema->'forms','[]')<>'[]' or coalesce(p_schema->'workflows','[]')<>'[]'
 or coalesce(p_schema->'collections','[]')<>'[]' or coalesce(p_schema->'users','[]')<>'[]'
 or coalesce(p_schema->'roles','[]')<>'[]' then return false; end if;
 -- Recursive inspection covers direct, free and legacy row/column elements.
 for node in select value from jsonb_path_query(p_schema,'$.**.elements') as q(value)
 union all select value from jsonb_path_query(p_schema,'$.**.freeElements') as q(value) loop
  if jsonb_typeof(node)<>'array' then return false;end if;
  for element in select value from jsonb_array_elements(node) loop
   if coalesce(element->>'type','') not in ('heading','text','button','image','imageButton','imageCardButton','card','carousel','logoSlider','list','divider','thinDivider','metric','academyFeaturedCourses','academyCourseCollection','academyPlans','academyContinueLearning','academyInstructors','academyContact','academyExchangeOpportunities','academyProgrammeInfo') then return false;end if;
   if coalesce(element->>'connectedFormId','')<>'' then return false;end if;
   if element ? 'action' and jsonb_typeof(element->'action') not in ('object','null') then return false;end if;
   if coalesce(element->'action'->>'type','none') not in ('none','openUrl','scrollToSection','goToPage') then return false;end if;
   if element->>'type' like 'academy%' then
    if element - array['id','type','name','content','mode','position','styles','action','connectedFormId','academy'] <> '{}' then return false;end if;
    config:=coalesce(element->'academy','{}');
    if jsonb_typeof(config)<>'object' or config - array['heading','description','maxItems','courseIds','planIds','variant','featuredOnly','instructorIds'] <> '{}' then return false;end if;
    if coalesce(config->>'variant','grid') not in ('grid','compact') then return false;end if;
    foreach field in array array['heading','description'] loop
     if config ? field and (jsonb_typeof(config->field)<>'string' or length(config->>field)>case when field='heading' then 160 else 1200 end) then return false;end if;
    end loop;
    if config ? 'featuredOnly' and jsonb_typeof(config->'featuredOnly')<>'boolean' then return false;end if;
    if config ? 'maxItems' and (jsonb_typeof(config->'maxItems')<>'number' or (config->>'maxItems') !~ '^[0-9]+$' or (config->>'maxItems')::int not between 1 and 24) then return false;end if;
    foreach field in array array['courseIds','planIds','instructorIds'] loop
     if config ? field then
      if jsonb_typeof(config->field)<>'array' or jsonb_array_length(config->field)>24 then return false;end if;
      for selected_id in select value from jsonb_array_elements(config->field) loop
       if jsonb_typeof(selected_id)<>'string' then return false;end if;
       perform (selected_id#>>'{}')::uuid;
      end loop;
     end if;
    end loop;
   end if;
  end loop;
 end loop;
 return true;
exception when others then return false;
end $$;



create function public.academy_classified_students(p_tenant integer,p_admin integer,p_classification text default null,p_limit integer default 50,p_offset integer default 0) returns jsonb
language plpgsql stable security definer set search_path='' as $$declare cfg jsonb;result jsonb;begin
 perform public.commerce_assert_member(p_tenant,p_admin,true);
 select settings into cfg from public.elearning_settings where tenant_id=p_tenant;
 if p_classification is not null and p_classification not in ('institution','regular') then raise exception using errcode='22023',message='invalid_classification';end if;
 select coalesce(jsonb_agg(value),'[]') into result from (
  select to_jsonb(l)||jsonb_build_object('email_verified',coalesce(u.email_verified and u.account_status='active' and m.status='active',false),'institution_verified',matched,
  'classification',case when matched then coalesce(cfg->>'institution_student_label','Institution Student') else coalesce(cfg->>'regular_student_label','Regular Student') end) as value
  from public.elearning_learners l left join public.users u on u.id=l.user_id
  left join public.tenant_memberships m on(m.tenant_id,m.user_id)=(l.tenant_id,l.user_id)
  cross join lateral(select coalesce(u.email_verified and u.account_status='active' and m.status='active' and coalesce((cfg->>'institution_enabled')::boolean,false) and coalesce(cfg->'institution_email_domains','[]') ? lower(split_part(u.email,'@',2)),false) as matched)x
  where l.tenant_id=p_tenant and (p_classification is null or matched=(p_classification='institution')) order by l.name,l.id limit least(greatest(p_limit,1),100)+1 offset greatest(p_offset,0)
 )s;
 return jsonb_build_object('learners',result,'has_more',jsonb_array_length(result)>least(greatest(p_limit,1),100));
end $$;
revoke all on function public.academy_classified_students(integer,integer,text,integer,integer) from public,anon,authenticated;
grant execute on function public.academy_classified_students(integer,integer,text,integer,integer) to service_role;


create function public.get_academy_open_opportunities(p_tenant integer,p_user integer default null,p_limit integer default 24) returns jsonb
language plpgsql stable security definer set search_path='' as $$declare cfg jsonb;begin
 select settings into cfg from public.elearning_settings where tenant_id=p_tenant;
 if not coalesce((cfg->>'programmes_enabled')::boolean,false) or not coalesce((cfg->>'exchange_programme_enabled')::boolean,false) then return '[]';end if;
 if p_user is not null then
  perform public.commerce_assert_member(p_tenant,p_user);
  if not coalesce((public.academy_wallet_values(p_tenant,p_user)->>'exchange_eligible')::boolean,false) then return '[]';end if;
 end if;
 return coalesce((select jsonb_agg(value) from(select to_jsonb(o)-array['tenant_id','created_by','revision'] as value from public.academy_exchange_opportunities o where o.tenant_id=p_tenant and o.status='published' and(o.deadline is null or o.deadline>now()) and(o.capacity is null or (select count(*) from public.academy_applications a where a.tenant_id=o.tenant_id and a.opportunity_id=o.id and a.status='approved')<o.capacity) order by o.updated_at desc,o.id limit least(greatest(p_limit,1),100))s),'[]');
end $$;
revoke all on function public.get_academy_open_opportunities(integer,integer,integer) from public,anon,authenticated;
grant execute on function public.get_academy_open_opportunities(integer,integer,integer) to service_role;

update public.application_schema_state set schema_version = 140,applied_at=now() where contract_key='core';
notify pgrst,'reload schema';
commit;
