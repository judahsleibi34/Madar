begin;

do $$
declare
  v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version
  into v_schema_version
  from public.application_schema_state
  where contract_key = 'core'
  for update;

  if v_schema_version is null then
    raise exception using errcode = 'P0001', message = 'migration_145_schema_state_missing';
  end if;
  if v_schema_version <> 144 then
    raise exception using errcode = 'P0001',
      message = format('migration_145_expected_schema_144_got_%s', v_schema_version);
  end if;
end;
$$;

-- A paid price lock exists only while the database clock is inside confirmed
-- paid coverage. Recursion follows exactly adjacent half-open periods, so an
-- advance renewal at [old.valid_until, new.valid_until) has no artificial gap.
create function public.commercial_paid_continuity_end(
  p_tenant_id integer,
  p_module_id text,
  p_price_book_id text,
  p_at timestamptz default statement_timestamp()
) returns timestamptz
language sql
stable
security definer
set search_path = ''
as $$
with recursive eligible as (
  select p.id, p.effective_during
  from public.commercial_access_periods p
  where p.tenant_id = p_tenant_id
    and p.plan_id is null
    and p.module_ids @> array[p_module_id]::text[]
    and p.source_type in ('cash','bank_transfer','other_manual','cybersource')
    and not isempty(p.effective_during)
    and exists (
      select 1
      from jsonb_array_elements(coalesce(p.price_snapshot->'price_groups','[]'::jsonb)) g
      where g->>'price_book_id' = p_price_book_id
        and coalesce(g->'module_ids','[]'::jsonb) ? p_module_id
    )
), chain as (
  select e.id, upper(e.effective_during) as covered_until
  from eligible e
  where e.effective_during @> p_at
  union all
  select n.id, upper(n.effective_during)
  from chain c
  join eligible n on lower(n.effective_during) = c.covered_until
)
select max(covered_until) from chain;
$$;

create function public.commercial_basis_exception_valid(
  p_basis jsonb,
  p_at timestamptz default statement_timestamp()
) returns boolean
language sql
stable
set search_path = ''
as $$
select coalesce((p_basis->>'restoration_pending')::boolean,false)
  and nullif(p_basis->>'restored_at','')::timestamptz <= p_at
  and length(btrim(coalesce(p_basis->>'restoration_reference',''))) between 1 and 200;
$$;

-- This replaces schema115's paid_since shortcut. Without a tenant command
-- context a closed price book is never considered reusable.
create or replace function public.resolve_module_price(
  b jsonb,
  p_at timestamptz default statement_timestamp()
) returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  g record;
  module_key text;
  book public.commercial_price_books;
  n integer;
  amount bigint;
  total bigint := 0;
  groups jsonb := '[]'::jsonb;
  tenant_text text := current_setting('madar.commercial_tenant_id', true);
  tenant_id integer;
  book_open boolean;
  protected boolean;
  exception_used boolean;
  continuity_until timestamptz;
  group_until timestamptz;
begin
  if b='{}'::jsonb or b is null or not public.valid_module_basis(b) then
    raise exception using errcode='22023',message='commercial_module_set_invalid';
  end if;
  if tenant_text ~ '^[1-9][0-9]*$' then tenant_id:=tenant_text::integer; end if;

  for g in
    select value->>'price_book_id' book_id, array_agg(key order by key) modules
    from jsonb_each(b)
    group by value->>'price_book_id'
    order by value->>'price_book_id'
  loop
    select * into book from public.commercial_price_books where id=g.book_id;
    if not found or book.effective_from>p_at then
      raise exception using errcode='22023',message='commercial_price_book_unavailable';
    end if;
    book_open := book.sales_start_at is not null and book.sales_start_at<=p_at
      and (book.sales_end_at is null or book.sales_end_at>p_at);
    protected := true;
    exception_used := false;
    group_until := null;
    foreach module_key in array g.modules loop
      continuity_until := null;
      if tenant_id is not null then
        continuity_until := public.commercial_paid_continuity_end(
          tenant_id,module_key,g.book_id,p_at
        );
      end if;
      if continuity_until is not null then
        group_until := case when group_until is null then continuity_until
          else least(group_until,continuity_until) end;
      elsif public.commercial_basis_exception_valid(b->module_key,p_at) then
        exception_used := true;
      else
        protected := false;
      end if;
    end loop;
    if not book_open and not protected then
      raise exception using errcode='22023',message='commercial_paid_continuity_required';
    end if;
    n:=cardinality(g.modules);
    if book.bundle_minor ? n::text then amount:=(book.bundle_minor->>n::text)::bigint;
    else select sum((book.standalone_minor->>m)::bigint) into amount from unnest(g.modules) m; end if;
    if amount is null or amount<=0 or amount>1000000000000
       or exists(select 1 from unnest(g.modules) m where not (book.standalone_minor ? m)) then
      raise exception using errcode='22023',message='commercial_price_invalid';
    end if;
    total:=total+amount;
    groups:=groups||jsonb_build_array(jsonb_build_object(
      'price_book_id',book.id,
      'price_book_version',book.version,
      'module_ids',g.modules,
      'recurring_minor',amount,
      'grandfathered',not book_open and protected,
      'protected_by',case when exception_used then 'administrative_exception'
                          when not book_open and protected then 'paid_continuity'
                          else null end,
      'protection_valid_until',group_until,
      'new_sales_active',book_open
    ));
  end loop;
  return jsonb_build_object(
    'module_ids',(select jsonb_agg(key order by key) from jsonb_each(b)),
    'price_groups',groups,
    'currency','USD',
    'billing_interval','month',
    'recurring_minor',total
  );
end;
$$;

create function public.inspect_tenant_module_price(p_tenant_id integer,b jsonb)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  if b is null or b='{}'::jsonb then return null; end if;
  perform set_config('madar.commercial_tenant_id',p_tenant_id::text,true);
  return public.resolve_module_price(b);
exception when sqlstate '22023' then
  return jsonb_build_object('pricing_status','review_required');
end;
$$;

create or replace function public.quote_commercial_modules(p_tenant_id integer,r jsonb)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  wanted text[];
  subscription public.tenant_subscriptions;
  basis jsonb;
  module_key text;
  current_basis jsonb;
  book_id text;
  book public.commercial_price_books;
  price jsonb;
  v_now timestamptz:=clock_timestamp();
  book_open boolean;
  continuity_until timestamptz;
begin
  if not exists(select 1 from public.tenants where tenant_id=p_tenant_id) then
    raise exception using errcode='P0002',message='commercial_tenant_not_found';
  end if;
  if jsonb_typeof(r->'module_ids') is distinct from 'array' then
    raise exception using errcode='22023',message='commercial_module_set_invalid';
  end if;
  select array_agg(distinct m order by m) into wanted from jsonb_array_elements_text(r->'module_ids') m;
  wanted:=coalesce(wanted,array[]::text[]);
  if not (wanted <@ array['forms','website','ecommerce']::text[])
     or cardinality(wanted)<>jsonb_array_length(r->'module_ids') then
    raise exception using errcode='22023',message='commercial_module_set_invalid';
  end if;

  select * into subscription from public.tenant_subscriptions
    where tenant_id=p_tenant_id and state='active';
  current_basis:=coalesce(subscription.module_basis,'{}'::jsonb);
  select coalesce(jsonb_object_agg(key,value),'{}'::jsonb) into basis
    from jsonb_each(current_basis) where key=any(wanted);

  -- Expired closed-book bases remain in the old subscription row but are not
  -- carried into an ordinary successor assignment.
  foreach module_key in array wanted loop
    if basis ? module_key then
      book_id:=basis->module_key->>'price_book_id';
      select * into book from public.commercial_price_books where id=book_id;
      book_open:=found and book.effective_from<=v_now
        and book.sales_start_at is not null and book.sales_start_at<=v_now
        and (book.sales_end_at is null or book.sales_end_at>v_now);
      continuity_until:=public.commercial_paid_continuity_end(
        p_tenant_id,module_key,book_id,v_now
      );
      if not book_open and continuity_until is null
         and not public.commercial_basis_exception_valid(basis->module_key,v_now) then
        basis:=basis-module_key;
      end if;
    end if;
  end loop;

  foreach module_key in array wanted loop
    if not (basis ? module_key) then
      book_id:=r->'price_books'->>module_key;
      if book_id is null then
        select id into book_id from public.commercial_price_books
        where effective_from<=v_now and sales_start_at<=v_now
          and (sales_end_at is null or sales_end_at>v_now)
        order by case when id='launch_2026' then 0 else 1 end,effective_from desc,id limit 1;
      end if;
      select * into book from public.commercial_price_books where id=book_id;
      if not found or book.effective_from>v_now or book.sales_start_at is null
         or book.sales_start_at>v_now
         or (book.sales_end_at is not null and book.sales_end_at<=v_now) then
        raise exception using errcode='22023',message='commercial_price_book_unavailable';
      end if;
      basis:=basis||jsonb_build_object(module_key,jsonb_build_object(
        'price_book_id',book_id,'acquired_at',v_now,'paid_since',null
      ));
    elsif r->'price_books' ? module_key
      and r->'price_books'->>module_key is distinct from basis->module_key->>'price_book_id' then
      raise exception using errcode='22023',message='commercial_continuous_basis_immutable';
    end if;
  end loop;

  perform set_config('madar.commercial_tenant_id',p_tenant_id::text,true);
  if cardinality(wanted)>0 then price:=public.resolve_module_price(basis);
  else price:=jsonb_build_object('module_ids','[]'::jsonb,'price_groups','[]'::jsonb,
    'recurring_minor',0,'currency','USD','billing_interval','month'); end if;
  return jsonb_build_object(
    'module_basis',basis,
    'pricing',price,
    'revision',(select revision from public.tenant_commercial_state where tenant_id=p_tenant_id),
    'removed_module_ids',(select coalesce(jsonb_agg(key order by key),'[]'::jsonb)
      from jsonb_each(current_basis) where not(key=any(wanted)))
  );
end;
$$;

-- Enforce adjacency for every closed-book module before immutable paid access
-- evidence is inserted. Complimentary periods never extend paid continuity.
create function public.guard_paid_commercial_continuity145()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  subscription public.tenant_subscriptions;
  item record;
  book public.commercial_price_books;
  continuity_until timestamptz;
  v_now timestamptz:=clock_timestamp();
begin
  if new.plan_id is not null
     or new.source_type not in ('cash','bank_transfer','other_manual','cybersource') then
    return new;
  end if;
  select * into subscription from public.tenant_subscriptions
    where tenant_id=new.tenant_id and state='active' for share;
  if subscription.module_basis is null then
    raise exception using errcode='22023',message='commercial_assignment_mismatch';
  end if;
  for item in select key,value from jsonb_each(subscription.module_basis) loop
    select * into book from public.commercial_price_books
      where id=item.value->>'price_book_id';
    if not found then
      raise exception using errcode='22023',message='commercial_price_book_unavailable';
    end if;
    if book.sales_start_at is not null and book.sales_start_at<=v_now
       and (book.sales_end_at is null or book.sales_end_at>v_now) then
      continue;
    end if;
    if public.commercial_basis_exception_valid(item.value,v_now) then
      if new.valid_from < (item.value->>'restored_at')::timestamptz then
        raise exception using errcode='22023',message='commercial_restoration_backdate_forbidden';
      end if;
      continue;
    end if;
    continuity_until:=public.commercial_paid_continuity_end(
      new.tenant_id,item.key,item.value->>'price_book_id',v_now
    );
    if continuity_until is null or new.valid_from is distinct from continuity_until then
      raise exception using errcode='22023',message='commercial_paid_continuity_required';
    end if;
  end loop;
  return new;
end;
$$;
create trigger paid_commercial_continuity145
before insert on public.commercial_access_periods
for each row execute function public.guard_paid_commercial_continuity145();

-- A successful paid grant consumes the one-time restoration authorization.
create function public.consume_commercial_restoration145()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare basis jsonb;
begin
  if new.plan_id is not null
     or new.source_type not in ('cash','bank_transfer','other_manual','cybersource') then
    return new;
  end if;
  select jsonb_object_agg(key,value-'restoration_pending'-'restored_at'-'restored_by'-'restoration_reference')
  into basis
  from jsonb_each((select module_basis from public.tenant_subscriptions
    where tenant_id=new.tenant_id and state='active'));
  if basis is not null then
    update public.tenant_subscriptions
    set module_basis=basis,updated_at=clock_timestamp()
    where tenant_id=new.tenant_id and state='active'
      and module_basis is distinct from basis;
  end if;
  return new;
end;
$$;
create trigger consume_commercial_restoration145
after insert on public.commercial_access_periods
for each row execute function public.consume_commercial_restoration145();

create or replace function public.resolve_commercial_access(p_tenant_id integer)
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
select jsonb_build_object(
  'contract_version',115,
  'protection_contract_version',145,
  'protection_policy','strict_paid_continuity_v1',
  'tenant_id',s.tenant_id,
  'revision',s.revision,
  'review_state',s.review_state,
  'commercial_suspended_at',s.commercial_suspended_at,
  'commercial_suspended_by',s.commercial_suspended_by,
  'access_state',case
    when s.commercial_suspended_at is not null then 'suspended'
    when s.review_state='review_required' then 'review_required'
    when exists(select 1 from public.commercial_access_periods p
      where p.tenant_id=s.tenant_id and p.effective_during @> statement_timestamp()) then 'active'
    when exists(select 1 from public.commercial_access_periods p
      where p.tenant_id=s.tenant_id and p.valid_until<=statement_timestamp()) then 'expired'
    else 'inactive' end,
  'subscriptions',coalesce((select jsonb_agg(jsonb_build_object(
      'id',a.id,'tenant_id',a.tenant_id,'plan_id',a.plan_id,'module_basis',a.module_basis,
      'pricing',public.inspect_tenant_module_price(a.tenant_id,a.module_basis),
      'state',a.state,'period_start',a.period_start,'period_end',a.period_end,'source',a.source
    ) order by a.updated_at desc) from public.tenant_subscriptions a
    where a.tenant_id=s.tenant_id),'[]'::jsonb),
  'reviewed_at',s.reviewed_at,
  'effective_at',statement_timestamp(),
  'period',(select to_jsonb(p)-'reason'-'source_reference'-'effective_during'
    from public.commercial_access_periods p
    where p.tenant_id=s.tenant_id and p.effective_during @> statement_timestamp()),
  'has_history',exists(select 1 from public.commercial_access_periods p where p.tenant_id=s.tenant_id),
  'grandfathered_subdomain',exists(select 1 from public.website_settings w
    where w.tenant_id=s.tenant_id and w.branded_subdomain_commercial_status='grandfathered'),
  'next_transition_at',(select min(t) from (
    select unnest(array[lower(p.effective_during),upper(p.effective_during)]) t
      from public.commercial_access_periods p where p.tenant_id=s.tenant_id
    union all select unnest(array[a.period_start,a.period_end])
      from public.tenant_subscriptions a where a.tenant_id=s.tenant_id
    union all select unnest(array[a.period_start,a.period_end])
      from public.tenant_addons a where a.tenant_id=s.tenant_id and a.state='active'
  ) transitions where t>statement_timestamp()),
  'addons',coalesce((select jsonb_agg(to_jsonb(a)-'reason'-'migration_provenance')
    from public.tenant_addons a where a.tenant_id=s.tenant_id and a.state='active'
      and (a.period_start is null or a.period_start<=statement_timestamp())
      and (a.period_end is null or a.period_end>statement_timestamp())),'[]'::jsonb)
) from public.tenant_commercial_state s where s.tenant_id=p_tenant_id;
$$;

-- Retain schema115's command implementation as a private core. The wrapper
-- supplies tenant context to price resolution and owns the new exception path.
alter function public.apply_commercial_access_command(integer,integer,text,text,text,text,jsonb)
  rename to apply_commercial_access_command_115_core;
revoke all on function public.apply_commercial_access_command_115_core(integer,integer,text,text,text,text,jsonb)
  from public,anon,authenticated,service_role;

create function public.restore_commercial_price_basis145(
  p_tenant_id integer,p_actor_user_id integer,p_aal text,
  p_idempotency_key text,p_request_id text,p_payload jsonb
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  r jsonb:=p_payload->'request';
  fingerprint text;
  prior public.commercial_access_events;
  before_state jsonb;
  after_state jsonb;
  result jsonb;
  subscription public.tenant_subscriptions;
  historical public.tenant_subscriptions;
  basis jsonb:='{}'::jsonb;
  price jsonb;
  modules text[];
  module_key text;
  book_id text;
  book public.commercial_price_books;
  v_revision bigint;
  v_now timestamptz;
begin
  perform 1 from public.users u where u.id=p_actor_user_id
    and lower(btrim(u.user_type))='admin' and u.account_status='active' for share;
  if p_aal is distinct from 'aal2' or not found then
    raise exception using errcode='42501',message='platform_admin_aal2_required';
  end if;
  perform 1 from public.tenants t where t.tenant_id=p_tenant_id
    and t.lifecycle_state='active' for update;
  if not found then raise exception using errcode='P0002',message='commercial_tenant_not_found'; end if;
  if jsonb_typeof(r) is distinct from 'object'
     or jsonb_typeof(r->'module_ids') is distinct from 'array'
     or jsonb_typeof(r->'price_books') is distinct from 'object'
     or length(p_idempotency_key) not between 16 and 128
     or length(p_request_id) not between 1 and 128
     or length(btrim(coalesce(r->>'reason',''))) not between 3 and 1000
     or length(btrim(coalesce(r->>'reference',''))) not between 1 and 200 then
    raise exception using errcode='22023',message='commercial_restoration_invalid';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('commercial-access:'||p_tenant_id,0));
  v_now:=clock_timestamp();
  select array_agg(distinct value order by value) into modules
    from jsonb_array_elements_text(r->'module_ids');
  if modules is null or cardinality(modules)<>jsonb_array_length(r->'module_ids')
     or not (modules <@ array['forms','website','ecommerce']::text[])
     or (select array_agg(key order by key) from jsonb_each(r->'price_books')) is distinct from modules then
    raise exception using errcode='22023',message='commercial_restoration_invalid';
  end if;
  r:=jsonb_set(r,'{module_ids}',to_jsonb(modules));
  fingerprint:=encode(extensions.digest(convert_to(jsonb_build_object(
    'request',r,'actor',p_actor_user_id)::text,'UTF8'),'sha256'),'hex');
  select * into prior from public.commercial_access_events
    where tenant_id=p_tenant_id and idempotency_key=p_idempotency_key
    order by created_at limit 1;
  if found then
    if prior.operation<>'restore_price_basis' or prior.request_hash<>fingerprint then
      raise exception using errcode='23505',message='commercial_idempotency_conflict';
    end if;
    return prior.result;
  end if;
  select revision into v_revision from public.tenant_commercial_state
    where tenant_id=p_tenant_id for update;
  if jsonb_typeof(r->'expected_revision') is distinct from 'number'
     or (r->>'expected_revision') !~ '^[1-9][0-9]*$'
     or (r->>'expected_revision')::bigint<>v_revision then
    raise exception using errcode='40001',message='commercial_revision_conflict';
  end if;
  if exists(select 1 from public.commercial_access_periods p
    where p.tenant_id=p_tenant_id and p.effective_during @> v_now) then
    raise exception using errcode='22023',message='commercial_restoration_requires_expired_access';
  end if;
  before_state:=public.resolve_commercial_access(p_tenant_id);
  foreach module_key in array modules loop
    book_id:=r->'price_books'->>module_key;
    select * into book from public.commercial_price_books where id=book_id;
    if not found or book.effective_from>v_now
       or (book.sales_start_at is not null and book.sales_start_at<=v_now
         and (book.sales_end_at is null or book.sales_end_at>v_now)) then
      raise exception using errcode='22023',message='commercial_restoration_basis_invalid';
    end if;
    select * into historical from public.tenant_subscriptions h
      where h.tenant_id=p_tenant_id and h.module_basis ? module_key
        and h.module_basis->module_key->>'price_book_id'=book_id
        and h.module_basis->module_key->>'paid_since' is not null
      order by h.updated_at desc,h.id desc limit 1;
    if not found then
      raise exception using errcode='22023',message='commercial_restoration_history_missing';
    end if;
    if not exists(
      select 1
      from public.commercial_access_periods p
      where p.tenant_id=p_tenant_id
        and p.plan_id is null
        and p.module_ids @> array[module_key]::text[]
        and p.source_type in ('cash','bank_transfer','other_manual','cybersource')
        and exists (
          select 1
          from jsonb_array_elements(coalesce(p.price_snapshot->'price_groups','[]'::jsonb)) g
          where g->>'price_book_id'=book_id
            and coalesce(g->'module_ids','[]'::jsonb) ? module_key
        )
    ) then
      raise exception using errcode='22023',message='commercial_restoration_history_missing';
    end if;
    basis:=basis||jsonb_build_object(module_key,
      ((historical.module_basis->module_key)
        -'restoration_pending'-'restored_at'-'restored_by'-'restoration_reference')
      ||jsonb_build_object(
        'restoration_pending',true,
        'restored_at',v_now,
        'restored_by',p_actor_user_id,
        'restoration_reference',btrim(r->>'reference')
      ));
  end loop;
  perform set_config('madar.commercial_tenant_id',p_tenant_id::text,true);
  price:=public.resolve_module_price(basis,v_now);
  select * into subscription from public.tenant_subscriptions
    where tenant_id=p_tenant_id and state='active' for update;
  if subscription.id is not null then
    update public.tenant_subscriptions set state='canceled',updated_at=v_now
      where id=subscription.id;
  end if;
  insert into public.tenant_subscriptions(
    tenant_id,plan_id,module_basis,state,catalog_version,currency,price_minor,
    billing_interval,source,activated_by_user_id
  ) values(
    p_tenant_id,null,basis,'active','strict-paid-continuity-v1','USD',
    (price->>'recurring_minor')::integer,'month','audited_price_restoration',p_actor_user_id
  );
  update public.tenant_commercial_state
    set review_state='reviewed',reviewed_by=p_actor_user_id,reviewed_at=v_now,
        revision=revision+1,updated_at=v_now
    where tenant_id=p_tenant_id returning revision into v_revision;
  after_state:=public.resolve_commercial_access(p_tenant_id);
  result:=jsonb_build_object(
    'payment_id',null,'period_id',null,'revision',v_revision,
    'operation','restore_price_basis','tenant_id',p_tenant_id,
    'price_snapshot',price||jsonb_build_object(
      'tenant_id',p_tenant_id,'effective_from',v_now,'effective_until',null,
      'reference',btrim(r->>'reference'),'administrative_exception',true
    ),
    'previous_state',before_state,'resulting_state',after_state,
    'reason',btrim(r->>'reason'),'reference',btrim(r->>'reference')
  );
  insert into public.commercial_access_events(
    tenant_id,operation,idempotency_key,request_hash,actor_user_id,aal,request_id,revision,result
  ) values(
    p_tenant_id,'restore_price_basis',p_idempotency_key,fingerprint,
    p_actor_user_id,p_aal,p_request_id,v_revision,result
  );
  insert into public.audit_logs(
    tenant_id,actor_user_id,action,target_type,target_id,metadata
  ) values(
    p_tenant_id,p_actor_user_id,'admin.commercial.restore_price_basis',
    'commercial_access',p_tenant_id::text,jsonb_build_object(
      'aal',p_aal,'actor_role','admin','request_id',p_request_id,
      'idempotency_key',p_idempotency_key,'reason',btrim(r->>'reason'),
      'reference',btrim(r->>'reference'),'module_ids',to_jsonb(modules),
      'price_books',r->'price_books','previous_state',before_state,
      'resulting_state',after_state,'revision',v_revision
    )
  );
  return result;
end;
$$;

create function public.apply_commercial_access_command(
  p_tenant_id integer,p_actor_user_id integer,p_aal text,p_operation text,
  p_idempotency_key text,p_request_id text,p_payload jsonb
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
begin
  if p_operation='restore_price_basis' then
    return public.restore_commercial_price_basis145(
      p_tenant_id,p_actor_user_id,p_aal,p_idempotency_key,p_request_id,p_payload
    );
  end if;
  perform set_config('madar.commercial_tenant_id',p_tenant_id::text,true);
  return public.apply_commercial_access_command_115_core(
    p_tenant_id,p_actor_user_id,p_aal,p_operation,p_idempotency_key,p_request_id,p_payload
  );
end;
$$;

revoke all on function public.commercial_paid_continuity_end(integer,text,text,timestamptz),
  public.commercial_basis_exception_valid(jsonb,timestamptz),
  public.inspect_tenant_module_price(integer,jsonb),
  public.guard_paid_commercial_continuity145(),
  public.consume_commercial_restoration145(),
  public.restore_commercial_price_basis145(integer,integer,text,text,text,jsonb)
  from public,anon,authenticated,service_role;
revoke all on function public.resolve_module_price(jsonb,timestamptz),
  public.quote_commercial_modules(integer,jsonb),
  public.resolve_commercial_access(integer),
  public.apply_commercial_access_command(integer,integer,text,text,text,text,jsonb)
  from public,anon,authenticated;
grant execute on function public.resolve_module_price(jsonb,timestamptz),
  public.quote_commercial_modules(integer,jsonb),
  public.resolve_commercial_access(integer),
  public.apply_commercial_access_command(integer,integer,text,text,text,text,jsonb)
  to service_role;

update public.application_schema_state
set schema_version=145,applied_at=now()
where contract_key='core';

notify pgrst,'reload schema';
commit;
