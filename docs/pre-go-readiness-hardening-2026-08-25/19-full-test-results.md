# Full validation results

## Backend

The complete supported no-external-network suite ran against final code SHA `9a3c67e6058768b71100349b89379b2b6052915a`:

```text
Tests run: 1047
Passed: 1047
Failed: 0
Unexpected skips: 0
Runtime: 82.005 seconds
External network attempts: 0
External sites contacted: 0
```

Focused coverage includes deployment, schema compatibility, quiz redaction/server scoring, MFA/AAL2, canonical entitlements, deletion lifecycle, publication identity, storage/quota, notifications, Redis failure policy, rate limiting, health/readiness, and two-tenant isolation.

## Frontend

No frontend application/UI file changed. `web/frontend/Dockerfile` was changed only to place release metadata arguments after `npm ci`, preserving the dependency cache across immutable SHA builds without changing browser behavior.

```text
Unit: 117 files, 738 passed, 1 intentional skip
Lint: PASS
Build: PASS (6.14 seconds)
```

The intentional skip is the established baseline, not an unexpected environmental skip.

## Migrations and disposable services

- Migration mirror checker: 83/83, zero errors.
- PostgreSQL 17 schema 81 -> 82 -> 83: PASS.
- Migration rerun and held-lock refusal: PASS.
- RLS/grants and integrity query suite: PASS.
- Redis healthy/outage/recovery and fail-closed protection: PASS.

## Docker release identity

- Running staging SHA: `9a3c67e6058768b71100349b89379b2b6052915a`.
- Backend digest: `sha256:67ba38a4bfbe0387c7d100b6f68458d768627dfb93d85dbc716563768ca7c134`.
- Frontend digest: `sha256:0941db55d35246b4e78ecffedafb0ea46b5ed38a43cd9d042a90863db18d38e2`.
- Image labels and `/health/version` matched the intended code SHA.

## Safety

All provider integrations used mocks/fakes or local disposable infrastructure. No SMTP, Google, Microsoft, AI, customer endpoint, or other external provider was contacted.
