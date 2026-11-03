#!/usr/bin/env bash
# Source only from a bounded synthetic rehearsal; this owns one exact container.
synthetic_postgres_cleanup() {
  local result=$?
  trap - EXIT INT TERM
  if ! python3 "$SCRIPT_DIR/synthetic_postgres.py" cleanup "$CONTAINER_NAME" \
      "$SYNTHETIC_POSTGRES_OWNER" "$SYNTHETIC_POSTGRES_PURPOSE" "$POSTGRES_IMAGE"; then
    echo 'synthetic_postgres_cleanup_failed: ownership or Docker observation refused' >&2
    if ((result == 0)); then result=1; fi
  fi
  exit "$result"
}

synthetic_postgres_start() {
  SYNTHETIC_POSTGRES_PURPOSE="$1"
  SYNTHETIC_POSTGRES_OWNER="$(python3 -c 'import uuid; print(uuid.uuid4())')"
  CONTAINER_NAME="madar-synthetic-$SYNTHETIC_POSTGRES_OWNER"
  # Install before create: failed starts and lost create acknowledgements still
  # leave a container that must be authenticated and removed.
  trap synthetic_postgres_cleanup EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  docker create --memory=768m --cpus=0.75 --pids-limit=128 --restart=no \
    --name "$CONTAINER_NAME" --label "madar.rehearsal=$SYNTHETIC_POSTGRES_PURPOSE" \
    --label "madar.rehearsal.owner=$SYNTHETIC_POSTGRES_OWNER" \
    --publish 127.0.0.1::5432 --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=1g \
    -e POSTGRES_HOST_AUTH_METHOD=trust "$POSTGRES_IMAGE" >/dev/null
  local container_id
  container_id="$(python3 "$SCRIPT_DIR/synthetic_postgres.py" identity "$CONTAINER_NAME" \
    "$SYNTHETIC_POSTGRES_OWNER" "$SYNTHETIC_POSTGRES_PURPOSE" "$POSTGRES_IMAGE")"
  docker start "$container_id" >/dev/null
  SYNTHETIC_POSTGRES_PORT="$(python3 "$SCRIPT_DIR/synthetic_postgres.py" port "$CONTAINER_NAME" \
    "$SYNTHETIC_POSTGRES_OWNER" "$SYNTHETIC_POSTGRES_PURPOSE" "$POSTGRES_IMAGE")"
}
