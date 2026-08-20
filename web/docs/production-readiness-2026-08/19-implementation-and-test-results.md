# Implementation and test results

Evidence date: 2026-08-19. This document is finalized after the validation pass. No production mutation is authorized by these changes.

## Development implementation

### Madar

- backup format 2 publishes a hidden same-filesystem staging directory atomically only after manifest/checksum verification and adds `BACKUP_COMPLETE`; failed staging is never named as a final recovery point;
- verification accepts legacy format 1 while requiring the completion marker for format 2;
- migration 081 introduces an authoritative application schema-version row in both mirrored migration trees; runtime service-role access is read-only;
- readiness performs one bounded authoritative schema query rather than dozens of remote table probes, and fails closed for missing, duplicate, malformed or stale state;
- regression tests cover successful/failed backup publication, legacy/new verification, one-probe schema readiness, stale/missing state and mirrored migration policy.

Migration 081 is development-only. Production order is migration with approved authority, then compatible application. Until that separately approved deployment, live readiness continues to report the existing schema-unavailable condition.

### Briefedly

- status and OpenAPI identity now use `briefedly-backend`/Briefedly rather than the historical Priorify name;
- an integration assertion prevents the stale service identity from recurring.

The secure Ollama and least-privilege database changes remain those in committed P0 development work; no weakening or production reconciliation occurred.

## Validation results

Final clean-diff validation results:

| Repository/suite | Passed | Failed | Skipped/blocked | Notes |
|---|---:|---:|---:|---|
| Madar backup tooling | 7 | 0 | 0 | host Python standard-library harness |
| Madar readiness targeted | 21 | 0 | 0 | actual module and repository tests with only unavailable imported dependencies stubbed; `APP_ENV=test` |
| Madar Python syntax | 3 files | 0 | 0 | changed readiness/test modules compiled |
| Madar shell syntax | 3 scripts | 0 | 0 | backup, verify and restore scripts |
| Madar migration mirror | 1 | 0 | 0 | byte-identical SQL trees; read-only runtime grant asserted in readiness suite |
| Madar Compose | 2 files | 0 | 0 | `config --no-interpolate --quiet`; no secret rendering |
| Madar frontend build/theme audit | 1 | 0 | 0 | production build passed; 2,587 modules |
| Madar frontend unit suite, current attempt | summary unavailable | 2 known failures | runner did not terminate | reproduced only the two pre-existing Page Builder collision/render assertions |
| Madar frontend last complete checkpoint (2026-08-18) | 735 | 2 | 1 | same frontend HEAD/diff; supporting context, not substituted for a current completed run |
| Briefedly identity assertions | 3 | 0 | 0 | AST/source assertions plus changed-file compilation |
| Briefedly Compose | 2 files | 0 | 0 | `config --no-interpolate --quiet`; no secret rendering |
| Briefedly frontend unit | 5 | 0 | 0 | all state tests passed |
| Briefedly frontend build | 1 | 0 | 0 | production build passed; 1,840 modules |
| Briefedly backend/P0 runtime rerun | 0 | 0 | blocked | host lacks Python dependencies and isolated Docker access was rejected by the execution environment usage gate |
| Both repository diff checks | 2 | 0 | 0 | no whitespace errors |

Unavailable external tests are intentionally separate: Node B hardware/GPU benchmarks, real Ollama gateway, backup-drive/off-host restore, Google verification/security assessment, public perimeter scan requiring approved source, and production P0 cutover. They are not counted as passing.

The unchanged Briefedly P0 checkpoint remains 136/136 backend tests, 33/33 P0-specific tests and 9/9 disposable-PostgreSQL tests from 2026-08-18. Those counts are historical evidence only; they were not re-counted as current passes. A current isolated-container rerun was attempted but Docker access was unavailable. One exploratory Madar invocation used an unsupported Vitest reporter name and failed before test discovery; the normal command was then used and is the result recorded above.

## Baseline runtime evidence

Node A had 43 running containers at inspection. Root filesystem was 456 GiB total, 117 GiB used and 320 GiB available (27% used); inode use 13%. RAM was 7.2 GiB total with 3.8 GiB available; 1.6 GiB of 4 GiB swap was in use. These are a point-in-time sample, not capacity certification.

Madar liveness returned 200; readiness returned 503 solely with schema unavailable in the captured component metadata, while backup freshness was disabled. Briefedly production exposed only backend/frontend/database and no worker; its shallow status returned 200 with stale Priorify identity. Production Alembic revision remained `d8c6b4a2f190`; the development target remained `c8e5f1a3b647`. Aggregate-only production inspection found 2 users, 2 workspaces, 2 Gmail connections, 141 threads, 173 messages, 5 imports, 2 reports and 4 report sources. The live `briefedly_app` role still had all five prohibited elevated flags. No row content was read.

## Safety

No production repository, database/schema/data, credential, container/service, Mailcow file, firewall/SSH rule, Cloudflare/DNS setting, router or external provider state was changed. No customer-content test, real Gmail test, real Ollama test, production load test, push or merge occurred.
