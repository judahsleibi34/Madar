# Auto-deploy and rollback review

## Current flow

```text
2-minute timer
 -> root storage preparation (recursive chown)
 -> unprivileged wrapper fetches origin/main
 -> flock /tmp/madar-production-deploy.lock
 -> require main + clean tree + fast-forward
 -> reset checkout to target
 -> validate Compose
 -> build while old containers run
 -> Compose up --wait
 -> backend deep readiness (12 x 5 s)
 -> frontend GET
 -> on failure reset old commit, rebuild, Compose up, healthcheck
```

The lock prevents overlap; dirty-tree and non-fast-forward states fail safely. Builds occur before container replacement. The service runs as `madar`, deploy scripts are root-owned and installed copies hash-match source. Storage preparation rejects symlink roots. These are meaningful controls.

## Confirmed production failure

On 2026-08-23, the timer repeatedly attempted builds approximately every two minutes for hours after failures. At 10:49 UTC it deployed current target `0eaa9ed`; backend readiness returned failure for all 12 attempts. At 10:56 it reset to `82d78dd`, rebuilt the prior source and started rollback containers. Rollback backend readiness also failed all 12 attempts. At 11:01:22 the journal recorded:

`CRITICAL: Automatic rollback failed.`

Production was later manually recreated and is currently healthy. This proves rollback is not reliable and that the timer has no exponential backoff/circuit breaker after deterministic failure.

## Failure model defects

- Migrations are explicitly not run by the deploy script. A commit requiring migration can be pulled automatically into an incompatible schema and repeatedly fail.
- There is no preflight comparison between application schema range and live schema before replacing containers.
- The prior image digest is not captured/retained; rollback rebuilds old source. Build failure, registry/cache loss or non-reproducible dependency behavior can prevent recovery.
- There is no traffic drain/maintenance switch, blue-green target, database write pause or post-deploy business smoke test.
- Old code/new DB and new code/old DB compatibility are not classified per release. Migrations cannot be rolled back automatically and partial migrations are outside the script's state machine.
- A reboot can leave checkout, images and containers at different stages; no durable deployment transaction/journal resolves intent on restart.
- Root `chown -R` runs every timer even when there is no new commit, and scales with stored files.
- Tunnel traffic continues throughout a bad container replacement.

## Required production design

Promote a CI-built, scanned, immutable image set tagged by Git SHA and digest. Preflight clean source, exact env schema, disk, backup freshness, migration contract and prior image availability. Apply only rehearsed backward-compatible migrations with a durable deployment record. Start the candidate on separate ports/network, run deep readiness and read-only business/tenant smoke tests, then switch traffic. Roll back traffic to the retained prior image only when schema compatibility is certified; otherwise execute a rehearsed forward repair. Add retry backoff and operator intervention after one failed target.

G16 is **FAIL (High)**. Do not leave automatic production promotion enabled for new customer releases until both success and rollback fault-injection drills pass.
