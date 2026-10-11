begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_142_schema_state_missing';end if;
 if v_schema_version <> 141 then raise exception 'migration_142_expected_schema_141_got_%',v_schema_version;end if;
end $$;
-- No historical answers are copied or rewritten.
alter table public.academy_exchange_opportunities add column application_form_id uuid,
 add constraint exchange_form_tenant_fk foreign key(tenant_id,application_form_id) references public.elearning_forms(tenant_id,id) on delete restrict;
alter table public.elearning_form_responses add column opportunity_id uuid,
 add constraint form_response_opportunity_fk foreign key(tenant_id,opportunity_id) references public.academy_exchange_opportunities(tenant_id,id) on delete restrict,
 add constraint exchange_response_member check(opportunity_id is null or user_id is not null);
create index form_response_opportunity_inbox on public.elearning_form_responses(tenant_id,opportunity_id,submitted_at desc) where opportunity_id is not null;
create unique index exchange_response_one_member on public.elearning_form_responses(tenant_id,opportunity_id,user_id) where opportunity_id is not null;
create table public.academy_exchange_decisions (
 tenant_id integer not null,response_id uuid not null,status text not null default 'submitted' check(status in ('submitted','under_review','approved','not_approved')),
 revision integer not null default 1 check(revision>0),reviewed_by integer,reviewed_at timestamptz,note text not null default '' check(length(note)<=4000),
 primary key(tenant_id,response_id),
 foreign key(tenant_id,response_id) references public.elearning_form_responses(tenant_id,id) on delete restrict,
 foreign key(tenant_id,reviewed_by) references public.tenant_memberships(tenant_id,user_id) on delete restrict
);
create table public.academy_exchange_decision_history (
 id uuid primary key default gen_random_uuid(),tenant_id integer not null,response_id uuid not null,actor_id integer not null,
 old_status text,new_status text not null,note text not null default '' check(length(note)<=4000),created_at timestamptz not null default now(),
 foreign key(tenant_id,response_id) references public.academy_exchange_decisions(tenant_id,response_id) on delete restrict,
 foreign key(tenant_id,actor_id) references public.tenant_memberships(tenant_id,user_id) on delete restrict
);
-- Existing immutable-history guard also protects the new response context.
create trigger exchange_history_immutable before update or delete on public.academy_exchange_decision_history for each row execute function public.guard_elearning_form_history();
create function public.exchange_approved_places(p_tenant integer,p_opportunity uuid) returns bigint
language sql stable set search_path='' as $$
 select (select count(*) from public.academy_applications where tenant_id=p_tenant and opportunity_id=p_opportunity and status='approved')+
 (select count(*) from public.academy_exchange_decisions d join public.elearning_form_responses r on(r.tenant_id,r.id)=(d.tenant_id,d.response_id) where r.tenant_id=p_tenant and r.opportunity_id=p_opportunity and d.status='approved');
$$;
create function public.assert_exchange_submission(p_tenant integer,p_user integer,p_opportunity uuid,p_form uuid) returns text
language plpgsql security definer set search_path='' as $$declare o public.academy_exchange_opportunities;cfg jsonb;begin
 cfg:=public.academy_assert_enabled(p_tenant,p_user);
 if not coalesce((cfg->>'exchange_programme_enabled')::boolean,false) or not coalesce((cfg->>'exchange_applications_enabled')::boolean,true) then raise exception using errcode='42501',message='exchange_disabled';end if;
 select * into o from public.academy_exchange_opportunities where tenant_id=p_tenant and id=p_opportunity for update;
 if not found or o.application_form_id is distinct from p_form then raise exception using errcode='P0002',message='opportunity_form_not_found';end if;
 if o.status<>'published' or (o.deadline is not null and o.deadline<=now()) then raise exception using errcode='42501',message='opportunity_closed';end if;
 if o.capacity is not null and public.exchange_approved_places(p_tenant,o.id)>=o.capacity then raise exception using errcode='42501',message='opportunity_full';end if;
 if p_user is null or not coalesce((public.academy_wallet_values(p_tenant,p_user)->>'exchange_eligible')::boolean,false) then raise exception using errcode='42501',message='active_learner_required';end if;
 return o.title;
end $$;
create or replace function public.manage_academy_opportunity(p_tenant integer,p_admin integer,p_id uuid,p_revision integer,p_data jsonb)
returns jsonb language plpgsql security definer set search_path='' as $$ declare result public.academy_exchange_opportunities; form_id uuid;begin
 perform public.academy_assert_enabled(p_tenant,p_admin,true);
 if not coalesce((select (settings->>'exchange_programme_enabled')::boolean from public.elearning_settings where tenant_id=p_tenant),false) then raise exception using errcode='42501',message='exchange_disabled';end if;
 form_id:=nullif(p_data->>'application_form_id','')::uuid;
 if form_id is not null and not exists(select 1 from public.elearning_forms where tenant_id=p_tenant and id=form_id and status<>'archived') then raise exception using errcode='23503',message='exchange_form_tenant_mismatch_or_archived';end if;
 if p_id is null then
  insert into public.academy_exchange_opportunities(tenant_id,created_by,title) values(p_tenant,p_admin,p_data->>'title') returning * into result;
 else
  select * into result from public.academy_exchange_opportunities where tenant_id=p_tenant and id=p_id for update;
  if not found then raise exception using errcode='P0002',message='opportunity_not_found';end if;
  if result.revision<>p_revision then raise exception using errcode='40001',message='opportunity_revision_conflict';end if;
  if result.status='archived' then raise exception using errcode='22023',message='opportunity_archived';end if;
 end if;
 if p_data->>'status'='published' and (form_id is null or not exists(select 1 from public.elearning_forms where tenant_id=p_tenant and id=form_id and status='active')) then raise exception using errcode='22023',message='active_application_form_required';end if;
 if p_id is not null and result.application_form_id is distinct from form_id and exists(select 1 from public.elearning_form_responses where tenant_id=p_tenant and opportunity_id=p_id) then raise exception using errcode='40001',message='application_form_locked_after_submission';end if;
 if (p_data->>'capacity')::integer is not null and public.exchange_approved_places(p_tenant,result.id)>(p_data->>'capacity')::integer then raise exception using errcode='22023',message='capacity_below_approved_places';end if;
 update public.academy_exchange_opportunities set application_form_id=form_id, title=p_data->>'title',short_description=coalesce(p_data->>'short_description',''),description=coalesce(p_data->>'description',''),host_institution=coalesce(p_data->>'host_institution',''),location=coalesce(p_data->>'location',''),start_date=(p_data->>'start_date')::date,end_date=(p_data->>'end_date')::date,deadline=(p_data->>'deadline')::timestamptz,requirements=coalesce(p_data->>'requirements',''),capacity=(p_data->>'capacity')::integer,status=p_data->>'status',revision=case when p_id is null then 1 else revision+1 end,updated_at=now() where tenant_id=p_tenant and id=result.id returning * into result;
 return to_jsonb(result);
end $$;

drop function public.submit_elearning_form(integer,integer,uuid,integer,uuid,uuid,text,jsonb,jsonb);
create function public.submit_elearning_form(p_tenant integer,p_user integer,p_form uuid,p_version integer,p_id uuid,p_key uuid,p_hash text,p_answers jsonb,p_files jsonb,p_opportunity uuid default null) returns jsonb
language plpgsql security definer set search_path='' as $$declare f public.elearning_forms;s jsonb;r public.elearning_form_responses;a jsonb;opportunity_title text;begin
 -- Opportunity first, then Form: same lock order for submission and approval.
 if p_opportunity is not null then
 perform public.commerce_assert_member(p_tenant,p_user);
 perform 1 from public.academy_exchange_opportunities where tenant_id=p_tenant and id=p_opportunity for update;
 if not found then raise exception using errcode='P0002',message='opportunity_form_not_found';end if;
 end if;
 select * into f from public.elearning_forms where tenant_id=p_tenant and id=p_form for update;
 if not found then raise exception using errcode='P0002',message='form_not_found';end if;
 select * into r from public.elearning_form_responses where tenant_id=p_tenant and form_id=p_form and idempotency_key=p_key;
 if found then
 if r.request_hash<>p_hash or r.user_id is distinct from p_user or r.opportunity_id is distinct from p_opportunity then raise exception using errcode='40001',message='form_submission_changed';end if;
 return jsonb_build_object('id',r.id,'duplicate',true);end if;
 if p_opportunity is not null then opportunity_title:=public.assert_exchange_submission(p_tenant,p_user,p_opportunity,p_form);end if;
 if f.status<>'active' or f.version<>p_version then raise exception using errcode='40001',message='form_not_active_or_changed';end if;
 select schema into s from public.elearning_form_versions where tenant_id=p_tenant and form_id=p_form and version=p_version;
 if p_user is not null then perform public.commerce_assert_member(p_tenant,p_user);end if;
 if coalesce(s->>'access','public')<>'public' and p_user is null then raise exception using errcode='42501',message='form_login_required';end if;
 if s->>'access'='enrolled' and not public.elearning_form_enrolled(p_tenant,p_user) then raise exception using errcode='42501',message='form_enrollment_required';end if;
 insert into public.elearning_form_responses(id,tenant_id,form_id,version,user_id,answers,idempotency_key,request_hash,opportunity_id) values(p_id,p_tenant,p_form,p_version,p_user,p_answers,p_key,p_hash,p_opportunity);
 for a in select value from jsonb_array_elements(p_files) loop
 insert into public.elearning_form_files(id,tenant_id,response_id,field_id,storage_key,filename,mime_type,size_bytes,sha256) values((a->>'id')::uuid,p_tenant,p_id,a->>'field_id',a->>'storage_key',a->>'filename',a->>'mime_type',(a->>'size_bytes')::integer,a->>'sha256');end loop;
 if p_opportunity is not null then
 insert into public.academy_exchange_decisions(tenant_id,response_id) values(p_tenant,p_id);
 insert into public.academy_exchange_decision_history(tenant_id,response_id,actor_id,new_status) values(p_tenant,p_id,p_user,'submitted');
 end if;
 if coalesce((s->>'notifyOwner')::boolean,true) then perform public.learning_notify_owners(p_tenant,'learning_form_response','elearning_form_response',p_id::text,case when p_opportunity is null then 'New form response' else 'New Exchange application for '||opportunity_title end,'/e-learning/forms/responses/'||p_id);end if;
 if coalesce((s->>'confirmSubmitter')::boolean,false) then perform public.enqueue_learning_notification(p_tenant,p_user,'learning_form_confirmation','elearning_form_response',p_id::text,'Your form response was received','/my-learning');end if;
 return jsonb_build_object('id',p_id,'duplicate',false);
end $$;
alter function public.academy_submit_application(integer,integer,text,jsonb,uuid) rename to academy_submit_application_legacy;
revoke all on function public.academy_submit_application_legacy(integer,integer,text,jsonb,uuid) from public,anon,authenticated,service_role;
create function public.academy_submit_application(p_tenant integer,p_user integer,p_kind text,p_details jsonb,p_key uuid) returns uuid
language plpgsql security definer set search_path='' as $$begin
 if p_kind='exchange' and not exists(select 1 from public.academy_applications where tenant_id=p_tenant and user_id=p_user and kind='exchange' and idempotency_key=p_key) then raise exception using errcode='42501',message='exchange_use_learning_forms';end if;
 return public.academy_submit_application_legacy(p_tenant,p_user,p_kind,p_details,p_key);
end $$;
revoke all on function public.academy_submit_application(integer,integer,text,jsonb,uuid) from public,anon,authenticated;
grant execute on function public.academy_submit_application(integer,integer,text,jsonb,uuid) to service_role;
create or replace function public.academy_opportunity_review_guard() returns trigger language plpgsql set search_path='' as $$declare limit_places integer;begin
 if new.opportunity_id is distinct from old.opportunity_id then raise exception using errcode='42501',message='opportunity_immutable';end if;
 if new.opportunity_id is not null and new.status='approved' and old.status<>'approved' then
  select capacity into limit_places from public.academy_exchange_opportunities where tenant_id=new.tenant_id and id=new.opportunity_id for update;
  if limit_places is not null and public.exchange_approved_places(new.tenant_id,new.opportunity_id)>=limit_places then raise exception using errcode='42501',message='opportunity_full';end if;
 end if;return new;
end $$;
create or replace function public.get_academy_open_opportunities(p_tenant integer,p_user integer default null,p_limit integer default 24) returns jsonb
language plpgsql stable security definer set search_path='' as $$declare cfg jsonb;begin
 select settings into cfg from public.elearning_settings where tenant_id=p_tenant;
 if not coalesce((cfg->>'programmes_enabled')::boolean,false) or not coalesce((cfg->>'exchange_programme_enabled')::boolean,false) then return '[]';end if;
 if p_user is not null then
  perform public.commerce_assert_member(p_tenant,p_user);
  if not coalesce((public.academy_wallet_values(p_tenant,p_user)->>'exchange_eligible')::boolean,false) then return '[]';end if;
 end if;
 return coalesce((select jsonb_agg(value) from(select to_jsonb(o)-array['tenant_id','created_by','revision'] as value from public.academy_exchange_opportunities o where o.tenant_id=p_tenant and o.status='published' and o.application_form_id is not null and exists(select 1 from public.elearning_forms f where f.tenant_id=o.tenant_id and f.id=o.application_form_id and f.status='active') and(o.deadline is null or o.deadline>now()) and(o.capacity is null or public.exchange_approved_places(o.tenant_id,o.id)<o.capacity) order by o.updated_at desc,o.id limit least(greatest(p_limit,1),100))s),'[]');
end $$;
create function public.exchange_opportunity_available(p_tenant integer,p_user integer,p_opportunity uuid) returns boolean
language plpgsql security definer set search_path='' as $$declare f uuid;begin
 select application_form_id into f from public.academy_exchange_opportunities where tenant_id=p_tenant and id=p_opportunity;
 if f is null then return false;end if;
 perform public.assert_exchange_submission(p_tenant,p_user,p_opportunity,f);
 return exists(select 1 from public.elearning_forms where tenant_id=p_tenant and id=f and status='active');
exception when insufficient_privilege or no_data_found then return false;
end $$;
revoke all on function public.exchange_opportunity_available(integer,integer,uuid) from public,anon,authenticated;
grant execute on function public.exchange_opportunity_available(integer,integer,uuid) to service_role;
create function public.review_exchange_response(p_tenant integer,p_admin integer,p_response uuid,p_revision integer,p_status text,p_note text) returns jsonb
language plpgsql security definer set search_path='' as $$declare d public.academy_exchange_decisions;r public.elearning_form_responses;o public.academy_exchange_opportunities;begin
 perform public.academy_assert_enabled(p_tenant,p_admin,true);
 select * into r from public.elearning_form_responses where tenant_id=p_tenant and id=p_response and opportunity_id is not null;
 if not found then raise exception using errcode='P0002',message='exchange_response_not_found';end if;
 select * into o from public.academy_exchange_opportunities where tenant_id=p_tenant and id=r.opportunity_id for update;
 select * into d from public.academy_exchange_decisions where tenant_id=p_tenant and response_id=p_response for update;
 if not found then raise exception using errcode='P0002',message='exchange_decision_not_found';end if;
 if d.revision<>p_revision then raise exception using errcode='40001',message='exchange_decision_changed';end if;
 if d.status not in ('submitted','under_review') or p_status not in ('under_review','approved','not_approved') or p_status=d.status or length(btrim(coalesce(p_note,''))) not between 1 and 4000 then raise exception using errcode='22023',message='exchange_decision_invalid';end if;
 if p_status='approved' and o.capacity is not null and public.exchange_approved_places(p_tenant,o.id)>=o.capacity then raise exception using errcode='42501',message='opportunity_full';end if;
 update public.academy_exchange_decisions set status=p_status,revision=revision+1,reviewed_by=p_admin,reviewed_at=now(),note=p_note where tenant_id=p_tenant and response_id=p_response;
 insert into public.academy_exchange_decision_history(tenant_id,response_id,actor_id,old_status,new_status,note) values(p_tenant,p_response,p_admin,d.status,p_status,p_note);
 perform public.enqueue_learning_notification(p_tenant,r.user_id,'learning_exchange_'||p_status,'exchange_decision',p_response::text,'Exchange application: '||p_status||' · '||o.title,'/my-learning/exchange/'||o.id);
 return (select to_jsonb(x) from public.academy_exchange_decisions x where tenant_id=p_tenant and response_id=p_response);
end $$;
do $$declare t text;begin
 foreach t in array array['academy_exchange_decisions','academy_exchange_decision_history'] loop
 execute format('alter table public.%I enable row level security',t);
 execute format('revoke all on public.%I from public,anon,authenticated,service_role',t);
 execute format('grant select on public.%I to service_role',t);
 end loop;
end $$;
revoke all on function public.exchange_approved_places(integer,uuid),public.assert_exchange_submission(integer,integer,uuid,uuid) from public,anon,authenticated,service_role;
revoke all on function public.submit_elearning_form(integer,integer,uuid,integer,uuid,uuid,text,jsonb,jsonb,uuid),public.review_exchange_response(integer,integer,uuid,integer,text,text) from public,anon,authenticated;
grant execute on function public.submit_elearning_form(integer,integer,uuid,integer,uuid,uuid,text,jsonb,jsonb,uuid),public.review_exchange_response(integer,integer,uuid,integer,text,text) to service_role;
update public.application_schema_state set schema_version=142,applied_at=now() where contract_key='core';
notify pgrst,'reload schema';
commit;
