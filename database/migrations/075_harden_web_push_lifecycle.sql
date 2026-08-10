-- Permission synchronization and history-preserving Push subscription rotation.
begin;

update public.app_installations
set notifications_enabled = false
where notification_permission <> 'granted'
  and notifications_enabled = true;

update public.web_push_subscriptions subscription
set revoked_at = coalesce(subscription.revoked_at, now())
from public.app_installations installation
where subscription.app_installation_id = installation.id
  and installation.notification_permission <> 'granted'
  and subscription.revoked_at is null;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'app_installations_push_permission_check'
      and conrelid = 'public.app_installations'::regclass
  ) then
    alter table public.app_installations
      add constraint app_installations_push_permission_check
      check (not notifications_enabled or notification_permission = 'granted')
      not valid;
  end if;
end
$$;

alter table public.app_installations
  validate constraint app_installations_push_permission_check;

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
        when excluded.notification_permission <> 'granted' then false
        else public.app_installations.notifications_enabled
      end
  returning * into installation;

  if p_notification_permission <> 'granted' then
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

revoke all on function public.register_app_installation(integer, integer, uuid, text, text, text, boolean) from public, anon, authenticated;
revoke all on function public.bind_web_push_subscription_to_installation(integer, integer, uuid, text, text, text, text) from public, anon, authenticated;
grant execute on function public.register_app_installation(integer, integer, uuid, text, text, text, boolean) to service_role;
grant execute on function public.bind_web_push_subscription_to_installation(integer, integer, uuid, text, text, text, text) to service_role;

notify pgrst, 'reload schema';
commit;
