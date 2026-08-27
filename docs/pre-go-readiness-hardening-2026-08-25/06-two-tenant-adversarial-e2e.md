# Authenticated two-tenant adversarial E2E

## Result

**PASS:** 14 staging HTTP checks, zero external network attempts.

Two synthetic tenants (`9101` and `9102`) were created with isolated memberships, content, notifications, calendars, entitlements, and deletion resources. The suite used authenticated and unauthenticated direct API calls rather than relying on frontend guards.

## Covered boundaries

- Cross-tenant user and membership access was denied.
- Builder projects, publications, draft content, and mixed identifiers remained tenant-bound.
- Draft assets required same-tenant authentication; anonymous and wrong-tenant possession was denied.
- Public site and bootstrap resolved the bound publication; grading-secret scans found zero forbidden keys.
- Cross-tenant form, quiz attempt, reservation, calendar, analytics, and notification identifiers were rejected by route tests and the full regression suite.
- Tenant A could not use Tenant B subscription or deletion request.
- Missing, malformed, and duplicate canonical entitlement states failed closed.
- CSRF rejection and exact-origin CORS behavior were exercised over HTTP.
- Administrator paths retained exact authorization and AAL2 requirements.

The successful public fixture returned only Tenant A's bound content. No fallback to Tenant B was observed.
