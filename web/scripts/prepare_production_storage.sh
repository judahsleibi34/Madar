#!/usr/bin/env bash
set -Eeuo pipefail

# This script is deliberately non-configurable: only Madar's four trusted bind
# mount roots may be created or recursively re-owned.
if (( $# != 0 )); then
    echo "Usage: $0" >&2
    exit 64
fi

if (( EUID != 0 )); then
    echo "Production storage preparation must run as root." >&2
    exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# The web sources moved below web/, but the production data directories must
# remain at the repository root so existing bind mounts keep the same host
# paths across the monorepo transition.
REPOSITORY_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd -P)"
readonly STORAGE_UID=65534
readonly STORAGE_GID=65534
readonly STORAGE_MODE=0755
readonly -a STORAGE_PATHS=(
    "backend/private_uploads"
    "backend/avatar_uploads"
    "backend/private_generated_charts"
    "backend/uploads"
)

for relative_path in "${STORAGE_PATHS[@]}"; do
    target_path="$REPOSITORY_ROOT/$relative_path"
    if [[ -L "$target_path" ]]; then
        echo "Refusing symbolic-link storage root: $relative_path" >&2
        exit 1
    fi

    install -d \
        -o "$STORAGE_UID" \
        -g "$STORAGE_GID" \
        -m "$STORAGE_MODE" \
        -- "$target_path"

    # Existing content is retained. Recursive ownership is required because
    # tenant directories may have been created by an older root-run container.
    chown -R -- "$STORAGE_UID:$STORAGE_GID" "$target_path"
    chmod "$STORAGE_MODE" -- "$target_path"
done
