# Docker and deployment review

## Container hardening

Production and development define non-root UIDs, read-only root filesystems, all-capability drops, no-new-privileges, init, PID/CPU/memory limits, bounded tmpfs, healthchecks, internal worker networks and log rotation. Ports bind to loopback. Base images are digest-pinned. The parser cannot egress; the remote fetcher has no secret env file or host volume. No privileged mode or Docker socket mount exists inside Madar services.

Production containers are healthy and were recreated on August 23. Source and installed deploy scripts have matching SHA-256 hashes. The deployed backend/frontend images are locally built and do not carry a verifiable Git revision/SBOM label; provenance is inferred from journal/container times and checkout state rather than proven.

## Development drift

Development repository HEAD is August 23, but all live development application/worker containers were created August 14. The existing `madar_dev-backend` image contained older tests and expectations; running it initially produced obsolete failures. Development Compose does not bind-mount source, so repository edits do not affect running services until an explicit build/recreate. This recreates the prior stale-image failure mode.

Require a documented command such as `docker compose ... build --pull=false` followed by `up -d --force-recreate --wait`, and bake/display the Git SHA. CI and developers should never infer current code from “healthy.”

## Build reproducibility

The current backend built successfully into separate audit image `madar-audit-backend:0eaa9ed`. Frontend production source builds successfully; pinned lockfiles and `npm ci`/constraints are present. Registry/base images are pinned, but application images are not published as immutable release artifacts. Rollback rebuilds can still vary with build tooling/context and depend on retained external layers/packages.

The live Redis mount contradicts Compose tmpfs. This is direct evidence that Compose source plus healthy status is not sufficient proof of effective runtime configuration.

## Resource/log policy

JSON log caps are configured. Docker build cache is 81.21 GiB after the August 23 retry storm, 65.89 GiB reclaimable. Add thresholded cache monitoring and a reviewed prune policy; no destructive cleanup was performed.

G2 is **PASS WITH CONDITIONS** for a clean build, but promotion/runtime provenance is not production-grade. G16 fails in the dedicated rollback report.
