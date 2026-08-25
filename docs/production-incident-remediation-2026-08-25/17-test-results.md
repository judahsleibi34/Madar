# Test results

## Backend

- Full hermetic suite: **1,068/1,068 passed**.
- Failures: 0.
- Unexpected skips: 0.
- External network attempts: 0 (`EXTERNAL_ATTEMPTS []`, `EXTERNAL_SITES []`).
- Runtime: 74.495 seconds.
- Installed dependency consistency: `pip check` passed.

Focused coverage includes runtime configuration, MFA/AAL2, entitlements, deletion, quiz, publication, storage/quota/privacy, deployment, migration, backup, workers, readiness, Redis/rate limits, and tenant isolation.

## Frontend

- Test files: **118/118 passed**.
- Tests: **741 passed, 1 intentional skip**.
- Failures: 0.
- Lint: PASS.
- Production build: PASS (`vite`, 2,587 modules; large-chunk advisory remains nonblocking).
- CSP/theme security checks: PASS.

An initial parallel validation invocation caused resource-contention timeouts in several deterministic frontend tests. Those duplicate harnesses were terminated, and the authoritative serialized rerun above passed in 177.33 seconds. No test was weakened.

## Other gates

- Dependency locks: PASS.
- Migration parity: 83/83, zero errors.
- Production backup verification: PASS.
- npm production dependency audit from the unchanged lockfile: zero vulnerabilities in the preceding candidate gate.
- Path-only tracked high-confidence secret scan: zero candidate files.
