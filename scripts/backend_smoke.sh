#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-}"
MISSING_SITE="definitely-missing-test-site-999"

case "$MODE" in
  prod-local)
    BASE_URL="http://127.0.0.1:8001"
    CORS_ORIGIN="https://madarportal.com"
    ;;
  dev-local)
    BASE_URL="http://127.0.0.1:8002"
    CORS_ORIGIN="http://172.0.0.1:3001"
    ;;
  prod-public)
    BASE_URL="https://api.madarportal.com"
    CORS_ORIGIN="https://madarportal.com"
    ;;
  *)
    cat >&2 <<USAGE
Usage: $0 <prod-local|dev-local|prod-public>

Modes:
  prod-local   Smoke test http://127.0.0.1:8001 with Origin https://madarportal.com
  dev-local    Smoke test http://127.0.0.1:8002 with Origin http://172.0.0.1:3001
  prod-public  Smoke test https://api.madarportal.com with Origin https://madarportal.com
USAGE
    exit 2
    ;;
esac

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

pass() {
  printf 'PASS %-34s %s\n' "$1" "$2"
}

fail() {
  printf 'FAIL %-34s %s\n' "$1" "$2" >&2
  exit 1
}

request_get() {
  local path="$1"
  local expected_status="$2"
  local label="$3"
  local body_file="$TMP_DIR/body.txt"
  local status

  status="$(curl -sS --max-time 15 -o "$body_file" -w '%{http_code}' "$BASE_URL$path")" || {
    fail "$label" "curl failed for GET $BASE_URL$path"
  }

  if [[ "$status" != "$expected_status" ]]; then
    local preview
    preview="$(head -c 240 "$body_file" | tr '\n' ' ')"
    fail "$label" "expected HTTP $expected_status, got $status from $path; body: $preview"
  fi

  pass "$label" "GET $path returned $status"
}

assert_body_contains() {
  local path="$1"
  local expected_status="$2"
  local needle="$3"
  local label="$4"
  local body_file="$TMP_DIR/body.txt"
  local status

  status="$(curl -sS --max-time 15 -o "$body_file" -w '%{http_code}' "$BASE_URL$path")" || {
    fail "$label" "curl failed for GET $BASE_URL$path"
  }

  if [[ "$status" != "$expected_status" ]]; then
    local preview
    preview="$(head -c 240 "$body_file" | tr '\n' ' ')"
    fail "$label" "expected HTTP $expected_status, got $status from $path; body: $preview"
  fi

  if ! grep -Fq "$needle" "$body_file"; then
    local preview
    preview="$(head -c 240 "$body_file" | tr '\n' ' ')"
    fail "$label" "response from $path did not contain '$needle'; body: $preview"
  fi

  pass "$label" "GET $path returned $status and contained '$needle'"
}

check_cors_preflight() {
  local path="/builder/projects"
  local headers_file="$TMP_DIR/cors_headers.txt"
  local clean_headers_file="$TMP_DIR/cors_headers_clean.txt"
  local status
  local allow_origin

  status="$(curl -sS --max-time 15 -o /dev/null -D "$headers_file" -w '%{http_code}' -X OPTIONS "$BASE_URL$path" \
    -H "Origin: $CORS_ORIGIN" \
    -H 'Access-Control-Request-Method: PUT' \
    -H 'Access-Control-Request-Headers: Content-Type,X-CSRF-Token')" || {
      fail "cors preflight" "curl failed for OPTIONS $BASE_URL$path"
    }

  tr -d '\r' < "$headers_file" > "$clean_headers_file"

  if [[ "$status" != "200" ]]; then
    fail "cors preflight" "expected HTTP 200, got $status for Origin $CORS_ORIGIN"
  fi

  allow_origin="$(
    sed -n 's/^[Aa][Cc][Cc][Ee][Ss][Ss]-[Cc][Oo][Nn][Tt][Rr][Oo][Ll]-[Aa][Ll][Ll][Oo][Ww]-[Oo][Rr][Ii][Gg][Ii][Nn]:[[:space:]]*//p' "$clean_headers_file" \
      | head -n 1 \
      | sed 's/[[:space:]]*$//'
  )"

  if [[ "$allow_origin" != "$CORS_ORIGIN" ]]; then
    fail "cors preflight" "expected access-control-allow-origin '$CORS_ORIGIN', got '${allow_origin:-missing}'"
  fi

  pass "cors preflight" "OPTIONS $path allowed Origin $CORS_ORIGIN"
}

printf 'Backend smoke test: mode=%s base_url=%s origin=%s\n' "$MODE" "$BASE_URL" "$CORS_ORIGIN"

request_get "/" "200" "root status"
request_get "/health/live" "200" "health live"
request_get "/health/ready" "200" "health ready"
assert_body_contains "/auth/user_status" "200" '"logged_in":false' "auth user_status"
request_get "/builder/projects" "401" "builder unauth"
request_get "/public/sites/$MISSING_SITE" "404" "missing public site"
check_cors_preflight

printf 'Backend smoke test completed successfully for %s\n' "$MODE"
