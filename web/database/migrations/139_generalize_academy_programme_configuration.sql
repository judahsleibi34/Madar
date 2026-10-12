begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_139_schema_state_missing';end if;
 if v_schema_version <> 138 then raise exception 'migration_139_expected_schema_138_got_%',v_schema_version;end if;
end $$;

-- Compatibility translation only: never seed any academy/course or price.
create function public.normalize_academy_programme_settings(cfg jsonb)
returns jsonb language plpgsql immutable set search_path='' as $$ begin
 if not cfg ? 'programmes_enabled' then
  cfg:=cfg||jsonb_build_object('programmes_enabled',coalesce((cfg->>'eduhope_enabled')::boolean,false));
  if coalesce((cfg->>'eduhope_enabled')::boolean,false) then
   cfg:=jsonb_build_object('tuition_sales_threshold',4,'minimum_withdrawal_amount','50.00','withdrawals_enabled',true,'withdrawal_methods',jsonb_build_array('Palestinian Bank Transfer','PayPal'),'support_programme_name','Tuition Support','support_eligibility','verified_referral_sales','referral_eligibility','purchase_or_affiliate')||cfg;
  end if;
 end if;
 return cfg-'eduhope_enabled';
end $$;
create function public.normalize_academy_programme_settings_write() returns trigger
language plpgsql set search_path='' as $$ begin new.settings:=public.normalize_academy_programme_settings(new.settings);return new;end $$;
create trigger academy_programme_settings_normalization before insert or update of settings on public.elearning_settings for each row execute function public.normalize_academy_programme_settings_write();
update public.elearning_settings set settings=public.normalize_academy_programme_settings(settings) where settings ? 'eduhope_enabled';
revoke all on function public.normalize_academy_programme_settings(jsonb),public.normalize_academy_programme_settings_write() from public,anon,authenticated,service_role;

-- Canonical referral facts are mutated only by existing owner-run RPCs/triggers.
revoke all on public.academy_referral_codes,public.academy_referrals,public.academy_referral_rewards from service_role;
grant select on public.academy_referral_codes,public.academy_referrals,public.academy_referral_rewards to service_role;

-- Strengthen indirect ownership without rewriting immutable history rows.
alter table public.academy_applications add constraint academy_application_member_fk foreign key(tenant_id,user_id) references public.tenant_memberships(tenant_id,user_id) on delete restrict;
alter table public.academy_withdrawals add constraint academy_withdrawal_member_fk foreign key(tenant_id,user_id) references public.tenant_memberships(tenant_id,user_id) on delete restrict;
alter table public.academy_workflow_history
 add column application_id uuid generated always as(case when entity_type='application' then entity_id end) stored,
 add column withdrawal_id uuid generated always as(case when entity_type='withdrawal' then entity_id end) stored,
 add constraint academy_history_application_fk foreign key(tenant_id,application_id) references public.academy_applications(tenant_id,id) on delete restrict,
 add constraint academy_history_withdrawal_fk foreign key(tenant_id,withdrawal_id) references public.academy_withdrawals(tenant_id,id) on delete restrict,
 add constraint academy_history_actor_fk foreign key(tenant_id,actor_id) references public.tenant_memberships(tenant_id,user_id) on delete restrict;

create or replace function public.academy_assert_enabled(p_tenant integer,p_user integer,p_admin boolean default false)
returns jsonb language plpgsql security definer set search_path='' as $$ declare cfg jsonb; begin
 perform public.commerce_assert_member(p_tenant,p_user,p_admin);
 select settings into cfg from public.elearning_settings where tenant_id=p_tenant;
 if not coalesce((cfg->>'programmes_enabled')::boolean,false) then raise exception using errcode='42501',message='academy_programmes_disabled'; end if;
 return cfg;
end $$;

create or replace function public.academy_can_refer(p_tenant integer,p_user integer)
returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.elearning_settings where tenant_id=p_tenant and settings->>'referral_eligibility'='registration') or exists(select 1 from public.academy_applications where tenant_id=p_tenant and user_id=p_user and kind='affiliate' and status='approved')
 or exists(select 1 from public.ecommerce_checkouts c join public.ecommerce_entitlements e on(e.tenant_id,e.checkout_id)=(c.tenant_id,c.id)
 where c.tenant_id=p_tenant and c.user_id=p_user and c.state='paid' and c.provider<>'local_test' and (c.terms->>'amount')::numeric>0 and e.status='active'
 and exists(select 1 from public.ecommerce_payment_events v where v.tenant_id=c.tenant_id and v.checkout_id=c.id and v.state in ('paid','active')));
$$;

create or replace function public.academy_wallet_values(p_tenant integer,p_user integer)
returns jsonb language plpgsql stable security definer set search_path='' as $$ declare cfg jsonb; earned numeric; reserved numeric; paid numeric; sales integer; threshold integer; begin
 select settings into cfg from public.elearning_settings where tenant_id=p_tenant;
 select coalesce(sum(r.amount),0) into earned from public.academy_referrals r join public.academy_referral_rewards w on(w.tenant_id,w.referral_id)=(r.tenant_id,r.id)
 join public.ecommerce_checkouts c on(c.tenant_id,c.id)=(w.tenant_id,w.checkout_id)
 where r.tenant_id=p_tenant and r.sender_id=p_user and r.currency=coalesce(cfg->>'referral_reward_currency','USD') and w.status='earned' and c.provider<>'local_test' and c.state='paid';
 select coalesce(sum(amount) filter(where status in ('pending','approved','processing')),0),coalesce(sum(amount) filter(where status='paid'),0) into reserved,paid from public.academy_withdrawals where tenant_id=p_tenant and user_id=p_user and currency=coalesce(cfg->>'referral_reward_currency','USD');
 sales:=public.academy_verified_sales(p_tenant,p_user); threshold:=(cfg->>'tuition_sales_threshold')::integer;
 return jsonb_build_object('currency',coalesce(cfg->>'referral_reward_currency','USD'),'available',greatest(earned-reserved-paid,0),'debt',greatest(reserved+paid-earned,0),'pending',reserved,'total_earned',earned,'total_withdrawn',paid,'verified_sales',sales,'threshold',threshold,'remaining_sales',greatest(threshold-sales,0),'tuition_eligible',coalesce((cfg->>'tuition_support_enabled')::boolean,false) and case when cfg->>'support_eligibility'='active_learner' then exists(select 1 from public.elearning_learners l join public.elearning_enrollments e on(e.tenant_id,e.learner_id)=(l.tenant_id,l.id) where l.tenant_id=p_tenant and l.user_id=p_user and l.status='active' and e.status='active' and public.elearning_enrollment_has_access(p_tenant,e.id)) else coalesce(sales>=threshold,false) end,'exchange_eligible',coalesce((cfg->>'exchange_programme_enabled')::boolean,false) and exists(select 1 from public.elearning_learners l join public.elearning_enrollments e on(e.tenant_id,e.learner_id)=(l.tenant_id,l.id) where l.tenant_id=p_tenant and l.user_id=p_user and l.status='active' and e.status='active' and public.elearning_enrollment_has_access(p_tenant,e.id)),'can_refer',public.academy_can_refer(p_tenant,p_user));
end $$;

create or replace function public.academy_request_withdrawal(p_tenant integer,p_user integer,p_amount numeric,p_method text,p_information text,p_confirm boolean,p_key uuid)
returns uuid language plpgsql security definer set search_path='' as $$ declare cfg jsonb; w jsonb; result uuid; begin
 cfg:=public.academy_assert_enabled(p_tenant,p_user); perform pg_advisory_xact_lock(p_tenant,p_user);
 select id into result from public.academy_withdrawals where tenant_id=p_tenant and user_id=p_user and idempotency_key=p_key;
 if result is not null then
  if p_confirm is distinct from true or not exists(select 1 from public.academy_withdrawals where id=result and amount=p_amount and payment_method=p_method and payment_information=p_information) then raise exception using errcode='40001',message='withdrawal_idempotency_conflict';end if;
  return result;
 end if;
 if not coalesce((cfg->>'withdrawals_enabled')::boolean,false) or cfg->>'minimum_withdrawal_amount' is null then raise exception using errcode='42501',message='academy_withdrawals_disabled';end if;
 w:=public.academy_wallet(p_tenant,p_user);
 if p_confirm is distinct from true or p_key is null or p_amount is null or p_amount<>round(p_amount,2) or p_amount<(cfg->>'minimum_withdrawal_amount')::numeric or p_amount>(w->>'available')::numeric or (w->>'debt')::numeric>0 or not (coalesce(cfg->'withdrawal_methods','[]'::jsonb) ? p_method) or length(btrim(coalesce(p_information,''))) not between 1 and 4000 then raise exception using errcode='22023',message='withdrawal_invalid_or_insufficient';end if;
 insert into public.academy_withdrawals(tenant_id,user_id,amount,currency,payment_method,payment_information,idempotency_key) values(p_tenant,p_user,p_amount,w->>'currency',p_method,p_information,p_key) returning id into result;
 insert into public.academy_workflow_history(tenant_id,entity_type,entity_id,actor_id,new_status) values(p_tenant,'withdrawal',result,p_user,'pending');
 perform public.enqueue_learning_notification(p_tenant,p_user,'learning_withdrawal_submitted','academy_withdrawal',result::text,'Withdrawal submitted','/my-learning/programmes');
 perform public.learning_notify_owners(p_tenant,'learning_withdrawal_request','academy_withdrawal',result::text,'New withdrawal request','/e-learning/programmes');
 return result;
end $$;

create or replace function public.get_academy_referral_account_legacy(p_tenant_id integer,p_user_id integer)
returns jsonb language plpgsql security definer set search_path='' as $$
declare cfg jsonb; token uuid; balances jsonb; history jsonb;
begin
 perform public.commerce_assert_member(p_tenant_id,p_user_id);
 select settings into cfg from public.elearning_settings where tenant_id=p_tenant_id;
 if coalesce((cfg->>'referral_rewards_enabled')::boolean,false) and (not coalesce((cfg->>'programmes_enabled')::boolean,false) or public.academy_can_refer(p_tenant_id,p_user_id)) then
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

create or replace function public.get_academy_referral_account(p_tenant_id integer,p_user_id integer)
returns jsonb language plpgsql security definer set search_path='' as $$ declare cfg jsonb; result jsonb; begin
 perform public.commerce_assert_member(p_tenant_id,p_user_id);
 select settings into cfg from public.elearning_settings where tenant_id=p_tenant_id;
 result:=public.get_academy_referral_account_legacy(p_tenant_id,p_user_id);
 if coalesce((cfg->>'programmes_enabled')::boolean,false) then result:=result||jsonb_build_object('wallet',public.academy_wallet(p_tenant_id,p_user_id));end if;
 return result;
end $$;

create or replace function public.academy_referral_eligibility_guard() returns trigger language plpgsql security definer set search_path='' as $$ begin
 if exists(select 1 from public.elearning_settings where tenant_id=new.tenant_id and coalesce((settings->>'programmes_enabled')::boolean,false)) and not public.academy_can_refer(new.tenant_id,new.sender_id) then raise exception using errcode='42501',message='referral_purchase_or_affiliate_required';end if;
 return new;
end $$;

create or replace function public.academy_tuition_eligibility_notice() returns trigger language plpgsql security definer set search_path='' as $$ declare u integer; cfg jsonb; threshold integer; begin
 select settings into cfg from public.elearning_settings where tenant_id=new.tenant_id;
 if not coalesce((cfg->>'programmes_enabled')::boolean,false) or not coalesce((cfg->>'tuition_support_enabled')::boolean,false) then return new;end if;
 select sender_id into u from public.academy_referrals where tenant_id=new.tenant_id and id=new.referral_id;
 threshold:=(cfg->>'tuition_sales_threshold')::integer;
 if new.status='earned' and public.academy_verified_sales(new.tenant_id,u)=threshold then
  perform public.enqueue_learning_notification(new.tenant_id,u,'learning_tuition_eligible','academy_reward',new.referral_id::text,'You are eligible to apply for '||coalesce(cfg->>'support_programme_name','Support Programme'),'/my-learning/programmes');
 elsif new.status='reversed' then
  perform public.enqueue_learning_notification(new.tenant_id,u,'learning_tuition_eligibility_changed','academy_reward',new.referral_id::text,'Your verified referral sales count changed','/my-learning/programmes');
 end if;return new;
end $$;

create or replace function public.academy_settings_currency_guard() returns trigger language plpgsql security definer set search_path='' as $$ begin
 if coalesce((new.settings->>'programmes_enabled')::boolean,false) and coalesce(new.settings->>'referral_reward_currency','USD') is distinct from coalesce(old.settings->>'referral_reward_currency','USD') and exists(select 1 from public.academy_referrals where tenant_id=new.tenant_id) then raise exception using errcode='22023',message='academy_currency_has_history';end if;
 return new;
end $$;

create or replace function public.configure_elearning_cefr(p_tenant integer,p_admin integer,p_course uuid,p_section uuid,p_level text,p_template uuid,p_enabled boolean)
returns void language plpgsql security definer set search_path='' as $$ begin
 perform public.commerce_assert_member(p_tenant,p_admin,true);
 perform pg_advisory_xact_lock(125,p_tenant);
 if p_enabled and not exists(select 1 from public.elearning_assessment_placements p join public.elearning_assessments a on(a.tenant_id,a.id)=(p.tenant_id,p.assessment_id) where p.tenant_id=p_tenant and p.course_id=p_course and p.section_id=p_section and p.placement_type='section' and p.required_for_completion and p.archived_at is null and a.status='published' and a.passing_score=70 and (a.max_attempts is null or a.max_attempts>1)) then raise exception using errcode='22023',message='cefr_final_exam_required';end if;
 insert into public.elearning_section_certificates(tenant_id,course_id,section_id,cefr_level,template_id,enabled) values(p_tenant,p_course,p_section,p_level,p_template,p_enabled)
 on conflict(tenant_id,course_id,section_id) do update set cefr_level=excluded.cefr_level,template_id=excluded.template_id,enabled=excluded.enabled;
 insert into public.audit_logs(tenant_id,actor_user_id,action,target_type,target_id,metadata) values(p_tenant,p_admin,'elearning.cefr.configured','elearning_section',p_section::text,jsonb_build_object('course_id',p_course,'cefr_level',p_level,'enabled',p_enabled));
end $$;

update public.application_schema_state set schema_version = 139,applied_at=now() where contract_key = 'core';
notify pgrst,'reload schema';
commit;
