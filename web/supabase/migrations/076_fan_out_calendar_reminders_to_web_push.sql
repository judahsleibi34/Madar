-- Keep the durable in-app calendar reminder and also fan it out to every
-- active, opted-in browser installation owned by the same recipient.
begin;

create or replace function public.fan_out_calendar_reminder_web_push()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.notification_deliveries (
    outbox_id, tenant_id, event_id, user_id, subscription_id, channel,
    template, recipient_reference, payload, deduplication_key, retention_until
  )
  select
    new.outbox_id, new.tenant_id, new.event_id, new.user_id, subscription.id,
    'web_push', new.template, concat('subscription:', subscription.id),
    new.payload,
    concat('outbox:', new.outbox_id, ':web_push:subscription:', subscription.id),
    new.retention_until
  from public.tenant_memberships membership
  join public.web_push_subscriptions subscription
    on subscription.user_id = membership.user_id
   and subscription.tenant_id = membership.tenant_id
   and subscription.revoked_at is null
  left join public.app_installations installation
    on installation.id = subscription.app_installation_id
  where membership.tenant_id = new.tenant_id
    and membership.user_id = new.user_id
    and membership.status = 'active'
    and (
      subscription.app_installation_id is null
      or (
        installation.user_id = membership.user_id
        and installation.revoked_at is null
        and installation.notifications_enabled = true
        and installation.notification_permission = 'granted'
      )
    )
  on conflict (deduplication_key) do nothing;

  return new;
end;
$$;

revoke all on function public.fan_out_calendar_reminder_web_push()
from public, anon, authenticated;

drop trigger if exists fan_out_calendar_reminder_web_push
on public.notification_deliveries;

create trigger fan_out_calendar_reminder_web_push
after insert on public.notification_deliveries
for each row
when (new.channel = 'internal' and new.template = 'calendar_reminder')
execute function public.fan_out_calendar_reminder_web_push();

commit;
