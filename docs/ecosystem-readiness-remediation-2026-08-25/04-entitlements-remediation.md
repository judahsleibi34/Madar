# Entitlements remediation

## Canonical resolution

`web/backend/services/entitlement_service.py` is now the server-authoritative resolution path. It distinguishes active, trial, grace, past-due/inactive, suspended/cancelled/expired, missing, malformed, ambiguous and dependency-unavailable states. Missing or malformed state grants no paid capability. Multiple entitled canonical records fail with 503 rather than choosing an arbitrary row. Legacy rows are inventory evidence, not a catalog-wide authorization fallback.

Existing public-site continuity is deliberately narrow: only a dependency outage can use an already-bound public publication fallback. A missing subscription remains a commercial denial. Explicit grandfathering is represented by explicit commercial state, never inferred from absence.

AI capability reports two independent facts: licensed capability and provider availability. An absent provider removes the operational capability without rewriting the commercial license.

## Existing tenant prerequisite

The audit found 11 tenants and no active canonical subscriptions. No plan was invented and no production row was modified. `web/backend/scripts/report_entitlement_migration.py` is a read-only/dry-run inventory tool for operator mapping. Before promotion, an authorized commercial owner must review its output and produce an explicit mapping for every tenant, including any time-bounded grace/grandfather record.

## Verification

The test matrix covers capabilities/plans, missing and malformed state, duplicate active state, inactive/suspended/expired, trial/grace/grandfathering, lookup failure, storage/user quota, builder/forms/analytics/reservations/AI and direct backend route enforcement. This finding remains partially fixed operationally until the 11 mappings exist.
