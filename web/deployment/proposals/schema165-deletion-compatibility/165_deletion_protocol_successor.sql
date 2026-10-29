-- UNSELECTED REVIEW PROPOSAL. Preparation only; DO NOT EXECUTE.
-- Not canonical history, not an admitted release, not a scope expansion.
begin;
do $$
declare current_schema integer;
begin
  select schema_version into current_schema
    from public.application_schema_state where contract_key='core' for update;
  if current_schema is distinct from 164 then
    raise exception 'proposal_165_expected_schema_164';
  end if;
  if public.notification_delivery_protocol() is distinct from 2
     or public.notification_outbox_protocol() is distinct from 2
     or public.data_deletion_ownership_protocol() is distinct from 0 then
    raise exception 'proposal_165_protocol_origin_invalid';
  end if;
  if exists(select 1 from public.data_deletion_requests
      where state in ('in_progress','pending','waiting_retry','waiting_retention'))
     or exists(select 1 from public.data_deletion_effects
      where state in ('intent','uncertain')) then
    raise exception 'proposal_165_requires_reconciled_deletion_work';
  end if;
end $$;

-- Exact165 horizon, not a permissive future-schema range. Existing function
-- identity/owner/ACL must be independently checked before and after execution.
create or replace function public.data_deletion_ownership_protocol()
returns integer language sql stable security definer set search_path=''
as $$ select case when (select schema_version
  from public.application_schema_state where contract_key='core')=165
  then 2 else 0 end $$;

update public.application_schema_state set schema_version=165,
  applied_at=clock_timestamp() where contract_key='core';
commit;
