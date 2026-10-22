begin;
-- Reconciled forward migration; original architecture SQL is archived unchanged.

do $$
declare
  v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version into v_schema_version from public.application_schema_state
  where contract_key = 'core' for update;
  if v_schema_version is null then raise exception using errcode='P0001',message='migration_158_schema_state_missing'; end if;
  if v_schema_version <> 157 then raise exception using errcode='P0001',message='migration_158_expected_schema_157'; end if;
end;
$$;

create or replace function public.update_builder_reservation_status_notified_safe(
  p_reservation_id uuid,
  p_tenant_id integer,
  p_status text,
  p_updated_at timestamptz default now()
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  reservation_row public.builder_reservations;
  v_project_id uuid;
  v_block_id text;
begin
  if p_status is null or p_status not in ('new','confirmed','cancelled','completed','rejected') then
    raise exception using errcode='P0001',message='reservation_status_invalid';
  end if;
  -- Match create_builder_reservation_safe's lock order: block, then row.
  -- Taking the row first could deadlock a concurrent idempotent create retry.
  select project_id,block_id into v_project_id,v_block_id
  from public.builder_reservations where id=p_reservation_id and tenant_id=p_tenant_id;
  if not found then return null; end if;
  perform pg_advisory_xact_lock(hashtext(concat_ws(':','builder-reservation',p_tenant_id,v_project_id,v_block_id)));
  select * into reservation_row from public.builder_reservations
  where id=p_reservation_id and tenant_id=p_tenant_id for update;
  if not found then return null; end if;
  if reservation_row.project_id is distinct from v_project_id or reservation_row.block_id is distinct from v_block_id then
    raise exception using errcode='40001',message='reservation_identity_changed';
  end if;
  if p_status in ('new','confirmed') and reservation_row.exclusive_slot then
    if reservation_row.starts_at is null then
      raise exception using errcode='P0001',message='reservation_time_required';
    end if;
    if exists (
      select 1 from public.builder_reservations other
      where other.tenant_id=p_tenant_id and other.project_id=v_project_id and other.block_id=v_block_id
        and other.id<>p_reservation_id and other.status in ('new','confirmed')
        and ((reservation_row.ends_at is null and
              (other.starts_at=reservation_row.starts_at or
               (other.ends_at is not null and other.starts_at<=reservation_row.starts_at and other.ends_at>reservation_row.starts_at)))
          or (reservation_row.ends_at is not null and
              ((other.ends_at is null and other.starts_at>=reservation_row.starts_at and other.starts_at<reservation_row.ends_at)
               or (other.ends_at is not null and other.starts_at<reservation_row.ends_at and other.ends_at>reservation_row.starts_at))))
    ) then raise exception using errcode='P0001',message='reservation_slot_unavailable'; end if;
  end if;
  update public.builder_reservations
  set status = p_status, updated_at = p_updated_at
  where id = p_reservation_id and tenant_id = p_tenant_id
  returning * into reservation_row;
  if not found then
    return null;
  end if;
  if nullif(btrim(reservation_row.customer_email), '') is not null then
    insert into public.notification_outbox (
      tenant_id, channel, template, recipient_reference, payload, status,
      available_at, deduplication_key, retention_until
    ) values (
      reservation_row.tenant_id, 'email', 'reservation_status_changed',
      concat('reservation:', reservation_row.id),
      jsonb_build_object('reservation_id', reservation_row.id, 'status', reservation_row.status),
      'pending', now(),
      concat('reservation-status:', reservation_row.id, ':', reservation_row.status),
      now() + interval '90 days'
    ) on conflict do nothing;
  end if;
  return to_jsonb(reservation_row);
end;
$$;

-- Production SDK paths already use the notified status/cancellation RPCs.
-- Do not permit an accidental direct UPDATE to bypass their capacity lock.
revoke update on public.builder_reservations from public,anon,authenticated,service_role;
revoke all on function public.update_builder_reservation_status_notified_safe(uuid,integer,text,timestamptz)
  from public,anon,authenticated;
grant execute on function public.update_builder_reservation_status_notified_safe(uuid,integer,text,timestamptz) to service_role;

update public.application_schema_state set schema_version=158,applied_at=now()
where contract_key = 'core';
notify pgrst,'reload schema';
commit;
