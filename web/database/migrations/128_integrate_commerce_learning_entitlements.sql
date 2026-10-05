begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_128_schema_state_missing'; end if;
 if v_schema_version <> 127 then raise exception 'migration_128_expected_schema_127_got_%',v_schema_version; end if;
 update public.application_schema_state set schema_version=128,applied_at=now() where contract_key = 'core';
end $$;

-- Offerings extend the existing product/price and order ledger. Learning owns
-- only its resource associations; it never owns payment or accounting records.
create table public.ecommerce_offerings (
 id uuid primary key default gen_random_uuid(), tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
 product_id uuid not null, billing_type text not null check(billing_type in ('one_time','monthly','yearly')),
 resource_type text not null check(resource_type='elearning_course'), access_scope text not null check(access_scope in ('single_course','selected_courses','all_courses')),
 revision integer not null default 1 check(revision>0),
 foreign key(tenant_id,product_id) references public.ecommerce_products(tenant_id,id) on delete restrict,
 unique(tenant_id,id),unique(tenant_id,product_id)
);
alter table public.elearning_courses add column catalog_visible boolean not null default true;
create table public.elearning_offering_courses (
 tenant_id integer not null,offering_id uuid not null,course_id uuid not null,
 primary key(tenant_id,offering_id,course_id),
 foreign key(tenant_id,offering_id) references public.ecommerce_offerings(tenant_id,id) on delete cascade,
 foreign key(tenant_id,course_id) references public.elearning_courses(tenant_id,id) on delete cascade
);
alter table public.ecommerce_orders drop constraint ecommerce_orders_payment_method_check;
alter table public.ecommerce_orders add constraint ecommerce_orders_payment_method_check check(payment_method in ('cash_on_delivery','provider'));
create table public.ecommerce_checkouts (
 id uuid primary key default gen_random_uuid(), tenant_id integer not null references public.tenants(tenant_id) on delete cascade,
 user_id integer not null references public.users(id) on delete restrict,offering_id uuid not null,order_id uuid not null,
 provider text not null,provider_transaction_id text, idempotency_key uuid not null,
 requested_resource_id uuid, terms jsonb not null check(jsonb_typeof(terms)='object'),
 state text not null default 'pending' check(state in ('pending','paid','failed','refunded','reversed')),
 event_sequence bigint not null default 0,created_at timestamptz not null default now(),
 foreign key(tenant_id,offering_id) references public.ecommerce_offerings(tenant_id,id) on delete restrict,
 foreign key(tenant_id,order_id) references public.ecommerce_orders(tenant_id,id) on delete restrict,
 unique(tenant_id,id),unique(tenant_id,user_id,idempotency_key),unique(tenant_id,order_id),
 unique(provider,provider_transaction_id)
);
create table public.ecommerce_payment_events (
 provider text not null,event_id text not null,tenant_id integer not null,checkout_id uuid not null,
 transaction_id text not null,sequence bigint not null, state text not null,amount numeric(14,2) not null,currency text not null,
 period_end timestamptz,cancel_at_period_end boolean not null default false,created_at timestamptz not null default now(),
 primary key(provider,event_id),
 foreign key(tenant_id,checkout_id) references public.ecommerce_checkouts(tenant_id,id) on delete restrict
);
create table public.ecommerce_entitlements (
 id uuid primary key default gen_random_uuid(),tenant_id integer not null,user_id integer not null references public.users(id) on delete restrict,
 checkout_id uuid not null,resource_type text not null check(resource_type='elearning_course'),
 terms jsonb not null check(jsonb_typeof(terms)='object'),status text not null check(status in ('active','expired','cancelled','revoked')),
 starts_at timestamptz not null default now(),expires_at timestamptz,cancel_at_period_end boolean not null default false,
 foreign key(tenant_id,checkout_id) references public.ecommerce_checkouts(tenant_id,id) on delete restrict,
 unique(tenant_id,id),unique(tenant_id,checkout_id),check(expires_at is null or expires_at>starts_at)
);
alter table public.elearning_enrollments drop constraint elearning_enrollments_access_source_check;
alter table public.elearning_enrollments add constraint elearning_enrollments_access_source_check check(access_source in ('manual','free','group','purchase'));
alter table public.elearning_access_grants drop constraint elearning_purchase_reserved;

create function public.commerce_assert_member(p_tenant_id integer,p_user_id integer,p_admin boolean default false)
returns void language plpgsql stable security definer set search_path='' as $$ begin
 if not exists(select 1 from public.tenant_memberships m join public.users u on u.id=m.user_id where m.tenant_id=p_tenant_id and m.user_id=p_user_id and m.status='active' and u.account_status='active' and(not p_admin or m.role in ('owner','admin'))) then
 raise exception using errcode='42501',message='commerce_forbidden';end if;
end $$;
create function public.elearning_catalog_eligible(p_tenant_id integer,p_course_id uuid)
returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id and status='published' and catalog_visible and access_type in ('free','paid'));
$$;
create function public.elearning_terms_cover(p_tenant_id integer,p_terms jsonb,p_course_id uuid)
returns boolean language sql stable security definer set search_path='' as $$
 select public.elearning_catalog_eligible(p_tenant_id,p_course_id) and(p_terms->>'access_scope'='all_courses' or coalesce(p_terms->'course_ids','[]') @> jsonb_build_array(p_course_id::text));
$$;
create function public.elearning_entitlement_for(p_tenant_id integer,p_user_id integer,p_course_id uuid)
returns jsonb language sql stable security definer set search_path='' as $$
 select jsonb_build_object('id',id,'name',terms->>'name') from public.ecommerce_entitlements
 where tenant_id=p_tenant_id and user_id=p_user_id and resource_type='elearning_course' and status='active' and starts_at<=now() and(expires_at is null or expires_at>now())
 and public.elearning_terms_cover(p_tenant_id,terms,p_course_id) order by expires_at nulls first,id limit 1;
$$;
-- Additive resolver: a Purchase grant is valid only while at least one confirmed
-- entitlement covers this exact user's eligible course. Never delete history.
create or replace function public.elearning_valid_grants(p_tenant_id integer,p_enrollment_id uuid)
returns jsonb language sql stable security definer set search_path='' as $$
 select coalesce(jsonb_agg(jsonb_build_object('id',a.id,'type',a.grant_type,'group_id',a.source_group_id,'group_name',g.name,'created_at',a.created_at) order by a.grant_type,g.name,a.id),'[]')
 from public.elearning_access_grants a join public.elearning_enrollments e on(e.tenant_id,e.id)=(a.tenant_id,a.enrollment_id)
 join public.elearning_learners l on(l.tenant_id,l.id)=(e.tenant_id,e.learner_id)
 left join public.elearning_groups g on(g.tenant_id,g.id)=(a.tenant_id,a.source_group_id)
 where a.tenant_id=p_tenant_id and a.enrollment_id=p_enrollment_id and a.revoked_at is null
 and(a.grant_type<>'purchase' or public.elearning_entitlement_for(a.tenant_id,l.user_id,a.course_id) is not null)
 and(a.grant_type<>'group' or(g.status='active' and exists(select 1 from public.elearning_group_members m where m.tenant_id=a.tenant_id and m.group_id=a.source_group_id and m.user_id=l.user_id and m.removed_at is null)
 and exists(select 1 from public.elearning_group_courses c where c.tenant_id=a.tenant_id and c.group_id=a.source_group_id and c.course_id=a.course_id and c.removed_at is null)));
$$;

create function public.get_elearning_offerings(p_tenant_id integer,p_user_id integer,p_admin boolean default false)
returns jsonb language plpgsql stable security definer set search_path='' as $$ begin
 perform public.commerce_assert_member(p_tenant_id,p_user_id,p_admin);
 return jsonb_build_object('plans',coalesce((select jsonb_agg(jsonb_build_object('id',o.id,'revision',o.revision,'name',p.translations->'en'->>'name','description',p.translations->'en'->>'description','status',p.status,'amount',p.price,'currency',p.currency,'billing_type',o.billing_type,'access_scope',o.access_scope,'course_ids',coalesce((select jsonb_agg(course_id order by course_id) from public.elearning_offering_courses where tenant_id=p_tenant_id and offering_id=o.id),'[]')) order by p.created_at,o.id) from public.ecommerce_offerings o join public.ecommerce_products p on(p.tenant_id,p.id)=(o.tenant_id,o.product_id) where o.tenant_id=p_tenant_id and(p_admin or p.status='active')),'[]'));
end $$;
create function public.manage_elearning_offering(p_tenant_id integer,p_user_id integer,p_id uuid,p_revision integer,p_details jsonb)
returns jsonb language plpgsql security definer set search_path='' as $$
declare o public.ecommerce_offerings%rowtype; pid uuid;cid uuid;scope text:=p_details->>'access_scope';ids jsonb:=coalesce(p_details->'course_ids','[]');
begin
 perform public.commerce_assert_member(p_tenant_id,p_user_id,true);
 perform pg_advisory_xact_lock(125,p_tenant_id);
 if p_details is null or not p_details ?& array['billing_type','access_scope','status','name','amount','currency'] or jsonb_path_exists(p_details,'$.* ? (@ == null)') or p_details->>'billing_type' not in ('one_time','monthly','yearly') or scope not in ('single_course','selected_courses','all_courses') or p_details->>'status' not in ('draft','active','archived') or length(btrim(coalesce(p_details->>'name',''))) not between 1 and 120 or length(coalesce(p_details->>'description',''))>4000 or p_details->>'currency' !~ '^[A-Z]{3}$' or (p_details->>'amount')::numeric<=0 or (p_details->>'amount')::numeric<>round((p_details->>'amount')::numeric,2) or jsonb_typeof(ids)<>'array' then raise exception using errcode='22023',message='commerce_plan_invalid';end if;
 if(scope='single_course' and jsonb_array_length(ids)<>1) or(scope='selected_courses' and jsonb_array_length(ids)<1) or(scope='all_courses' and jsonb_array_length(ids)<>0) then raise exception using errcode='22023',message='commerce_scope_invalid';end if;
 for cid in select value::uuid from jsonb_array_elements_text(ids) loop
 if not exists(select 1 from public.elearning_courses where tenant_id=p_tenant_id and id=cid and status<>'archived' and catalog_visible and access_type<>'private') then raise exception using errcode='22023',message='commerce_course_invalid';end if;end loop;
 if p_id is null then
 pid:=gen_random_uuid();
 insert into public.ecommerce_products(id,tenant_id,sku,slug,translations,status,product_type,price,currency,track_inventory,requires_shipping,taxable,created_by)
 values(pid,p_tenant_id,'learning-'||pid,'learning-'||pid,jsonb_build_object('en',jsonb_build_object('name',p_details->>'name','description',coalesce(p_details->>'description',''))),p_details->>'status','digital',(p_details->>'amount')::numeric,p_details->>'currency',false,false,false,p_user_id);
 insert into public.ecommerce_offerings(tenant_id,product_id,billing_type,resource_type,access_scope) values(p_tenant_id,pid,p_details->>'billing_type','elearning_course',scope) returning * into o;
 else
 select * into o from public.ecommerce_offerings where tenant_id=p_tenant_id and id=p_id for update;
 if not found then raise exception using errcode='P0002',message='commerce_plan_not_found';end if;
 if o.revision<>p_revision then raise exception using errcode='40001',message='commerce_revision_conflict';end if;
 update public.ecommerce_products set translations=jsonb_build_object('en',jsonb_build_object('name',p_details->>'name','description',coalesce(p_details->>'description',''))),status=p_details->>'status',price=(p_details->>'amount')::numeric,currency=p_details->>'currency' where tenant_id=p_tenant_id and id=o.product_id;
 update public.ecommerce_offerings set billing_type=p_details->>'billing_type',access_scope=scope,revision=revision+1 where id=o.id;
 delete from public.elearning_offering_courses where tenant_id=p_tenant_id and offering_id=o.id;
 end if;
 insert into public.elearning_offering_courses select p_tenant_id,o.id,value::uuid from jsonb_array_elements_text(ids) on conflict do nothing;
 return public.get_elearning_offerings(p_tenant_id,p_user_id,true)||jsonb_build_object('saved_plan_id',o.id);
end $$;

create function public.elearning_course_cta(p_tenant_id integer,p_user_id integer,p_course_id uuid)
returns jsonb language plpgsql stable security definer set search_path='' as $$
declare c public.elearning_courses%rowtype;e public.elearning_enrollments%rowtype;r public.elearning_learners%rowtype;ent jsonb;
begin
 select * into c from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id and status='published';
 if not found then return jsonb_build_object('action','unavailable');end if;
 select * into r from public.elearning_learners where tenant_id=p_tenant_id and user_id=p_user_id;
 select * into e from public.elearning_enrollments where tenant_id=p_tenant_id and course_id=p_course_id and learner_id=r.id;
 if r.status='archived' or e.status='suspended' then return jsonb_build_object('action','suspended');end if;
 if public.elearning_enrollment_has_access(p_tenant_id,e.id) then return jsonb_build_object('action','continue','enrollment_id',e.id);end if;
 if not public.elearning_catalog_eligible(p_tenant_id,p_course_id) then return jsonb_build_object('action','unavailable');end if;
 if c.access_type='free' then return jsonb_build_object('action','enroll_free');end if;
 ent:=public.elearning_entitlement_for(p_tenant_id,p_user_id,p_course_id);
 if ent is not null then return jsonb_build_object('action','enroll','included_in',ent);end if;
 return jsonb_build_object('action','buy');
end $$;
create function public.get_elearning_catalog(p_tenant_id integer,p_user_id integer)
returns jsonb language plpgsql stable security definer set search_path='' as $$ begin
 perform public.commerce_assert_member(p_tenant_id,p_user_id);
 return jsonb_build_object('courses',coalesce((select jsonb_agg(jsonb_build_object('id',c.id,'name',c.name,'description',c.description,'cover_asset',c.cover_asset,'access_type',c.access_type,'cta',public.elearning_course_cta(p_tenant_id,p_user_id,c.id),'plans',coalesce((select jsonb_agg(o.id) from public.ecommerce_offerings o join public.ecommerce_products p on(p.tenant_id,p.id)=(o.tenant_id,o.product_id) where o.tenant_id=p_tenant_id and p.status='active' and(o.access_scope='all_courses' or exists(select 1 from public.elearning_offering_courses oc where oc.tenant_id=o.tenant_id and oc.offering_id=o.id and oc.course_id=c.id))),'[]')) order by c.name,c.id) from public.elearning_courses c where c.tenant_id=p_tenant_id and public.elearning_catalog_eligible(p_tenant_id,c.id)),'[]'));
end $$;
create function public.enroll_elearning_catalog(p_tenant_id integer,p_user_id integer,p_course_id uuid)
returns jsonb language plpgsql security definer set search_path='' as $$
declare c public.elearning_courses%rowtype;r public.elearning_learners%rowtype;e public.elearning_enrollments%rowtype;src text;u public.users%rowtype;
begin
 perform public.commerce_assert_member(p_tenant_id,p_user_id);
 perform pg_advisory_xact_lock(125,p_tenant_id);
 select * into c from public.elearning_courses where tenant_id=p_tenant_id and id=p_course_id for update;
 if not found or not public.elearning_catalog_eligible(p_tenant_id,p_course_id) then raise exception using errcode='P0002',message='commerce_course_unavailable';end if;
 select * into u from public.users where id=p_user_id;
 select * into r from public.elearning_learners where tenant_id=p_tenant_id and(user_id=p_user_id or email=lower(btrim(u.email))) order by user_id nulls last limit 1 for update;
 if r.id is not null and(r.status<>'active' or(r.user_id is not null and r.user_id<>p_user_id)) then raise exception using errcode='42501',message='commerce_profile_unavailable';end if;
 if r.id is not null and r.user_id is null then update public.elearning_learners set user_id=p_user_id where id=r.id;end if;
 if r.id is null then
 insert into public.elearning_learners(tenant_id,user_id,name,email,created_by) values(p_tenant_id,p_user_id,coalesce(nullif(btrim(concat_ws(' ',u.first_name,u.last_name)),''),'Learner'),lower(btrim(u.email)),p_user_id) returning * into r;
 end if;
 select * into e from public.elearning_enrollments where tenant_id=p_tenant_id and course_id=p_course_id and learner_id=r.id;
 if r.status<>'active' or e.status='suspended' then raise exception using errcode='42501',message='commerce_access_suspended';end if;
 if public.elearning_enrollment_has_access(p_tenant_id,e.id) then return jsonb_build_object('enrollment_id',e.id);end if;
 src:=case when c.access_type='free' then 'free' else 'purchase' end;
 if src='purchase' and public.elearning_entitlement_for(p_tenant_id,p_user_id,p_course_id) is null then raise exception using errcode='42501',message='commerce_entitlement_required';end if;
 insert into public.elearning_enrollments(tenant_id,course_id,learner_id,access_source,created_by) values(p_tenant_id,p_course_id,r.id,src,p_user_id)
 on conflict(tenant_id,course_id,learner_id) do update set status='active' returning * into e;
 insert into public.elearning_access_grants(tenant_id,course_id,enrollment_id,grant_type) values(p_tenant_id,p_course_id,e.id,src)
 on conflict(tenant_id,enrollment_id,grant_type) where source_group_id is null do update set revoked_at=null;
 return jsonb_build_object('enrollment_id',e.id);
end $$;

create function public.create_commerce_learning_checkout(p_tenant_id integer,p_user_id integer,p_offering_id uuid,p_course_id uuid,p_idempotency_key uuid,p_provider text)
returns jsonb language plpgsql security definer set search_path='' as $$
declare o public.ecommerce_offerings%rowtype;p public.ecommerce_products%rowtype;ch public.ecommerce_checkouts%rowtype;u public.users%rowtype;terms jsonb;orderid uuid:=gen_random_uuid();
begin
 perform public.commerce_assert_member(p_tenant_id,p_user_id);
 perform pg_advisory_xact_lock(125,p_tenant_id);
 if p_provider is null or p_provider='' or p_idempotency_key is null then raise exception using errcode='22023',message='commerce_checkout_invalid';end if;
 select * into ch from public.ecommerce_checkouts where tenant_id=p_tenant_id and user_id=p_user_id and idempotency_key=p_idempotency_key;
 if found then
 if ch.offering_id<>p_offering_id or ch.requested_resource_id is distinct from p_course_id or ch.provider<>p_provider then raise exception using errcode='40001',message='commerce_idempotency_conflict';end if;
 return jsonb_build_object('checkout',to_jsonb(ch));end if;
 select * into o from public.ecommerce_offerings where tenant_id=p_tenant_id and id=p_offering_id for update;
 if not found then raise exception using errcode='P0002',message='commerce_plan_not_found';end if;
 select * into p from public.ecommerce_products where tenant_id=p_tenant_id and id=o.product_id for update;
 if p.status<>'active' then raise exception using errcode='42501',message='commerce_plan_inactive';end if;
 terms:=jsonb_build_object('name',p.translations->'en'->>'name','amount',p.price,'currency',p.currency,'billing_type',o.billing_type,'access_scope',o.access_scope,'offering_id',o.id,'product_id',p.id,'revision',o.revision,'catalog_policy','current_and_future_eligible','course_ids',coalesce((select jsonb_agg(course_id order by course_id) from public.elearning_offering_courses where tenant_id=p_tenant_id and offering_id=o.id),'[]'));
 if p_course_id is not null then
 if not public.elearning_terms_cover(p_tenant_id,terms,p_course_id) then raise exception using errcode='42501',message='commerce_course_not_covered';end if;
 if public.elearning_course_cta(p_tenant_id,p_user_id,p_course_id)->>'action'='suspended' then raise exception using errcode='42501',message='commerce_access_suspended';end if;
 end if;
 select * into u from public.users where id=p_user_id;
 insert into public.ecommerce_orders(id,tenant_id,order_number,payment_method,currency,subtotal,total,customer_name,customer_email,customer_phone,address_line_1,city,country,idempotency_key_hash,request_hash)
 values(orderid,p_tenant_id,'learning-'||orderid,'provider',p.currency,p.price,p.price,coalesce(nullif(btrim(concat_ws(' ',u.first_name,u.last_name)),''),'Learner'),u.email,'','','','',encode(extensions.digest(p_user_id||':'||p_idempotency_key,'sha256'),'hex'),encode(extensions.digest(terms::text||coalesce(p_course_id::text,''),'sha256'),'hex'));
 insert into public.ecommerce_order_items(tenant_id,order_id,product_id,sku,product_slug,product_name,quantity,unit_price,list_unit_price,line_total,product_snapshot) values(p_tenant_id,orderid,p.id,p.sku,p.slug,terms->>'name',1,p.price,p.price,p.price,terms);
 insert into public.ecommerce_checkouts(tenant_id,user_id,offering_id,order_id,provider,idempotency_key,requested_resource_id,terms) values(p_tenant_id,p_user_id,o.id,orderid,p_provider,p_idempotency_key,p_course_id,terms) returning * into ch;
 return jsonb_build_object('checkout',to_jsonb(ch));
end $$;
create function public.get_commerce_learning_account(p_tenant_id integer,p_user_id integer)
returns jsonb language plpgsql stable security definer set search_path='' as $$ begin
 perform public.commerce_assert_member(p_tenant_id,p_user_id);
 return jsonb_build_object('checkouts',coalesce((select jsonb_agg(to_jsonb(c) order by c.created_at desc) from public.ecommerce_checkouts c where tenant_id=p_tenant_id and user_id=p_user_id),'[]'),
 'entitlements',coalesce((select jsonb_agg(to_jsonb(e)||jsonb_build_object('effective_status',case when status='active' and expires_at<=now() then 'expired' else status end) order by starts_at desc) from public.ecommerce_entitlements e where tenant_id=p_tenant_id and user_id=p_user_id),'[]'));
end $$;

-- Called only after a provider adapter has authenticated authoritative events.
-- Local development adapter is guarded in Python, never accepted as a redirect.
create function public.apply_commerce_payment_event(p_tenant_id integer,p_checkout_id uuid,p_provider text,p_event_id text,p_transaction_id text,p_sequence bigint,p_state text,p_amount numeric,p_currency text,p_period_end timestamptz default null,p_cancel_at_period_end boolean default false)
returns jsonb language plpgsql security definer set search_path='' as $$
declare ch public.ecommerce_checkouts%rowtype;ev public.ecommerce_payment_events%rowtype;expiry timestamptz;eid uuid;
begin
 perform pg_advisory_xact_lock(125,p_tenant_id);
 select * into ch from public.ecommerce_checkouts where tenant_id=p_tenant_id and id=p_checkout_id for update;
 if not found or ch.provider<>p_provider then raise exception using errcode='P0002',message='commerce_checkout_not_found';end if;
 if p_event_id is null or length(p_event_id) not between 1 and 200 or p_transaction_id is null or length(p_transaction_id) not between 1 and 200 or p_sequence is null or p_sequence<=0 or p_state is null or p_state not in ('paid','failed','active','expired','cancelled','refunded','reversed') or p_amount is null or p_amount<>(ch.terms->>'amount')::numeric or p_currency is distinct from ch.terms->>'currency' or(ch.provider_transaction_id is not null and ch.provider_transaction_id<>p_transaction_id) then raise exception using errcode='22023',message='commerce_payment_mismatch';end if;
 select * into ev from public.ecommerce_payment_events where provider=p_provider and event_id=p_event_id;
 if found then
 if ev.tenant_id<>p_tenant_id or ev.checkout_id<>p_checkout_id or ev.transaction_id<>p_transaction_id or ev.sequence<>p_sequence or ev.state<>p_state or ev.amount<>p_amount or ev.currency<>p_currency or ev.period_end is distinct from p_period_end or ev.cancel_at_period_end<>p_cancel_at_period_end then raise exception using errcode='40001',message='commerce_event_conflict';end if;
 return jsonb_build_object('duplicate',true,'checkout_id',ch.id);end if;
 if ch.terms->>'billing_type'='one_time' and(p_period_end is not null or p_cancel_at_period_end or p_state in ('active','expired','cancelled')) then raise exception using errcode='22023',message='commerce_lifetime_terms_invalid';end if;
 if ch.state in ('refunded','reversed') and p_state not in ('refunded','reversed') then raise exception using errcode='42501',message='commerce_payment_reversed';end if;
 if ch.terms->>'billing_type'<>'one_time' and p_state in ('paid','active') and(p_period_end is null or p_period_end<=now()) then raise exception using errcode='22023',message='commerce_period_invalid';end if;
 if p_state in ('refunded','reversed','expired','cancelled','active') and ch.state<>'paid' then raise exception using errcode='42501',message='commerce_initial_payment_required';end if;
 insert into public.ecommerce_payment_events values(p_provider,p_event_id,p_tenant_id,ch.id,p_transaction_id,p_sequence,p_state,p_amount,p_currency,p_period_end,p_cancel_at_period_end,now());
 if p_sequence<=ch.event_sequence then return jsonb_build_object('stale',true,'checkout_id',ch.id);end if;
 update public.ecommerce_checkouts set event_sequence=p_sequence,provider_transaction_id=p_transaction_id,state=case when p_state in ('active','expired','cancelled') then 'paid' else p_state end where id=ch.id;
 if p_state='failed' and ch.state='paid' then raise exception using errcode='42501',message='commerce_paid_cannot_fail';end if;
if p_state='failed' then return jsonb_build_object('checkout_id',ch.id,'state','failed');end if;
 if p_state in ('paid','active') then
 expiry:=case when ch.terms->>'billing_type'='one_time' then null else p_period_end end;
 insert into public.ecommerce_entitlements(tenant_id,user_id,checkout_id,resource_type,terms,status,expires_at,cancel_at_period_end) values(p_tenant_id,ch.user_id,ch.id,'elearning_course',ch.terms,'active',expiry,p_cancel_at_period_end)
 on conflict(tenant_id,checkout_id) do update set status='active',expires_at=excluded.expires_at,cancel_at_period_end=excluded.cancel_at_period_end returning id into eid;
 update public.ecommerce_orders set payment_status='paid',status='confirmed' where tenant_id=p_tenant_id and id=ch.order_id;
 -- Payment may outlive publication or arrive during suspension. Preserve the
 -- entitlement, but do not let fulfillment override these access restrictions.
 if ch.requested_resource_id is not null and public.elearning_terms_cover(p_tenant_id,ch.terms,ch.requested_resource_id) and public.elearning_course_cta(p_tenant_id,ch.user_id,ch.requested_resource_id)->>'action'<>'suspended' then
 perform public.enroll_elearning_catalog(p_tenant_id,ch.user_id,ch.requested_resource_id);end if;
 else
 update public.ecommerce_entitlements set status=case when p_state in ('refunded','reversed') then 'revoked' else p_state end,cancel_at_period_end=false where tenant_id=p_tenant_id and checkout_id=ch.id;
 if p_state in ('refunded','reversed') then update public.ecommerce_orders set payment_status='refunded' where tenant_id=p_tenant_id and id=ch.order_id;end if;
 end if;
 return jsonb_build_object('checkout_id',ch.id,'entitlement_id',eid,'state',p_state);
end $$;

do $$ declare tbl text;f record;begin
 foreach tbl in array array['ecommerce_offerings','elearning_offering_courses','ecommerce_checkouts','ecommerce_payment_events','ecommerce_entitlements'] loop
 execute 'alter table public.'||tbl||' enable row level security';
 execute 'revoke all on public.'||tbl||' from public,anon,authenticated,service_role';end loop;
 for f in select p.oid::regprocedure signature from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname in('commerce_assert_member','elearning_catalog_eligible','elearning_terms_cover','elearning_entitlement_for','get_elearning_offerings','manage_elearning_offering','elearning_course_cta','get_elearning_catalog','enroll_elearning_catalog','create_commerce_learning_checkout','get_commerce_learning_account','apply_commerce_payment_event') loop
 execute 'revoke all on function '||f.signature||' from public,anon,authenticated,service_role';end loop;
 grant execute on function public.get_elearning_offerings(integer,integer,boolean),public.manage_elearning_offering(integer,integer,uuid,integer,jsonb),public.get_elearning_catalog(integer,integer),public.enroll_elearning_catalog(integer,integer,uuid),public.create_commerce_learning_checkout(integer,integer,uuid,uuid,uuid,text),public.get_commerce_learning_account(integer,integer),public.apply_commerce_payment_event(integer,uuid,text,text,text,bigint,text,numeric,text,timestamptz,boolean) to service_role;
end $$;
notify pgrst,'reload schema';
commit;
