#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WEB_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONTAINER_NAME="madar-105-rehearsal-$RANDOM-$$"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:17-alpine}"
cleanup() { docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$CONTAINER_NAME" --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=1g -e POSTGRES_HOST_AUTH_METHOD=trust "$POSTGRES_IMAGE" >/dev/null
docker exec "$CONTAINER_NAME" sh -c 'until pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done'
docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
create role anon nologin; create role authenticated nologin; create role service_role nologin;
create schema auth; create table auth.users(id uuid primary key,email_confirmed_at timestamptz,confirmed_at timestamptz);
create function auth.uid() returns uuid language sql stable as $$ select null::uuid $$;
create schema storage; create table storage.buckets(id text primary key,name text not null,public boolean not null default false,file_size_limit bigint,allowed_mime_types text[]);
create table storage.objects(id uuid primary key default gen_random_uuid(),bucket_id text references storage.buckets(id),name text); alter table storage.objects enable row level security;
create schema extensions; create extension pgcrypto schema extensions;
SQL

for migration in "$WEB_ROOT"/database/migrations/*.sql; do
  number="$(basename "$migration" | cut -d_ -f1)"
  ((10#$number > 104)) && continue
  docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q < "$migration"
done

docker exec -i "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
insert into public.tenants(tenant_id,brand_name,owner_name) values
  (1051,'Existing canonical','Owner'),(1052,'Backfill canonical','Owner'),
  (1053,'Case normalization','Owner'),(1054,'Invalid fixture','Owner'),
  (1055,'Duplicate fixture A','Owner'),(1056,'Duplicate fixture B','Owner');
insert into auth.users(id,email_confirmed_at) values
  ('00000000-0000-0000-0000-000000001051',now()),('00000000-0000-0000-0000-000000001052',now()),
  ('00000000-0000-0000-0000-000000001053',now()),('00000000-0000-0000-0000-000000001054',now()),
  ('00000000-0000-0000-0000-000000001055',now()),('00000000-0000-0000-0000-000000001056',now());
insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified,email_verified_at)
select ('00000000-0000-0000-0000-'||lpad(tenant_id::text,12,'0'))::uuid,'Owner',tenant_id::text,format('owner-%s@example.invalid',tenant_id),tenant_id,'active',true,now()
from public.tenants where tenant_id between 1051 and 1056;
insert into public.website_settings(user_id,tenant_id,subdomain,standard_path_slug,brand)
select id,tenant_id,
  case tenant_id when 1051 then 'canonical' when 1052 then null when 1053 then 'UPPER-HOST'
       when 1054 then 'api' when 1055 then 'Case-Dupe' when 1056 then 'case-dupe' end,
  case tenant_id when 1051 then 'legacy-alias' when 1052 then 'backfilled-host' when 1053 then 'case-legacy'
       when 1054 then 'valid-invalid-fixture' when 1055 then 'dupe-legacy-a' when 1056 then 'dupe-legacy-b' end,
  format('Tenant %s',tenant_id)
from public.users where tenant_id between 1051 and 1056;
insert into public.builder_projects(id,tenant_id,owner_user_id,name,slug,status,draft_schema,published_schema,published_version,published_revision,last_published_at)
select '10510000-0000-0000-0000-000000000001',1051,id,'Preserved project','preserved-project','published',
  '{"defaultPageId":"home","pages":[{"id":"home","slug":"/","isDefault":true,"sections":[]}],"forms":[{"id":"contact","name":"Contact","fields":[]}]}',
  '{"defaultPageId":"home","pages":[{"id":"home","slug":"/","isDefault":true,"sections":[]}],"forms":[{"id":"contact","name":"Contact","fields":[]}]}',7,0,now()
from public.users where tenant_id=1051;
update public.website_settings
set published_project_id='10510000-0000-0000-0000-000000000001'
where tenant_id=1051;
insert into public.builder_form_submissions(tenant_id,project_id,form_id,answers)
values(1051,'10510000-0000-0000-0000-000000000001','contact','{"answer":"preserved"}');
insert into public.builder_reservations(tenant_id,project_id,site_subdomain,block_id,reservation_title,customer_name)
values(1051,'10510000-0000-0000-0000-000000000001','canonical','reservation','Preserved','Customer');
insert into public.ecommerce_products(tenant_id,sku,slug,translations,status,price)
values(1051,'KEEP-105','keep-105','{"en":{"name":"Preserved"}}','active',10);
insert into public.audit_logs(tenant_id,actor_user_id,action,target_type,target_id)
select 1051,id,'rehearsal.preserve','website_settings','1051' from public.users where tenant_id=1051;
insert into public.site_visit_counters(tenant_id,website_visits,store_visits) values(1051,12,5);
insert into public.tenant_commercial_state(tenant_id) values(1051) on conflict(tenant_id) do nothing;
SQL

if docker exec -i "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q < "$WEB_ROOT/database/migrations/105_canonical_tenant_subdomains.sql"; then
  echo "migration 105 unexpectedly accepted reserved hostname" >&2
  exit 1
fi

docker exec "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q -c "delete from public.website_settings where tenant_id=1054"
if docker exec -i "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q < "$WEB_ROOT/database/migrations/105_canonical_tenant_subdomains.sql"; then
  echo "migration 105 unexpectedly accepted case-insensitive collision" >&2
  exit 1
fi

docker exec "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q -c "delete from public.website_settings where tenant_id in(1055,1056)"
docker exec -i "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q < "$WEB_ROOT/database/migrations/105_canonical_tenant_subdomains.sql"
docker exec -i "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q < "$WEB_ROOT/database/verification/105_verify_canonical_tenant_subdomains.sql"

docker exec -i "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
do $$
begin
  if (select subdomain from public.website_settings where tenant_id=1051)<>'canonical'
     or (select standard_path_slug from public.website_settings where tenant_id=1051)<>'legacy-alias' then
    raise exception 'existing_canonical_or_legacy_alias_changed';
  end if;
  if (select subdomain from public.website_settings where tenant_id=1052)<>'backfilled-host' then
    raise exception 'missing_subdomain_not_backfilled';
  end if;
  if (select subdomain from public.website_settings where tenant_id=1053)<>'upper-host'
     or (select standard_path_slug from public.website_settings where tenant_id=1053)<>'case-legacy' then
    raise exception 'case_canonicalization_or_legacy_preservation_failed';
  end if;
  if (select count(*) from public.builder_projects where id='10510000-0000-0000-0000-000000000001')<>1
     or (select published_project_id from public.website_settings where tenant_id=1051)<>'10510000-0000-0000-0000-000000000001'
     or (select count(*) from public.builder_form_submissions where project_id='10510000-0000-0000-0000-000000000001')<>1
     or (select count(*) from public.builder_reservations where project_id='10510000-0000-0000-0000-000000000001')<>1
     or (select count(*) from public.ecommerce_products where tenant_id=1051)<>1
     or (select count(*) from public.tenant_commercial_state where tenant_id=1051)<>1
     or (select count(*) from public.audit_logs where action='rehearsal.preserve')<>1
     or (select website_visits from public.site_visit_counters where tenant_id=1051)<>12 then
    raise exception 'cross_domain_data_not_preserved';
  end if;
end $$;
SQL

echo "Migration 105 schema 104 to 105 rehearsal passed"
