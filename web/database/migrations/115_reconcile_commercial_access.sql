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

-- V2 modular assignment extends the existing subscription authority. Legacy
-- plan rows and financial evidence are retained, never inferred into modules.
create table public.commercial_price_books (
  id text primary key check (id ~ '^[a-z][a-z0-9_]{2,63}$'),
  version text not null,
  effective_from timestamptz not null check (isfinite(effective_from)),
  currency text not null check (currency='USD'),
  billing_interval text not null check (billing_interval='month'),
  standalone_minor jsonb not null,
  bundle_minor jsonb not null default '{}'::jsonb,
  sales_start_at timestamptz check (sales_start_at is null or isfinite(sales_start_at)),
  sales_end_at timestamptz check (sales_end_at is null or (isfinite(sales_end_at) and sales_end_at>sales_start_at)),
  check (sales_start_at is not null or sales_end_at is null)
);
-- Prepared, NOT commercially activated. A governed future launch records start.
insert into public.commercial_price_books(id,version,effective_from,currency,billing_interval,standalone_minor,bundle_minor)
values('launch_2026','2026-09-30','2026-09-30T00:00:00Z','USD','month',
  '{"forms":1500,"website":2000,"ecommerce":2000}','{"2":3000,"3":4000}');
alter table public.commercial_price_books enable row level security;
revoke all on public.commercial_price_books from public,anon,authenticated,service_role;
grant select on public.commercial_price_books to service_role;
create function public.guard_price_book_definition() returns trigger language plpgsql set search_path='' as $$
begin
  if tg_op='DELETE' or (to_jsonb(new)-'sales_start_at'-'sales_end_at') is distinct from (to_jsonb(old)-'sales_start_at'-'sales_end_at') then
    raise exception using errcode='42501',message='commercial_price_book_immutable';
  end if;
  if old.sales_start_at is not null and new.sales_start_at is distinct from old.sales_start_at then
    raise exception using errcode='42501',message='commercial_sales_start_immutable';
  end if;
  if old.sales_end_at is not null and new.sales_end_at is distinct from old.sales_end_at then
    raise exception using errcode='42501',message='commercial_sales_close_immutable';
  end if;
  return new;
end;
$$;
create trigger price_book_definition_immutable before update or delete on public.commercial_price_books
for each row execute function public.guard_price_book_definition();

create function public.valid_module_basis(b jsonb) returns boolean language plpgsql immutable set search_path='' as $$
declare m record; acquired timestamptz; paid timestamptz;
begin
  if b is null or jsonb_typeof(b)<>'object' then return false; end if;
  for m in select key,value from jsonb_each(b) loop
    if m.key not in ('forms','website','ecommerce') or jsonb_typeof(m.value)<>'object'
      or jsonb_typeof(m.value->'price_book_id') is distinct from 'string'
      or length(m.value->>'price_book_id') not between 3 and 64
      or jsonb_typeof(m.value->'acquired_at') is distinct from 'string'
      or not (m.value ? 'paid_since') or jsonb_typeof(m.value->'paid_since') not in ('null','string') then return false; end if;
    acquired:=(m.value->>'acquired_at')::timestamptz;
    paid:=(m.value->>'paid_since')::timestamptz;
    if acquired is null or not isfinite(acquired) or (paid is not null and (not isfinite(paid) or paid<acquired)) then return false; end if;
  end loop;
  return true;
exception when others then return false;
end;
$$;
alter table public.tenant_subscriptions alter column plan_id drop not null,
  add column module_basis jsonb,
  add constraint tenant_subscription_product_model check (
    (module_basis is null and plan_id is not null) or
    (plan_id is null and module_basis is not null and public.valid_module_basis(module_basis) and (module_basis<>'{}'::jsonb or state='canceled') and state in ('active','canceled'))
  );
alter table public.commercial_access_periods alter column plan_id drop not null,
  add column module_ids text[], add column price_snapshot jsonb,
  add constraint access_period_product_model check (
    (plan_id is not null and module_ids is null) or
    (plan_id is null and module_ids is not null and cardinality(module_ids)>0 and module_ids <@ array['forms','website','ecommerce']::text[] and price_snapshot is not null)
  );
alter table public.commercial_manual_payments alter column plan_id drop not null,
  add column module_ids text[], add column price_snapshot jsonb,
  add constraint manual_payment_product_model check (
    (plan_id is not null and module_ids is null) or
    (plan_id is null and module_ids is not null and cardinality(module_ids)>0 and module_ids <@ array['forms','website','ecommerce']::text[] and price_snapshot is not null)
  );

-- Subscription mutation is also routed through privileged transactional RPCs.
revoke insert,update,delete on public.tenant_subscriptions from service_role;

-- Each price-book group uses only its own approved bundle rule. No inferred
-- cross-book discount; closed books remain eligible ONLY for paid continuous bases.
create function public.resolve_module_price(b jsonb, p_at timestamptz default statement_timestamp()) returns jsonb
language plpgsql stable security definer set search_path='' as $$
declare g record; book public.commercial_price_books; n integer; amount bigint; total bigint:=0; groups jsonb:='[]';
begin
  if b='{}'::jsonb or b is null or not public.valid_module_basis(b) then
    raise exception using errcode='22023',message='commercial_module_set_invalid';
  end if;
  for g in select value->>'price_book_id' book_id,array_agg(key order by key) modules,
    bool_and(value->>'paid_since' is not null) locked from jsonb_each(b) group by value->>'price_book_id' order by value->>'price_book_id' loop
    select * into book from public.commercial_price_books where id=g.book_id;
    if not found or book.effective_from>p_at or
      (not g.locked and (book.sales_start_at>p_at or (book.sales_end_at is not null and book.sales_end_at<=p_at))) then
      raise exception using errcode='22023',message='commercial_price_book_unavailable';
    end if;
    n:=cardinality(g.modules);
    if book.bundle_minor ? n::text then amount:=(book.bundle_minor->>n::text)::bigint;
    else select sum((book.standalone_minor->>m)::bigint) into amount from unnest(g.modules) m; end if;
    if amount is null or amount<=0 or amount>1000000000000 or exists(select 1 from unnest(g.modules) m where not (book.standalone_minor ? m)) then
      raise exception using errcode='22023',message='commercial_price_invalid';
    end if;
    total:=total+amount;
    groups:=groups||jsonb_build_array(jsonb_build_object('price_book_id',book.id,'price_book_version',book.version,
      'module_ids',g.modules,'recurring_minor',amount,'grandfathered',g.locked,'new_sales_active',book.sales_start_at is not null and book.sales_start_at<=p_at and (book.sales_end_at is null or book.sales_end_at>p_at)));
  end loop;
  return jsonb_build_object('module_ids',(select jsonb_agg(key order by key) from jsonb_each(b)),
    'price_groups',groups,'currency','USD','billing_interval','month','recurring_minor',total);
end;
$$;
-- Inspection remains usable if no approved current price exists after launch
-- closes; the basis is preserved and quoting/mutations fail with a conflict.
create function public.inspect_module_price(b jsonb) returns jsonb language plpgsql stable security definer set search_path='' as $$
begin
  if b is null or b='{}'::jsonb then return null; end if;
  return public.resolve_module_price(b);
exception when sqlstate '22023' then return jsonb_build_object('pricing_status','review_required');
end;
$$;
revoke all on function public.resolve_module_price(jsonb,timestamptz),public.inspect_module_price(jsonb),public.valid_module_basis(jsonb),public.guard_price_book_definition() from public,anon,authenticated;
grant execute on function public.resolve_module_price(jsonb,timestamptz),public.inspect_module_price(jsonb),public.valid_module_basis(jsonb) to service_role;

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
      'module_basis',a.module_basis,'pricing',public.inspect_module_price(a.module_basis),
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

-- Preserve Phase 4B: canonical access joins the publication in one SQL snapshot.
create or replace function public.get_public_site_runtime_context(
  p_identifier text,
  p_allow_legacy_alias boolean default false
)
returns table (
  settings jsonb,
  tenant_active boolean,
  project jsonb
)
language sql
stable
security invoker
set search_path = ''
as $function$
  with canonical as (
    select s.*
    from public.website_settings as s
    where s.subdomain = lower(p_identifier)
    limit 2
  ), matching as (
    select * from canonical
    union all
    select s.*
    from public.website_settings as s
    where p_allow_legacy_alias
      and not exists (select 1 from canonical)
      and lower(s.standard_path_slug) = lower(p_identifier)
    limit 2
  )
  select
    jsonb_build_object(
      'id', s.id,
      'tenant_id', s.tenant_id,
      'subdomain', s.subdomain,
      'standard_path_slug', s.standard_path_slug,
      'published_project_id', s.published_project_id,
      'user_id', to_jsonb(s)->'user_id',
      'brand', to_jsonb(s)->'brand',
      'footer_store_name', to_jsonb(s)->'footer_store_name',
      'logo_url', to_jsonb(s)->'logo_url',
      'loading_image_url', to_jsonb(s)->'loading_image_url',
      'contact_email', to_jsonb(s)->'contact_email',
      'phone', to_jsonb(s)->'phone',
      'description', to_jsonb(s)->'description',
      'ecommerce_theme', to_jsonb(s)->'ecommerce_theme',
      '_commercial_snapshot', public.resolve_commercial_access(s.tenant_id)
    ),
    coalesce(t.lifecycle_state = 'active', false),
    case when p.id is not null then jsonb_build_object(
      'id', p.id,
      'tenant_id', p.tenant_id,
      'name', p.name,
      'slug', p.slug,
      'status', p.status,
      'published_schema', p.published_schema,
      'published_version', p.published_version,
      'published_revision', p.published_revision,
      'schema_version', p.schema_version,
      'last_published_at', p.last_published_at,
      'updated_at', p.updated_at
    ) end
  from matching as s
  left join public.tenants as t on t.tenant_id = s.tenant_id
  left join public.builder_projects as p
    on p.id = s.published_project_id
   and p.tenant_id = s.tenant_id
   and p.status = 'published'
   and p.published_schema is not null
  where p_identifier ~ '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$';
$function$;

revoke all on function public.get_public_site_runtime_context(text, boolean)
  from public, anon, authenticated;
grant execute on function public.get_public_site_runtime_context(text, boolean)
  to service_role;

create or replace function public.apply_commercial_access_command(
  p_tenant_id integer, p_actor_user_id integer, p_aal text,
  p_operation text, p_idempotency_key text, p_request_id text, p_payload jsonb
) returns jsonb language plpgsql security definer set search_path='' as $$
declare
  r jsonb := p_payload->'request'; q jsonb := p_payload->'quote';
  fingerprint text; prior public.commercial_access_events;
  payment public.commercial_manual_payments; corrected public.commercial_manual_payments;
  period public.commercial_access_periods; before_state jsonb; result jsonb;
  v_revision bigint; after_state jsonb; subscription public.tenant_subscriptions; basis jsonb;
  module_key text; wanted text[]; price jsonb; snapshot jsonb; book_id text; book public.commercial_price_books; v_now timestamptz := statement_timestamp();
begin
  perform 1 from public.users u where u.id=p_actor_user_id and lower(btrim(u.user_type))='admin' and u.account_status='active' for share;
  if p_aal is distinct from 'aal2' or not found then
    raise exception using errcode='42501',message='platform_admin_aal2_required';
  end if;
  perform 1 from public.tenants t where t.tenant_id=p_tenant_id and t.lifecycle_state='active' for update;
  if not found then
    raise exception using errcode='P0002',message='commercial_tenant_not_found';
  end if;
  if p_operation not in ('manual_payment','correct_payment','complimentary','revoke','review_inactive','suspend','reactivate','assign_modules')
    or p_operation is null or jsonb_typeof(r) is distinct from 'object'
    or length(p_idempotency_key) not between 16 and 128 or p_idempotency_key is null
    or length(p_request_id) not between 1 and 128 or p_request_id is null
    or length(btrim(r->>'reason')) not between 3 and 1000 or r->>'reason' is null then
    raise exception using errcode='22023',message='commercial_command_invalid';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('commercial-access:'||p_tenant_id,0));
  if r ? 'module_ids' and jsonb_typeof(r->'module_ids')='array' then
    r:=jsonb_set(r,'{module_ids}',(select coalesce(jsonb_agg(value order by value),'[]'::jsonb) from jsonb_array_elements(r->'module_ids')));
  end if;
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
  if p_operation='assign_modules' then
    if jsonb_typeof(r->'module_ids') is distinct from 'array' then raise exception using errcode='22023',message='commercial_module_set_invalid'; end if;
    select array_agg(distinct m order by m) into wanted from jsonb_array_elements_text(r->'module_ids') m;
    wanted:=coalesce(wanted,array[]::text[]);
    if not (wanted <@ array['forms','website','ecommerce']::text[]) or cardinality(wanted)<>jsonb_array_length(r->'module_ids') then
      raise exception using errcode='22023',message='commercial_module_set_invalid';
    end if;
    select * into subscription from public.tenant_subscriptions where tenant_id=p_tenant_id and state='active' for update;
    basis:=coalesce(subscription.module_basis,'{}'::jsonb);
    select coalesce(jsonb_object_agg(key,value),'{}'::jsonb) into basis from jsonb_each(basis) where key=any(wanted);
    foreach module_key in array wanted loop
      if not (basis ? module_key) then
        book_id:=r->'price_books'->>module_key;
        if book_id is null then
          -- Prefer the still-open launch offer; after closure acquire under
          -- the latest approved active book, never restore a canceled lock.
          select id into book_id from public.commercial_price_books where effective_from<=v_now
            and sales_start_at<=v_now and (sales_end_at is null or sales_end_at>v_now)
            order by case when id='launch_2026' then 0 else 1 end,effective_from desc,id limit 1;
          if book_id is null then
            select id into book_id from public.commercial_price_books where id='launch_2026' and sales_start_at is null;
          end if;
        end if;
        select * into book from public.commercial_price_books where id=book_id;
        if not found or book.effective_from>v_now or book.sales_start_at>v_now or (book.sales_end_at is not null and book.sales_end_at<=v_now) then
          raise exception using errcode='22023',message='commercial_price_book_unavailable';
        end if;
        basis:=basis||jsonb_build_object(module_key,jsonb_build_object('price_book_id',book_id,'acquired_at',v_now,'paid_since',null));
      elsif r->'price_books' ? module_key and r->'price_books'->>module_key is distinct from basis->module_key->>'price_book_id' then
        raise exception using errcode='22023',message='commercial_continuous_basis_immutable';
      end if;
    end loop;
    if cardinality(wanted)>0 then price:=public.resolve_module_price(basis); else price:=jsonb_build_object('module_ids','[]'::jsonb,'price_groups','[]'::jsonb,'recurring_minor',0,'currency','USD','billing_interval','month'); end if;
    if subscription.id is not null then
      update public.tenant_subscriptions set state='canceled',updated_at=v_now where id=subscription.id;
    end if;
    if cardinality(wanted)>0 then
      insert into public.tenant_subscriptions(tenant_id,plan_id,module_basis,state,catalog_version,currency,price_minor,billing_interval,source,activated_by_user_id)
      values(p_tenant_id,null,basis,'active','2026-09-30-v2','USD',(price->>'recurring_minor')::integer,'month','reviewed_module_assignment',p_actor_user_id);
    end if;
    snapshot:=price||jsonb_build_object('tenant_id',p_tenant_id,'catalog_version','2026-09-30-v2','effective_from',v_now,
      'effective_until',null,'addons',coalesce(before_state->'addons','[]'::jsonb),'reference',r->>'reference',
      'previous_revision',v_revision,'revision',v_revision+1);
  end if;
  if p_operation in ('manual_payment','complimentary') and r ? 'module_ids' then
    select * into subscription from public.tenant_subscriptions where tenant_id=p_tenant_id and state='active' for update;
    basis:=subscription.module_basis;
    select array_agg(distinct m order by m) into wanted from jsonb_array_elements_text(r->'module_ids') m;
    if basis is null or cardinality(wanted)<>jsonb_array_length(r->'module_ids') or wanted is distinct from (select array_agg(key order by key) from jsonb_each(basis)) then
      raise exception using errcode='22023',message='commercial_assignment_mismatch';
    end if;
    if p_operation='manual_payment' and exists(
      select 1 from jsonb_each(basis) m left join public.commercial_price_books pb on pb.id=m.value->>'price_book_id'
      where m.value->>'paid_since' is null and (pb.id is null or pb.sales_start_at is null or pb.sales_start_at>v_now or (pb.sales_end_at is not null and pb.sales_end_at<=v_now))) then
      raise exception using errcode='22023',message='commercial_price_book_unavailable';
    end if;
    price:=public.resolve_module_price(basis);
    q:=jsonb_build_object('expected_minor',(price->>'recurring_minor')::bigint*coalesce((r->>'billing_months')::integer,1),'catalog_version','2026-09-30-v2');
    snapshot:=price||jsonb_build_object('tenant_id',p_tenant_id,'catalog_version','2026-09-30-v2','effective_from',r->>'valid_from',
      'effective_until',r->>'valid_until','addons',coalesce(before_state->'addons','[]'::jsonb),'reference',coalesce(r->>'reference',r->>'receipt_reference'),
      'previous_revision',v_revision,'revision',v_revision+1);
    if p_operation='manual_payment' then
      select jsonb_object_agg(key,value||jsonb_build_object('paid_since',coalesce(value->>'paid_since',v_now::text))) into basis from jsonb_each(basis);
      update public.tenant_subscriptions set module_basis=basis,updated_at=v_now where id=subscription.id;
    end if;
  elsif p_operation in ('manual_payment','complimentary') and exists(select 1 from public.commercial_price_books where sales_start_at<=v_now and (sales_end_at is null or sales_end_at>v_now)) then
    raise exception using errcode='22023',message='commercial_legacy_new_sales_retired';
  end if;
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
      paid_at,valid_from,valid_until,billing_months,receipt_reference,reason,override_reason,corrects_payment_id,created_by,module_ids,price_snapshot)
    values(p_tenant_id,coalesce(corrected.plan_id,r->>'plan_id'),coalesce(corrected.method,r->>'method'),
      coalesce(corrected.expected_minor,(q->>'expected_minor')::bigint),(r->>'actual_minor')::bigint,
      coalesce(corrected.currency,r->>'currency'),coalesce(corrected.catalog_version,q->>'catalog_version'),
      (r->>'paid_at')::timestamptz,coalesce(corrected.valid_from,(r->>'valid_from')::timestamptz),
      coalesce(corrected.valid_until,(r->>'valid_until')::timestamptz),coalesce(corrected.billing_months,(r->>'billing_months')::integer),
      r->>'receipt_reference',r->>'reason',nullif(r->>'override_reason',''),corrected.id,p_actor_user_id,coalesce(corrected.module_ids,wanted),coalesce(corrected.price_snapshot,snapshot)) returning * into payment;
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
    insert into public.commercial_access_periods(tenant_id,plan_id,valid_from,valid_until,source_type,manual_payment_id,reason,created_by,module_ids,price_snapshot)
    values(p_tenant_id,r->>'plan_id',(r->>'valid_from')::timestamptz,(r->>'valid_until')::timestamptz,
      case when p_operation='manual_payment' then r->>'method' else 'complimentary' end,payment.id,r->>'reason',p_actor_user_id,wanted,snapshot)
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
    'price_snapshot',snapshot,'previous_state',before_state,'resulting_state',after_state,'reason',btrim(r->>'reason'),'reference',coalesce(r->>'reference',r->>'receipt_reference'));
  insert into public.commercial_access_events(tenant_id,operation,idempotency_key,request_hash,actor_user_id,aal,request_id,revision,result)
    values(p_tenant_id,p_operation,p_idempotency_key,fingerprint,p_actor_user_id,p_aal,p_request_id,v_revision,result);
  insert into public.audit_logs(tenant_id,actor_user_id,action,target_type,target_id,metadata)
    values(p_tenant_id,p_actor_user_id,'admin.commercial.'||p_operation,'commercial_access',coalesce(period.id::text,payment.id::text,p_tenant_id::text),
      jsonb_build_object('aal',p_aal,'actor_role','admin','request_id',p_request_id,'idempotency_key',p_idempotency_key,
        'price_snapshot',snapshot,'reason',btrim(r->>'reason'),'reference',coalesce(r->>'reference',r->>'receipt_reference'),'previous_state',before_state,'resulting_state',after_state,'previous_revision',before_state->'revision','revision',v_revision,
        'old_plan',before_state->'period'->>'plan_id','new_plan',public.resolve_commercial_access(p_tenant_id)->'period'->>'plan_id',
        'expected_minor',payment.expected_minor,'actual_minor',payment.actual_minor,'currency',payment.currency,'method',payment.method));
  return result;
end;
$$;


-- A period can be revoked/superseded, but its coverage/price evidence is immutable.
create function public.guard_access_period_evidence() returns trigger language plpgsql set search_path='' as $$
begin
  if tg_op='DELETE' or (to_jsonb(new)-'revoked_at'-'revoked_by'-'effective_during') is distinct from (to_jsonb(old)-'revoked_at'-'revoked_by'-'effective_during') then
    raise exception using errcode='42501',message='commercial_period_evidence_immutable';
  end if;
  return new;
end;
$$;
create trigger access_period_evidence_immutable before update or delete on public.commercial_access_periods
for each row execute function public.guard_access_period_evidence();
revoke all on function public.guard_access_period_evidence() from public,anon,authenticated,service_role;

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
