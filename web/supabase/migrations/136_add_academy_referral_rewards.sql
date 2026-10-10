begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_136_schema_state_missing'; end if;
 if v_schema_version <> 135 then raise exception 'migration_136_expected_schema_135_got_%',v_schema_version; end if;
end $$;

create table public.academy_referral_codes (
 tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
 user_id integer not null references public.users(id) on delete restrict,
 code uuid not null default gen_random_uuid() unique,
 primary key(tenant_id,user_id), unique(tenant_id,code)
);
create table public.academy_referrals (
 id uuid primary key default gen_random_uuid(), tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
 sender_id integer not null references public.users(id) on delete restrict,
 referred_id integer not null references public.users(id) on delete cascade,
 amount numeric(14,2) not null check(amount>0), currency text not null check(currency ~ '^[A-Z]{3}$'),
 created_at timestamptz not null default now(),
 unique(tenant_id,referred_id),unique(tenant_id,id),check(sender_id<>referred_id)
);
create table public.academy_referral_rewards (
 tenant_id integer not null, referral_id uuid not null, checkout_id uuid not null,
 status text not null default 'earned' check(status in ('earned','reversed')),
 earned_at timestamptz not null default now(), reversed_at timestamptz,
 primary key(tenant_id,referral_id), unique(tenant_id,checkout_id),
 foreign key(tenant_id,referral_id) references public.academy_referrals(tenant_id,id) on delete restrict,
 foreign key(tenant_id,checkout_id) references public.ecommerce_checkouts(tenant_id,id) on delete restrict,
 check((status='earned' and reversed_at is null) or (status='reversed' and reversed_at is not null))
);

-- Called only inside the existing new-account registration compensation scope.
-- Existing users cannot claim an invitation retroactively.
create function public.attach_academy_referral(p_tenant_id integer,p_referred_id integer,p_code uuid)
returns void language plpgsql security definer set search_path='' as $$
declare sender integer; cfg jsonb;
begin
 select settings into cfg from public.elearning_settings where tenant_id=p_tenant_id;
 if not coalesce((cfg->>'referral_rewards_enabled')::boolean,false) then return; end if;
 select c.user_id into sender from public.academy_referral_codes c
 join public.tenant_memberships m on m.tenant_id=c.tenant_id and m.user_id=c.user_id
 join public.users u on u.id=c.user_id
 where c.tenant_id=p_tenant_id and c.code=p_code and m.status='active' and u.account_status='active' and u.email_verified;
 if sender is null then raise exception using errcode='22023',message='academy_referral_invalid'; end if;
 if sender=p_referred_id or not exists(select 1 from public.users u join public.tenant_memberships m on m.user_id=u.id where u.id=p_referred_id and u.tenant_id=p_tenant_id and u.account_status='pending_verification' and not u.email_verified and m.tenant_id=p_tenant_id and m.role='learner' and m.status='active') or exists(select 1 from public.ecommerce_checkouts where tenant_id=p_tenant_id and user_id=p_referred_id) then
  raise exception using errcode='42501',message='academy_referral_new_account_required';
 end if;
 insert into public.academy_referrals(tenant_id,sender_id,referred_id,amount,currency)
 values(p_tenant_id,sender,p_referred_id,(cfg->>'referral_reward_amount')::numeric,cfg->>'referral_reward_currency');
end $$;

create function public.get_academy_referral_account(p_tenant_id integer,p_user_id integer)
returns jsonb language plpgsql security definer set search_path='' as $$
declare cfg jsonb; token uuid; balances jsonb; history jsonb;
begin
 perform public.commerce_assert_member(p_tenant_id,p_user_id);
 select settings into cfg from public.elearning_settings where tenant_id=p_tenant_id;
 if coalesce((cfg->>'referral_rewards_enabled')::boolean,false) then
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

-- Executes inside the verified payment-event transaction. Replays, stale events,
-- renewals and later purchases cannot award a second reward. A refund reverses it.
create function public.credit_academy_referral_purchase()
returns trigger language plpgsql security definer set search_path='' as $$
declare referral uuid;
begin
 if new.state in ('refunded','reversed') then
  update public.academy_referral_rewards set status='reversed',reversed_at=coalesce(reversed_at,now()) where tenant_id=new.tenant_id and checkout_id=new.id and status='earned';
 elsif new.state='paid' and old.state<>'paid' and (new.terms->>'amount')::numeric>0 and exists(select 1 from public.ecommerce_payment_events e where e.tenant_id=new.tenant_id and e.checkout_id=new.id and e.sequence=new.event_sequence and e.state in ('paid','active') and e.transaction_id=new.provider_transaction_id) then
  perform pg_advisory_xact_lock(136,new.user_id);
  select r.id into referral from public.academy_referrals r
  join public.users u on u.id=r.referred_id
  join public.tenant_memberships m on m.user_id=u.id and m.tenant_id=r.tenant_id
  where r.tenant_id=new.tenant_id and r.referred_id=new.user_id and u.account_status='active' and u.email_verified and m.status='active';
  if referral is not null and not exists(select 1 from public.ecommerce_checkouts where tenant_id=new.tenant_id and user_id=new.user_id and id<>new.id and state in ('paid','refunded','reversed')) then
   insert into public.academy_referral_rewards(tenant_id,referral_id,checkout_id) values(new.tenant_id,referral,new.id) on conflict(tenant_id,referral_id) do nothing;
  end if;
 end if;
 return new;
end $$;
create trigger academy_referral_purchase after update of state on public.ecommerce_checkouts for each row execute function public.credit_academy_referral_purchase();

do $$ declare tbl text; begin
 foreach tbl in array array['academy_referral_codes','academy_referrals','academy_referral_rewards'] loop
  execute format('alter table public.%I enable row level security',tbl);
  execute format('revoke all on table public.%I from public,anon,authenticated',tbl);
  execute format('grant all on table public.%I to service_role',tbl);
 end loop;
end $$;
revoke all on function public.attach_academy_referral(integer,integer,uuid),public.get_academy_referral_account(integer,integer),public.credit_academy_referral_purchase() from public,anon,authenticated;
grant execute on function public.attach_academy_referral(integer,integer,uuid),public.get_academy_referral_account(integer,integer) to service_role;
update public.application_schema_state set schema_version=136,applied_at=now() where contract_key = 'core';
commit;
