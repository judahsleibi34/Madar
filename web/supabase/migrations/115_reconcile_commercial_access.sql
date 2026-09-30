BEGIN;

-- Product assignment remains in tenant_subscriptions. Effective access and
-- reversible administrative holds belong to the existing commercial ledger.
alter table public.tenant_commercial_state
  add column commercial_suspended_at timestamptz,
  add column commercial_suspended_by integer references public.users(id) on delete restrict,
  add column commercial_suspension_reason text,
  add constraint tenant_commercial_hold_consistent check (
    (commercial_suspended_at is null and commercial_suspended_by is null and commercial_suspension_reason is null)
    or (commercial_suspended_at is not null and isfinite(commercial_suspended_at)
      and commercial_suspended_by is not null
      and length(btrim(commercial_suspension_reason)) between 3 and 1000
      and commercial_suspension_reason is not null)
  );

create or replace function public.resolve_commercial_access(p_tenant_id integer) returns jsonb
language sql stable security definer set search_path='' as $$
select jsonb_build_object(
  'contract_version',115,'tenant_id', s.tenant_id, 'revision',s.revision,'review_state',s.review_state,
  'commercial_suspended_at',s.commercial_suspended_at,
  'commercial_suspended_by',s.commercial_suspended_by,
  'access_state',case
    when s.commercial_suspended_at is not null then 'suspended'
    when s.review_state='review_required' then 'review_required'
    when exists(select 1 from public.commercial_access_periods p where p.tenant_id=s.tenant_id and p.effective_during @> statement_timestamp()) then 'active'
    when exists(select 1 from public.commercial_access_periods p where p.tenant_id=s.tenant_id and p.valid_until <= statement_timestamp()) then 'expired'
    else 'inactive' end,
  'subscriptions',coalesce((select jsonb_agg(jsonb_build_object('id',a.id,'tenant_id',a.tenant_id,'plan_id',a.plan_id,
      'state',a.state,'period_start',a.period_start,'period_end',a.period_end,'source',a.source) order by a.updated_at desc)
    from public.tenant_subscriptions a where a.tenant_id=s.tenant_id),'[]'::jsonb),
  'reviewed_at',s.reviewed_at,'effective_at',statement_timestamp(),
  'period',(select to_jsonb(p)-'reason'-'source_reference'-'effective_during' from public.commercial_access_periods p
            where p.tenant_id=s.tenant_id and p.effective_during @> statement_timestamp()),
  'has_history',exists(select 1 from public.commercial_access_periods p where p.tenant_id=s.tenant_id),
  'grandfathered_subdomain',exists(select 1 from public.website_settings w where w.tenant_id=s.tenant_id and w.branded_subdomain_commercial_status='grandfathered'),
  'next_transition_at',(select min(t) from (
    select unnest(array[lower(p.effective_during),upper(p.effective_during)]) t from public.commercial_access_periods p where p.tenant_id=s.tenant_id
    union all select unnest(array[a.period_start,a.period_end]) from public.tenant_subscriptions a where a.tenant_id=s.tenant_id
    union all select unnest(array[a.period_start,a.period_end]) from public.tenant_addons a where a.tenant_id=s.tenant_id and a.state='active'
  ) transitions where t > statement_timestamp()),
  'addons',coalesce((select jsonb_agg(to_jsonb(a)-'reason'-'migration_provenance') from public.tenant_addons a where a.tenant_id=s.tenant_id
            and a.state='active' and (a.period_start is null or a.period_start <= statement_timestamp())
            and (a.period_end is null or a.period_end > statement_timestamp())), '[]'::jsonb)
) from public.tenant_commercial_state s where s.tenant_id=p_tenant_id;
$$;

create or replace function public.apply_commercial_access_command(
  p_tenant_id integer, p_actor_user_id integer, p_aal text,
  p_operation text, p_idempotency_key text, p_request_id text, p_payload jsonb
) returns jsonb language plpgsql security definer set search_path='' as $$
declare
  r jsonb := p_payload->'request'; q jsonb := p_payload->'quote';
  fingerprint text; prior public.commercial_access_events;
  payment public.commercial_manual_payments; corrected public.commercial_manual_payments;
  period public.commercial_access_periods; before_state jsonb; result jsonb;
  v_revision bigint; after_state jsonb; v_now timestamptz := statement_timestamp();
begin
  perform 1 from public.users u where u.id=p_actor_user_id and lower(btrim(u.user_type))='admin' and u.account_status='active' for share;
  if p_aal is distinct from 'aal2' or not found then
    raise exception using errcode='42501',message='platform_admin_aal2_required';
  end if;
  perform 1 from public.tenants t where t.tenant_id=p_tenant_id and t.lifecycle_state='active' for update;
  if not found then
    raise exception using errcode='P0002',message='commercial_tenant_not_found';
  end if;
  if p_operation not in ('manual_payment','correct_payment','complimentary','revoke','review_inactive','suspend','reactivate')
    or p_operation is null or jsonb_typeof(r) is distinct from 'object'
    or length(p_idempotency_key) not between 16 and 128 or p_idempotency_key is null
    or length(p_request_id) not between 1 and 128 or p_request_id is null
    or length(btrim(r->>'reason')) not between 3 and 1000 or r->>'reason' is null then
    raise exception using errcode='22023',message='commercial_command_invalid';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('commercial-access:'||p_tenant_id,0));
  fingerprint := encode(extensions.digest(convert_to(jsonb_build_object('request',r,'actor',p_actor_user_id)::text,'UTF8'),'sha256'),'hex');
  select * into prior from public.commercial_access_events where tenant_id=p_tenant_id and idempotency_key=p_idempotency_key order by created_at limit 1;
  if found then
    if prior.operation<>p_operation or prior.request_hash<>fingerprint then raise exception using errcode='23505',message='commercial_idempotency_conflict'; end if;
    return prior.result;
  end if;
  -- Replay precedes revision comparison: a retry returns the committed result.
  select revision into v_revision from public.tenant_commercial_state where tenant_id=p_tenant_id for update;
  if not found then raise exception using errcode='P0002',message='commercial_state_missing'; end if;
  if jsonb_typeof(r->'expected_revision') is distinct from 'number'
     or (r->>'expected_revision') !~ '^[1-9][0-9]*$' then
    raise exception using errcode='22023',message='commercial_expected_revision_required';
  end if;
  if (r->>'expected_revision')::bigint <> v_revision then
    raise exception using errcode='40001',message='commercial_revision_conflict';
  end if;
  if r ? 'reference' and (jsonb_typeof(r->'reference') is distinct from 'string' or length(r->>'reference')>200) then
    raise exception using errcode='22023',message='commercial_reference_invalid';
  end if;
  before_state := public.resolve_commercial_access(p_tenant_id);
  if p_operation='suspend' then
    update public.tenant_commercial_state set commercial_suspended_at=coalesce(commercial_suspended_at,v_now),
      commercial_suspended_by=coalesce(commercial_suspended_by,p_actor_user_id),
      commercial_suspension_reason=coalesce(commercial_suspension_reason,btrim(r->>'reason'))
      where tenant_id=p_tenant_id;
  elsif p_operation='reactivate' then
    update public.tenant_commercial_state set commercial_suspended_at=null,
      commercial_suspended_by=null,commercial_suspension_reason=null where tenant_id=p_tenant_id;
  end if;
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
  update public.tenant_commercial_state set review_state=case when p_operation in ('suspend','reactivate') then review_state else 'reviewed' end,reviewed_by=case when p_operation in ('suspend','reactivate') then reviewed_by else p_actor_user_id end,
    reviewed_at=case when p_operation in ('suspend','reactivate') then reviewed_at else v_now end,
    revision=revision+1,updated_at=v_now where tenant_id=p_tenant_id returning revision into v_revision;
  if not found then raise exception using errcode='P0002',message='commercial_state_missing'; end if;
  after_state := public.resolve_commercial_access(p_tenant_id);
  result := jsonb_build_object('payment_id',payment.id,'period_id',period.id,'revision',v_revision,'operation',p_operation,'tenant_id',p_tenant_id,
    'previous_state',before_state,'resulting_state',after_state,'reason',btrim(r->>'reason'),'reference',coalesce(r->>'reference',r->>'receipt_reference'));
  insert into public.commercial_access_events(tenant_id,operation,idempotency_key,request_hash,actor_user_id,aal,request_id,revision,result)
    values(p_tenant_id,p_operation,p_idempotency_key,fingerprint,p_actor_user_id,p_aal,p_request_id,v_revision,result);
  insert into public.audit_logs(tenant_id,actor_user_id,action,target_type,target_id,metadata)
    values(p_tenant_id,p_actor_user_id,'admin.commercial.'||p_operation,'commercial_access',coalesce(period.id::text,payment.id::text,p_tenant_id::text),
      jsonb_build_object('aal',p_aal,'actor_role','admin','request_id',p_request_id,'idempotency_key',p_idempotency_key,
        'reason',btrim(r->>'reason'),'reference',coalesce(r->>'reference',r->>'receipt_reference'),'previous_state',before_state,'resulting_state',after_state,'previous_revision',before_state->'revision','revision',v_revision,
        'old_plan',before_state->'period'->>'plan_id','new_plan',public.resolve_commercial_access(p_tenant_id)->'period'->>'plan_id',
        'expected_minor',payment.expected_minor,'actual_minor',payment.actual_minor,'currency',payment.currency,'method',payment.method));
  return result;
end;
$$;


-- The RPC remains the sole application mutation boundary. Financial evidence
-- and command history cannot be overwritten even by a later privileged writer.
create function public.guard_commercial_immutable_history() returns trigger
language plpgsql set search_path='' as $$
begin
  raise exception using errcode='42501',message='commercial_history_immutable';
end;
$$;
create trigger commercial_payment_immutable before update or delete on public.commercial_manual_payments
  for each row execute function public.guard_commercial_immutable_history();
create trigger commercial_event_immutable before update or delete on public.commercial_access_events
  for each row execute function public.guard_commercial_immutable_history();
revoke all on function public.guard_commercial_immutable_history() from public,anon,authenticated,service_role;
revoke all on function public.resolve_commercial_access(integer) from public,anon,authenticated;
revoke all on function public.apply_commercial_access_command(integer,integer,text,text,text,text,jsonb) from public,anon,authenticated;
grant execute on function public.resolve_commercial_access(integer) to service_role;
grant execute on function public.apply_commercial_access_command(integer,integer,text,text,text,text,jsonb) to service_role;

do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
  if v_schema_version is null then raise exception using errcode='P0001',message='migration_115_schema_state_missing'; end if;
  if v_schema_version <> 114 then raise exception using errcode='P0001',message=format('migration_115_expected_schema_114_got_%s',v_schema_version); end if;
  update public.application_schema_state set schema_version=115,applied_at=now() where contract_key = 'core';
end;
$$;
notify pgrst,'reload schema';
COMMIT;
