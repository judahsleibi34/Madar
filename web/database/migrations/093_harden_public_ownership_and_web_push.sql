BEGIN;

-- Keep the SECURITY DEFINER search path restricted to public. pgcrypto is
-- installed in the extensions schema in production, so qualify digest at the
-- one call site instead of widening the function's lookup path.
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
    or existing_subscription.p256dh <> p_p256dh
    or existing_subscription.auth <> p_auth
  ) then
    update public.web_push_subscriptions
    set endpoint = concat(
          'revoked:', existing_subscription.id, ':',
          encode(extensions.digest(existing_subscription.endpoint, 'sha256'), 'hex')
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

-- Ownership is part of the same transaction as the durable customer record
-- and its notification. The membership domain is validated before calling
-- the existing concurrency-safe insert function.
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
  saved_row public.builder_form_submissions;
  p_tenant_id integer;
  p_site_user_id integer;
  p_site_membership_id bigint;
begin
  p_tenant_id := nullif(p_submission ->> 'tenant_id', '')::integer;
  p_site_user_id := nullif(p_submission ->> 'site_user_id', '')::integer;
  p_site_membership_id := nullif(p_submission ->> 'site_membership_id', '')::bigint;

  if p_site_membership_id is not null and (
    p_site_user_id is null or not exists (
      select 1 from public.tenant_site_memberships membership
      where membership.id = p_site_membership_id
        and membership.tenant_id = p_tenant_id
        and membership.user_id = p_site_user_id
        and membership.status = 'active'
    )
  ) then
    raise exception using errcode = 'P0001', message = 'site_record_owner_invalid';
  end if;
  if p_site_user_id is not null and p_site_membership_id is null and not exists (
    select 1 from public.users site_user
    where site_user.id = p_site_user_id
      and (
        site_user.tenant_id = p_tenant_id
        or exists (
          select 1 from public.tenant_memberships membership
          where membership.tenant_id = p_tenant_id
            and membership.user_id = p_site_user_id
            and membership.status = 'active'
        )
        or exists (
          select 1 from public.website_settings settings
          where settings.tenant_id = p_tenant_id
            and settings.user_id = p_site_user_id
        )
      )
  ) then
    raise exception using errcode = 'P0001', message = 'site_record_owner_invalid';
  end if;

  result := public.create_builder_form_submission_safe(
    p_submission, p_idempotency_key_hash, p_request_hash
  );
  saved := result -> 'submission';
  update public.builder_form_submissions
  set site_user_id = p_site_user_id,
      site_membership_id = p_site_membership_id
  where id = (saved ->> 'id')::uuid
    and tenant_id = p_tenant_id
  returning * into saved_row;
  if not found then
    raise exception using errcode = 'P0001', message = 'form_submission_owner_update_failed';
  end if;
  saved := to_jsonb(saved_row);
  result := jsonb_set(result, '{submission}', saved, true);

  if not coalesce((result ->> 'duplicate')::boolean, false) then
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
  saved_row public.builder_reservations;
  reservation_id uuid;
  p_tenant_id integer;
  p_site_user_id integer;
  p_site_membership_id bigint;
begin
  p_tenant_id := nullif(p_reservation ->> 'tenant_id', '')::integer;
  p_site_user_id := nullif(p_reservation ->> 'site_user_id', '')::integer;
  p_site_membership_id := nullif(p_reservation ->> 'site_membership_id', '')::bigint;

  if p_site_membership_id is not null and (
    p_site_user_id is null or not exists (
      select 1 from public.tenant_site_memberships membership
      where membership.id = p_site_membership_id
        and membership.tenant_id = p_tenant_id
        and membership.user_id = p_site_user_id
        and membership.status = 'active'
    )
  ) then
    raise exception using errcode = 'P0001', message = 'site_record_owner_invalid';
  end if;
  if p_site_user_id is not null and p_site_membership_id is null and not exists (
    select 1 from public.users site_user
    where site_user.id = p_site_user_id
      and (
        site_user.tenant_id = p_tenant_id
        or exists (
          select 1 from public.tenant_memberships membership
          where membership.tenant_id = p_tenant_id
            and membership.user_id = p_site_user_id
            and membership.status = 'active'
        )
        or exists (
          select 1 from public.website_settings settings
          where settings.tenant_id = p_tenant_id
            and settings.user_id = p_site_user_id
        )
      )
  ) then
    raise exception using errcode = 'P0001', message = 'site_record_owner_invalid';
  end if;

  result := public.create_builder_reservation_safe(
    p_reservation, p_idempotency_key_hash, p_request_hash, p_exclusive_slot
  );
  saved := result -> 'reservation';
  reservation_id := (saved ->> 'id')::uuid;
  update public.builder_reservations
  set site_user_id = p_site_user_id,
      site_membership_id = p_site_membership_id
  where id = reservation_id
    and tenant_id = p_tenant_id
  returning * into saved_row;
  if not found then
    raise exception using errcode = 'P0001', message = 'reservation_owner_update_failed';
  end if;
  saved := to_jsonb(saved_row);
  result := jsonb_set(result, '{reservation}', saved, true);

  if not coalesce((result ->> 'duplicate')::boolean, false) then
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

revoke all on function public.bind_web_push_subscription_to_installation(integer, integer, uuid, text, text, text, text) from public, anon, authenticated;
revoke all on function public.create_builder_form_submission_notified_safe(jsonb, text, text, jsonb) from public, anon, authenticated;
revoke all on function public.create_builder_reservation_notified_safe(jsonb, text, text, boolean, jsonb) from public, anon, authenticated;
grant execute on function public.bind_web_push_subscription_to_installation(integer, integer, uuid, text, text, text, text) to service_role;
grant execute on function public.create_builder_form_submission_notified_safe(jsonb, text, text, jsonb) to service_role;
grant execute on function public.create_builder_reservation_notified_safe(jsonb, text, text, boolean, jsonb) to service_role;

do $$
declare
  v_schema_version public.application_schema_state.schema_version%TYPE;
begin
  select schema_version
  into v_schema_version
  from public.application_schema_state
  where contract_key = 'core'
  for update;

  if v_schema_version is null then
    raise exception using
      errcode = 'P0001',
      message = 'migration_093_schema_state_missing';
  end if;

  if v_schema_version <> 92 then
    raise exception using
      errcode = 'P0001',
      message = format(
        'migration_093_expected_schema_92_got_%s',
        v_schema_version
      );
  end if;

  update public.application_schema_state
  set schema_version = 93,
      applied_at = now()
  where contract_key = 'core';
end;
$$;

notify pgrst, 'reload schema';

COMMIT;
