# Entitlement and deletion readiness summary

## Outcome

**Provisional classification: NO-GO — 79/100.** The development candidate materially closes the technical deletion-lifecycle gap, but this is not a production promotion or launch authorization.

Workstream A found **12 production tenants**, not the 11 recorded on 2026-08-24. None has an entitlement-bearing canonical subscription. All 12 require an authorized commercial decision; no plan or state was assigned. `MADAR-BILL-001` is therefore **PARTIALLY FIXED** and G15 remains **BLOCKED ON AUTHORIZED COMMERCIAL MAPPING**.

Workstream B implements an additive schema-83 deletion saga with durable requests and steps, atomic freeze/manifest capture, leased worker claims, bounded retry, late authentication-provider deletion, explicit retained classes, and a verification pass. It is covered by unit/adversarial tests and a disposable PostgreSQL 17 rehearsal. `MADAR-DATA-001` is **FIXED IN THE VALIDATED DEVELOPMENT CANDIDATE**; G22 is **PASS WITH CONDITIONS** pending controlled promotion, worker activation, a non-customer operational exercise, and policy decisions listed in `09-deletion-retention-policy-gaps.md`.

Production source, subscriptions, tenant data, users, infrastructure, and traffic were not modified. Nothing was pushed. No frontend file changed and the UI was not redesigned.

## Source evidence

- Development start: branch `builder-backend`, clean SHA `ec0c2fa10b36115afae523460319313428a29133`.
- Production inspection: branch `main`, clean SHA `0eaa9edd297d2fd6618d50ae5dfc4b08c94ba1df`.
- The production inventory ran through the existing production backend container using SELECT-only code; names were omitted from the report and no output file was written there.
- Production inventory timestamp: `2026-08-25T07:03:07.725079+00:00`.

## Validation

- Backend: **1,032/1,032 passed**, 0 failures, 0 unexpected skips; external attempts `[]`.
- Frontend: **738 passed, 1 intentional skip**; lint PASS; build PASS.
- Migration checker: 83/83 mirrors, 0 errors, two unchanged historical duplicate-content warnings.
- PostgreSQL: migration 083 forward application and rerun PASS on disposable PostgreSQL 17, including entitlement replay, retention, RLS, double-claim rejection, and lease recovery.
- Development runtime: backend/frontend image labels and `/health/version` match code SHA `09e4076566b27a42dedee414ae9abe20c062e63b`; both containers are healthy, readiness is HTTP 200 on existing development schema 81, frontend is HTTP 200, and deletion worker state is truthfully `disabled` until schema 083 is promoted.

## Remaining launch blockers

1. G15: authorized commercial mapping for all 12 tenants, dry-run review, approved application, and post-apply capability verification.
2. G16: staging deployment/migration/traffic-switch/rollback fault drill remains outside this task.
3. G18: physical off-host media and complete replacement-host restore remain outside this task.
4. Promote schema 083, application image, and the deletion worker through the controlled release process; then perform a synthetic/non-customer lifecycle exercise.
