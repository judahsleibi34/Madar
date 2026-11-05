# MADAR — Frontend Architecture Constitution & Expansion Rules

**Document ID:** MADAR-ARCH-FE-001
**Version:** 0.2
**Status:** APPROVED — REPOSITORY ACTIVATION PENDING
**Prepared:** 2026-11-06
**Approval authority:** Madar product owner
**Approval date:** 2026-11-06
**Approved scope:** `web/frontend`, hosted tenant frontend delivery, frontend-facing FastAPI contracts, and future Madar web frontend modules
**Effective date:** Pending completion of repository adoption gates
**Supersedes:** Version 0.1 upon repository activation. Existing root `AGENTS.md` security, development, QA, CI, migration, deployment, and production-release rules remain in effect.

> **Architecture objective:** Madar must be able to add substantial products and features repeatedly without requiring repeated structural rewrites, duplicating shared engines, weakening tenant isolation, breaking published content, or making routine AI-assisted work depend on reading unrelated modules.

## 1. Authority, precedence, and prospective application

- **MUST / MUST NOT** becomes binding only after this document is formally approved, tracked in Git, and referenced as active authority by root `AGENTS.md`.
- **SHOULD / SHOULD NOT** states a reviewable default. Deviations require an explanation in change review and may require an exception when they create sustained architectural divergence.
- **MAY** permits an option but grants no authority to bypass a higher rule.

The governing order, from highest to lowest, is:

1. Existing security, tenant-authorization, migration, deployment, production-authorization, and release contracts, together with their enforcing implementation.
2. The mandatory development and QA lifecycle in root `AGENTS.md`.
3. This constitution after formal approval and adoption.
4. Product-owner-approved Architecture Decision Records (ADRs) that comply with levels 1–3. An ADR may justify or authorize preparation of a constitutional amendment, but it does not itself change or override a constitutional **MUST** or **MUST NOT**.
5. Approved domain contracts and module documentation.
6. Feature-specific developer guidance.
7. Existing legacy implementation where no higher approved rule governs the change.

A lower level MAY clarify or strengthen a higher level but MUST NOT weaken or contradict it. More-specific guidance applies only while it remains consistent with every higher level. No product-owner architecture decision, ADR, exception, or amendment can bypass existing security, tenant authorization, QA, CI, migration, deployment, or production-release controls. If applicable requirements cannot all be satisfied, implementation MUST stop pending a decision from the authority responsible for the higher rule.

The current implementation remains authoritative evidence of current runtime behavior, compatibility, and release mechanics. It does not authorize new code to reproduce undocumented legacy coupling. These rules apply prospectively to new and materially modified code. Unmodified legacy functionality remains supported until separately classified through an approved review. Normal bug fixes that preserve public contracts, dependency direction, persistence meaning, authorization boundaries, and runtime behavior do not trigger unrelated legacy remediation.

## 2. Operational definitions

- **Business domain:** A cohesive business capability with accountable decisions, workflows, business rules, data meaning, and contracts. A domain is not inferred solely from a folder, route, team, or commercial SKU.
- **Technical module:** A bounded implementation unit with defined entry points, dependencies, state ownership, and tests. One business domain may contain several technical modules, and an approved shared module may serve several domains.
- **Commercial module:** A customer-facing package, subscription, add-on, or entitlement. Commercial packaging may map many-to-many to business domains and technical modules and does not define code ownership or authorization by itself.
- **Shared platform capability:** Intentionally reusable functionality serving multiple domains under one accountable contract owner, such as authenticated API transport or shared Page Builder rendering. Reuse by multiple consumers alone does not establish ownership.
- **Public contract:** An intentionally supported interface, schema, persisted identifier, extension point, or observable behavior documented for consumers and covered by proportionate compatibility evidence. Exporting a symbol or importing a file does not by itself make it public.
- **Private implementation:** Code, data shapes, styles, or behavior not declared as a public contract. Technical importability does not make private implementation supported for cross-domain use.
- **New feature or module:** A new business workflow, route, hosted exposure, persisted content type, API contract, module integration, or materially new user capability. A behavior-preserving refactor or isolated defect correction is not automatically a new feature.
- **Materially modified code:** Code changed in a way that affects domain ownership, dependency direction, a public contract, persisted schema meaning, authorization or tenant scope, entitlement behavior, shared multi-consumer behavior, hosted/theme boundaries, or module lifecycle integration.
- **Breaking architectural change:** A change that removes or changes a supported public contract, persisted meaning, trust boundary, or delivery surface such that a supported consumer must migrate or coordinated compatibility work is required.
- **Approved architectural exception:** A written, scoped, product-owner-approved, time-limited deviation recorded in `docs/architecture/EXCEPTIONS.md`, including risk, affected consumers, safeguards, tests, review date, and expiry. An exception operates only where this constitution expressly permits an exception or against a lower-level rule; it does not amend a constitutional **MUST** or **MUST NOT** and cannot waive a higher-level rule.

## 3. Evidence and non-negotiable context

The following is a *current-state baseline*, not a mandate to preserve all implementation details. It comes from the read-only Phase 1–6 Codex repository assessments:

- Web: React 19, Vite 8, React Router 7, JavaScript/JSX, plain CSS; Python/FastAPI as backend.
- Portal and hosted-tenant experiences use separate frontend entry graphs and different CSS loading profiles.
- Page Builder's schema, rendering, editor, themes, forms UI, and publication capabilities are **intentionally reused** by websites, academies, previews, and hosted sites.
- Website forms and E-learning forms share frontend concepts but have **distinct backend persistence and server validation**.
- Authenticated tenant identity, permissions, commercial entitlements, and publication access are enforced by FastAPI. The frontend is not the authorization authority.
- Published schemas and publication workflows have existing version and compatibility contracts.
- E-learning and Analytics are under development and may be commercialized later; the current commercial catalog **must not** be mistaken for the permanent technical domain map.
- Global CSS refinements and cross-feature imports are real compatibility-sensitive surfaces. Extensive CI, RTL, tenant, and publishing checks already exist.
- Current project structure does **not** yet enforce the future domain boundaries or provide a general frontend module registry. Do not describe proposed mechanisms as already implemented.

**Evidence disclaimer:** Six reports are static-source investigations; no production workload, full regression suite, actual AI token usage, or real user performance was measured by those reports. Verify facts at implementation time.

## 4. Architectural direction proposed for approval and unresolved decisions

The proposed architectural direction for formal owner review and staged adoption is **domain ownership + modular monolith + limited first-party extension contracts**. It is not approved until the product owner adopts this constitution.

1. **Domain ownership:** Define which business capability is responsible for decisions, data shapes, workflows, screens, tests, and APIs.
2. **Modular monolith:** Keep a coordinated web deployment while making source boundaries, dependencies, and public module interfaces explicit and enforceable.
3. **Limited microkernel principles:** Allow build-known, first-party products and shared engines to contribute predictable routes, navigation, and supported extensions **if a validated registry or extension contract is adopted**.

This is **not** an authorization to rewrite existing directories or build a general plugin platform. A build-time first-party module registry, a Page Builder block-extension contract, and a remotely loaded third-party plugin system are separate decisions. Remote executable plugins, module federation, and micro-frontends require an explicit ADR and security review.

**Do not change React, Vite, JavaScript/JSX, npm, FastAPI, workspace tooling, or deployment topology just to match an architecture diagram.** Technology migrations require evidence, alternatives, compatibility plans, and approval.

The direction above does not decide the unresolved commercial packaging, deployment independence, third-party plugin, domain-owner, or product-roadmap questions listed in Section 18.

## 5. Mandatory architectural invariants

**INV-01 — Server-side trust boundary.** FastAPI is Madar's existing backend authority. The permanent invariant is verified server-side enforcement of tenant isolation, authentication, authorization, commercial entitlements, data ownership, and all write/publication decisions. Any future change in backend service ownership or authorization architecture requires an explicit ADR, security review, compatibility validation, and product-owner approval. Frontend modules, UI visibility, navigation, plugin metadata, and extension metadata MUST NEVER become authoritative for backend permissions.

**INV-02 — Shared Page Builder parity.** Editor, preview, published website, hosted runtime, and academy consumers MUST remain compatible with their supported page/schema and rendering contracts. Reuse MUST NOT be replaced with unreviewed feature-specific forks.

**INV-03 — Historical content safety.** Published schema versions, persisted element IDs, revisions, and existing reader behavior MUST be considered before changing builder contracts. Unsupported versions require an explicit migration or compatibility policy.

**INV-04 — Intentional domain ownership.** Every new business feature MUST have one documented owning domain, even when it consumes shared engines or supports multiple commercial products.

**INV-05 — Explicit dependencies.** Cross-domain communication MUST use public contracts, integration interfaces, or composition points. New imports into another domain's private implementation are prohibited absent a documented exception.

**INV-06 — Distinct business persistence.** Shared visual form concepts MUST NOT silently merge website form validation/persistence with E-learning form validation/persistence. A merger would require a separate business and migration decision.

**INV-07 — Separate commercial concepts.** Technical domains, modules, capabilities, product SKUs/subscriptions, permissions, operational status, and navigation are distinct concepts. One MUST NOT be assumed to equal another.

**INV-08 — Preserve delivery surfaces.** Portal and hosted-tenant entry graphs, hostname resolution, public/visitor access boundaries, and authored-theme isolation MUST be preserved unless explicitly redesigned and validated.

**INV-09 — Internationalization and accessibility.** All user-facing work MUST account for Arabic/English, RTL/LTR, keyboard/accessibility needs, responsive layouts, and supported themes.

**INV-10 — Continuous QA and release safety.** Existing tests, CI, security gates, and release restrictions MUST NOT be bypassed to accommodate architecture changes.

**INV-11 — No speculative infrastructure.** A feature MUST NOT introduce a global abstraction, new framework, state library, runtime plugin mechanism, or independently deployed frontend merely because future scale is anticipated. The need and alternatives MUST be documented.

**INV-12 — Agent-readable boundaries.** Each new domain MUST be navigable through compact ownership, contract, and test documentation so a coding agent does not need to inspect unrelated feature internals to start work.

**INV-13 — Existing-system compatibility.** Architecture governance MUST preserve supported Page Builder authoring and rendering contracts, editor/preview/published-site/hosted-runtime/academy parity, published schema compatibility, separate website and E-learning persistence and server validation, FastAPI tenant and authorization authority, separation of commercial and technical modules, Arabic/English and RTL/LTR behavior, tenant themes and authored-output isolation, and every applicable QA and release contract.

**INV-14 — Developing products are not final packaging.** E-learning and Analytics remain products under development. Their current routes, flags, or commercial packaging MUST NOT be treated as final product ownership, permanent commercial identifiers, or approval for an independent deployment model.

## 6. Responsibility model (conceptual, not a prescribed directory move)

| Responsibility | Owns | Must not own |
|---|---|---|
| **Application shell/platform** | Entry selection, authenticated shell, routing composition, navigation presentation, identity/session integration, localization initialization, errors | E-learning/Commerce/Analytics business workflows; authoritative backend permissions |
| **Shared Page Builder engine** | Supported schema, element rendering, shared editor/runtime contracts, blocks, theme/rendering abstractions, publication compatibility surfaces | Course grading, commerce order rules, learner persistence |
| **Product domains** | Their business screens, workflows, domain-facing API adapters, local state, owned styles and tests | Another domain's private implementation or global authentication decisions |
| **Shared infrastructure** | `apiFetch` conventions, common media primitives, cross-product UI design tokens/components, approved AI transport abstractions | Business-specific behavior added merely for convenience |
| **Hosted/public delivery** | Host-derived site/academy/storefront composition, public runtime integration, guest UX | Substituting frontend checks for FastAPI's public entitlement and resource checks |
| **FastAPI** | Business authority, tenant/security enforcement, persistence, publication checks, AI processing and job controls | Frontend layout composition |

A capability can have **multiple consumers but one accountable contract owner**. The Page Builder editor is a user-facing application; the underlying rendering/schema contracts are deliberately shared. Ownership of themes, reservations, academy block extension semantics, and common forms UI remains to be formally confirmed; do not guess from folder names alone.

## 7. Dependencies and module public surfaces

For **new and deliberately migrated** modules, the default dependency direction is:

```text
entry / application shell
    -> product-domain public entry points
        -> approved shared engines / platform contracts
            -> shared infrastructure (API transport, UI primitives)
```

- Modules MUST declare their *public* imports/exports or integration entry points; other domains SHOULD consume only those stable surfaces.
- Domain internals MUST NOT import another domain's private files. A necessary E-learning ↔ Page Builder integration is permitted through **explicit composition contracts**, not by banning legitimate business interactions.
- Shared infrastructure MUST NOT import arbitrary product domain internals. Where the Page Builder needs academy-specific content, the integration contract may receive a provider, renderer override, or other explicitly approved adapter.
- Public APIs SHOULD be minimal and purpose-specific; avoid `export *` surfaces that accidentally turn every internal into a contract.
- Circular dependency **claims** require an actual module graph/cycle check. A bidirectional feature relationship alone is not proof of runtime circular imports.
- Names, packages, folder layouts, or independent deployments MUST NOT be changed solely for visual symmetry.

**Legacy rule:** Existing direct cross-feature imports remain supported until individually classified as intentional shared contracts, temporary exceptions, or migration candidates, with tests and owners identified.

## 8. Requirements for every new first-party SaaS product or module

Before implementation, each new product/domain MUST have a compact `MODULE.md` (or agreed equivalent) recording:

1. **Identity:** stable module ID, name, owning domain/maintainer, current lifecycle (`experimental`, `under development`, `released`, `deprecated`), and scope.
2. **Capabilities:** user-visible workflows, dependencies on shared engines, and non-goals.
3. **Integration:** route(s), navigation contribution, localized labels, entry component(s), loading/error behavior, and hosted exposure if relevant.
4. **Access:** required FastAPI authorization checks, permission/capability identifiers, and optional commercial entitlement mapping; clearly distinguish each.
5. **Contracts:** public frontend interface, required backend endpoints/models, persisted schema and event versions, and supported extension points.
6. **State and styling:** owner of server state, feature-local state, browser storage, CSS, theme, RTL, and lifecycle cleanup.
7. **QA:** unit/integration/E2E, tenant/security, public-runtime, accessibility/RTL and compatibility tests relevant to the feature.
8. **Change impact:** cross-feature consumers and migration implications.

**When a first-party registry is approved:** registration MUST be statically discoverable and build-known by default, with deterministic navigation ordering, route ownership, lazy-load error boundaries, visibility metadata, and validated references. The registry MAY provide UI routing/navigation metadata; it MUST NOT replace backend authorization. Until then, document the existing manual route/sidebar/i18n integration steps rather than pretending a registry exists.

**Adding a new module MUST NOT require copying a shared Page Builder engine, form runtime, API security wrapper, or styling token system.** Reuse through stable contracts.

## 9. Page Builder, shared engines, and extension contracts

Changes to page/element/block/form/theme contracts MUST document:

- Stable persisted type identifiers, payload fields, defaults, schema version, and migration/unsupported-type policy.
- Editor creation/editing, preview, hosted site display, academy display where applicable, accessibility and RTL behavior.
- Backend validation and publication checks; public visitor/resource authorization when relevant.
- Which product owns feature-specific data and actions. Academy courses and assessments remain E-learning concerns; Page Builder handles presentation mechanics.
- Existing legacy publications and version compatibility expectations.
- Required contract, renderer, runtime, academy, and backend tests.

Do not add new blocks through editor-only rendering if published runtime and academy consumers need them. Do not silently change stored schema meaning. Replacing a shared implementation with a new engine is a major ADR-level decision.

A new SaaS product MUST document its business domain, technical modules, lifecycle, public contracts, backend authority, routes, navigation, localization, commercial mapping if decided, hosted exposure if any, shared-engine dependencies, and QA scope. An undecided commercial mapping MUST be recorded as unresolved rather than inferred from current feature flags or navigation.

Changes to any shared engine MUST identify its accountable contract owner, affected consumers, compatibility obligations, and test evidence. A new cross-domain dependency MUST use a declared public contract or composition point; importing another domain's private implementation requires a time-limited approved exception.

Build-known first-party extension contracts MAY be proposed through an ADR. Remote executable plugins, third-party extensions, module federation, or independently deployed frontend units require a separate ADR, security review, compatibility model, failure-isolation analysis, and explicit product-owner approval. No such external plugin or deployment model is approved by this constitution.

## 10. API, data, authentication, and AI rules

- The existing centralized `apiFetch` session/cookie/CSRF/refresh behavior is the default transport. New API callers MUST use the approved transport or document a justified exception.
- Business requests MUST obtain tenant scope from the authenticated backend contract; do not invent a client-provided tenant header as an authorization mechanism.
- Treat server data as server-owned state and local ephemeral UI state separately. A global state library is optional, not automatically required.
- Persisted browser caches MUST use appropriate tenant/user/resource scoping, and authenticated data MUST be cleared or invalidated on logout or identity change. Tenant switching requires its own approved behavior before implementation.
- Backend API shapes MUST be documented and validated. TypeScript migration or generated OpenAPI clients MAY be evaluated later; existing JavaScript/JSX is not a license to leave cross-module data contracts ambiguous.
- For AI features, distinguish deterministic assistance, model inference, jobs, streams, and background processing. Cancellation, progress, data governance, permissions, metering, and tenant-scoped outputs MUST have explicit contracts when applicable.
- E-learning and Analytics being under development MUST NOT dictate their final commercial module identifiers or deployment model.

## 11. Styles, design system, and hosted runtime

- New feature styling MUST have clearly identified ownership and scope. Avoid adding new broad global selectors for feature-local behavior.
- Use existing semantic tokens and theme contracts. Do not override authored site/theme output through portal-only selectors.
- New `!important` and late global override usage SHOULD be exceptional, justified, and tested across affected screens; existing instances must not be mass-removed without visual evidence.
- Portal/hosted-tenant CSS entry separation MUST be maintained. Any import that increases hosted CSS scope requires a bundle/theme impact assessment.
- Test relevant light/dark, RTL/LTR, mobile/responsive, preview and hosted scenarios. Global CSS cleanup is a separately approved compatibility project.

## 12. Continuous quality contract for architecture changes

For every code-changing task follow the existing Madar lifecycle:

**UNDERSTAND → PLAN → BUILD → TEST → VALIDATE → FIX → RETEST → REPORT**

Before implementation: identify module owner, impacted public contracts, tenant/access implications, relevant existing tests, and compatibility surfaces.

During implementation: limit unrelated edits; preserve existing behavior unless changed by approved requirement; avoid introducing invisible cross-module dependencies; update module docs/contracts when interfaces change.

Before merge: run all proportionate existing checks and additional impacted contract/tenant/RTL/hosted-runtime checks. Record outcomes and any tests not run. Do not bypass failed release/security gates.

Architecture reporting is additive to the mandatory root `AGENTS.md` completion report. It MUST NOT replace, rename, or omit any required QA field. Within those fields, or in a clearly attached architecture subsection, report:

- affected business domains and technical modules;
- public contract, persisted-schema, and cross-domain dependency changes;
- Page Builder and other shared-engine consumers;
- tenant, authorization, entitlement, and public-access impact;
- published-content compatibility;
- CSS, theme, RTL, accessibility, and hosted-runtime impact;
- ADR or approved-exception references; and
- architecture validation performed or explicitly not performed.

Release-specific reporting remains governed by root `AGENTS.md` and the existing release contracts.

## 13. Enforcement maturity model

Architecture enforcement is incremental and has three levels:

### Level 1 — Immediately mandatory after adoption

These rules are enforced through change scope, review evidence, existing tests, and the mandatory QA report:

- preserve all higher-level security, authorization, QA, CI, migration, deployment, and release requirements;
- preserve FastAPI as the existing backend authority and verified server-side enforcement of tenant isolation, authentication, authorization, entitlements, data ownership, persistence, and publication decisions;
- preserve supported published content and Page Builder consumer compatibility;
- do not introduce an unreviewed feature-specific fork of a shared engine;
- do not present frontend visibility or module metadata as runtime authorization; and
- include the architecture impact information required by Section 12.

### Level 2 — Documented architecture review

The following require reviewable documentation before implementation or merge, as applicable:

- new product/domain/module ownership and its `MODULE.md` or approved equivalent;
- a new cross-domain dependency or public contract;
- a Page Builder or shared-engine cross-consumer impact map;
- a breaking architectural change and its ADR;
- a time-limited exception;
- browser-cache, global-style, tenant-theme, hosted-runtime, or plugin/extension boundary changes; and
- changes to the constitution or an established shared engine.

Evidence consists of the applicable module contract, ADR, exception record, consumer map, compatibility analysis, test plan, and recorded review. A new Level 2 requirement MUST NOT silently force an unrelated rewrite of legacy code.

### Level 3 — Future automated CI enforcement

Future CI MAY verify prohibited private imports, required module metadata, declared public entry points, route/navigation/localization references, exception expiry, contract compatibility, and relevant test selection. Tooling and rollout require separate evaluation and approval. Current frontend CI provides dependency-lock verification, lint, tests, build audits, and dependency audit; it does not yet enforce the architectural module boundaries defined here. No Level 3 rule may be described as automated until its repository check is implemented and required by the applicable CI/release policy.

Architecture CI governance MUST track the accountable enforcement owner, existing checks, proposed checks, planned verification milestones, and a review trigger or review date. Until decided, these fields MUST use `PENDING OWNER DECISION`; no owner or date may be inferred. Future automation is not a prerequisite for adoption of Constitution v0.2.

Stable shared entry points SHOULD gain consumer-compatibility tests progressively. Automated checks MUST begin with new or deliberately migrated code and an approved legacy baseline, not a surprise repository-wide failure.

## 14. AI-assisted development and token-efficiency rules

- First consult available ownership documentation, module contracts, architecture maps, public contracts, and affected-test guidance.
- If that documentation is absent or incomplete for legacy code, use bounded repository searches and representative call sites to establish the current apparent owner and consumers.
- Record ownership uncertainty explicitly. Do not invent a module contract, owner, public interface, or claim that missing documentation already exists.
- Incomplete legacy module documentation alone MUST NOT block a routine bug fix that preserves contracts and architectural boundaries. New modules still MUST document their ownership and public interfaces before implementation.
- Prefer bounded search, symbol-level inspection, relevant line ranges, and existing interface docs over dumping whole large files.
- Do not assume reducing total source LOC will reduce token consumption. Measure *files/lines actually inspected*, unrelated exploration, manual integration edits, test-selection breadth, and actual tokens only when logs expose them.
- When adding a feature, the agent MUST describe why each shared engine or adjacent domain needs to be inspected or modified.
- Changes to Page Builder schema/runtime must use a **cross-consumer impact map**; deep shared-engine work is legitimately broader than isolated BI UI work.
- Avoid generated abstractions or premature packages that increase navigation cost without reducing proven coupling.

## 15. Approval, ADRs, exceptions, and constitutional change control

The Madar product owner is the final approving authority for frontend architecture decisions, constitutional amendments, ADRs, and architectural exceptions. This authority is architectural only: it cannot waive or bypass any security, tenant-authorization, QA, CI, migration, deployment, or production-release requirement.

File presence, draft text, review discussion, implementation, or silence does not constitute approval. An approved record MUST identify its status, approving authority, approval date, scope, and any review or expiry condition.

### ADR requirements

An ADR MUST be prepared before:

- adopting a new frontend platform framework, bundler, workspace system, global state solution, or design-system replacement;
- making a breaking change to a published Page Builder schema, element ID, rendering/publication contract, forms persistence boundary, or public API contract;
- changing backend service ownership, tenant identity selection, authorization architecture or authority, entitlement semantics, or hosted-routing trust boundaries;
- creating or replacing a shared cross-domain engine;
- introducing remote runtime plugins, module federation, micro-frontends, third-party executable extensions, or independently deployed frontend units;
- establishing a sustained cross-domain dependency that cannot use an existing public contract; or
- making a major change to the approved architectural direction.

ADRs live under `docs/architecture/decisions/` and use `ADR-TEMPLATE.md`. Each ADR records status; decision owner; context and evidence; decision; rejected alternatives; affected domains and consumers; tenant/security impact; commercial impact if known; backward compatibility and migration impact; QA, release, and rollback requirements; product-owner approval; and re-evaluation trigger.

An approved ADR may justify or authorize preparation and review of a constitutional amendment. It does not itself override, suspend, or replace an existing constitutional **MUST** or **MUST NOT**. Changing a binding constitutional requirement requires a versioned amendment to this document, documented impact review, explicit product-owner approval, and a recorded effective date and scope. Cross-domain changes require documented review from the accountable owners of every affected domain. If an owner has not been established, the ownership field remains `PENDING OWNER DECISION`, and the interim rule is to preserve the existing contract and behavior.

### Time-limited exceptions

Architectural exceptions are recorded in `docs/architecture/EXCEPTIONS.md`. An exception MUST include an identifier, affected rule, exact scope, rationale, risk, affected consumers, safeguards, validation, accountable owner, product-owner approval date, and a finite review or expiry date. Exceptions are not permanent architecture and do not silently establish a public contract.

Expiry never authorizes automatic code removal. At review, the exception must be closed, renewed with fresh approval, replaced by an ADR, or assigned an approved remediation decision. No exception may amend a constitutional **MUST** or **MUST NOT**, waive a higher-level rule, or permit a release/security failure to be bypassed. A binding constitutional change follows the versioned amendment procedure instead.

### Constitution amendments and future evolution

Every amendment requires a version change, change summary, documented impact review, explicit product-owner approval, approval date, recorded effective date and scope, and effective status. A major change in architectural direction requires an ADR before or with the amendment. Amendments MUST preserve all higher-level security, tenant-authorization, QA, CI, migration, deployment, and release rules. An ADR without the corresponding approved versioned amendment leaves the existing constitutional requirement unchanged.

Architecture evolves through approved evidence, ADRs, and versioned amendments—not as an incidental side effect of feature delivery.

## 16. New feature acceptance checklist

A feature is architecturally ready only when reviewers can answer:

- [ ] Which domain owns it? Is it new, or part of an existing product?
- [ ] Which shared contracts does it use, and which public APIs are exposed?
- [ ] Does it affect Page Builder editor/preview/hosted/academy parity or stored schemas?
- [ ] What are its FastAPI tenant, user, capability, entitlement, and public access checks?
- [ ] How are route, navigation, localization, loading/error, and hosted exposure integrated?
- [ ] Where do state, caches, styles, assets, and RTL/theme behavior live?
- [ ] Which tests establish function, tenant isolation, compatibility, accessibility, and regression safety?
- [ ] Has its `MODULE.md`/contract documentation been added or updated?
- [ ] Has a scoped QA report been produced without bypassing existing gates?
- [ ] If architecture is changed, is an approved ADR recorded?

## 17. Adoption gates (not an implementation or migration authorization)

### Required before policy adoption

- [x] The product owner completes final review and records explicit approval of version 0.2.
- [x] Final wording, document version, approval date, and effective status are internally consistent.
- [ ] The constitution, ADR template, and exception register are tracked in Git at their approved paths.
- [ ] Root `AGENTS.md` authority reference is committed through an authorized Git workflow.
- [x] The precedence, definitions, approval procedure, reporting integration, and existing-system compatibility rules are accepted.
- [x] Domain ownership decisions are recorded, or unresolved owners are marked `PENDING OWNER DECISION` with the preservation-first interim rule.
- [x] Level 3 governance fields exist for accountable owner, existing/proposed checks, milestones, and review trigger/date; specific values may remain `PENDING OWNER DECISION`, and future automation is not an adoption prerequisite.
- [x] Review confirms that existing security, tenant authorization, QA, CI, migration, deployment, and production-release gates remain unchanged.
- [x] Adoption is not bundled with a broad source reorganization, legacy rewrite, architecture migration, or new dependency.

### Later maturity work; not automatically adoption-blocking

- Validate one representative module's owner, public surface, and test map without changing functional behavior.
- Complete the domain and public-contract inventory.
- Classify legacy cross-feature imports and record necessary exceptions.
- Measure AI context and cross-feature change impact where evidence is available.
- Design, approve, and incrementally introduce Level 3 CI checks.
- Address legacy hotspots through separately approved, compatibility-tested work rather than a big-bang rewrite.

## 18. Explicit unresolved product decisions

Before treating optional machinery as mandatory, confirm:

1. Product roadmap and approximate expected module count/teams in the next 6–24 months.
2. Coordinated versus independent product release/deployment requirements.
3. Whether customers/partners will ever supply **executable** plugins versus using first-party products and configurable content.
4. Product-authoritative owner of shared themes, forms UI, reservations, media, academy block contracts, and historical page schemas.
5. Published-site backward compatibility duration and supported schema migration policy.
6. Desired behavior for multi-tenant memberships, tenant switching, and identity/cache transition.
7. Visibility rules for under-development, unavailable, discoverable, and commercially launched products.
8. Required measurable improvements in development time, cross-feature changes, and AI token/context consumption.

**Until resolved:** mark the decision `PENDING OWNER DECISION`, preserve existing behavior and higher-level safeguards, use documented boundaries for new code, and do not conflate commercial packaging, feature readiness, technical architecture, or deployment topology.

**Approved interim handling:** On 2026-11-06, the Madar product owner approved the preservation-first interim policy for unresolved product, domain-ownership, and architectural decisions. This approves the interim handling policy, not the unresolved decisions themselves.

---

**Review status:** Product-owner approved v0.2; repository activation pending. This is not a claim that current code conforms.
**Approval authority:** Madar product owner.
**Approval date:** 2026-11-06.
**Effective date:** Pending completion of repository adoption gates.
**Approved scope:** `web/frontend`, hosted tenant frontend delivery, frontend-facing FastAPI contracts, and future Madar web frontend modules.
**Repository path:** `docs/architecture/MADAR_FRONTEND_ARCHITECTURE_CONSTITUTION.md`
**Activation requirement:** The governance documents and approved root `AGENTS.md` authority reference must be tracked and committed through a separately authorized Git workflow. Until those repository adoption gates are satisfied, product-owner approval is granted but repository activation remains pending.
