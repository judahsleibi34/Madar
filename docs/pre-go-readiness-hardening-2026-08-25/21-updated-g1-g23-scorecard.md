# Updated G1-G23 readiness scorecard

| Gate | Grade | Current evidence | Remaining work / blocker severity |
| --- | --- | --- | --- |
| G1 Source integrity | PASS | Clean local history; production read-only; immutable SHA identity. | None. |
| G2 Build reproducibility | PASS | SHA images, digests, locks, SBOMs, repeat builds. | None. |
| G3 Automated tests | PASS | Backend 1,047/1,047; frontend 738 plus one intentional skip; lint/build pass. | None. |
| G4 Authentication/security | PASS | MFA fail-closed, exact AAL2, CSRF/CORS/cookie HTTP drills, no-network regressions. | None. |
| G5 Tenant isolation | PASS | Authenticated two-tenant HTTP suite and full BOLA/ownership regressions. | None. |
| G6 Database integrity | PASS | PG17 81->83, parity, RLS/grants, zero integrity anomalies. | None. |
| G7 Storage/uploads | PASS | Quota/avatar tooling, reconciliation, private permissions, 25 MiB boundary. | Production changes remain a controlled promotion step, not missing engineering. |
| G8 Public-site publication | PASS | Same snapshot, hostname/project/publication binding, secret scan, asset boundary. | None. |
| G9 Forms/tests | PASS | Server-authoritative attempt/scoring, publication pin, replay/concurrency/redaction tests. | Focus signals remain advisory by browser nature. |
| G10 Reservations/calendar | PASS | Tenant isolation and 20-way contention produced exactly one winner. | External calendars remain disabled unless separately enabled. |
| G11 Notifications/workers | PASS | Worker outage/restart, queue observability, truthful disabled SMTP. | SMTP remains intentionally disabled until real provider configuration. |
| G12 Analytics | PASS | Tenant/abuse/pagination/rate-limit and bounded ingestion tests. | Retention duration is tracked under G22 policy. |
| G13 AI integrations | NOT APPLICABLE | Unreleased/unconfigured AI/OCR paths remain unavailable and fail closed. | Separate enablement review if released. |
| G14 External integrations | PASS | Released paths fake-tested; unavailable providers truthfully disabled. | Microsoft must remain disabled until provider revocation support is added. |
| G15 Billing/entitlements | BLOCKED | Canonical resolver and apply tooling pass; 12 production tenants lack authorized decisions. | **High: BLOCKED ON AUTHORIZED COMMERCIAL MAPPING.** |
| G16 Deployment/rollback | PASS | Real blue/green switch, 81->83 locked migration, failure campaign, retained rollback, bad-SHA suppression. | Whole-node reboot deferred for shared-host safety; equivalent process interruption passed. |
| G17 Backups | PASS | Local backup manifest, checksums, completion marker, verification, alerting. | Continue scheduled verification. |
| G18 Restore/DR | BLOCKED | Software/media path prepared; dedicated drives absent; no replacement-host restore. | **High: BLOCKED ON PHYSICAL BACKUP DRIVES / FULL RESTORE.** |
| G19 Observability | PASS | Truthful layered health, protected diagnostics, 12 alert classes, current runbooks. | Connect chosen production alert provider during promotion. |
| G20 Performance/scalability | PASS WITH CONDITIONS | Bounded p50/p95/p99, rate abuse, reservation contention, queue/concurrency regressions. | Low: prolonged soak and larger scale proof before broad expansion. |
| G21 Host capacity | PASS WITH CONDITIONS | Disk/inode/RAM healthy; threshold tooling works. | Medium: swap 83% and cache 101.9 GB require headroom recovery before promotion. |
| G22 Privacy/data lifecycle | PASS WITH CONDITIONS | Durable saga operationally verified; retained classes explicit. | Medium policy: approve retention durations; engine does not invent them. |
| G23 Operational documentation | PASS | Current source-of-truth index, promotion steps, and incident runbooks. | Keep versioned with releases. |

## Totals

- PASS: 17
- PASS WITH CONDITIONS: 3
- BLOCKED: 2
- FAIL: 0
- NOT APPLICABLE: 1

Technical readiness excluding G15/G18: **95/100 — CONDITIONAL GO**. Overall launch readiness: **86/100 — NO-GO**.
