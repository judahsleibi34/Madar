#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONTAINER_NAME="madar-073-rehearsal-$RANDOM-$$"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:17-alpine}"

cleanup() { docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$CONTAINER_NAME" \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=1g \
  -e POSTGRES_HOST_AUTH_METHOD=trust "$POSTGRES_IMAGE" >/dev/null
docker exec "$CONTAINER_NAME" sh -c \
  'until pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done'

docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
create role anon nologin;
create role authenticated nologin;
create role service_role nologin;
create schema auth;
create table auth.users (id uuid primary key,email_confirmed_at timestamptz,confirmed_at timestamptz);
create function auth.uid() returns uuid language sql stable as $$ select null::uuid $$;
create schema storage;
create table storage.buckets (id text primary key,name text not null,public boolean not null default false,file_size_limit bigint,allowed_mime_types text[]);
create table storage.objects (id uuid primary key default gen_random_uuid(),bucket_id text references storage.buckets(id),name text);
alter table storage.objects enable row level security;
SQL

for migration in "$REPO_ROOT"/database/migrations/*.sql; do
  number="$(basename "$migration" | cut -d_ -f1)"
  ((10#$number > 72)) && continue
  docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q < "$migration"
done

docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/073_create_notification_deliveries.sql"
docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/073_create_notification_deliveries.sql"

docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
insert into public.tenants (tenant_id,brand_name,owner_name,business_type)
values (301,'Delivery Test','Owner','business');
insert into auth.users (id,email_confirmed_at,confirmed_at) values
  ('00000000-0000-0000-0000-000000000301',now(),now()),
  ('00000000-0000-0000-0000-000000000302',now(),now());
insert into public.users (auth_id,first_name,last_name,email,tenant_id,account_status,email_verified)
values
  ('00000000-0000-0000-0000-000000000301','One','Member','one@example.invalid',301,'active',true),
  ('00000000-0000-0000-0000-000000000302','Two','Member','two@example.invalid',301,'active',true);
insert into public.tenant_memberships (tenant_id,user_id,auth_id,role,status)
select 301,id,auth_id,'member','active' from public.users where tenant_id=301;
insert into public.builder_projects (id,tenant_id,owner_user_id,name,slug,status,draft_schema,published_schema,published_version,published_revision,last_published_at)
select '30000000-0000-0000-0000-000000000301',301,min(id),'Test','test','published',
  '{"defaultPageId":"home","pages":[{"id":"home","slug":"/","isDefault":true,"sections":[]}],"forms":[]}',
  '{"defaultPageId":"home","pages":[{"id":"home","slug":"/","isDefault":true,"sections":[]}],"forms":[]}',
  1,0,now()
from public.users where tenant_id=301;

select public.create_notification_event_intent(
  301,'builder.test','form','source-1','Title','Body','{"answer":1}',
  'event-source-1'
);
select public.create_notification_event_intent(
  301,'builder.test','form','source-1','Title','Body','{"answer":1}',
  'event-source-1'
);

do $$
begin
  if (select count(*) from public.notification_events where deduplication_key='event-source-1') <> 1
    then raise exception 'event_dedup_failed'; end if;
  if (select count(*) from public.notification_outbox where deduplication_key='event-source-1') <> 1
    then raise exception 'outbox_dedup_failed'; end if;
end $$;

insert into public.web_push_subscriptions (tenant_id,user_id,endpoint,p256dh,auth)
select 301,id,'https://push.example.invalid/'||id,'key','auth'
from public.users where tenant_id=301;

select public.resolve_notification_outbox(id)
from public.claim_notification_outbox(1,now());

do $$
begin
  if (select count(*) from public.notification_deliveries where channel='internal') <> 2
    then raise exception 'internal_resolution_failed'; end if;
  if (select count(*) from public.notification_deliveries where channel='web_push') <> 2
    then raise exception 'push_resolution_failed'; end if;
  if (select count(*) from public.notification_outbox where status='sent') <> 1
    then raise exception 'outbox_not_resolved'; end if;
end $$;

-- Claiming is lease-based; a second claim cannot return the same row.
create temporary table first_claim as
select id from public.claim_notification_deliveries(1,now(),30);
do $$
begin
  if exists (
    select 1 from public.claim_notification_deliveries(1,now(),30) second_claim
    join first_claim first_claim on first_claim.id=second_claim.id
  ) then raise exception 'delivery_double_claimed'; end if;
end $$;

-- After lease expiry, abandoned work becomes claimable; permanent completion
-- is terminal immediately and never receives another availability timestamp.
create temporary table reclaimed as
select second_claim.id
from public.claim_notification_deliveries(100,now()+interval '31 seconds',30) second_claim
join first_claim first_claim on first_claim.id=second_claim.id;
do $$
begin
  if (select count(*) from reclaimed) <> 1
    then raise exception 'expired_lease_not_reclaimed'; end if;
end $$;
select public.finish_notification_delivery(
  id,'dead','invalid_payload',null,null,null,now()+interval '31 seconds'
) from reclaimed;
do $$
begin
  if not exists (
    select 1 from public.notification_deliveries delivery
    join reclaimed on reclaimed.id=delivery.id
    where delivery.status='dead' and delivery.last_error_code='invalid_payload'
  ) then raise exception 'permanent_delivery_not_terminal'; end if;
end $$;

-- A rolled-back domain wrapper leaves neither domain state nor notification intent.
do $$
begin
  begin
    perform public.create_builder_form_submission_notified_safe(
      jsonb_build_object(
        'tenant_id',301,'project_id','30000000-0000-0000-0000-000000000301',
        'form_id','rollback-form','status','new','answers','{}'::jsonb,
        'field_snapshot','[]'::jsonb
      ), null, repeat('a',64),
      jsonb_build_object(
        'event_type','builder.form_submitted','source_type','form',
        'title','Form','body','Body','data','{}'::jsonb
      )
    );
    raise exception 'intentional_rollback';
  exception when others then
    if sqlerrm <> 'intentional_rollback' then raise; end if;
  end;
  if exists (select 1 from public.builder_form_submissions where form_id='rollback-form')
    then raise exception 'domain_rollback_failed'; end if;
  if exists (select 1 from public.notification_events where source_id in (
    select id::text from public.builder_form_submissions where form_id='rollback-form'
  )) then raise exception 'intent_rollback_failed'; end if;
end $$;

-- Public reservation customer delivery remains tenant/resource-bound but does
-- not require the customer to be a tenant member.
create temporary table reservation_result as
select public.create_builder_reservation_notified_safe(
  jsonb_build_object(
    'tenant_id',301,'project_id','30000000-0000-0000-0000-000000000301',
    'block_id','reservation-block','block_type','reservationBlock',
    'reservation_title','Reservation','customer_email','customer@example.invalid',
    'status','new','payload','{}'::jsonb,'field_snapshot','[]'::jsonb,
    'cancellation_token_hash',repeat('c',64),
    'cancellation_expires_at',now()+interval '1 day'
  ), null, repeat('b',64), false,
  jsonb_build_object(
    'event_type','builder.reservation_requested','source_type','reservationBlock',
    'title','Reservation','body','New reservation','data','{}'::jsonb
  )
) result;
do $$
declare reservation_id uuid;
begin
  reservation_id := ((select result from reservation_result) -> 'reservation' ->> 'id')::uuid;
  if not exists (
    select 1 from public.notification_outbox
    where deduplication_key=concat('reservation-confirmation:',reservation_id)
  ) then raise exception 'reservation_confirmation_intent_missing'; end if;
  perform public.update_builder_reservation_status_notified_safe(
    reservation_id,301,'confirmed',now()
  );
  if not exists (
    select 1 from public.notification_outbox
    where deduplication_key=concat('reservation-status:',reservation_id,':confirmed')
  ) then raise exception 'reservation_status_intent_missing'; end if;
  perform public.cancel_builder_reservation_notified_safe(
    reservation_id,repeat('c',64),now()
  );
  if not exists (
    select 1 from public.notification_outbox
    where deduplication_key=concat('reservation-cancelled:',reservation_id)
  ) then raise exception 'reservation_cancellation_intent_missing'; end if;
end $$;

insert into public.notification_deliveries (
  tenant_id,user_id,channel,template,payload,status,deduplication_key,
  sent_at,retention_until
) select 301,min(id),'email','test','{}','sent','expired-sent',now()-interval '2 days',now()-interval '1 day'
from public.users where tenant_id=301;
insert into public.notification_deliveries (
  tenant_id,user_id,channel,template,payload,status,deduplication_key,
  retention_until
) select 301,min(id),'email','test','{}','pending','expired-pending',now()-interval '1 day'
from public.users where tenant_id=301;
insert into public.notification_deliveries (
  tenant_id,user_id,channel,template,payload,status,deduplication_key,
  dead_at,retention_until,last_error_code
) select 301,min(id),'email','test','{}','dead','expired-dead',now()-interval '200 days',now()-interval '1 day','invalid_recipient'
from public.users where tenant_id=301;
insert into public.notification_deliveries (
  tenant_id,user_id,channel,template,payload,status,deduplication_key,
  dead_at,retention_until,last_error_code
) select 301,min(id),'email','test','{}','dead','future-dead',now(),now()+interval '180 days','invalid_recipient'
from public.users where tenant_id=301;
insert into public.user_notifications (
  event_id,tenant_id,user_id,event_type,title,body,data
) select event.id,301,min(users.id),event.event_type,event.title,event.body,event.data
from public.notification_events event
cross join public.users users
where event.deduplication_key='event-source-1' and users.tenant_id=301
group by event.id;
select public.cleanup_notification_delivery_data(now(),1000);
do $$
begin
  if exists (select 1 from public.notification_deliveries where deduplication_key='expired-sent')
    then raise exception 'sent_cleanup_failed'; end if;
  if not exists (select 1 from public.notification_deliveries where deduplication_key='expired-pending')
    then raise exception 'pending_cleanup_was_destructive'; end if;
  if exists (select 1 from public.notification_deliveries where deduplication_key='expired-dead')
    then raise exception 'dead_cleanup_failed'; end if;
  if not exists (select 1 from public.notification_deliveries where deduplication_key='future-dead')
    then raise exception 'future_dead_cleanup_was_destructive'; end if;
  if (select count(*) from public.user_notifications) <> 1
    then raise exception 'inbox_history_changed'; end if;
end $$;
SQL

echo "migration 073 rehearsal passed"
