-- Durable notification delivery work. This migration does not schedule a worker
-- and does not delete any existing notification or customer data.
begin;

create extension if not exists pgcrypto;

create table if not exists public.notification_outbox (
  id uuid primary key default gen_random_uuid(),
  tenant_id integer references public.tenants(tenant_id) on delete cascade,
  user_id integer references public.users(id) on delete set null,
  channel text not null,
  template text not null,
  recipient_hash text,
  recipient_reference text,
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'pending',
  attempts integer not null default 0,
  max_attempts integer not null default 5,
  available_at timestamptz not null default now(),
  last_error_code text,
  deduplication_key text,
  processing_started_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  sent_at timestamptz,
  retention_until timestamptz,
  constraint notification_outbox_channel_check
    check (channel in ('internal', 'email', 'web_push')),
  constraint notification_outbox_status_check
    check (status in ('pending', 'processing', 'sent', 'failed', 'dead')),
  constraint notification_outbox_attempts_check
    check (attempts >= 0 and max_attempts between 1 and 20),
  constraint notification_outbox_payload_object_check
    check (jsonb_typeof(payload) = 'object'),
  constraint notification_outbox_recipient_hash_check
    check (recipient_hash is null or recipient_hash ~ '^[0-9a-f]{64}$')
);

drop index if exists public.notification_outbox_deduplication_unique_idx;
create unique index notification_outbox_deduplication_unique_idx
on public.notification_outbox (coalesce(tenant_id, -1), channel, deduplication_key)
where deduplication_key is not null;

create index if not exists notification_outbox_pending_available_idx
on public.notification_outbox (status, available_at, processing_started_at, created_at)
where status in ('pending', 'failed', 'processing');

create index if not exists notification_outbox_tenant_created_idx
on public.notification_outbox (tenant_id, created_at desc);

drop trigger if exists set_notification_outbox_updated_at on public.notification_outbox;
create trigger set_notification_outbox_updated_at
before update on public.notification_outbox
for each row execute function public.set_updated_at();

alter table public.notification_outbox enable row level security;
revoke all on public.notification_outbox from anon, authenticated;
grant select, insert, update, delete on public.notification_outbox to service_role;

create or replace function public.claim_notification_outbox(
  p_limit integer default 25,
  p_now timestamptz default now()
)
returns setof public.notification_outbox
language plpgsql
security definer
set search_path = public
as $$
begin
  -- A worker can crash after claiming its final allowed attempt. Without this
  -- transition the row is no longer claimable and remains processing forever.
  update public.notification_outbox outbox
  set status = 'dead',
      processing_started_at = null,
      last_error_code = coalesce(outbox.last_error_code, 'delivery_attempts_exhausted')
  where outbox.status = 'processing'
    and outbox.processing_started_at < p_now - interval '15 minutes'
    and outbox.attempts >= outbox.max_attempts;

  return query
  update public.notification_outbox outbox
  set status = 'processing',
      attempts = outbox.attempts + 1,
      processing_started_at = p_now,
      last_error_code = null
  where outbox.id in (
    select candidate.id
    from public.notification_outbox candidate
    where (
        (candidate.status in ('pending', 'failed') and candidate.available_at <= p_now)
        or (
          candidate.status = 'processing'
          and candidate.processing_started_at < p_now - interval '15 minutes'
        )
      )
      and candidate.attempts < candidate.max_attempts
    order by candidate.available_at, candidate.created_at
    limit greatest(1, least(coalesce(p_limit, 25), 100))
    for update skip locked
  )
  returning outbox.*;
end;
$$;

revoke all on function public.claim_notification_outbox(integer, timestamptz)
from public, anon, authenticated;
grant execute on function public.claim_notification_outbox(integer, timestamptz)
to service_role;

create or replace function public.finish_notification_outbox(
  p_outbox_id uuid,
  p_succeeded boolean,
  p_failure_code text default null,
  p_available_at timestamptz default null,
  p_finished_at timestamptz default now()
)
returns public.notification_outbox
language plpgsql
security definer
set search_path = public
as $$
declare
  outbox_row public.notification_outbox;
begin
  select * into outbox_row
  from public.notification_outbox
  where id = p_outbox_id
  for update;

  if not found or outbox_row.status not in ('pending', 'processing') then
    raise exception using errcode = 'P0001', message = 'notification_outbox_state_conflict';
  end if;

  update public.notification_outbox
  set status = case
        when p_succeeded then 'sent'
        when attempts >= max_attempts then 'dead'
        else 'failed'
      end,
      sent_at = case when p_succeeded then p_finished_at else null end,
      available_at = case
        when not p_succeeded and attempts < max_attempts
          then coalesce(p_available_at, p_finished_at + interval '1 minute')
        else available_at
      end,
      last_error_code = case when p_succeeded then null else p_failure_code end,
      processing_started_at = null
  where id = p_outbox_id
  returning * into outbox_row;
  return outbox_row;
end;
$$;

revoke all on function public.finish_notification_outbox(uuid, boolean, text, timestamptz, timestamptz)
from public, anon, authenticated;
grant execute on function public.finish_notification_outbox(uuid, boolean, text, timestamptz, timestamptz)
to service_role;

notify pgrst, 'reload schema';
commit;
