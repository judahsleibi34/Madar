# Master implementation: architecture and release gaps

Attested 2026-09-08. Baseline main/production/controller/live:
`29dabdff2667984b8d66ff038be4463e46b93421`, green, schema 93.
This is an implementation work record, not release acceptance.

## Existing architecture to preserve

| Area | Existing implementation | Observed gap / required work |
| --- | --- | --- |
| Authentication | HttpOnly access/refresh cookies; Supabase Auth get_user; bounded refresh replay; email verification and account lifecycle | Shared client session used by AAL2 helper and several MFA operations. Bind sensitive authorization to the verified requesting session. |
| Authorization | tenant_service verifies tenant/user/auth membership and lifecycle; platform admin is distinct; site_permission_service checks resource access | Audit coverage for all privileged client paths; 51 runtime files reference service_supabase in initial static inventory. Static discovery is not a completed authorization audit. |
| Commercial catalog | commercial_catalog.py: four base plans, 25 capabilities, USD minor units, add-ons | No e-commerce capability; Website reservations copy contradicts matrix. Do not choose commercial mapping silently. |
| Commercial subject | tenant_subscriptions / tenant_addons; migration 083 decisions; unique entitlement-bearing row | Already tenant scoped. Live 12 tenants have no approved entitlement decisions and no entitlement-bearing subscriptions. Tenant 8 has Forms/pending_review; three legacy rows canceled. Global enforcement blocked. |
| Resolution | entitlement_service.py; unknown plan denies; dependency errors deny; configurable compatibility override | period_start/end ignored; active add-ons can grant on unknown base plan; lookup bounded before active filtering; explicit expiry, safe registry validation, and revision required. |
| Manual administration | admin_billing_routes requires system admin + AAL2; assign_commercial_subscription RPC | Existing grant operation is not a cash ledger. Need append-only payment, period, correction/revocation, fingerprint idempotency and audit in one transaction. |
| Frontend | billing catalog/entitlements APIs; dashboard/sidebar/store screens; browser cookies | Sidebar e-commerce unconditional; no universal capability guard. No premium prefetch before permission resolution. |
| Catalog | migrations 070/088/089; categories/tags/products; UUIDs, NUMERIC prices; asset ownership checks | Variants and explicit capability assignment missing. Remote images allowed. No generalized currency exponent support. |
| Orders | migration 090; public_site_routes order creation; order/line snapshots; COD only | Separate inserts + compensating deletion; read-only stock check; no durable idempotency; tax/shipping config ignored. Must make financially correct before new sales. |
| Public isolation | verified website settings and tenant lifecycle; standard slug + branded bindings | Store binding cache can bypass fresh lifecycle verification; forwarded host/origin influences routing; no e-commerce publication capability. Preserve standard paths and add validated host boundary. |
| Payments | legacy billing webhook/request code; no CyberSource client found | Need separate subscription/order merchant contexts; durable attempts/events, unknown state, reconciliation, verified encrypted webhook. Live processing prohibited. |
| Supabase | centralized database.py; Auth + PostgREST + Storage; opaque key compatibility already exists | Preserve modern key header handling. Complete schema/service inventory and self-host integration tests before any cutover claim. |
| Storage | local private/public roots + provider-backed builder assets; signed URL verifies configured scheme/host | S3-to-S3 migration, bucket/object/reference parity required; physical file copy is not Storage API migration. |
| Existing queues | durable notification outbox; calendar queue RPCs, claims and retries; dedicated workers | Reuse worker conventions, not best-effort notification enqueue as transaction guarantee. General external sync absent. |
| Recovery | format-3 DB/local/provider backup, verification marker, Node 1 replica, isolated restore tool | Preserve all. Full Supabase platform recovery and PITR are not attested by logical backup. |
| Release | paired migrations + validators; immutable blue/green controller; exact-SHA governed upgrade | New schema must rehearse before release; no production source edits, cutover or manual state writes. |
| Node 1 | i3-6100, 4 logical CPUs, 7.2 GiB RAM; Mailcow containers; /dev/sdc1 ext4 at /srv/data2, 869 GiB available | SMART privileged check blocked: sudo -n requires authentication. Do not select primary placement before disk and capacity proof. /srv/data1 prohibited; /srv/data2/docker reserved for Mailcow. |

## Release prerequisites

1. User-confirmed e-commerce plan mapping and resolution of reservations conflict.
2. Explicit tenant commercial decisions; current usage is not payment evidence.
3. Request-bound AAL2, temporal entitlement checks, financial transactions and isolation regressions.
4. Complete CI, safe E2E, migration/restore rehearsal, exact-head checks and healthy governed release.
5. Self-host readiness requires its own target versions, complete platform tests, Storage and Auth parity and PITR proof.

No existing override is authority to fabricate grants. No production enforcement
activation, customer DB onboarding, real payment processing or DB cutover follows
from this document.
