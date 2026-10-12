begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_144_schema_state_missing';end if;
 if v_schema_version <> 143 then raise exception 'migration_144_expected_schema_143_got_%',v_schema_version;end if;
end $$;

--139's invoker trigger calls its intentionally private pure normalizer. The
--native service-role settings RPC otherwise fails before configuring any Form
--workflow. Retain the helper's private grants and empty search path; run only
--this row-normalization trigger under its existing owner.
alter function public.normalize_academy_programme_settings_write() security definer;

-- Presentation and review metadata only: no second definition, answer or file store.
create table public.elearning_form_reviews (
 tenant_id integer not null,response_id uuid not null,status text not null default 'submitted',
 revision integer not null default 1 check(revision>0),reviewer_id integer,reviewed_at timestamptz,
 note text not null default '' check(length(note)<=4000),
 primary key(tenant_id,response_id),
 check(status in ('submitted','under_review','approved','not_approved','suspended')),
 foreign key(tenant_id,response_id) references public.elearning_form_responses(tenant_id,id) on delete restrict,
 foreign key(tenant_id,reviewer_id) references public.tenant_memberships(tenant_id,user_id) on delete restrict
);
create table public.elearning_form_decision_history (
 id bigint generated always as identity primary key,tenant_id integer not null,response_id uuid not null,
 revision integer not null check(revision>1),actor_id integer not null,old_status text not null,new_status text not null,
 note text not null check(length(btrim(note)) between 1 and 4000),created_at timestamptz not null default now(),
 unique(tenant_id,response_id,revision),
 foreign key(tenant_id,response_id) references public.elearning_form_reviews(tenant_id,response_id) on delete restrict,
 foreign key(tenant_id,actor_id) references public.tenant_memberships(tenant_id,user_id) on delete restrict
);
create index elearning_form_reviews_status144 on public.elearning_form_reviews(tenant_id,status,response_id);
create index elearning_form_decision_history_response144 on public.elearning_form_decision_history(tenant_id,response_id,revision);
insert into public.elearning_form_reviews(tenant_id,response_id) select tenant_id,id from public.elearning_form_responses;
alter table public.academy_applications add column learning_form_response_id uuid;
alter table public.academy_applications add constraint academy_application_learning_response144
 foreign key(tenant_id,learning_form_response_id) references public.elearning_form_responses(tenant_id,id) on delete restrict;
create unique index academy_application_learning_response144 on public.academy_applications(tenant_id,learning_form_response_id) where learning_form_response_id is not null;

create function public.learning_form_actor144(p_tenant integer,p_user integer,p_admin boolean default false)
returns void language plpgsql security definer set search_path='' as $$begin
 -- SHARE locks prevent concurrent membership/account revocation through commit.
 perform 1 from public.tenants where tenant_id=p_tenant for share;
 perform 1 from public.users where id=p_user and tenant_id=p_tenant for share;
 perform 1 from public.tenant_memberships where tenant_id=p_tenant and user_id=p_user for share;
 perform public.commerce_assert_member(p_tenant,p_user,p_admin);
end $$;

create function public.learning_form_workflow144(p_tenant integer,p_user integer,p_schema jsonb)
returns text language plpgsql security definer set search_path='' as $$
declare kind text;cfg jsonb;begin
 kind:=coalesce(p_schema->'workflow'->>'kind','none');
 if kind not in ('none','affiliate','tuition','exchange') then raise exception using errcode='22023',message='form_workflow_invalid';end if;
 if kind='none' then return kind;end if;
 if p_user is null then raise exception using errcode='42501',message='form_workflow_authentication_required';end if;
 perform public.learning_form_actor144(p_tenant,p_user);
 perform 1 from public.elearning_settings where tenant_id=p_tenant for share;
 cfg:=public.academy_assert_enabled(p_tenant,p_user);
 if kind='affiliate' and (not coalesce((cfg->>'affiliates_enabled')::boolean,false) or not coalesce((cfg->>'affiliate_applications_enabled')::boolean,true)) then raise exception using errcode='42501',message='affiliates_disabled';end if;
 if kind='tuition' and (not coalesce((cfg->>'tuition_applications_enabled')::boolean,true) or not coalesce((public.academy_wallet(p_tenant,p_user)->>'tuition_eligible')::boolean,false)) then raise exception using errcode='42501',message='tuition_sales_required';end if;
 if kind='exchange' and (not coalesce((cfg->>'exchange_programme_enabled')::boolean,false) or not coalesce((cfg->>'exchange_applications_enabled')::boolean,true) or not public.elearning_form_enrolled(p_tenant,p_user)) then raise exception using errcode='42501',message='active_learner_required';end if;
 return kind;
end $$;

create function public.guard_learning_form_workflow144() returns trigger
language plpgsql security definer set search_path='' as $$
declare s jsonb;kind text;terms_id text;choice jsonb;begin
 select schema into s from public.elearning_form_versions where (tenant_id,form_id,version)=(new.tenant_id,new.form_id,new.version);
 kind:=coalesce(s->'workflow'->>'kind','none');
 if kind='none' then return new;end if;
 if new.user_id is null then raise exception using errcode='42501',message='form_workflow_authentication_required';end if;
 perform pg_advisory_xact_lock(new.tenant_id,new.user_id);
 perform public.learning_form_workflow144(new.tenant_id,new.user_id,s);
 terms_id:=s->'workflow'->>'termsFieldId';
 select field into choice from jsonb_array_elements(s->'sections') section,
 lateral jsonb_array_elements(section->'fields') field where field->>'id'=terms_id;
 if choice is null or choice->>'type'<>'checkboxes' or choice->>'required'<>'true'
 or jsonb_typeof(new.answers->terms_id) is distinct from 'array'
 or jsonb_array_length(new.answers->terms_id)<>1
 or not (choice->'options' @> (new.answers->terms_id)) then raise exception using errcode='22023',message='form_workflow_terms_required';end if;
 if exists(select 1 from public.elearning_form_responses r join public.elearning_form_reviews v on(v.tenant_id,v.response_id)=(r.tenant_id,r.id)
 join public.elearning_form_versions f on(f.tenant_id,f.form_id,f.version)=(r.tenant_id,r.form_id,r.version)
 where r.tenant_id=new.tenant_id and r.user_id=new.user_id and f.schema->'workflow'->>'kind'=kind and v.status in ('submitted','under_review','approved','suspended')) then raise exception using errcode='23505',message='form_workflow_duplicate';end if;
 return new;
end $$;
create trigger learning_form_workflow_submission144 before insert on public.elearning_form_responses for each row execute function public.guard_learning_form_workflow144();

create function public.initialize_learning_form_review144() returns trigger
language plpgsql security definer set search_path='' as $$
declare s jsonb;kind text;identifier uuid;cfg jsonb;begin
 insert into public.elearning_form_reviews(tenant_id,response_id) values(new.tenant_id,new.id);
 select schema into s from public.elearning_form_versions where(tenant_id,form_id,version)=(new.tenant_id,new.form_id,new.version);
 kind:=coalesce(s->'workflow'->>'kind','none');
 if kind in ('affiliate','tuition') then
  -- The canonical application retains only a reference and its terms snapshot.
  -- Answers and attachments remain exclusively in Forms, including arbitrary fields.
  select settings into cfg from public.elearning_settings where tenant_id=new.tenant_id;
  insert into public.academy_applications(tenant_id,user_id,kind,details,terms_snapshot,idempotency_key,learning_form_response_id)
  values(new.tenant_id,new.user_id,kind,jsonb_build_object('form_response_id',new.id,'terms_accepted',true),coalesce(cfg->>(kind||'_terms'),''),new.idempotency_key,new.id) returning id into identifier;
  insert into public.academy_workflow_history(tenant_id,entity_type,entity_id,actor_id,new_status)
  values(new.tenant_id,'application',identifier,new.user_id,'submitted');
 end if;
 return new;
end $$;
create trigger initialize_learning_form_review144 after insert on public.elearning_form_responses for each row execute function public.initialize_learning_form_review144();

create function public.guard_learning_form_decisions144() returns trigger language plpgsql set search_path='' as $$begin
 raise exception using errcode='42501',message='form_decision_history_immutable';
end $$;
create trigger learning_form_decision_history_immutable144 before update or delete on public.elearning_form_decision_history for each row execute function public.guard_learning_form_decisions144();

-- Keep the exact existing privileged domain implementation, including all
-- withdrawal accounting. Only the public dispatcher changes for Form bindings.
alter function public.academy_review(integer,integer,text,uuid,text,integer,text) rename to academy_review_core144;
revoke all on function public.academy_review_core144(integer,integer,text,uuid,text,integer,text) from public,anon,authenticated,service_role;

create function public.review_elearning_form_response(p_tenant integer,p_admin integer,p_response uuid,p_status text,p_revision integer,p_note text)
returns jsonb language plpgsql security definer set search_path='' as $$
declare r public.elearning_form_responses;v public.elearning_form_reviews;a public.academy_applications;s jsonb;kind text;u integer;begin
 perform public.learning_form_actor144(p_tenant,p_admin,true);
 if length(btrim(coalesce(p_note,''))) not between 1 and 4000 then raise exception using errcode='22023',message='form_review_note_required';end if;
 select user_id into u from public.elearning_form_responses where tenant_id=p_tenant and id=p_response;
 if not found then raise exception using errcode='P0002',message='form_response_not_found';end if;
 if u=p_admin then raise exception using errcode='42501',message='form_self_approval_forbidden';end if;
 if u is not null then perform pg_advisory_xact_lock(p_tenant,u);end if;
 select * into r from public.elearning_form_responses where tenant_id=p_tenant and id=p_response for update;
 select * into v from public.elearning_form_reviews where tenant_id=p_tenant and response_id=p_response for update;
 select schema into s from public.elearning_form_versions where(tenant_id,form_id,version)=(p_tenant,r.form_id,r.version);
 kind:=coalesce(s->'workflow'->>'kind','none');
 -- A retry must match its exact immutable actor/note/revision decision.
 if v.revision=p_revision+1 and exists(select 1 from public.elearning_form_decision_history where tenant_id=p_tenant and response_id=p_response and revision=v.revision and actor_id=p_admin and new_status=p_status and note=p_note) then return to_jsonb(v)||jsonb_build_object('duplicate',true);end if;
 if v.revision is distinct from p_revision then raise exception using errcode='40001',message='form_review_stale';end if;
 if not ((v.status in ('submitted','under_review') and p_status in ('under_review','approved','not_approved') and v.status<>p_status)
 or(kind='affiliate' and ((v.status='approved' and p_status='suspended') or(v.status='suspended' and p_status='approved')))) then raise exception using errcode='22023',message='form_review_transition_invalid';end if;
 if kind<>'none' then
  if p_status in ('approved','under_review') then perform public.learning_form_workflow144(p_tenant,u,s);
  else perform public.academy_assert_enabled(p_tenant,p_admin,true);end if;
 end if;
 if kind in ('affiliate','tuition') then
  select * into a from public.academy_applications where tenant_id=p_tenant and learning_form_response_id=p_response for update;
  if not found or a.user_id is distinct from u or a.kind is distinct from kind or a.status is distinct from v.status then raise exception using errcode='40001',message='form_domain_binding_mismatch';end if;
  perform public.academy_review_core144(p_tenant,p_admin,'application',a.id,p_status,a.revision,p_note);
 end if;
 update public.elearning_form_reviews set status=p_status,revision=revision+1,reviewer_id=p_admin,reviewed_at=now(),note=p_note where tenant_id=p_tenant and response_id=p_response returning * into v;
 insert into public.elearning_form_decision_history(tenant_id,response_id,revision,actor_id,old_status,new_status,note)
 values(p_tenant,p_response,v.revision,p_admin,coalesce((select new_status from public.elearning_form_decision_history where tenant_id=p_tenant and response_id=p_response order by revision desc limit 1),'submitted'),p_status,p_note);
 if u is not null then perform public.enqueue_learning_notification(p_tenant,u,'learning_form_decision','elearning_form_response',p_response::text||':'||v.revision,'Your form submission status was updated','/my-learning/form-responses/'||p_response);end if;
 return to_jsonb(v)||jsonb_build_object('duplicate',false);
end $$;

create function public.academy_review(p_tenant integer,p_admin integer,p_type text,p_id uuid,p_status text,p_revision integer,p_note text)
returns void language plpgsql security definer set search_path='' as $$declare response_id uuid;begin
 if p_type='application' then select learning_form_response_id into response_id from public.academy_applications where tenant_id=p_tenant and id=p_id;end if;
 if response_id is not null then
  -- Preserve the domain UI's expected revision contract. Both revisions advance
  -- together and all linked decisions return to the one Forms response inbox.
  perform public.review_elearning_form_response(p_tenant,p_admin,response_id,p_status,p_revision,p_note);
 else perform public.academy_review_core144(p_tenant,p_admin,p_type,p_id,p_status,p_revision,p_note);end if;
end $$;

create function public.get_elearning_form_applicant_response(p_tenant integer,p_user integer,p_response uuid)
returns jsonb language plpgsql security definer set search_path='' as $$declare r public.elearning_form_responses;v public.elearning_form_reviews;s jsonb;begin
 perform public.learning_form_actor144(p_tenant,p_user);
 select * into r from public.elearning_form_responses where tenant_id=p_tenant and user_id=p_user and id=p_response;
 if not found then raise exception using errcode='P0002',message='form_response_not_found';end if;
 select * into v from public.elearning_form_reviews where tenant_id=p_tenant and response_id=p_response;
 select schema into s from public.elearning_form_versions where(tenant_id,form_id,version)=(p_tenant,r.form_id,r.version);
 -- Internal notes, reviewer identity and private decision history are not exposed.
 return jsonb_build_object('id',r.id,'form_id',r.form_id,'version',r.version,'submitted_at',r.submitted_at,'answers',r.answers,'schema',s,'status',v.status,'revision',v.revision,'reviewed_at',v.reviewed_at);
end $$;

do $$declare table_name text;begin
 foreach table_name in array array['elearning_form_reviews','elearning_form_decision_history'] loop
 execute format('alter table public.%I enable row level security',table_name);
 execute format('revoke all on public.%I from public,anon,authenticated,service_role',table_name);
 execute format('grant select on public.%I to service_role',table_name);
 end loop;
end $$;
revoke all on function public.learning_form_actor144(integer,integer,boolean),public.learning_form_workflow144(integer,integer,jsonb),public.guard_learning_form_workflow144(),public.initialize_learning_form_review144(),public.guard_learning_form_decisions144() from public,anon,authenticated,service_role;
revoke all on function public.review_elearning_form_response(integer,integer,uuid,text,integer,text),public.academy_review(integer,integer,text,uuid,text,integer,text),public.get_elearning_form_applicant_response(integer,integer,uuid) from public,anon,authenticated;
grant execute on function public.review_elearning_form_response(integer,integer,uuid,text,integer,text),public.academy_review(integer,integer,text,uuid,text,integer,text),public.get_elearning_form_applicant_response(integer,integer,uuid) to service_role;
update public.application_schema_state set schema_version=144,applied_at=now() where contract_key='core';
notify pgrst,'reload schema';
commit;
