# Commercial access implementation — continuation

Status: implementation under validation on builder-backend; the commercial ledger now follows the mainline schema-098 commerce migrations as schema 099. This document supersedes the earlier unresolved plan-mapping notes, not their historical evidence.

## Canonical commercial contract

The user’s continuation explicitly assigns Reservations to Website, Business and Business Plus, and commerce to Business and Business Plus. Forms retains Forms, public form links, response management/overview, data import and standard analysis. Business Plus retains priority_support. The existing advertised CV reranker is represented explicitly. `commercial_catalog.py` owns 30 identifiers and the plan matrix; `generate_commercial_contract.py --check` prevents drift in the frontend generated representation. Add-ons remain explicit products, not new base-plan privileges.

`tenant_commercial_state` is initialized review_required for every existing/new tenant. No historical payment or plan is fabricated. Schema99 resolves one tenant snapshot through a single PostgreSQL statement. A GiST exclusion constraint prevents overlapping effective access ranges. Membership, role, capability, resource ownership and resource state remain independent checks. The platform-admin boundary remains independent of tenant commerce.

## Financial administration

Only request-verified platform administrators at AAL2 can access commercial administration. Browser mutations retain global CSRF/origin checks and independent admin/tenant rate limits. Strict DTOs reject actor, tenant, revision, expected-price and source mass assignment. The backend calculates expected USD minor units from the canonical price and billed months. Calendar-month periods and nonstandard amount/period overrides are explicit. Complimentary access has a separate source and no fake payment.

The database command atomically appends receipt, access period, entitlement event, revision and audit. It serializes commands for a tenant and fingerprints operation/actor/request. Same key and request return the original response after reconnect; changed payload conflicts. Catalog price changes do not break an already-recorded idempotent replay. Financial corrections append entries referencing the prior record. Revocation and supersession retain original period bounds and close their effective ranges. Runtime roles have SELECT-only grants on financial history and EXECUTE only on reviewed command/resolver functions. Security-definer search paths are empty, objects qualified, helper execution revoked.

Financial references use restrictive foreign keys. Deletion lifecycle guards reject tenant/account deletion before freezing or purging when financial retention review is required. This preserves both history and deletion transaction integrity; it does not invent a legal retention duration.

## Cache and request isolation

The authoritative resolver does not cache grants in Redis or the browser. Revision combines catalog version, database revision and effective-state digest; temporal transitions are calculated at each resolution. Ledger, legacy commercial and relevant setting changes bump the database revision. The frontend discards prior capabilities before a tenant switch, aborts stale requests/responses including refresh retries, and refreshes at effective-period transitions and focus. Capability-sensitive catalog caches include tenant, actor, role and revision, and authorization runs before cache access. Public commerce responses cannot be cached by browsers/CDNs. Public website responses require revalidation and disable CDN storage; each origin request resolves current entitlements.

Shared builder routes additionally authorize document changes. Forms saves may retain unchanged historical website content after downgrade, but cannot create/edit pages, site roles or site members. Form themes remain shared presentation data used by the existing Forms renderer. Reservation blocks require reservations even inside forms. Public website pages—including member pages—require website_publish, and public forms require public_form_links. A published binding never permits fallback access on resolver failure.

## Rollout and recovery

Schema 099 is an additive bridge compatible with schemas 081–099. Its release manifest carries the contiguous 096→097→098→099 chain because production has not yet applied the two intervening mainline migrations. Rollback to the retained pre-migration application is valid only before migration. The exact-SHA governed controller upgrade is required for the new release metadata. The isolated migration runner applies the paired tree, validates RLS/grants, exercises real SQL concurrency/idempotency, dumps/restores a synthetic financial ledger and verifies schema/index/history invariants. No production commercial-ledger migration has been run for this change.

Global COMMERCIAL_ENTITLEMENTS_ENFORCED remains disabled until every active production tenant has a deliberate reviewed state. Code readiness and global activation are separate. There are no CyberSource credentials, payment-provider calls, production database endpoint changes or customer connectors in this commercial change.

## Evidence and remaining release gates

Durable continuation evidence: `/home/madar/master-continuation-20260908`, `/home/madar/master-resume-20260909`, and `/home/madar/master-resume-20260914`. These protected directories contain separate safe result files and private synthetic credentials; never commit/copy credential files. The current schema-99 browser proof covers real password login, four-plan switching, denied API/route access, admin TOTP/AAL2, one cash receipt, replay without a second effect, refresh and logout. Independent SQL counts confirmed one current receipt/period/command/audit effect; an older September 9 audit row remains preserved as historical synthetic evidence.

The source remediation now separates terminal recipient/subscription outcomes from actionable platform/provider failures. Historical failures remain durable telemetry, thresholds are unchanged, and no row is deleted or relabeled. Production remains unchanged during this development session, so its previously degraded readiness is not claimed repaired until the candidate receives independent release review and governed deployment. Do not interpret this document as release acceptance.

### Resumed validation results

- Authoritative backend workflow at the current implementation head: 1427 tests, zero failures/errors, 14 explicitly skipped database tests executed separately; external attempts/sites empty.
- Complete focused notification suite: 126 tests passed; readiness subset: 39 tests passed. Terminal recipients do not poison readiness, while recent provider configuration/authentication failure and real queue failures remain operationally visible.
- Fresh PostgreSQL migration/ledger suite through schema 99: 14 tests, exact RLS/grants, SQL concurrency/idempotency and synthetic ledger dump/restore passed with zero invalid indexes.
- Frontend: 938 tests passed, 1 existing skip; lint, production API-origin build and shipped npm audit passed.
- Authenticated schema-99 browser: all four plans, tenant switching, direct API denials, admin MFA/AAL2, manual receipt, durable replay, refresh and logout passed with no console errors or external requests.
- Latest real backup `madar-20260909T021625Z`: isolated migration 93→94 passed, 78 public tables, four expected additions, 0 invalid indexes, 98 local files and 102 provider objects verified. Network disabled; temporary target removed; platform_recovery_proven=false.
- Pinned pip-audit 2.10.1 and the shipped npm audit report no known vulnerabilities. No approved image scanner is installed; image vulnerability scan is not claimed.
- All 52 direct/aliased privileged-client application files are classified and rechecked on 2026-09-14. Ordinary-user privileged paths retain explicit user, membership, tenant, resource, role and capability boundaries. Static inventory is an additional completeness gate, not proof that RLS constrains service-role access.

Safe current result files live under `/home/madar/master-resume-20260914`; previous evidence remains unchanged.

### Calendar privacy audit follow-up

Calendar bootstrap previously cached private event payloads in each backend process for15 seconds. Permission changes handled by a different process could not invalidate that copy. Bootstrap now rebuilds from current calendar membership and event visibility on each request, retaining no-store HTTP semantics. This adds database reads; a future cache would need a durable permission/data revision before reuse. Route-coverage tests now include every calendar and shared website-settings endpoint. Focused60 authorization/calendar tests and the full backend workflow passed in `backend-calendar`; no external attempts/sites.
