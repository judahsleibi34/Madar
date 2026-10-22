#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PG_IMAGE="postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73"
REST_IMAGE="public.ecr.aws/supabase/postgrest@sha256:d155c6718ed9a9f990d159a2ab7c0a3f16944dbb6d0a0344557421042acfe0df"
VAULT_IMAGE="hashicorp/vault@sha256:5be49781ecf78bfe775c5309c6a4d9f4e9e040b6c885c99eb2b12fb69855e1a2"
RUN_ID="${RANDOM}-$$"
NETWORK="madar-c3-${RUN_ID}"
PG_NAME="madar-c3-pg-${RUN_ID}"
REST_NAME="madar-c3-rest-${RUN_ID}"
GATEWAY_NAME="madar-c3-gateway-${RUN_ID}"
VAULT_NAME="madar-c3-vault-${RUN_ID}"
TEMP_DIR="$(mktemp -d)"
JWT_SECRET="$(openssl rand -hex 32)"
ROOT_TOKEN="$(openssl rand -hex 24)"

cleanup() {
  docker rm -f "${GATEWAY_NAME}" "${REST_NAME}" "${VAULT_NAME}" "${PG_NAME}" >/dev/null 2>&1 || true
  docker network rm "${NETWORK}" >/dev/null 2>&1 || true
  find "${TEMP_DIR}" -type f -exec chmod u+w {} + 2>/dev/null || true
  rm -rf "${TEMP_DIR}"
}
trap cleanup EXIT

docker network create "${NETWORK}" >/dev/null
docker run -d --name "${PG_NAME}" --network "${NETWORK}" --network-alias pg \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=2g \
  -e POSTGRES_HOST_AUTH_METHOD=trust "${PG_IMAGE}" >/dev/null
for _ in $(seq 1 60); do
  docker exec "${PG_NAME}" pg_isready -U postgres >/dev/null 2>&1 && break
  sleep 0.25
done

docker exec "${PG_NAME}" pg_isready -U postgres >/dev/null

docker exec -i "${PG_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres <<'SQL'
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create role authenticator noinherit login password 'fixture-password';
grant anon,authenticated,service_role to authenticator;
create schema auth;
create table auth.users(id uuid primary key,email_confirmed_at timestamptz,confirmed_at timestamptz);
create function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid
$$;
create schema storage;
create table storage.buckets(id text primary key,name text not null,public boolean not null default false,file_size_limit bigint,allowed_mime_types text[]);
create table storage.objects(id uuid primary key default gen_random_uuid(),bucket_id text references storage.buckets(id),name text);
alter table storage.objects enable row level security;
create schema extensions;
create extension pgcrypto schema extensions;
SQL

apply_range() {
  local minimum="$1" maximum="$2" migration number
  for migration in "${ROOT_DIR}"/web/database/migrations/*.sql; do
    number="$(basename "${migration}" | cut -d_ -f1)"
    if ((10#${number} < minimum || 10#${number} > maximum || 10#${number} == 142)); then
      continue
    fi
    docker exec -e PGOPTIONS='-c client_min_messages=warning' -i "${PG_NAME}" \
      psql -X -v ON_ERROR_STOP=1 -U postgres -q < "${migration}"
  done
}
apply_range 1 114
docker exec "${PG_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres -q \
  -c 'alter table auth.users add column email text'
apply_range 115 156

docker exec -i "${PG_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres <<'SQL'
insert into auth.users(id,email,email_confirmed_at,confirmed_at)
values('70000000-0000-4000-8000-000000000001','sync@example.invalid',now(),now());
insert into public.tenants(tenant_id,brand_name,owner_name) values(7001,'Sync','Owner');
insert into public.users(id,auth_id,first_name,last_name,email,tenant_id,account_kind,account_status)
overriding system value values(7001,'70000000-0000-4000-8000-000000000001','Sync','Owner',
  'sync@example.invalid',7001,'platform','active');
insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status)
values(7001,7001,'70000000-0000-4000-8000-000000000001','owner','active');
insert into public.builder_projects(id,tenant_id,owner_user_id,name,slug,status,draft_schema)
values('70000000-0000-4000-8000-000000000002',7001,7001,'Sync project','sync-project','draft',
  '{"workspaceKind":"data"}'::jsonb);
insert into public.data_sources(id,tenant_id,project_id,creator_user_id,source_type,
  display_name,status,provider_key,resource_type)
values('70000000-0000-4000-8000-000000000003',7001,
  '70000000-0000-4000-8000-000000000002',7001,'api_provider','Fixture','active',
  'http_fixture','records');
insert into public.data_source_resources(id,tenant_id,project_id,source_id,resource_key)
values('70000000-0000-4000-8000-000000000004',7001,
  '70000000-0000-4000-8000-000000000002','70000000-0000-4000-8000-000000000003','records');
SQL

SERVICE_JWT="$(docker run --rm -e JWT_SECRET="${JWT_SECRET}" madar-backend-test \
  python -c "import jwt,os,time;print(jwt.encode({'role':'service_role','exp':int(time.time())+3600},os.environ['JWT_SECRET'],algorithm='HS256'))")"
ANON_JWT="$(docker run --rm -e JWT_SECRET="${JWT_SECRET}" madar-backend-test \
  python -c "import jwt,os,time;print(jwt.encode({'role':'anon','exp':int(time.time())+3600},os.environ['JWT_SECRET'],algorithm='HS256'))")"

docker run -d --name "${REST_NAME}" --network "${NETWORK}" --network-alias rest \
  -e PGRST_DB_URI='postgres://authenticator:fixture-password@pg:5432/postgres' \
  -e PGRST_DB_SCHEMAS=public -e PGRST_DB_ANON_ROLE=anon \
  -e PGRST_JWT_SECRET="${JWT_SECRET}" -e PGRST_DB_CONFIG=false \
  "${REST_IMAGE}" >/dev/null
for _ in $(seq 1 60); do
  docker run --rm --network "${NETWORK}" madar-backend-test \
    python -c "import httpx;raise SystemExit(0 if httpx.get('http://rest:3000/',timeout=1).status_code<500 else 1)" \
    >/dev/null 2>&1 && break
  sleep 0.25
done

docker run -d --name "${GATEWAY_NAME}" --network "${NETWORK}" --network-alias gateway \
  -v "${ROOT_DIR}/web/backend/tests/disposable_supabase_gateway.py:/fixture/gateway.py:ro" \
  -e POSTGREST_UPSTREAM=http://rest:3000 madar-backend-test \
  python /fixture/gateway.py >/dev/null
for _ in $(seq 1 60); do
  docker run --rm --network "${NETWORK}" madar-backend-test \
    python -c "import httpx;raise SystemExit(0 if httpx.get('http://gateway:8000/rest/v1/',timeout=1).status_code<500 else 1)" \
    >/dev/null 2>&1 && break
  sleep 0.25
done

docker run -d --rm --name "${VAULT_NAME}" --network "${NETWORK}" --network-alias vault \
  --cap-add IPC_LOCK -e VAULT_DEV_ROOT_TOKEN_ID="${ROOT_TOKEN}" \
  -e VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200 \
  -v "${ROOT_DIR}/web/deployment/vault/data-sources-transit-policy.hcl:/vault/data-sources-policy.hcl:ro" \
  "${VAULT_IMAGE}" server -dev >/dev/null
for _ in $(seq 1 60); do
  docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN="${ROOT_TOKEN}" \
    "${VAULT_NAME}" vault status >/dev/null 2>&1 && break
  sleep 0.25
done
docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN="${ROOT_TOKEN}" \
  "${VAULT_NAME}" vault secrets enable transit >/dev/null
docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN="${ROOT_TOKEN}" \
  "${VAULT_NAME}" vault write transit/keys/madar-data-sources derived=true \
  exportable=false allow_plaintext_backup=false >/dev/null
docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN="${ROOT_TOKEN}" \
  "${VAULT_NAME}" vault policy write madar-data-sources /vault/data-sources-policy.hcl >/dev/null
APP_TOKEN="$(docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN="${ROOT_TOKEN}" \
  "${VAULT_NAME}" vault token create -policy=madar-data-sources -ttl=10m \
  -explicit-max-ttl=20m -renewable=true -field=token)"
install -m 0600 /dev/null "${TEMP_DIR}/token"
printf '%s' "${APP_TOKEN}" > "${TEMP_DIR}/token"
chmod 0400 "${TEMP_DIR}/token"

docker run --rm --network "container:${VAULT_NAME}" --user "$(id -u):$(id -g)" \
  -v "${ROOT_DIR}/web/backend:/app:ro" -v "${TEMP_DIR}:/run/madar-c3:ro" -w /app \
  -e HOME=/tmp -e MPLCONFIGDIR=/tmp/matplotlib -e PYTHONPATH=/app -e APP_ENV=test \
  -e COMMERCIAL_ENTITLEMENTS_ENFORCED=false \
  -e DATA_UPLOAD_DIR=/tmp/madar-c3/uploads \
  -e MADAR_CHECKPOINT_SCRATCH_DIR=/tmp/madar-c3/checkpoints \
  -e SUPABASE_URL=http://gateway:8000 -e SUPABASE_ANON_KEY="${ANON_JWT}" \
  -e SUPABASE_SERVICE_KEY="${SERVICE_JWT}" \
  -e DATA_SOURCE_CREDENTIAL_ENVIRONMENT=test -e DATA_SOURCE_VAULT_ADDR=http://127.0.0.1:8200 \
  -e DATA_SOURCE_VAULT_TOKEN_FILE=/run/madar-c3/token \
  -e DATA_SOURCE_VAULT_TRANSIT_KEY=madar-data-sources \
  madar-backend-test python tests/rehearse_automatic_source_sync_integration.py
