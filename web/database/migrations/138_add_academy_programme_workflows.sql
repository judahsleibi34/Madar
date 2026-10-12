begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_138_schema_state_missing'; end if;
 if v_schema_version <> 137 then raise exception 'migration_138_expected_schema_137_got_%',v_schema_version; end if;
end $$;

-- Applications are private tenant/user documents, never tenant staff roles.
create table public.academy_applications (
 id uuid primary key default gen_random_uuid(),tenant_id integer not null references public.tenants(tenant_id) on delete restrict,
 user_id integer not null references public.users(id) on delete restrict,
 kind text not null check(kind in ('affiliate','tuition','exchange')),
 status text not null default 'submitted' check(status in ('submitted','under_review','approved','not_approved','suspended')),
 details jsonb not null check(jsonb_typeof(details)='object'),terms_snapshot text not null default '',
 idempotency_key uuid not null,revision integer not null default 1 check(revision>0),
 created_at timestamptz not null default now(),updated_at timestamptz not null default now(),
 unique(tenant_id,id),unique(tenant_id,user_id,kind,idempotency_key)
);
create unique index academy_application_open on public.academy_applications(tenant_id,user_id,kind) where status in ('submitted','under_review','approved','suspended');
create index academy_application_review on public.academy_applications(tenant_id,kind,status,created_at desc);
create table public.academy_workflow_history (
 id bigint generated always as identity primary key,tenant_id integer not null references public.tenants(tenant_id) on delete restrict,
 entity_type text not null check(entity_type in ('application','withdrawal')),entity_id uuid not null,
 actor_id integer not null references public.users(id) on delete restrict,
 old_status text,new_status text not null,note text not null default '',created_at timestamptz not null default now()
);
create table public.academy_withdrawals (
 id uuid primary key default gen_random_uuid(),tenant_id integer not null references public.tenants(tenant_id) on delete restrict,
 user_id integer not null references public.users(id) on delete restrict,
 amount numeric(14,2) not null check(amount>0),currency text not null check(currency ~ '^[A-Z]{3}$'),
 payment_method text not null,payment_information text not null check(length(payment_information) between 1 and 4000),
 status text not null default 'pending' check(status in ('pending','approved','processing','paid','rejected')),
 idempotency_key uuid not null,revision integer not null default 1 check(revision>0),
 created_at timestamptz not null default now(),updated_at timestamptz not null default now(),paid_at timestamptz,
 unique(tenant_id,id),unique(tenant_id,user_id,idempotency_key),check((status='paid')=(paid_at is not null))
);
create index academy_withdrawal_review on public.academy_withdrawals(tenant_id,status,created_at desc);

create function public.academy_assert_enabled(p_tenant integer,p_user integer,p_admin boolean default false)
returns jsonb language plpgsql security definer set search_path='' as $$ declare cfg jsonb; begin
 perform public.commerce_assert_member(p_tenant,p_user,p_admin);
 select settings into cfg from public.elearning_settings where tenant_id=p_tenant;
 if not coalesce((cfg->>'eduhope_enabled')::boolean,false) then raise exception using errcode='42501',message='eduhope_disabled'; end if;
 return cfg;
end $$;

create function public.academy_can_refer(p_tenant integer,p_user integer)
returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.academy_applications where tenant_id=p_tenant and user_id=p_user and kind='affiliate' and status='approved')
 or exists(select 1 from public.ecommerce_checkouts c join public.ecommerce_entitlements e on(e.tenant_id,e.checkout_id)=(c.tenant_id,c.id)
 where c.tenant_id=p_tenant and c.user_id=p_user and c.state='paid' and c.provider<>'local_test' and (c.terms->>'amount')::numeric>0 and e.status='active'
 and exists(select 1 from public.ecommerce_payment_events v where v.tenant_id=c.tenant_id and v.checkout_id=c.id and v.state in ('paid','active')));
$$;
create function public.academy_verified_sales(p_tenant integer,p_user integer)
returns integer language sql stable security definer set search_path='' as $$
 select count(*)::integer from public.academy_referrals r join public.academy_referral_rewards w on(w.tenant_id,w.referral_id)=(r.tenant_id,r.id)
 join public.ecommerce_checkouts c on(c.tenant_id,c.id)=(w.tenant_id,w.checkout_id)
 where r.tenant_id=p_tenant and r.sender_id=p_user and w.status='earned' and c.state='paid' and c.provider<>'local_test';
$$;
create function public.academy_wallet_values(p_tenant integer,p_user integer)
returns jsonb language plpgsql stable security definer set search_path='' as $$ declare cfg jsonb; earned numeric; reserved numeric; paid numeric; sales integer; threshold integer; begin
 select settings into cfg from public.elearning_settings where tenant_id=p_tenant;
 select coalesce(sum(r.amount),0) into earned from public.academy_referrals r join public.academy_referral_rewards w on(w.tenant_id,w.referral_id)=(r.tenant_id,r.id)
 join public.ecommerce_checkouts c on(c.tenant_id,c.id)=(w.tenant_id,w.checkout_id)
 where r.tenant_id=p_tenant and r.sender_id=p_user and r.currency=coalesce(cfg->>'referral_reward_currency','USD') and w.status='earned' and c.provider<>'local_test' and c.state='paid';
 select coalesce(sum(amount) filter(where status in ('pending','approved','processing')),0),coalesce(sum(amount) filter(where status='paid'),0) into reserved,paid from public.academy_withdrawals where tenant_id=p_tenant and user_id=p_user and currency=coalesce(cfg->>'referral_reward_currency','USD');
 sales:=public.academy_verified_sales(p_tenant,p_user); threshold:=coalesce((cfg->>'tuition_sales_threshold')::integer,4);
 return jsonb_build_object('currency',coalesce(cfg->>'referral_reward_currency','USD'),'available',greatest(earned-reserved-paid,0),'debt',greatest(reserved+paid-earned,0),'pending',reserved,'total_earned',earned,'total_withdrawn',paid,'verified_sales',sales,'threshold',threshold,'remaining_sales',greatest(threshold-sales,0),'tuition_eligible',coalesce((cfg->>'tuition_support_enabled')::boolean,false) and sales>=threshold,'exchange_eligible',coalesce((cfg->>'exchange_programme_enabled')::boolean,false) and exists(select 1 from public.elearning_learners l join public.elearning_enrollments e on(e.tenant_id,e.learner_id)=(l.tenant_id,l.id) where l.tenant_id=p_tenant and l.user_id=p_user and l.status='active' and e.status='active' and public.elearning_enrollment_has_access(p_tenant,e.id)),'can_refer',public.academy_can_refer(p_tenant,p_user));
end $$;

create function public.academy_wallet(p_tenant integer,p_user integer) returns jsonb language plpgsql stable security definer set search_path='' as $$ begin
 perform public.academy_assert_enabled(p_tenant,p_user);
 return public.academy_wallet_values(p_tenant,p_user);
end $$;

create function public.academy_submit_application(p_tenant integer,p_user integer,p_kind text,p_details jsonb,p_key uuid)
returns uuid language plpgsql security definer set search_path='' as $$ declare cfg jsonb; result uuid; field text; fields text[]; begin
 cfg:=public.academy_assert_enabled(p_tenant,p_user);
 perform pg_advisory_xact_lock(p_tenant,p_user);
 select id into result from public.academy_applications where tenant_id=p_tenant and user_id=p_user and kind=p_kind and idempotency_key=p_key;
 if result is not null then
  if not exists(select 1 from public.academy_applications where id=result and details=p_details) then raise exception using errcode='40001',message='application_idempotency_conflict';end if;
  return result;
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
 insert into public.academy_applications(tenant_id,user_id,kind,details,terms_snapshot,idempotency_key) values(p_tenant,p_user,p_kind,p_details,coalesce(cfg->>(p_kind||'_terms'),''),p_key) returning id into result;
 insert into public.academy_workflow_history(tenant_id,entity_type,entity_id,actor_id,new_status) values(p_tenant,'application',result,p_user,'submitted');
 perform public.enqueue_learning_notification(p_tenant,p_user,'learning_'||p_kind||'_submitted','academy_application',result::text,'Application submitted','/my-learning/programmes');
 perform public.learning_notify_owners(p_tenant,'learning_'||p_kind||'_application','academy_application',result::text,'New programme application','/e-learning/programmes');
 return result;
end $$;

create function public.academy_request_withdrawal(p_tenant integer,p_user integer,p_amount numeric,p_method text,p_information text,p_confirm boolean,p_key uuid)
returns uuid language plpgsql security definer set search_path='' as $$ declare cfg jsonb; w jsonb; result uuid; begin
 cfg:=public.academy_assert_enabled(p_tenant,p_user); perform pg_advisory_xact_lock(p_tenant,p_user);
 select id into result from public.academy_withdrawals where tenant_id=p_tenant and user_id=p_user and idempotency_key=p_key;
 if result is not null then
  if p_confirm is distinct from true or not exists(select 1 from public.academy_withdrawals where id=result and amount=p_amount and payment_method=p_method and payment_information=p_information) then raise exception using errcode='40001',message='withdrawal_idempotency_conflict';end if;
  return result;
 end if;
 w:=public.academy_wallet(p_tenant,p_user);
 if p_confirm is distinct from true or p_key is null or p_amount is null or p_amount<>round(p_amount,2) or p_amount<coalesce((cfg->>'minimum_withdrawal_amount')::numeric,50) or p_amount>(w->>'available')::numeric or (w->>'debt')::numeric>0 or not (coalesce(cfg->'withdrawal_methods','["Palestinian Bank Transfer","PayPal"]'::jsonb) ? p_method) or length(btrim(coalesce(p_information,''))) not between 1 and 4000 then raise exception using errcode='22023',message='withdrawal_invalid_or_insufficient';end if;
 insert into public.academy_withdrawals(tenant_id,user_id,amount,currency,payment_method,payment_information,idempotency_key) values(p_tenant,p_user,p_amount,w->>'currency',p_method,p_information,p_key) returning id into result;
 insert into public.academy_workflow_history(tenant_id,entity_type,entity_id,actor_id,new_status) values(p_tenant,'withdrawal',result,p_user,'pending');
 perform public.enqueue_learning_notification(p_tenant,p_user,'learning_withdrawal_submitted','academy_withdrawal',result::text,'Withdrawal submitted','/my-learning/programmes');
 perform public.learning_notify_owners(p_tenant,'learning_withdrawal_request','academy_withdrawal',result::text,'New withdrawal request','/e-learning/programmes');
 return result;
end $$;

create function public.academy_review(p_tenant integer,p_admin integer,p_type text,p_id uuid,p_status text,p_revision integer,p_note text)
returns void language plpgsql security definer set search_path='' as $$ declare old_status text; rev integer; u integer; kind text; wallet jsonb; begin
 perform public.academy_assert_enabled(p_tenant,p_admin,true);
 if length(btrim(coalesce(p_note,''))) not between 1 and 4000 then raise exception using errcode='22023',message='review_reason_required';end if;
 -- Same member lock as request creation and reward reversal; obtain it before
 -- locking the request so concurrent requests cannot spend the same credit.
 if p_type='withdrawal' then select user_id into u from public.academy_withdrawals where tenant_id=p_tenant and id=p_id;
 elsif p_type='application' then select user_id into u from public.academy_applications where tenant_id=p_tenant and id=p_id;
 else raise exception using errcode='22023',message='review_invalid_type';end if;
 if u is null then raise exception using errcode='P0002',message='review_not_found';end if;
 perform pg_advisory_xact_lock(p_tenant,u);
 if p_type='withdrawal' then
  select status,revision into old_status,rev from public.academy_withdrawals where tenant_id=p_tenant and id=p_id for update;
  if old_status=p_status and old_status in ('paid','rejected') then return;end if;
  if rev is distinct from p_revision then raise exception using errcode='40001',message='review_stale';end if;
  if not ((old_status='pending' and p_status in ('approved','rejected')) or(old_status='approved' and p_status in ('processing','rejected')) or(old_status='processing' and p_status in ('paid','rejected'))) then raise exception using errcode='22023',message='withdrawal_invalid_transition';end if;
  wallet:=public.academy_wallet_values(p_tenant,u);
  if p_status<>'rejected' and exists(select 1 from public.academy_withdrawals where tenant_id=p_tenant and id=p_id and currency is distinct from wallet->>'currency') then raise exception using errcode='42501',message='withdrawal_currency_mismatch';end if;
  if p_status<>'rejected' and (wallet->>'debt')::numeric>0 then raise exception using errcode='42501',message='withdrawal_credit_reversed';end if;
  update public.academy_withdrawals set status=p_status,revision=revision+1,updated_at=now(),paid_at=case when p_status='paid' then now() end where tenant_id=p_tenant and id=p_id;
 else
  select status,revision,a.kind into old_status,rev,kind from public.academy_applications a where tenant_id=p_tenant and id=p_id for update;
  if rev is distinct from p_revision then raise exception using errcode='40001',message='review_stale';end if;
  if not ((old_status in ('submitted','under_review') and p_status in ('under_review','approved','not_approved') and old_status<>p_status) or(kind='affiliate' and ((old_status='approved' and p_status='suspended') or(old_status='suspended' and p_status='approved')))) then raise exception using errcode='22023',message='application_invalid_transition';end if;
  if kind='tuition' and p_status='approved' and not (public.academy_wallet(p_tenant,u)->>'tuition_eligible')::boolean then raise exception using errcode='42501',message='tuition_sales_required';end if;
  update public.academy_applications set status=p_status,revision=revision+1,updated_at=now() where tenant_id=p_tenant and id=p_id;
 end if;
 insert into public.academy_workflow_history(tenant_id,entity_type,entity_id,actor_id,old_status,new_status,note) values(p_tenant,p_type,p_id,p_admin,old_status,p_status,p_note);
 perform public.enqueue_learning_notification(p_tenant,u,'learning_'||p_type||'_'||p_status,'academy_'||p_type,p_id::text||':'||(rev+1),'Request status updated','/my-learning/programmes');
end $$;

-- Preserve the existing account projection for other academies. The opt-in
-- profile changes code eligibility, never legacy reward amounts/history.
alter function public.get_academy_referral_account(integer,integer) rename to get_academy_referral_account_legacy;
create or replace function public.get_academy_referral_account_legacy(p_tenant_id integer,p_user_id integer)
returns jsonb language plpgsql security definer set search_path='' as $$
declare cfg jsonb; token uuid; balances jsonb; history jsonb;
begin
 perform public.commerce_assert_member(p_tenant_id,p_user_id);
 select settings into cfg from public.elearning_settings where tenant_id=p_tenant_id;
 if coalesce((cfg->>'referral_rewards_enabled')::boolean,false) and (not coalesce((cfg->>'eduhope_enabled')::boolean,false) or public.academy_can_refer(p_tenant_id,p_user_id)) then
  insert into public.academy_referral_codes(tenant_id,user_id) values(p_tenant_id,p_user_id) on conflict(tenant_id,user_id) do nothing;
  select code into token from public.academy_referral_codes where tenant_id=p_tenant_id and user_id=p_user_id;
 end if;
 select coalesce(jsonb_agg(to_jsonb(b)),'[]'::jsonb) into balances from (
  select r.currency,(ch.provider='local_test') as simulated,coalesce(sum(r.amount) filter(where w.status='earned'),0) as amount
  from public.academy_referrals r join public.academy_referral_rewards w on w.tenant_id=r.tenant_id and w.referral_id=r.id
  join public.ecommerce_checkouts ch on ch.tenant_id=w.tenant_id and ch.id=w.checkout_id
  where r.tenant_id=p_tenant_id and r.sender_id=p_user_id group by r.currency,(ch.provider='local_test') order by r.currency
 ) b;
 select coalesce(jsonb_agg(to_jsonb(h)),'[]'::jsonb) into history from (
  select r.id,r.amount,r.currency,r.created_at,coalesce(w.status,'pending') as status,w.earned_at,w.reversed_at,coalesce(ch.provider='local_test',false) as simulated
  from public.academy_referrals r left join public.academy_referral_rewards w on w.tenant_id=r.tenant_id and w.referral_id=r.id
  left join public.ecommerce_checkouts ch on ch.tenant_id=w.tenant_id and ch.id=w.checkout_id
  where r.tenant_id=p_tenant_id and r.sender_id=p_user_id order by r.created_at desc,r.id limit 50
 ) h;
 return jsonb_build_object('available',true,'enabled',coalesce((cfg->>'referral_rewards_enabled')::boolean,false),'code',token,'reward_amount',cfg->>'referral_reward_amount','currency',cfg->>'referral_reward_currency','balances',balances,'history',history,'referred_count',(select count(*) from public.academy_referrals where tenant_id=p_tenant_id and sender_id=p_user_id),'earned_count',(select count(*) from public.academy_referrals r join public.academy_referral_rewards w on w.tenant_id=r.tenant_id and w.referral_id=r.id where r.tenant_id=p_tenant_id and r.sender_id=p_user_id and w.status='earned'));
end $$;


create function public.get_academy_referral_account(p_tenant_id integer,p_user_id integer)
returns jsonb language plpgsql security definer set search_path='' as $$ declare cfg jsonb; result jsonb; begin
 perform public.commerce_assert_member(p_tenant_id,p_user_id);
 select settings into cfg from public.elearning_settings where tenant_id=p_tenant_id;
 result:=public.get_academy_referral_account_legacy(p_tenant_id,p_user_id);
 if coalesce((cfg->>'eduhope_enabled')::boolean,false) then result:=result||jsonb_build_object('wallet',public.academy_wallet(p_tenant_id,p_user_id));end if;
 return result;
end $$;

create function public.academy_referral_eligibility_guard() returns trigger language plpgsql security definer set search_path='' as $$ begin
 if exists(select 1 from public.elearning_settings where tenant_id=new.tenant_id and coalesce((settings->>'eduhope_enabled')::boolean,false)) and not public.academy_can_refer(new.tenant_id,new.sender_id) then raise exception using errcode='42501',message='referral_purchase_or_affiliate_required';end if;
 return new;
end $$;
create trigger academy_referral_eligibility before insert on public.academy_referrals for each row execute function public.academy_referral_eligibility_guard();

-- Refund and withdrawal operations serialize on the same referrer's lock.
create function public.academy_reward_wallet_lock() returns trigger language plpgsql security definer set search_path='' as $$ declare u integer; begin
 select sender_id into u from public.academy_referrals where tenant_id=new.tenant_id and id=new.referral_id;
 perform pg_advisory_xact_lock(new.tenant_id,u);
 return new;
end $$;
create trigger academy_reward_wallet_lock before insert or update on public.academy_referral_rewards for each row execute function public.academy_reward_wallet_lock();

create function public.academy_private_immutable() returns trigger language plpgsql set search_path='' as $$ begin raise exception using errcode='42501',message='academy_history_immutable';end $$;
create trigger academy_history_immutable before update or delete on public.academy_workflow_history for each row execute function public.academy_private_immutable();

do $$ declare tbl text; f record;begin
 foreach tbl in array array['academy_applications','academy_withdrawals','academy_workflow_history'] loop
  execute format('alter table public.%I enable row level security',tbl);
  execute format('revoke all on public.%I from public,anon,authenticated,service_role',tbl);
  execute format('grant select on public.%I to service_role',tbl);
 end loop;
 for f in select p.oid::regprocedure signature from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and (p.proname like 'academy_%' or p.proname in ('get_academy_referral_account','get_academy_referral_account_legacy')) loop
  execute 'revoke all on function '||f.signature||' from public,anon,authenticated,service_role';
 end loop;
end $$;
grant execute on function public.get_academy_referral_account(integer,integer),public.academy_wallet(integer,integer),public.academy_submit_application(integer,integer,text,jsonb,uuid),public.academy_request_withdrawal(integer,integer,numeric,text,text,boolean,uuid),public.academy_review(integer,integer,text,uuid,text,integer,text) to service_role;
-- CEFR configuration extends the existing certificate engine at section scope.
-- Templates, credential snapshots, downloads, verification and revocation remain
-- the same. Course completion certificates keep their original configuration.
create table public.elearning_section_certificates (
 tenant_id integer not null,course_id uuid not null,section_id uuid not null,
 cefr_level text not null check(cefr_level in ('A1','A2','B1','B2','C1')),
 template_id uuid not null,enabled boolean not null default true,
 primary key(tenant_id,course_id,section_id),unique(tenant_id,course_id,cefr_level),
 foreign key(tenant_id,course_id,section_id) references public.elearning_sections(tenant_id,course_id,id) on delete restrict,
 foreign key(tenant_id,template_id) references public.elearning_certificate_templates(tenant_id,id) on delete restrict
);
alter table public.elearning_section_certificates enable row level security;
revoke all on public.elearning_section_certificates from public,anon,authenticated,service_role;
grant select on public.elearning_section_certificates to service_role;
alter table public.elearning_credentials drop constraint elearning_credentials_credential_type_check;
alter table public.elearning_credentials add constraint elearning_credentials_credential_type_check check(credential_type in ('course_completion','cefr_A1','cefr_A2','cefr_B1','cefr_B2','cefr_C1'));

create function public.configure_elearning_cefr(p_tenant integer,p_admin integer,p_course uuid,p_section uuid,p_level text,p_template uuid,p_enabled boolean)
returns void language plpgsql security definer set search_path='' as $$ begin
 perform public.academy_assert_enabled(p_tenant,p_admin,true);
 perform pg_advisory_xact_lock(125,p_tenant);
 if p_enabled and not exists(select 1 from public.elearning_assessment_placements p join public.elearning_assessments a on(a.tenant_id,a.id)=(p.tenant_id,p.assessment_id) where p.tenant_id=p_tenant and p.course_id=p_course and p.section_id=p_section and p.placement_type='section' and p.required_for_completion and p.archived_at is null and a.status='published' and a.passing_score=70 and (a.max_attempts is null or a.max_attempts>1)) then raise exception using errcode='22023',message='cefr_final_exam_required';end if;
 insert into public.elearning_section_certificates(tenant_id,course_id,section_id,cefr_level,template_id,enabled) values(p_tenant,p_course,p_section,p_level,p_template,p_enabled)
 on conflict(tenant_id,course_id,section_id) do update set cefr_level=excluded.cefr_level,template_id=excluded.template_id,enabled=excluded.enabled;
 insert into public.audit_logs(tenant_id,actor_user_id,action,target_type,target_id,metadata) values(p_tenant,p_admin,'elearning.cefr.configured','elearning_section',p_section::text,jsonb_build_object('course_id',p_course,'cefr_level',p_level,'enabled',p_enabled));
end $$;
create function public.elearning_issue_section_credential() returns trigger language plpgsql security definer set search_path='' as $$
declare cfg public.elearning_section_certificates%rowtype;t public.elearning_certificate_templates%rowtype;l public.elearning_learners%rowtype;issued uuid;begin
 if new.scope<>'section' then return new;end if;
 select * into cfg from public.elearning_section_certificates where tenant_id=new.tenant_id and course_id=new.course_id and section_id=new.section_id and enabled;if not found then return new;end if;
 select * into t from public.elearning_certificate_templates where tenant_id=new.tenant_id and id=cfg.template_id and status='active';if not found then return new;end if;
 select l0.* into l from public.elearning_enrollments e join public.elearning_learners l0 on(l0.tenant_id,l0.id)=(e.tenant_id,e.learner_id) where e.tenant_id=new.tenant_id and e.id=new.enrollment_id;
 if l.user_id is null then return new;end if;
 insert into public.elearning_credentials(tenant_id,learner_id,user_id,course_id,completion_id,credential_type,completed_at,snapshot)
 values(new.tenant_id,l.id,l.user_id,new.course_id,new.id,'cefr_'||cfg.cefr_level,new.completed_at,jsonb_build_object('schema',138,'design',t.design,'learner_name',l.name,'course_name',(select name from public.elearning_courses where tenant_id=new.tenant_id and id=new.course_id)||' — CEFR '||cfg.cefr_level,'cefr_level',cfg.cefr_level,'template_revision',t.revision))
 on conflict(tenant_id,learner_id,course_id,completion_id,credential_type) do nothing returning id into issued;
 if issued is not null then insert into public.audit_logs(tenant_id,action,target_type,target_id,metadata) values(new.tenant_id,'elearning.credential.issued','elearning_credential',issued::text,jsonb_build_object('completion_id',new.id,'cefr_level',cfg.cefr_level));end if;
 return new;
end $$;
create trigger elearning_cefr_credential after insert on public.elearning_completion_events for each row execute function public.elearning_issue_section_credential();
revoke all on function public.configure_elearning_cefr(integer,integer,uuid,uuid,text,uuid,boolean),public.elearning_issue_section_credential() from public,anon,authenticated;
grant execute on function public.configure_elearning_cefr(integer,integer,uuid,uuid,text,uuid,boolean) to service_role;

-- Eligibility notices are prospective; refunds update the authoritative count.
create function public.academy_tuition_eligibility_notice() returns trigger language plpgsql security definer set search_path='' as $$ declare u integer; cfg jsonb; threshold integer; begin
 select settings into cfg from public.elearning_settings where tenant_id=new.tenant_id;
 if not coalesce((cfg->>'eduhope_enabled')::boolean,false) or not coalesce((cfg->>'tuition_support_enabled')::boolean,false) then return new;end if;
 select sender_id into u from public.academy_referrals where tenant_id=new.tenant_id and id=new.referral_id;
 threshold:=coalesce((cfg->>'tuition_sales_threshold')::integer,4);
 if new.status='earned' and public.academy_verified_sales(new.tenant_id,u)=threshold then
  perform public.enqueue_learning_notification(new.tenant_id,u,'learning_tuition_eligible','academy_reward',new.referral_id::text,'You are eligible to apply for Tuition Support','/my-learning/programmes');
 elsif new.status='reversed' then
  perform public.enqueue_learning_notification(new.tenant_id,u,'learning_tuition_eligibility_changed','academy_reward',new.referral_id::text,'Your verified referral sales count changed','/my-learning/programmes');
 end if;return new;
end $$;
create trigger academy_tuition_eligibility_notice after insert or update of status on public.academy_referral_rewards for each row execute function public.academy_tuition_eligibility_notice();
revoke all on function public.academy_tuition_eligibility_notice() from public,anon,authenticated;

create function public.academy_owner_report(p_tenant integer,p_admin integer,p_course uuid default null,p_user integer default null,p_section uuid default null,p_from timestamptz default null,p_to timestamptz default null,p_status text default null)
returns jsonb language plpgsql stable security definer set search_path='' as $$ declare course_row record; row jsonb; rows jsonb:='[]';begin
 perform public.commerce_assert_member(p_tenant,p_admin,true);
 for course_row in select id,name from public.elearning_courses where tenant_id=p_tenant and (p_course is null or id=p_course) order by name,id loop
  for row in select value from jsonb_array_elements(public.get_elearning_progress_records(p_tenant,course_row.id,true,true)->'enrollments') loop
   if (p_user is null or (row->>'user_id')::integer=p_user) and (p_from is null or (row->>'enrolled_at')::timestamptz>=p_from) and(p_to is null or(row->>'enrolled_at')::timestamptz<=p_to) and(p_status is null or row->>'progress_status'=p_status or row->>'enrollment_status'=p_status) and (p_section is null or exists(select 1 from jsonb_array_elements(row->'sections') s where(s->>'id')::uuid=p_section)) then
    rows:=rows||jsonb_build_array(row||jsonb_build_object('course_id',course_row.id,'course_name',course_row.name));
   end if;
  end loop;
 end loop;
 return jsonb_build_object('enrollments',rows,'summary',jsonb_build_object(
 'enrollments',jsonb_array_length(rows),'students',(select count(distinct x->>'learner_id') from jsonb_array_elements(rows) x),'active_enrollments',(select count(*) from jsonb_array_elements(rows) x where x->>'enrollment_status'='active'),
 'completed_courses',(select count(*) from jsonb_array_elements(rows) x where x->>'progress_status'='completed'),
 'completed_topics',(select coalesce(sum((x->>'completed_lessons')::integer),0) from jsonb_array_elements(rows) x),
 'completed_levels',(select count(*) from jsonb_array_elements(rows) x cross join lateral jsonb_array_elements(x->'sections') section where (section->'completion'->>'completed')::boolean),
 'average_score',(select coalesce(round(avg(score_percentage),2),0) from public.elearning_assessment_attempts where tenant_id=p_tenant and status='submitted' and(p_course is null or course_id=p_course) and(p_user is null or user_id=p_user) and(p_from is null or submitted_at>=p_from) and(p_to is null or submitted_at<=p_to)),
 'attempts',(select count(*) from public.elearning_assessment_attempts where tenant_id=p_tenant and status='submitted' and(p_course is null or course_id=p_course) and(p_user is null or user_id=p_user) and(p_from is null or submitted_at>=p_from) and(p_to is null or submitted_at<=p_to)),
 'pass_rate',(select coalesce(round(100.0*count(*) filter(where passed)/nullif(count(*),0),2),0) from public.elearning_assessment_attempts where tenant_id=p_tenant and status='submitted' and(p_course is null or course_id=p_course) and(p_user is null or user_id=p_user) and(p_from is null or submitted_at>=p_from) and(p_to is null or submitted_at<=p_to)),
 'certificates',(select count(*) from public.elearning_credentials where tenant_id=p_tenant and(p_course is null or course_id=p_course) and(p_user is null or user_id=p_user) and(p_from is null or issued_at>=p_from) and(p_to is null or issued_at<=p_to))),
 'progress_distribution',(select coalesce(jsonb_agg(to_jsonb(d)),'[]') from(select x->>'progress_status' as status,count(*) as count from jsonb_array_elements(rows) x group by x->>'progress_status') d),
 'level_distribution',(select coalesce(jsonb_agg(to_jsonb(d)),'[]') from(select coalesce((select section->>'name' from jsonb_array_elements(x->'sections') section where section->>'status'='published' and not coalesce((section->'completion'->>'completed')::boolean,false) limit 1),'completed') as level,count(*) as count from jsonb_array_elements(rows) x group by 1) d),
 'applications',coalesce((select jsonb_agg(to_jsonb(a)) from (select kind,status,count(*) as count from public.academy_applications where tenant_id=p_tenant and(p_user is null or user_id=p_user) and(p_from is null or created_at>=p_from) and(p_to is null or created_at<=p_to) group by kind,status) a),'[]'),
 'rewards',coalesce((select jsonb_agg(to_jsonb(a)) from (select r.currency,w.status,c.provider='local_test' as simulated,count(*) as sales,sum(r.amount) as amount from public.academy_referrals r join public.academy_referral_rewards w on(w.tenant_id,w.referral_id)=(r.tenant_id,r.id) join public.ecommerce_checkouts c on(c.tenant_id,c.id)=(w.tenant_id,w.checkout_id) where r.tenant_id=p_tenant and(p_user is null or r.sender_id=p_user) and(p_from is null or w.earned_at>=p_from) and(p_to is null or w.earned_at<=p_to) and(p_course is null or (c.terms->>'access_scope'='all_courses' or coalesce(c.terms->'course_ids','[]') @> jsonb_build_array(p_course::text))) group by r.currency,w.status,c.provider='local_test') a),'[]'));
end $$;
revoke all on function public.academy_owner_report(integer,integer,uuid,integer,uuid,timestamptz,timestamptz,text) from public,anon,authenticated;
grant execute on function public.academy_owner_report(integer,integer,uuid,integer,uuid,timestamptz,timestamptz,text) to service_role;

alter table public.academy_referral_codes add column clicks bigint not null default 0 check(clicks>=0);
create function public.academy_record_referral_click(p_tenant integer,p_code uuid) returns void language plpgsql security definer set search_path='' as $$ begin
 if exists(select 1 from public.elearning_settings where tenant_id=p_tenant and coalesce((settings->>'referral_rewards_enabled')::boolean,false)) then
  update public.academy_referral_codes set clicks=clicks+1 where tenant_id=p_tenant and code=p_code and public.academy_can_refer(p_tenant,user_id);
 end if;
end $$;
revoke all on function public.academy_record_referral_click(integer,uuid) from public,anon,authenticated;
grant execute on function public.academy_record_referral_click(integer,uuid) to service_role;

create function public.academy_owner_finance(p_tenant integer,p_admin integer,p_kind text,p_limit integer default 50,p_offset integer default 0)
returns jsonb language plpgsql stable security definer set search_path='' as $$ declare result jsonb;begin
 perform public.commerce_assert_member(p_tenant,p_admin,true);
 if p_limit not between 1 and 100 or p_offset<0 then raise exception using errcode='22023',message='finance_invalid_page';end if;
 if p_kind='referrals' then
  select coalesce(jsonb_agg(to_jsonb(x)),'[]') into result from (
   select r.id,r.sender_id as user_id,r.referred_id,r.created_at,r.amount,r.currency,coalesce(w.status,'pending') as status,c.code,c.clicks,ch.provider='local_test' as simulated,w.checkout_id
   from public.academy_referrals r left join public.academy_referral_rewards w on(w.tenant_id,w.referral_id)=(r.tenant_id,r.id)
   left join public.academy_referral_codes c on(c.tenant_id,c.user_id)=(r.tenant_id,r.sender_id)
   left join public.ecommerce_checkouts ch on(ch.tenant_id,ch.id)=(w.tenant_id,w.checkout_id)
   where r.tenant_id=p_tenant order by r.created_at desc,r.id limit p_limit offset p_offset
  ) x;
 elsif p_kind='rewards' then
  select coalesce(jsonb_agg(to_jsonb(x)),'[]') into result from (
   select r.id,r.sender_id as user_id,r.amount,r.currency,w.status,w.earned_at as created_at,w.reversed_at,w.checkout_id,c.provider='local_test' as simulated
   from public.academy_referrals r join public.academy_referral_rewards w on(w.tenant_id,w.referral_id)=(r.tenant_id,r.id)
   join public.ecommerce_checkouts c on(c.tenant_id,c.id)=(w.tenant_id,w.checkout_id)
   where r.tenant_id=p_tenant order by w.earned_at desc,r.id limit p_limit offset p_offset
  ) x;
 elsif p_kind='transactions' then
  -- A permanent projection of existing immutable evidence. No competing balance
  -- table or silently editable transaction records.
  select coalesce(jsonb_agg(to_jsonb(x)),'[]') into result from (
   select * from (
    select e.event_id as id,c.user_id,e.state as type,e.state as status,e.amount,e.currency,e.created_at,e.checkout_id as reference,c.provider='local_test' as simulated
    from public.ecommerce_payment_events e join public.ecommerce_checkouts c on(c.tenant_id,c.id)=(e.tenant_id,e.checkout_id) where e.tenant_id=p_tenant
    union all
    select r.id::text||':reward',r.sender_id,'referral_reward','earned',r.amount,r.currency,w.earned_at,w.checkout_id,c.provider='local_test'
    from public.academy_referrals r join public.academy_referral_rewards w on(w.tenant_id,w.referral_id)=(r.tenant_id,r.id) join public.ecommerce_checkouts c on(c.tenant_id,c.id)=(w.tenant_id,w.checkout_id) where r.tenant_id=p_tenant
    union all
    select r.id::text||':reversal',r.sender_id,'reward_reversal','reversed',-r.amount,r.currency,w.reversed_at,w.checkout_id,c.provider='local_test'
    from public.academy_referrals r join public.academy_referral_rewards w on(w.tenant_id,w.referral_id)=(r.tenant_id,r.id) join public.ecommerce_checkouts c on(c.tenant_id,c.id)=(w.tenant_id,w.checkout_id) where r.tenant_id=p_tenant and w.status='reversed'
    union all
    select h.id::text,w.user_id,'withdrawal_'||h.new_status,h.new_status,case when h.new_status='paid' then -w.amount else 0 end,w.currency,h.created_at,w.id,false
    from public.academy_withdrawals w join public.academy_workflow_history h on h.tenant_id=w.tenant_id and h.entity_type='withdrawal' and h.entity_id=w.id where w.tenant_id=p_tenant
   ) ledger order by created_at desc,id limit p_limit offset p_offset
  ) x;
 else raise exception using errcode='22023',message='finance_invalid_kind';end if;
 return jsonb_build_object('items',result);
end $$;
revoke all on function public.academy_owner_finance(integer,integer,text,integer,integer) from public,anon,authenticated;
grant execute on function public.academy_owner_finance(integer,integer,text,integer,integer) to service_role;

-- Currency is fixed once this opt-in programme has attribution history; it
-- cannot relabel historic credits or reservations as another currency.
create function public.academy_settings_currency_guard() returns trigger language plpgsql security definer set search_path='' as $$ begin
 if coalesce((new.settings->>'eduhope_enabled')::boolean,false) and coalesce(new.settings->>'referral_reward_currency','USD') is distinct from coalesce(old.settings->>'referral_reward_currency','USD') and exists(select 1 from public.academy_referrals where tenant_id=new.tenant_id) then raise exception using errcode='22023',message='academy_currency_has_history';end if;
 return new;
end $$;
create trigger academy_settings_currency_guard before update of settings on public.elearning_settings for each row execute function public.academy_settings_currency_guard();
revoke all on function public.academy_settings_currency_guard() from public,anon,authenticated;

create function public.academy_owner_member_profile(p_tenant integer,p_admin integer,p_user integer)
returns jsonb language plpgsql stable security definer set search_path='' as $$begin
 perform public.commerce_assert_member(p_tenant,p_admin,true);
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant and user_id=p_user) then raise exception using errcode='P0002',message='academy_member_not_found';end if;
 return jsonb_build_object('wallet',public.academy_wallet_values(p_tenant,p_user),'role',(select role from public.tenant_memberships where tenant_id=p_tenant and user_id=p_user),
 'user',(select jsonb_build_object('id',id,'name',btrim(concat_ws(' ',first_name,last_name)),'email',email) from public.users where id=p_user),
 'referrals',coalesce((select jsonb_agg(to_jsonb(x)) from (select r.id,r.referred_id,r.amount,r.currency,r.created_at,w.status,w.checkout_id from public.academy_referrals r left join public.academy_referral_rewards w on(w.tenant_id,w.referral_id)=(r.tenant_id,r.id) where r.tenant_id=p_tenant and r.sender_id=p_user order by r.created_at desc limit 50)x),'[]'),
 'withdrawals',coalesce((select jsonb_agg(to_jsonb(x)) from (select id,amount,currency,status,created_at from public.academy_withdrawals where tenant_id=p_tenant and user_id=p_user order by created_at desc limit 50)x),'[]'),
 'transactions',coalesce((select jsonb_agg(to_jsonb(x)) from (select e.event_id,e.state,e.amount,e.currency,e.created_at,c.provider='local_test' as simulated from public.ecommerce_payment_events e join public.ecommerce_checkouts c on(c.tenant_id,c.id)=(e.tenant_id,e.checkout_id) where e.tenant_id=p_tenant and c.user_id=p_user order by e.created_at desc limit 50)x),'[]'),
 'history',coalesce((select jsonb_agg(to_jsonb(x)) from (select h.* from public.academy_workflow_history h where h.tenant_id=p_tenant and ((h.entity_type='application' and exists(select 1 from public.academy_applications a where a.tenant_id=h.tenant_id and a.id=h.entity_id and a.user_id=p_user)) or(h.entity_type='withdrawal' and exists(select 1 from public.academy_withdrawals w where w.tenant_id=h.tenant_id and w.id=h.entity_id and w.user_id=p_user))) order by h.created_at desc limit 100)x),'[]'));
end $$;
revoke all on function public.academy_owner_member_profile(integer,integer,integer) from public,anon,authenticated;
grant execute on function public.academy_owner_member_profile(integer,integer,integer) to service_role;

update public.application_schema_state set schema_version=138,applied_at=now() where contract_key='core';
notify pgrst,'reload schema';
commit;
