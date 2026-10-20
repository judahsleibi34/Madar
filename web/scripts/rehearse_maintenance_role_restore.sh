#!/usr/bin/env bash
set -euo pipefail
# Pin one local daemon for creation/inspection/cleanup; ignore ambient contexts.
docker() { /usr/bin/docker --host unix:///var/run/docker.sock "$@"; }
# Owned synthetic role/ACL restoration only; not production backup acceptance.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WEB_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
IMAGE='postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73'
BACKEND_TEST_IMAGE="${BACKEND_TEST_IMAGE:-madar-backend-test}"
fixture="$(mktemp -d)"
source_name="madar-role-source-$RANDOM-$$"
target_name="madar-role-restore-$RANDOM-$$"
created=()
cleanup() {
  for name in "${created[@]}"; do
    label="$(docker inspect --format '{{index .Config.Labels "madar.rehearsal"}}' "$name")"
    if [[ "$label" == original-role-restore ]]; then docker rm -f "$name" >/dev/null; fi
  done
  # Only this mktemp directory is owned; no backup/controller path is touched.
  for leaf in original.sql current.sql restore.sql database.dump before.json after.json system-id; do rm -f -- "$fixture/$leaf"; done
  rmdir -- "$fixture"
}
trap cleanup EXIT
for name in "$source_name" "$target_name"; do
  docker create --name "$name" --network none --memory=256m --cpus=0.5 --pids-limit=96 \
    --label madar.rehearsal=original-role-restore --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=256m \
    -e POSTGRES_HOST_AUTH_METHOD=trust "$IMAGE" >/dev/null
  created+=("$name"); docker start "$name" >/dev/null
  for attempt in $(seq 1 60); do
    if docker exec "$name" pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1; then break; fi
    sleep 1
  done
done
docker exec -i "$source_name" psql -X -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
create role synthetic_owner nologin nosuperuser nobypassrls;
create role synthetic_group nologin;
do $$ begin execute format('create role synthetic_provider login nosuperuser nobypassrls connection limit 3 password %L',gen_random_uuid()::text); end $$;
grant synthetic_group to synthetic_provider with inherit false;
alter role synthetic_provider set statement_timeout='9s';
create table public.synthetic_owned(id integer primary key,payload text);
alter table public.synthetic_owned owner to synthetic_owner;
insert into public.synthetic_owned values(1,'retained');
grant select on public.synthetic_owned to synthetic_provider;
create table public.application_schema_state(contract_key text primary key,schema_version integer);
insert into public.application_schema_state values('core',146);
SQL
role_query="select json_build_object('roles',(select json_agg(to_jsonb(r)-'oid' order by rolname) from pg_authid r where rolname like 'synthetic_%'),'memberships',(select json_agg(json_build_object('role',roleid::regrole::text,'member',member::regrole::text,'grantor',grantor::regrole::text,'admin',admin_option,'inherit',inherit_option,'set',set_option) order by roleid::regrole::text,member::regrole::text) from pg_auth_members where member::regrole::text like 'synthetic_%'),'settings',(select json_agg(json_build_object('role',setrole::regrole::text,'settings',setconfig) order by setrole::regrole::text) from pg_db_role_setting where setrole::regrole::text like 'synthetic_%'));"
docker exec "$source_name" psql -X -U postgres -Atc "$role_query" > "$fixture/before.json"
docker exec "$source_name" pg_dumpall -U postgres --roles-only > "$fixture/original.sql"
docker exec "$source_name" psql -X -U postgres -Atc 'select system_identifier from pg_control_system()' > "$fixture/system-id"
docker exec "$source_name" psql -X -U postgres -v ON_ERROR_STOP=1 -q -c 'alter role synthetic_provider nologin'
docker exec "$source_name" pg_dumpall -U postgres --roles-only > "$fixture/current.sql"
docker exec "$source_name" pg_dump -U postgres -Fc postgres > "$fixture/database.dump"
# psql's fresh administrator already exists. Only that exact CREATE is omitted;
# all captured attributes/settings/memberships/password hashes are restored.
python3 - "$fixture" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1]); body=(root/'original.sql').read_bytes()
assert body.count(b'CREATE ROLE postgres;')==1
assert b'ALTER ROLE synthetic_provider WITH' in body
(root/'restore.sql').write_bytes(body.replace(b'CREATE ROLE postgres;\n',b'',1))
PY
docker exec -i "$target_name" psql -X -U postgres -v ON_ERROR_STOP=1 -q < "$fixture/restore.sql"
docker exec -i "$target_name" pg_restore -U postgres --exit-on-error -d postgres < "$fixture/database.dump"
docker exec "$target_name" psql -X -U postgres -Atc "$role_query" > "$fixture/after.json"
python3 - "$fixture" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1])
assert json.loads((root/'before.json').read_bytes())==json.loads((root/'after.json').read_bytes())
print('PASS native original LOGIN/attributes/password hash/membership/settings restoration')
PY
result="$(docker exec "$target_name" psql -X -U postgres -Atc "select tableowner='synthetic_owner' from pg_tables where schemaname='public' and tablename='synthetic_owned';select has_table_privilege('synthetic_provider','public.synthetic_owned','SELECT') and not has_table_privilege('synthetic_provider','public.synthetic_owned','UPDATE');set role synthetic_provider;select payload from public.synthetic_owned;")"
test "$result" = $'t\nt\nSET\nretained'
if denial="$(docker exec "$target_name" psql -X -U postgres -v ON_ERROR_STOP=1 -v VERBOSITY=sqlstate -q -c "set role synthetic_provider;update public.synthetic_owned set payload='unauthorized'" 2>&1)"; then
  echo 'FAIL unexpected runtime UPDATE permission' >&2; exit 1
else
  [[ "$denial" == *42501* ]] || { echo 'FAIL expected permission-denied SQLSTATE' >&2; exit 1; }
fi

# Inspect only immutable synthetic bytes inside a networkless bounded container.
# The capsule is an input, never an approval, backup receipt or write grant.
docker run --rm --network none --memory=256m --cpus=0.5 --pids-limit=64 --read-only --user 0:0 \
 --env PYTHONPATH=/test-repository --volume "$WEB_ROOT:/test-repository:ro" --volume "$fixture:/synthetic-roles:ro" \
 --entrypoint python "$BACKEND_TEST_IMAGE" -c '
import hashlib,json
from pathlib import Path
from deployment.lib.maintenance_backup_roles import OriginalRoleArchive
from deployment.lib.completed_normal_admission import digest,encoded
r=Path("/synthetic-roles"); sql=(r/"original.sql").read_bytes(); original=json.loads((r/"before.json").read_bytes())
binding={"operation":"completed-normal-schema146-150-coordinated-release","context_sha256":"a"*64,"source_sha":"b"*40,"controller_sha":"c"*40,"inventory_sha256":"d"*64,"system_identifier":(r/"system-id").read_text().strip(),"source_schema":146,"target_schema":150}
meta={"version":1,"binding_sha256":digest(binding),"captured_schema":146,"preimage_sha256":digest({"roles":original}),"original_roles_sha256":digest(original),"sql_sha256":hashlib.sha256(sql).hexdigest(),"sql_bytes":len(sql),"authority_issued":False}
archive=OriginalRoleArchive(encoded(meta),sql); archive.verify(binding,expected_schema=146)
for candidate in ((r/"current.sql").read_bytes(),sql[:-10]):
 try: OriginalRoleArchive(encoded(meta),candidate).verify(binding,expected_schema=146)
 except RuntimeError: pass
 else: raise AssertionError("corrupt or fenced role input accepted")
try: archive.verify(dict(binding,system_identifier="different"),expected_schema=146)
except RuntimeError: pass
else: raise AssertionError("wrong cluster accepted")
print("PASS original capsule; fenced/truncated/wrong-cluster substitution rejected; no authority issued")'
echo 'PASS native preserved ownership/ACL/data; unauthorized UPDATE rejected'
