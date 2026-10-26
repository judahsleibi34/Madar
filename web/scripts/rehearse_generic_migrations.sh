#!/usr/bin/env bash
set -euo pipefail
# Pin one local daemon for creation/inspection/cleanup; ignore ambient contexts.
docker() { /usr/bin/docker --host unix:///var/run/docker.sock "$@"; }
# REHEARSE only. No published ports, persistent DB volume or production target.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WEB_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
modules=(test_generic_migration_source test_generic_migration_plan test_migration_candidate_rehearsal test_generic_migrations_database test_measured_migration_policy test_schema150_quiescence_scope_database)
if [[ "$#" -gt 0 ]]; then
  if [[ "$#" -ne 1 || "$1" != --measured-only ]]; then echo 'ERROR: generic_rehearsal_arguments_invalid' >&2; exit 2; fi
  modules=(test_measured_migration_policy)
fi
POSTGRES_IMAGE='postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73'
BACKEND_TEST_IMAGE="${BACKEND_TEST_IMAGE:-madar-backend-test}"
CONTAINER_NAME="madar-generic-synthetic-$RANDOM-$$"
RUN_ID="generic-$(date -u +%Y%m%dT%H%M%SZ)-$RANDOM-$$"
owned=false
backup_dir="$(mktemp -d)"
cleanup() {
  local cid record label
  for record in "$backup_dir/candidate.cid" "$backup_dir/acceptance.cid"; do
    if [[ -f "$record" ]]; then
      cid="$(cat "$record")"
      if docker inspect "$cid" >/dev/null 2>&1; then
        label="$(docker inspect --format '{{index .Config.Labels "com.madar.rehearsal.run"}}' "$cid")"
        if [[ "$label" != "$RUN_ID" ]]; then echo 'ERROR: generic_cleanup_owner_changed' >&2; return 1; fi
        docker rm -f -v "$cid" >/dev/null
      fi
    fi
  done
  if "$owned"; then
    label="$(docker inspect --format '{{index .Config.Labels "com.madar.rehearsal.run"}}' "$container_id")"
    if [[ "$label" != "$RUN_ID" ]]; then echo 'ERROR: generic_cleanup_owner_changed' >&2; return 1; fi
    docker rm -f -v "$container_id" >/dev/null
  fi
  rm -f -- "$backup_dir/database.dump" "$backup_dir/manifest.json" "$backup_dir/candidate.cid" "$backup_dir/acceptance.cid"
  rmdir -- "$backup_dir"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

container_id="$(docker create --name "$CONTAINER_NAME" --network none --memory=384m --cpus=0.5 --pids-limit=96 \
  --label madar.rehearsal=generic-migration-future-fixtures \
  --label "com.madar.rehearsal.run=$RUN_ID" \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=384m \
  -e POSTGRES_HOST_AUTH_METHOD=trust "$POSTGRES_IMAGE" postgres -c max_prepared_transactions=10)"
owned=true
docker start "$CONTAINER_NAME" >/dev/null
for attempt in $(seq 1 60); do
  if docker exec "$CONTAINER_NAME" pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1; then break; fi
  sleep 1
done
docker exec -i "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
comment on database postgres is 'madar-generic-migration-synthetic-rehearsal';
create table public.application_schema_state(contract_key text primary key,schema_version integer not null);
insert into public.application_schema_state values('core',150);
create table public.synthetic_preserved(payload text);
insert into public.synthetic_preserved values('retained');
create table public.future_one(id pg_catalog.int8 primary key);
insert into public.future_one select generate_series(1,50);
SQL
docker exec "$CONTAINER_NAME" pg_dump -U postgres -Fc postgres > "$backup_dir/database.dump"
cluster="$(docker exec "$CONTAINER_NAME" psql -X -U postgres -Atc 'select system_identifier from pg_control_system()')"
fixture_root="$(docker exec "$CONTAINER_NAME" psql -X -U postgres -Atc "select encode(sha256(convert_to(string_agg(id::text,',' order by id),'UTF8')),'hex') from public.future_one")"
python3 - "$backup_dir" "$cluster" "$fixture_root" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]); body=(root/'database.dump').read_bytes()
(root/'manifest.json').write_text(json.dumps({'sha256':hashlib.sha256(body).hexdigest(),'system_identifier':sys.argv[2],'class_b_fixture_sha256':sys.argv[3]}))
PY
# Component restore into another DB in this cluster, not an independent receiver.
docker exec "$CONTAINER_NAME" createdb -U postgres restored_fixture
docker exec "$CONTAINER_NAME" psql -X -U postgres -v ON_ERROR_STOP=1 -q -c \
  "comment on database restored_fixture is 'madar-generic-migration-synthetic-rehearsal'"
docker exec -i "$CONTAINER_NAME" pg_restore -U postgres --exit-on-error -d restored_fixture < "$backup_dir/database.dump"
restored="$(docker exec "$CONTAINER_NAME" psql -X -U postgres -d restored_fixture -Atc 'select payload from public.synthetic_preserved')"
test "$restored" = retained
test "$(docker exec "$CONTAINER_NAME" psql -X -U postgres -d restored_fixture -Atc "select encode(sha256(convert_to(string_agg(id::text,',' order by id),'UTF8')),'hex') from public.future_one")" = "$fixture_root"
chmod 755 "$backup_dir"
chmod 644 "$backup_dir/database.dump" "$backup_dir/manifest.json"
# A retained local test image may mount a verified parser wheel for diagnosis;
# CI builds the test target with the hash-locked parser. This is not an accepted
# runtime image and no result is represented as production artifact acceptance.
parser_args=()
if [[ -n "${MIGRATION_REHEARSAL_PARSER_DIR:-}" ]]; then
  parser_args=(--volume "$MIGRATION_REHEARSAL_PARSER_DIR:/parser:ro")
fi
if [[ -n "${CI_SOURCE_SHA:-}" && -n "${CI_HISTORY_BASE_SHA:-}" ]]; then
  # Test actual newly discovered routine SQL, not only synthetic framework cases.
  # Non-routine SQL produces an explicit BLOCKED coverage report, never a PASS.
  docker run --rm --cidfile "$backup_dir/candidate.cid" --label "com.madar.rehearsal.run=$RUN_ID" --network "container:$CONTAINER_NAME" --memory=384m --cpus=0.75 --pids-limit=96 --read-only \
    --tmpfs /tmp:rw,exec,nosuid,nodev,size=128m,mode=1777 \
    --env CI_SOURCE_SHA --env CI_HISTORY_BASE_SHA \
    --env PYTHONPATH=/parser:/repository/web \
    --env GENERIC_MIGRATION_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=5432 dbname=postgres user=postgres' \
    --env GENERIC_MIGRATION_SYNTHETIC_BACKUP=/verified-backup \
    --volume "$backup_dir:/verified-backup:ro" --volume "$WEB_ROOT/..:/repository:ro" \
    "${parser_args[@]}" --entrypoint python "$BACKEND_TEST_IMAGE" \
    /repository/web/scripts/rehearse_migration_candidate.py > "$WEB_ROOT/../migration-native.json"
fi
docker run --rm --cidfile "$backup_dir/acceptance.cid" --label "com.madar.rehearsal.run=$RUN_ID" --network "container:$CONTAINER_NAME" --memory=384m --cpus=0.75 --pids-limit=96 --read-only \
  --tmpfs /tmp:rw,exec,nosuid,nodev,size=128m,mode=1777 \
  --env PYTHONPATH=/parser:/test-repository:/test-repository/backend/tests \
  --env MADAR_TEST_REPOSITORY_ROOT=/test-repository \
  --env GENERIC_MIGRATION_SYNTHETIC_DATABASE_DSN='host=127.0.0.1 port=5432 dbname=postgres user=postgres' \
  --env GENERIC_MIGRATION_SYNTHETIC_BACKUP=/verified-backup \
  --volume "$backup_dir:/verified-backup:ro" --volume "$WEB_ROOT:/test-repository:ro" \
  "${parser_args[@]}" --entrypoint python "$BACKEND_TEST_IMAGE" \
  -m unittest "${modules[@]}" -v
