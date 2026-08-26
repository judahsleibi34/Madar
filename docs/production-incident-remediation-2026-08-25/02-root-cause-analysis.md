# Root-cause analysis

## Direct startup causes

1. `services/runtime_config.py` correctly requires a dedicated production `CSRF_SECRET`. The legacy environment had none because old request security fell back to unrelated application credentials.
2. The legacy Compose invocation did not inject `MADAR_RELEASE_SHA` or `MADAR_BUILD_TIMESTAMP`; hardened Compose defaults therefore resolved to `development` and `unknown`, which production validation correctly rejected.
3. Production had `ALLOW_REMOTE_DATASET_URLS=true` while the required isolated AI boundary was not enabled. The hardened validator correctly failed closed.

The validator was not weakened. Provisioning and release orchestration were brought into compliance.

## Availability cause

The legacy deployer rebuilt and recreated the active backend/frontend before candidate readiness. Rollback also rebuilt historical source rather than selecting retained artifacts. Stable origin ports therefore disappeared during both deployment and rollback, causing edge 502 periods.

## Retry-storm cause

The installed timer uses `OnUnitActiveSec=2min`. The legacy deployment state had no durable failed-SHA record or suppression check, so every tick selected the same remote SHA and repeated the disruptive workflow.

## Evidence

- Installed service executes `/usr/local/sbin/madar-auto-deploy`; its drop-in runs privileged recursive storage preparation.
- Installed timer is the old two-minute `OnUnitActiveSec` definition.
- Journal records mutable `:latest` image builds, live container recreation, rollback rebuild, and successful rollback at 14:09 followed by service failure.
- Disposable candidate startup reproduced all three configuration failures and passed when the dedicated CSRF secret, real SHA/timestamp, schema range, and disabled remote ingestion were supplied.
- The pre-merge audited code SHA `9a3c67e...` to merge SHA `eb22f736...` delta contains documentation only; no intervening application-code change caused the failure.

## Data/migration impact

The pre-migration production backup recorded schema 81, proving migrations 82/83 were not applied by the failed legacy attempts. The candidate backend failed during import, before serving requests. Candidate queue-worker durable writes could not be conclusively proven absent from retained logs; no evidence of such writes was found. This uncertainty is recorded rather than treated as proof of absence.
