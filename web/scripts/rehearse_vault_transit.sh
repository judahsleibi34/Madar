#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VAULT_IMAGE="hashicorp/vault:2.0.4@sha256:5be49781ecf78bfe775c5309c6a4d9f4e9e040b6c885c99eb2b12fb69855e1a2"
VAULT_NAME="madar-vault-c2-$RANDOM-$$"
TEMP_DIR="$(mktemp -d)"
ROOT_TOKEN="$(openssl rand -hex 24)"

cleanup() {
  docker rm -f "${VAULT_NAME}" >/dev/null 2>&1 || true
  find "${TEMP_DIR}" -type f -exec chmod u+w {} + 2>/dev/null || true
  rm -rf "${TEMP_DIR}"
}
trap cleanup EXIT

docker run -d --rm --name "${VAULT_NAME}" --cap-add IPC_LOCK \
  -p 127.0.0.1::8200 \
  -e VAULT_DEV_ROOT_TOKEN_ID="${ROOT_TOKEN}" \
  -e VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200 \
  -v "${ROOT_DIR}/web/deployment/vault/data-sources-transit-policy.hcl:/vault/data-sources-policy.hcl:ro" \
  "${VAULT_IMAGE}" server -dev >/dev/null

for _ in $(seq 1 60); do
  if docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN="${ROOT_TOKEN}" \
      "${VAULT_NAME}" vault status >/dev/null 2>&1; then break; fi
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
  "${VAULT_NAME}" vault token create -policy=madar-data-sources -ttl=5m \
  -explicit-max-ttl=10m -renewable=true -field=token)"
install -m 0600 /dev/null "${TEMP_DIR}/token"
printf '%s' "${APP_TOKEN}" > "${TEMP_DIR}/token"
chmod 0400 "${TEMP_DIR}/token"
install -m 0600 /dev/null "${TEMP_DIR}/admin-token"
printf '%s' "${ROOT_TOKEN}" > "${TEMP_DIR}/admin-token"
chmod 0400 "${TEMP_DIR}/admin-token"

VAULT_PORT="$(docker port "${VAULT_NAME}" 8200/tcp | sed 's/.*://')"
docker run --rm --network host --user "$(id -u):$(id -g)" \
  -v "${ROOT_DIR}/web/backend:/app" -v "${TEMP_DIR}:/run/madar-test-vault:ro" \
  -w /app \
  -e HOME=/tmp -e MPLCONFIGDIR=/tmp/matplotlib -e PYTHONPATH=/app -e APP_ENV=test \
  -e SUPABASE_URL=http://127.0.0.1:54321 \
  -e SUPABASE_ANON_KEY=synthetic-anon-key-not-real \
  -e SUPABASE_SERVICE_KEY=synthetic-service-key-not-real \
  -e DATA_SOURCE_CREDENTIAL_ENVIRONMENT=test \
  -e DATA_SOURCE_VAULT_ADDR="http://127.0.0.1:${VAULT_PORT}" \
  -e DATA_SOURCE_VAULT_TOKEN_FILE=/run/madar-test-vault/token \
  -e DATA_SOURCE_VAULT_TRANSIT_KEY=madar-data-sources \
  -e MADAR_TEST_VAULT_ADMIN_TOKEN_FILE=/run/madar-test-vault/admin-token \
  madar-backend-test-c2:latest python3 tests/rehearse_vault_transit_integration.py
