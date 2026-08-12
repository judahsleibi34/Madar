#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONTAINER_NAME="madar-076-079-rehearsal-$RANDOM-$$"
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
  ((10#$number > 75)) && continue
  docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q < "$migration"
done

docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
insert into public.tenants (tenant_id,brand_name,owner_name,business_type)
values (501,'Migration Test','Owner','business');
insert into auth.users (id,email_confirmed_at,confirmed_at)
values ('00000000-0000-0000-0000-000000000501',now(),now());
insert into public.users (auth_id,first_name,last_name,email,tenant_id,account_status,email_verified)
values ('00000000-0000-0000-0000-000000000501','Active','Member','active@example.invalid',501,'active',true);
insert into public.tenant_memberships (tenant_id,user_id,auth_id,role,status)
select 501,id,auth_id,'member','active' from public.users where tenant_id=501;

select public.register_app_installation(
  id,501,'123e4567-e89b-42d3-a456-426614174000','linux','browser','granted',false
) from public.users where tenant_id=501;
select public.bind_web_push_subscription_to_installation(
  id,501,'123e4567-e89b-42d3-a456-426614174000',
  'https://push.example.invalid/device','test-key','test-auth','test'
) from public.users where tenant_id=501;

insert into public.builder_assets (
  tenant_id,uploader_user_id,storage_key,original_filename,managed_filename,
  mime_type,size_bytes,sha256
)
select 501,id,'tenant_501/builder_assets/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg',
       'existing.jpg','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg','image/jpeg',100,repeat('a',64)
from public.users where tenant_id=501;

insert into public.calendar_tasks (
  tenant_id,owner_user_id,title,status,scheduled_start,scheduled_end
)
select 501,id,'Overdue unfinished','todo',now() - interval '2 hours',now() - interval '1 hour'
from public.users where tenant_id=501;
SQL

# Each migration is applied explicitly; no later file can be selected by a runner.
docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/076_fan_out_calendar_reminders_to_web_push.sql"
docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/076_fan_out_calendar_reminders_to_web_push.sql"

docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
do $$
declare event_row public.notification_events; outbox_row public.notification_outbox; member_id integer;
begin
  select id into member_id from public.users where tenant_id=501;
  insert into public.notification_events (tenant_id,event_type,source_type,source_id,title,body,data)
  values (501,'calendar_task_reminder','calendar_task','task-test','Reminder','Reminder','{}')
  returning * into event_row;
  insert into public.notification_outbox (
    tenant_id,user_id,channel,template,payload,status,deduplication_key,retention_until
  ) values (
    501,member_id,'internal','calendar_reminder',jsonb_build_object('event_id',event_row.id),
    'sent','rehearsal-calendar-reminder',now()+interval '90 days'
  ) returning * into outbox_row;
  insert into public.notification_deliveries (
    outbox_id,tenant_id,event_id,user_id,channel,template,payload,deduplication_key
  ) values (
    outbox_row.id,501,event_row.id,member_id,'internal','calendar_reminder','{}',
    'rehearsal-internal-calendar-reminder'
  );
end $$;

do $$ begin
  if (select count(*) from public.notification_deliveries where channel='web_push' and template='calendar_reminder') <> 1
  then raise exception 'calendar_reminder_push_fanout_invalid'; end if;
end $$;
SQL

docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/077_allow_builder_video_assets.sql"
docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/077_allow_builder_video_assets.sql"
docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
insert into public.builder_assets (
  tenant_id,uploader_user_id,storage_key,original_filename,managed_filename,mime_type,size_bytes,sha256
)
select 501,id,'tenant_501/builder_assets/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.mp4',
       'video.mp4','bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.mp4','video/mp4',100,repeat('b',64)
from public.users where tenant_id=501;
SQL

docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/078_allow_builder_document_assets.sql"
docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/078_allow_builder_document_assets.sql"
docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
insert into public.builder_assets (
  tenant_id,uploader_user_id,storage_key,original_filename,managed_filename,mime_type,size_bytes,sha256
)
select 501,id,format('tenant_501/builder_assets/%s.%s',repeat(prefix,32),extension),
       format('document.%s',extension),format('%s.%s',repeat(prefix,32),extension),mime_type,100,repeat('c',64)
from public.users cross join (values
  ('c','pdf','application/pdf'),
  ('d','doc','application/msword'),
  ('e','docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document')
) asset(prefix,extension,mime_type)
where tenant_id=501;

do $$ begin
  begin
    insert into public.builder_assets (
      tenant_id,storage_key,original_filename,managed_filename,mime_type,size_bytes,sha256
    ) values (
      501,'tenant_501/builder_assets/ffffffffffffffffffffffffffffffff.zip','bad.zip',
      'ffffffffffffffffffffffffffffffff.zip','application/zip',1,repeat('f',64)
    );
    raise exception 'unsupported_builder_extension_accepted';
  exception when check_violation then null;
  end;
end $$;
SQL

docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/079_add_calendar_task_archive_state.sql"
docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/079_add_calendar_task_archive_state.sql"
docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
do $$ begin
  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='calendar_tasks' and column_name='archived_at'
  ) then raise exception 'calendar_archive_column_missing'; end if;
  if (select status from public.calendar_tasks where title='Overdue unfinished') <> 'todo'
  then raise exception 'historic_task_status_changed'; end if;
  if (select archived_at from public.calendar_tasks where title='Overdue unfinished') is not null
  then raise exception 'historic_task_was_archived'; end if;
  if (select count(*) from public.builder_assets where tenant_id=501) <> 5
  then raise exception 'representative_builder_assets_invalid'; end if;
end $$;
SQL

# Migration 080 is deliberately applied explicitly and twice. It is additive,
# sparse (no backfill), and must be safe to replay under this repository's
# migration convention.
docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/080_create_notification_preferences.sql"
docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/080_create_notification_preferences.sql"
docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
do $$
declare member_id integer;
begin
  select id into member_id from public.users where tenant_id=501;
  insert into public.notification_preferences (tenant_id,user_id,category,channel,enabled)
  values (501,member_id,'calendar','push',false);

  begin
    insert into public.notification_preferences (tenant_id,user_id,category,channel,enabled)
    values (501,member_id,'calendar','push',true);
    raise exception 'preference_unique_constraint_missing';
  exception when unique_violation then null;
  end;

  begin
    insert into public.notification_preferences (tenant_id,user_id,category,channel,enabled)
    values (501,member_id,'forms','email',false);
    raise exception 'unsupported_preference_pair_accepted';
  exception when check_violation then null;
  end;
end $$;

do $$ begin
  if not exists (
    select 1 from pg_constraint
    where conname='notification_preferences_tenant_user_category_channel_unique'
  ) then raise exception 'preference_unique_constraint_not_found'; end if;
  if not exists (
    select 1 from pg_indexes
    where schemaname='public' and indexname='notification_preferences_tenant_user_idx'
  ) then raise exception 'preference_index_not_found'; end if;
  if not exists (
    select 1 from pg_tables
    where schemaname='public' and tablename='notification_preferences' and rowsecurity
  ) then raise exception 'preference_rls_not_enabled'; end if;
  if not has_table_privilege('service_role','public.notification_preferences','select,insert,update,delete')
  then raise exception 'service_role_preference_grant_missing'; end if;
  if has_table_privilege('authenticated','public.notification_preferences','select')
  then raise exception 'authenticated_preference_grant_too_broad'; end if;
  if (select enabled from public.notification_preferences limit 1) is distinct from false
  then raise exception 'explicit_disabled_preference_not_retained'; end if;
end $$;
SQL

echo "migrations 076-080 rehearsal passed"
