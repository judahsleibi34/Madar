# Test results

## Backend

- Full hermetic suite: **1,068/1,068 passed**.
- Failures: 0.
- Unexpected skips: 0.
- External network attempts: 0 (`EXTERNAL_ATTEMPTS []`, `EXTERNAL_SITES []`).
- Final exact-image runtime: 58.978 seconds.
- Installed dependency consistency: `pip check` passed.

Focused coverage includes runtime configuration, MFA/AAL2, entitlements, deletion, quiz, publication, storage/quota/privacy, deployment, migration, backup, workers, readiness, Redis/rate limits, and tenant isolation.

## Frontend

- Test files: **119/119 passed**.
- Tests: **744 passed, 1 intentional skip**.
- Failures: 0.
- Lint: PASS.
- Production build: PASS (`vite`, 2,587 modules; large-chunk advisory remains nonblocking).
- CSP/theme security checks: PASS.
- Production API-origin source/build/bundle checks: PASS.
- Negative builds with missing or noncanonical production API origins: rejected.

An initial parallel validation invocation caused resource-contention timeouts in several deterministic frontend tests. Those duplicate harnesses were terminated, and the authoritative serialized rerun above passed in 177.33 seconds. No test was weakened.

## Other gates

- Dependency locks: PASS.
- Migration parity: 83/83, zero errors.
- Production backup verification: PASS.
- npm production dependency audit from the unchanged lockfile: zero vulnerabilities in the preceding candidate gate.
- Path-only tracked high-confidence secret scan: zero candidate files.

## Live corrective release checks

- Inactive candidate API origin in bundle: canonical production host present;
  bad `/api/auth/login` pattern absent.
- Inactive and live candidate `/health/version`: exact `4faf63a6...`.
- Login preflight: HTTP 200 with exact-origin credentialed CORS.
- Controlled invalid login: HTTP 422 JSON; no real credentials used.
- Madar origin HTML: zero executable inline scripts.
- Public edge HTML: Cloudflare-only inline/Insights injection observed and
  blocked by the unchanged strict CSP.
