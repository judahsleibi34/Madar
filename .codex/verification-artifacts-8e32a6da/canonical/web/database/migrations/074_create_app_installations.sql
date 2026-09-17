-- Stable, privacy-minimized browser/PWA installation identity and Push binding.
-- Installation rows are identity metadata only; tenant authorization continues
-- to come from active tenant memberships at API and delivery time.
begin;

create extension if not exists pgcrypto;

create table if not exists public.app_installations (
  id uuid primary key default gen_random_uuid(),
  installation_id uuid not null,
  user_id integer not null references public.users(id) on delete cascade,
  current_tenant_id integer references public.tenants(tenant_id) on delete set null,
  platform text not null default 'unknown',
  display_mode text not null default 'browser',
  notification_permission text not null default 'unknown',
  notifications_enabled boolean not null default false,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  installed_confirmed_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint app_installations_user_client_unique
    unique (user_id, installation_id),
  constraint app_installations_platform_check
    check (platform in ('ios', 'android', 'windows', 'macos', 'linux', 'chromeos', 'unknown')),
  constraint app_installations_display_mode_check
    check (display_mode in ('browser', 'standalone', 'ios_standalone')),
  constraint app_installations_permission_check
    check (notification_permission in ('default', 'granted', 'denied', 'unknown'))
);

create index if not exists app_installations_current_tenant_idx
on public.app_installations (current_tenant_id, last_seen_at desc);

create index if not exists app_installations_last_seen_idx
on public.app_installations (last_seen_at desc);

create index if not exists app_installations_revoked_idx
on public.app_installations (revoked_at)
where revoked_at is not null;

drop trigger if exists set_app_installations_updated_at on public.app_installations;
create trigger set_app_installations_updated_at
before update on public.app_installations
for each row execute function public.set_updated_at();

alter table public.app_installations enable row level security;
revoke all on public.app_installations from anon, authenticated;
grant select, insert, update, delete on public.app_installations to service_role;

alter table public.web_push_subscriptions
  add column if not exists app_installation_id uuid
  references public.app_installations(id) on delete set null;

create index if not exists web_push_subscriptions_installation_active_idx
on public.web_push_subscriptions (app_installation_id, last_seen_at desc)
where app_installation_id is not null and revoked_at is null;

create or replace function public.register_app_installation(
  p_user_id integer,
  p_tenant_id integer,
  p_installation_id uuid,
  p_platform text,
  p_display_mode text,
  p_notification_permission text,
  p_installed_confirmed boolean default false
)
returns public.app_installations
language plpgsql
security definer
set search_path = public
as $$
declare
  installation public.app_installations;
begin
  if p_user_id is null or p_tenant_id is null or p_installation_id is null
    or p_platform not in ('ios', 'android', 'windows', 'macos', 'linux', 'chromeos', 'unknown')
    or p_display_mode not in ('browser', 'standalone', 'ios_standalone')
    or p_notification_permission not in ('default', 'granted', 'denied', 'unknown')
  then
    raise exception using errcode = 'P0001', message = 'app_installation_invalid';
  end if;

  if not exists (
    select 1 from public.tenant_memberships membership
    where membership.tenant_id = p_tenant_id
      and membership.user_id = p_user_id
      and membership.status = 'active'
  ) then
    raise exception using errcode = 'P0001', message = 'active_tenant_membership_required';
  end if;

  insert into public.app_installations (
    installation_id, user_id, current_tenant_id, platform, display_mode,
    notification_permission, installed_confirmed_at
  ) values (
    p_installation_id, p_user_id, p_tenant_id, p_platform, p_display_mode,
    p_notification_permission,
    case when p_installed_confirmed then now() else null end
  )
  on conflict (user_id, installation_id) do update
  set current_tenant_id = excluded.current_tenant_id,
      platform = excluded.platform,
      display_mode = excluded.display_mode,
      notification_permission = excluded.notification_permission,
      last_seen_at = now(),
      installed_confirmed_at = case
        when public.app_installations.installed_confirmed_at is not null
          then public.app_installations.installed_confirmed_at
        when p_installed_confirmed then now()
        else null
      end,
      notifications_enabled = case
        when excluded.notification_permission = 'denied' then false
        else public.app_installations.notifications_enabled
      end
  returning * into installation;

  if p_notification_permission = 'denied' then
    update public.web_push_subscriptions
    set revoked_at = coalesce(revoked_at, now())
    where app_installation_id = installation.id and revoked_at is null;
  end if;

  return installation;
end;
$$;

create or replace function public.bind_web_push_subscription_to_installation(
  p_user_id integer,
  p_tenant_id integer,
  p_installation_id uuid,
  p_endpoint text,
  p_p256dh text,
  p_auth text,
  p_user_agent text
)
returns public.web_push_subscriptions
language plpgsql
security definer
set search_path = public
as $$
declare
  installation public.app_installations;
  subscription public.web_push_subscriptions;
  existing_subscription public.web_push_subscriptions;
begin
  if not exists (
    select 1 from public.tenant_memberships membership
    where membership.tenant_id = p_tenant_id
      and membership.user_id = p_user_id
      and membership.status = 'active'
  ) then
    raise exception using errcode = 'P0001', message = 'active_tenant_membership_required';
  end if;

  select * into installation
  from public.app_installations candidate
  where candidate.user_id = p_user_id
    and candidate.installation_id = p_installation_id
    and candidate.revoked_at is null
  for update;

  if not found then
    raise exception using errcode = 'P0001', message = 'app_installation_not_available';
  end if;

  -- One browser site-data context has one current Push endpoint. Endpoint
  -- rotation revokes the old binding without changing installation identity.
  update public.web_push_subscriptions
  set revoked_at = coalesce(revoked_at, now())
  where app_installation_id = installation.id
    and endpoint <> p_endpoint
    and revoked_at is null;

  select * into existing_subscription
  from public.web_push_subscriptions candidate
  where candidate.endpoint = p_endpoint
  for update;

  if found and (
    existing_subscription.user_id <> p_user_id
    or existing_subscription.app_installation_id is distinct from installation.id
  ) then
    -- Preserve the old row (and delivery audit references) as a revoked
    -- tombstone, then give the newly authenticated account a fresh binding.
    update public.web_push_subscriptions
    set endpoint = concat(
          'revoked:', existing_subscription.id, ':',
          encode(digest(existing_subscription.endpoint, 'sha256'), 'hex')
        ),
        revoked_at = coalesce(revoked_at, now())
    where id = existing_subscription.id;
  end if;

  insert into public.web_push_subscriptions (
    tenant_id, user_id, app_installation_id, endpoint, p256dh, auth,
    user_agent, last_seen_at, revoked_at
  ) values (
    p_tenant_id, p_user_id, installation.id, p_endpoint, p_p256dh, p_auth,
    left(coalesce(p_user_agent, ''), 1000), now(), null
  )
  on conflict (endpoint) do update
  set tenant_id = excluded.tenant_id,
      user_id = excluded.user_id,
      app_installation_id = excluded.app_installation_id,
      p256dh = excluded.p256dh,
      auth = excluded.auth,
      user_agent = excluded.user_agent,
      last_seen_at = now(),
      revoked_at = null
  returning * into subscription;

  update public.app_installations
  set current_tenant_id = p_tenant_id,
      last_seen_at = now(),
      notification_permission = 'granted',
      notifications_enabled = true
  where id = installation.id;

  return subscription;
end;
$$;

create or replace function public.revoke_installation_push_subscriptions(
  p_user_id integer,
  p_installation_id uuid
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  installation_uuid uuid;
  revoked_count integer := 0;
begin
  select id into installation_uuid
  from public.app_installations
  where user_id = p_user_id and installation_id = p_installation_id
  for update;

  if installation_uuid is null then return 0; end if;

  update public.web_push_subscriptions
  set revoked_at = coalesce(revoked_at, now())
  where app_installation_id = installation_uuid and revoked_at is null;
  get diagnostics revoked_count = row_count;

  update public.app_installations
  set notifications_enabled = false, last_seen_at = now()
  where id = installation_uuid;

  return revoked_count;
end;
$$;

-- Replace Phase 2 recipient resolution so a bound subscription is eligible
-- only when its installation is active and Push-enabled. NULL installation
-- references remain a temporary legacy compatibility path.
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
  select * into work from public.notification_outbox where id = p_outbox_id for update;
  if not found or work.status <> 'processing' then
    raise exception using errcode = 'P0001', message = 'notification_outbox_state_conflict';
  end if;

  if work.template = 'tenant_event' then
    begin canonical_event_id := nullif(work.payload ->> 'event_id', '')::uuid;
    exception when invalid_text_representation then
      raise exception using errcode = 'P0001', message = 'notification_event_reference_invalid';
    end;
    if canonical_event_id is null then
      select event.id into canonical_event_id from public.notification_events event
      where event.tenant_id = work.tenant_id
        and event.event_type = work.payload ->> 'event_type'
        and event.source_type = work.payload ->> 'source_type'
        and event.source_id is not distinct from nullif(work.payload ->> 'source_id', '')
      order by event.created_at limit 1;
    end if;
    if canonical_event_id is null then
      select event.id into canonical_event_id
      from public.get_or_create_notification_event(
        work.tenant_id, work.payload ->> 'event_type', work.payload ->> 'source_type',
        work.payload ->> 'source_id', work.payload ->> 'title', work.payload ->> 'body',
        coalesce(work.payload -> 'data', '{}'::jsonb),
        coalesce(work.deduplication_key, concat('legacy-outbox:', work.id))
      ) event;
    end if;
    if not exists (select 1 from public.notification_events event
      where event.id = canonical_event_id and event.tenant_id = work.tenant_id) then
      raise exception using errcode = 'P0001', message = 'notification_event_reference_invalid';
    end if;
  end if;

  if work.channel = 'internal' then
    insert into public.notification_deliveries (
      outbox_id, tenant_id, event_id, user_id, channel, template,
      recipient_reference, payload, deduplication_key, retention_until
    )
    select work.id, work.tenant_id, canonical_event_id, membership.user_id,
      'internal', work.template, concat('user:', membership.user_id), work.payload,
      concat('outbox:', work.id, ':internal:user:', membership.user_id),
      coalesce(work.retention_until, p_now + interval '90 days')
    from public.tenant_memberships membership
    where membership.tenant_id = work.tenant_id and membership.status = 'active'
      and (work.user_id is null or membership.user_id = work.user_id)
    on conflict (deduplication_key) do nothing;
    get diagnostics affected = row_count; inserted_count := inserted_count + affected;

    if work.template = 'tenant_event' then
      insert into public.notification_deliveries (
        outbox_id, tenant_id, event_id, user_id, subscription_id, channel,
        template, recipient_reference, payload, deduplication_key, retention_until
      )
      select work.id, work.tenant_id, canonical_event_id, membership.user_id,
        subscription.id, 'web_push', work.template, concat('subscription:', subscription.id),
        work.payload, concat('outbox:', work.id, ':web_push:subscription:', subscription.id),
        coalesce(work.retention_until, p_now + interval '90 days')
      from public.tenant_memberships membership
      join public.web_push_subscriptions subscription
        on subscription.user_id = membership.user_id
       and subscription.tenant_id = membership.tenant_id and subscription.revoked_at is null
      left join public.app_installations installation on installation.id = subscription.app_installation_id
      where membership.tenant_id = work.tenant_id and membership.status = 'active'
        and (work.user_id is null or membership.user_id = work.user_id)
        and (subscription.app_installation_id is null or (
          installation.user_id = membership.user_id and installation.revoked_at is null
          and installation.notifications_enabled = true))
      on conflict (deduplication_key) do nothing;
      get diagnostics affected = row_count; inserted_count := inserted_count + affected;
    end if;
  elsif work.channel = 'web_push' then
    insert into public.notification_deliveries (
      outbox_id, tenant_id, user_id, subscription_id, channel, template,
      recipient_reference, payload, deduplication_key, retention_until
    )
    select work.id, work.tenant_id, membership.user_id, subscription.id,
      'web_push', work.template, concat('subscription:', subscription.id), work.payload,
      concat('outbox:', work.id, ':web_push:subscription:', subscription.id),
      coalesce(work.retention_until, p_now + interval '90 days')
    from public.tenant_memberships membership
    join public.web_push_subscriptions subscription
      on subscription.user_id = membership.user_id
     and subscription.tenant_id = membership.tenant_id and subscription.revoked_at is null
    left join public.app_installations installation on installation.id = subscription.app_installation_id
    where membership.tenant_id = work.tenant_id and membership.status = 'active'
      and (work.user_id is null or membership.user_id = work.user_id)
      and (subscription.app_installation_id is null or (
        installation.user_id = membership.user_id and installation.revoked_at is null
        and installation.notifications_enabled = true))
    on conflict (deduplication_key) do nothing;
    get diagnostics affected = row_count; inserted_count := inserted_count + affected;
  elsif work.channel = 'email' then
    insert into public.notification_deliveries (
      outbox_id, tenant_id, user_id, channel, template, recipient_hash,
      recipient_reference, payload, deduplication_key, retention_until
    ) values (
      work.id, work.tenant_id, work.user_id, 'email', work.template,
      work.recipient_hash, work.recipient_reference, work.payload,
      concat('outbox:', work.id, ':email'), coalesce(work.retention_until, p_now + interval '90 days')
    ) on conflict (deduplication_key) do nothing;
    get diagnostics affected = row_count; inserted_count := inserted_count + affected;
  else
    raise exception using errcode = 'P0001', message = 'notification_channel_unsupported';
  end if;

  update public.notification_outbox set status = 'sent', sent_at = p_now,
    processing_started_at = null, last_error_code = null where id = work.id;
  return inserted_count;
end;
$$;

revoke all on function public.register_app_installation(integer, integer, uuid, text, text, text, boolean) from public, anon, authenticated;
revoke all on function public.bind_web_push_subscription_to_installation(integer, integer, uuid, text, text, text, text) from public, anon, authenticated;
revoke all on function public.revoke_installation_push_subscriptions(integer, uuid) from public, anon, authenticated;
revoke all on function public.resolve_notification_outbox(uuid, timestamptz) from public, anon, authenticated;
grant execute on function public.register_app_installation(integer, integer, uuid, text, text, text, boolean) to service_role;
grant execute on function public.bind_web_push_subscription_to_installation(integer, integer, uuid, text, text, text, text) to service_role;
grant execute on function public.revoke_installation_push_subscriptions(integer, uuid) to service_role;
grant execute on function public.resolve_notification_outbox(uuid, timestamptz) to service_role;

notify pgrst, 'reload schema';
commit;
