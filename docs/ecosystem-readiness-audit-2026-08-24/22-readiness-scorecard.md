# Readiness gates

| Gate | Grade | Evidence / reason | Remaining work | Blocker severity |
| --- | --- | --- | --- | --- |
| G1 Source integrity | PASS WITH CONDITIONS | Both clean tracked trees at same commit/upstreams; ignored operational roots understood | Add artifact SHA provenance; reports are new dev-only changes | Low |
| G2 Build reproducibility | PASS WITH CONDITIONS | Current backend/frontend builds; pinned locks/digests | Publish immutable app images/SBOM; remove stale dev runtime | Medium |
| G3 Automated tests | FAIL | Frontend 736 pass/2 fail/1 skip plus 4 lint errors; backend 967/3 timing errors; isolated rerun passes | Fix renderer/lint and timing flakiness; all-green full run | Medium |
| G4 Authentication/security | FAIL | Cookies/CSRF/CORS/AAL2 strong; MFA login/factor removal fail open | Close AUTH-001/002; enroll/test admins | High |
| G5 Tenant isolation | PASS WITH CONDITIONS | No live mismatch/duplicates; strong hostname/project/RPC filters; distinct live samples | Disposable authenticated two-tenant adversarial E2E | Medium |
| G6 Database integrity | PASS WITH CONDITIONS | PG17, schema81, RLS64/64, constraints, no current overlaps/counter errors | Active-subscription uniqueness; migration rehearsals | Medium |
| G7 Storage/uploads | PASS WITH CONDITIONS | Exact limits, streaming/signatures, atomic quota, readiness write probe | Cleanup schedule, avatar quota, permissions, malware policy | Medium |
| G8 Public-site publication | PASS WITH CONDITIONS | Atomic snapshot/binding/ETag isolation; bootstrap exception | Fix snapshot bootstrap; published asset visibility design | Medium |
| G9 Forms/tests | FAIL | Ordinary forms idempotent; public answer keys and no server quiz enforcement | Rebuild test attempt/scoring model | High |
| G10 Reservations/calendar | PASS WITH CONDITIONS | Reservation advisory lock/idempotency; zero live overlaps; calendar scoped | Concurrency/DST/provider E2E | Medium |
| G11 Notifications/workers | FAIL | workers/push/internal active; SMTP absent and 3 dead | Configure/disable email and alert dead deliveries | High |
| G12 Analytics | PASS WITH CONDITIONS | Implemented tenant-scoped basic/advanced data analytics | Retention, bot quality, scale benchmarks | Medium |
| G13 AI integrations | FAIL | Code exists, provider absent/guard disabled, fallback grants AI | Deny as N/A or configure secure provider/readiness | Medium/High via BILL |
| G14 External integrations | PASS WITH CONDITIONS | Google/ICS ready; OAuth state/credential controls; Microsoft unconfigured; Drive roadmap | Provider revocation/outage E2E; accurate availability UI | Medium |
| G15 Billing/entitlements | FAIL | 0 active canonical subscriptions; permissive fallback | Canonicalize and fail closed | High |
| G16 Deployment/rollback | FAIL | Production rollback actually failed | Immutable/blue-green/schema-aware deployment drill | High |
| G17 Backups | FAIL | Valid fresh local backup; no schedule/off-host/freshness | Automate, encrypt, replicate, alert | High |
| G18 Restore/DR | BLOCKED | Partial restore only; full Supabase-compatible target unavailable | Full isolated platform/replacement-host drill | High |
| G19 Observability | FAIL | Structured logs/IDs; false-green dependencies/no alerts | External SLO dashboards/alerts/runbooks | Medium |
| G20 Performance/scalability | PASS WITH CONDITIONS | Current small load fits; no disruptive test | Staging load/soak and query/bundle tuning | Medium |
| G21 Host capacity | PASS WITH CONDITIONS | 318 GiB free, 3.3 GiB available; swap/cache risks | Monitor/threshold cache, swap, disk growth | Medium |
| G22 Privacy/data lifecycle | FAIL | Delete/retention/export coverage incomplete and multi-system best effort | Formal lifecycle workflows and verification | Medium |
| G23 Operational documentation | FAIL | Strong design docs, but rollback/backup/entitlement claims diverge from reality | Supersede stale runbooks; executable incident/release/DR docs | Medium |

## Totals

- PASS: 0
- PASS WITH CONDITIONS: 11
- BLOCKED: 1
- FAIL: 11
- NOT APPLICABLE: 0

The launch result is **NO-GO** regardless of the 58/100 score because six High production blockers remain.
