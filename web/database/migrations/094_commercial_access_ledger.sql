BEGIN;

-- Additive bridge: no plan/payment is inferred from historical usage.
create extension if not exists btree_gist with schema extensions;

create table public.tenant_commercial_state (
  tenant_id integer primary key references public.tenants(tenant_id) on delete cascade,
  revision bigint not null default 1 check (revision > 0),
  review_state text not null default 'review_required' check (review_state in ('review_required','reviewed')),
  reviewed_by integer references public.users(id) on delete restrict,
  reviewed_at timestamptz,
  updated_at timestamptz not null default now(),
  check ((review_state='review_required' and reviewed_by is null and reviewed_at is null)
      or (review_state='reviewed' and reviewed_by is not null and reviewed_at is not null))
);
insert into public.tenant_commercial_state (tenant_id) select tenant_id from public.tenants;

create table public.commercial_manual_payments (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete restrict,
  plan_id text not null check (plan_id in ('forms','website','business','business_plus')),
  method text not null check (method in ('cash','bank_transfer','other_manual')),
  expected_minor bigint not null check (expected_minor > 0 and expected_minor <= 1000000000000),
  actual_minor bigint not null check (actual_minor > 0 and actual_minor <= 1000000000000),
  currency text not null check (currency='USD'),
  catalog_version text not null,
  paid_at timestamptz not null check (isfinite(paid_at)),
  valid_from timestamptz not null check (isfinite(valid_from)),
  valid_until timestamptz not null check (isfinite(valid_until) and valid_until > valid_from),
  billing_months integer not null check (billing_months between 1 and 120),
  receipt_reference text not null check (length(receipt_reference) between 1 and 200),
  reason text not null check (length(reason) between 3 and 1000),
  override_reason text check (override_reason is null or length(override_reason) between 3 and 1000),
  corrects_payment_id uuid,
  created_by integer not null references public.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  unique (tenant_id,id),
  unique (corrects_payment_id),
  foreign key (tenant_id,corrects_payment_id) references public.commercial_manual_payments(tenant_id,id) on delete restrict,
  check (expected_minor=actual_minor or override_reason is not null)
);

create table public.commercial_access_periods (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete restrict,
  plan_id text not null check (plan_id in ('forms','website','business','business_plus')),
  valid_from timestamptz not null check (isfinite(valid_from)),
  valid_until timestamptz not null check (isfinite(valid_until) and valid_until > valid_from),
  source_type text not null check (source_type in ('cash','bank_transfer','other_manual','complimentary','legacy_migration','cybersource')),
  manual_payment_id uuid,
  source_reference text,
  reason text not null check (length(reason) between 3 and 1000),
  created_by integer not null references public.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  revoked_at timestamptz check (revoked_at is null or isfinite(revoked_at)),
  revoked_by integer references public.users(id) on delete restrict,
  effective_during tstzrange generated always as (
    case when revoked_at <= valid_from then 'empty'::tstzrange
    else tstzrange(valid_from,least(valid_until,revoked_at),'[)') end
  ) stored,
  unique (tenant_id,id),
  foreign key (tenant_id,manual_payment_id) references public.commercial_manual_payments(tenant_id,id) on delete restrict,
  check ((revoked_at is null) = (revoked_by is null)),
  check ((source_type in ('cash','bank_transfer','other_manual')) = (manual_payment_id is not null)),
  constraint commercial_access_periods_no_overlap exclude using gist
    (tenant_id extensions.gist_int4_ops with =, effective_during with &&)
);

create table public.commercial_access_events (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer not null references public.tenants(tenant_id) on delete restrict,
  operation text not null,
  idempotency_key text not null check (length(idempotency_key) between 16 and 128),
  request_hash text not null check (request_hash ~ '^[a-f0-9]{64}$'),
  actor_user_id integer not null references public.users(id) on delete restrict,
  aal text not null check (aal='aal2'),
  request_id text not null check (length(request_id) between 1 and 128),
  revision bigint not null,
  result jsonb not null,
  created_at timestamptz not null default now(),
  unique (tenant_id,operation,idempotency_key)
);
create index commercial_manual_payments_history_idx on public.commercial_manual_payments(tenant_id,created_at desc);
create index commercial_access_events_history_idx on public.commercial_access_events(tenant_id,created_at desc);

create function public.bump_commercial_revision() returns trigger
language plpgsql security definer set search_path='' as $$
declare tid integer;
begin
  tid := case when TG_OP='DELETE' then OLD.tenant_id else NEW.tenant_id end;
  if not exists(select 1 from public.tenants where tenant_id=tid) then return OLD; end if;
  insert into public.tenant_commercial_state(tenant_id) values(tid)
  on conflict(tenant_id) do update set revision=public.tenant_commercial_state.revision+1,updated_at=now();
  return case when TG_OP='DELETE' then OLD else NEW end;
end;
$$;
create trigger commercial_new_tenant after insert on public.tenants for each row execute function public.bump_commercial_revision();
create trigger commercial_period_revision after insert or update on public.commercial_access_periods for each row execute function public.bump_commercial_revision();
create trigger commercial_payment_revision after insert on public.commercial_manual_payments for each row execute function public.bump_commercial_revision();
create trigger commercial_subscription_revision after insert or update or delete on public.tenant_subscriptions for each row execute function public.bump_commercial_revision();
create trigger commercial_addon_revision after insert or update or delete on public.tenant_addons for each row execute function public.bump_commercial_revision();
create trigger commercial_feature_revision after insert or update or delete on public.features for each row execute function public.bump_commercial_revision();
create trigger commercial_website_revision after insert or update or delete on public.website_settings for each row execute function public.bump_commercial_revision();
create trigger commercial_decision_revision after insert or update or delete on public.tenant_entitlement_decisions for each row execute function public.bump_commercial_revision();

-- Retain the financial foreign keys. Until an explicit financial retention /
-- anonymization policy is approved, refuse destructive deletion BEFORE the
-- workflow freezes accounts or removes files/provider objects. Do not invent
-- a retention duration or silently erase the ledger to satisfy deletion.
create function public.guard_commercial_financial_deletion() returns trigger
language plpgsql security definer set search_path='' as $$
begin
  if TG_TABLE_NAME='tenants' then
    if NEW.lifecycle_state='deletion_pending' and OLD.lifecycle_state is distinct from NEW.lifecycle_state and (
      exists(select 1 from public.commercial_manual_payments p where p.tenant_id=NEW.tenant_id)
      or exists(select 1 from public.commercial_access_periods p where p.tenant_id=NEW.tenant_id)
      or exists(select 1 from public.commercial_access_events e where e.tenant_id=NEW.tenant_id)
    ) then raise exception using errcode='P0001',message='commercial_financial_retention_review_required'; end if;
  else
    if NEW.account_status='deletion_pending' and OLD.account_status is distinct from NEW.account_status and (
      exists(select 1 from public.commercial_manual_payments p where p.created_by=NEW.id)
      or exists(select 1 from public.commercial_access_periods p where p.created_by=NEW.id or p.revoked_by=NEW.id)
      or exists(select 1 from public.commercial_access_events e where e.actor_user_id=NEW.id)
      or exists(select 1 from public.tenant_commercial_state s where s.reviewed_by=NEW.id)
    ) then raise exception using errcode='P0001',message='commercial_financial_retention_review_required'; end if;
  end if;
  return NEW;
end;
$$;
create trigger commercial_tenant_deletion_guard before update of lifecycle_state on public.tenants for each row execute function public.guard_commercial_financial_deletion();
create trigger commercial_actor_deletion_guard before update of account_status on public.users for each row execute function public.guard_commercial_financial_deletion();
revoke all on function public.guard_commercial_financial_deletion() from public,anon,authenticated,service_role;

-- One statement snapshot; callers cannot obtain a revision and period from
-- different commits. Time expiry changes effective identity without a TTL job.
create function public.resolve_commercial_access(p_tenant_id integer) returns jsonb
language sql stable security definer set search_path='' as $$
select jsonb_build_object(
  'tenant_id', s.tenant_id, 'revision',s.revision,'review_state',s.review_state,
  'reviewed_at',s.reviewed_at,'effective_at',statement_timestamp(),
  'period',(select to_jsonb(p)-'reason'-'source_reference'-'effective_during' from public.commercial_access_periods p
            where p.tenant_id=s.tenant_id and p.effective_during @> statement_timestamp()),
  'has_history',exists(select 1 from public.commercial_access_periods p where p.tenant_id=s.tenant_id),
  'grandfathered_subdomain',exists(select 1 from public.website_settings w where w.tenant_id=s.tenant_id and w.branded_subdomain_commercial_status='grandfathered'),
  'next_transition_at',(select min(t) from (
    select unnest(array[lower(p.effective_during),upper(p.effective_during)]) t from public.commercial_access_periods p where p.tenant_id=s.tenant_id
    union all select unnest(array[a.period_start,a.period_end]) from public.tenant_addons a where a.tenant_id=s.tenant_id and a.state='active'
  ) transitions where t > statement_timestamp()),
  'addons',coalesce((select jsonb_agg(to_jsonb(a)) from public.tenant_addons a where a.tenant_id=s.tenant_id
            and a.state='active' and (a.period_start is null or a.period_start <= statement_timestamp())
            and (a.period_end is null or a.period_end > statement_timestamp())), '[]'::jsonb)
) from public.tenant_commercial_state s where s.tenant_id=p_tenant_id;
$$;

-- HTTP authorization supplies the provider-verified actor/AAL. The privileged
-- function independently checks actor role, tenant lifecycle, financial input,
-- cross-tenant references, overlap and durable idempotency in one transaction.
create function public.apply_commercial_access_command(
  p_tenant_id integer, p_actor_user_id integer, p_aal text,
  p_operation text, p_idempotency_key text, p_request_id text, p_payload jsonb
) returns jsonb language plpgsql security definer set search_path='' as $$
declare
  r jsonb := p_payload->'request'; q jsonb := p_payload->'quote';
  fingerprint text; prior public.commercial_access_events;
  payment public.commercial_manual_payments; corrected public.commercial_manual_payments;
  period public.commercial_access_periods; before_state jsonb; result jsonb;
  v_revision bigint; v_now timestamptz := statement_timestamp();
begin
  perform 1 from public.users u where u.id=p_actor_user_id and lower(btrim(u.user_type))='admin' and u.account_status='active' for share;
  if p_aal is distinct from 'aal2' or not found then
    raise exception using errcode='42501',message='platform_admin_aal2_required';
  end if;
  perform 1 from public.tenants t where t.tenant_id=p_tenant_id and t.lifecycle_state='active' for update;
  if not found then
    raise exception using errcode='P0002',message='commercial_tenant_not_found';
  end if;
  if p_operation not in ('manual_payment','correct_payment','complimentary','revoke','review_inactive')
    or p_operation is null or jsonb_typeof(r) is distinct from 'object'
    or length(p_idempotency_key) not between 16 and 128 or p_idempotency_key is null
    or length(p_request_id) not between 1 and 128 or p_request_id is null
    or length(r->>'reason') not between 3 and 1000 or r->>'reason' is null then
    raise exception using errcode='22023',message='commercial_command_invalid';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('commercial-access:'||p_tenant_id,0));
  fingerprint := encode(extensions.digest(convert_to(jsonb_build_object('request',r,'actor',p_actor_user_id)::text,'UTF8'),'sha256'),'hex');
  select * into prior from public.commercial_access_events where tenant_id=p_tenant_id and operation=p_operation and idempotency_key=p_idempotency_key;
  if found then
    if prior.request_hash<>fingerprint then raise exception using errcode='23505',message='commercial_idempotency_conflict'; end if;
    return prior.result;
  end if;
  before_state := public.resolve_commercial_access(p_tenant_id);
  if p_operation in ('manual_payment','correct_payment') then
    if p_operation='correct_payment' then
      select * into corrected from public.commercial_manual_payments where tenant_id=p_tenant_id and id=(r->>'payment_id')::uuid for update;
      if not found then raise exception using errcode='P0002',message='commercial_payment_not_found'; end if;
      if exists(select 1 from public.commercial_manual_payments where corrects_payment_id=corrected.id) then
        raise exception using errcode='23505',message='commercial_payment_already_corrected';
      end if;
    end if;
    if (r->>'paid_at')::timestamptz > v_now + interval '5 minutes' then
      raise exception using errcode='22023',message='commercial_paid_at_in_future';
    end if;
    insert into public.commercial_manual_payments(tenant_id,plan_id,method,expected_minor,actual_minor,currency,catalog_version,
      paid_at,valid_from,valid_until,billing_months,receipt_reference,reason,override_reason,corrects_payment_id,created_by)
    values(p_tenant_id,coalesce(corrected.plan_id,r->>'plan_id'),coalesce(corrected.method,r->>'method'),
      coalesce(corrected.expected_minor,(q->>'expected_minor')::bigint),(r->>'actual_minor')::bigint,
      coalesce(corrected.currency,r->>'currency'),coalesce(corrected.catalog_version,q->>'catalog_version'),
      (r->>'paid_at')::timestamptz,coalesce(corrected.valid_from,(r->>'valid_from')::timestamptz),
      coalesce(corrected.valid_until,(r->>'valid_until')::timestamptz),coalesce(corrected.billing_months,(r->>'billing_months')::integer),
      r->>'receipt_reference',r->>'reason',nullif(r->>'override_reason',''),corrected.id,p_actor_user_id) returning * into payment;
  end if;
  if p_operation in ('manual_payment','complimentary') then
    if nullif(r->>'supersedes_period_id','') is not null then
      select * into period from public.commercial_access_periods where tenant_id=p_tenant_id and id=(r->>'supersedes_period_id')::uuid for update;
      if not found then raise exception using errcode='P0002',message='commercial_period_not_found'; end if;
      if period.revoked_at is not null or (r->>'valid_from')::timestamptz < v_now
         or (r->>'valid_from')::timestamptz < period.valid_from
         or (r->>'valid_from')::timestamptz > period.valid_until then
        raise exception using errcode='22023',message='commercial_supersession_invalid';
      end if;
      update public.commercial_access_periods set revoked_at=(r->>'valid_from')::timestamptz,revoked_by=p_actor_user_id where id=period.id;
    end if;
    insert into public.commercial_access_periods(tenant_id,plan_id,valid_from,valid_until,source_type,manual_payment_id,reason,created_by)
    values(p_tenant_id,r->>'plan_id',(r->>'valid_from')::timestamptz,(r->>'valid_until')::timestamptz,
      case when p_operation='manual_payment' then r->>'method' else 'complimentary' end,payment.id,r->>'reason',p_actor_user_id)
    returning * into period;
  elsif p_operation='revoke' then
    select * into period from public.commercial_access_periods where tenant_id=p_tenant_id and id=(r->>'period_id')::uuid for update;
    if not found then raise exception using errcode='P0002',message='commercial_period_not_found'; end if;
    if period.revoked_at is not null then raise exception using errcode='23505',message='commercial_period_already_revoked'; end if;
    update public.commercial_access_periods set revoked_at=v_now,revoked_by=p_actor_user_id where id=period.id returning * into period;
  elsif p_operation='review_inactive' then
    if exists(select 1 from public.commercial_access_periods p where p.tenant_id=p_tenant_id and not isempty(p.effective_during) and upper(p.effective_during)>v_now) then
      raise exception using errcode='23505',message='commercial_revoke_access_first';
    end if;
  end if;
  update public.tenant_commercial_state set review_state='reviewed',reviewed_by=p_actor_user_id,reviewed_at=v_now,
    revision=revision+1,updated_at=v_now where tenant_id=p_tenant_id returning revision into v_revision;
  if not found then raise exception using errcode='P0002',message='commercial_state_missing'; end if;
  result := jsonb_build_object('payment_id',payment.id,'period_id',period.id,'revision',v_revision,'operation',p_operation,'tenant_id',p_tenant_id);
  insert into public.commercial_access_events(tenant_id,operation,idempotency_key,request_hash,actor_user_id,aal,request_id,revision,result)
    values(p_tenant_id,p_operation,p_idempotency_key,fingerprint,p_actor_user_id,p_aal,p_request_id,v_revision,result);
  insert into public.audit_logs(tenant_id,actor_user_id,action,target_type,target_id,metadata)
    values(p_tenant_id,p_actor_user_id,'admin.commercial.'||p_operation,'commercial_access',coalesce(period.id,payment.id)::text,
      jsonb_build_object('aal',p_aal,'request_id',p_request_id,'previous_revision',before_state->'revision','revision',v_revision,
        'old_plan',before_state->'period'->>'plan_id','new_plan',public.resolve_commercial_access(p_tenant_id)->'period'->>'plan_id',
        'expected_minor',payment.expected_minor,'actual_minor',payment.actual_minor,'currency',payment.currency,'method',payment.method));
  return result;
end;
$$;

alter table public.tenant_commercial_state enable row level security;
alter table public.commercial_manual_payments enable row level security;
alter table public.commercial_access_periods enable row level security;
alter table public.commercial_access_events enable row level security;
revoke all on public.tenant_commercial_state,public.commercial_manual_payments,public.commercial_access_periods,public.commercial_access_events from public,anon,authenticated,service_role;
grant select on public.tenant_commercial_state,public.commercial_manual_payments,public.commercial_access_periods,public.commercial_access_events to service_role;
revoke all on function public.bump_commercial_revision() from public,anon,authenticated,service_role;
revoke all on function public.resolve_commercial_access(integer) from public,anon,authenticated;
revoke all on function public.apply_commercial_access_command(integer,integer,text,text,text,text,jsonb) from public,anon,authenticated;
grant execute on function public.resolve_commercial_access(integer) to service_role;
grant execute on function public.apply_commercial_access_command(integer,integer,text,text,text,text,jsonb) to service_role;

do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
  if v_schema_version is null then raise exception using errcode='P0001',message='migration_094_schema_state_missing'; end if;
  if v_schema_version <> 93 then raise exception using errcode='P0001',message=format('migration_094_expected_schema_93_got_%s',v_schema_version); end if;
  update public.application_schema_state set schema_version=94,applied_at=now() where contract_key = 'core';
end;
$$;
notify pgrst,'reload schema';
COMMIT;
