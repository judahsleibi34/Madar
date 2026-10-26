#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PG_IMAGE="postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73"
REST_IMAGE="public.ecr.aws/supabase/postgrest@sha256:d155c6718ed9a9f990d159a2ab7c0a3f16944dbb6d0a0344557421042acfe0df"
VAULT_IMAGE="hashicorp/vault@sha256:5be49781ecf78bfe775c5309c6a4d9f4e9e040b6c885c99eb2b12fb69855e1a2"
RUN_ID="browser-${RANDOM}-$$"
DATABASE_ID="madar_e2e_${RUN_ID//-/_}"
NETWORK="madar-c3-browser-${RUN_ID}"
PG_NAME="madar-c3-browser-pg-${RUN_ID}"
REST_NAME="madar-c3-browser-rest-${RUN_ID}"
GATEWAY_NAME="madar-c3-browser-gateway-${RUN_ID}"
VAULT_NAME="madar-c3-browser-vault-${RUN_ID}"
FIXTURE_NAME="madar-c3-browser-fixture-${RUN_ID}"
BACKEND_NAME="madar-c3-browser-backend-${RUN_ID}"
TEMP_DIR="$(mktemp -d)"
REPORT_DIR="${TEMP_DIR}/private-reports"
ARTIFACT_DIR="${MADAR_E2E_ARTIFACT_DIR:-/tmp/madar-data-sources-c3-step5-${RUN_ID}}"
JWT_SECRET="$(openssl rand -hex 32)"
ROOT_TOKEN="$(openssl rand -hex 24)"
CONTROL_TOKEN="$(openssl rand -hex 24)"
PROVIDER_TOKEN="fixture-token-not-a-real-credential"
GOOGLE_STATE_KEY="$(openssl rand -hex 32)"
AUTH_ID="70000000-0000-4000-8000-000000000001"
PROJECT_ID="70000000-0000-4000-8000-000000000002"
CROSS_AUTH_ID="70000000-0000-4000-8000-000000000011"
CROSS_PROJECT_ID="70000000-0000-4000-8000-000000000012"
VITE_PID=""

free_port() {
  python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()'
}

GATEWAY_PORT="$(free_port)"
VAULT_PORT="$(free_port)"
PROVIDER_PORT="$(free_port)"
OBJECT_PORT="$(free_port)"
CONTROL_PORT="$(free_port)"
BACKEND_PORT="$(free_port)"
FRONTEND_PORT="$(free_port)"

cleanup() {
  local status=$?
  if ((status != 0)); then
    docker logs "${BACKEND_NAME}" >"${ARTIFACT_DIR}/backend.log" 2>&1 || true
    docker logs "${FIXTURE_NAME}" >"${ARTIFACT_DIR}/fixture.log" 2>&1 || true
    docker logs "${GATEWAY_NAME}" >"${ARTIFACT_DIR}/gateway.log" 2>&1 || true
  fi
  if [[ -n "${VITE_PID}" ]]; then
    kill "${VITE_PID}" >/dev/null 2>&1 || true
    wait "${VITE_PID}" >/dev/null 2>&1 || true
  fi
  docker rm -f "${BACKEND_NAME}" "${FIXTURE_NAME}" "${GATEWAY_NAME}" \
    "${REST_NAME}" "${VAULT_NAME}" "${PG_NAME}" >/dev/null 2>&1 || true
  docker network rm "${NETWORK}" >/dev/null 2>&1 || true
  find "${TEMP_DIR}" -type f -exec chmod u+w {} + 2>/dev/null || true
  rm -rf "${TEMP_DIR}"
  return "${status}"
}
trap cleanup EXIT

mkdir -p "${ARTIFACT_DIR}" "${REPORT_DIR}"
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
apply_range 115 141

docker exec -i "${PG_NAME}" psql -X -v ON_ERROR_STOP=1 -U postgres <<SQL
insert into auth.users(id,email,email_confirmed_at,confirmed_at) values
('${AUTH_ID}','browser@example.invalid',now(),now()),
('${CROSS_AUTH_ID}','cross@example.invalid',now(),now());
insert into public.tenants(tenant_id,brand_name,owner_name) values
(7001,'Browser E2E','Owner'),(7002,'Cross tenant','Owner');
insert into public.users(id,auth_id,first_name,last_name,email,tenant_id,account_kind,account_status)
overriding system value values
(7001,'${AUTH_ID}','Browser','Owner','browser@example.invalid',7001,'platform','active'),
(7002,'${CROSS_AUTH_ID}','Cross','Owner','cross@example.invalid',7002,'platform','active');
insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values
(7001,7001,'${AUTH_ID}','owner','active'),
(7002,7002,'${CROSS_AUTH_ID}','owner','active');
insert into public.builder_projects(id,tenant_id,owner_user_id,name,slug,status,draft_schema) values
('${PROJECT_ID}',7001,7001,'Browser API project','browser-api-project','draft','{"workspaceKind":"data"}'::jsonb),
('${CROSS_PROJECT_ID}',7002,7002,'Cross project','cross-project','draft','{"workspaceKind":"data"}'::jsonb);
SQL

SERVICE_JWT="$(docker run --rm -e JWT_SECRET="${JWT_SECRET}" madar-backend-test \
  python -c "import jwt,os,time;print(jwt.encode({'role':'service_role','exp':int(time.time())+3600},os.environ['JWT_SECRET'],algorithm='HS256'))")"
ANON_JWT="$(docker run --rm -e JWT_SECRET="${JWT_SECRET}" madar-backend-test \
  python -c "import jwt,os,time;print(jwt.encode({'role':'anon','exp':int(time.time())+3600},os.environ['JWT_SECRET'],algorithm='HS256'))")"
ACCESS_JWT="$(docker run --rm -e JWT_SECRET="${JWT_SECRET}" -e AUTH_ID="${AUTH_ID}" madar-backend-test \
  python -c "import jwt,os,time;print(jwt.encode({'role':'authenticated','sub':os.environ['AUTH_ID'],'aud':'authenticated','exp':int(time.time())+3600},os.environ['JWT_SECRET'],algorithm='HS256'))")"

docker run -d --name "${REST_NAME}" --network "${NETWORK}" --network-alias rest \
  -e PGRST_DB_URI='postgres://authenticator:fixture-password@pg:5432/postgres' \
  -e PGRST_DB_SCHEMAS=public -e PGRST_DB_ANON_ROLE=anon \
  -e PGRST_JWT_SECRET="${JWT_SECRET}" -e PGRST_DB_CONFIG=false "${REST_IMAGE}" >/dev/null
for _ in $(seq 1 60); do
  docker run --rm --network "${NETWORK}" madar-backend-test \
    python -c "import httpx;raise SystemExit(0 if httpx.get('http://rest:3000/',timeout=1).status_code<500 else 1)" \
    >/dev/null 2>&1 && break
  sleep 0.25
done

docker run -d --name "${GATEWAY_NAME}" --network "${NETWORK}" --network-alias gateway \
  -p "127.0.0.1:${GATEWAY_PORT}:8000" \
  -v "${ROOT_DIR}/web/backend/tests/disposable_supabase_gateway.py:/fixture/gateway.py:ro" \
  -e POSTGREST_UPSTREAM=http://rest:3000 -e AUTH_TEST_TOKEN="${ACCESS_JWT}" \
  -e AUTH_TEST_USER_ID="${AUTH_ID}" -e AUTH_TEST_EMAIL=browser@example.invalid \
  madar-backend-test python /fixture/gateway.py >/dev/null

docker run -d --name "${VAULT_NAME}" --network "${NETWORK}" --network-alias vault \
  -p "127.0.0.1:${VAULT_PORT}:8200" --cap-add IPC_LOCK \
  -e VAULT_DEV_ROOT_TOKEN_ID="${ROOT_TOKEN}" -e VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200 \
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
  "${VAULT_NAME}" vault write transit/keys/madar-data-sources derived=true exportable=false allow_plaintext_backup=false >/dev/null
docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN="${ROOT_TOKEN}" \
  "${VAULT_NAME}" vault policy write madar-data-sources /vault/data-sources-policy.hcl >/dev/null
APP_TOKEN="$(docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN="${ROOT_TOKEN}" \
  "${VAULT_NAME}" vault token create -policy=madar-data-sources -ttl=20m -explicit-max-ttl=30m \
  -renewable=true -field=token)"
install -m 0600 /dev/null "${TEMP_DIR}/vault-token"
printf '%s' "${APP_TOKEN}" > "${TEMP_DIR}/vault-token"
chmod 0400 "${TEMP_DIR}/vault-token"

COMMON_ENV=(
  -e APP_ENV=test -e COMMERCIAL_ENTITLEMENTS_ENFORCED=false -e RATE_LIMIT_ENABLED=false
  -e SUPABASE_URL="http://127.0.0.1:${GATEWAY_PORT}"
  -e SUPABASE_ANON_KEY="${ANON_JWT}" -e SUPABASE_SERVICE_KEY="${SERVICE_JWT}"
  -e DATA_SOURCE_CREDENTIAL_ENVIRONMENT=test
  -e DATA_SOURCE_VAULT_ADDR="http://127.0.0.1:${VAULT_PORT}"
  -e DATA_SOURCE_VAULT_TOKEN_FILE=/run/madar-e2e/vault-token
  -e DATA_SOURCE_VAULT_TRANSIT_KEY=madar-data-sources
  -e MADAR_TEST_WEBHOOK_ADAPTER_ENABLED=true -e MADAR_WEBHOOK_INGRESS_ENABLED=true
  -e MADAR_TEST_HTTP_PROVIDER_URL="http://127.0.0.1:${PROVIDER_PORT}"
  -e GOOGLE_SHEETS_PROVIDER_ENABLED=true -e GOOGLE_SHEETS_CLIENT_ID=fixture-google-client
  -e GOOGLE_SHEETS_CLIENT_SECRET=fixture-google-client-secret
  -e GOOGLE_SHEETS_STATE_KEY="${GOOGLE_STATE_KEY}"
  -e GOOGLE_SHEETS_REDIRECT_URI="http://127.0.0.1:${FRONTEND_PORT}/api/data/oauth/google-sheets/callback"
  -e GOOGLE_SHEETS_AUTHORIZATION_ENDPOINT="http://127.0.0.1:${PROVIDER_PORT}/google/authorize"
  -e GOOGLE_SHEETS_TOKEN_ENDPOINT="http://127.0.0.1:${PROVIDER_PORT}/google"
  -e GOOGLE_SHEETS_API_ENDPOINT="http://127.0.0.1:${PROVIDER_PORT}/google"
  -e DATA_IMMUTABLE_STORAGE_BACKEND=test_http
  -e DATA_IMMUTABLE_TEST_URL="http://127.0.0.1:${OBJECT_PORT}"
  -e DATA_UPLOAD_DIR=/tmp/madar-e2e/uploads
  -e MADAR_CHECKPOINT_SCRATCH_DIR=/tmp/madar-e2e/checkpoints
  -e PRIVATE_CHARTS_DIR=/tmp/madar-private-reports
  -e HOME=/tmp -e MPLCONFIGDIR=/tmp/matplotlib -e PYTHONPATH=/app -e PYTHONFAULTHANDLER=1
)

docker run -d --name "${FIXTURE_NAME}" --network host --user "$(id -u):$(id -g)" \
  -v "${ROOT_DIR}/web/backend:/app:ro" -v "${TEMP_DIR}:/run/madar-e2e:ro" \
  -v "${REPORT_DIR}:/tmp/madar-private-reports" -w /app \
  "${COMMON_ENV[@]}" -e MADAR_E2E_TENANT_ID=7001 -e MADAR_E2E_PROJECT_ID="${PROJECT_ID}" \
  -e MADAR_E2E_PROVIDER_TOKEN="${PROVIDER_TOKEN}" -e MADAR_E2E_CONTROL_TOKEN="${CONTROL_TOKEN}" \
  -e MADAR_E2E_PROVIDER_PORT="${PROVIDER_PORT}" -e MADAR_E2E_OBJECT_PORT="${OBJECT_PORT}" \
  -e MADAR_E2E_CONTROL_PORT="${CONTROL_PORT}" \
  madar-backend-test python tests/data_sources_browser_e2e_fixture.py >/dev/null

docker run -d --name "${BACKEND_NAME}" --network host --user "$(id -u):$(id -g)" \
  -v "${ROOT_DIR}/web/backend:/app:ro" -v "${TEMP_DIR}:/run/madar-e2e:ro" -w /app \
  "${COMMON_ENV[@]}" -e CSRF_SECRET="$(openssl rand -hex 32)" \
  -e SCHEMA_COMPATIBLE_MIN=141 -e SCHEMA_COMPATIBLE_MAX=143 -e SCHEMA_EXCLUDED_VERSIONS=142 \
  -e FRONTEND_URLS="http://127.0.0.1:${FRONTEND_PORT}" \
  -e FRONTEND_PRIMARY_URL="http://127.0.0.1:${FRONTEND_PORT}" -e PORT="${BACKEND_PORT}" \
  madar-backend-test python -c \
  'import os,uvicorn;from app import app;uvicorn.run(app,host="127.0.0.1",port=int(os.environ["PORT"]))' >/dev/null

for endpoint in "http://127.0.0.1:${CONTROL_PORT}/health" "http://127.0.0.1:${BACKEND_PORT}/health/recovery"; do
  ready=false
  for _ in $(seq 1 120); do
    if curl -fsS "${endpoint}" >/dev/null 2>&1; then
      ready=true
      break
    fi
    sleep 0.25
  done
  if [[ "${ready}" != true ]]; then
    printf 'service_readiness_failed endpoint=%s\n' "${endpoint}" >&2
    docker logs "${FIXTURE_NAME}" >&2 || true
    docker logs "${BACKEND_NAME}" >&2 || true
    exit 1
  fi
done
docker exec "${BACKEND_NAME}" python -c \
  'from services.provider_registry import public_provider_capabilities; providers=public_provider_capabilities(); assert any(item["key"] == "http_fixture" for item in providers), providers'

(
  cd "${ROOT_DIR}/web/frontend"
  VITE_DEV_PROXY_TARGET="http://127.0.0.1:${BACKEND_PORT}" \
  VITE_DEV_PROXY_REQUEST_ORIGIN="http://127.0.0.1:${FRONTEND_PORT}" \
  npm run dev -- --host 127.0.0.1 --port "${FRONTEND_PORT}" >"${TEMP_DIR}/vite.log" 2>&1
) &
VITE_PID=$!
for _ in $(seq 1 120); do
  curl -fsS "http://127.0.0.1:${FRONTEND_PORT}/" >/dev/null 2>&1 && break
  sleep 0.25
done
curl -fsS "http://127.0.0.1:${FRONTEND_PORT}/" >/dev/null

if [[ "${MADAR_E2E_WEBHOOK_ONLY:-NO}" != "YES" && "${MADAR_E2E_REPORTING_ONLY:-NO}" != "YES" ]]; then
(
  cd "${ROOT_DIR}/web/frontend"
  MADAR_E2E_CONFIRM_ISOLATED=YES \
  MADAR_E2E_BASE_URL="http://127.0.0.1:${FRONTEND_PORT}" \
  MADAR_E2E_DATABASE_ID="${DATABASE_ID}" MADAR_E2E_RUN_ID="${RUN_ID}-schema141" \
  MADAR_E2E_MIGRATIONS_APPLIED_FROM_CLEAN=YES MADAR_E2E_EXTERNAL_DELIVERY_DISABLED=YES \
  MADAR_E2E_ACCESS_TOKEN="${ACCESS_JWT}" \
  MADAR_E2E_CONTROL_URL="http://127.0.0.1:${CONTROL_PORT}" \
  MADAR_E2E_CONTROL_TOKEN="${CONTROL_TOKEN}" MADAR_E2E_PROJECT_ID="${PROJECT_ID}" \
  MADAR_E2E_CROSS_TENANT_PROJECT_ID="${CROSS_PROJECT_ID}" \
  MADAR_E2E_PROVIDER_TOKEN="${PROVIDER_TOKEN}" MADAR_E2E_SCREENSHOT_DIR="${ARTIFACT_DIR}" \
  MADAR_E2E_SPEC=data-sources-older-schema-live.spec.mjs \
  npx playwright test --config=playwright.data-sources-live.config.mjs
)
fi

docker rm -f "${BACKEND_NAME}" >/dev/null
apply_range 143 161
docker restart "${REST_NAME}" >/dev/null
for _ in $(seq 1 60); do
  docker run --rm --network "${NETWORK}" madar-backend-test \
    python -c "import httpx;raise SystemExit(0 if httpx.get('http://rest:3000/',timeout=1).status_code<500 else 1)" \
    >/dev/null 2>&1 && break
  sleep 0.25
done

docker run -d --name "${BACKEND_NAME}" --network host --user "$(id -u):$(id -g)" \
  -v "${ROOT_DIR}/web/backend:/app:ro" -v "${TEMP_DIR}:/run/madar-e2e:ro" -w /app \
  "${COMMON_ENV[@]}" -e CSRF_SECRET="$(openssl rand -hex 32)" \
  -e SCHEMA_COMPATIBLE_MIN=161 -e SCHEMA_COMPATIBLE_MAX=161 -e SCHEMA_EXCLUDED_VERSIONS= \
  -e FRONTEND_URLS="http://127.0.0.1:${FRONTEND_PORT}" \
  -e FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}" \
  -e FRONTEND_PRIMARY_URL="http://127.0.0.1:${FRONTEND_PORT}" -e PORT="${BACKEND_PORT}" \
  madar-backend-test python -c \
  'import os,uvicorn;from app import app;uvicorn.run(app,host="127.0.0.1",port=int(os.environ["PORT"]))' >/dev/null
ready=false
for _ in $(seq 1 120); do
  if curl -fsS "http://127.0.0.1:${BACKEND_PORT}/health/recovery" >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 0.25
done
if [[ "${ready}" != true ]]; then
  printf 'schema161_backend_readiness_failed\n' >&2
  docker logs "${BACKEND_NAME}" >&2 || true
  exit 1
fi

if [[ "${MADAR_E2E_GOOGLE_ONLY:-NO}" != "YES" && "${MADAR_E2E_WEBHOOK_ONLY:-NO}" != "YES" && "${MADAR_E2E_REPORTING_ONLY:-NO}" != "YES" ]]; then
(
  cd "${ROOT_DIR}/web/frontend"
  MADAR_E2E_CONFIRM_ISOLATED=YES \
  MADAR_E2E_BASE_URL="http://127.0.0.1:${FRONTEND_PORT}" \
  MADAR_E2E_DATABASE_ID="${DATABASE_ID}" MADAR_E2E_RUN_ID="${RUN_ID}" \
  MADAR_E2E_MIGRATIONS_APPLIED_FROM_CLEAN=YES MADAR_E2E_EXTERNAL_DELIVERY_DISABLED=YES \
  MADAR_E2E_ACCESS_TOKEN="${ACCESS_JWT}" \
  MADAR_E2E_CONTROL_URL="http://127.0.0.1:${CONTROL_PORT}" \
  MADAR_E2E_CONTROL_TOKEN="${CONTROL_TOKEN}" MADAR_E2E_PROJECT_ID="${PROJECT_ID}" \
  MADAR_E2E_CROSS_TENANT_PROJECT_ID="${CROSS_PROJECT_ID}" \
  MADAR_E2E_PROVIDER_TOKEN="${PROVIDER_TOKEN}" MADAR_E2E_SCREENSHOT_DIR="${ARTIFACT_DIR}" \
  npx playwright test --config=playwright.data-sources-live.config.mjs
)
fi

if [[ "${MADAR_E2E_WEBHOOK_ONLY:-NO}" != "YES" && "${MADAR_E2E_REPORTING_ONLY:-NO}" != "YES" ]]; then
(
  cd "${ROOT_DIR}/web/frontend"
  MADAR_E2E_CONFIRM_ISOLATED=YES \
  MADAR_E2E_BASE_URL="http://127.0.0.1:${FRONTEND_PORT}" \
  MADAR_E2E_DATABASE_ID="${DATABASE_ID}" MADAR_E2E_RUN_ID="${RUN_ID}-google-sheets" \
  MADAR_E2E_MIGRATIONS_APPLIED_FROM_CLEAN=YES MADAR_E2E_EXTERNAL_DELIVERY_DISABLED=YES \
  MADAR_E2E_ACCESS_TOKEN="${ACCESS_JWT}" \
  MADAR_E2E_CONTROL_URL="http://127.0.0.1:${CONTROL_PORT}" \
  MADAR_E2E_CONTROL_TOKEN="${CONTROL_TOKEN}" MADAR_E2E_PROJECT_ID="${PROJECT_ID}" \
  MADAR_E2E_CROSS_TENANT_PROJECT_ID="${CROSS_PROJECT_ID}" \
  MADAR_E2E_PROVIDER_TOKEN="${PROVIDER_TOKEN}" MADAR_E2E_SCREENSHOT_DIR="${ARTIFACT_DIR}" \
  MADAR_E2E_SPEC=data-sources-google-sheets-live.spec.mjs \
  npx playwright test --config=playwright.data-sources-live.config.mjs
)
fi

# C4 runs only after the unchanged schema161 browser/Google rehearsals. Migration162
# remains confined to this tmpfs database and the backend remains loopback-only.
docker rm -f "${BACKEND_NAME}" >/dev/null
apply_range 162 162
docker restart "${REST_NAME}" >/dev/null
for _ in $(seq 1 60); do
  docker run --rm --network "${NETWORK}" madar-backend-test \
    python -c "import httpx;raise SystemExit(0 if httpx.get('http://rest:3000/',timeout=1).status_code<500 else 1)" \
    >/dev/null 2>&1 && break
  sleep 0.25
done

docker run -d --name "${BACKEND_NAME}" --network host --user "$(id -u):$(id -g)" \
  -v "${ROOT_DIR}/web/backend:/app:ro" -v "${TEMP_DIR}:/run/madar-e2e:ro" -w /app \
  "${COMMON_ENV[@]}" -e CSRF_SECRET="$(openssl rand -hex 32)" \
  -e SCHEMA_COMPATIBLE_MIN=162 -e SCHEMA_COMPATIBLE_MAX=162 -e SCHEMA_EXCLUDED_VERSIONS= \
  -e FRONTEND_URLS="http://127.0.0.1:${FRONTEND_PORT}" \
  -e FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}" \
  -e FRONTEND_PRIMARY_URL="http://127.0.0.1:${FRONTEND_PORT}" -e PORT="${BACKEND_PORT}" \
  madar-backend-test python -c \
  'import os,uvicorn;from app import app;uvicorn.run(app,host="127.0.0.1",port=int(os.environ["PORT"]))' >/dev/null
ready=false
for _ in $(seq 1 120); do
  if curl -fsS "http://127.0.0.1:${BACKEND_PORT}/health/recovery" >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 0.25
done
if [[ "${ready}" != true ]]; then
  printf 'schema162_backend_readiness_failed\n' >&2
  docker logs "${BACKEND_NAME}" >&2 || true
  exit 1
fi

if [[ "${MADAR_E2E_REPORTING_ONLY:-NO}" != "YES" ]]; then
(
  cd "${ROOT_DIR}/web/frontend"
  MADAR_E2E_CONFIRM_ISOLATED=YES \
  MADAR_E2E_BASE_URL="http://127.0.0.1:${FRONTEND_PORT}" \
  MADAR_E2E_DATABASE_ID="${DATABASE_ID}" MADAR_E2E_RUN_ID="${RUN_ID}-webhook" \
  MADAR_E2E_MIGRATIONS_APPLIED_FROM_CLEAN=YES MADAR_E2E_EXTERNAL_DELIVERY_DISABLED=YES \
  MADAR_E2E_ACCESS_TOKEN="${ACCESS_JWT}" \
  MADAR_E2E_CONTROL_URL="http://127.0.0.1:${CONTROL_PORT}" \
  MADAR_E2E_CONTROL_TOKEN="${CONTROL_TOKEN}" MADAR_E2E_PROJECT_ID="${PROJECT_ID}" \
  MADAR_E2E_CROSS_TENANT_PROJECT_ID="${CROSS_PROJECT_ID}" \
  MADAR_E2E_PROVIDER_TOKEN="${PROVIDER_TOKEN}" MADAR_E2E_SCREENSHOT_DIR="${ARTIFACT_DIR}" \
  MADAR_E2E_SPEC=data-sources-webhook-live.spec.mjs \
  npx playwright test --config=playwright.data-sources-live.config.mjs
)
fi

# C5 runs only after C4 completes. Schema159 and its backend remain confined to
# this tmpfs database and loopback-only browser stack.
docker rm -f "${BACKEND_NAME}" >/dev/null
apply_range 163 163
docker restart "${REST_NAME}" >/dev/null
for _ in $(seq 1 60); do
  docker run --rm --network "${NETWORK}" madar-backend-test \
    python -c "import httpx;raise SystemExit(0 if httpx.get('http://rest:3000/',timeout=1).status_code<500 else 1)" \
    >/dev/null 2>&1 && break
  sleep 0.25
done

docker run -d --name "${BACKEND_NAME}" --network host --user "$(id -u):$(id -g)" \
  -v "${ROOT_DIR}/web/backend:/app:ro" -v "${TEMP_DIR}:/run/madar-e2e:ro" -w /app \
  "${COMMON_ENV[@]}" -e CSRF_SECRET="$(openssl rand -hex 32)" \
  -e SCHEMA_COMPATIBLE_MIN=163 -e SCHEMA_COMPATIBLE_MAX=163 -e SCHEMA_EXCLUDED_VERSIONS= \
  -e FRONTEND_URLS="http://127.0.0.1:${FRONTEND_PORT}" \
  -e FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}" \
  -e FRONTEND_PRIMARY_URL="http://127.0.0.1:${FRONTEND_PORT}" -e PORT="${BACKEND_PORT}" \
  madar-backend-test python -c \
  'import os,uvicorn;from app import app;uvicorn.run(app,host="127.0.0.1",port=int(os.environ["PORT"]))' >/dev/null
ready=false
for _ in $(seq 1 120); do
  if curl -fsS "http://127.0.0.1:${BACKEND_PORT}/health/recovery" >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 0.25
done
if [[ "${ready}" != true ]]; then
  printf 'schema163_backend_readiness_failed\n' >&2
  docker logs "${BACKEND_NAME}" >&2 || true
  exit 1
fi

if [[ "${MADAR_E2E_REPORTING_ONLY:-NO}" != "YES" ]]; then
(
  cd "${ROOT_DIR}/web/frontend"
  MADAR_E2E_CONFIRM_ISOLATED=YES \
  MADAR_E2E_BASE_URL="http://127.0.0.1:${FRONTEND_PORT}" \
  MADAR_E2E_DATABASE_ID="${DATABASE_ID}" MADAR_E2E_RUN_ID="${RUN_ID}-business-intelligence" \
  MADAR_E2E_MIGRATIONS_APPLIED_FROM_CLEAN=YES MADAR_E2E_EXTERNAL_DELIVERY_DISABLED=YES \
  MADAR_E2E_ACCESS_TOKEN="${ACCESS_JWT}" \
  MADAR_E2E_CONTROL_URL="http://127.0.0.1:${CONTROL_PORT}" \
  MADAR_E2E_CONTROL_TOKEN="${CONTROL_TOKEN}" MADAR_E2E_PROJECT_ID="${PROJECT_ID}" \
  MADAR_E2E_CROSS_TENANT_PROJECT_ID="${CROSS_PROJECT_ID}" \
  MADAR_E2E_PROVIDER_TOKEN="${PROVIDER_TOKEN}" MADAR_E2E_SCREENSHOT_DIR="${ARTIFACT_DIR}" \
  MADAR_E2E_SPEC=business-intelligence-live.spec.mjs \
  npx playwright test --config=playwright.data-sources-live.config.mjs
)
fi

# C5 Step 3 advances only the same disposable tmpfs database to candidate 164.
# The one-shot scheduler and worker are invoked only through the token-protected
# loopback fixture, and private CSV artifacts live in the disposable shared path.
docker rm -f "${BACKEND_NAME}" >/dev/null
apply_range 164 164
docker restart "${REST_NAME}" >/dev/null
for _ in $(seq 1 60); do
  docker run --rm --network "${NETWORK}" madar-backend-test \
    python -c "import httpx;raise SystemExit(0 if httpx.get('http://rest:3000/',timeout=1).status_code<500 else 1)" \
    >/dev/null 2>&1 && break
  sleep 0.25
done

docker run -d --name "${BACKEND_NAME}" --network host --user "$(id -u):$(id -g)" \
  -v "${ROOT_DIR}/web/backend:/app:ro" -v "${TEMP_DIR}:/run/madar-e2e:ro" \
  -v "${REPORT_DIR}:/tmp/madar-private-reports" -w /app \
  "${COMMON_ENV[@]}" -e CSRF_SECRET="$(openssl rand -hex 32)" \
  -e SCHEMA_COMPATIBLE_MIN=164 -e SCHEMA_COMPATIBLE_MAX=164 -e SCHEMA_EXCLUDED_VERSIONS= \
  -e FRONTEND_URLS="http://127.0.0.1:${FRONTEND_PORT}" \
  -e FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}" \
  -e FRONTEND_PRIMARY_URL="http://127.0.0.1:${FRONTEND_PORT}" -e PORT="${BACKEND_PORT}" \
  madar-backend-test python -c \
  'import os,uvicorn;from app import app;uvicorn.run(app,host="127.0.0.1",port=int(os.environ["PORT"]))' >/dev/null
ready=false
for _ in $(seq 1 120); do
  if curl -fsS "http://127.0.0.1:${BACKEND_PORT}/health/recovery" >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 0.25
done
if [[ "${ready}" != true ]]; then
  printf 'schema164_backend_readiness_failed\n' >&2
  docker logs "${BACKEND_NAME}" >&2 || true
  exit 1
fi

(
  cd "${ROOT_DIR}/web/frontend"
  MADAR_E2E_CONFIRM_ISOLATED=YES \
  MADAR_E2E_BASE_URL="http://127.0.0.1:${FRONTEND_PORT}" \
  MADAR_E2E_DATABASE_ID="${DATABASE_ID}" MADAR_E2E_RUN_ID="${RUN_ID}-business-reporting" \
  MADAR_E2E_MIGRATIONS_APPLIED_FROM_CLEAN=YES MADAR_E2E_EXTERNAL_DELIVERY_DISABLED=YES \
  MADAR_E2E_ACCESS_TOKEN="${ACCESS_JWT}" \
  MADAR_E2E_CONTROL_URL="http://127.0.0.1:${CONTROL_PORT}" \
  MADAR_E2E_CONTROL_TOKEN="${CONTROL_TOKEN}" MADAR_E2E_PROJECT_ID="${PROJECT_ID}" \
  MADAR_E2E_CROSS_TENANT_PROJECT_ID="${CROSS_PROJECT_ID}" \
  MADAR_E2E_PROVIDER_TOKEN="${PROVIDER_TOKEN}" MADAR_E2E_SCREENSHOT_DIR="${ARTIFACT_DIR}" \
  MADAR_E2E_SPEC=business-reporting-live.spec.mjs \
  npx playwright test --config=playwright.data-sources-live.config.mjs
)

printf 'data_sources_browser_e2e_passed artifacts=%s\n' "${ARTIFACT_DIR}"
