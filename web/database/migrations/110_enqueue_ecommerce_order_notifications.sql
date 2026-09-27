begin;

-- Order creation and its durable owner-notification intent must commit together.
-- The constraint trigger is deferred so it reads the finalized totals written
-- later in create_ecommerce_order_safe's transaction.
create or replace function public.enqueue_ecommerce_order_created_notification(
  p_tenant_id integer,
  p_order_id uuid
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_order public.ecommerce_orders;
  v_display_number text;
  v_amount text;
  v_body text;
  v_deduplication_key text;
begin
  select *
  into v_order
  from public.ecommerce_orders
  where tenant_id = p_tenant_id
    and id = p_order_id;

  if not found then
    raise exception using
      errcode = 'P0001',
      message = 'ecommerce_order_notification_order_not_found';
  end if;

  v_display_number := coalesce(
    nullif(btrim(v_order.order_number), ''),
    left(v_order.id::text, 8),
    'New order'
  );
  v_amount := concat_ws(
    ' ',
    nullif(btrim(v_order.currency), ''),
    v_order.total::text
  );
  v_body := format(
    '%s was placed by %s%s.',
    v_display_number,
    btrim(v_order.customer_name),
    case when v_amount <> '' then ' for ' || v_amount else '' end
  );
  v_deduplication_key := encode(
    extensions.digest(
      concat_ws(
        ':',
        v_order.tenant_id,
        'ecommerce_order_created',
        'ecommerce_order',
        v_order.id
      ),
      'sha256'
    ),
    'hex'
  );

  perform public.create_notification_event_intent(
    v_order.tenant_id,
    'ecommerce_order_created',
    'ecommerce_order',
    v_order.id::text,
    'New order: ' || v_display_number,
    v_body,
    jsonb_build_object(
      'order_id', v_order.id::text,
      'order_number', v_order.order_number,
      'status', v_order.status,
      'payment_status', v_order.payment_status,
      'currency', v_order.currency,
      'total', v_order.total::text,
      'action', jsonb_build_object(
        'kind', 'notification_center',
        'path', '/notifications',
        'object_id', v_order.id::text,
        'tenant_id', v_order.tenant_id::text
      )
    ),
    v_deduplication_key
  );
end;
$$;

revoke all on function public.enqueue_ecommerce_order_created_notification(integer, uuid)
from public, anon, authenticated;
grant execute on function public.enqueue_ecommerce_order_created_notification(integer, uuid)
to service_role;

create or replace function public.enqueue_ecommerce_order_created_notification_trigger()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  perform public.enqueue_ecommerce_order_created_notification(
    new.tenant_id,
    new.id
  );
  return new;
end;
$$;

revoke all on function public.enqueue_ecommerce_order_created_notification_trigger()
from public, anon, authenticated;

drop trigger if exists ecommerce_order_created_notification_intent
on public.ecommerce_orders;

create constraint trigger ecommerce_order_created_notification_intent
after insert on public.ecommerce_orders
deferrable initially deferred
for each row
execute function public.enqueue_ecommerce_order_created_notification_trigger();

-- Repair only recent orders that predate the atomic trigger. The notification
-- event/outbox deduplication key makes this replay safe.
do $$
declare
  v_order record;
begin
  for v_order in
    select orders.tenant_id, orders.id
    from public.ecommerce_orders orders
    where orders.created_at >= now() - interval '30 days'
      and not exists (
        select 1
        from public.notification_events event
        where event.tenant_id = orders.tenant_id
          and event.event_type = 'ecommerce_order_created'
          and event.source_type = 'ecommerce_order'
          and event.source_id = orders.id::text
      )
    order by orders.created_at, orders.id
  loop
    perform public.enqueue_ecommerce_order_created_notification(
      v_order.tenant_id,
      v_order.id
    );
  end loop;
end;
$$;

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
      message = 'migration_110_schema_state_missing';
  end if;

  if v_schema_version <> 109 then
    raise exception using
      errcode = 'P0001',
      message = format('migration_110_expected_schema_109_got_%s', v_schema_version);
  end if;

  update public.application_schema_state
  set schema_version = 110,
      applied_at = now()
  where contract_key = 'core';
end;
$$;

notify pgrst, 'reload schema';

commit;