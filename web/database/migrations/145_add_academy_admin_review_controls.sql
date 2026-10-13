begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_145_schema_state_missing';end if;
 if v_schema_version <> 144 then raise exception 'migration_145_expected_schema_144_got_%',v_schema_version;end if;
end $$;

-- Academy admin review controls. Every behaviour change is opt-in per tenant
-- (elearning_settings.referral_reward_review_required) or an explicit owner
-- action; academies that do neither keep schema-144 behaviour exactly.

-- 1. Referral reward review. With review required, a confirmed referred
-- purchase creates a pending reward that counts towards nothing (wallet,
-- verified sales, Tuition) until an owner approves it; owners may reject it
-- with a reason. Refunds reverse pending and earned rewards alike.
do $$ declare c record; begin
 for c in select conname from pg_constraint where conrelid='public.academy_referral_rewards'::regclass and contype='c' loop
  execute format('alter table public.academy_referral_rewards drop constraint %I',c.conname);
 end loop;
end $$;
alter table public.academy_referral_rewards
 add column reviewed_by integer,
 add column reviewed_at timestamptz,
 add column review_note text not null default '' check(length(review_note)<=1000),
 add constraint academy_reward_status145 check(status in ('pending','earned','rejected','reversed')),
 add constraint academy_reward_reversal145 check((status='reversed')=(reversed_at is not null)),
 add constraint academy_reward_review145 check((reviewed_by is null)=(reviewed_at is null)),
 add constraint academy_reward_reviewer145 foreign key(tenant_id,reviewed_by) references public.tenant_memberships(tenant_id,user_id) on delete restrict;

create or replace function public.credit_academy_referral_purchase()
returns trigger language plpgsql security definer set search_path='' as $$
declare referral uuid; review boolean;
begin
 if new.state in ('refunded','reversed') then
  update public.academy_referral_rewards set status='reversed',reversed_at=coalesce(reversed_at,now()) where tenant_id=new.tenant_id and checkout_id=new.id and status in ('earned','pending');
 elsif new.state='paid' and old.state<>'paid' and (new.terms->>'amount')::numeric>0 and exists(select 1 from public.ecommerce_payment_events e where e.tenant_id=new.tenant_id and e.checkout_id=new.id and e.sequence=new.event_sequence and e.state in ('paid','active') and e.transaction_id=new.provider_transaction_id) then
  perform pg_advisory_xact_lock(136,new.user_id);
  select r.id into referral from public.academy_referrals r
  join public.users u on u.id=r.referred_id
  join public.tenant_memberships m on m.user_id=u.id and m.tenant_id=r.tenant_id
  where r.tenant_id=new.tenant_id and r.referred_id=new.user_id and u.account_status='active' and u.email_verified and m.status='active';
  if referral is not null and not exists(select 1 from public.ecommerce_checkouts where tenant_id=new.tenant_id and user_id=new.user_id and id<>new.id and state in ('paid','refunded','reversed')) then
   select coalesce((settings->>'referral_reward_review_required')::boolean,false) into review from public.elearning_settings where tenant_id=new.tenant_id;
   insert into public.academy_referral_rewards(tenant_id,referral_id,checkout_id,status) values(new.tenant_id,referral,new.id,case when coalesce(review,false) then 'pending' else 'earned' end) on conflict(tenant_id,referral_id) do nothing;
  end if;
 end if;
 return new;
end $$;

create function public.academy_review_reward(p_tenant integer,p_admin integer,p_referral uuid,p_decision text,p_note text)
returns jsonb language plpgsql security definer set search_path='' as $$
declare current text;
begin
 perform public.academy_assert_enabled(p_tenant,p_admin,true);
 if p_decision is null or p_decision not in ('earned','rejected') or length(coalesce(p_note,''))>1000 or (p_decision='rejected' and length(btrim(coalesce(p_note,''))) not between 1 and 1000) then
  raise exception using errcode='22023',message='academy_reward_review_invalid';
 end if;
 select status into current from public.academy_referral_rewards where tenant_id=p_tenant and referral_id=p_referral for update;
 if current is null then raise exception using errcode='P0002',message='academy_reward_not_found';end if;
 if current<>'pending' then raise exception using errcode='40001',message='academy_reward_not_pending';end if;
 update public.academy_referral_rewards set status=p_decision,reviewed_by=p_admin,reviewed_at=now(),review_note=btrim(coalesce(p_note,'')),
  earned_at=case when p_decision='earned' then now() else earned_at end
 where tenant_id=p_tenant and referral_id=p_referral;
 insert into public.audit_logs(tenant_id,actor_user_id,action,target_type,target_id,metadata)
 values(p_tenant,p_admin,'academy.reward.'||case when p_decision='earned' then 'approved' else 'rejected' end,'academy_referral',p_referral::text,jsonb_build_object('previous_status',current,'note',btrim(coalesce(p_note,''))));
 return jsonb_build_object('referral_id',p_referral,'status',p_decision);
end $$;

-- 2. Tuition Support eligibility override, always with a reason in the audit log.
create table public.academy_tuition_overrides(
 tenant_id integer not null,user_id integer not null,eligible boolean not null,
 reason text not null check(length(btrim(reason)) between 1 and 1000),
 actor_id integer not null,updated_at timestamptz not null default now(),
 primary key(tenant_id,user_id),
 foreign key(tenant_id,user_id) references public.tenant_memberships(tenant_id,user_id) on delete restrict,
 foreign key(tenant_id,actor_id) references public.tenant_memberships(tenant_id,user_id) on delete restrict
);

create function public.academy_set_tuition_override(p_tenant integer,p_admin integer,p_user integer,p_eligible boolean,p_reason text)
returns jsonb language plpgsql security definer set search_path='' as $$
declare previous boolean;
begin
 perform public.academy_assert_enabled(p_tenant,p_admin,true);
 if length(btrim(coalesce(p_reason,''))) not between 1 and 1000 then raise exception using errcode='22023',message='academy_override_reason_required';end if;
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant and user_id=p_user) then raise exception using errcode='P0002',message='academy_member_not_found';end if;
 perform pg_advisory_xact_lock(p_tenant,p_user);
 select eligible into previous from public.academy_tuition_overrides where tenant_id=p_tenant and user_id=p_user;
 if p_eligible is null then
  delete from public.academy_tuition_overrides where tenant_id=p_tenant and user_id=p_user;
 else
  insert into public.academy_tuition_overrides(tenant_id,user_id,eligible,reason,actor_id) values(p_tenant,p_user,p_eligible,btrim(p_reason),p_admin)
  on conflict(tenant_id,user_id) do update set eligible=excluded.eligible,reason=excluded.reason,actor_id=excluded.actor_id,updated_at=now();
 end if;
 insert into public.audit_logs(tenant_id,actor_user_id,action,target_type,target_id,metadata)
 values(p_tenant,p_admin,case when p_eligible is null then 'academy.tuition_override.cleared' else 'academy.tuition_override.set' end,'academy_member',p_user::text,
  jsonb_build_object('eligible',p_eligible,'previous',previous,'reason',btrim(p_reason)));
 return jsonb_build_object('user_id',p_user,'override',p_eligible);
end $$;

create or replace function public.academy_wallet_values(p_tenant integer,p_user integer)
returns jsonb language plpgsql stable security definer set search_path='' as $$ declare cfg jsonb; earned numeric; reserved numeric; paid numeric; sales integer; threshold integer; override boolean; computed boolean; begin
 select settings into cfg from public.elearning_settings where tenant_id=p_tenant;
 select coalesce(sum(r.amount),0) into earned from public.academy_referrals r join public.academy_referral_rewards w on(w.tenant_id,w.referral_id)=(r.tenant_id,r.id)
 join public.ecommerce_checkouts c on(c.tenant_id,c.id)=(w.tenant_id,w.checkout_id)
 where r.tenant_id=p_tenant and r.sender_id=p_user and r.currency=coalesce(cfg->>'referral_reward_currency','USD') and w.status='earned' and c.provider<>'local_test' and c.state='paid';
 select coalesce(sum(amount) filter(where status in ('pending','approved','processing')),0),coalesce(sum(amount) filter(where status='paid'),0) into reserved,paid from public.academy_withdrawals where tenant_id=p_tenant and user_id=p_user and currency=coalesce(cfg->>'referral_reward_currency','USD');
 sales:=public.academy_verified_sales(p_tenant,p_user); threshold:=(cfg->>'tuition_sales_threshold')::integer;
 select eligible into override from public.academy_tuition_overrides where tenant_id=p_tenant and user_id=p_user;
 computed:=case when cfg->>'support_eligibility'='active_learner' then exists(select 1 from public.elearning_learners l join public.elearning_enrollments e on(e.tenant_id,e.learner_id)=(l.tenant_id,l.id) where l.tenant_id=p_tenant and l.user_id=p_user and l.status='active' and e.status='active' and public.elearning_enrollment_has_access(p_tenant,e.id)) else coalesce(sales>=threshold,false) end;
 return jsonb_build_object('currency',coalesce(cfg->>'referral_reward_currency','USD'),'available',greatest(earned-reserved-paid,0),'debt',greatest(reserved+paid-earned,0),'pending',reserved,'total_earned',earned,'total_withdrawn',paid,'verified_sales',sales,'threshold',threshold,'remaining_sales',greatest(threshold-sales,0),'tuition_eligible',coalesce((cfg->>'tuition_support_enabled')::boolean,false) and coalesce(override,computed),'tuition_override',override,'exchange_eligible',coalesce((cfg->>'exchange_programme_enabled')::boolean,false) and exists(select 1 from public.elearning_learners l join public.elearning_enrollments e on(e.tenant_id,e.learner_id)=(l.tenant_id,l.id) where l.tenant_id=p_tenant and l.user_id=p_user and l.status='active' and e.status='active' and public.elearning_enrollment_has_access(p_tenant,e.id)),'can_refer',public.academy_can_refer(p_tenant,p_user));
end $$;

-- 3. Manual institution verification ("Verified PAU Student"); the email-domain
-- match alone only selects the institution label.
create table public.academy_institution_verifications(
 tenant_id integer not null,user_id integer not null,verified_by integer not null,verified_at timestamptz not null default now(),
 note text not null default '' check(length(note)<=1000),
 primary key(tenant_id,user_id),
 foreign key(tenant_id,user_id) references public.tenant_memberships(tenant_id,user_id) on delete restrict,
 foreign key(tenant_id,verified_by) references public.tenant_memberships(tenant_id,user_id) on delete restrict
);

create function public.academy_set_institution_verification(p_tenant integer,p_admin integer,p_user integer,p_verified boolean,p_note text)
returns jsonb language plpgsql security definer set search_path='' as $$
begin
 perform public.commerce_assert_member(p_tenant,p_admin,true);
 if p_verified is null or length(coalesce(p_note,''))>1000 then raise exception using errcode='22023',message='academy_verification_invalid';end if;
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant and user_id=p_user) then raise exception using errcode='P0002',message='academy_member_not_found';end if;
 if p_verified then
  insert into public.academy_institution_verifications(tenant_id,user_id,verified_by,note) values(p_tenant,p_user,p_admin,btrim(coalesce(p_note,'')))
  on conflict(tenant_id,user_id) do update set verified_by=excluded.verified_by,verified_at=now(),note=excluded.note;
 else
  delete from public.academy_institution_verifications where tenant_id=p_tenant and user_id=p_user;
 end if;
 insert into public.audit_logs(tenant_id,actor_user_id,action,target_type,target_id,metadata)
 values(p_tenant,p_admin,case when p_verified then 'academy.institution.verified' else 'academy.institution.unverified' end,'academy_member',p_user::text,jsonb_build_object('note',btrim(coalesce(p_note,''))));
 return jsonb_build_object('user_id',p_user,'verified',p_verified);
end $$;

create or replace function public.academy_classified_students(p_tenant integer,p_admin integer,p_classification text default null,p_limit integer default 50,p_offset integer default 0) returns jsonb
language plpgsql stable security definer set search_path='' as $$declare cfg jsonb;result jsonb;begin
 perform public.commerce_assert_member(p_tenant,p_admin,true);
 select settings into cfg from public.elearning_settings where tenant_id=p_tenant;
 if p_classification is not null and p_classification not in ('institution','regular') then raise exception using errcode='22023',message='invalid_classification';end if;
 select coalesce(jsonb_agg(value),'[]') into result from (
  select to_jsonb(l)||jsonb_build_object('email_verified',coalesce(u.email_verified and u.account_status='active' and m.status='active',false),'institution_verified',matched,
  'classification',case when matched then coalesce(cfg->>'institution_student_label','Institution Student') else coalesce(cfg->>'regular_student_label','Regular Student') end,
  'institution_manually_verified',exists(select 1 from public.academy_institution_verifications v where v.tenant_id=l.tenant_id and v.user_id=l.user_id),
  'tuition_override',(select o.eligible from public.academy_tuition_overrides o where o.tenant_id=l.tenant_id and o.user_id=l.user_id)) as value
  from public.elearning_learners l left join public.users u on u.id=l.user_id
  left join public.tenant_memberships m on(m.tenant_id,m.user_id)=(l.tenant_id,l.user_id)
  cross join lateral(select coalesce(u.email_verified and u.account_status='active' and m.status='active' and coalesce((cfg->>'institution_enabled')::boolean,false) and coalesce(cfg->'institution_email_domains','[]') ? lower(split_part(u.email,'@',2)),false) as matched)x
  where l.tenant_id=p_tenant and (p_classification is null or matched=(p_classification='institution')) order by l.name,l.id limit least(greatest(p_limit,1),100)+1 offset greatest(p_offset,0)
 )s;
 return jsonb_build_object('learners',result,'has_more',jsonb_array_length(result)>least(greatest(p_limit,1),100));
end $$;

-- 4. Read-only audit log for the academy's own owners/admins.
create function public.academy_audit_log(p_tenant integer,p_admin integer,p_limit integer default 50,p_offset integer default 0)
returns jsonb language plpgsql stable security definer set search_path='' as $$declare result jsonb;begin
 perform public.commerce_assert_member(p_tenant,p_admin,true);
 select coalesce(jsonb_agg(to_jsonb(x)),'[]') into result from (
  select a.id,a.created_at,a.action,a.target_type,a.target_id,a.metadata,a.actor_user_id,
   nullif(btrim(coalesce(u.first_name,'')||' '||coalesce(u.last_name,'')),'') as actor_name,u.email as actor_email
  from public.audit_logs a left join public.users u on u.id=a.actor_user_id
  where a.tenant_id=p_tenant and (a.action like 'academy.%' or a.action like 'elearning.%')
  order by a.created_at desc,a.id limit least(greatest(p_limit,1),100)+1 offset greatest(p_offset,0)
 )x;
 return jsonb_build_object('entries',result,'has_more',jsonb_array_length(result)>least(greatest(p_limit,1),100));
end $$;

-- Learner history distinguishes a sign-up (no reward) from the reward's own state.
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
  select r.id,r.amount,r.currency,r.created_at,coalesce(w.status,'pending') as status,w.status as reward_status,w.earned_at,w.reversed_at,coalesce(ch.provider='local_test',false) as simulated
  from public.academy_referrals r left join public.academy_referral_rewards w on w.tenant_id=r.tenant_id and w.referral_id=r.id
  left join public.ecommerce_checkouts ch on ch.tenant_id=w.tenant_id and ch.id=w.checkout_id
  where r.tenant_id=p_tenant_id and r.sender_id=p_user_id order by r.created_at desc,r.id limit 50
 ) h;
 return jsonb_build_object('available',true,'enabled',coalesce((cfg->>'referral_rewards_enabled')::boolean,false),'code',token,'reward_amount',cfg->>'referral_reward_amount','currency',cfg->>'referral_reward_currency','balances',balances,'history',history,'referred_count',(select count(*) from public.academy_referrals where tenant_id=p_tenant_id and sender_id=p_user_id),'earned_count',(select count(*) from public.academy_referrals r join public.academy_referral_rewards w on w.tenant_id=r.tenant_id and w.referral_id=r.id where r.tenant_id=p_tenant_id and r.sender_id=p_user_id and w.status='earned'));
end $$;

do $$ declare tbl text; begin
 foreach tbl in array array['academy_tuition_overrides','academy_institution_verifications'] loop
  execute format('alter table public.%I enable row level security',tbl);
  execute format('revoke all on table public.%I from public,anon,authenticated,service_role',tbl);
  execute format('grant select on table public.%I to service_role',tbl);
 end loop;
end $$;
revoke all on function public.academy_review_reward(integer,integer,uuid,text,text),public.academy_set_tuition_override(integer,integer,integer,boolean,text),
 public.academy_set_institution_verification(integer,integer,integer,boolean,text),public.academy_audit_log(integer,integer,integer,integer) from public,anon,authenticated;
grant execute on function public.academy_review_reward(integer,integer,uuid,text,text),public.academy_set_tuition_override(integer,integer,integer,boolean,text),
 public.academy_set_institution_verification(integer,integer,integer,boolean,text),public.academy_audit_log(integer,integer,integer,integer) to service_role;

update public.application_schema_state set schema_version = 145,applied_at=now() where contract_key = 'core';
notify pgrst,'reload schema';
commit;
