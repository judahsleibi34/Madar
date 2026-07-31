-- Destructive test data for the disposable migration-071 rehearsal only.

do $$
declare
  review_row public.legacy_billing_migration_reviews%rowtype;
begin
  if exists (
    select 1 from public.legacy_billing_migration_reviews where tenant_id=101
  ) then
    raise exception 'tenant_without_active_legacy_record_was_marked';
  end if;

  select * into review_row
  from public.legacy_billing_migration_reviews
  where tenant_id=102;
  if review_row.migration_state<>'mapped'
    or review_row.recommended_plan_id<>'forms'
    or review_row.active_legacy_record->>'plan'<>'basic'
  then
    raise exception 'inactive_higher_tier_changed_active_mapping';
  end if;

  if not exists (
    select 1 from public.legacy_billing_migration_reviews
    where tenant_id=104 and migration_state='review_required'
      and recommended_plan_id is null and active_legacy_feature_id is null
  ) then
    raise exception 'multiple_active_legacy_records_not_review_required';
  end if;

  if not exists (
    select 1 from public.legacy_billing_migration_reviews
    where tenant_id=105 and migration_state='review_required'
      and recommended_plan_id is null
      and active_legacy_record->>'plan'='starter'
  ) then
    raise exception 'ambiguous_active_legacy_label_not_review_required';
  end if;

  if (select standard_path_slug from public.website_settings where tenant_id=103)<>'foo-shop'
    or (select standard_path_slug from public.website_settings where tenant_id=105)<>'duplicate-shop-105'
    or (select standard_path_slug from public.website_settings where tenant_id=108)<>'site-108'
    or (select standard_path_slug from public.website_settings where tenant_id=109)<>'site-109'
    or (select standard_path_slug from public.website_settings where tenant_id=110)<>'site-109-110'
  then
    raise exception 'standard_path_slug_normalization_unexpected';
  end if;

  if exists (
    select 1 from public.website_settings
    where branded_subdomain_commercial_status<>'pending_review'
      or not legacy_subdomain_routing_preserved
  ) then
    raise exception 'legacy_route_was_commercially_grandfathered_or_not_preserved';
  end if;

  if not exists (
    select 1 from public.hosted_address_migration_reviews
    where tenant_id=106 and publication_state='published'
      and commercial_review_state='pending_review'
  ) or not exists (
    select 1 from public.hosted_address_migration_reviews
    where tenant_id=107 and publication_state='unpublished'
  ) or not exists (
    select 1 from public.hosted_address_migration_reviews
    where tenant_id=108 and commercial_review_state='pending_review'
  ) then
    raise exception 'hosted_address_review_provenance_incomplete';
  end if;

  if (select count(*) from public.builder_form_submissions)<>1
    or (select count(*) from public.builder_reservations)<>1
    or (select count(*) from public.calendar_events)<>1
    or (select used_bytes from public.storage_accounts where tenant_id=102)<>8589934592
    or (select message_count from public.ai_usage_daily where tenant_id=102)<>17
  then
    raise exception 'legacy_application_data_not_preserved';
  end if;
end
$$;

insert into public.ai_token_allocations (
  tenant_id,period_key,allocation_type,standard_tokens,idempotency_key
)
select
  tenant_id,
  to_char(now() at time zone 'UTC','YYYY-MM'),
  'migration',
  case when tenant_id in (104,105) then 300 else 1000 end,
  'rehearsal-allocation-'||tenant_id
from generate_series(101,105) tenant_id;

select * from public.reserve_ai_standard_tokens(
  101,(select id from public.users where tenant_id=101),
  to_char(now() at time zone 'UTC','YYYY-MM'),
  'rehearsal-below-101','analytics',400,now()+interval '15 minutes'
);
select * from public.finalize_ai_standard_tokens(
  'rehearsal-below-101','mock','mock','v1',250,0,50,300,300,
  'succeeded','provider',false
);

select * from public.reserve_ai_standard_tokens(
  102,(select id from public.users where tenant_id=102),
  to_char(now() at time zone 'UTC','YYYY-MM'),
  'rehearsal-equal-102','analytics',400,now()+interval '15 minutes'
);
select * from public.finalize_ai_standard_tokens(
  'rehearsal-equal-102','mock','mock','v1',350,0,50,400,400,
  'succeeded','provider',false
);

select * from public.reserve_ai_standard_tokens(
  103,(select id from public.users where tenant_id=103),
  to_char(now() at time zone 'UTC','YYYY-MM'),
  'rehearsal-over-103','analytics',200,now()+interval '15 minutes'
);
select * from public.finalize_ai_standard_tokens(
  'rehearsal-over-103','mock','mock','v1',450,0,50,500,500,
  'succeeded','provider',false
);

select * from public.reserve_ai_standard_tokens(
  104,(select id from public.users where tenant_id=104),
  to_char(now() at time zone 'UTC','YYYY-MM'),
  'rehearsal-deficit-104','analytics',200,now()+interval '15 minutes'
);
select * from public.finalize_ai_standard_tokens(
  'rehearsal-deficit-104','mock','mock','v1',450,0,50,500,500,
  'provider_error','provider_partial',false
);
-- Duplicate finalization must return the original ledger outcome.
select * from public.finalize_ai_standard_tokens(
  'rehearsal-deficit-104','mock','mock','v1',450,0,50,500,500,
  'provider_error','provider_partial',false
);

select * from public.reserve_ai_standard_tokens(
  105,(select id from public.users where tenant_id=105),
  to_char(now() at time zone 'UTC','YYYY-MM'),
  'rehearsal-expired-105','analytics',200,now()+interval '15 minutes'
);
update public.ai_token_reservations
set expires_at=now()-interval '1 second'
where request_id='rehearsal-expired-105';
select * from public.reserve_ai_standard_tokens(
  105,(select id from public.users where tenant_id=105),
  to_char(now() at time zone 'UTC','YYYY-MM'),
  'rehearsal-reuse-105','analytics',300,now()+interval '15 minutes'
);
select * from public.finalize_ai_standard_tokens(
  'rehearsal-reuse-105','mock','mock','v1',250,0,50,300,300,
  'succeeded','provider',false
);
select * from public.finalize_ai_standard_tokens(
  'rehearsal-expired-105','mock','mock','v1',80,0,20,100,100,
  'timeout','provider_partial',false
);

do $$
begin
  if not exists (
    select 1 from public.ai_token_ledger
    where request_id='rehearsal-below-101'
      and standard_tokens=300 and covered_standard_tokens=300
      and deficit_standard_tokens=0
  ) or not exists (
    select 1 from public.ai_token_ledger
    where request_id='rehearsal-equal-102'
      and standard_tokens=400 and covered_standard_tokens=400
  ) or not exists (
    select 1 from public.ai_token_ledger
    where request_id='rehearsal-over-103'
      and standard_tokens=500 and reservation_applied_tokens=200
      and additional_applied_tokens=300 and deficit_standard_tokens=0
  ) or not exists (
    select 1 from public.ai_token_ledger
    where request_id='rehearsal-deficit-104'
      and standard_tokens=500 and covered_standard_tokens=300
      and deficit_standard_tokens=200
      and request_status='provider_error' and usage_source='provider_partial'
  ) or not exists (
    select 1 from public.ai_token_ledger
    where request_id='rehearsal-expired-105'
      and standard_tokens=100 and covered_standard_tokens=0
      and deficit_standard_tokens=100 and request_status='timeout'
  ) then
    raise exception 'ai_token_rehearsal_assertion_failed';
  end if;

  if exists (
    select request_id from public.ai_token_ledger
    group by request_id having count(*)>1
  ) then
    raise exception 'ai_token_finalization_not_idempotent';
  end if;
end
$$;
