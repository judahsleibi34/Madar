# Commercial, commerce, payment, migration and sync threat model

Review date: 2026-09-08. Baseline: schema 93. Controls below are requirements;
only controls backed by test evidence may be reported as implemented.

## Trust boundaries and assets

Anonymous visitors, shoppers, ordinary members, owners, employees and tenant
administrators remain untrusted. A higher plan does not elevate role. A malicious
tenant, compromised tenant account, compromised platform administrator,
malicious browser, webhook/replay attacker, compromised payment credentials,
malicious product author, malicious external database/connector, compromised
connector agent/worker, rogue sync event, network attacker and stolen integration
credentials are in scope. Platform administrators can record approved commercial
transactions but cannot choose unbounded SQL, redirect providers or bypass AAL2.

Protected assets include tenant capability state, orders, immutable sale truth,
inventory, payment/refund state, cash records, customer PII, merchant mappings,
CyberSource credentials, Auth users/sessions, PostgreSQL, backups, object storage,
external client records, connector credentials, versions and mappings.

Boundaries: browser → authenticated Madar API → verified membership/tenant →
role + commercial capability + resource/state authorization → privileged DB.
Shop host → verified site binding → tenant → publication capability → catalog.
Checkout document is Madar-controlled and excludes arbitrary builder scripts.
Provider → edge allowlist → controlled Tunnel/proxy → cryptographic signature →
MLE → validation/dedupe → financial transaction. Network headers alone prove none
of these identities. Customer connector agent uses outbound mutually authenticated
TLS and typed, allowlisted operations; no remote SQL interface.

## Prevention, detection, recovery and regression obligations

| Threat | Prevention | Detection | Recovery | Required regression |
| --- | --- | --- | --- | --- |
| BOLA/IDOR, cross-tenant access | Verified membership, tenant-filtered lookup and composite foreign keys | Non-PII denial metrics | Revoke compromised session, audit affected resources | Every role/verb against own and foreign tenant; foreign object 404 |
| BFLA, privilege escalation, plan/role confusion | Role ∩ capability ∩ resource/state; no owner plan bypass | Capability/admin denial counters | Revoke grant/session | Premium member denied admin; tenant admin denied unpaid features |
| Frontend-only enforcement, direct API bypass | Backend guard before cache/read/write | Route coverage inventory | Disable unsafe route through governed release | Route/API access without UI, no premium prefetch |
| Stale entitlement/role cache, tenant switch | Fresh resolution; revision + catalog version + role context; expiry boundary | Resolution failure/revision metrics | Invalidate generation, refresh client | Revoke/expire/switch then cached request denies |
| Unknown plan/capability, resolver failure | Deny unknowns and dependency failures | Dependency/ambiguity alerts | Repair canonical data through audited workflow | Malformed/unknown base plus active add-on grants nothing |
| Service-role RLS bypass, unsafe definer | Explicit backend ownership; backend-only grants; safe search_path | Catalog/grants inventory | Revoke excessive grants and forward-repair | Adversarial RPC tenant substitution, untrusted search_path |
| Stale/wrong-session AAL2 | Assurance derived from this request’s provider-verified session | Sensitive action denial/audit | Reauthenticate/revoke suspect sessions | AAL1 request while another session is AAL2, concurrency |
| Manual grant abuse, mass assignment | Platform admin AAL2, strict DTO, explicit reason and immutable references | Append-only audit and financial ledger | Correct/revoke by new event; preserve receipt | Tenant/admin impersonation denial, extra fields, underpayment reason |
| CSRF, spoofed Origin | Existing cookie origin + CSRF middleware; no browser exemption for financial writes | Origin/CSRF denial metrics | Revoke session if compromised | Missing/forged CSRF, foreign/null Origin |
| Stored XSS, checkout JS, malicious SVG | Controlled document CSP; no tenant scripts; content/MIME validation | CSP reports, content checks | Unpublish asset, restore sanitized version | HTML/script/SVG/iframe payloads cannot execute |
| SSRF, path traversal, credential exfiltration | Explicit connector targets, TLS verification, typed paths, existing ingestion guard | Rejected destinations/content | Disable connector, rotate credential | Loopback/link-local/redirect/file/metadata URL attacks |
| SQL injection, arbitrary external SQL | Parameterized values and quoted allowlisted identifiers; no SQL in protocol | Invalid mapping/schema events | Disable integration and restore approved mapping | SQL-like names/payloads remain data |
| Price/currency/subtotal manipulation, float/negative/huge quantity | Server quote, Decimal/NUMERIC or exact minor units; bounded strict integers | Quote mismatch/validation counters | Reject/requote, explicit financial correction | Client totals ignored; unsupported currency and quantity rejected |
| Overselling, stock race | Atomic reservation/update with sorted row locks; versioned inventory ledger | Reservation failures, negative-stock invariant | Idempotent release/expiry | Concurrent final-unit purchases produce one reservation |
| Checkout replay, duplicate order/payment | DB uniqueness for tenant + operation + key and request hash | Dedupe/conflict counters | Return original result; conflict for changed body | Concurrent same key/body and changed-body retry after restart |
| Payment timeout ambiguity | Persist attempt/reference before provider call; UNKNOWN on uncertain outcome | Reconciliation backlog/age | Query provider, never blindly retry charge | Remote success + lost response, duplicate callback |
| Fake/replayed/out-of-order webhook | Mandatory signature + MLE, bounded schema, unique event and state transition | Crypto failures/dedupes/invalid transitions | Quarantine, reconcile provider | Invalid signature/MLE; refunded cannot become captured |
| Wrong merchant MID, amount/currency | Backend merchant mapping from tenant and payment context; match captured facts | Mismatch alerts | Quarantine/reconcile; no automatic grant | Browser MID ignored; cross-tenant transaction/amount rejected |
| Refund abuse/over-refund | Role/ownership/step-up, captured remainder lock, idempotency | Refund audit/reconciliation | Explicit correction/provider reconciliation | Parallel partial refunds cannot exceed capture |
| PAN/CVV/transient token/PII/secret leakage | Never accept card data; ephemeral token only; allowlisted logging; protected secret references | Secret/log hygiene gates | Rotate compromised credentials, incident review | Logs/traces/errors/browser persistence omit sensitive tokens |
| Key expiration or shared meta-key compromise | Versioned secret references, expiry alerts, staged rotation, merchant kill switches | Per-key expiry/health | Rotate and reconcile affected merchants | Expired/unknown key fails closed, no cross-MID fallback |
| Migration divergence, missing DDL/sequences | One writer; ordered DDL and explicit parity/sequence synchronization | Functions/triggers/grants/RLS/count/hash parity | Retain source, abort cutover before write acceptance | Logical row copy without DDL/sequence proof is insufficient |
| CDC lag/conflict, slot WAL exhaustion | Table allowlist, replica identity, disk budget and bounded WAL retention | Lag bytes/time, inactive slot, retained WAL and disk alerts | Fence/abort/reinitialize safely; never skip conflicts blindly | Inactive slot, conflict and WAL pressure trip gates |
| Auth/JWT migration failure | Test users/hash/identity/MFA parity; explicit signing/session strategy | Login/refresh/AAL2 probes | Roll back before target writes, reauth per approved strategy | HS256/ES256, missing issuer/key, refresh/OAuth redirect tests |
| Storage metadata/object mismatch | S3 protocol copy; bucket/count/bytes/hash and active-reference parity | Missing active object alerts | Recopy/restore verified object; block cutover | Missing object/hash mismatch/private signed URL tests |
| Backup co-location/failure, false recovery proof | True off-host repo + offline/immutable layer; verified logical backup + PITR | Freshness/checksum/restore proof | Restore to isolated compatible stack | WAL recovery to chosen point and full object reconstruction |
| External duplicate event, lost ACK, crash after commit | Durable inbox/outbox + remote idempotency; refuse unsafe adapter | Duplicate/delivery/retry metrics | Replay same event identity | Remote commit followed by crash does not duplicate effect |
| Lost external update, both-side change | Explicit authority + base/current versions; persist manual conflicts | Conflict/drift metrics | Audited resolution with expected version | Concurrent edits and stale snapshots never silently overwrite |
| Sync loop | Origin/correlation/causation and no echo to same origin | Loop/dedupe counters | Quarantine looping integration | External→Madar→external echo terminates |
| Stale cursor, out-of-order events | Version/cursor checkpoint in apply transaction; per-aggregate ordering | Cursor age/sequence gap alerts | Reconcile/resnapshot | v6 then v5 cannot regress state |
| Tombstone resurrection, destructive delete | Versioned tombstones and explicit deletion authority/retention | Tombstone conflicts | Manual recovery policy | Delayed update cannot resurrect deletion |
| External-ID/mapping collision | Tenant/integration/entity-qualified identity and unique mapping | Collision audit | Disable mapping, resolve explicitly | Same external ID across integrations remains distinct |
| Source schema change, mapping drift | Fingerprint + payload/mapping versions; stop on incompatible change | Schema mismatch health | Approve revised mapping then replay | Missing/type-changed column never coerces silently to NULL |
| Sync queue poisoning/oversized malformed events | Strict versioned DTO, size bounds, allowlisted entities | Reject/dead-letter metrics | Quarantine and audited replay | Oversized/malformed/unknown entity rejects without mutation |
| Compromised worker/agent and tenant starvation | Least privilege scoped credentials; bounded per-tenant leases/timeouts/circuit breaker | Lag, retry, fairness and dead letters | Disable individual integration; rotate/reissue scope | One failing integration does not block another |
| Inventory sync overwrites local sales | Explicit ERP authority + reservations/deltas or CAS ledger | Stock/version reconciliation | Conflict workflow; preserve sale ledger | External snapshot concurrent with final stock sale |

## Recovery and authorization boundaries

Managed→self-host CDC is one-way migration only, never generic bidirectional sync.
The target cannot accept production writes until a separately authorized write
fence, final parity, sequence sync and configuration cutover. Rollback after target
writes needs a reviewed reverse data transfer; pointing at stale managed source
would lose writes. Physical recovery and Storage recovery are separate proofs.

Do not enable global commercial enforcement while any live tenant lacks an
approved mapping. No use of cash, payment webhooks or provider subscription status
as direct authorization: only a committed canonical access period may grant it.
Existing paid-order fulfillment/refunds survive commercial expiry through narrow
operational authority; this must never authorize new sales.

## Current test evidence

This document precedes implementation. The tables describe required tests, not
passing results. The accompanying final evidence report must distinguish each
executed check, untested component and blocked release gate.
