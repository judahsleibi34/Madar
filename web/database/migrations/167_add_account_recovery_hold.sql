begin;
-- Serialize before taking any relation lock: later RLS installation requires EX.
select pg_advisory_xact_lock(167, 167);
do $$declare v_schema_version public.application_schema_state.schema_version%type;begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key='core' for update;
 if v_schema_version is null then raise exception 'migration_167_schema_state_missing';end if;
 if v_schema_version<>166 then raise exception 'migration_167_expected_schema_166';end if;
 if exists(select 1 from public.data_deletion_requests where state not in ('completed','completed_with_retained_records','cancelled_before_execution'))
 or exists(select 1 from public.users where account_status='deletion_pending') then raise exception 'migration_167_requires_reconciled_deletion_backlog';end if;
end;$$;

-- Unpublished candidate revised for TWO owner-approved actions. No publication
-- or customer admission follows from this service-only implementation.
create table public.account_lifecycles167(
 id uuid primary key references public.data_deletion_requests(id) on delete restrict,
 user_id integer references public.users(id) on delete set null,
 subject_id integer,tenant_id integer,auth_id uuid,email_fingerprint text,
 action text not null check(action in ('deactivate','delete')),
 state text not null check(state in ('recovery_pending','erasure_pending','processing','retry_pending','blocked','reactivated','completed')),
 requested_at timestamptz not null,recovery_deadline timestamptz,eligible_at timestamptz not null,
 deactivated_at timestamptz,delete_requested_at timestamptz,
 restore_epoch bigint,
 previous_status text not null,
 storage_binding jsonb not null check(jsonb_typeof(storage_binding)='object' and octet_length(storage_binding::text)<=4096),
 project_ids uuid[] not null default '{}',
 lease_owner text,lease_token uuid,generation bigint not null default 0,lease_until timestamptz,
 irreversible_at timestamptz,database_released boolean not null default false,subject_removed boolean not null default false,
 error_code text,completed_at timestamptz,reactivated_at timestamptz,
 check((action='delete' and recovery_deadline is null) or (action='deactivate' and recovery_deadline=requested_at+interval '2160 hours')),
 check(state<>'processing' or (lease_owner is not null and lease_token is not null and lease_until is not null)),
 check(state<>'completed' or (subject_id is null and auth_id is null and user_id is null and completed_at is not null))
);
create unique index account_lifecycle_active167 on public.account_lifecycles167(subject_id) where state not in ('completed','reactivated');
create table public.account_lifecycle_resources167(
 id bigint generated always as identity primary key,request_id uuid not null references public.account_lifecycles167(id) on delete restrict,
 kind text not null check(kind in ('storage','report','file','auth')),
 resource_key text not null,identity jsonb not null check(octet_length(identity::text)<=65536),
 state text not null default 'pending' check(state in ('pending','intent','verified','uncertain')),
 unique(request_id,kind,resource_key)
);
alter table public.account_lifecycles167 enable row level security;
alter table public.account_lifecycle_resources167 enable row level security;
revoke all on public.account_lifecycles167,public.account_lifecycle_resources167 from public,anon,authenticated,service_role;
grant select on public.account_lifecycles167,public.account_lifecycle_resources167 to service_role;

-- Shared platform state, with no subject/user/request identifiers. The live
-- filesystem floor is published first; committed epoch advances atomically
-- with verified completion. Old snapshots cannot be admitted after erasure.
create table public.account_restore_state167(singleton boolean primary key default true check(singleton),allocated_epoch bigint not null default 0,committed_epoch bigint not null default 0,check(committed_epoch<=allocated_epoch));
insert into public.account_restore_state167 default values;
alter table public.account_restore_state167 enable row level security;
revoke all on public.account_restore_state167 from public,anon,authenticated,service_role;
create function public.account_restore_boundary167() returns jsonb language sql stable security definer set search_path='' as $$select jsonb_build_object('committed_epoch',committed_epoch,'erasure_in_progress',exists(select 1 from public.account_lifecycles167 where irreversible_at is not null)) from public.account_restore_state167 where singleton$$;

create function public.account_lifecycle_capability167() returns jsonb language sql stable security definer set search_path='' as $$
 select case when (select schema_version from public.application_schema_state where contract_key='core')=167 then
 '{"protocol":3,"deactivate_recovery_hours":2160,"delete_recovery_hours":0,"admission":{"deactivate":false,"delete":false},"completion_boundary":"server_controlled"}'::jsonb else '{}'::jsonb end
$$;
create function public.account_recovery_capability167() returns jsonb language sql stable security definer set search_path='' as $$select '{}'::jsonb$$;

-- Require an explicitly known Auth session topology; never infer that a ban
-- revokes sessions. Unsupported managed Auth contracts fail before enrollment.
create function public.account_auth_contract167() returns boolean language plpgsql stable security definer set search_path='' as $$
begin
 return to_regclass('auth.sessions') is not null and to_regclass('auth.refresh_tokens') is not null
 and exists(select 1 from pg_catalog.pg_attribute where attrelid='auth.users'::regclass and attname='banned_until' and not attisdropped)
 and exists(select 1 from pg_catalog.pg_attribute where attrelid=to_regclass('auth.refresh_tokens') and attname='user_id' and not attisdropped)
 and exists(select 1 from pg_catalog.pg_constraint c where c.conrelid=to_regclass('auth.refresh_tokens') and c.confrelid=to_regclass('auth.sessions') and c.contype='f' and c.confdeltype='c');
end;$$;

alter function public.create_data_deletion_request(text,integer,integer,integer,timestamptz) rename to create_data_deletion_request160;
alter function public.cancel_data_deletion_request_v2(uuid) rename to cancel_data_deletion_request160;
revoke all on function public.create_data_deletion_request160(text,integer,integer,integer,timestamptz),public.cancel_data_deletion_request160(uuid),
 public.claim_data_deletion_requests_v2(text,integer,integer),public.run_data_deletion_local_step_v2(uuid,text,bigint,integer,bigint,integer),
 public.transition_data_deletion_v2(uuid,text,bigint,integer,text,bigint,integer,jsonb),
 public.data_deletion_effect_v2(uuid,text,bigint,integer,bigint,integer,text,text,text,text) from public,anon,authenticated,service_role;

create function public.create_data_deletion_request(p_request_type text,p_target_user_id integer,p_target_tenant_id integer,p_requested_by_user_id integer,p_retention_until timestamptz default null)
returns public.data_deletion_requests language plpgsql security definer set search_path='' as $$begin
 if p_request_type='tenant' then raise exception 'tenant_erasure_policy_unapproved';end if;
 raise exception 'explicit_account_action_required';
end;$$;
create function public.cancel_data_deletion_request_v2(p_request_id uuid) returns public.data_deletion_requests language plpgsql security definer set search_path='' as $$begin raise exception 'explicit_account_reactivation_required';end;$$;

create function public.fence_account_jobs167(p_user_id integer,p_deadline timestamptz)
returns void language plpgsql security definer set search_path='' as $$
begin
  update public.admin_account_access_sessions set ended_at=coalesce(ended_at,clock_timestamp()),ended_reason='account_lifecycle_frozen' where (admin_user_id=p_user_id or target_user_id=p_user_id) and ended_at is null;
  update public.admin_account_access_requests set revoked_at=coalesce(revoked_at,clock_timestamp()),revoked_reason='account_lifecycle_frozen',code_hash=null where (admin_user_id=p_user_id or target_user_id=p_user_id) and revoked_at is null;
  update public.password_reset_requests set status='revoked' where user_id=p_user_id and status in ('pending','processing');
  update public.calendar_task_sync_jobs j set status='superseded',lease_owner=null,leased_at=null,
   completed_at=clock_timestamp(),last_error_code='account_lifecycle_frozen'
   from public.calendar_sync_connections c where c.id=j.connection_id and c.user_id=p_user_id
    and j.status in ('pending','processing','failed');
  update public.calendar_connection_sync_jobs j set status='failed',attempts=max_attempts,
   lease_owner=null,leased_at=null,completed_at=clock_timestamp(),last_error_code='account_lifecycle_frozen'
   from public.calendar_sync_connections c where c.id=j.connection_id and c.user_id=p_user_id
    and j.status in ('pending','processing','failed');
  -- Called under the enrollment/user lock BEFORE publishing the account freeze.
  -- Preserve ambiguous ingestion identities; never retry an accepted effect just
  -- because its predecessor can no longer acknowledge the outcome.
  update public.data_source_ingestion_runs set lease_token=gen_random_uuid(),lease_owner='account-recovery-hold',
    lease_expires_at=p_deadline,reconciliation_state='ambiguous',reconciliation_code='account_recovery_hold'
    where initiated_by_user_id=p_user_id and status='processing';
  update public.data_source_ingestion_runs set status='failed',failure_code='account_recovery_hold',completed_at=clock_timestamp()
    where initiated_by_user_id=p_user_id and status='pending';
  update public.data_source_sync_attempts a set status='fenced',completed_at=clock_timestamp(),error_category='account_recovery_hold'
    from public.data_sources s where a.source_id=s.id and s.creator_user_id=p_user_id and a.status='leased';
  update public.data_source_sync_schedules q set status=case when q.enabled then 'idle' else 'disabled' end,
    lease_token=null,lease_owner=null,lease_expires_at=null,ingestion_run_id=null,fence=q.fence+1
    from public.data_sources s where q.source_id=s.id and s.creator_user_id=p_user_id and q.status='leased';
  update public.data_source_webhook_events set status='dead_letter',processed_at=clock_timestamp(),error_category='account_recovery_hold',
    lease_token=null,lease_owner=null,lease_expires_at=null,lease_fence=lease_fence+1
    where actor_user_id=p_user_id and status in ('pending','leased','retry');
  update public.bi_report_runs set status='cancelled',error_code='account_recovery_hold',completed_at=clock_timestamp(),
    lease_token=null,lease_owner=null,lease_expires_at=null,lease_fence=lease_fence+1
    where creator_user_id=p_user_id and status in ('queued','running','retry_pending');
  update public.bi_report_deliveries set status='revoked',last_error_code='account_recovery_hold',
    lease_token=null,lease_owner=null,lease_expires_at=null,lease_fence=lease_fence+1
    where (owner_user_id=p_user_id or recipient_user_id=p_user_id) and status in ('pending','processing','retry_pending');
  update public.bi_report_cleanup_jobs set status='cancelled',last_error_code='account_recovery_hold',
    lease_token=null,lease_owner=null,lease_expires_at=null,lease_fence=lease_fence+1
    where owner_user_id=p_user_id and status in ('pending','processing','retry_pending');
update public.notification_outbox set status='dead',last_error_code='account_lifecycle_frozen',claim_generation=claim_generation+1,processing_started_at=null,processing_lease_until=null where (user_id=p_user_id or payload->>'event_id' in (select e.id::text from public.notification_events e join public.bi_report_runs r on e.source_type='bi_report' and e.source_id=r.id::text where r.creator_user_id=p_user_id)) and status in ('pending','processing','failed');
 update public.notification_deliveries set status='dead',last_error_code='account_lifecycle_frozen',claim_generation=claim_generation+1,processing_started_at=null,processing_lease_until=null,dead_at=clock_timestamp() where (user_id=p_user_id or event_id in (select e.id from public.notification_events e join public.bi_report_runs r on e.source_type='bi_report' and e.source_id=r.id::text where r.creator_user_id=p_user_id)) and status in ('pending','processing');
 end;$$;
create function public.create_account_action167(p_user_id integer,p_actor_id integer,p_action text,p_storage_binding jsonb)
returns public.account_lifecycles167 language plpgsql security definer set search_path='' set timezone='UTC' as $$
declare h public.account_lifecycles167;r public.data_deletion_requests;u public.users;at_time timestamptz;deadline timestamptz;
begin
 if public.account_lifecycle_capability167()->>'protocol' is distinct from '3' then raise exception 'account_lifecycle_schema_unsupported';end if;
 if p_action not in ('deactivate','delete') or p_action is null then raise exception 'explicit_account_action_required';end if;
 if jsonb_typeof(p_storage_binding) is distinct from 'object' or not(p_storage_binding ? 'uploads' and p_storage_binding ? 'charts') then raise exception 'account_storage_binding_required';end if;
 if not public.account_auth_contract167() then raise exception 'account_auth_session_contract_unsupported';end if;
 perform pg_advisory_xact_lock(hashtextextended('data-deletion-enrollment-150',0));
 select * into u from public.users where id=p_user_id for update;
 if not found then raise exception 'deletion_target_not_found';end if;
 if p_storage_binding ? 'identity_sha256' and p_storage_binding->>'identity_sha256' is distinct from encode(sha256(convert_to(lower(btrim(u.email)),'UTF8')),'hex') then raise exception 'account_identity_canonicalization_required';end if;
 if p_actor_id is distinct from p_user_id and not exists(select 1 from public.users where id=p_actor_id and user_type='admin' and account_status='active') then raise exception 'deletion_request_unauthorized';end if;
 select * into h from public.account_lifecycles167 where subject_id=p_user_id and state not in ('completed','reactivated') for update;
 if found then
   if p_action='deactivate' and h.action='delete' then raise exception 'direct_deletion_not_recoverable';end if;
   if p_action='delete' and h.action='deactivate' then
     update public.account_lifecycles167 set action='delete',delete_requested_at=clock_timestamp(),recovery_deadline=null,eligible_at=clock_timestamp(),state=case when state='processing' then state else 'erasure_pending' end where id=h.id returning * into h;
     update public.data_deletion_requests set state='pending',retention_until=null,retry_after=null where id=h.id;
   end if;
   return h;
 end if;
 at_time:=clock_timestamp();deadline:=case when p_action='deactivate' then at_time+interval '2160 hours' else null end;
 perform public.fence_account_jobs167(p_user_id,coalesce(deadline,at_time));
 r:=public.create_data_deletion_request160('user',p_user_id,null,p_actor_id,deadline);
 insert into public.account_lifecycles167(id,user_id,subject_id,tenant_id,auth_id,action,state,requested_at,recovery_deadline,eligible_at,previous_status,storage_binding,deactivated_at,delete_requested_at,email_fingerprint)
 values(r.id,u.id,u.id,u.tenant_id,u.auth_id,p_action,case when p_action='deactivate' then 'recovery_pending' else 'erasure_pending' end,at_time,deadline,coalesce(deadline,at_time),u.account_status,p_storage_binding,case when p_action='deactivate' then at_time end,case when p_action='delete' then at_time end,encode(sha256(convert_to(lower(btrim(u.email)),'UTF8')),'hex')) returning * into h;
 -- Auth-side session insertion is fenced below. Both sessions and refresh
 -- tokens are revoked transactionally, including JWTs still cryptographically valid.
 execute 'delete from auth.refresh_tokens where user_id::text=$1::text' using u.auth_id;
 execute 'delete from auth.sessions where user_id=$1' using u.auth_id;
 execute 'update auth.users set banned_until=clock_timestamp()+interval ''100 years'' where id=$1' using u.auth_id;
 return h;
end;$$;

create function public.reactivate_account167(p_request_id uuid,p_actor_id integer)
returns public.account_lifecycles167 language plpgsql security definer set search_path='' as $$
declare h public.account_lifecycles167;
begin
 if public.account_lifecycle_capability167()->>'protocol' is distinct from '3' then raise exception 'account_lifecycle_schema_unsupported';end if;
 if not exists(select 1 from public.users where id=p_actor_id and user_type='admin' and account_status='active') then raise exception 'deletion_request_unauthorized';end if;
 perform pg_advisory_xact_lock(hashtextextended('data-deletion-enrollment-150',0));
 select * into h from public.account_lifecycles167 where id=p_request_id for update;
 if not found then raise exception 'deletion_target_not_found';end if;
 if h.action<>'deactivate' then raise exception 'direct_deletion_not_recoverable';end if;
 if h.state='reactivated' then return h;end if;
 if clock_timestamp()>=h.recovery_deadline or h.irreversible_at is not null or h.state not in ('recovery_pending','blocked','retry_pending') then raise exception 'account_reactivation_closed';end if;
 update public.account_lifecycles167 set state='reactivated',reactivated_at=clock_timestamp(),lease_token=null,lease_owner=null,lease_until=null where id=h.id returning * into h;
 perform public.cancel_data_deletion_request160(h.id);
 execute 'update auth.users set banned_until=null where id=$1' using h.auth_id;
 -- Revoked sessions are NEVER restored. A new provider login is required.
 return h;
end;$$;

create function public.claim_account_erasure167(p_owner text,p_limit integer default 1,p_lease_seconds integer default 120)
returns setof public.account_lifecycles167 language plpgsql security definer set search_path='' as $$
declare h public.account_lifecycles167;
begin
 if public.account_lifecycle_capability167()->>'protocol' is distinct from '3' then raise exception 'account_lifecycle_schema_unsupported';end if;
 if length(p_owner) not between 1 and 160 or p_limit not between 1 and 5 or p_lease_seconds not between 30 and 300 then raise exception 'account_claim_bounds';end if;
 perform pg_advisory_xact_lock(hashtextextended('data-deletion-enrollment-150',0));
 for h in select * from public.account_lifecycles167 where eligible_at<=clock_timestamp()
 and (state in ('recovery_pending','erasure_pending','retry_pending') or (state='processing' and lease_until<=clock_timestamp())) order by eligible_at,id for update skip locked limit p_limit loop
  update public.account_lifecycles167 set state='processing',lease_owner=p_owner,lease_token=gen_random_uuid(),generation=generation+1,lease_until=clock_timestamp()+make_interval(secs=>p_lease_seconds),error_code=null where id=h.id returning * into h;
  return next h;
 end loop;
end;$$;
create function public.owned_account_erasure167(p_request_id uuid,p_token uuid,p_generation bigint)
returns public.account_lifecycles167 language plpgsql security definer set search_path='' as $$
declare h public.account_lifecycles167;
begin
 if public.account_lifecycle_capability167()->>'protocol' is distinct from '3' then raise exception 'account_lifecycle_schema_unsupported';end if;
 select * into h from public.account_lifecycles167 where id=p_request_id for update;
 if not found or h.state<>'processing' or h.lease_token is distinct from p_token or h.generation is distinct from p_generation or h.lease_until<=clock_timestamp() then raise exception 'account_erasure_claim_lost';end if;
 return h;
end;$$;
create function public.erasure_scope_authorized167(p_user_id integer) returns boolean language plpgsql security definer set search_path='' as $$
declare h public.account_lifecycles167;
begin
 if nullif(current_setting('madar.erasure_request',true),'') is null then return false;end if;
 h:=public.owned_account_erasure167(current_setting('madar.erasure_request')::uuid,current_setting('madar.erasure_token')::uuid,current_setting('madar.erasure_generation')::bigint);
 return h.subject_id=p_user_id and h.irreversible_at is not null;
end;$$;

-- Phase6I: a Commerce checkout is a mixed customer/merchant record.  Its
-- customer pointer may be erased, but the merchant's order/payment ledger is
-- preserved.  Live provider checkouts remain blocked until an adapter can
-- independently remove or establish retention for provider-side customer data.
alter table public.ecommerce_checkouts alter column user_id drop not null;

create function public.account_commerce_order_owned167(p public.ecommerce_orders,p_subject integer)
returns boolean language sql stable security definer set search_path='' as $$
 select coalesce(p.customer_id=p_subject,false) or exists(
  select 1 from public.ecommerce_checkouts c
  where (c.tenant_id,c.order_id)=(p.tenant_id,p.id) and c.user_id=p_subject)
$$;

create function public.account_commerce_tables167() returns text[] language sql immutable set search_path='' as $$select array[
 'ecommerce_tags','ecommerce_categories','ecommerce_brands','ecommerce_products','ecommerce_product_tags','ecommerce_product_categories',
 'ecommerce_product_attributes','ecommerce_product_options','ecommerce_product_option_values','ecommerce_product_variants','ecommerce_variant_option_values',
 'ecommerce_service_areas','ecommerce_tenant_service_areas','ecommerce_delivery_pricing','ecommerce_inventory_movements',
 'ecommerce_orders','ecommerce_order_items','ecommerce_order_status_history','ecommerce_loyalty_accounts','ecommerce_loyalty_rules',
 'ecommerce_loyalty_entitlements','ecommerce_loyalty_transactions','ecommerce_offerings','ecommerce_checkouts','ecommerce_payment_events','ecommerce_entitlements'
]::text[]$$;

-- Preserve the ordinary append-only loyalty contract.  The only exception is
-- DELETE of the exact departing customer's ledger under a live irreversible
-- protocol3 lease. UPDATE remains forbidden and merchant rules/orders remain.
create or replace function public.reject_ecommerce_loyalty_ledger_mutation()
returns trigger language plpgsql security definer set search_path='' as $$begin
 if tg_op='DELETE' and public.erasure_scope_authorized167(old.customer_id) then return old;end if;
 raise exception using errcode='P0001',message='ecommerce_loyalty_ledger_append_only';
end $$;

-- Owner-approved permanent erasure is the ONLY exception to normal append-only
-- credential history. UPDATE is always forbidden; DELETE requires a live,
-- irreversible protocol3 scope and exact source/project ownership. GUCs alone
-- grant nothing: erasure_scope_authorized167 revalidates token/generation/lease.
create or replace function public.reject_data_source_credential_event_mutation155()
returns trigger language plpgsql security definer set search_path='' as $$
declare subject integer;
begin
 if tg_op='DELETE' then
  select s.creator_user_id into subject from public.data_sources s
   join public.builder_projects p on p.id=s.project_id and p.tenant_id=s.tenant_id
   where s.id=old.source_id and s.tenant_id=old.tenant_id and s.project_id=old.project_id
    and p.owner_user_id=s.creator_user_id;
  if subject is not null and public.erasure_scope_authorized167(subject) then return old;end if;
 end if;
 raise exception using errcode='42501',message='credential_events_are_append_only';
end;$$;

-- Learning/Academy immutable history may be removed only as a child of the
-- exact account being irreversibly erased.  Catalog versions, courses, forms,
-- opportunities and another participant's history remain immutable.
create or replace function public.guard_elearning_form_history() returns trigger language plpgsql security definer set search_path='' as $$
declare subject integer;
begin
 if tg_op='DELETE' then
  if tg_table_name='elearning_form_responses' then subject:=old.user_id;
  elsif tg_table_name='elearning_form_files' then select user_id into subject from public.elearning_form_responses where (tenant_id,id)=(old.tenant_id,old.response_id);
  end if;
  if subject is not null and public.erasure_scope_authorized167(subject) then return old;end if;
  raise exception using errcode='42501',message='form_history_immutable';
 end if;
 if tg_table_name<>'elearning_form_responses' or (to_jsonb(new)-array['read_at','owner_notes','search_text']) is distinct from (to_jsonb(old)-array['read_at','owner_notes','search_text']) then raise exception using errcode='42501',message='form_history_immutable';end if;
 return new;
end $$;

create or replace function public.elearning_immutable_completion() returns trigger language plpgsql security definer set search_path='' as $$
declare subject integer;
begin
 if tg_op='DELETE' and tg_table_name='elearning_assessment_reviews' then
  select user_id into subject from public.elearning_assessment_attempts where (tenant_id,id)=(old.tenant_id,old.attempt_id);
  if subject is not null and public.erasure_scope_authorized167(subject) then return old;end if;
 end if;
 raise exception using errcode='42501',message='elearning_completion_immutable';
end $$;

create or replace function public.guard_learning_form_decisions144() returns trigger language plpgsql security definer set search_path='' as $$
declare subject integer;
begin
 if tg_op='DELETE' then
  select r.user_id into subject from public.elearning_form_responses r where (r.tenant_id,r.id)=(old.tenant_id,old.response_id);
  if subject is not null and public.erasure_scope_authorized167(subject) then return old;end if;
 end if;
 raise exception using errcode='42501',message='form_decision_history_immutable';
end $$;

create or replace function public.academy_private_immutable() returns trigger language plpgsql security definer set search_path='' as $$
declare subject integer;
begin
 if tg_op='DELETE' and old.entity_type='application' then
  select user_id into subject from public.academy_applications where (tenant_id,id)=(old.tenant_id,old.entity_id);
  if subject is not null and public.erasure_scope_authorized167(subject) then return old;end if;
 end if;
 raise exception using errcode='42501',message='academy_history_immutable';
end $$;

create function public.account_audit_owned167(a public.audit_logs,p_subject integer,p_auth uuid,p_email_fingerprint text)
returns boolean language sql immutable set search_path='' as $$
 select a.actor_user_id=p_subject
 or (a.target_type in ('user','tenant_membership') and a.target_id=p_subject::text)
 or (a.target_type='auth_user' and a.target_id=p_auth::text)
 or a.metadata->>'affected_user_id'=p_subject::text
 or a.metadata->>'restored_user_id'=p_subject::text
 or a.metadata->>'target_user_id'=p_subject::text
 or a.metadata->>'target_email_hash'=p_email_fingerprint
 or a.metadata->>'affected_user_email_hash'=p_email_fingerprint
 or a.metadata->>'identifier_hash'=p_email_fingerprint
$$;

-- Phase6F: declared local Calendar ownership. Actor fields are not ownership.
-- Phase6G: Builder ownership is explicit and is not inferred from uploader or
-- project references. Existing rows remain legacy/unprovable until reconciled.
alter table public.builder_assets add column owner_user_id integer references public.users(id) on delete set null;
alter table public.builder_assets add column ownership_status text not null default 'legacy_unverified'
 check(ownership_status in ('verified','legacy_unverified'));
alter table public.builder_assets add column storage_backend text;
alter table public.builder_assets add column storage_bucket text;
alter table public.builder_assets add column provider_object_key text;
alter table public.builder_assets add constraint builder_assets_verified_ownership167 check(
 ownership_status<>'verified' or (owner_user_id is not null and storage_backend='supabase_builder_private'
 and storage_bucket='builder-assets' and provider_object_key=storage_key));
create index builder_assets_owner167_idx on public.builder_assets(owner_user_id,id);

create function public.account_fence_registration167(p_tenant_id integer,p_user_id integer)
returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.users where id=p_user_id and tenant_id=p_tenant_id)
$$;

create function public.account_calendar_predicate167(p_table text) returns text language plpgsql immutable set search_path='' as $$
begin
 case p_table
 when 'calendars' then return 'p.owner_user_id=$1';
 when 'calendar_memberships' then return 'p.user_id=$1 or p.calendar_id in(select id from public.calendars where owner_user_id=$1)';
 when 'calendar_events' then return 'p.calendar_id in(select id from public.calendars where owner_user_id=$1)';
 when 'calendar_tasks' then return 'p.owner_user_id=$1';
 when 'calendar_task_reminders' then return 'p.task_id in(select id from public.calendar_tasks where owner_user_id=$1)';
 when 'calendar_task_dependencies' then return 'p.task_id in(select id from public.calendar_tasks where owner_user_id=$1)';
 when 'calendar_event_attendees','calendar_event_reminders','calendar_event_changes','calendar_invitation_reviews' then
 return 'p.event_id in(select e.id from public.calendar_events e join public.calendars c on c.id=e.calendar_id where c.owner_user_id=$1)';
 else return null;
 end case;
end;$$;

create function public.account_notification_owned167(p public.notification_events,p_subject integer) returns boolean
language sql stable security definer set search_path='' as $$select
 (p.source_type='bi_report' and exists(select 1 from public.bi_report_runs r where r.id::text=p.source_id and r.creator_user_id=p_subject))
 or (p.source_type='calendar_event' and exists(select 1 from public.calendar_events e join public.calendars c on c.id=e.calendar_id where e.id::text=p.source_id and c.owner_user_id=p_subject))
 or (p.source_type='calendar_task' and exists(select 1 from public.calendar_tasks t where t.id::text=p.source_id and t.owner_user_id=p_subject))
$$;

create function public.account_closure_tables167() returns text[] language sql immutable set search_path='' as $$select array[
 'admin_account_access_sessions','admin_account_access_requests','password_reset_requests','pending_account_onboarding','email_verification_attempts','audit_logs','notification_deliveries','notification_outbox','user_notifications','notification_preferences','web_push_subscriptions',
 'bi_report_deliveries','bi_report_cleanup_jobs','bi_report_delivery_recipients','bi_report_delivery_configs','bi_report_lifecycle_settings','bi_report_shares','bi_dashboard_shares','bi_report_runs','bi_report_schedules','bi_dashboard_widgets','bi_dashboards',
 'data_source_webhook_events','data_source_webhook_endpoints','data_source_oauth_transactions','google_sheets_source_mappings','data_source_sync_attempts','data_source_sync_schedules','data_source_credential_events','data_source_credentials','data_ingestion_staged_changes','data_dataset_current_records','data_dataset_record_changes','data_dataset_checkpoints','data_source_ingestion_runs','data_dataset_versions','data_datasets','data_source_resources','data_sources',
 'calendar_event_attendees','calendar_event_reminders','calendar_event_changes','calendar_invitation_reviews','calendar_task_reminders','calendar_task_dependencies','calendar_memberships','calendar_events','calendar_tasks','calendars',
 'app_installations','user_security_settings','workspace_screen_time_daily','public_quiz_attempts',
 'elearning_recording_cleanup','elearning_assessment_recordings','elearning_assessment_reviews','elearning_assessment_media_refs','elearning_assessment_answers','elearning_assessment_attempts','elearning_credentials','elearning_completion_events','elearning_lesson_completions','elearning_access_grants','elearning_enrollments','elearning_group_members','elearning_learners','elearning_instructors',
 'elearning_form_decision_history','elearning_form_reviews','elearning_form_files','elearning_form_responses','academy_application_documents','academy_workflow_history','academy_applications','academy_referral_codes',
 'builder_form_drafts','builder_form_submissions','builder_reservations','builder_project_versions','builder_projects']::text[]$$;

-- Catalog-only predicates for fail-closed dependency inventory. These are
-- private helpers, never caller-provided table names/SQL or a generic eraser.
create function public.account_parent_predicate167(p_table text) returns text language plpgsql stable security definer set search_path='' as $$
declare pred text:='false';col record;
begin
 pred:=public.account_calendar_predicate167(p_table);if pred is not null then return pred;end if;pred:='false';
 if p_table='users' then return 'p.id=$1';end if;
 if p_table='builder_projects' then return 'p.owner_user_id=$1';end if;
 if p_table='audit_logs' then return 'public.account_audit_owned167(p,$1,$3,$4)';end if;
 if p_table='notification_events' then return 'public.account_notification_owned167(p,$1)';end if;
 if p_table='ecommerce_orders' then return 'public.account_commerce_order_owned167(p,$1)';end if;
 if p_table='ecommerce_checkouts' then return 'p.user_id=$1';end if;
 for col in select attname,atttypid from pg_catalog.pg_attribute where attrelid=to_regclass('public.'||p_table) and attnum>0 and not attisdropped loop
  if col.attname in ('user_id','owner_user_id','creator_user_id','created_by_user_id','initiated_by_user_id','actor_user_id','recipient_user_id','member_user_id','admin_user_id','target_user_id','target_user_id_snapshot','subject_id') and col.atttypid in (20,21,23) then pred:=pred||format(' or p.%I=$1',col.attname);end if;
  if col.attname='project_id' and col.atttypid='uuid'::regtype then pred:=pred||' or p.project_id=any($2)';end if;
  if col.attname='auth_id' and col.atttypid='uuid'::regtype then pred:=pred||' or p.auth_id=$3';end if;
  if col.attname='email_hash' then pred:=pred||' or p.email_hash=$4';end if;
  if col.attname='request_id' and col.atttypid='uuid'::regtype then pred:=pred||' or p.request_id in(select id from public.data_deletion_requests where target_user_id_snapshot=$1)';end if;
 end loop;
 return pred;
end;$$;

-- No arbitrary tables/SQL supplied by a caller. Catalog checks reject undeclared
-- ownership or retention-bearing rows, including ON DELETE CASCADE/SET NULL edges.
create function public.preflight_account_erasure167(p_request_id uuid,p_token uuid,p_generation bigint)
returns jsonb language plpgsql security definer set search_path='' as $$
declare h public.account_lifecycles167;t record;c record;n bigint;pred text;projects uuid[];allowed text[];edge record;join_pred text;matched boolean;module_rows bigint:=0;
begin
 h:=public.owned_account_erasure167(p_request_id,p_token,p_generation);
 if h.database_released then projects:=h.project_ids;
 else select coalesce(array_agg(id),'{}'::uuid[]) into projects from public.builder_projects where owner_user_id=h.subject_id;end if;
 -- Pseudonymous email-only history is not silently exempt. A duplicate
 -- identity in another account makes ownership ambiguous and blocks erasure.
 if exists(select 1 from public.users u where u.id<>h.subject_id and encode(sha256(convert_to(lower(btrim(u.email)),'UTF8')),'hex')=h.email_fingerprint)
 and (exists(select 1 from public.email_verification_attempts e where e.email_hash=h.email_fingerprint and e.user_id is null and e.auth_id is null)
 or exists(select 1 from public.audit_logs a where a.metadata->>'target_email_hash'=h.email_fingerprint or a.metadata->>'affected_user_email_hash'=h.email_fingerprint or a.metadata->>'identifier_hash'=h.email_fingerprint))
 then raise exception 'shared_project_ownership:ambiguous_email_history';end if;
 -- Only the registered Data workspace/storage adapters are currently
 -- complete. Never certify deletion of an unclassified published/archived
 -- workspace or silently apply the home-tenant file layout to another tenant.
 if exists(select 1 from public.builder_projects p where p.owner_user_id=h.subject_id and
  (p.tenant_id<>h.tenant_id or (p.draft_schema->>'workspaceKind' is not null and p.draft_schema->>'workspaceKind'<>'data')
   or (p.published_schema->>'workspaceKind' is not null and p.published_schema->>'workspaceKind'<>'data')))
 then raise exception 'account_inventory_adapter_required:workspace_or_tenant';end if;
 -- Foreign-project participation is not project ownership. Preserve the
 -- independent project and block unresolved account content/actor history.
 if exists(select 1 from public.builder_form_drafts d where d.site_user_id=h.subject_id and d.project_id<>all(projects))
 or exists(select 1 from public.contacts contact_row where encode(sha256(convert_to(lower(btrim(contact_row.email)),'UTF8')),'hex')=h.email_fingerprint and (contact_row.project_id is null or contact_row.project_id<>all(projects)))
 or exists(select 1 from public.builder_reservations r where encode(sha256(convert_to(lower(btrim(r.customer_email)),'UTF8')),'hex')=h.email_fingerprint and r.project_id<>all(projects))
 then raise exception 'shared_project_ownership:participation';end if;
 -- Unclassified notification payloads cannot be treated as orphan-free
 -- merely by deleting their recipient copy. Preserve unknown history and block.
 if exists(select 1 from public.user_notifications un join public.notification_events ne on ne.id=un.event_id
 where un.user_id=h.subject_id and ne.source_type not in ('bi_report','calendar_event','calendar_task'))
 then raise exception 'account_inventory_adapter_required:notification_source';end if;
 -- Learning participation is personal; teaching resources are independent.
 -- Actor/uploader attribution never grants authority over another person's
 -- attempt, response or application.
 if exists(select 1 from public.elearning_instructors i where i.user_id=h.subject_id and
   (exists(select 1 from public.elearning_course_instructors x where (x.tenant_id,x.instructor_id)=(i.tenant_id,i.id))
    or exists(select 1 from public.elearning_group_instructors x where (x.tenant_id,x.instructor_id)=(i.tenant_id,i.id))))
 then raise exception 'shared_learning_ownership:instructor_assignment';end if;
 if exists(select 1 from public.elearning_assessment_reviews r join public.elearning_assessment_attempts a on (a.tenant_id,a.id)=(r.tenant_id,r.attempt_id)
   where r.reviewer_id=h.subject_id and a.user_id<>h.subject_id)
 or exists(select 1 from public.elearning_form_reviews v join public.elearning_form_responses r on (r.tenant_id,r.id)=(v.tenant_id,v.response_id)
   where v.reviewer_id=h.subject_id and r.user_id is distinct from h.subject_id)
 or exists(select 1 from public.elearning_form_decision_history d join public.elearning_form_responses r on (r.tenant_id,r.id)=(d.tenant_id,d.response_id)
   where d.actor_id=h.subject_id and r.user_id is distinct from h.subject_id)
 then raise exception 'shared_learning_ownership:review_history';end if;
 if exists(select 1 from public.academy_workflow_history w left join public.academy_applications a
   on w.entity_type='application' and (a.tenant_id,a.id)=(w.tenant_id,w.entity_id)
   where w.actor_id=h.subject_id and (a.user_id is null or a.user_id<>h.subject_id))
 or exists(select 1 from public.academy_application_documents d join public.academy_applications a on (a.tenant_id,a.id)=(d.tenant_id,d.application_id)
   where d.uploaded_by=h.subject_id and a.user_id<>h.subject_id)
 then raise exception 'shared_academy_ownership:actor_history';end if;
 if exists(select 1 from public.academy_applications a join public.elearning_form_responses r
   on (r.tenant_id,r.id)=(a.tenant_id,a.learning_form_response_id)
   where (a.user_id=h.subject_id) is distinct from (r.user_id=h.subject_id))
 then raise exception 'shared_academy_ownership:form_application';end if;
 -- Every committed private Learning/Academy byte must have one exact quota
 -- registry identity owned by the same account.  Missing or contradictory
 -- accounting blocks before immutable relational metadata is released.
 if exists(select 1 from public.elearning_assessment_recordings r join public.elearning_assessment_attempts a on (a.tenant_id,a.id)=(r.tenant_id,r.attempt_id)
   where a.user_id=h.subject_id and not exists(select 1 from public.storage_objects o where o.tenant_id=r.tenant_id and o.user_id=h.subject_id and o.category='elearning_assessment' and o.storage_key=r.storage_key and o.sha256=r.sha256 and o.size_bytes=r.size_bytes and o.status='active'))
 or exists(select 1 from public.elearning_form_files f join public.elearning_form_responses r on (r.tenant_id,r.id)=(f.tenant_id,f.response_id)
   where r.user_id=h.subject_id and not exists(select 1 from public.storage_objects o where o.tenant_id=f.tenant_id and o.user_id=h.subject_id and o.category='elearning_form' and o.storage_key=f.storage_key and o.sha256=f.sha256 and o.size_bytes=f.size_bytes and o.status='active'))
 or exists(select 1 from public.academy_application_documents d join public.academy_applications a on (a.tenant_id,a.id)=(d.tenant_id,d.application_id)
   where a.user_id=h.subject_id and d.removed_at is null and not exists(select 1 from public.storage_objects o where o.tenant_id=d.tenant_id and o.user_id=h.subject_id and o.category='academy_document' and o.storage_key=d.storage_key and o.sha256=d.sha256 and o.size_bytes=d.size_bytes and o.status='active'))
 then raise exception 'account_learning_storage_registry_mismatch';end if;
 -- Commerce customer identity is exact only through customer_id or checkout
 -- user_id. Email similarity alone cannot authorize changing a merchant order.
 -- A live provider may hold payment/customer bytes outside Madar; without a
 -- provider erasure/retention adapter, refuse before changing either ledger.
 if exists(select 1 from public.ecommerce_orders o where public.account_commerce_order_owned167(o,h.subject_id) and o.tenant_id<>h.tenant_id)
 or exists(select 1 from public.ecommerce_checkouts checkout_row where checkout_row.user_id=h.subject_id and checkout_row.tenant_id<>h.tenant_id)
 or exists(select 1 from public.ecommerce_checkouts checkout_row join public.ecommerce_orders o on (o.tenant_id,o.id)=(checkout_row.tenant_id,checkout_row.order_id)
   where checkout_row.user_id=h.subject_id and o.customer_id is not null and o.customer_id<>h.subject_id)
 then raise exception 'shared_commerce_ownership:customer_link';end if;
 if exists(select 1 from public.ecommerce_orders o
   where encode(sha256(convert_to(lower(btrim(o.customer_email)),'UTF8')),'hex')=h.email_fingerprint
   and not public.account_commerce_order_owned167(o,h.subject_id))
 then raise exception 'account_commerce_identity_unresolved:guest_order_email';end if;
 if exists(select 1 from public.ecommerce_checkouts checkout_row where checkout_row.user_id=h.subject_id and checkout_row.provider<>'local_test')
 then raise exception 'account_commerce_provider_erasure_required';end if;
 select count(*) into n from (select o.id from public.ecommerce_orders o where public.account_commerce_order_owned167(o,h.subject_id) limit 20001) commerce_orders;
 module_rows:=module_rows+n;if module_rows>20000 then raise exception 'account_inventory_limit:commerce';end if;
 select count(*) into n from (select checkout_row.id from public.ecommerce_checkouts checkout_row where checkout_row.user_id=h.subject_id limit 20001) commerce_checkouts;
 module_rows:=module_rows+n;if module_rows>20000 then raise exception 'account_inventory_limit:commerce';end if;
 select count(*) into n from (select x.id from public.ecommerce_loyalty_transactions x where x.customer_id=h.subject_id limit 20001) commerce_loyalty;
 module_rows:=module_rows+n;if module_rows>20000 then raise exception 'account_inventory_limit:commerce';end if;
 -- New metadata adapters have an aggregate bounded row budget as well as
 -- the existing physical-object inventory bound. Predicates mirror release.
 for t in select unnest(array['app_installations','user_security_settings','workspace_screen_time_daily','public_quiz_attempts','builder_form_drafts','builder_form_submissions','builder_reservations']) as relname loop
  pred:=case when t.relname in ('app_installations','user_security_settings','workspace_screen_time_daily') then 'p.user_id=$1' else 'p.project_id=any($2)' end;
  execute format('select count(*) from (select 1 from public.%I p where %s limit 20001) bounded_rows',t.relname,pred) into n using h.subject_id,projects;
  module_rows:=module_rows+n;if module_rows>20000 then raise exception 'account_inventory_limit:metadata';end if;
 end loop;
 -- A private local calendar is an owned resource; shared calendars and remote
 -- objects have no admitted erasure adapter. Fail before changing any payload.
 if exists(select 1 from public.calendars cal_owner where cal_owner.owner_user_id=h.subject_id and (cal_owner.tenant_id<>h.tenant_id or cal_owner.visibility<>'private'))
 or exists(select 1 from public.calendar_memberships m join public.calendars cal_owner on cal_owner.id=m.calendar_id where cal_owner.owner_user_id=h.subject_id and m.user_id<>h.subject_id)
 or exists(select 1 from public.calendar_events e join public.calendars cal_owner on cal_owner.id=e.calendar_id where
  (cal_owner.owner_user_id=h.subject_id and (e.tenant_id<>h.tenant_id or e.created_by is distinct from h.subject_id or e.source_type<>'madar' or e.source_id is not null or (e.project_id is not null and e.project_id<>all(projects))))
  or (cal_owner.owner_user_id is distinct from h.subject_id and (e.created_by=h.subject_id or e.project_id=any(projects))))
 or exists(select 1 from public.calendar_tasks cal_task left join public.calendars cal_owner on cal_owner.id=cal_task.calendar_id where
  (cal_task.owner_user_id=h.subject_id and (cal_task.tenant_id<>h.tenant_id or (cal_task.calendar_id is not null and cal_owner.owner_user_id is distinct from h.subject_id) or (cal_task.project_id is not null and cal_task.project_id<>all(projects))))
  or (cal_task.owner_user_id is distinct from h.subject_id and (cal_owner.owner_user_id=h.subject_id or cal_task.project_id=any(projects))))
 or exists(select 1 from public.calendar_event_changes x join public.calendar_events e on e.id=x.event_id join public.calendars cal_owner on cal_owner.id=e.calendar_id where x.changed_by=h.subject_id and cal_owner.owner_user_id is distinct from h.subject_id)
 or exists(select 1 from public.calendar_task_dependencies d join public.calendar_tasks a on a.id=d.task_id join public.calendar_tasks b on b.id=d.depends_on_task_id where (a.owner_user_id=h.subject_id) is distinct from (b.owner_user_id=h.subject_id))
 or exists(select 1 from public.calendar_events e join public.calendar_events parent on parent.id=e.recurrence_parent_id join public.calendars a on a.id=e.calendar_id join public.calendars b on b.id=parent.calendar_id where (a.owner_user_id=h.subject_id) is distinct from (b.owner_user_id=h.subject_id))
 then raise exception 'shared_project_ownership:calendar';end if;
 if exists(select 1 from public.calendar_sync_connections cal_owner where cal_owner.user_id=h.subject_id or cal_owner.local_calendar_id in(select id from public.calendars where owner_user_id=h.subject_id))
 or exists(select 1 from public.calendar_tasks cal_task where cal_task.owner_user_id=h.subject_id and (cal_task.sync_connection_id is not null or cal_task.sync_event_id is not null))
 then raise exception 'account_inventory_adapter_required:calendar_provider';end if;
 for t in select unnest(array['calendars','calendar_events','calendar_tasks','calendar_memberships','calendar_event_attendees','calendar_event_changes','calendar_event_reminders','calendar_invitation_reviews','calendar_task_dependencies','calendar_task_reminders']) as relname loop
  pred:=public.account_calendar_predicate167(t.relname);
  execute format('select count(*) from (select 1 from public.%I p where (%s) limit 20001) bounded_rows',t.relname,pred) into n using h.subject_id;
  module_rows:=module_rows+n;if module_rows>20000 then raise exception 'account_inventory_limit:calendar';end if;
  execute format('select exists(select 1 from public.%I p where (%s) and p.tenant_id<>$2)',t.relname,pred) into matched using h.subject_id,h.tenant_id;
  if matched then raise exception 'shared_project_ownership:calendar_tenant';end if;
 end loop;
 -- Email-only participation in someone else's calendar cannot be removed by
 -- deleting the independent calendar. Require an explicit ownership decision.
 if exists(select 1 from public.calendar_event_attendees a join public.calendar_events e on e.id=a.event_id join public.calendars cal_owner on cal_owner.id=e.calendar_id
 where encode(sha256(convert_to(lower(btrim(a.email)),'UTF8')),'hex')=h.email_fingerprint and cal_owner.owner_user_id is distinct from h.subject_id)
 then raise exception 'shared_project_ownership:calendar_attendee';end if;
 -- Builder assets are an independently owned resource family. Uploader is
 -- attribution only; owned projects are consumers, not ownership evidence.
 if exists(select 1 from public.builder_assets a where
   (a.owner_user_id=h.subject_id or a.uploader_user_id=h.subject_id or exists(select 1 from public.builder_asset_references r where r.asset_id=a.id and r.project_id=any(projects)))
   and (a.ownership_status<>'verified' or a.owner_user_id is null or a.storage_backend<>'supabase_builder_private'
    or a.storage_bucket<>'builder-assets' or a.provider_object_key is distinct from a.storage_key))
 then raise exception 'account_builder_asset_ownership_unresolved';end if;
 if exists(select 1 from public.builder_assets a join public.builder_asset_references r on r.asset_id=a.id
   join public.builder_projects p on p.id=r.project_id
   where a.owner_user_id=h.subject_id and p.owner_user_id is distinct from h.subject_id)
 then raise exception 'shared_project_ownership:builder_asset';end if;
 if exists(select 1 from public.builder_assets a join public.builder_asset_references r on r.asset_id=a.id
   join public.builder_projects p on p.id=r.project_id
   where p.owner_user_id=h.subject_id and a.owner_user_id is distinct from h.subject_id)
 then raise exception 'shared_project_ownership:builder_asset_dependency';end if;
 if exists(select 1 from public.builder_assets a join storage.objects o on o.bucket_id=a.storage_bucket and o.name=a.provider_object_key
   where a.owner_user_id=h.subject_id and ((nullif(to_jsonb(o)->>'owner_id','') is not null and to_jsonb(o)->>'owner_id'<>h.auth_id::text)
    or (nullif(to_jsonb(o)->>'owner','') is not null and to_jsonb(o)->>'owner'<>h.auth_id::text)))
 then raise exception 'shared_project_ownership:builder_provider';end if;
 -- Product/taxonomy/variant/order-snapshot media belongs to the independent
 -- merchant record once referenced.  Do not reinterpret uploader/account
 -- ownership or delete those bytes; refuse until an explicit owner is agreed.
 if exists(select 1 from public.builder_assets a where a.owner_user_id=h.subject_id and (
   exists(select 1 from public.ecommerce_products p where p.tenant_id=a.tenant_id and p.images ? ('/uploads/'||a.storage_key))
   or exists(select 1 from public.ecommerce_product_variants v where v.tenant_id=a.tenant_id and v.images ? ('/uploads/'||a.storage_key))
   or exists(select 1 from public.ecommerce_categories category_row where category_row.tenant_id=a.tenant_id and category_row.image_url='/uploads/'||a.storage_key)
   or exists(select 1 from public.ecommerce_brands b where b.tenant_id=a.tenant_id and b.image_url='/uploads/'||a.storage_key)
   or exists(select 1 from public.ecommerce_order_items i where i.tenant_id=a.tenant_id and ((i.product_snapshot->'images') ? ('/uploads/'||a.storage_key) or (i.variant_snapshot->'images') ? ('/uploads/'||a.storage_key)))
   or exists(select 1 from public.website_settings s cross join lateral jsonb_array_elements(coalesce(s.ecommerce_theme->'landing_page'->'slides','[]'::jsonb)) slide where s.tenant_id=a.tenant_id and slide->>'image_url'='/uploads/'||a.storage_key)
 )) then raise exception 'shared_commerce_ownership:catalog_asset';end if;
 allowed:=public.account_closure_tables167()||public.account_commerce_tables167()||array['users','tenant_memberships','builder_assets','builder_asset_references','storage_objects','storage_reservations','storage_accounts',
   'data_deletion_requests','data_deletion_subjects','data_deletion_steps','data_deletion_resources','data_deletion_effects','account_lifecycles167','account_lifecycle_resources167'];
 for t in select cl.relname from pg_catalog.pg_class cl join pg_catalog.pg_namespace ns on ns.oid=cl.relnamespace where ns.nspname='public' and cl.relkind='r' and cl.relname<>all(allowed) loop
  pred:='false';
  for c in select a.attname,a.atttypid from pg_catalog.pg_attribute a where a.attrelid=to_regclass('public.'||t.relname) and a.attnum>0 and not a.attisdropped loop
   if c.attname in ('user_id','owner_user_id','creator_user_id','created_by_user_id','initiated_by_user_id','actor_user_id','recipient_user_id','member_user_id','requested_by_user_id') and c.atttypid in (20,21,23) then pred:=pred||format(' or %I=$1',c.attname);end if;
   if c.attname='auth_id' and c.atttypid='uuid'::regtype then pred:=pred||format(' or %I=$3',c.attname);end if;
   if c.attname='project_id' and c.atttypid='uuid'::regtype then pred:=pred||format(' or %I=any($2)',c.attname);end if;
  end loop;
  -- Follow catalog-declared identity FKs, including differently named actor,
  -- uploader and target fields. SET NULL/CASCADE must not silently erase the
  -- ownership link before retention/adapter review.
  for c in select a.attname,f.confrelid from pg_catalog.pg_constraint f
   join pg_catalog.pg_attribute a on a.attrelid=f.conrelid and a.attnum=f.conkey[1]
   where f.conrelid=to_regclass('public.'||t.relname) and f.contype='f'
     and cardinality(f.conkey)=1 and f.confrelid in ('public.users'::regclass,'auth.users'::regclass,'public.builder_projects'::regclass) loop
    if c.confrelid='public.users'::regclass then pred:=pred||format(' or %I=$1',c.attname);
    elsif c.confrelid='auth.users'::regclass then pred:=pred||format(' or %I=$3',c.attname);
    else pred:=pred||format(' or %I=any($2)',c.attname);end if;
  end loop;
  execute format('select count(*) from public.%I where %s',t.relname,pred) into n using h.subject_id,projects,h.auth_id;
  if n>0 then raise exception 'account_retention_or_adapter_required:%',t.relname;end if;
 end loop;
 -- A child can contain private payload even without a user/project column.
 -- Refuse unknown FK dependents BEFORE CASCADE/SET NULL can destroy the link.
 for edge in select f.conrelid,f.confrelid,f.conkey,f.confkey,child.relname as child_name,parent.relname as parent_name
  from pg_catalog.pg_constraint f join pg_catalog.pg_class child on child.oid=f.conrelid
  join pg_catalog.pg_namespace cn on cn.oid=child.relnamespace
  join pg_catalog.pg_class parent on parent.oid=f.confrelid
  join pg_catalog.pg_namespace pn on pn.oid=parent.relnamespace
  where f.contype='f' and cn.nspname='public' and pn.nspname='public'
   and child.relname<>all(allowed) and parent.relname=any(allowed||array['notification_events']) loop
  select string_agg(format('c.%I=p.%I',ca.attname,pa.attname),' and ') into join_pred
   from generate_subscripts(edge.conkey,1) i
   join pg_catalog.pg_attribute ca on ca.attrelid=edge.conrelid and ca.attnum=edge.conkey[i]
   join pg_catalog.pg_attribute pa on pa.attrelid=edge.confrelid and pa.attnum=edge.confkey[i];
  pred:=public.account_parent_predicate167(edge.parent_name);
  execute format('select exists(select 1 from public.%I c join public.%I p on %s where (%s))',edge.child_name,edge.parent_name,join_pred,pred) into matched using h.subject_id,projects,h.auth_id,h.email_fingerprint;
  if matched then raise exception 'account_inventory_adapter_required:%',edge.child_name;end if;
 end loop;
 -- Immutable versions and provider objects must not straddle owners. A creator
 -- reference alone does not authorize changing someone else's independent data.
 if exists(select 1 from public.data_dataset_versions v join public.data_datasets d on d.id=v.dataset_id
   join public.builder_projects p on p.id=d.project_id join public.storage_objects o on o.id=v.storage_object_id
   where (v.created_by_user_id=h.subject_id and (d.creator_user_id<>h.subject_id or p.owner_user_id<>h.subject_id))
    or (d.creator_user_id=h.subject_id and (v.created_by_user_id<>h.subject_id or o.user_id<>h.subject_id)))
 then raise exception 'shared_project_ownership';end if;
 if exists(select 1 from public.storage_objects o join public.storage_objects other
   on other.storage_backend=o.storage_backend and other.storage_bucket=o.storage_bucket and other.provider_object_key=o.provider_object_key
   where o.user_id=h.subject_id and other.user_id<>h.subject_id)
 then raise exception 'shared_project_ownership';end if;
 -- Every supported C5 row in an owned project must itself belong to this
 -- account. Target-authored resources in someone else's project also block.
 for t in select unnest(public.account_closure_tables167()) as relname loop
  if to_regclass('public.'||t.relname) is null then continue;end if;
  if exists(select 1 from pg_catalog.pg_attribute where attrelid=to_regclass('public.'||t.relname) and attname='project_id' and not attisdropped) then
   for c in select attname from pg_catalog.pg_attribute where attrelid=to_regclass('public.'||t.relname) and attname in ('creator_user_id','created_by_user_id','initiated_by_user_id','actor_user_id','owner_user_id') and not attisdropped loop
    if t.relname='data_source_credential_events' and c.attname='actor_user_id' then
     -- An admin who rotated an account's credentials is an actor, not the
     -- owner of the account's credential-event content. Shared project writes
     -- by this subject into someone else's project still block.
     select count(*) into n from public.data_source_credential_events e
      join public.builder_projects p on p.id=e.project_id
      where e.actor_user_id=h.subject_id and p.owner_user_id is distinct from h.subject_id;
    else
    execute format('select count(*) from public.%I t join public.builder_projects p on p.id=t.project_id where (t.%I=$1 and p.owner_user_id is distinct from $1) or (p.owner_user_id=$1 and t.%I is not null and t.%I<>$1)',t.relname,c.attname,c.attname,c.attname) into n using h.subject_id;
    end if;
    if n>0 then raise exception 'shared_project_ownership';end if;
   end loop;
  end if;
 end loop;
 if exists(select 1 from public.builder_projects p where p.owner_user_id is distinct from h.subject_id and
    (p.draft_schema::text like '%tenant_'||h.tenant_id||'/user_'||h.subject_id||'/%' or p.published_schema::text like '%tenant_'||h.tenant_id||'/user_'||h.subject_id||'/%')) then raise exception 'shared_project_ownership';end if;
 -- Registry provenance cannot override contradictory provider ownership.
 -- Check both legacy/current owner fields: an empty newer field must not hide
 -- a different legacy owner, including objects missing from another registry.
 if exists(select 1 from storage.objects o join (
    select r.storage_bucket as bucket,r.provider_object_key as key from public.storage_objects r where r.user_id=h.subject_id and r.storage_backend='supabase_private'
    union all select case when r.category='elearning_assessment' then 'elearning-assessment-recordings' else 'builder-assets' end,r.storage_key from public.storage_objects r where r.user_id=h.subject_id and r.category in ('elearning_assessment','elearning_form','academy_document')
    union all select 'avatars',r.storage_key from public.storage_objects r where r.user_id=h.subject_id and r.category='avatar'
    union all select r.storage_bucket,r.provider_object_key from public.storage_reservations r where r.user_id=h.subject_id and r.transfer_state<>'none'
   ) owned on owned.bucket=o.bucket_id and owned.key=o.name
   where (nullif(to_jsonb(o)->>'owner_id','') is not null and to_jsonb(o)->>'owner_id'<>h.auth_id::text)
      or (nullif(to_jsonb(o)->>'owner','') is not null and to_jsonb(o)->>'owner'<>h.auth_id::text))
 then raise exception 'shared_project_ownership:provider_registry_disagreement';end if;
 -- Provider metadata is an independent inventory, not just registry evidence.
 -- Unknown objects block before references are released; ownership is never
 -- inferred from a path alone or widened to another account's namespace.
 if to_regclass('storage.objects') is null then raise exception 'account_provider_inventory_unavailable';end if;
 if exists(select 1 from storage.objects o where
    coalesce(to_jsonb(o)->>'owner_id',to_jsonb(o)->>'owner')=h.auth_id::text
    and not exists(select 1 from public.storage_objects r where r.user_id=h.subject_id and
      ((r.storage_backend='supabase_private' and r.storage_bucket=o.bucket_id and r.provider_object_key=o.name)
       or (r.category='elearning_assessment' and o.bucket_id='elearning-assessment-recordings' and r.storage_key=o.name)
       or (r.category in ('elearning_form','academy_document') and o.bucket_id='builder-assets' and r.storage_key=o.name)
       or (r.category='avatar' and o.bucket_id='avatars' and r.storage_key=o.name)))
    and not exists(select 1 from public.storage_reservations r where r.user_id=h.subject_id and r.storage_bucket=o.bucket_id and r.provider_object_key=o.name)
    and not exists(select 1 from public.builder_assets a where a.owner_user_id=h.subject_id and a.ownership_status='verified' and a.storage_bucket=o.bucket_id and a.provider_object_key=o.name))
 then raise exception 'account_retention_or_adapter_required:unregistered_provider_object';end if;
 if (select count(*) from public.storage_objects where user_id=h.subject_id)+(select count(*) from public.bi_report_runs where creator_user_id=h.subject_id)>10000 then raise exception 'account_inventory_limit';end if;
 return jsonb_build_object('released',false,'project_ids',to_jsonb(projects));
end;$$;

create function public.inventory_account_erasure167(p_request_id uuid,p_token uuid,p_generation bigint)
returns void language plpgsql security definer set search_path='' as $$
declare h public.account_lifecycles167;
begin
 h:=public.owned_account_erasure167(p_request_id,p_token,p_generation);
 perform public.preflight_account_erasure167(p_request_id,p_token,p_generation);
 if h.database_released then return;end if;
 update public.account_lifecycles167 set project_ids=coalesce((select array_agg(id) from public.builder_projects where owner_user_id=h.subject_id),'{}'::uuid[]) where id=h.id;
 insert into public.account_lifecycle_resources167(request_id,kind,resource_key,identity)
 select h.id,'storage',id::text,jsonb_build_object('id',id,'tenant_id',tenant_id,'user_id',user_id,'category',category,'storage_key',storage_key,
  'backend',case when category in ('elearning_assessment','elearning_form','academy_document') then 'supabase_learning_private' else storage_backend end,
  'bucket',case when category='elearning_assessment' then 'elearning-assessment-recordings' when category in ('elearning_form','academy_document') then 'builder-assets' else storage_bucket end,
  'provider_key',case when category in ('elearning_assessment','elearning_form','academy_document') then storage_key else provider_object_key end,'sha256',sha256,'size_bytes',size_bytes)
 from public.storage_objects where user_id=h.subject_id and category<>'builder_asset' on conflict do nothing;
 insert into public.account_lifecycle_resources167(request_id,kind,resource_key,identity)
 select h.id,'storage','reservation:'||r.id,jsonb_build_object('tenant_id',r.tenant_id,'user_id',r.user_id,'category',r.category,'backend',r.storage_backend,'bucket',r.storage_bucket,'provider_key',r.provider_object_key,'sha256',r.expected_sha256,'size_bytes',r.bytes)
 from public.storage_reservations r where r.user_id=h.subject_id and r.transfer_state<>'none' and r.provider_object_key is not null
 and not exists(select 1 from public.storage_objects o where o.storage_bucket=r.storage_bucket and o.provider_object_key=r.provider_object_key) on conflict do nothing;
 insert into public.account_lifecycle_resources167(request_id,kind,resource_key,identity)
 select h.id,'report',id::text,jsonb_build_object('id',id,'tenant_id',tenant_id,'owner_user_id',creator_user_id,'archived_at',archived_at,'storage_key',artifact_storage_key)
 from public.bi_report_runs where creator_user_id=h.subject_id on conflict do nothing;
 insert into public.account_lifecycle_resources167(request_id,kind,resource_key,identity)
 select h.id,'storage','builder:'||a.id,jsonb_build_object('id',a.id,'tenant_id',a.tenant_id,'owner_user_id',a.owner_user_id,
  'category','builder_asset','backend',a.storage_backend,'bucket',a.storage_bucket,'provider_key',a.provider_object_key,
  'local_relative',a.storage_key,'sha256',a.sha256,'size_bytes',a.size_bytes)
 from public.builder_assets a where a.owner_user_id=h.subject_id on conflict do nothing;
 insert into public.account_lifecycle_resources167(request_id,kind,resource_key,identity) values(h.id,'auth',h.auth_id::text,jsonb_build_object('auth_id',h.auth_id)) on conflict do nothing;
end;$$;

create function public.register_account_file167(p_request_id uuid,p_token uuid,p_generation bigint,p_key text,p_identity jsonb)
returns void language plpgsql security definer set search_path='' as $$
declare h public.account_lifecycles167;
begin
 h:=public.owned_account_erasure167(p_request_id,p_token,p_generation);
 if h.database_released then raise exception 'account_inventory_sealed';end if;
 if (select count(*) from public.account_lifecycle_resources167 where request_id=h.id)>=20000 then raise exception 'account_inventory_limit';end if;
 if p_identity->>'root' not in ('uploads','charts','public') or p_identity->>'relative' is distinct from p_key
 or p_key~'(^/|(^|/)[.]{1,2}(/|$))' or position(chr(92) in p_key)>0 or not
  (p_key like 'tenant_'||h.tenant_id||'/user_'||h.subject_id||'/%'
   or (p_identity->>'root'='uploads' and p_key like '.parquet_cache/tenant_'||h.tenant_id||'/user_'||h.subject_id||'/%')
   or (p_identity->>'root'='uploads' and exists(select 1 from public.account_lifecycle_resources167 r where r.request_id=h.id and r.kind='storage' and r.identity->>'backend'='supabase_private' and p_key like '.immutable_scratch/tenant_'||h.tenant_id||'/object_'||encode(sha256(convert_to((r.identity->>'bucket')||'/'||(r.identity->>'provider_key'),'UTF8')),'hex')||'/%'))
   or (p_identity->>'root'='charts' and exists(select 1 from public.bi_report_runs r where r.creator_user_id=h.subject_id and (p_key like 'reports/tenant_'||h.tenant_id||'/'||r.id||'/%' or p_key like '.report-tmp/tenant_'||h.tenant_id||'/'||r.id||'/%')))
   or (p_identity->>'root'='public' and exists(select 1 from public.account_lifecycle_resources167 r where r.request_id=h.id and r.kind='storage' and r.identity->>'category'='builder_asset' and r.identity->>'local_relative'=p_key))) then raise exception 'account_file_scope_invalid';end if;
 insert into public.account_lifecycle_resources167(request_id,kind,resource_key,identity) values(h.id,'file',p_identity->>'root'||':'||p_key,p_identity) on conflict do nothing;
end;$$;

create function public.release_account_database167(p_request_id uuid,p_token uuid,p_generation bigint)
returns void language plpgsql security definer set search_path='' as $$
declare h public.account_lifecycles167;info jsonb;projects uuid[];events uuid[];commerce_orders uuid[];t text;col record;pred text;pass integer;n bigint;remaining boolean;progress boolean;
begin
 h:=public.owned_account_erasure167(p_request_id,p_token,p_generation);
 if h.database_released then return;end if;
 info:=public.preflight_account_erasure167(p_request_id,p_token,p_generation);
 select coalesce(array_agg(value::uuid),'{}'::uuid[]) into projects from jsonb_array_elements_text(info->'project_ids');
 select coalesce(array_agg(e.id),'{}'::uuid[]) into events from public.notification_events e where public.account_notification_owned167(e,h.subject_id);
 update public.account_lifecycles167 set irreversible_at=clock_timestamp() where id=h.id;
 perform set_config('madar.erasure_request',h.id::text,true);perform set_config('madar.erasure_token',p_token::text,true);perform set_config('madar.erasure_generation',p_generation::text,true);
 -- Personal Commerce access/loyalty rows are erased. Mixed merchant ledgers
 -- stay intact but lose only their exact customer pointer, contact/address
 -- payload and customer-facing confirmation/idempotency identifiers. Totals,
 -- items, inventory movements, status/payment history and catalogs are unchanged.
 select coalesce(array_agg(o.id),'{}'::uuid[]) into commerce_orders from public.ecommerce_orders o where public.account_commerce_order_owned167(o,h.subject_id);
 delete from public.ecommerce_entitlements where user_id=h.subject_id;
 delete from public.ecommerce_loyalty_transactions where customer_id=h.subject_id;
 update public.ecommerce_order_items i set loyalty_entitlement_id=null where exists(
  select 1 from public.ecommerce_loyalty_entitlements e where e.customer_id=h.subject_id and (e.tenant_id,e.id)=(i.tenant_id,i.loyalty_entitlement_id));
 delete from public.ecommerce_loyalty_entitlements where customer_id=h.subject_id;
 delete from public.ecommerce_loyalty_accounts where customer_id=h.subject_id;
 update public.ecommerce_checkouts set user_id=null where user_id=h.subject_id;
 update public.ecommerce_orders set customer_id=null,customer_name='Erased customer',customer_email='',customer_phone='',
  address_line_1='',address_line_2='',city='',postal_code='',country='',notes='',street='',building='',floor_apartment='',
  address_description='',delivery_notes='',status_reason='',confirmation_token_hash=null,idempotency_key_hash=null,request_hash=null
  where id=any(commerce_orders);
 -- Personal Learning/Academy records are released leaf-first while their
 -- independently owned course/form/opportunity catalogs remain untouched.
 delete from public.elearning_recording_cleanup c where exists(select 1 from public.elearning_assessment_recordings r join public.elearning_assessment_attempts a on (a.tenant_id,a.id)=(r.tenant_id,r.attempt_id) where a.user_id=h.subject_id and (c.tenant_id,c.storage_key)=(r.tenant_id,r.storage_key));
 delete from public.elearning_assessment_recordings r where exists(select 1 from public.elearning_assessment_attempts a where a.user_id=h.subject_id and (a.tenant_id,a.id)=(r.tenant_id,r.attempt_id));
 delete from public.elearning_assessment_reviews r where exists(select 1 from public.elearning_assessment_attempts a where a.user_id=h.subject_id and (a.tenant_id,a.id)=(r.tenant_id,r.attempt_id));
 delete from public.elearning_assessment_media_refs r where r.attempt_id is not null and exists(select 1 from public.elearning_assessment_attempts a where a.user_id=h.subject_id and (a.tenant_id,a.id)=(r.tenant_id,r.attempt_id));
 delete from public.elearning_assessment_answers a where exists(select 1 from public.elearning_assessment_attempts t where t.user_id=h.subject_id and (t.tenant_id,t.id)=(a.tenant_id,a.attempt_id));
 delete from public.elearning_assessment_attempts where user_id=h.subject_id;
 delete from public.elearning_credentials where user_id=h.subject_id;
 delete from public.elearning_completion_events e where exists(select 1 from public.elearning_enrollments n join public.elearning_learners l on (l.tenant_id,l.id)=(n.tenant_id,n.learner_id) where l.user_id=h.subject_id and (n.tenant_id,n.id)=(e.tenant_id,e.enrollment_id));
 delete from public.elearning_lesson_completions x where exists(select 1 from public.elearning_enrollments n join public.elearning_learners l on (l.tenant_id,l.id)=(n.tenant_id,n.learner_id) where l.user_id=h.subject_id and (n.tenant_id,n.id)=(x.tenant_id,x.enrollment_id));
 delete from public.elearning_access_grants g where exists(select 1 from public.elearning_enrollments n join public.elearning_learners l on (l.tenant_id,l.id)=(n.tenant_id,n.learner_id) where l.user_id=h.subject_id and (n.tenant_id,n.id)=(g.tenant_id,g.enrollment_id));
 delete from public.elearning_enrollments n where exists(select 1 from public.elearning_learners l where l.user_id=h.subject_id and (l.tenant_id,l.id)=(n.tenant_id,n.learner_id));
 delete from public.elearning_group_members where user_id=h.subject_id;
 delete from public.elearning_learners where user_id=h.subject_id;
 delete from public.elearning_instructors where user_id=h.subject_id;
 delete from public.academy_application_documents d where exists(select 1 from public.academy_applications a where a.user_id=h.subject_id and (a.tenant_id,a.id)=(d.tenant_id,d.application_id));
 delete from public.academy_workflow_history w where w.entity_type='application' and exists(select 1 from public.academy_applications a where a.user_id=h.subject_id and (a.tenant_id,a.id)=(w.tenant_id,w.entity_id));
 delete from public.academy_applications where user_id=h.subject_id;
 delete from public.elearning_form_decision_history d where exists(select 1 from public.elearning_form_responses r where r.user_id=h.subject_id and (r.tenant_id,r.id)=(d.tenant_id,d.response_id));
 delete from public.elearning_form_reviews v where exists(select 1 from public.elearning_form_responses r where r.user_id=h.subject_id and (r.tenant_id,r.id)=(v.tenant_id,v.response_id));
 delete from public.elearning_form_files f where exists(select 1 from public.elearning_form_responses r where r.user_id=h.subject_id and (r.tenant_id,r.id)=(f.tenant_id,f.response_id));
 delete from public.elearning_form_responses where user_id=h.subject_id;
 delete from public.academy_referral_codes where user_id=h.subject_id;
 -- Break only declared nullable history pointers. Published protection triggers
 -- and every FK remain enabled; the deletion transaction rolls back on a gap.
 update public.data_sources set latest_dataset_id=null,latest_version_id=null,active_credential_id=null where creator_user_id=h.subject_id;
 update public.data_source_resources set latest_checkpoint_version_id=null,dataset_id=null where project_id=any(projects);
 for pass in 1..40 loop
  remaining:=false;progress:=false;
  foreach t in array public.account_closure_tables167() loop
   if to_regclass('public.'||t) is null then continue;end if;
   pred:=public.account_calendar_predicate167(t);
   if pred is not null then
    execute format('delete from public.%I p where %s',t,pred) using h.subject_id;
    get diagnostics n=row_count;progress:=progress or n>0;continue;
   end if;
   pred:='false';
   if t='builder_projects' then pred:='owner_user_id=$1';end if;
   if t='email_verification_attempts' then pred:='user_id=$1 or auth_id=$5 or email_hash=$6';end if;
   if t='audit_logs' then pred:='public.account_audit_owned167(audit_logs,$1,$5,$6)';end if;
   if t in ('notification_deliveries','user_notifications') then pred:=pred||' or event_id=any($3)';end if;
   if t='notification_outbox' then pred:=pred||' or payload->>''event_id''=any($4)';end if;
   for col in select attname from pg_catalog.pg_attribute where attrelid=to_regclass('public.'||t) and attnum>0 and not attisdropped loop
    if col.attname='project_id' then pred:=pred||' or project_id=any($2)';end if;
    if col.attname in ('recipient_user_id','member_user_id','admin_user_id','target_user_id','user_id','creator_user_id','created_by_user_id','initiated_by_user_id','actor_user_id','owner_user_id') then pred:=pred||format(' or %I=$1',col.attname);end if;
   end loop;
   begin
    execute format('delete from public.%I where %s',t,pred) using h.subject_id,projects,events,events::text[],h.auth_id,h.email_fingerprint;
    get diagnostics n=row_count;progress:=progress or n>0;
   exception when foreign_key_violation then remaining:=true;end;
  end loop;
  exit when not remaining;
  if not progress then raise exception 'account_dependency_release_blocked';end if;
 end loop;
 if remaining then raise exception 'account_dependency_release_blocked';end if;
 delete from public.notification_events where id=any(events);
 update public.account_lifecycles167 set database_released=true where id=h.id;
end;$$;

create function public.account_erasure_transition167(p_request_id uuid,p_token uuid,p_generation bigint,p_action text,p_resource_id bigint default null,p_code text default null)
returns public.account_lifecycles167 language plpgsql security definer set search_path='' as $$
declare h public.account_lifecycles167;
begin
 h:=public.owned_account_erasure167(p_request_id,p_token,p_generation);
 if p_action='renew' then update public.account_lifecycles167 set lease_until=clock_timestamp()+interval '120 seconds' where id=h.id;
 elsif p_action in ('intent','verified','uncertain') then
   if not h.database_released then raise exception 'account_database_not_released';end if;
   update public.account_lifecycle_resources167 set state=p_action where id=p_resource_id and request_id=h.id;
   if not found then raise exception 'account_resource_scope_invalid';end if;
 elsif p_action in ('retry','block') then
   update public.account_lifecycles167 set state=case when p_action='retry' and generation<10 then 'retry_pending' else 'blocked' end,eligible_at=case when p_action='retry' then clock_timestamp()+make_interval(secs=>least(300,5*generation)::integer) else eligible_at end,error_code=left(p_code,100),lease_owner=null,lease_token=null,lease_until=null where id=h.id;
 else raise exception 'account_erasure_action_invalid';end if;
 select * into h from public.account_lifecycles167 where id=h.id;return h;
end;$$;

create function public.remove_account_subject167(p_request_id uuid,p_token uuid,p_generation bigint)
returns void language plpgsql security definer set search_path='' as $$
declare h public.account_lifecycles167;o public.storage_objects;
begin
 h:=public.owned_account_erasure167(p_request_id,p_token,p_generation);
 if h.subject_removed then return;end if;
 if not h.database_released or exists(select 1 from public.account_lifecycle_resources167 where request_id=h.id and kind<>'auth' and state<>'verified') then raise exception 'account_resources_unverified';end if;
 perform 1 from public.users where id=h.subject_id for update;
 perform public.preflight_account_erasure167(p_request_id,p_token,p_generation);
 perform set_config('madar.erasure_request',h.id::text,true);perform set_config('madar.erasure_token',p_token::text,true);perform set_config('madar.erasure_generation',p_generation::text,true);
 for o in select * from public.storage_objects where user_id=h.subject_id and status='active' for update loop
  perform public.release_storage_object(o.tenant_id,o.category,o.storage_key);
 end loop;
 delete from public.storage_objects where user_id=h.subject_id;
 delete from public.storage_reservations where user_id=h.subject_id;
 delete from public.storage_accounts where user_id=h.subject_id;
 if exists(select 1 from public.builder_assets a where a.owner_user_id=h.subject_id and not exists(
   select 1 from public.account_lifecycle_resources167 r where r.request_id=h.id and r.resource_key='builder:'||a.id and r.state='verified'))
 then raise exception 'account_resources_unverified';end if;
 delete from public.builder_assets where owner_user_id=h.subject_id;
 delete from public.tenant_memberships where user_id=h.subject_id;
 delete from public.users where id=h.subject_id;
 update public.account_lifecycles167 set subject_removed=true where id=h.id;
end;$$;
create function public.reserve_account_restore_epoch167(p_request_id uuid,p_token uuid,p_generation bigint) returns bigint language plpgsql security definer set search_path='' as $$
declare h public.account_lifecycles167;e bigint;
begin
 h:=public.owned_account_erasure167(p_request_id,p_token,p_generation);
 if not h.subject_removed then raise exception 'account_resources_unverified';end if;
 update public.account_restore_state167 set allocated_epoch=allocated_epoch+1 where singleton returning allocated_epoch into e;
 update public.account_lifecycles167 set restore_epoch=e where id=h.id;
 return e;
end;$$;
create function public.complete_account_erasure167(p_request_id uuid,p_token uuid,p_generation bigint,p_restore_epoch bigint)
returns public.account_lifecycles167 language plpgsql security definer set search_path='' as $$
declare h public.account_lifecycles167;n bigint;history uuid[];
begin
 h:=public.owned_account_erasure167(p_request_id,p_token,p_generation);
 if not h.subject_removed or not h.database_released or exists(select 1 from public.account_lifecycle_resources167 where request_id=h.id and state<>'verified') or exists(select 1 from public.users where id=h.subject_id) then raise exception 'account_erasure_not_verified';end if;
 if exists(select 1 from storage.objects o where coalesce(to_jsonb(o)->>'owner_id',to_jsonb(o)->>'owner')=h.auth_id::text or exists(select 1 from public.account_lifecycle_resources167 r where r.request_id=h.id and r.kind='storage' and r.identity->>'bucket'=o.bucket_id and r.identity->>'provider_key'=o.name)) then raise exception 'account_provider_object_remains';end if;
 execute 'select count(*) from auth.users where id=$1' into n using h.auth_id;
 if n<>0 then raise exception 'account_auth_identity_remains';end if;
 execute 'select count(*) from auth.sessions where user_id=$1' into n using h.auth_id;
 if n<>0 then raise exception 'account_auth_sessions_remain';end if;
 execute 'select count(*) from auth.refresh_tokens where user_id::text=$1::text' into n using h.auth_id;
 if n<>0 then raise exception 'account_auth_refresh_tokens_remain';end if;
 if h.restore_epoch is null or h.restore_epoch is distinct from p_restore_epoch then raise exception 'restore_epoch_required';end if;
 update public.account_restore_state167 set committed_epoch=greatest(committed_epoch,p_restore_epoch) where singleton;
 select array_agg(id) into history from public.data_deletion_requests where request_type='user' and target_user_id_snapshot=h.subject_id;
 delete from public.data_deletion_resources where request_id=any(history);
 delete from public.data_deletion_effects where request_id=any(history);
 delete from public.data_deletion_steps where request_id=any(history);
 delete from public.data_deletion_subjects where request_id=any(history);
 delete from public.account_lifecycle_resources167 where request_id=any(history);
 -- No default audit/history retention: delete prior reactivation/erasure
 -- records after independently verified completion, rather than anonymizing
 -- account action receipts indefinitely. The caller receives a transient ACK.
 delete from public.account_lifecycles167 where id=any(history);
 delete from public.data_deletion_requests where id=any(history);
 h.state:='completed';h.user_id:=null;h.subject_id:=null;h.tenant_id:=null;
 h.auth_id:=null;h.email_fingerprint:=null;h.previous_status:='';h.project_ids:='{}';h.storage_binding:='{}';
 h.completed_at:=clock_timestamp();h.lease_owner:=null;h.lease_token:=null;h.lease_until:=null;
 return h;
end;$$;

create function public.guard_account_work167() returns trigger language plpgsql security definer set search_path='' as $$
declare row_data jsonb;ident text;uid integer;parent text;target text;owner_column text;account_state text;held public.account_lifecycles167;
begin
  for row_data in select v from jsonb_array_elements(
    case when tg_op='INSERT' then jsonb_build_array(to_jsonb(new))
      when tg_op='DELETE' then jsonb_build_array(to_jsonb(old))
      else jsonb_build_array(to_jsonb(old),to_jsonb(new)) end) v loop
    if tg_op<>'DELETE' and tg_table_name in ('audit_logs','email_verification_attempts') then
     for held in select * from public.account_lifecycles167 where state not in ('reactivated','completed') loop
      if ((tg_table_name='email_verification_attempts' and row_data->>'email_hash'=held.email_fingerprint)
       or (tg_table_name='audit_logs' and public.account_audit_owned167(jsonb_populate_record(null::public.audit_logs,row_data),held.subject_id,held.auth_id,held.email_fingerprint)))
       and not public.erasure_scope_authorized167(held.subject_id) then raise exception 'account_processing_frozen';end if;
     end loop;
    end if;
    foreach ident in array array['user_id','customer_id','owner_user_id','creator_user_id','created_by_user_id','initiated_by_user_id','actor_user_id','recipient_user_id','member_user_id','requested_by_user_id','admin_user_id','target_user_id'] loop
      if row_data->>ident is not null then
        select id,account_status into uid,account_state from public.users where id::text=row_data->>ident for share;
        if account_state='deletion_pending' and not public.erasure_scope_authorized167(uid) then raise exception 'account_processing_frozen';end if;
      end if;
    end loop;
    if tg_table_name like 'calendar_%' and row_data->>'event_id' ~ '^[0-9a-fA-F-]{36}$' then
     select u.id,u.account_status into uid,account_state from public.calendar_events e join public.calendars c on c.id=e.calendar_id join public.users u on u.id=c.owner_user_id where e.id=(row_data->>'event_id')::uuid for share of u;
     if account_state='deletion_pending' and not public.erasure_scope_authorized167(uid) then raise exception 'account_processing_frozen';end if;
    end if;
    if tg_table_name='notification_events' and tg_op<>'DELETE' and row_data->>'source_type' in ('bi_report','calendar_event','calendar_task') then
     uid:=null;account_state:=null;
     if row_data->>'source_type'='bi_report' then
      select u.id,u.account_status into uid,account_state from public.bi_report_runs r join public.users u on u.id=r.creator_user_id where r.id::text=row_data->>'source_id' for share of u;
     elsif row_data->>'source_type'='calendar_event' then
      select u.id,u.account_status into uid,account_state from public.calendar_events e join public.calendars cal on cal.id=e.calendar_id join public.users u on u.id=cal.owner_user_id where e.id::text=row_data->>'source_id' for share of u;
     else
      select u.id,u.account_status into uid,account_state from public.calendar_tasks ct join public.users u on u.id=ct.owner_user_id where ct.id::text=row_data->>'source_id' for share of u;
     end if;
     if uid is null then raise exception 'account_notification_resource_unavailable';end if;
     if account_state='deletion_pending' and not public.erasure_scope_authorized167(uid) then raise exception 'account_processing_frozen';end if;
    end if;
    for parent,target,owner_column in values
      ('source_id','data_sources','creator_user_id'),('dataset_id','data_datasets','creator_user_id'),
      ('report_id','bi_report_runs','creator_user_id'),('schedule_id','bi_report_schedules','creator_user_id'),
      ('ingestion_run_id','data_source_ingestion_runs','initiated_by_user_id'),
      ('calendar_id','calendars','owner_user_id'),('connection_id','calendar_sync_connections','user_id'),('task_id','calendar_tasks','owner_user_id'),('project_id','builder_projects','owner_user_id'),
      ('checkout_id','ecommerce_checkouts','user_id'),('order_id','ecommerce_orders','customer_id') loop
      if row_data->>parent ~ '^[0-9a-fA-F-]{36}$' then
        execute format('select u.id,u.account_status from public.%I p join public.users u on u.id=p.%I where p.id=$1::uuid for share of u',target,owner_column)
          into uid,account_state using row_data->>parent;
        if account_state='deletion_pending' and not public.erasure_scope_authorized167(uid) then raise exception 'account_processing_frozen';end if;
      end if;
    end loop;
  end loop;
  if tg_op='DELETE' then return old;end if;return new;
end;$$;
do $$declare t record;begin
 for t in select c.relname from pg_catalog.pg_class c join pg_catalog.pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind='r' and c.relname not in ('users','data_deletion_requests','account_lifecycles167','account_lifecycle_resources167')
 and exists(select 1 from pg_catalog.pg_attribute a where a.attrelid=c.oid and a.attnum>0 and not a.attisdropped and a.attname in ('user_id','customer_id','owner_user_id','creator_user_id','created_by_user_id','initiated_by_user_id','actor_user_id','recipient_user_id','member_user_id','requested_by_user_id','member_user_id','requested_by_user_id','auth_id','project_id','source_id','dataset_id','report_id','schedule_id','ingestion_run_id','task_id','connection_id','checkout_id','order_id','calendar_id','event_id','admin_user_id','target_user_id')) loop
 execute format('create trigger guard_account_work167 before insert or update or delete on public.%I for each row execute function public.guard_account_work167()',t.relname);
 end loop;
end;$$;

create function public.resume_account_erasure167(p_request_id uuid,p_actor_id integer)
returns public.account_lifecycles167 language plpgsql security definer set search_path='' as $$
declare h public.account_lifecycles167;
begin
 if public.account_lifecycle_capability167()->>'protocol' is distinct from '3' then raise exception 'account_lifecycle_schema_unsupported';end if;
 if not exists(select 1 from public.users where id=p_actor_id and user_type='admin' and account_status='active') then raise exception 'deletion_request_unauthorized';end if;
 select * into h from public.account_lifecycles167 where id=p_request_id for update;
 if not found or h.state<>'blocked' then raise exception 'account_resume_unavailable';end if;
 -- No effect/intent is reset and no recovery window is extended. An uncertain
 -- provider resource still requires independent absence before it can advance.
 update public.account_lifecycles167 set state='erasure_pending',error_code=null where id=h.id returning * into h;
 return h;
end;$$;


-- Filter held owners BEFORE taking a bounded scheduler batch. Configuration
-- stays intact during recovery; held rows cannot starve independent customers.
create function public.list_account_work167(p_kind text,p_limit integer,p_before timestamptz)
returns setof jsonb language plpgsql stable security definer set search_path='' as $$
begin
 if public.account_lifecycle_capability167()->>'protocol' is distinct from '3' then raise exception 'account_lifecycle_schema_unsupported';end if;
 if p_limit is null or p_limit<1 or p_limit>(case when p_kind='calendar' then 100 else 20 end) then raise exception 'account_work_bounds';end if;
 if p_kind='schedules' then
  return query select to_jsonb(s) from public.bi_report_schedules s
   join public.users u on u.id=s.creator_user_id join public.builder_projects p on p.id=s.project_id
   join public.users owner on owner.id=p.owner_user_id
   where s.enabled and s.next_run_at<=p_before and u.account_status='active' and owner.account_status='active'
    and p.status<>'archived' and p.draft_schema->>'workspaceKind'='data'
   order by s.next_run_at,s.id limit p_limit;
 elsif p_kind='dashboards' then
  return query select jsonb_build_object('id',d.id,'tenant_id',d.tenant_id,'project_id',d.project_id,'creator_user_id',d.creator_user_id,'revision',d.revision)
   from public.bi_dashboards d join public.users u on u.id=d.creator_user_id join public.builder_projects p on p.id=d.project_id
   join public.users owner on owner.id=p.owner_user_id
   where d.auto_refresh_enabled and u.account_status='active' and owner.account_status='active'
    and p.status<>'archived' and p.draft_schema->>'workspaceKind'='data'
   order by d.updated_at,d.id limit p_limit;
 elsif p_kind='calendar' then
  return query select jsonb_build_object('id',c.id,'tenant_id',c.tenant_id,'last_inbound_success_at',c.last_inbound_success_at,'last_attempt_at',c.last_attempt_at,'inbound_sync_status',c.inbound_sync_status)
   from public.calendar_sync_connections c join public.users u on u.id=c.user_id
   where c.provider in ('google','microsoft') and c.status in ('connected','degraded')
    and c.inbound_sync_status in ('idle','synced') and c.inbound_sync_enabled and c.encrypted_credentials is not null
    and (c.last_inbound_success_at is null or c.last_inbound_success_at<p_before) and u.account_status='active'
   order by c.last_inbound_success_at,c.id limit p_limit;
 else raise exception 'account_work_kind_invalid';end if;
end;$$;

-- Storage INSERT/UPDATE resurrection is independently fenced even for
-- service-role provider uploads. DELETE remains on the durable provider-intent
-- path; ordinary authenticated deletion is denied by the account session RLS.
create function public.guard_account_provider_write167() returns trigger language plpgsql security definer set search_path='' as $$
declare candidate jsonb;h public.account_lifecycles167;
begin
 for candidate in select v from jsonb_array_elements(case when tg_op='INSERT' then jsonb_build_array(to_jsonb(new)) else jsonb_build_array(to_jsonb(old),to_jsonb(new)) end) v loop
  if nullif(coalesce(candidate->>'owner_id',candidate->>'owner'),'') is not null and not exists(select 1 from auth.users a where a.id::text=coalesce(candidate->>'owner_id',candidate->>'owner')) then raise exception 'account_provider_owner_missing';end if;
  if candidate->>'bucket_id'='madar-data-immutable' and
   not exists(select 1 from public.storage_objects o join public.users u on u.id=o.user_id where o.storage_bucket=candidate->>'bucket_id' and o.provider_object_key=candidate->>'name' and u.account_status='active') and
   not exists(select 1 from public.storage_reservations r join public.users u on u.id=r.user_id where r.storage_bucket=candidate->>'bucket_id' and r.provider_object_key=candidate->>'name' and u.account_status='active')
  then raise exception 'account_provider_frozen';end if;
  if candidate->>'bucket_id'='builder-assets' and not exists(
   select 1 from public.builder_assets a join public.users u on u.id=a.owner_user_id
   where a.storage_bucket=candidate->>'bucket_id' and a.provider_object_key=candidate->>'name'
    and a.ownership_status='verified' and u.account_status='active')
   and not exists(select 1 from public.users u where u.auth_id::text=coalesce(candidate->>'owner_id',candidate->>'owner') and u.account_status='active'
    and (candidate->>'name' ~ ('^(elearning-private/tenant_'||u.tenant_id||'/response_[0-9a-f-]{36}/[0-9a-f-]{36}|academy-private/tenant_'||u.tenant_id||'/application_[0-9a-f-]{36}/[0-9a-f-]{36})$')))
  then raise exception 'account_provider_frozen';end if;
  if candidate->>'bucket_id'='elearning-assessment-recordings' and not exists(
   select 1 from public.users u where u.auth_id::text=coalesce(candidate->>'owner_id',candidate->>'owner') and u.account_status='active'
    and candidate->>'name' ~ ('^elearning-assessments/tenant_'||u.tenant_id||'/attempt_[0-9a-f-]{36}/[0-9a-f-]{36}[.]wav$'))
  then raise exception 'account_provider_frozen';end if;

  for h in select * from public.account_lifecycles167 where state not in ('reactivated','completed') and (
    auth_id::text=coalesce(candidate->>'owner_id',candidate->>'owner')
    or exists(select 1 from public.storage_objects o where o.user_id=subject_id and o.storage_bucket=candidate->>'bucket_id' and o.provider_object_key=candidate->>'name')
    or exists(select 1 from public.storage_reservations r where r.user_id=subject_id and r.storage_bucket=candidate->>'bucket_id' and r.provider_object_key=candidate->>'name')
    or exists(select 1 from public.account_lifecycle_resources167 r where r.request_id=account_lifecycles167.id and r.kind='storage' and r.identity->>'bucket'=candidate->>'bucket_id' and r.identity->>'provider_key'=candidate->>'name')) loop
   raise exception 'account_provider_frozen';
  end loop;
 end loop;
 return new;
end;$$;
create trigger guard_account_provider_write167 before insert or update on storage.objects for each row execute function public.guard_account_provider_write167();

-- Cleanup workers carry the owning account identity into the filesystem fence.
create or replace function public.prepare_elearning_recording_cleanup(p_limit integer default 100,p_apply boolean default false) returns jsonb language plpgsql security definer set search_path='' as $$
declare candidate record;items jsonb:='[]';begin
 if p_limit is null or p_limit not between 1 and 500 then raise exception using errcode='22023',message='assessment_invalid_pagination';end if;
 for candidate in select o.tenant_id,o.user_id,o.storage_key,o.sha256,substring(o.storage_key from '/([0-9a-f-]{36})[.]wav$')::uuid recording_id
 from public.storage_objects o left join public.elearning_recording_cleanup d on (d.tenant_id,d.storage_key)=(o.tenant_id,o.storage_key)
 where o.category='elearning_assessment' and o.status='active' and o.user_id is not null and o.created_at<now()-interval '24 hours'
 and o.storage_key ~ ('^elearning-assessments/tenant_'||o.tenant_id||'/attempt_[0-9a-f-]{36}/[0-9a-f-]{36}[.]wav$')
 and d.completed_at is null and not exists(select 1 from public.elearning_assessment_recordings r join public.elearning_assessment_attempts t on (t.tenant_id,t.id)=(r.tenant_id,r.attempt_id)
 where r.tenant_id=o.tenant_id and r.storage_key=o.storage_key and (t.status='in_progress' or exists(select 1 from public.elearning_assessment_answers a where a.tenant_id=r.tenant_id and a.attempt_id=r.attempt_id and a.response->>'recording_id'=r.id::text)))
 order by o.created_at,o.id limit p_limit loop
 perform pg_advisory_xact_lock(125,candidate.tenant_id);
 if exists(select 1 from public.elearning_assessment_recordings r join public.elearning_assessment_attempts t on (t.tenant_id,t.id)=(r.tenant_id,r.attempt_id) where r.tenant_id=candidate.tenant_id and r.storage_key=candidate.storage_key and (t.status='in_progress' or exists(select 1 from public.elearning_assessment_answers a where a.tenant_id=r.tenant_id and a.attempt_id=r.attempt_id and a.response->>'recording_id'=r.id::text))) then continue;end if;
 if p_apply then insert into public.elearning_recording_cleanup(tenant_id,storage_key,recording_id) values(candidate.tenant_id,candidate.storage_key,candidate.recording_id) on conflict do nothing;end if;
 items:=items||jsonb_build_array(to_jsonb(candidate));
 end loop;return items;
end $$;

create or replace function public.claim_calendar_task_sync_jobs(
  p_worker_id text,
  p_limit integer default 10,
  p_now timestamptz default now()
)
returns setof public.calendar_task_sync_jobs
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.calendar_task_sync_jobs job
  set status = 'failed',
      leased_at = null,
      lease_owner = null,
      next_attempt_at = p_now,
      last_error_code = coalesce(job.last_error_code, 'worker_lease_expired')
  where job.status = 'processing'
    and job.leased_at < p_now - interval '2 minutes'
    and job.attempts < job.max_attempts;

  update public.calendar_task_sync_jobs job
  set status = 'failed',
      leased_at = null,
      lease_owner = null,
      last_error_code = coalesce(job.last_error_code, 'sync_attempts_exhausted')
  where job.status = 'processing'
    and job.leased_at < p_now - interval '2 minutes'
    and job.attempts >= job.max_attempts;

  return query
  update public.calendar_task_sync_jobs job
  set status = 'processing',
      attempts = job.attempts + 1,
      leased_at = p_now,
      lease_owner = left(p_worker_id, 120),
      last_error_code = null
  where job.id in (
    select candidate.id
    from public.calendar_task_sync_jobs candidate
    where candidate.status in ('pending', 'failed')
      and exists(select 1 from public.calendar_tasks t join public.users u on u.id=t.owner_user_id where t.id=candidate.task_id and u.account_status='active')
      and exists(select 1 from public.calendar_sync_connections c join public.users u on u.id=c.user_id where c.id=candidate.connection_id and u.account_status='active')
      and candidate.next_attempt_at <= p_now
      and candidate.attempts < candidate.max_attempts
    order by candidate.next_attempt_at, candidate.created_at
    limit greatest(1, least(coalesce(p_limit, 10), 50))
    for update skip locked
  )
  returning job.*;
end;
$$;

create or replace function public.claim_calendar_connection_sync_jobs(
  p_worker_id text,
  p_limit integer default 2,
  p_now timestamptz default now()
)
returns setof public.calendar_connection_sync_jobs
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.calendar_connection_sync_jobs job
  set status = 'failed',
      leased_at = null,
      lease_owner = null,
      next_attempt_at = p_now,
      last_error_code = coalesce(job.last_error_code, 'worker_lease_expired')
  where job.status = 'processing'
    and job.leased_at < p_now - interval '3 minutes'
    and job.attempts < job.max_attempts;
  update public.calendar_connection_sync_jobs job
  set status = 'failed',
      leased_at = null,
      lease_owner = null,
      completed_at = p_now,
      last_error_code = coalesce(job.last_error_code, 'sync_attempts_exhausted')
  where job.status = 'processing'
    and job.leased_at < p_now - interval '3 minutes'
    and job.attempts >= job.max_attempts;
  return query
  update public.calendar_connection_sync_jobs job
  set status = 'processing',
      attempts = job.attempts + 1,
      leased_at = p_now,
      lease_owner = left(p_worker_id, 120),
      last_error_code = null
  where job.id in (
    select candidate.id
    from public.calendar_connection_sync_jobs candidate
    where candidate.status in ('pending', 'failed')
      and exists(select 1 from public.calendar_sync_connections c join public.users u on u.id=c.user_id where c.id=candidate.connection_id and u.account_status='active')
      and candidate.next_attempt_at <= p_now
      and candidate.attempts < candidate.max_attempts
    order by candidate.next_attempt_at, candidate.created_at
    limit greatest(1, least(coalesce(p_limit, 2), 10))
    for update skip locked
  )
  returning job.*;
end;
$$;

create or replace function public.claim_due_data_source_syncs156(
  p_worker_id text, p_limit integer default 5, p_lease_seconds integer default 900,
  p_tenant_limit integer default 2, p_provider_limit integer default 4,
  p_now timestamptz default now()
)
returns table(
  schedule_id uuid,lease_token uuid,fence bigint,tenant_id integer,project_id uuid,
  source_id uuid,source_resource_id uuid,resource_key text,provider_key text,
  actor_user_id integer,credential_revision bigint,interval_seconds integer
)
language plpgsql security definer set search_path='' as $$
declare
  v_candidate record;
  v_schedule public.data_source_sync_schedules;
begin
  if length(p_worker_id) not between 3 and 200 or p_limit not between 1 and 50
     or p_lease_seconds not between 60 and 3600 or p_tenant_limit not between 1 and 20
     or p_provider_limit not between 1 and 50 then
    raise exception using errcode='22023',message='source_sync_claim_input_invalid';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('madar_source_sync_dispatch156',0));
  for v_candidate in
    with ranked as (
      select q.id,row_number() over(partition by q.tenant_id order by q.next_due_at,q.id) tenant_rank
      from public.data_source_sync_schedules q
      join public.data_sources s on s.id=q.source_id and s.tenant_id=q.tenant_id
        and s.project_id=q.project_id
      join public.builder_projects p on p.id=q.project_id and p.tenant_id=q.tenant_id
      join public.tenant_memberships m on m.tenant_id=q.tenant_id
        and m.user_id=s.creator_user_id and m.status='active' and m.role<>'learner'
      where exists(select 1 from public.users u where u.id=s.creator_user_id and u.account_status='active') and exists(select 1 from public.users u where u.id=p.owner_user_id and u.account_status='active') and q.enabled and q.status in ('idle','backoff','credential_attention','permanent_failure')
        and q.next_due_at<=p_now and s.status='active' and s.source_type='api_provider'
        and s.provider_key is not null and p.status<>'archived'
        and p.draft_schema->>'workspaceKind'='data'
        and not exists(select 1 from public.data_source_ingestion_runs r
          where r.source_resource_id=q.source_resource_id and r.status='processing')
        and (select count(*) from public.data_source_sync_schedules a
          where a.tenant_id=q.tenant_id and a.status='leased' and a.lease_expires_at>p_now)<p_tenant_limit
        and (select count(*) from public.data_source_sync_schedules a
          join public.data_sources x on x.id=a.source_id
          where x.provider_key=s.provider_key and a.status='leased' and a.lease_expires_at>p_now)<p_provider_limit
    )
    select q.id from ranked r join public.data_source_sync_schedules q on q.id=r.id
    where r.tenant_rank<=p_tenant_limit
    order by r.tenant_rank,q.next_due_at,q.tenant_id,q.id
    for update of q skip locked limit p_limit
  loop
    update public.data_source_sync_schedules q set
      status='leased',last_attempt_at=p_now,lease_token=gen_random_uuid(),
      lease_owner=p_worker_id,lease_expires_at=p_now+make_interval(secs=>p_lease_seconds),
      fence=q.fence+1,ingestion_run_id=null,diagnostic_metadata='{}'::jsonb
    where q.id=v_candidate.id
    returning * into v_schedule;
    insert into public.data_source_sync_attempts(
      schedule_id,tenant_id,project_id,source_id,source_resource_id,fence,credential_revision
    ) values(v_schedule.id,v_schedule.tenant_id,v_schedule.project_id,v_schedule.source_id,
      v_schedule.source_resource_id,v_schedule.fence,v_schedule.credential_revision);
    return query select v_schedule.id,v_schedule.lease_token,v_schedule.fence,
      v_schedule.tenant_id,v_schedule.project_id,v_schedule.source_id,
      v_schedule.source_resource_id,r.resource_key,s.provider_key,s.creator_user_id,
      s.credential_revision,v_schedule.interval_seconds
    from public.data_source_resources r join public.data_sources s on s.id=r.source_id
    where r.id=v_schedule.source_resource_id;
  end loop;
end;
$$;

create or replace function public.claim_data_source_webhook_events162(
  p_worker_id text,p_limit integer default 10,p_lease_seconds integer default 300,
  p_now timestamptz default now()
) returns setof public.data_source_webhook_events
language plpgsql security definer set search_path='' as $$
begin
  return query with candidates as (
    select e.id from public.data_source_webhook_events e
    join public.data_source_webhook_endpoints w on w.id=e.endpoint_id
    join public.data_sources s on s.id=e.source_id and s.tenant_id=e.tenant_id
    join public.data_source_credentials c on c.id=e.credential_id and c.source_id=e.source_id
      and c.tenant_id=e.tenant_id and c.project_id=e.project_id
    where e.status in ('pending','retry') and exists(select 1 from public.users u where u.id=s.creator_user_id and u.account_status='active') and exists(select 1 from public.builder_projects p join public.users u on u.id=p.owner_user_id where p.id=e.project_id and u.account_status='active') and e.next_attempt_at<=p_now
      and w.status='enabled' and w.fence=e.endpoint_fence and s.status='active'
      and w.credential_id=e.credential_id and w.credential_revision=e.credential_revision
      and s.active_credential_id=e.credential_id and s.credential_revision=e.credential_revision
      and c.status='active' and c.credential_version=e.credential_version
      and c.source_revision=e.credential_revision and (c.expires_at is null or c.expires_at>p_now)
      and not exists(select 1 from public.data_source_webhook_events a
        where a.source_resource_id=e.source_resource_id and a.status='leased')
    order by e.received_at for update of e skip locked limit greatest(1,least(p_limit,50))
  ) update public.data_source_webhook_events e set status='leased',attempts=attempts+1,
      lease_token=gen_random_uuid(),lease_owner=left(p_worker_id,200),
      lease_expires_at=p_now+make_interval(secs=>greatest(60,least(p_lease_seconds,1800))),
      lease_fence=lease_fence+1,error_category=null,diagnostic_metadata='{}'::jsonb
    from candidates c where e.id=c.id returning e.*;
end;
$$;

create or replace function public.claim_bi_report_runs164(
  p_worker_id text,p_limit integer,p_lease_seconds integer,p_now timestamptz
) returns setof public.bi_report_runs language plpgsql security definer set search_path='' as $$
declare candidate public.bi_report_runs;claimed public.bi_report_runs;claimed_count integer:=0;
begin
  if length(p_worker_id) not between 1 and 160 or p_limit not between 1 and 20 or p_lease_seconds not between 30 and 1800 then
    raise exception using errcode='22023',message='report_claim_bounds_invalid';end if;
  for candidate in select r.* from public.bi_report_runs r
    where r.status in ('queued','retry_pending') and exists(select 1 from public.users u where u.id=r.creator_user_id and u.account_status='active') and exists(select 1 from public.builder_projects p join public.users u on u.id=p.owner_user_id where p.id=r.project_id and u.account_status='active') and r.available_at<=p_now and r.attempts<r.max_attempts
      and (select count(*) from public.bi_report_runs x where x.tenant_id=r.tenant_id and x.status='running')<2
    order by r.available_at,r.created_at,r.id for update skip locked limit p_limit
  loop
    update public.bi_report_runs set status='running',lease_owner=p_worker_id,lease_token=gen_random_uuid(),
      lease_fence=lease_fence+1,lease_expires_at=p_now+make_interval(secs=>p_lease_seconds),
      last_heartbeat_at=p_now,started_at=coalesce(started_at,p_now),attempts=attempts+1,error_code=null
      where id=candidate.id returning * into claimed;
    return next claimed;claimed_count:=claimed_count+1;
    exit when claimed_count>=p_limit;
  end loop;
end;$$;

create function public.guard_account_hold167() returns trigger language plpgsql security definer set search_path='' as $$
begin
 if exists(select 1 from public.account_lifecycles167 where subject_id=old.id and state not in ('completed','reactivated')) and not public.erasure_scope_authorized167(old.id) then raise exception 'account_lifecycle_frozen';end if;
 if tg_op='DELETE' then return old;end if;return new;
end;$$;
create trigger guard_account_hold167 before update or delete on public.users for each row execute function public.guard_account_hold167();

create function public.account_session_allowed167(p_auth_id uuid,p_session_id uuid) returns boolean language plpgsql stable security definer set search_path='' as $$
declare ok boolean;
begin
 if not public.account_auth_contract167() then return false;end if;
 execute 'select exists(select 1 from public.users u join auth.sessions s on s.user_id=u.auth_id join auth.users a on a.id=u.auth_id where u.auth_id=$1 and s.id=$2 and u.account_status=''active'' and (a.banned_until is null or a.banned_until<=clock_timestamp()))' into ok using p_auth_id,p_session_id;
 return ok;
end;$$;
create function public.current_account_session167() returns boolean language plpgsql stable security definer set search_path='' as $$
declare claims jsonb;sub text;sid text;
begin
 claims:=coalesce(nullif(current_setting('request.jwt.claims',true),'')::jsonb,'{}'::jsonb);
 sub:=coalesce(claims->>'sub',nullif(current_setting('request.jwt.claim.sub',true),''));sid:=claims->>'session_id';
 if sub is null or sid is null then return false;end if;
 return public.account_session_allowed167(sub::uuid,sid::uuid);
exception when invalid_text_representation then return false;
end;$$;
create function public.guard_account_session167() returns trigger language plpgsql security definer set search_path='' as $$
declare uid integer;status text;
begin
 select id,account_status into uid,status from public.users where auth_id=new.user_id for share;
 if status='deletion_pending' or exists(select 1 from public.account_lifecycles167 where (subject_id=uid or auth_id=new.user_id) and state not in ('reactivated','completed')) then raise exception 'account_session_frozen';end if;
 return new;
end;$$;
do $$declare t record;begin
 if public.account_auth_contract167() then
   execute 'create trigger guard_account_session167 before insert or update on auth.sessions for each row execute function public.guard_account_session167()';
 end if;
 for t in select n.nspname,c.relname from pg_catalog.pg_class c join pg_catalog.pg_namespace n on n.oid=c.relnamespace where n.nspname in ('public','storage') and c.relkind='r' and c.relrowsecurity loop
  execute format('create policy account_session_required167 on %I.%I as restrictive for all to authenticated using(public.current_account_session167()) with check(public.current_account_session167())',t.nspname,t.relname);
 end loop;
end;$$;

-- Already-leased retention/delivery work must authorize before touching files.
alter function public.authorize_bi_report_cleanup166(uuid,uuid,bigint,timestamptz) rename to authorize_bi_report_cleanup_original166;
alter function public.authorize_bi_report_delivery166(uuid,uuid,bigint) rename to authorize_bi_report_delivery_original166;
create function public.authorize_bi_report_cleanup166(p_job_id uuid,p_lease_token uuid,p_lease_fence bigint,p_now timestamptz)
returns jsonb language plpgsql security definer set search_path='' as $$begin
 if exists(select 1 from public.bi_report_cleanup_jobs j join public.users u on u.id=j.owner_user_id where j.id=p_job_id and u.account_status<>'active') then raise exception 'account_processing_frozen';end if;
 return public.authorize_bi_report_cleanup_original166(p_job_id,p_lease_token,p_lease_fence,p_now);
end;$$;
create function public.authorize_bi_report_delivery166(p_delivery_id uuid,p_lease_token uuid,p_lease_fence bigint)
returns jsonb language plpgsql security definer set search_path='' as $$begin
 if exists(select 1 from public.bi_report_deliveries j join public.users u on u.id=j.owner_user_id or u.id=j.recipient_user_id where j.id=p_delivery_id and u.account_status<>'active') then raise exception 'account_processing_frozen';end if;
 return public.authorize_bi_report_delivery_original166(p_delivery_id,p_lease_token,p_lease_fence);
end;$$;

do $$declare f record;sig text;begin
 for f in select p.oid,p.proname from pg_catalog.pg_proc p join pg_catalog.pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and
 (p.proname like '%167' or p.proname in ('create_data_deletion_request','cancel_data_deletion_request_v2','authorize_bi_report_cleanup166','authorize_bi_report_delivery166','authorize_bi_report_cleanup_original166','authorize_bi_report_delivery_original166')) loop
  sig:=f.oid::regprocedure::text;
  execute format('revoke all on function %s from public,anon,authenticated,service_role',sig);
  if f.proname=any(array['reserve_account_restore_epoch167','account_restore_boundary167','account_fence_registration167','list_account_work167','account_lifecycle_capability167','create_account_action167','reactivate_account167','resume_account_erasure167','claim_account_erasure167','preflight_account_erasure167','inventory_account_erasure167','register_account_file167','release_account_database167','account_erasure_transition167','remove_account_subject167','complete_account_erasure167','account_session_allowed167','authorize_bi_report_cleanup166','authorize_bi_report_delivery166','account_recovery_capability167','create_data_deletion_request','cancel_data_deletion_request_v2']) then execute format('grant execute on function %s to service_role',sig);end if;
 end loop;
end;$$;
grant execute on function public.current_account_session167() to authenticated;
update public.application_schema_state set schema_version=167,applied_at=clock_timestamp() where contract_key='core';
notify pgrst,'reload schema';
commit;
