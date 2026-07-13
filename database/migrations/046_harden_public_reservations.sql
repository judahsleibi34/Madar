-- Idempotent public reservations, bounded collision prevention, and safe cancellation.
begin;

alter table public.builder_reservations
  add column if not exists idempotency_key_hash text;
alter table public.builder_reservations
  add column if not exists request_hash text;
alter table public.builder_reservations
  add column if not exists exclusive_slot boolean not null default false;
alter table public.builder_reservations
  add column if not exists cancellation_token_hash text;
alter table public.builder_reservations
  add column if not exists cancellation_expires_at timestamptz;
alter table public.builder_reservations
  add column if not exists cancelled_at timestamptz;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'builder_reservations_time_order_check'
      and conrelid = 'public.builder_reservations'::regclass
  ) then
    alter table public.builder_reservations
      add constraint builder_reservations_time_order_check
      check (starts_at is null or ends_at is null or starts_at < ends_at) not valid;
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname = 'builder_reservations_idempotency_hash_check'
      and conrelid = 'public.builder_reservations'::regclass
  ) then
    alter table public.builder_reservations
      add constraint builder_reservations_idempotency_hash_check
      check (idempotency_key_hash is null or idempotency_key_hash ~ '^[0-9a-f]{64}$') not valid;
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname = 'builder_reservations_request_hash_check'
      and conrelid = 'public.builder_reservations'::regclass
  ) then
    alter table public.builder_reservations
      add constraint builder_reservations_request_hash_check
      check (request_hash is null or request_hash ~ '^[0-9a-f]{64}$') not valid;
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname = 'builder_reservations_cancellation_hash_check'
      and conrelid = 'public.builder_reservations'::regclass
  ) then
    alter table public.builder_reservations
      add constraint builder_reservations_cancellation_hash_check
      check (cancellation_token_hash is null or cancellation_token_hash ~ '^[0-9a-f]{64}$') not valid;
  end if;
end $$;

create unique index if not exists builder_reservations_idempotency_unique_idx
on public.builder_reservations (tenant_id, project_id, block_id, idempotency_key_hash)
where idempotency_key_hash is not null;

create index if not exists builder_reservations_active_slot_idx
on public.builder_reservations (tenant_id, project_id, block_id, starts_at, ends_at)
where status in ('new', 'confirmed');

create unique index if not exists builder_reservations_cancellation_token_unique_idx
on public.builder_reservations (cancellation_token_hash)
where cancellation_token_hash is not null;

create or replace function public.create_builder_reservation_safe(
  p_reservation jsonb,
  p_idempotency_key_hash text,
  p_request_hash text,
  p_exclusive_slot boolean default false
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  p_tenant_id integer;
  p_project_id uuid;
  p_block_id text;
  p_starts_at timestamptz;
  p_ends_at timestamptz;
  existing_row public.builder_reservations;
  saved_row public.builder_reservations;
begin
  if jsonb_typeof(p_reservation) <> 'object' then
    raise exception using errcode = 'P0001', message = 'reservation_payload_invalid';
  end if;

  p_tenant_id := nullif(p_reservation ->> 'tenant_id', '')::integer;
  p_project_id := nullif(p_reservation ->> 'project_id', '')::uuid;
  p_block_id := nullif(p_reservation ->> 'block_id', '');
  p_starts_at := nullif(p_reservation ->> 'starts_at', '')::timestamptz;
  p_ends_at := nullif(p_reservation ->> 'ends_at', '')::timestamptz;

  if p_tenant_id is null or p_project_id is null or p_block_id is null then
    raise exception using errcode = 'P0001', message = 'reservation_payload_invalid';
  end if;
  if p_request_hash is null or p_request_hash !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = 'P0001', message = 'reservation_payload_invalid';
  end if;
  if p_idempotency_key_hash is not null and p_idempotency_key_hash !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = 'P0001', message = 'idempotency_key_invalid';
  end if;
  if not exists (
    select 1 from public.builder_projects
    where id = p_project_id and tenant_id = p_tenant_id and status = 'published'
  ) then
    raise exception using errcode = 'P0002', message = 'builder_project_not_found';
  end if;
  if p_starts_at is not null and p_ends_at is not null and p_starts_at >= p_ends_at then
    raise exception using errcode = 'P0001', message = 'reservation_time_invalid';
  end if;
  if p_exclusive_slot and p_starts_at is null then
    raise exception using errcode = 'P0001', message = 'reservation_time_required';
  end if;

  -- Serialize writers for one published block. The transaction-scoped lock keeps
  -- overlap checks and inserts race-free without imposing a new exclusion
  -- constraint on historical data.
  perform pg_advisory_xact_lock(hashtext(
    concat_ws(':', 'builder-reservation', p_tenant_id, p_project_id, p_block_id)
  ));

  if p_idempotency_key_hash is not null then
    select * into existing_row
    from public.builder_reservations
    where tenant_id = p_tenant_id
      and project_id = p_project_id
      and block_id = p_block_id
      and idempotency_key_hash = p_idempotency_key_hash
    for update;

    if found then
      if existing_row.request_hash is distinct from p_request_hash then
        raise exception using errcode = 'P0001', message = 'idempotency_conflict';
      end if;
      return jsonb_build_object('duplicate', true, 'reservation', to_jsonb(existing_row));
    end if;
  end if;

  if p_exclusive_slot and exists (
    select 1
    from public.builder_reservations reservation
    where reservation.tenant_id = p_tenant_id
      and reservation.project_id = p_project_id
      and reservation.block_id = p_block_id
      and reservation.status in ('new', 'confirmed')
      and (
        (
          p_ends_at is null
          and (
            reservation.starts_at = p_starts_at
            or (
              reservation.ends_at is not null
              and reservation.starts_at <= p_starts_at
              and reservation.ends_at > p_starts_at
            )
          )
        )
        or (
          p_ends_at is not null
          and (
            (
              reservation.ends_at is null
              and reservation.starts_at >= p_starts_at
              and reservation.starts_at < p_ends_at
            )
            or (
              reservation.ends_at is not null
              and reservation.starts_at < p_ends_at
              and reservation.ends_at > p_starts_at
            )
          )
        )
      )
  ) then
    raise exception using errcode = 'P0001', message = 'reservation_slot_unavailable';
  end if;

  insert into public.builder_reservations (
    tenant_id,
    project_id,
    site_subdomain,
    block_id,
    block_type,
    reservation_title,
    customer_name,
    customer_email,
    customer_phone,
    starts_at,
    ends_at,
    timezone,
    status,
    payload,
    field_snapshot,
    submitter_ip,
    user_agent,
    idempotency_key_hash,
    request_hash,
    exclusive_slot,
    cancellation_token_hash,
    cancellation_expires_at
  ) values (
    p_tenant_id,
    p_project_id,
    nullif(p_reservation ->> 'site_subdomain', ''),
    p_block_id,
    nullif(p_reservation ->> 'block_type', ''),
    nullif(p_reservation ->> 'reservation_title', ''),
    nullif(p_reservation ->> 'customer_name', ''),
    nullif(p_reservation ->> 'customer_email', ''),
    nullif(p_reservation ->> 'customer_phone', ''),
    p_starts_at,
    p_ends_at,
    nullif(p_reservation ->> 'timezone', ''),
    coalesce(nullif(p_reservation ->> 'status', ''), 'new'),
    coalesce(p_reservation -> 'payload', '{}'::jsonb),
    coalesce(p_reservation -> 'field_snapshot', '[]'::jsonb),
    nullif(p_reservation ->> 'submitter_ip', ''),
    nullif(p_reservation ->> 'user_agent', ''),
    p_idempotency_key_hash,
    p_request_hash,
    p_exclusive_slot,
    nullif(p_reservation ->> 'cancellation_token_hash', ''),
    nullif(p_reservation ->> 'cancellation_expires_at', '')::timestamptz
  )
  returning * into saved_row;

  return jsonb_build_object('duplicate', false, 'reservation', to_jsonb(saved_row));
end;
$$;

revoke all on function public.create_builder_reservation_safe(jsonb, text, text, boolean)
from public, anon, authenticated;
grant execute on function public.create_builder_reservation_safe(jsonb, text, text, boolean)
to service_role;

create or replace function public.cancel_builder_reservation_safe(
  p_reservation_id uuid,
  p_token_hash text,
  p_cancelled_at timestamptz default now()
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  reservation_row public.builder_reservations;
begin
  select * into reservation_row
  from public.builder_reservations
  where id = p_reservation_id
  for update;

  if not found
    or reservation_row.cancellation_token_hash is null
    or reservation_row.cancellation_token_hash is distinct from p_token_hash
  then
    raise exception using errcode = 'P0002', message = 'reservation_cancellation_invalid';
  end if;
  if reservation_row.cancellation_expires_at is not null
    and reservation_row.cancellation_expires_at <= p_cancelled_at
  then
    raise exception using errcode = 'P0001', message = 'reservation_cancellation_expired';
  end if;
  if reservation_row.status = 'cancelled' then
    raise exception using errcode = 'P0001', message = 'reservation_cancellation_replayed';
  end if;
  if reservation_row.status in ('completed', 'rejected') then
    raise exception using errcode = 'P0001', message = 'reservation_cancellation_unavailable';
  end if;

  update public.builder_reservations
  set status = 'cancelled', cancelled_at = p_cancelled_at
  where id = p_reservation_id
  returning * into reservation_row;

  return to_jsonb(reservation_row);
end;
$$;

revoke all on function public.cancel_builder_reservation_safe(uuid, text, timestamptz)
from public, anon, authenticated;
grant execute on function public.cancel_builder_reservation_safe(uuid, text, timestamptz)
to service_role;

notify pgrst, 'reload schema';
commit;
