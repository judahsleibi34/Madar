# MADAR Frontend Architecture Decision Record

**ADR ID:** ADR-FE-006
**Title:** Documentation-First First-Party Module Ownership and Explicit Composition
**Status:** APPROVED — LOGICAL ARCHITECTURE ONLY
**Decision owner:** Madar product owner
**Affected business domains:** All major frontend product domains and shared platform capabilities
**Affected technical modules:** Portal composition, hosted composition, product route entries, navigation, localization, shared capability contracts, product API adapters, module ownership documentation, and future architecture checks
**Prepared:** 2026-11-06
**Product-owner approval:** FINAL ADR DOCUMENT APPROVED — LOGICAL ARCHITECTURE ONLY
**Logical architecture:** APPROVED
**Selected direction:** OPTION B — DOCUMENTATION-FIRST, MANUAL FIRST-PARTY COMPOSITION
**Logical decision date:** 2026-11-06
**Final ADR document approval:** APPROVED
**Final ADR document approval date:** 2026-11-06
**Implementation authorization:** NOT AUTHORIZED
**Repository-wide adoption:** PENDING INDEPENDENT REVIEW AND AUTHORIZED MERGE
**Technical maintainer:** PENDING OWNER DECISION
**Re-evaluation triggers:** Demonstrated repeated composition errors; approved metadata validator need; route-collision automation need; material module-count or team-scaling change; third-party extension proposal; independent deployment proposal
**Constitutional impact:** None proposed

Only the Madar product owner may mark this complete ADR document `APPROVED`. The product owner approved Phase 25 Option B—documentation-first, manual first-party composition—as the logical architectural direction on 2026-11-06 and separately approved the final corrected wording of this ADR on the same date. Final document approval is for logical architecture only and does not authorize implementation or waive security, tenant authorization, QA, CI, migration, deployment, or production-release requirements.

## Context and evidence

### Verified current state

- The Frontend Architecture Constitution defines technical modules, commercial modules, shared platform capabilities, public contracts, and private implementation as distinct concepts (`docs/architecture/MADAR_FRONTEND_ARCHITECTURE_CONSTITUTION.md:38-49`). It requires explicit ownership and public surfaces for new first-party products while stating that no general frontend module registry currently exists (`docs/architecture/MADAR_FRONTEND_ARCHITECTURE_CONSTITUTION.md:63`, `144-163`).
- Portal composition is explicit in source. `web/frontend/src/App.jsx:50-52` declares lazy route groups, and `web/frontend/src/App.jsx:679-733` manually selects tenant, admin, user-workspace, or public route composition. `web/frontend/src/routes/AdminRoutes.jsx:54-160` declares product routes directly.
- Portal preload integration is a manually maintained route-to-loader list in `web/frontend/src/routes/routePreload.js:3-40`. Route constants are separately maintained in `web/frontend/src/config/routes.js:17-55`, and dashboard navigation groups are assembled in `web/frontend/src/components/DashboardBuilder/DashboardSidebar.jsx:158-220`.
- Portal and hosted delivery use different entry graphs: `web/frontend/src/main.jsx:8-18` selects `tenantMain.jsx` for recognized tenant hosts and `appMain.jsx` otherwise.
- Hosted composition is also explicit. `web/frontend/src/routes/TenantSiteRoutes.jsx:139-160` orders Academy, learner, Storefront, Forms, and website catch-all routes, while `web/frontend/src/tenantRuntimePreload.js:17-49` contains a small explicit hosted route-loader and translation map.
- ADR-FE-005 assigns shared hosted entry and route governance to Platform Hosted Composition while leaving product route declarations and runtime behavior with product owners (`docs/architecture/decisions/ADR-FE-005-PLATFORM-HOSTED-COMPOSITION.md:45-88`, `107-144`). It does not create a hosted adapter implementation or registry.
- Existing approved logical ownership decisions keep Platform Shared Forms separate from Website and E-learning persistence, Data Analysis separate from Business Intelligence, and Reservations separate from Calendar / Planning (`docs/architecture/decisions/ADR-FE-002-PLATFORM-SHARED-FORMS.md:43-105`; `ADR-FE-003-SHARED-DATA-ANALYTICS-AND-BI.md:45-104`; `ADR-FE-004-RESERVATIONS-CALENDAR-OWNERSHIP.md:47-106`).
- Commercial packaging is backend-defined and does not mirror the complete frontend domain map. The authoritative catalog currently defines core commercial module IDs and separate capabilities in `web/backend/services/commercial_catalog.py:1-68`, while server entitlement evaluation is implemented separately in `web/backend/services/entitlement_service.py:1-38` and `336-488`.
- Targeted inspection found explicit route, navigation, preload, capability, and commercial mechanisms rather than one universal first-party code registry. This is evidence of current implementation, not proof that no registry-like mechanism can exist anywhere outside the inspected scope.

### Interpretation

Madar already behaves as a coordinated modular monolith, but ownership and integration knowledge is distributed across source, ADRs, tests, and backend contracts. A universal registry is not required to document ownership or make existing manual composition reviewable. Domain-specific extension systems also carry different schema, persistence, rendering, and compatibility obligations and should not be collapsed into a single module identity mechanism.

### Decision pressure

Future SaaS growth needs compact, human-readable ownership and contract guidance without making unrelated products own each other's internals, treating frontend metadata as authorization, eagerly importing every product, or prematurely introducing a universal registration framework.

## Decision

The Madar product owner approved **Option B — documentation-first, manual first-party composition** as the logical direction on 2026-11-06.

Madar uses a modular monolith with explicit first-party domain boundaries. Each major product domain and shared platform capability will have a stable technical identity and lightweight ownership documentation describing:

- owning domain and accountable maintainer when assigned;
- purpose, scope, and canonical technical lifecycle;
- supported public interfaces and private implementation boundaries;
- declared dependencies and integration points;
- backend authority and security references;
- compatibility responsibilities; and
- relevant QA ownership and evidence.

Portal and hosted composition remain separate, explicit, and manually maintained by their appropriate composition owners. This decision does not require every component, helper, hook, utility, route file, or internal service to become a separately registered architectural module.

No universal first-party code registry, automatic module discovery, runtime plugin infrastructure, module federation, or automatic composition mechanism is approved. Specialized build-time registration may be reconsidered only for a demonstrated concrete need, with compatibility evidence, security review where applicable, and separate product-owner approval.

## Module classification

The following categories are intentionally distinct and are not forced into one descriptor or registry:

| Category | Meaning | Current or representative examples | Governance boundary |
|---|---|---|---|
| **Platform shared capability** | Reusable capability with one accountable contract owner and multiple approved consumers | Shared Page Builder, Platform Shared Forms, Shared Data and Deterministic Analytics, Platform Hosted Composition | Owns shared contracts and compatibility, not consumer business workflows |
| **Product domain** | Business capability owning its workflows, data meaning, product adapters, state, and tests | Website, E-learning / Academy, E-commerce, Data Analysis, Business Intelligence, Reservations, Calendar / Planning | Must not absorb unrelated product internals merely because composition is shared |
| **Hosted product adapter** | Explicit boundary between Platform Hosted Composition and a product-owned hosted experience | Future formal Website, Academy, learner, or Storefront adapter contracts | Logical/proposed unless an actual supported interface is separately implemented and approved |
| **Presentation or content extension** | Domain-specific extension with schema, authoring, rendering, and persisted compatibility responsibilities | Page Builder blocks, Shared Forms fields, Academy content elements | Identity and compatibility belong to the relevant extension owner; not a SaaS-product registry entry |
| **Commercial product or capability** | Backend-authoritative packaging, subscription, entitlement, or operational access concept | Catalog module IDs, capabilities, add-ons, entitlement responses | Does not determine technical source ownership or frontend authorization |
| **Private implementation module** | Internal product code that is not a supported cross-domain contract | Product components, hooks, helpers, local state and private services | Does not require independent architecture registration solely because it is importable |

## Proposed `MODULE.md` ownership contract

The following is a **PROPOSED DOCUMENT CONTRACT**, not an implemented file layout or approved automation format. Major product domains and shared platform capabilities should eventually have a compact `MODULE.md` or approved equivalent. Smaller domains may use proportionately smaller documents.

### Identity

- stable technical ID and display name;
- module category and owning domain;
- technical maintainer or `PENDING OWNER DECISION`;
- canonical lifecycle; and
- purpose, scope, and explicit non-goals.

### Boundaries

- supported public entry points;
- private implementation locations;
- allowed dependencies;
- provided and consumed capabilities;
- known legacy coupling; and
- applicable ADRs and approved exceptions.

Each documented entry point must distinguish these descriptive categories:

- **EXISTING SUPPORTED CONTRACT:** Verified to exist and intended for supported consumers.
- **PROPOSED — NOT IMPLEMENTED:** A future contract shape or API proposal; it must not be presented as an existing export.
- **LEGACY / UNCLASSIFIED:** Existing implementation without a verified public-support contract. An importable internal file is not automatically a public API.

These categories do not create a runtime registry or an enforced machine-readable metadata schema and do not require immediate replacement of legacy imports.

A new or changed public interface must identify its owning domain and affected consumers and receive proportionate compatibility review and relevant test coverage before it is described as supported. For a new or materially changed interface, review should account for known direct consumers, relevant known transitive consumers, portal and hosted entry graphs, persisted or published schemas, Shared Page Builder / Forms integration, existing runtime behavior, security boundaries, and appropriate QA and regression coverage. Review scope must be proportionate to the actual change; application implementation requires separate authorization.

### Integration

- portal routes, navigation, preloads, and localization;
- hosted routes or adapter relationship where applicable;
- Shared Page Builder and Platform Shared Forms integration where applicable;
- backend API ownership;
- styling, theme, and authored-output boundaries; and
- browser state, cache scope, and cleanup responsibilities.

### Security and access

- verified backend access requirements;
- tenant, resource, role, membership, ownership, HTTP-method, operation, publication, visitor, commercial, and operational dependencies where applicable;
- unresolved authorization questions; and
- verified commercial relationship, if one exists.

Frontend access metadata uses only these evidence states:

| State | Meaning |
|---|---|
| `VERIFIED_REQUIRED` | A specific backend path proves the requirement |
| `BACKEND_PROVEN_NONE` | Specific backend-path evidence proves no such requirement for the recorded operation |
| `UNRESOLVED` | Evidence is absent, incomplete, conditional, or conflicting |

Missing evidence is `UNRESOLVED`, never an empty permission list or implied unrestricted access. Frontend documentation may describe backend contracts but cannot grant access, calculate authoritative entitlements, or replace FastAPI checks.

### Quality and compatibility

- relevant unit, integration, browser, tenant/security, accessibility, RTL, performance, and release checks;
- existing CI and static audits;
- published or persisted compatibility surfaces;
- known regression risks; and
- files or contracts requiring special review.

Ownership documents should link to authoritative backend, schema, ADR, and test contracts rather than duplicating their full implementation logic. No `MODULE.md` is created or approved for implementation by this ADR.

The owning product domain or shared-capability owner is accountable for keeping its ownership document aligned with supported contracts, dependencies, integration points, and tests. An individual technical maintainer remains `PENDING OWNER DECISION` until explicitly assigned. Review the ownership document when relevant public contracts or integration behavior change, in proportion to the significance of the change; trivial internal edits that leave those documented responsibilities unchanged do not require a documentation update.

## Technical and commercial separation

One technical domain is not necessarily one commercial product. A technical domain may exist before commercial release, independent subscription, final entitlement design, public hosted exposure, or production activation.

This ADR does not assume that:

- one source module equals one SKU;
- one domain equals one backend router;
- one domain equals one permission identifier;
- one technical module equals one database schema; or
- route or navigation visibility implies authorization.

Commercial catalog entries and technical ownership may map many-to-many. FastAPI remains authoritative for tenant identity, authentication, authorization, resource ownership, commercial entitlements, publication, persistence, and business operations. Frontend module identity, lifecycle, visibility, or metadata cannot grant backend access.

## Technical lifecycle policy

The only canonical technical lifecycle identifiers are those established by Constitution v0.2.1:

- `experimental`
- `under-development`
- `released`
- `deprecated`

Technical lifecycle is separate from commercial catalog status, subscription status, operational availability, tenant entitlements, release readiness, active migrations, and route visibility. This ADR creates no lifecycle state machine.

E-learning, Data Analysis, Business Intelligence, and AI analytics must not be described as `released` merely because routes, source files, schemas, or candidate capabilities exist. A deprecated module retains existing public, persisted, published, security, and compatibility obligations until a separately approved retirement or migration decision takes effect.

## Portal composition

Portal composition remains explicit and manually reviewable. Its current integration surfaces include product routes, navigation groups, route preloads, localization bundles, shared UI entry points, and backend API adapters.

The portal composition owner coordinates integration but does not own each product's business logic. Each product owns its domain behavior, product-specific components, API contracts, internal state, tests, and compatibility responsibilities.

Adding or changing a product may require coordinated edits to current manual composition points such as `App.jsx`, route-group files, `config/routes.js`, `routePreload.js`, dashboard navigation, translation bundles, and affected tests. This is current-state documentation, not an authorization to edit those files.

No portal module registry, automatically generated route, or automatically generated sidebar contribution is introduced by this ADR.

## Hosted composition

ADR-FE-005 remains authoritative for hosted composition. Platform Hosted Composition owns the shared hosted entry, route namespace governance, precedence and arbitration, common bootstrap, hosted-safe integration rules, and dependency/bundle safeguards. Hosted products own their route declarations, runtime behavior, business workflows, and backend interfaces.

The following compatibility boundaries remain protected:

- separate portal and hosted entry graphs;
- lazy-loaded hosted products;
- existing hosted URLs, canonical redirects, and website catch-all precedence;
- backend-authoritative host and tenant validation;
- tenant/theme and authored-output isolation;
- Arabic/English and RTL/LTR behavior; and
- published content and schema compatibility.

Future hosted adapters may document contract shapes, but this ADR does not claim that a generic hosted adapter interface currently exists and does not authorize automatic hosted routing.

## Domain-specific extension contracts

First-party product identity is distinct from Page Builder block integration, Shared Forms field integration, Academy content rendering, data-visualization integration, and hosted product runtime adapters.

Each extension contract must be governed by its actual owner and consumers. Where persisted or published content is involved, changes must preserve supported type identifiers, schemas, historical readers, editor/preview/runtime parity, localization, accessibility, and compatible rendering.

No evidence establishes that one generic plugin interface is appropriate for all extension surfaces. This ADR therefore creates no universal extension descriptor or extension registry.

## Dependency boundaries

For new and materially modified code:

- cross-domain consumption must use supported public entry points or approved composition contracts;
- new imports from unrelated product-private implementation are prohibited absent an approved exception;
- hosted code must not newly import portal shells, administrative state, editor workspaces, authenticated admin APIs, or portal-only CSS;
- composition must preserve lazy loading rather than eagerly importing every SaaS product;
- shared-capability consumers must follow the capability's approved public interface and compatibility contract; and
- dependency direction, affected consumers, and applicable exceptions must be documented.

Existing legacy coupling must be inventoried and classified before replacement. It may remain as a supported legacy dependency, become an intentional contract, require a time-limited exception, or become a separately authorized remediation candidate. Legacy imports must not be removed automatically, and incomplete legacy documentation alone does not block a routine behavior-preserving bug fix.

Architecture CI does not currently enforce all of these boundaries. Documentation is an immediate review contract; automated enforcement remains a separate implementation decision.

## AI-assisted development workflow

Ownership documentation is intended to support the existing root `AGENTS.md` lifecycle:

1. **UNDERSTAND:** Read the owning `MODULE.md` or equivalent, relevant ADRs, public contracts, and affected tests. If documentation is absent, use bounded repository searches and record ownership uncertainty.
2. **PLAN:** Identify supported interfaces, dependency and consumer impact, tenant/security implications, compatibility surfaces, and QA scope.
3. **BUILD:** Modify only the smallest authorized domain scope and preserve public/private boundaries.
4. **TEST / VALIDATE:** Run proportionate existing QA, compatibility, security, RTL/accessibility, and release checks permitted by the task.
5. **FIX / RETEST:** Repair regressions without bypassing meaningful gates.
6. **REPORT:** Record changed files, architecture impact, compatibility, security, executed tests, limitations, and remaining risks.

Module documentation should help an agent locate the domain owner, supported APIs, integration files, test entry points, permission references, known legacy exceptions, and protected persisted contracts. These benefits are expected but have not been measured; this ADR claims no token-saving percentage or development-time improvement.

## Staged adoption options

The following stages describe possible future work, not implementation approval:

| Stage | Potential activity | Status under this ADR |
|---|---|---|
| **0 — Documentation** | Create focused ownership documents for priority domains and shared capabilities | Future implementation requires a separate authorized task |
| **1 — Contract inventory** | Verify public entry points and classify legacy private imports | Future implementation requires a separate authorized task |
| **2 — Selective metadata** | Add machine-readable metadata only for approved concrete validators or consumers | Not approved |
| **3 — Specialized build-time composition** | Consider limited static registration for a proven need such as route-collision validation or hosted adapter composition | Deferred; separate evidence and approval required |
| **4 — CI boundary enforcement** | Baseline legacy violations and reject newly introduced violations | Not implemented or approved here |

No stage is automatically mandatory beyond the approved logical documentation policy. Ordering, priority domains, owners, deadlines, and verification tooling remain unresolved.

## Alternatives considered

### Option A — No registry and no structured module documentation

Not selected. It avoids documentation work but leaves ownership, supported interfaces, tests, and integration discovery fragmented across source and institutional knowledge.

### Option B — Documentation-first, manual composition

**Approved logical direction.** It makes ownership and contracts reviewable while preserving explicit portal/hosted composition, lazy loading, existing delivery topology, and domain-specific extension mechanisms.

### Option C — Static or build-time first-party registration

Deferred. A limited registry may be reconsidered for a specific proven validator or composition need after separate evidence, compatibility analysis, implementation design, and product-owner approval. Build-time registration would not imply independent product deployment.

### Option D — Dynamic runtime plugin or extension registry

Not authorized. Current evidence does not justify its runtime trust, failure-isolation, compatibility, operational, and bundle complexity.

## Consequences and trade-offs

### Benefits

- clearer technical ownership and architecture discovery;
- reviewable portal, hosted, and shared-capability integration points;
- explicit public/private boundaries;
- preservation of current lazy loading and coordinated deployment;
- smaller initial migration burden than a universal registry; and
- freedom to evolve specialized contracts independently.

### Costs and limitations

- some new products continue to require manual route, navigation, preload, localization, and test updates;
- ownership documentation requires maintenance and may become stale unless reviewed with code changes;
- documentation alone does not enforce dependency rules;
- existing cross-domain legacy coupling remains until separately classified and remediated;
- coordinated frontend releases and affected-consumer regression QA remain necessary when shared composition or shared contracts change;
- AI-context improvements remain unmeasured;
- the model does not create independent frontend deployments; and
- product integration is not automatic or guaranteed to be effortless.

Shared capability changes may affect multiple product runtimes. Relevant consumer validation must follow existing `AGENTS.md`, security, QA, CI, and release requirements. This ADR does not authorize test execution or changes to release gates.

## Ownership and consumers

| Responsibility | Logical owner | Consumers | Current decision status |
|---|---|---|---|
| First-party module ownership policy | Frontend architecture governance; accountable technical maintainer pending | All major product domains and shared platform capabilities | Logical direction approved; implementation not authorized |
| Portal composition | Existing application-shell/portal composition owner; exact maintainer pending | Authenticated product workspaces and portal navigation | Existing explicit implementation preserved |
| Hosted composition | Platform Hosted Composition | Website, Forms, Academy, learner, Storefront, future approved hosted products | Approved by ADR-FE-005 |
| Product behavior and adapters | Respective product domain | Portal and/or hosted composition | Existing ownership direction; formal public facades may remain unresolved |
| Shared capability contracts | Respective approved shared-capability owner | Approved product consumers | ADR- and contract-specific |
| Commercial access authority | FastAPI commercial and entitlement services | Portal, hosted products, backend operations | Existing backend authority |

No accountable technical maintainer is appointed by this ADR.

## Contracts and compatibility

This decision preserves:

- existing portal and hosted route behavior;
- published Page Builder schemas and editor/preview/hosted/Academy compatibility;
- separate Website Forms and E-learning Forms persistence and server validation;
- Reservations and Calendar / Planning ownership boundaries;
- Academy, learner, Storefront, Data Analysis, and Business Intelligence behavior and contracts;
- tenant identity, authorization, resource ownership, publication, and commercial entitlement checks;
- product-specific persistence;
- Arabic/English, RTL/LTR, themes, responsive behavior, and accessibility; and
- all existing QA, CI, migration, deployment, and release gates.

A future ownership document is a navigation and governance aid. It must link to authoritative contracts and cannot silently redefine an API, persisted schema, permission, entitlement, route, extension identifier, or compatibility promise.

## Commercial and lifecycle impact

This ADR creates no SKU, subscription, capability, entitlement, commercial launch, navigation visibility rule, operational-availability decision, or independent deployment. Existing commercial identifiers remain backend concepts and do not become technical-domain IDs merely by being documented.

E-learning, Data Analysis, Business Intelligence, and AI analytics retain their independently established development and commercialization status. This ADR does not declare them commercially launched or technically `released`.

## Implementation and dependency impact

Implementation is **NOT AUTHORIZED**. This ADR creates no `MODULE.md`, registry, metadata file, source move, public facade, adapter, route, navigation contribution, preload, localization bundle, dependency, build step, CI check, API, schema, migration, or deployment change.

Any implementation stage requires a separate authorized task, preservation of the legacy baseline, identification of affected consumers, and the complete root `AGENTS.md`, constitution, security, QA, CI, migration, deployment, and release lifecycle.

## QA, CI, and release impact

No application tests, builds, servers, migrations, or deployments were executed for this documentation-only ADR.

Representative existing evidence includes:

- `web/frontend/src/routes/UserWorkspaceRoutes.test.jsx`, `AdminRoutes` consumers, and route-specific tests for explicit portal routing;
- `web/frontend/src/components/DashboardBuilder/DashboardSidebar.test.jsx` for current navigation behavior;
- `web/frontend/src/routes/routePreload.test.js` for explicit preload selection;
- `web/frontend/src/tenantEntry.test.js`, `tenantRuntimePreload.test.js`, `routes/TenantSiteRoutes.preload.test.jsx`, and `TenantSiteRoutes.storefront.test.jsx` for hosted entry, preloading, and route composition;
- Shared Page Builder, Forms, E-learning, E-commerce, Reservations, Calendar, Data Analysis, and BI tests cited by ADR-FE-002 through ADR-FE-005; and
- `web/backend/tests/test_modular_commercial_contract.py`, `test_commercial_entitlements.py`, and authorization/tenant tests for backend commercial and access behavior.

These files demonstrate existing test surfaces only. They were not executed in this phase and do not prove complete module-boundary coverage.

- **Existing architecture checks:** Root QA/release gates, current route/navigation/runtime tests, dependency-lock checks, frontend tests and build audits where already configured.
- **Proposed architecture checks:** Required ownership-document validation, prohibited-private-import checks, declared-entry validation, route/navigation/localization reference checks, exception expiry, and new-violation baselines.
- **Accountable CI enforcement owner:** PENDING OWNER DECISION
- **Planned verification milestones:** PENDING OWNER DECISION
- **Review trigger/date:** Re-evaluation triggers in this ADR; no calendar date approved

Proposed checks are not implemented and future CI automation is not a prerequisite for approval of this logical documentation policy.

## Rollback, migration, and failure handling

There is no runtime rollback, data migration, or deployment because implementation is not authorized. This approved ADR may be superseded only through the governed ADR process.

Any later documentation rollout must preserve working code and supported contracts when documentation is incomplete or stale. Any later validator or composition mechanism requires its own incremental rollout, legacy baseline, failure behavior, rollback plan, and approval.

## Risks and unresolved questions

- Specific `MODULE.md` locations, naming conventions, document sizes, and adoption order: unresolved.
- Accountable maintainers for individual domains, shared capabilities, portal composition, and architecture CI: `PENDING OWNER DECISION`.
- Final public API facade names and physical entry points: unresolved until verified or separately implemented.
- Classification of existing private and cross-domain imports: unresolved pending bounded inventories.
- Architecture CI tooling, enforcement ownership, baseline format, and milestones: `PENDING OWNER DECISION`.
- Approved machine-readable metadata validators or consumers: none approved.
- Route-collision automation: not approved.
- Threshold for specialized static/build-time registration: unresolved.
- Third-party executable extension policy: unresolved and not authorized by this ADR.
- Independent frontend deployment triggers: unresolved and require separate architecture and security approval.
- Documentation staleness detection and review responsibility: unresolved.

## Non-goals and exclusions

This ADR does **not** authorize:

- creating any `MODULE.md` now;
- universal module registration or runtime discovery;
- dynamic plugin loading, module federation, or micro-frontends;
- automatic portal or hosted route generation;
- physical module relocation or source restructuring;
- new public API facades or hosted adapters;
- backend entitlement redesign or frontend permission authority;
- commercial product restructuring;
- shared persistence migration;
- CI or validator implementation;
- dependency installation;
- application code or test changes;
- database migrations;
- staging, commits, pushes, merges, rebases, deployments, or production mutation.

## Approval record

### Logical direction approval history

- **Logical architecture:** APPROVED BY PRODUCT OWNER
- **Logical approval date:** 2026-11-06
- **Selected model:** OPTION B — DOCUMENTATION-FIRST, MANUAL FIRST-PARTY COMPOSITION
- **Approved logical scope:** Human-readable ownership for major product domains and shared capabilities; explicit manual portal and hosted composition; supported public/private boundaries; separate extension contracts; technical/commercial separation; canonical lifecycle governance; and staged future options requiring separate approval
- **Explicit limitations:** No implementation, `MODULE.md`, registry, automation, restructuring, Git release action, or deployment was authorized

### Current approval status

- **Complete ADR document:** APPROVED — LOGICAL ARCHITECTURE ONLY
- **Final document approval date:** 2026-11-06
- **Implementation authorization:** NOT AUTHORIZED
- **Repository-wide adoption:** PENDING INDEPENDENT REVIEW AND AUTHORIZED MERGE
- **Technical maintainer:** PENDING OWNER DECISION
- **Related ADRs:** ADR-FE-002, ADR-FE-003, ADR-FE-004, ADR-FE-005
- **Related exception IDs:** None
- **Related constitutional amendment:** Constitution v0.2.1 lifecycle terminology; no new amendment proposed
- **Supersedes / superseded by:** None

### Final document approval history

- **Approval event:** FINAL DOCUMENT APPROVAL
- **Approval authority:** Madar product owner
- **Approval date:** 2026-11-06
- **Approved document:** ADR-FE-006 incorporating Phase 26.2 corrections F-01 through F-03
- **Approved scope:** Documentation-first ownership governance, explicit manual portal and hosted composition, module documentation contracts, supported public/private interface rules, technical and commercial separation, lifecycle policy, dependency boundaries, compatibility obligations, trade-offs, and non-goals
- **Implementation authorization:** NOT AUTHORIZED
- **Repository-wide adoption:** PENDING INDEPENDENT REVIEW AND AUTHORIZED MERGE
