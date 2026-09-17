# Tests and validation record

## Commands/results

| Validation | Exact command (abridged only where repeated mounts are documented below) | Result |
| --- | --- | --- |
| Frontend unit | `cd web/frontend && npm test` | 117 files: 116 passed, 1 failed; 739 tests: 736 passed, 2 failed, 1 skipped; 243.22 s |
| Failed module rerun | `npx vitest run --environment jsdom src/components/PageBuilder/core/PageBuilder.collisionPadding.renderer.test.jsx` | 2 failed, 4 passed; deterministic |
| Backend current-source build | `docker build --tag madar-audit-backend:0eaa9ed web/backend` | PASS |
| Backend hermetic suite | Exact `.github/workflows/backend-check.yml` mounts/env, audit image, plus `--network none --read-only` | 967 run, 3 timing errors, no external attempts |
| Timing module rerun | `python -m unittest -v tests.test_generated_code_worker tests.test_parser_isolation` in isolated audit container | 17/17 passed in 3.864 s |
| Frontend build | `cd web/frontend && npm run build` | PASS; >500 KiB chunk warning |
| Frontend lint | `cd web/frontend && npm run lint` | FAIL: 4 errors, 0 warnings |
| Theme contract | `npm run theme:audit` | PASS |
| Edge contract | `npm run edge:audit -- http://127.0.0.1:3000` | PASS |
| E2E safety guard | `npm run test:e2e:safety` | 1/1 passed |
| Mobile TypeScript | `cd mobile && npm run typecheck` | PASS |
| Mobile lint | `cd mobile && npm run lint` | PASS |
| Migration trees | `python web/scripts/check_migrations.py` in backend image | PASS, 81/81, 2 historical warnings |
| Python installed consistency | `pip check` in backend image | PASS |
| Frontend prod dependency audit | `npm audit --omit=dev --audit-level=low` | 0 vulnerabilities |
| Mobile dependency audit | same in `mobile` | 16 advisories: 5 High, 11 Moderate |
| Backup verification | `sha256sum -c SHA256SUMS`, `pg_restore --list database.dump` | 92/92 checksums; 1,059 TOC entries |

The backend full-suite errors were timeouts in otherwise valid generated-code and parser-worker cases while build/audit work was concurrently loading the host. All affected modules passed immediately in isolation. This is evidence of timing-sensitive/flaky CI thresholds, not evidence the behavior is correct under resource pressure. The full command still exited non-green and must be stabilized.

The exact backend CI command is the workflow's `docker run` with placeholder loopback Supabase values, dedicated `/tmp/madar-ci/*` storage, synthetic read-only `/test-repository` mounts, one GiB tmpfs and the current audit image; external network was additionally disabled. The initial attempt using the pre-existing development image exposed that image as stale and was excluded from authoritative source results.

## Missing test proof

- authenticated two-tenant black-box E2E;
- private/public quiz answer redaction and server-owned attempt concurrency;
- real Supabase-compatible restore/application test;
- deployment success and rollback fault injection;
- SMTP/push provider outage and dead-letter alert;
- entitlement matrices against live canonical states;
- exact 25 MiB/25 MiB+1 cross-layer production-shaped upload;
- concurrent quota/process-kill reconciliation;
- DST/recurrence/provider-token calendar E2E;
- meaningful staged load and soak tests.

G3 is **FAIL** while deterministic frontend regressions and a non-green full backend run remain.
