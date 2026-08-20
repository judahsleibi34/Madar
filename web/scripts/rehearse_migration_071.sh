#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONTAINER_NAME="madar-071-rehearsal-$RANDOM-$$"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:17-alpine}"

cleanup() {
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker run -d \
  --name "$CONTAINER_NAME" \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=1g \
  -e POSTGRES_HOST_AUTH_METHOD=trust \
  "$POSTGRES_IMAGE" >/dev/null

docker exec "$CONTAINER_NAME" sh -c \
  'until pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done'

bootstrap_database() {
  local database_name="$1"
  docker exec -i "$CONTAINER_NAME" psql \
    -U postgres -d "$database_name" -v ON_ERROR_STOP=1 -q <<'SQL'
create role anon nologin;
create role authenticated nologin;
create role service_role nologin;
create schema auth;
create table auth.users (
  id uuid primary key,
  email_confirmed_at timestamptz,
  confirmed_at timestamptz
);
create function auth.uid() returns uuid
language sql stable as $$ select null::uuid $$;
create schema storage;
create table storage.buckets (
  id text primary key,
  name text not null,
  public boolean not null default false,
  file_size_limit bigint,
  allowed_mime_types text[]
);
create table storage.objects (
  id uuid primary key default gen_random_uuid(),
  bucket_id text references storage.buckets(id),
  name text
);
alter table storage.objects enable row level security;
SQL
}

apply_foundation_migrations() {
  local database_name="$1"
  local migration number
  for migration in "$REPO_ROOT"/database/migrations/*.sql; do
    number="$(basename "$migration" | cut -d_ -f1)"
    if ((10#$number > 70)); then
      continue
    fi
    docker exec -i "$CONTAINER_NAME" psql \
      -U postgres -d "$database_name" -v ON_ERROR_STOP=1 -q < "$migration"
  done
}

bootstrap_database postgres
apply_foundation_migrations postgres
docker exec -i "$CONTAINER_NAME" psql \
  -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/verification/071_rehearsal_seed.sql"

# Prove a late failure rolls the whole 071 transaction back.
sed \
  "s/^commit;$/select * from public.__intentional_071_failure__; commit;/" \
  "$REPO_ROOT/database/migrations/071_create_commercial_entitlements.sql" |
  docker exec -i "$CONTAINER_NAME" psql \
    -U postgres -v ON_ERROR_STOP=1 -q >/dev/null 2>&1 &&
  {
    echo "Expected the intentional migration failure" >&2
    exit 1
  }

rollback_state="$(
  docker exec "$CONTAINER_NAME" psql -U postgres -Atc \
    "select coalesce(to_regclass('public.tenant_subscriptions')::text,'absent')
      || ':' || exists (
        select 1 from information_schema.columns
        where table_schema='public' and table_name='website_settings'
          and column_name='standard_path_slug'
      )::text"
)"
if [[ "$rollback_state" != "absent:false" ]]; then
  echo "Failed 071 transaction left partial schema: $rollback_state" >&2
  exit 1
fi

docker exec -i "$CONTAINER_NAME" psql \
  -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/071_create_commercial_entitlements.sql"
docker exec -i "$CONTAINER_NAME" psql \
  -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/verification/071_verify_commercial_entitlements.sql"
docker exec -i "$CONTAINER_NAME" psql \
  -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/verification/071_rehearsal_assertions.sql"

# Reapplication must preserve existing rows and remain successful.
docker exec -i "$CONTAINER_NAME" psql \
  -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/071_create_commercial_entitlements.sql"

period_key="$(date -u +%Y-%m)"
docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<SQL
insert into public.ai_token_allocations (
  tenant_id,period_key,allocation_type,standard_tokens,idempotency_key
) values (109,'$period_key','migration',1000,'concurrent-finalization');
select * from public.reserve_ai_standard_tokens(
  109,(select id from public.users where tenant_id=109),'$period_key',
  'concurrent-finalize-a-109','analytics',400,now()+interval '15 minutes'
);
select * from public.reserve_ai_standard_tokens(
  109,(select id from public.users where tenant_id=109),'$period_key',
  'concurrent-finalize-b-109','analytics',400,now()+interval '15 minutes'
);
SQL

docker exec "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q -c \
  "select * from public.finalize_ai_standard_tokens('concurrent-finalize-a-109','mock','mock','v1',550,0,50,600,600,'succeeded','provider',false)" &
first_finalize_pid=$!
docker exec "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q -c \
  "select * from public.finalize_ai_standard_tokens('concurrent-finalize-b-109','mock','mock','v1',550,0,50,600,600,'succeeded','provider',false)" &
second_finalize_pid=$!
wait "$first_finalize_pid"
wait "$second_finalize_pid"

docker exec "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q -c \
  "begin; select * from public.assign_commercial_addon(106,'ai_analytics_starter',1,'active','v1',500,'month',(select id from users where tenant_id=106),'concurrent starter','concurrent-starter'); select pg_sleep(2); commit" &
starter_pid=$!
docker exec "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q -c \
  "select * from public.assign_commercial_addon(106,'ai_analytics_plus',1,'active','v1',1000,'month',(select id from users where tenant_id=106),'concurrent plus','concurrent-plus')" &
plus_pid=$!
wait "$starter_pid"
wait "$plus_pid"

docker exec -i "$CONTAINER_NAME" psql \
  -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
do $$
declare
  active_package text;
  inactive_package text;
  package_tokens bigint;
begin
  if (select count(*) from public.ai_token_ledger where tenant_id=109)<>2
    or (select sum(covered_standard_tokens) from public.ai_token_ledger where tenant_id=109)<>1000
    or (select sum(deficit_standard_tokens) from public.ai_token_ledger where tenant_id=109)<>200
  then
    raise exception 'concurrent_token_finalization_failed';
  end if;

  if (
    select count(*) from public.tenant_addons
    where tenant_id=106 and state='active'
      and addon_id in ('ai_analytics_starter','ai_analytics_plus')
  )<>1 then
    raise exception 'concurrent_ai_package_activation_failed';
  end if;

  select addon_id into active_package
  from public.tenant_addons
  where tenant_id=106 and state='active'
    and addon_id in ('ai_analytics_starter','ai_analytics_plus');
  inactive_package := case
    when active_package='ai_analytics_starter' then 'ai_analytics_plus'
    else 'ai_analytics_starter'
  end;
  package_tokens := case
    when active_package='ai_analytics_starter' then 500000 else 1500000
  end;
  perform public.ensure_ai_monthly_allocation(
    106,
    to_char(now() at time zone 'UTC','YYYY-MM'),
    active_package,
    package_tokens,
    'monthly-active-package',
    'rehearsal active package'
  );
  if (
    select count(*) from public.ai_token_allocations
    where tenant_id=106 and allocation_type='monthly_package' and state='active'
  )<>1 then
    raise exception 'monthly_ai_allocation_uniqueness_failed';
  end if;
  begin
    perform public.ensure_ai_monthly_allocation(
      106,
      to_char(now() at time zone 'UTC','YYYY-MM'),
      inactive_package,
      case when inactive_package='ai_analytics_starter' then 500000 else 1500000 end,
      'monthly-inactive-package',
      'stale request must fail'
    );
    raise exception 'inactive_ai_package_received_allocation';
  exception
    when sqlstate 'P0001' then
      if sqlerrm<>'ai_monthly_package_not_active' then
        raise;
      end if;
  end;

  begin
    insert into public.tenant_addons (
      tenant_id,addon_id,quantity,state,catalog_version,price_minor,
      billing_interval,idempotency_key
    ) values (
      106,
      case when exists (
        select 1 from public.tenant_addons
        where tenant_id=106 and addon_id='ai_analytics_starter' and state='active'
      ) then 'ai_analytics_plus' else 'ai_analytics_starter' end,
      1,'active','v1',500,'month','direct-unique-index-proof'
    );
    raise exception 'ai_package_partial_unique_index_did_not_reject';
  exception when unique_violation then
    null;
  end;
end
$$;
SQL

echo "Migration 071 disposable rehearsal passed."
