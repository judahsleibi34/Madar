-- Per-recipient durable notification delivery, event idempotency, and cleanup.
-- Apply this migration before deploying the Phase 2 worker/application image.
begin;

create extension if not exists pgcrypto;

alter table public.notification_events
  add column if not exists deduplication_key text;

create unique index if not exists notification_events_tenant_dedup_unique_idx
on public.notification_events (tenant_id, deduplication_key)
where deduplication_key is not null;

create table if not exists public.notification_deliveries (
  id uuid primary key default gen_random_uuid(),
  outbox_id uuid references public.notification_outbox(id) on delete set null,
  tenant_id integer references public.tenants(tenant_id) on delete cascade,
  event_id uuid references public.notification_events(id) on delete cascade,
  user_notification_id uuid references public.user_notifications(id) on delete set null,
  user_id integer references public.users(id) on delete set null,
  subscription_id uuid references public.web_push_subscriptions(id) on delete set null,
  channel text not null,
  template text not null,
  recipient_hash text,
  recipient_reference text,
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'pending',
  attempts integer not null default 0,
  max_attempts integer not null default 5,
  available_at timestamptz not null default now(),
  processing_started_at timestamptz,
  processing_lease_until timestamptz,
  sent_at timestamptz,
  dead_at timestamptz,
  last_error_code text,
  last_error_detail_safe text,
  provider_message_id text,
  deduplication_key text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  retention_until timestamptz not null default (now() + interval '90 days'),
  constraint notification_deliveries_channel_check
    check (channel in ('internal', 'email', 'web_push')),
  constraint notification_deliveries_status_check
    check (status in ('pending', 'processing', 'sent', 'dead')),
  constraint notification_deliveries_attempts_check
    check (attempts >= 0 and max_attempts between 1 and 20),
  constraint notification_deliveries_payload_object_check
    check (jsonb_typeof(payload) = 'object'),
  constraint notification_deliveries_recipient_hash_check
    check (recipient_hash is null or recipient_hash ~ '^[0-9a-f]{64}$'),
  constraint notification_deliveries_error_code_check
    check (last_error_code is null or last_error_code ~ '^[a-z0-9_.-]{1,100}$'),
  constraint notification_deliveries_dedup_unique unique (deduplication_key)
);

create index if not exists notification_deliveries_claim_idx
on public.notification_deliveries (available_at, created_at)
where status = 'pending';

create index if not exists notification_deliveries_lease_idx
on public.notification_deliveries (processing_lease_until)
where status = 'processing';

create index if not exists notification_deliveries_outbox_status_idx
on public.notification_deliveries (outbox_id, status);

create index if not exists notification_deliveries_tenant_event_user_idx
on public.notification_deliveries (tenant_id, event_id, user_id);

create index if not exists notification_deliveries_subscription_idx
on public.notification_deliveries (subscription_id)
where subscription_id is not null;

create index if not exists notification_deliveries_retention_idx
on public.notification_deliveries (retention_until)
where status in ('sent', 'dead');

create index if not exists notification_deliveries_dead_tenant_idx
on public.notification_deliveries (tenant_id, created_at desc)
where status = 'dead';

drop trigger if exists set_notification_deliveries_updated_at
on public.notification_deliveries;
create trigger set_notification_deliveries_updated_at
before update on public.notification_deliveries
for each row execute function public.set_updated_at();

alter table public.notification_deliveries enable row level security;
revoke all on public.notification_deliveries from anon, authenticated;
grant select, insert, update, delete on public.notification_deliveries to service_role;

create or replace function public.create_notification_event_intent(
  p_tenant_id integer,
  p_event_type text,
  p_source_type text,
  p_source_id text,
  p_title text,
  p_body text,
  p_data jsonb,
  p_deduplication_key text
)
returns public.notification_events
language plpgsql
security definer
set search_path = public
as $$
declare
  event_row public.notification_events;
begin
  if p_tenant_id is null
    or nullif(btrim(p_event_type), '') is null
    or nullif(btrim(p_source_type), '') is null
    or nullif(btrim(p_title), '') is null
    or nullif(btrim(p_deduplication_key), '') is null
    or jsonb_typeof(coalesce(p_data, '{}'::jsonb)) <> 'object'
  then
    raise exception using errcode = 'P0001', message = 'notification_event_invalid';
  end if;

  insert into public.notification_events (
    tenant_id, event_type, source_type, source_id, title, body, data,
    deduplication_key
  ) values (
    p_tenant_id, left(p_event_type, 120), left(p_source_type, 120),
    nullif(left(coalesce(p_source_id, ''), 200), ''), left(p_title, 200),
    left(coalesce(p_body, ''), 1000), coalesce(p_data, '{}'::jsonb),
    left(p_deduplication_key, 240)
  )
  on conflict (tenant_id, deduplication_key)
    where deduplication_key is not null
  do update set tenant_id = excluded.tenant_id
  returning * into event_row;

  begin
    insert into public.notification_outbox (
      tenant_id, channel, template, recipient_reference, payload, status,
      available_at, deduplication_key, retention_until
    ) values (
      p_tenant_id,
      'internal',
      'tenant_event',
      concat('tenant:', p_tenant_id),
      jsonb_build_object(
        'event_id', event_row.id,
        'event_type', event_row.event_type,
        'source_type', event_row.source_type,
        'source_id', event_row.source_id,
        'title', event_row.title,
        'body', event_row.body,
        'data', event_row.data,
        'event_deduplication_key', event_row.deduplication_key
      ),
      'pending', now(), left(p_deduplication_key, 240), now() + interval '90 days'
    );
  exception when unique_violation then
    null;
  end;

  return event_row;
end;
$$;

create or replace function public.get_or_create_notification_event(
  p_tenant_id integer,
  p_event_type text,
  p_source_type text,
  p_source_id text,
  p_title text,
  p_body text,
  p_data jsonb,
  p_deduplication_key text
)
returns public.notification_events
language plpgsql
security definer
set search_path = public
as $$
declare
  event_row public.notification_events;
begin
  if p_tenant_id is null
    or nullif(btrim(p_event_type), '') is null
    or nullif(btrim(p_source_type), '') is null
    or nullif(btrim(p_title), '') is null
    or nullif(btrim(p_deduplication_key), '') is null
  then
    raise exception using errcode = 'P0001', message = 'notification_event_invalid';
  end if;
  insert into public.notification_events (
    tenant_id, event_type, source_type, source_id, title, body, data,
    deduplication_key
  ) values (
    p_tenant_id, left(p_event_type, 120), left(p_source_type, 120),
    nullif(left(coalesce(p_source_id, ''), 200), ''), left(p_title, 200),
    left(coalesce(p_body, ''), 1000), coalesce(p_data, '{}'::jsonb),
    left(p_deduplication_key, 240)
  )
  on conflict (tenant_id, deduplication_key)
    where deduplication_key is not null
  do update set tenant_id = excluded.tenant_id
  returning * into event_row;
  return event_row;
end;
$$;

create or replace function public.resolve_notification_outbox(
  p_outbox_id uuid,
  p_now timestamptz default now()
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  work public.notification_outbox;
  inserted_count integer := 0;
  affected integer := 0;
  canonical_event_id uuid;
begin
  select * into work
  from public.notification_outbox
  where id = p_outbox_id
  for update;

  if not found or work.status <> 'processing' then
    raise exception using errcode = 'P0001', message = 'notification_outbox_state_conflict';
  end if;

  if work.template = 'tenant_event' then
    begin
      canonical_event_id := nullif(work.payload ->> 'event_id', '')::uuid;
    exception when invalid_text_representation then
      raise exception using errcode = 'P0001', message = 'notification_event_reference_invalid';
    end;
    if canonical_event_id is null then
      select event.id into canonical_event_id
      from public.notification_events event
      where event.tenant_id = work.tenant_id
        and event.event_type = work.payload ->> 'event_type'
        and event.source_type = work.payload ->> 'source_type'
        and event.source_id is not distinct from nullif(work.payload ->> 'source_id', '')
      order by event.created_at
      limit 1;
    end if;
    if canonical_event_id is null then
      select event.id into canonical_event_id
      from public.get_or_create_notification_event(
        work.tenant_id,
        work.payload ->> 'event_type',
        work.payload ->> 'source_type',
        work.payload ->> 'source_id',
        work.payload ->> 'title',
        work.payload ->> 'body',
        coalesce(work.payload -> 'data', '{}'::jsonb),
        coalesce(work.deduplication_key, concat('legacy-outbox:', work.id))
      ) event;
    end if;
    if not exists (
      select 1 from public.notification_events event
      where event.id = canonical_event_id and event.tenant_id = work.tenant_id
    ) then
      raise exception using errcode = 'P0001', message = 'notification_event_reference_invalid';
    end if;
  end if;

  if work.channel = 'internal' then
    insert into public.notification_deliveries (
      outbox_id, tenant_id, event_id, user_id, channel, template,
      recipient_reference, payload, deduplication_key, retention_until
    )
    select
      work.id, work.tenant_id, canonical_event_id, membership.user_id,
      'internal', work.template, concat('user:', membership.user_id), work.payload,
      concat('outbox:', work.id, ':internal:user:', membership.user_id),
      coalesce(work.retention_until, p_now + interval '90 days')
    from public.tenant_memberships membership
    where membership.tenant_id = work.tenant_id
      and membership.status = 'active'
      and (work.user_id is null or membership.user_id = work.user_id)
    on conflict (deduplication_key) do nothing;
    get diagnostics affected = row_count;
    inserted_count := inserted_count + affected;

    -- Canonical tenant events also create one independent push delivery per
    -- currently authorized active browser subscription.
    if work.template = 'tenant_event' then
      insert into public.notification_deliveries (
        outbox_id, tenant_id, event_id, user_id, subscription_id, channel,
        template, recipient_reference, payload, deduplication_key,
        retention_until
      )
      select
        work.id, work.tenant_id, canonical_event_id, membership.user_id,
        subscription.id, 'web_push', work.template,
        concat('subscription:', subscription.id), work.payload,
        concat('outbox:', work.id, ':web_push:subscription:', subscription.id),
        coalesce(work.retention_until, p_now + interval '90 days')
      from public.tenant_memberships membership
      join public.web_push_subscriptions subscription
        on subscription.user_id = membership.user_id
       and subscription.tenant_id = membership.tenant_id
       and subscription.revoked_at is null
      where membership.tenant_id = work.tenant_id
        and membership.status = 'active'
        and (work.user_id is null or membership.user_id = work.user_id)
      on conflict (deduplication_key) do nothing;
      get diagnostics affected = row_count;
      inserted_count := inserted_count + affected;
    end if;
  elsif work.channel = 'web_push' then
    insert into public.notification_deliveries (
      outbox_id, tenant_id, user_id, subscription_id, channel, template,
      recipient_reference, payload, deduplication_key, retention_until
    )
    select
      work.id, work.tenant_id, membership.user_id, subscription.id,
      'web_push', work.template, concat('subscription:', subscription.id),
      work.payload,
      concat('outbox:', work.id, ':web_push:subscription:', subscription.id),
      coalesce(work.retention_until, p_now + interval '90 days')
    from public.tenant_memberships membership
    join public.web_push_subscriptions subscription
      on subscription.user_id = membership.user_id
     and subscription.tenant_id = membership.tenant_id
     and subscription.revoked_at is null
    where membership.tenant_id = work.tenant_id
      and membership.status = 'active'
      and (work.user_id is null or membership.user_id = work.user_id)
    on conflict (deduplication_key) do nothing;
    get diagnostics affected = row_count;
    inserted_count := inserted_count + affected;
  elsif work.channel = 'email' then
    insert into public.notification_deliveries (
      outbox_id, tenant_id, user_id, channel, template, recipient_hash,
      recipient_reference, payload, deduplication_key, retention_until
    ) values (
      work.id, work.tenant_id, work.user_id, 'email', work.template,
      work.recipient_hash, work.recipient_reference, work.payload,
      concat('outbox:', work.id, ':email'),
      coalesce(work.retention_until, p_now + interval '90 days')
    ) on conflict (deduplication_key) do nothing;
    get diagnostics affected = row_count;
    inserted_count := inserted_count + affected;
  else
    raise exception using errcode = 'P0001', message = 'notification_channel_unsupported';
  end if;

  update public.notification_outbox
  set status = 'sent', sent_at = p_now, processing_started_at = null,
      last_error_code = null
  where id = work.id;

  return inserted_count;
end;
$$;

create or replace function public.claim_notification_deliveries(
  p_limit integer default 25,
  p_now timestamptz default now(),
  p_lease_seconds integer default 900
)
returns setof public.notification_deliveries
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.notification_deliveries delivery
  set status = 'dead', dead_at = p_now, processing_started_at = null,
      processing_lease_until = null,
      last_error_code = coalesce(delivery.last_error_code, 'delivery_attempts_exhausted'),
      retention_until = greatest(delivery.retention_until, p_now + interval '180 days')
  where delivery.status = 'processing'
    and delivery.processing_lease_until <= p_now
    and delivery.attempts >= delivery.max_attempts;

  return query
  update public.notification_deliveries delivery
  set status = 'processing',
      attempts = delivery.attempts + 1,
      processing_started_at = p_now,
      processing_lease_until = p_now + make_interval(
        secs => greatest(30, least(coalesce(p_lease_seconds, 900), 3600))
      ),
      last_error_code = null,
      last_error_detail_safe = null
  where delivery.id in (
    select candidate.id
    from public.notification_deliveries candidate
    where (
      (candidate.status = 'pending' and candidate.available_at <= p_now)
      or (
        candidate.status = 'processing'
        and candidate.processing_lease_until <= p_now
      )
    )
      and candidate.attempts < candidate.max_attempts
    order by candidate.available_at, candidate.created_at
    limit greatest(1, least(coalesce(p_limit, 25), 100))
    for update skip locked
  )
  returning delivery.*;
end;
$$;

create or replace function public.finish_notification_delivery(
  p_delivery_id uuid,
  p_outcome text,
  p_error_code text default null,
  p_error_detail_safe text default null,
  p_available_at timestamptz default null,
  p_provider_message_id text default null,
  p_finished_at timestamptz default now()
)
returns public.notification_deliveries
language plpgsql
security definer
set search_path = public
as $$
declare
  delivery public.notification_deliveries;
  terminal boolean;
begin
  if p_outcome not in ('sent', 'retry', 'dead', 'revoked') then
    raise exception using errcode = 'P0001', message = 'notification_delivery_outcome_invalid';
  end if;
  select * into delivery
  from public.notification_deliveries
  where id = p_delivery_id
  for update;
  if not found or delivery.status <> 'processing' then
    raise exception using errcode = 'P0001', message = 'notification_delivery_state_conflict';
  end if;

  terminal := p_outcome in ('dead', 'revoked')
    or (p_outcome = 'retry' and delivery.attempts >= delivery.max_attempts);
  update public.notification_deliveries
  set status = case
        when p_outcome = 'sent' then 'sent'
        when terminal then 'dead'
        else 'pending'
      end,
      sent_at = case when p_outcome = 'sent' then p_finished_at else null end,
      dead_at = case when terminal then p_finished_at else null end,
      available_at = case
        when p_outcome = 'retry' and not terminal
          then coalesce(p_available_at, p_finished_at + interval '1 minute')
        else available_at
      end,
      processing_started_at = null,
      processing_lease_until = null,
      last_error_code = case when p_outcome = 'sent' then null else p_error_code end,
      last_error_detail_safe = case
        when p_outcome = 'sent' then null else left(p_error_detail_safe, 500)
      end,
      provider_message_id = case
        when p_outcome = 'sent' then left(p_provider_message_id, 200)
        else provider_message_id
      end,
      retention_until = case
        when terminal then greatest(retention_until, p_finished_at + interval '180 days')
        else retention_until
      end
  where id = p_delivery_id
  returning * into delivery;
  return delivery;
end;
$$;

create or replace function public.cleanup_notification_delivery_data(
  p_now timestamptz default now(),
  p_limit integer default 1000
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  deleted_deliveries integer := 0;
  deleted_outbox integer := 0;
begin
  with candidates as (
    select id from public.notification_deliveries
    where status in ('sent', 'dead') and retention_until <= p_now
    order by retention_until
    limit greatest(1, least(coalesce(p_limit, 1000), 10000))
    for update skip locked
  )
  delete from public.notification_deliveries delivery
  using candidates where delivery.id = candidates.id;
  get diagnostics deleted_deliveries = row_count;

  with candidates as (
    select id from public.notification_outbox
    where status in ('sent', 'dead')
      and retention_until is not null and retention_until <= p_now
      and not exists (
        select 1 from public.notification_deliveries delivery
        where delivery.outbox_id = notification_outbox.id
          and delivery.status in ('pending', 'processing')
      )
    order by retention_until
    limit greatest(1, least(coalesce(p_limit, 1000), 10000))
    for update skip locked
  )
  delete from public.notification_outbox outbox
  using candidates where outbox.id = candidates.id;
  get diagnostics deleted_outbox = row_count;

  return jsonb_build_object(
    'deliveries', deleted_deliveries,
    'outbox', deleted_outbox
  );
end;
$$;

create or replace function public.enqueue_calendar_reminder_notification(
  p_reminder_source text,
  p_reminder_id uuid,
  p_scheduled_for timestamptz,
  p_tenant_id integer,
  p_user_id integer,
  p_channel text,
  p_recipient_reference text,
  p_deduplication_key text,
  p_payload jsonb
)
returns public.notification_outbox
language plpgsql
security definer
set search_path = public
as $$
declare
  queued public.notification_outbox;
begin
  if p_reminder_source not in ('event', 'task')
    or p_channel not in ('internal', 'email', 'web_push')
    or jsonb_typeof(coalesce(p_payload, '{}'::jsonb)) <> 'object'
    or nullif(p_deduplication_key, '') is null
  then
    raise exception using errcode = 'P0001', message = 'calendar_reminder_enqueue_invalid';
  end if;

  if p_reminder_source = 'event' then
    perform 1 from public.calendar_event_reminders
    where id = p_reminder_id and tenant_id = p_tenant_id
      and delivery_status = 'scheduled'
      and scheduled_for is not distinct from p_scheduled_for
    for update;
  else
    perform 1 from public.calendar_task_reminders
    where id = p_reminder_id and tenant_id = p_tenant_id
      and delivery_status = 'scheduled'
      and scheduled_for is not distinct from p_scheduled_for
    for update;
  end if;
  if not found then
    return null;
  end if;

  begin
    insert into public.notification_outbox (
      tenant_id,user_id,channel,template,recipient_reference,payload,status,
      available_at,deduplication_key,retention_until
    ) values (
      p_tenant_id,p_user_id,p_channel,'calendar_reminder',
      nullif(p_recipient_reference,''),coalesce(p_payload,'{}'::jsonb),'pending',
      now(),left(p_deduplication_key,240),now()+interval '90 days'
    ) returning * into queued;
  exception when unique_violation then
    select * into queued from public.notification_outbox
    where tenant_id = p_tenant_id and channel = p_channel
      and deduplication_key = left(p_deduplication_key,240)
    limit 1;
  end;

  if p_reminder_source = 'event' then
    update public.calendar_event_reminders
    set delivery_status='queued',failure_code=null
    where id=p_reminder_id and tenant_id=p_tenant_id
      and delivery_status='scheduled'
      and scheduled_for is not distinct from p_scheduled_for;
  else
    update public.calendar_task_reminders
    set delivery_status='queued',failure_code=null
    where id=p_reminder_id and tenant_id=p_tenant_id
      and delivery_status='scheduled'
      and scheduled_for is not distinct from p_scheduled_for;
  end if;
  return queued;
end;
$$;

-- Transactional wrappers around existing, already-concurrency-safe domain RPCs.
create or replace function public.create_builder_form_submission_notified_safe(
  p_submission jsonb,
  p_idempotency_key_hash text,
  p_request_hash text,
  p_notification jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  result jsonb;
  saved jsonb;
begin
  result := public.create_builder_form_submission_safe(
    p_submission, p_idempotency_key_hash, p_request_hash
  );
  if not coalesce((result ->> 'duplicate')::boolean, false) then
    saved := result -> 'submission';
    perform public.create_notification_event_intent(
      (saved ->> 'tenant_id')::integer,
      p_notification ->> 'event_type',
      p_notification ->> 'source_type',
      saved ->> 'id',
      p_notification ->> 'title',
      p_notification ->> 'body',
      coalesce(p_notification -> 'data', '{}'::jsonb)
        || jsonb_build_object('submission_id', saved ->> 'id'),
      concat('builder-form-submission:', saved ->> 'id')
    );
  end if;
  return result;
end;
$$;

create or replace function public.create_builder_reservation_notified_safe(
  p_reservation jsonb,
  p_idempotency_key_hash text,
  p_request_hash text,
  p_exclusive_slot boolean,
  p_notification jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  result jsonb;
  saved jsonb;
  reservation_id uuid;
begin
  result := public.create_builder_reservation_safe(
    p_reservation, p_idempotency_key_hash, p_request_hash, p_exclusive_slot
  );
  if not coalesce((result ->> 'duplicate')::boolean, false) then
    saved := result -> 'reservation';
    reservation_id := (saved ->> 'id')::uuid;
    perform public.create_notification_event_intent(
      (saved ->> 'tenant_id')::integer,
      p_notification ->> 'event_type',
      p_notification ->> 'source_type',
      reservation_id::text,
      p_notification ->> 'title',
      p_notification ->> 'body',
      coalesce(p_notification -> 'data', '{}'::jsonb)
        || jsonb_build_object('reservation_id', reservation_id),
      concat('builder-reservation-event:', reservation_id)
    );
    if saved ->> 'block_type' = 'reservationBlock'
      and nullif(btrim(saved ->> 'customer_email'), '') is not null
    then
      insert into public.notification_outbox (
        tenant_id, channel, template, recipient_reference, payload, status,
        available_at, deduplication_key, retention_until
      ) values (
        (saved ->> 'tenant_id')::integer,
        'email', 'reservation_confirmation', concat('reservation:', reservation_id),
        jsonb_build_object(
          'reservation_id', reservation_id,
          'status', coalesce(saved ->> 'status', 'new'),
          'site_subdomain', saved ->> 'site_subdomain'
        ),
        'pending', now(), concat('reservation-confirmation:', reservation_id),
        now() + interval '90 days'
      ) on conflict do nothing;
    end if;
  end if;
  return result;
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
begin
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

create or replace function public.cancel_builder_reservation_notified_safe(
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
  result jsonb;
begin
  result := public.cancel_builder_reservation_safe(
    p_reservation_id, p_token_hash, p_cancelled_at
  );
  if nullif(btrim(result ->> 'customer_email'), '') is not null then
    insert into public.notification_outbox (
      tenant_id, channel, template, recipient_reference, payload, status,
      available_at, deduplication_key, retention_until
    ) values (
      (result ->> 'tenant_id')::integer, 'email', 'reservation_status_changed',
      concat('reservation:', p_reservation_id),
      jsonb_build_object('reservation_id', p_reservation_id, 'status', 'cancelled'),
      'pending', now(), concat('reservation-cancelled:', p_reservation_id),
      now() + interval '90 days'
    ) on conflict do nothing;
  end if;
  return result;
end;
$$;

revoke all on function public.create_notification_event_intent(integer, text, text, text, text, text, jsonb, text) from public, anon, authenticated;
revoke all on function public.get_or_create_notification_event(integer, text, text, text, text, text, jsonb, text) from public, anon, authenticated;
revoke all on function public.resolve_notification_outbox(uuid, timestamptz) from public, anon, authenticated;
revoke all on function public.claim_notification_deliveries(integer, timestamptz, integer) from public, anon, authenticated;
revoke all on function public.finish_notification_delivery(uuid, text, text, text, timestamptz, text, timestamptz) from public, anon, authenticated;
revoke all on function public.cleanup_notification_delivery_data(timestamptz, integer) from public, anon, authenticated;
revoke all on function public.enqueue_calendar_reminder_notification(text, uuid, timestamptz, integer, integer, text, text, text, jsonb) from public, anon, authenticated;
revoke all on function public.create_builder_form_submission_notified_safe(jsonb, text, text, jsonb) from public, anon, authenticated;
revoke all on function public.create_builder_reservation_notified_safe(jsonb, text, text, boolean, jsonb) from public, anon, authenticated;
revoke all on function public.update_builder_reservation_status_notified_safe(uuid, integer, text, timestamptz) from public, anon, authenticated;
revoke all on function public.cancel_builder_reservation_notified_safe(uuid, text, timestamptz) from public, anon, authenticated;

grant execute on function public.create_notification_event_intent(integer, text, text, text, text, text, jsonb, text) to service_role;
grant execute on function public.get_or_create_notification_event(integer, text, text, text, text, text, jsonb, text) to service_role;
grant execute on function public.resolve_notification_outbox(uuid, timestamptz) to service_role;
grant execute on function public.claim_notification_deliveries(integer, timestamptz, integer) to service_role;
grant execute on function public.finish_notification_delivery(uuid, text, text, text, timestamptz, text, timestamptz) to service_role;
grant execute on function public.cleanup_notification_delivery_data(timestamptz, integer) to service_role;
grant execute on function public.enqueue_calendar_reminder_notification(text, uuid, timestamptz, integer, integer, text, text, text, jsonb) to service_role;
grant execute on function public.create_builder_form_submission_notified_safe(jsonb, text, text, jsonb) to service_role;
grant execute on function public.create_builder_reservation_notified_safe(jsonb, text, text, boolean, jsonb) to service_role;
grant execute on function public.update_builder_reservation_status_notified_safe(uuid, integer, text, timestamptz) to service_role;
grant execute on function public.cancel_builder_reservation_notified_safe(uuid, text, timestamptz) to service_role;

notify pgrst, 'reload schema';
commit;
