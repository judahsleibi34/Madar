#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CONTAINER_NAME="madar-072-rehearsal-$RANDOM-$$"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:17-alpine}"

cleanup() { docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$CONTAINER_NAME" \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=1g \
  -e POSTGRES_HOST_AUTH_METHOD=trust "$POSTGRES_IMAGE" >/dev/null
docker exec "$CONTAINER_NAME" sh -c 'until pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done'

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
  ((10#$number > 71)) && continue
  docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q < "$migration"
done

docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
insert into public.tenants (tenant_id,brand_name,owner_name,business_type)
select id,'Isolation '||id,'Owner '||id,'business' from generate_series(201,205) id;
insert into auth.users (id,email_confirmed_at,confirmed_at)
select ('00000000-0000-0000-0000-'||lpad(id::text,12,'0'))::uuid,now(),now()
from generate_series(201,205) id;
insert into public.users (auth_id,first_name,last_name,email,tenant_id,account_status,email_verified)
select ('00000000-0000-0000-0000-'||lpad(id::text,12,'0'))::uuid,
       'Owner',id::text,'isolation'||id||'@example.invalid',id,'active',true
from generate_series(201,205) id;
insert into public.tenant_memberships (tenant_id,user_id,auth_id,role,status)
select tenant_id,id,auth_id,'owner','active' from public.users where tenant_id between 201 and 205;

insert into public.builder_projects (
  id,tenant_id,owner_user_id,name,slug,status,draft_schema,published_schema,
  published_version,published_revision,last_published_at
)
select
  ('30000000-0000-0000-0000-'||lpad(t::text,12,'0'))::uuid,t,users.id,
  'Isolation '||t,'isolation-'||t,
  case when t=204 then 'archived' else case when t=205 then 'draft' else 'published' end end,
  '{"defaultPageId":"home","pages":[{"id":"home","slug":"/","isDefault":true,"sections":[]}],"forms":[]}'::jsonb,
  case
    when t=201 then '{"defaultPageId":"home","pages":[{"id":"home","slug":"/","isDefault":true,"sections":[]}],"forms":[]}'::jsonb
    when t=202 then '{"pages":[{"id":"legacy-home","slug":"/","sections":[]}],"forms":[]}'::jsonb
    when t=203 then '{"pages":[{"id":"one","slug":"/","sections":[]},{"id":"two","slug":"/","sections":[]}],"forms":[]}'::jsonb
    else null
  end,
  case when t between 201 and 203 then 1 else 0 end,
  case when t between 201 and 203 then 0 else null end,
  case when t between 201 and 203 then now() else null end
from generate_series(201,205) t
join public.users users on users.tenant_id=t;

insert into public.website_settings (user_id,tenant_id,subdomain,brand,published_project_id,standard_path_slug)
select users.id,users.tenant_id,'isolation-'||users.tenant_id,'Isolation',
       case when users.tenant_id between 201 and 203
         then ('30000000-0000-0000-0000-'||lpad(users.tenant_id::text,12,'0'))::uuid
         else null end,
       'isolation-'||users.tenant_id
from public.users users where users.tenant_id between 201 and 205;
SQL

# Prove a late error rolls the whole migration back.
sed 's/^commit;$/select * from public.__intentional_072_failure__; commit;/' \
  "$REPO_ROOT/database/migrations/072_harden_publication_isolation.sql" |
  docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q >/dev/null 2>&1 &&
  { echo "Expected intentional migration failure" >&2; exit 1; }

rollback_state="$(docker exec "$CONTAINER_NAME" psql -U postgres -Atc   "select coalesce(to_regclass('public.publication_integrity_reviews')::text,'absent')")"
[[ "$rollback_state" == "absent" ]] || { echo "Failed 072 left partial schema: $rollback_state" >&2; exit 1; }

docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/072_harden_publication_isolation.sql"

docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
do $$
begin
  if public.builder_publication_integrity_error(
    (select published_schema from public.builder_projects where tenant_id=201)
  ) is not null then raise exception 'valid_snapshot_rejected'; end if;

  if (select published_schema ->> 'defaultPageId' from public.builder_projects where tenant_id=202)
     <> 'legacy-home' then raise exception 'unambiguous_homepage_not_repaired'; end if;
  if (select published_version from public.builder_projects where tenant_id=202) <> 2
    then raise exception 'repair_did_not_change_cache_version'; end if;

  if not exists (
    select 1 from public.publication_integrity_reviews
    where tenant_id=203 and issue_code in ('homepage_id_missing','homepage_route_ambiguous')
      and review_status='pending'
  ) then raise exception 'ambiguous_snapshot_not_queued_for_review'; end if;

  if not exists (
    select 1 from pg_constraint
    where conname='builder_projects_publication_integrity_check'
      and convalidated=false
  ) then raise exception 'publication_constraint_state_unexpected'; end if;

  if has_table_privilege('anon','public.publication_integrity_reviews','select')
     or has_table_privilege('authenticated','public.publication_integrity_reviews','select')
  then raise exception 'review_table_exposed'; end if;
  if not has_table_privilege('service_role','public.publication_integrity_reviews','select')
  then raise exception 'service_review_access_missing'; end if;

  if (select count(*) from public.website_settings where published_project_id=
      '30000000-0000-0000-0000-000000000201'::uuid) <> 1
  then raise exception 'valid_binding_changed'; end if;
  if (select count(*) from public.builder_projects where tenant_id between 201 and 205) <> 5
  then raise exception 'application_data_lost'; end if;
end
$$;
SQL

# The migration is idempotent and must not duplicate reviews or repairs.
before_state="$(docker exec "$CONTAINER_NAME" psql -U postgres -Atc   "select (select count(*) from publication_integrity_reviews)||':'||
          (select published_version from builder_projects where tenant_id=202)")"
docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  < "$REPO_ROOT/database/migrations/072_harden_publication_isolation.sql"
after_state="$(docker exec "$CONTAINER_NAME" psql -U postgres -Atc   "select (select count(*) from publication_integrity_reviews)||':'||
          (select published_version from builder_projects where tenant_id=202)")"
[[ "$before_state" == "$after_state" ]] || {
  echo "Reapplying 072 changed state: $before_state -> $after_state" >&2
  exit 1
}

# Parse and execute the production diagnostic in the same disposable database.
docker exec -i "$CONTAINER_NAME" psql -U postgres -v ON_ERROR_STOP=1 -q \
  -v site_identifier='isolation-201' \
  -v project_id='30000000-0000-0000-0000-000000000201' \
  < "$REPO_ROOT/database/verification/072_publication_isolation_diagnostic.sql" \
  >/dev/null

echo "Migration 072 disposable rehearsal passed."
