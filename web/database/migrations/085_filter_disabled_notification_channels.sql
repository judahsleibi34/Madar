-- Gate notification delivery materialization on runtime channel capabilities.
--
-- The legacy resolve_notification_outbox RPC is intentionally preserved for
-- rollback compatibility with the currently active blue release. New code
-- uses resolve_notification_outbox_v2 and explicitly supplies deployment
-- channel capabilities.

create or replace function public.resolve_notification_outbox_v2(
  p_outbox_id uuid,
  p_now timestamptz,
  p_email_enabled boolean,
  p_web_push_enabled boolean
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
    if work.template = 'tenant_event' and p_web_push_enabled then
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
    if p_web_push_enabled then
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
    end if;
  elsif work.channel = 'email' then
    if p_email_enabled then
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
    end if;
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

revoke all on function public.resolve_notification_outbox_v2(
  uuid, timestamptz, boolean, boolean
) from public, anon, authenticated;

grant execute on function public.resolve_notification_outbox_v2(
  uuid, timestamptz, boolean, boolean
) to service_role;
