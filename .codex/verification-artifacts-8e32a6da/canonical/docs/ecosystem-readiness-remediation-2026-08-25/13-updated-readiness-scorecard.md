# Updated readiness scorecard

This is a provisional development assessment. Production remains unchanged.

| Gate | Grade | Evidence / reason | Remaining work | Blocker severity |
| --- | --- | --- | --- | --- |
| G1 Source integrity | PASS | Known clean start SHA; scoped reviewed changes; no production writes/push/secrets | Preserve logical commits and signed promotion record | Low |
| G2 Build reproducibility | PASS WITH CONDITIONS | Locks/builds green; SHA/build labels and immutable release tags | Registry retention/SBOM and staging rebuild proof | Medium |
| G3 Automated tests | PASS | Backend 1003/1003; frontend 738 pass/1 intentional skip; lint/build green | Enforce in CI | Low |
| G4 Authentication/security | PASS WITH CONDITIONS | Admin login/enrollment/removal fail closed with exact AAL2 tests | Admin enrollment and recovery drill | Medium |
| G5 Tenant isolation | PASS WITH CONDITIONS | Quiz/asset/publication/route regression coverage; explicit scopes | Authenticated two-tenant staging E2E | Medium |
| G6 Database integrity | PASS WITH CONDITIONS | Migration mirrors 82/82; isolated PG17 constraint/RPC proof | Rehearse against disposable production-like copy | Medium |
| G7 Storage/uploads | PASS WITH CONDITIONS | Safe cleanup, restrictive defaults, draft privacy, new avatar accounting | Existing-avatar backfill and production permission migration | Medium |
| G8 Public-site publication | PASS WITH CONDITIONS | Same-snapshot chrome/body and public redaction tests | Real hostname/cache staging smoke | Medium |
| G9 Forms/tests | PASS WITH CONDITIONS | Server-authoritative attempt/deadline/order/score; no public keys | Promote 082; advisory focus behavior product disclosure | Medium |
| G10 Reservations/calendar | PASS WITH CONDITIONS | Existing advisory-lock/idempotency suite remains green | Concurrency/DST/provider staging E2E | Medium |
| G11 Notifications/workers | PASS WITH CONDITIONS | Truthful channel states, bounded outcomes and diagnostics | SMTP decision/provider test; alert receiver | Medium |
| G12 Analytics | PASS WITH CONDITIONS | Existing tenant-scoped regression suite green | Retention/bot/scale controls | Medium |
| G13 AI integrations | PASS WITH CONDITIONS | Missing provider cannot appear operational or authorize a working path | Provider security/readiness only when released | Low |
| G14 External integrations | PASS WITH CONDITIONS | No insecure scope expansion; unavailable providers stay unavailable | Provider revocation/outage staging E2E | Medium |
| G15 Billing/entitlements | BLOCKED | Fail-closed code/tests complete; 11 real tenant mappings absent | Authorized canonical mapping and verification | High |
| G16 Deployment/rollback | BLOCKED | Immutable blue/green framework/fault units exist only in development | Migration executor plus staging install/fault drill | High |
| G17 Backups | PASS WITH CONDITIONS | Manifest/TOC/checksum/freshness/off-host tooling tested | Install schedule and observe successful production generations | Medium |
| G18 Restore/DR | BLOCKED | Software path prepared; no physical off-host copy/full restore | Dedicated media and replacement-host drill | High, external prerequisite |
| G19 Observability | PASS WITH CONDITIONS | Dependency/channel/backup/release diagnostics and hooks | Approved receiver, dashboards, external SLO probes | Medium |
| G20 Performance/scalability | PASS WITH CONDITIONS | Retry storm circuit breaker and thresholds; tests/build pass | Staging load/soak and bundle/query work | Medium |
| G21 Host capacity | PASS WITH CONDITIONS | Threshold tooling prepared; prior capacity evidence remains adequate | Monitor/cache cleanup and growth forecast | Medium |
| G22 Privacy/data lifecycle | BLOCKED | Cross-provider deletion remains best effort | Durable lifecycle saga and drill | Medium |
| G23 Operational documentation | PASS WITH CONDITIONS | Executable promotion/backup/restore/remediation docs added | Exercise and sign runbooks | Medium |

Totals: **PASS 2; PASS WITH CONDITIONS 17; BLOCKED 4; FAIL 0; NOT APPLICABLE 0.**

## Score: 78/100

| Weighted area | Earned / Weight | Main deduction |
| --- | ---: | --- |
| Security & authentication | 13 / 15 | operational admin recovery/enrollment drill |
| Tenant isolation | 13 / 15 | no full authenticated two-tenant staging E2E |
| Data/database integrity | 8 / 10 | production-like rehearsal and lifecycle saga absent |
| Deployment & rollback | 6 / 10 | development framework not installed/drilled; migration executor incomplete |
| Backups & recovery | 4 / 10 | no media/off-host generation/full restore |
| Builder/publication | 7 / 8 | hostname/cache smoke pending |
| Storage/uploads | 5 / 7 | avatar backfill and published namespace migration |
| Forms/reservations | 4 / 5 | staging concurrency/focus limitation |
| Notifications/workers | 4 / 5 | SMTP/alert provider unavailable |
| Tests | 5 / 5 | deterministic supported suites green |
| Observability/operations | 3 / 4 | hooks unconnected |
| Performance/capacity | 3 / 3 | architecture controls prepared; scale still conditional |
| Code quality/maintainability | 3 / 3 | scoped remediation avoids new coupling; legacy debt remains P3 |

The score does not override the four blocked gates. Classification remains **NO-GO**.
