#!/usr/bin/env bash
# Hermetic CI-equivalent backend runner. Only read-only source mounts and /tmp.
set -euo pipefail
REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
if (( $# == 0 )); then
 set -- python scripts/run_tests_no_external_network.py
fi
docker run --rm --network none \
 --env APP_ENV=test \
 --env SUPABASE_URL=http://127.0.0.1:54321 \
 --env SUPABASE_ANON_KEY=madar-ci-placeholder-anon-not-a-secret \
 --env SUPABASE_SERVICE_KEY=madar-ci-placeholder-service-not-a-secret \
 --env PUBLIC_UPLOADS_DIR=/tmp/madar-ci/public/uploads \
 --env DATA_UPLOAD_DIR=/tmp/madar-ci/private/uploads \
 --env PRIVATE_CHARTS_DIR=/tmp/madar-ci/private/generated-artifacts \
 --env MADAR_UPLOAD_WORKSPACE_DIR=/tmp/madar-ci/parser \
 --env MPLCONFIGDIR=/tmp/madar-ci/cache/matplotlib \
 --env XDG_CACHE_HOME=/tmp/madar-ci/cache/xdg \
 --env PYGWALKER_TELEMETRY_ENABLED=false \
 --env MADAR_TEST_REPOSITORY_ROOT=/test-repository \
 --tmpfs /tmp:rw,exec,nosuid,nodev,size=1g,mode=1777 \
 --volume "$REPO_ROOT/web/demo-data:/demo-data:ro" \
 --volume "$REPO_ROOT/web/frontend/public:/frontend/public:ro" \
 --volume "$REPO_ROOT/web/database:/app/database:ro" \
 --volume "$REPO_ROOT/web/supabase:/app/supabase:ro" \
 --volume "$REPO_ROOT/web/frontend/storefront_frame_headers.conf.template:/test-repository/frontend/storefront_frame_headers.conf.template:ro" \
 --volume "$REPO_ROOT/web/frontend/admin_preview_frame_headers.conf.template:/test-repository/frontend/admin_preview_frame_headers.conf.template:ro" \
 --volume "$REPO_ROOT/web/frontend/vite.config.js:/test-repository/frontend/vite.config.js:ro" \
 --volume "$REPO_ROOT/web/scripts:/scripts:ro" \
 --volume "$REPO_ROOT/web/scripts:/test-repository/scripts:ro" \
 --volume "$REPO_ROOT/web/deployment:/test-repository/deployment:ro" \
 --volume "$REPO_ROOT/web/backend/Dockerfile:/test-repository/backend/Dockerfile:ro" \
 --volume "$REPO_ROOT/web/frontend/Dockerfile:/test-repository/frontend/Dockerfile:ro" \
 --volume "$REPO_ROOT/web/frontend/security_headers.conf.template:/test-repository/frontend/security_headers.conf.template:ro" \
 --volume "$REPO_ROOT/web/frontend/nginx.conf.template:/test-repository/frontend/nginx.conf.template:ro" \
 --volume "$REPO_ROOT/web/docker-compose.yml:/test-repository/docker-compose.yml:ro" \
 --volume "$REPO_ROOT/web/docker-compose.dev.yml:/test-repository/docker-compose.dev.yml:ro" \
 --volume "$REPO_ROOT/web/database:/workspace/database:ro" \
 --volume "$REPO_ROOT/web/supabase:/workspace/supabase:ro" \
 --volume "$REPO_ROOT/web/database:/database:ro" \
 --volume "$REPO_ROOT/web/supabase:/supabase:ro" \
 --volume "$REPO_ROOT/.github/workflows/backend-check.yml:/test-repository/.github/workflows/backend-check.yml:ro" \
 madar-current-reconciliation-test "$@"
