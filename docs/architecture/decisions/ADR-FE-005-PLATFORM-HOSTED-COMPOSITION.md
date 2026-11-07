# MADAR Frontend Architecture Decision Record

**ADR ID:** ADR-FE-005
**Title:** Establish Platform-Owned Hosted Composition with Product-Owned Runtime Adapters
**Status:** APPROVED — LOGICAL ARCHITECTURE ONLY
**Decision owner:** Madar product owner
**Affected business domains:** Platform Hosted Composition, Website Runtime, E-learning / Academy, E-commerce / Storefront, Shared Page Builder, Platform Shared Forms
**Affected technical modules:** Hosted frontend entry, hosted routes, tenant runtime preload, website runtime, Academy runtime, Storefront runtime, public API adapters, hosted styles and bundle audits
**Prepared:** 2026-11-06
**Product-owner approval:** FINAL ADR DOCUMENT APPROVED — LOGICAL ARCHITECTURE ONLY
**Logical direction approval date:** 2026-11-06
**Final ADR document approval:** APPROVED
**Final ADR document approval date:** 2026-11-06
**Implementation authorization:** NOT AUTHORIZED
**Repository-wide adoption:** PENDING INDEPENDENT REVIEW AND AUTHORIZED MERGE
**Technical maintainer:** PENDING OWNER DECISION
**Re-evaluation triggers:** New hosted product integration; route precedence changes; cross-product visitor authentication; independent deployment requirements; third-party hosted extensions; material hosted bundle isolation changes
**Constitutional impact:** None proposed

Only the Madar product owner may mark this ADR `APPROVED`. The product owner approved the logical architectural direction and this complete ADR document on 2026-11-06. This approval is architectural only; it does not authorize implementation or waive security, tenant authorization, QA, CI, migration, deployment, or production-release requirements.

## Context and evidence

### Verified current state

- `web/frontend/src/main.jsx:1-18` selects `tenantMain.jsx` for recognized branded tenant hostnames and `appMain.jsx` otherwise. The hosted and portal entry graphs are therefore distinct.
- `web/frontend/src/tenantMain.jsx:1-93` initializes hosted localization, hosted styles, browser routing, route preloading, and `TenantSiteRoutes`.
- `web/frontend/src/routes/TenantSiteRoutes.jsx:58-81` lazy-loads or preloads website, Academy, learner, Storefront, and preview runtimes. Its ordered route declarations at `web/frontend/src/routes/TenantSiteRoutes.jsx:139-164` place Academy, learner, Storefront, and standalone-form routes before the catch-all website route.
- `web/frontend/src/utils/hostedAddress.js:1-63` recognizes branded subdomains, excludes reserved labels, and creates canonical hosted URLs. FastAPI independently verifies hosted identity, trusted forwarded-host handling, and host/path consistency in `web/backend/services/hosted_address_service.py:53-123`.
- `web/frontend/src/tenantRuntimePreload.js:17-148` provides product-aware loading for websites, standalone forms, and Storefront. Academy and learner paths are currently excluded from that primary-read preload classification.
- `web/frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.jsx:1-75` composes Shared Page Builder rendering, routing, themes, forms, and reservations for published websites and standalone website forms. Its runtime and protected-page reads validate publication boundaries before presenting content (`web/frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.jsx:868-989`, `web/frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.jsx:1136-1171`).
- `web/frontend/src/components/ELearning/ELearningAcademy.jsx:1-111` owns the Academy-facing runtime flow while consuming supported Page Builder presentation concepts. It also currently reaches some portal/admin-oriented implementations; this is legacy implementation evidence, not a declaration that those imports are hosted-safe public contracts.
- `web/frontend/src/components/EcommerceStore/EcommerceStorefront.jsx:1-32` and `web/frontend/src/services/ecommerceApi.js:392-429` implement the Storefront-facing runtime and public service calls. The service currently imports Dashboard Builder cache utilities; that dependency is existing implementation, not an approved hosted contract.
- `web/frontend/src/components/PageBuilder/services/PageBuilder.publicApi.js:1-250` implements public website, form, visitor, quiz, reservation, and protected-page transport. `web/frontend/src/utils/apiClient.js:137-220` supplies shared credential, CSRF, and token-refresh behavior.
- FastAPI validates published snapshots and tenant ownership in `web/backend/routes/public_site_routes.py:282-351`, filters public publication data in `web/backend/routes/public_site_routes.py:635-730`, resolves hosted runtime state and commercial availability in `web/backend/routes/public_site_routes.py:4322-4535`, and separately enforces protected-page, form, Storefront, Academy, and reservation rules.
- `web/frontend/scripts/check-public-tenant-bundle.mjs:10-48` preserves an existing tenant-entry and website-runtime bundle audit. It does not establish independent Academy or Storefront dynamic-graph budgets.

### Interpretation

Madar already has a platform-like hosted composition point: one hosted entry initializes shared concerns and an ordered router selects product runtimes. That behavior is not yet documented as an owned public contract. Product runtimes also contain direct cross-feature imports whose intended long-term status has not been individually classified.

### Decision pressure

Adding hosted SaaS products must not make Website Builder the owner of unrelated product behavior, duplicate common hostname and bootstrap responsibilities in every product, or weaken FastAPI's authority. At the same time, existing routes, published content, product runtimes, and legacy dependencies must remain supported until separately reviewed.

## Decision

The Madar product owner approved **Platform Hosted Composition with product-owned runtime adapters** as the intended logical ownership model on 2026-11-06 and approved this complete ADR wording on the same date. This approval is architectural only; implementation remains not authorized.

Platform Hosted Composition will own:

- hosted frontend entry selection;
- frontend hostname interpretation and canonical-routing integration, subordinate to backend verification;
- hosted route namespace governance, ordering, precedence, collision review and arbitration, composition of product-owned route entries, and compatibility of existing public URLs;
- composition of first-party product runtimes;
- shared hosted bootstrap and localization initialization;
- hosted-safe interface contracts;
- generic loading, lazy-load failure, and error boundaries;
- cross-product hosted integration rules; and
- hosted dependency and bundle safeguards.

This is a logical ownership decision. It does not create an implementation, export, registry, package, runtime framework, or physical directory boundary.

### Product runtime ownership

Each hosted product owns its product-specific route declarations, route behavior, business workflows, runtime components, and corresponding backend operations, subject to the FastAPI authority described below. Platform Hosted Composition owns their ordered integration and route arbitration, not their business meaning.

**Website Runtime** owns published website presentation, website-specific runtime behavior, integration with Shared Page Builder, and website-specific public interactions.

Website Runtime may present approved Reservations capabilities, but Reservations owns booking and availability semantics, and FastAPI remains authoritative for capacity, validation, persistence, status transitions, and cancellation.

**E-learning / Academy Runtime** owns Academy and learner experiences, learning-specific pages and workflows, Academy data and actions, supported Page Builder integration, and learning API adapters.

**E-commerce / Storefront Runtime** owns product browsing, cart, checkout and order presentation, Storefront-specific interactions, and commerce API adapters.

Approved shared capabilities, including Shared Page Builder and Platform Shared Forms, may serve hosted products through reviewed hosted-safe interfaces. Themes, media, transport, localization, and shared UI may do so only where their ownership and supported hosted contracts have been separately established.

### FastAPI authority

FastAPI remains authoritative for tenant and hosted-site resolution, authentication, authorization, commercial entitlements, resource access, public-data filtering, publication validation, product business operations, persistence, and tenant isolation.

Frontend routes, adapter metadata, product identity, loading state, navigation visibility, or commercial-display metadata must never grant backend access or replace authoritative server checks.

Any future change to backend service ownership or authorization architecture requires its own ADR, security review, compatibility validation, and explicit product-owner approval.

## Proposed first-party hosted adapter contract

The following is a **PROPOSED CONTRACT SHAPE**. No names below are claimed as existing exports, and this ADR does not authorize their implementation.

Each first-party hosted product adapter would document:

| Contract field | Required meaning |
|---|---|
| Product identity | Stable technical identity and accountable product/domain owner; not a permission or commercial entitlement |
| Owned routes | Exact route patterns, parameters, precedence needs, reserved-path interactions, and legacy URL obligations |
| Lazy entry | Product-owned hosted entry component and lazy-load boundary |
| Bootstrap context | Only the tenant-host, locale, direction, theme, and public session context that the adapter actually requires |
| Locale and direction | Supported Arabic/English behavior, RTL/LTR behavior, and translation namespaces |
| Theme requirements | Supported shared tokens, product theme inputs, authored-theme isolation, and cleanup responsibilities |
| Loading and failure | Product loading UI, lazy-load recovery, unavailable state, backend-error behavior, and isolation from sibling products |
| Access mode | Public, anonymous-visitor, authenticated-visitor, learner, customer, or protected-resource modes, without granting authorization |
| Backend ownership | Product-owned FastAPI APIs and authoritative checks relied upon by the runtime |
| Hosted-safe dependencies | Reviewed public/shared interfaces permitted in the hosted graph |
| Compatibility evidence | Relevant routing, publication, API, theme, RTL, accessibility, responsive, bundle, and authorization tests |

An adapter may describe how the frontend consumes an entitlement or access response. It must not calculate authoritative access, infer unrestricted access from missing metadata, or become a commercial-entitlement engine.

## Route ownership and compatibility

The approved route policy is:

1. Current hosted URLs, canonical-host behavior, and legacy redirects remain supported.
2. Current route precedence remains the compatibility baseline: specific product routes are evaluated before the website catch-all.
3. A new hosted product must declare its complete route patterns and path parameters before integration.
4. Review must compare new patterns with existing product routes, reserved system paths, legacy redirects, form paths, and the website catch-all.
5. A catch-all website route must not silently absorb or override an approved product-specific route.
6. Reserved system paths and their owner must be documented before enforcement is introduced.
7. Existing published URLs must not change without a separate compatibility decision covering redirects, historical content, and consumers.
8. No runtime registry or automatic module discovery is introduced by this ADR. The existing explicit route composition may remain until a separately approved need and design exist.

Automated route-collision validation is a future implementation proposal, not a current guarantee. Route metadata must never substitute for FastAPI authorization or product availability checks.

## Dependency boundaries

For new and materially modified hosted code, a product should consume only:

- approved Platform Hosted Composition contracts;
- relevant shared runtime capabilities through their supported interfaces;
- the product's own public or hosted adapters; and
- hosted-safe localization, design-token, media, transport, and UI primitives.

New hosted-product dependencies must not target:

- `App.jsx` or concrete portal-shell internals;
- `AdminRoutes`;
- Dashboard administrative state or private cache implementations;
- Page Builder workspace/editor private implementation;
- unrelated product-private implementations;
- portal-only CSS; or
- authenticated admin API adapters.

Static imports, dynamic imports, transitive dependencies, and CSS imports are all part of the hosted dependency graph and must be considered in review.

Existing direct dependencies remain supported until each is classified as an intentional shared contract, an adapter candidate, a governed exception, or a legacy dependency to retain. Their existence is not, by itself, a defect and does not force unrelated remediation during a routine bug fix.

## Visitor-session and security boundaries

Hosted products do not necessarily share identical identity or authorization semantics:

- an anonymous website visitor may access only backend-authorized public publication data;
- an authenticated site visitor may access only resources authorized for that visitor and tenant;
- an Academy learner remains subject to Academy membership, capability, and tenant checks;
- a Storefront customer remains subject to Storefront customer, tenant, order, and confirmation rules; and
- protected website content remains subject to server-side membership and resource authorization.

Frontend storage and caches must be scoped to the relevant tenant/site/product/session contract and cleared or invalidated according to that contract. A shared hostname or browser session does not prove that products may share identity, credentials, profile data, or authorization state.

Any future cross-product visitor-session contract requires a separate product decision, security review, explicit identity and logout semantics, tenant-isolation analysis, compatibility validation, and product-owner approval.

## Failure and compatibility contracts

Hosted UI may present product-specific states, but the server remains authoritative for the reason and allowed response. Future adapter reviews must cover:

- unavailable or disabled hosted products;
- missing, inactive, or unpublished sites;
- protected resources and authentication-required responses;
- expired or missing commercial entitlements;
- operational dependency failures;
- lazy-load and chunk failures;
- backend validation and service errors;
- tenant, host, site, or publication mismatch;
- legacy published URLs and redirects; and
- Shared Page Builder schema and renderer compatibility.

A generic frontend error boundary may isolate presentation failure. It must not transform an authorization denial into public access, conceal a tenant mismatch as successful content, or reinterpret an entitlement decision.

Changes to Shared Page Builder contracts must preserve or explicitly govern editor, preview, published website, hosted runtime, and Academy compatibility. Historical schemas, routes, identifiers, themes, forms, and authored content remain subject to their existing compatibility requirements.

## CSS, theme, bundle, and experience safeguards

Existing tenant-entry and public-runtime audits remain in force. Future implementation reviews should add proportionate evidence for:

1. hosted-versus-portal dependency separation;
2. Academy dynamic import and CSS graphs;
3. Storefront dynamic import and CSS graphs;
4. published website runtime dependencies;
5. portal-only CSS leakage;
6. ownership and stability of shared design tokens;
7. tenant-authored theme isolation and cleanup;
8. Arabic/English and RTL/LTR rendering;
9. keyboard access, accessibility, responsive behavior, and supported browsers; and
10. per-product loading and error isolation.

No bundle size has been measured in preparing this ADR, and no new budget is approved here. New automated audits, budgets, or forbidden-import enforcement require separate implementation approval, an accountable maintainer, and a baseline that rejects new violations without treating all known legacy dependencies as newly introduced failures.

## Alternatives considered

### Option A — Website Builder owns all hosted composition

Rejected as the intended long-term ownership model. Website Builder currently supplies important published-runtime capabilities, but Academy and Storefront own different product workflows, APIs, and access semantics. Treating Website Builder as their owner would conflate website authoring with unrelated hosted products.

### Option B — Each product owns a fully independent hosted entry and composition

Not selected. It could increase product autonomy but would duplicate hostname interpretation, canonical routing, localization bootstrap, shared loading behavior, and route-conflict handling without a demonstrated independent deployment requirement.

### Option C — Platform Hosted Composition with product-owned runtime adapters

Selected and approved as the logical direction. It preserves shared entry/composition responsibilities while keeping product behavior, API adapters, and business rules with their product owners. The complete ADR wording is approved; repository-wide adoption remains pending independent review and authorized merge.

## Consequences and Trade-offs

- A coordinated frontend build and deployment lifecycle remains the default.
- Central hosted route composition requires shared ownership and coordination.
- Changes to shared capabilities may affect multiple hosted product runtimes.
- Hosted-safe adapters and public contracts require ongoing maintenance and review.
- Legacy cross-product dependencies must be classified before replacement.
- Visitor-session semantics remain product- and security-sensitive.
- CSS, localization, and bundle isolation require explicit ongoing verification.
- Error and failure boundaries do not provide full independent application or deployment isolation.

These trade-offs do not authorize micro-frontends, separate frontend deployments, module federation, universal registries, runtime plugins, or physical source restructuring.

## Ownership and consumers

| Capability | Accountable owner in the approved logical architecture | Known consumers | Status |
|---|---|---|---|
| Hosted entry, route composition, collision policy, shared bootstrap | Platform Hosted Composition | Website, Forms, Academy, learner runtime, Storefront, future hosted products | Approved logical architecture; implementation not authorized |
| Published website presentation and interactions | Website Runtime | Public visitors and authenticated site visitors | Existing implementation; formal adapter proposed |
| Academy and learner runtime | E-learning / Academy | Public visitors, learners, instructors/preview users | Existing implementation; formal adapter proposed |
| Storefront runtime | E-commerce / Storefront | Shoppers and authenticated customers | Existing implementation; formal adapter proposed |
| Reusable rendering/schema/layout/theme compatibility | Platform Shared Page Builder | Website, Academy, preview and hosted consumers | Existing shared direction; no new interface approved here |
| Generic reusable form contracts | Platform Shared Forms | Website Forms, E-learning Forms, future approved consumers | Existing logical decision; staged implementation remains separate |
| Hosted identity and access authority | FastAPI | All hosted products | Existing backend authority |

Accountable technical maintainers remain `PENDING OWNER DECISION`.

## Commercial and lifecycle impact

This ADR does not decide subscriptions, product packaging, entitlement identifiers, launch status, navigation visibility, or independent deployment. E-learning and Analytics remain products under development; current routes or capability flags are not declarations of final commercial packaging.

A hosted adapter may report the backend contract it consumes. It must not make a product commercially available or infer access when an entitlement policy is unresolved.

## Implementation and dependency impact

Implementation is **NOT AUTHORIZED**. Approval of this ADR does not authorize source moves, new adapters, route changes, new exports, CSS changes, dependency installation, API or schema work, CI changes, migration, or deployment.

Any future implementation must preserve a reviewed legacy baseline, change incrementally, and follow the root `AGENTS.md` lifecycle and applicable constitution, security, QA, CI, migration, deployment, and release contracts.

## Non-goals and exclusions

This ADR does **not** authorize:

- new frontend runtime infrastructure;
- physical source relocation;
- new dependencies;
- module federation or micro-frontends;
- third-party runtime plugins;
- automatic module discovery or a runtime registry;
- independent frontend deployments;
- tenant identity or authorization changes;
- shared visitor-login behavior;
- backend API, schema, persistence, or entitlement changes;
- commercial packaging decisions;
- breaking hosted-route changes; or
- application migration.

## QA, CI, and release impact

No application tests, builds, servers, migrations, or deployments were executed for this documentation-only ADR.

Existing evidence includes:

- `web/frontend/src/tenantEntry.test.js` for portal/hosted entry separation and stylesheet expectations;
- `web/frontend/src/tenantRuntimePreload.test.js` for site, form, Storefront, Academy, and learner route classification and preload behavior;
- `web/frontend/src/routes/TenantSiteRoutes.preload.test.jsx` and `TenantSiteRoutes.storefront.test.jsx` for route loading and Storefront composition;
- `web/frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.routing.test.jsx` and `TenantSiteRuntime.flow.test.js` for published website routing and runtime behavior;
- `web/frontend/src/components/ELearning/ELearningAcademy.test.jsx` for Academy runtime behavior;
- `web/frontend/src/components/EcommerceStore/EcommerceStorefront.test.jsx` and `EcommerceStorefront.styles.test.js` for Storefront behavior and style contracts;
- `web/frontend/src/utils/hostedAddress.test.js` and `web/backend/tests/test_hosted_address_service.py` for hosted-address rules;
- `web/frontend/src/components/PageBuilder/core/PageBuilder.theme.test.js` and `web/frontend/scripts/check-theme-contract.mjs` for Page Builder theme contracts;
- `web/backend/tests/test_public_site_runtime.py` and `test_website_routes.py` for public website/runtime behavior;
- `web/backend/tests/test_elearning_academy.py` and `test_elearning_academy_database.py` for Academy access and data behavior;
- `web/backend/tests/test_ecommerce_authorization.py` and `test_ecommerce_routes.py` for Storefront authorization and routes; and
- `web/frontend/scripts/check-public-tenant-bundle.mjs` for the existing tenant entry and website public-runtime graph audit.

These files are evidence of existing coverage only. They were not executed in this phase and are not reported as passing.

- **Existing architecture checks:** Hosted entry, address, route, runtime, theme, product, backend access, and website bundle checks listed above; complete Academy and Storefront graph enforcement is not claimed.
- **Proposed architecture checks:** Route-collision validation, hosted-safe import rules, Academy/Storefront dynamic-graph audits, portal-CSS leakage checks, and per-product failure isolation. Each requires separate implementation approval and a legacy baseline.
- **Accountable CI enforcement owner:** PENDING OWNER DECISION
- **Planned verification milestones:** PENDING OWNER DECISION
- **Review trigger/date:** The re-evaluation triggers in this ADR; no calendar review date approved

All existing root `AGENTS.md`, constitution, security, tenant-authorization, QA, CI, migration, deployment, and production-release requirements remain unchanged and take precedence as defined by the constitution.

## Rollback, migration, and failure handling

There is no runtime rollback, data migration, or deployment because implementation is not authorized. This approved ADR may be superseded only through the governed ADR process.

Any later implementation must define incremental rollback, lazy-load failure behavior, partial product availability, legacy URL preservation, cache/session cleanup, compatibility with published content, and recovery behavior before release. This ADR grants no production-mutation authority.

## Risks and unresolved questions

- Accountable technical maintainer for Platform Hosted Composition: `PENDING OWNER DECISION`.
- Authoritative reserved hosted paths and the owner of that list: `PENDING OWNER DECISION`.
- Intended cross-product visitor identity, login, logout, and session-sharing semantics: unresolved and excluded from this decision.
- Whether current Academy and Storefront portal/admin dependencies become hosted-safe contracts or adapter candidates: unresolved pending individual classification.
- Whether Academy should participate in the current primary-read preload mechanism: unresolved.
- Academy and Storefront bundle budgets, baseline, milestones, and enforcement owner: `PENDING OWNER DECISION`.
- Exact physical location and names of any future hosted adapter interfaces: not approved.
- Custom-domain scope beyond the inspected branded-subdomain behavior: not established by this ADR.
- Theme-contract ownership where product-specific themes and tenant-authored output intersect: requires contract-level review.
- Threshold for reconsidering an explicit build-time registry, independent frontend deployment, or third-party extension model: no decision; each re-evaluation trigger requires separate evidence and approval.

## Approval record

### Logical direction approval history

- **Owner decision:** On 2026-11-06, the Madar product owner approved Platform-Owned Hosted Composition with Product-Owned Runtime Adapters as the logical architectural direction.
- **Approved principles:** Platform ownership of common hosted composition; product ownership of individual hosted runtimes; separate portal and hosted entry boundaries; backend-authoritative tenant identity, access, and entitlements; compatibility-preserving staged evolution; no automatic dynamic module registry; no automatic micro-frontends; and no assumption of independent deployment.
- **Explicit limitations:** No implementation, migration, route change, Git release action, or deployment was authorized by the logical-direction approval.

- **Product-owner decision:** FINAL ADR DOCUMENT APPROVED — LOGICAL ARCHITECTURE ONLY
- **Logical direction decision date:** 2026-11-06
- **Approved logical scope:** Platform-Owned Hosted Composition with Product-Owned Runtime Adapters and the principles recorded above
- **Final document decision:** APPROVED
- **Final document approval date:** 2026-11-06
- **Conditions:** Implementation remains unauthorized; repository-wide adoption remains pending independent review and authorized merge
- **Implementation authorization:** NOT AUTHORIZED
- **Related exception IDs:** None
- **Related constitutional amendment:** None
- **Supersedes / superseded by:** None

### Final document approval history

- **Approval event:** FINAL DOCUMENT APPROVAL
- **Approval authority:** Madar product owner
- **Approval date:** 2026-11-06
- **Approved document:** ADR-FE-005, incorporating Phase 25.2C corrections F-01 through F-06
- **Approved scope:** Logical ownership of Platform Hosted Composition with product-owned hosted runtime adapters, route governance responsibilities, dependency boundaries, compatibility obligations, architectural trade-offs, and non-goals
- **Implementation:** NOT AUTHORIZED
- **Repository-wide adoption:** PENDING INDEPENDENT REVIEW AND AUTHORIZED MERGE
