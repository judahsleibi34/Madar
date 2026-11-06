# MADAR Frontend Architecture Decision Record

**ADR ID:** ADR-FE-007
**ADR namespace:** `ADR-FE-NNN` identifies frontend architecture decisions; historical identifiers are unchanged.
**Title:** Incremental Architecture CI Enforcement with Reviewed Legacy Baselines
**Status:** APPROVED — LOGICAL ARCHITECTURE ONLY
**Decision owner:** Madar product owner
**Affected business domains:** All major frontend product domains and platform shared capabilities
**Affected technical modules:** Portal and hosted composition, shared-engine contracts, product entry points, source dependencies, styles, documentation, and future architecture validation
**Prepared:** 2026-11-06
**Product-owner approval:** FINAL ADR DOCUMENT APPROVED — LOGICAL ARCHITECTURE ONLY
**Logical architecture:** APPROVED
**Logical decision date:** 2026-11-06
**Phase 28.2 logical technical-direction approval:** APPROVED BY MADAR PRODUCT OWNER — 2026-11-06; implementation and final tooling selection excluded
**Selected approach:** Reviewed ownership classification, exact-edge legacy baseline, source-graph validation, complementary bundle audits, staged advisory-to-selective-blocking rollout
**Final ADR document status:** APPROVED — LOGICAL ARCHITECTURE ONLY
**Final ADR document approval:** APPROVED
**Final document approval date:** 2026-11-06
**Approval date:** 2026-11-06 for the final ADR document
**Implementation authorization:** NOT AUTHORIZED
**CI activation:** NOT AUTHORIZED
**Tooling selection:** NOT AUTHORIZED
**Legacy baseline creation:** NOT AUTHORIZED
**Repository-wide adoption:** PENDING INDEPENDENT REVIEW AND AUTHORIZED MERGE
**Technical maintainer:** PENDING OWNER DECISION
**CI enforcement owner:** PENDING OWNER DECISION
**Re-evaluation trigger/date:** PENDING OWNER DECISION; candidate triggers include resolver limitations, disputed ownership, repeated false positives, or proposed coverage expansion
**Constitutional impact:** None proposed

The product owner approved the Phase 27 logical policy direction and, separately, the Phase 28.2 logical technical directions on 2026-11-06. The product owner also approved the final corrected ADR wording incorporating Phase 28.3 clarifications A, B and C on 2026-11-06. Final document approval is for logical architecture governance only. No state in this record grants final tooling selection, baseline creation, implementation, CI activation, merge, deployment, or production authority.

This ADR cannot override a constitutional **MUST** or **MUST NOT**. A binding constitutional change requires a separately versioned amendment, documented impact review, explicit product-owner approval, and a recorded effective date and scope. Security, tenant authorization, mandatory root QA, CI, migration, and release controls remain higher authority.

## Context and evidence

### Governance and evidence status

The local constitution is v0.2.1, approved for the local governance record with repository-wide adoption pending. ADR-FE-005 and ADR-FE-006 are approved for logical architecture only; neither authorizes implementation. Relevant ownership records are:

- [Constitution v0.2.1](../MADAR_FRONTEND_ARCHITECTURE_CONSTITUTION.md), especially sections 1, 5, 7, 12–15 and 17.
- [ADR-FE-002 — Shared Forms](ADR-FE-002-PLATFORM-SHARED-FORMS.md).
- [ADR-FE-003 — Shared Data, Analytics and BI](ADR-FE-003-SHARED-DATA-ANALYTICS-AND-BI.md).
- [ADR-FE-004 — Reservations and Calendar](ADR-FE-004-RESERVATIONS-CALENDAR-OWNERSHIP.md).
- [ADR-FE-005 — Hosted Composition](ADR-FE-005-PLATFORM-HOSTED-COMPOSITION.md).
- [ADR-FE-006 — First-Party Module Composition](ADR-FE-006-FIRST-PARTY-MODULE-COMPOSITION.md).
- [Architecture exception register](../EXCEPTIONS.md), which contains no approved exceptions.

The Phase 27 investigation is conversation evidence, not a fabricated repository report. The source references below record its material findings. They describe inspected implementation and invocation, not a recent passing CI run or production observation. Line references are a snapshot and may drift with future edits.

### Existing implemented QA and CI

| Class / mechanism | Verified evidence | Coverage and limits |
|---|---|---|
| SOURCE VALIDATION — ESLint | `web/frontend/eslint.config.js:8–31`; `.github/workflows/frontend-check.yml:44–46` | JS/JSX recommended, Hooks and refresh rules; no domain import-boundary enforcement in the inspected configuration |
| UNIT/INTEGRATION TEST — Vitest | `web/frontend/package.json:17`; `web/frontend/vite.config.js:52–55`; frontend workflow:48–50 | CI runs source tests with jsdom and translation setup; not a complete browser or compatibility proof |
| BUNDLE VALIDATION — Vite | `web/frontend/vite.config.js:57–69`; frontend workflow:52–54 | Production manifest/chunk generation; not logical ownership enforcement |
| SOURCE / DEPENDENCY VALIDATION | `.github/workflows/frontend-check.yml:37–42,56–58` | Dependency-lock check, locked installation and shipped-dependency audit; not cross-domain policy |
| SOURCE VALIDATION — theme contract | `web/frontend/scripts/check-theme-contract.mjs:6–54`; `web/frontend/package.json:8–12` | Build invokes selected literal background/surface checks; exclusions include tokens, specified authoring theme files and tests; not complete CSS, RTL or authored-output isolation |
| BUNDLE VALIDATION — public tenant audit | `web/frontend/scripts/check-public-tenant-bundle.mjs:10–48`; `web/frontend/package.json:8–11` | Build invokes static manifest traversal from tenant entry and Website runtime; selected forbidden chunk labels and existing preload/icon/CSS limits |
| Conditional origin/bundle safeguards | `web/frontend/scripts/check-api-origin.mjs:1–15`; `check-production-bundle.mjs:4–26`; `web/frontend/Dockerfile:13–25` | Build invokes them, but enforcement skips without `MADAR_REQUIRE_PRODUCTION_API_URL`; frontend workflow does not set that flag and Docker argument defaults false |
| SOURCE / UNIT evidence — entry and routes | `web/frontend/src/main.jsx:9–17`; `tenantEntry.test.js:7–35`; `routes/TenantSiteRoutes.storefront.test.jsx:31–81`; `routes/TenantSiteRoutes.preload.test.jsx:48–70` | Distinct portal/tenant loading and selected route/preload behavior; not exhaustive source or emitted-graph isolation |
| SECURITY TEST — backend authority | `web/backend/tests/test_public_site_runtime.py:144,200,215`; `test_publication_isolation.py:116,133`; `test_public_store_resolution.py:149,265`; `test_commercial_authority.py:289` | Existing tests address protected content, publication binding, cached entitlement rechecks and tenant changes; existence does not prove every security property |
| SECURITY / REPOSITORY checks | `.github/workflows/backend-check.yml:28–102`; `web/backend/scripts/run_tests_no_external_network.py:80–89` | Backend preflights, test discovery and network guards are invoked; environment-dependent coverage and current results are not established here |
| RELEASE GATE | `.github/workflows/migration-safety.yml:29–74`; `.github/workflows/full-provider-staging.yml:112–144` | Migration/rehearsal and fresh staging acceptance remain separate; they grant no architecture implementation or production authority |

Existing public-bundle traversal follows manifest `imports`, not recursive `dynamicImports`. It does not independently cover all Academy/learner and Storefront dynamic graphs. Existing limits remain unchanged; this ADR creates no new bundle budget. CI invocation evidence is not evidence of a recent passing execution. No tests or builds were run for this record.

### Verified dependencies and interpretation

| Source evidence | Interpretation and limitation |
|---|---|
| `web/frontend/src/components/ELearning/LearningFormEditor.jsx:4–13,18–25` imports PB factories, FormsTab and CSS and adapts fields | Shared Forms reuse through current physical implementation; not a formal public facade or shared persistence model |
| `web/frontend/src/components/ELearning/LearningFormRenderer.jsx:6–10` imports PB validation, visibility and navigation | Reusable concepts with product-owned submission/validation authority |
| `web/frontend/src/components/ELearning/AcademyBuilderLanding.jsx:6–18` imports PB rendering, routing, themes and styles | Deliberate shared-engine consumption; style and runtime compatibility remain relevant |
| `web/frontend/src/components/ELearning/ELearningAcademy.jsx:2,21` imports Dashboard toast and Storefront SEO implementations | Existing cross-boundary candidates requiring support/ownership classification; not automatically violations |
| `web/frontend/src/services/ecommerceApi.js:8–23` imports Dashboard-located catalog/admin caches | Storefront service source reaches mixed implementation; tree-shaking/download consequences are not proven by this import alone |
| `web/frontend/src/components/PageBuilder/core/PageBuilder.elementRenderer.jsx:8` imports BuilderIcon from PageBuilderIconPicker | An editor-named file is not sufficient evidence of editor-only behavior |
| `web/frontend/src/components/PageBuilder/tabs/index.js:1–9` re-exports tabs | Barrels must be traversed; export presence alone does not establish supported contracts |
| `web/frontend/src/routes/TenantSiteRoutes.jsx:58–70,139–160` composes lazy products and public routes | Legitimate composition, not universal permission to import private product code |

Madar's approved direction is a modular monolith with logical domain ownership and explicit first-party contracts. Shared capabilities and product workflows coexist in Page Builder and Dashboard directories. Directory-wide ownership rules would misclassify some intentional reuse. Architecture CI should eventually detect new unapproved coupling without forcing broad legacy refactoring.

## Decision

### Approved logical enforcement policy

The product owner approved this direction on 2026-11-06:

1. Use reviewed logical ownership rather than blanket directory classification.
2. Preserve reviewed existing dependencies with a narrow exact-edge baseline.
3. Validate new forbidden direct dependencies and new forbidden transitive reachability.
4. Complement and preserve existing public bundle audits.
5. Progress through ownership classification, reviewed baseline, advisory validation, selective blocking and separately approved expansion.
6. Preserve all existing QA, security, tenant-isolation, CI, migration and release gates.
7. Never use architecture checks to grant backend permission, access or entitlement.

**PRESERVE REVIEWED EXISTING EDGES. REJECT NEW FORBIDDEN EDGES AFTER THE RELEVANT RULE IS ACTIVATED.**

No specific baseline, ownership map, parser, resolver, plugin, dependency, check implementation or activation is approved by this direction. New policy must remain consistent with prior ownership decisions and the constitution; it cannot convert all existing imports into approved exceptions.

### Non-goals and authorization exclusions

This record does not authorize CI scripts, baseline files, ownership manifests, fixtures, new dependencies, ESLint/Vite or GitHub Actions changes, application changes, import refactoring, physical module restructuring, facade extraction, or `MODULE.md` creation. It does not authorize a registry, automatic discovery/route generation, runtime plugin loading, module federation or micro-frontends. Commercial authorization redesign, backend permission changes, schema/migration changes, security-gate changes, release bypass, advisory/blocking activation and deployment are excluded. Staging, committing, pushing and merging require separate authorization.

## Alternatives considered

| Alternative | Disposition / trade-off |
|---|---|
| Fail all current forbidden imports | Rejected as the immediate approach: classification and compatibility evidence are incomplete; broad failure risks unrelated legacy remediation |
| Reviewed exact legacy baseline | Selected logical foundation; preserves behavior while making additions visible, but needs review and maintenance |
| Advisory-only diagnostics | Useful calibration, not the permanent enforcement end state; findings alone cannot prevent drift |
| Selected high-confidence blocking | Selected eventual approach after demonstrated accuracy and separate activation approval |
| Blanket folder lint rules | Insufficient for mixed ownership, transitive dependencies, re-exports and CSS; useful only where precise rules are justified |
| Source graph alone | Suitable primary ownership/reachability mechanism, but does not establish emitted chunks, downloads or backend security |
| Bundle audit alone | Protects emitted artifacts but cannot replace source ownership classification or consumer review |
| Hybrid plus manual review | Intended complementary approach: graph validation, suitable lint feedback, bundle audits and semantic review; exact tools remain undecided |
| Documentation/manual review only | Necessary for meaning and contracts; cannot reliably detect all new dependency edges |

## Ownership and consumers

### Logical classification, not directory assignment

| Category | Owners and consumers / physical evidence |
|---|---|
| Platform shared capabilities | Shared Page Builder; Platform Shared Forms; Shared Data and Deterministic Analytics; Platform Hosted Composition |
| Product domains | Website; E-learning / Academy; E-commerce; Data Analysis; Business Intelligence; Reservations; Calendar / Planning |
| Composition | Portal entry/routing and Hosted entry/routing coordinate product-owned behavior through reviewed integration points |
| Shared infrastructure | API/public transport, localization, approved common UI, and media/styling where support is established; not every utility is universally shared |

Shared Page Builder rendering serves Website and Academy. Generic Forms logically belongs to Platform Shared Forms while current implementation remains in PB utilities and E-learning adapters. Website and E-learning retain separate lifecycle, persistence and server validation (ADR-FE-002). Data Analysis and BI independently consume shared data/deterministic capabilities (ADR-FE-003); PB nesting does not determine Data Analysis ownership. Reservations retains booking authority, PB owns presentation integration, and Calendar consumes an authorized read-only projection (ADR-FE-004). Hosted Composition coordinates product-owned runtimes (ADR-FE-005), with explicit manual first-party composition (ADR-FE-006).

Representative mixed paths include `web/frontend/src/components/PageBuilder/`, `components/DashboardBuilder/`, `components/ELearning/`, `components/BusinessIntelligence/`, and `services/ecommerceApi.js` under `web/frontend/src`. Actual file-level ownership and supported interfaces require review; no directory-wide mapping is approved here.

Classification must distinguish logical owner, physical location, supported public entry, private implementation, approved composition dependency, existing legacy dependency, proposed interface and unknown ownership. Technical maintainer and CI accountability remain **PENDING OWNER DECISION**. No existing facade or module document is invented by this record.

## Contracts and compatibility

### Public contract categories

Use ADR-FE-006's categories without treating them as an implemented machine schema:

| Category | Required interpretation |
|---|---|
| EXISTING SUPPORTED CONTRACT | Verified source and consumer evidence plus intended support and proportionate compatibility evidence |
| PROPOSED — NOT IMPLEMENTED | Future contract only; cannot authorize imports from a nonexistent implementation or certify an export |
| LEGACY / UNCLASSIFIED | Existing code without verified public-support status; importability is not public API approval |

Composition roots may have narrowly documented direction exceptions, not broad private access. New or materially changed public APIs require relevant owner/consumer review, including applicable transitive consumers. Unknown ownership is not universally allowed. No immediate extraction of facades is required.

### Legacy baseline governance

Candidate identity fields are canonical importing source, resolved target, edge kind, applicable rule, ownership classification and reviewed legacy status. Storage format, location, canonicalization and independent approval mechanism remain unresolved.

- No blanket directory wildcard exemptions or whole-file permission for additional forbidden imports.
- No automatic baseline expansion when imports change; routine legacy-file edits do not authorize new prohibited dependencies.
- Compare new violating edges against a trusted reviewed baseline. A pull request cannot silently whitelist its own dependency through a self-approved baseline edit.
- Removed edges must not leave reusable allowances; renames/moves require reviewed edge identity reconciliation, including whether the actual dependency changed.
- Preserve distinct direct-edge evidence and shortest verified transitive paths. An unchanged legacy chain may remain supported, but a new edge exposing it from a protected hosted root receives no automatic allowance.
- A baseline allowance is not a public contract or automatically an approved exception. Formal exceptions follow the existing register, scope, product-owner approval and finite expiry/review requirements.
- Exceptions cannot waive tenant safeguards, security, release rules or constitutional requirements. Expiry calls for review; it does not authorize automatic deletion of existing functionality.

No actual baseline is created or approved by this ADR.

### Approved direction A — trusted policy and execution

The approved logical technical direction requires a coherent immutable policy revision, independently approved and executed through a trusted mechanism outside the candidate change's control.

The protected policy scope includes ownership classification, applicable architectural rules, exact legacy allowances, exception information, checker code, locked tooling and resolver dependencies, and activation/coverage state. The candidate source is evaluated as input data; it cannot supply authoritative policy or checker behavior for its own validation.

- Policy revision and candidate revision identities must be explicit, and results must identify both revisions used.
- Policy-sensitive changes require independent review and approval. A changed baseline or ownership map in the candidate cannot by itself authorize a newly forbidden import.
- A candidate workflow change must not silently suppress the trusted validation result.
- Missing or untrusted policy provenance cannot produce a valid compliance PASS for activated coverage. A local Git commit is not automatically an approved policy revision.
- A stale allowance for a deleted edge cannot automatically authorize reintroduction. Renames require reviewed identity reconciliation; legacy allowances remain distinct from approved exceptions.

**UNVERIFIED PREREQUISITES:** Local inspection did not verify remote required-check protection, independent reviewer enforcement or a trusted policy publisher. Exact repository protections, trusted revision selection, policy distribution, baseline format/schema and execution implementation require further evidence and separate approval. No external service or repository permission model is selected, and no complete trust mechanism is claimed to exist.

### Compatibility obligations

Preserve Shared Page Builder editor, preview, published Website, hosted and Academy parity; published schema versions, stable persisted identifiers and historical content; separate Website/E-learning form persistence and server validation; reservation projection boundaries; lazy loading; existing Website/Academy/Storefront behavior; tenant themes and authored-output isolation; accessibility, Arabic/English and RTL/LTR. Source enforcement must not force unrelated legacy changes during routine fixes.

## Tenant, security, and authorization impact

Architecture CI controls dependency direction, not commercial or resource access. FastAPI remains authoritative for tenant resolution, membership, roles, HTTP-method/resource-specific authorization, publication permission, entitlements, operational availability, data ownership and persistence. No frontend manifest, graph, route, hosted adapter or architecture exception grants backend access.

No session, cache, browser storage, public-access or data-exposure behavior changes here. Future relevant changes require tenant/user/resource scoping and security review under existing contracts. A backend service-ownership or authorization-architecture change requires an explicit ADR, security review, compatibility validation and product-owner approval. Architecture CI does not replace backend authorization or tenant-isolation tests.

## Commercial and lifecycle impact

No packaging, subscription, entitlement, product state, hosted availability or deployment topology changes. E-learning and Analytics remain under development; existing commercial packaging is not final. Canonical technical lifecycle identifiers remain `experimental`, `under-development`, `released`, `deprecated`. They are distinct from commercial launch, operational availability, release readiness and runtime permission. This ADR creates no lifecycle state machine.

## Implementation and dependency impact

### Proposed future source validation

Candidate coverage includes static JS/JSX imports, literal dynamic imports, re-exports/barrels, relative paths, verified aliases, index/extensionless resolution, and relevant CSS/side-effect imports. Implementation feasibility review must define package resolution, query suffixes, nonliteral dynamics, unresolved paths, possible aliases, test-only rules, generated/virtual modules and renames/moves. Type-only imports, if introduced, need distinct semantics. No case is claimed solved by this record.

Avoid regex-only parsing as primary assurance when it cannot represent the graph correctly. Evaluate available parsing/resolution facilities later; no parser, ESLint plugin or new dependency is selected. ESLint may provide complementary feedback where it can express approved rules. Do not maintain conflicting sources of rule authority.

### Approved direction C — extraction and bounded resolution feasibility

The preferred initial feasibility approach is to evaluate ESLint's supported JS/JSX programmatic rule/parsing interface for dependency-edge extraction, combined with a bounded, repository-owned source resolver whose behavior is validated against actual Madar/Vite resolution semantics. This approves an evaluation direction, not final tooling or implementation.

ESLint is a direct frontend dependency. Declarations and locked versions differ: `web/frontend/package.json:55–62` declares ESLint `^10.2.1` and Vite `^8.0.10`, while `web/frontend/package-lock.json:1682` and `3237` resolve ESLint `10.8.1` and Vite `8.2.1`. Compatibility must be verified against the locked installation. A transitive parser's presence is not permission to import it as an undeclared stable dependency; no installed-package or fixture success is claimed.

Parsing must represent re-exports, literal dynamic imports and static/dynamic distinctions. Relevant CSS imports, side effects and CSS parsing need separate coverage validation. Unknown aliases, query suffixes, virtual modules, nonliteral imports and unsupported syntax must remain visible; unsupported resolution cannot silently count as complete architectural compliance. Resolver fixtures and parity evidence against actual Vite behavior are required before blocking activation.

Vite configuration and plugin execution may have side effects. The current configuration calls `loadEnv` (`web/frontend/vite.config.js:27–28`); candidate-controlled configuration must not be executed with elevated trust merely to resolve imports. Final parser/resolver APIs or libraries, CSS parser, dependency additions, ownership schema, checker paths, CI invocation, fixture implementation and operational performance remain unapproved and require evidence. ESLint extraction has not passed Madar fixtures, and complete AST/CSS coverage is not established.

### Direct and transitive examples

**Direct example:** a new Storefront import of a verified Dashboard-private utility should BLOCK after that rule is approved and active. Existing mixed-directory utilities must first be classified.

**Transitive example:** a new hosted dependency exposes an old admin/editor chain. New forbidden reachability should BLOCK after the hosted rule is validated and active, even if downstream edges were already present. Re-exports cannot conceal forbidden targets. These examples do not declare all current cross-domain imports violations.

### Hosted and portal graphs

Retain separate portal shell and tenant entries, Website runtime, standalone public Forms, Academy/learner runtime, Storefront and editor-only boundaries. Future checks should consider portal shells, admin routes, Dashboard-private state, editor workspaces, admin-only APIs, portal-only CSS, eager unrelated products, and static/dynamic transitive paths. A Dashboard-named path is not automatically prohibited. Preserve supported shared utilities and lazy loading.

| Evidence layer | Meaning / limit |
|---|---|
| Source graph reachability | Potential source dependency; not proof of emitted or downloaded code |
| Emitted bundle reachability | Build-produced static/dynamic chunk links; not actual navigation downloads |
| Actual browser downloads | Observed navigation/network consumption; requires browser measurement |
| Backend authorization | Allowed server resources and operations; not established by frontend isolation |

Source checks do not replace Vite/bundle validation. Existing audits remain; implementation and activation of additional Academy/Storefront coverage need separate approval. No new bundle-size limit is inferred.

### Approved direction B — extend existing hosted manifest auditing

Extend the existing Vite manifest-based tenant audit with separately attributable hosted product-root reports, while retaining all current audit roots, budgets, forbidden patterns and failure behavior unchanged. This is the intended technical direction, not authorization for build or audit code changes or an independent replacement system.

| Reporting scope | Intended semantics and verified source relationship |
|---|---|
| Common hosted entry | Report the static closure of `web/frontend/src/tenantMain.jsx` and bootstrap dependencies; current imports appear at lines 52–60 |
| Website | Report `web/frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.jsx` static closure and relevant dynamic descendants; loader is `web/frontend/src/tenantRuntimePreload.js:17–19` |
| Standalone Forms | The route consumes Website runtime (`web/frontend/src/routes/TenantSiteRoutes.jsx:147`); do not invent an independent emitted root |
| Academy and learner | Routes load distinct exports of `web/frontend/src/components/ELearning/ELearningAcademy.jsx` (`web/frontend/src/routes/TenantSiteRoutes.jsx:66–70`); report the shared source/emitted module relationship where applicable, with separate functional loading scenarios, not invented separate output chunks |
| Storefront | Report `web/frontend/src/components/EcommerceStore/EcommerceStorefront.jsx` and its dependencies; loader is `web/frontend/src/tenantRuntimePreload.js:19` |
| Shared chunks | Attribute each common chunk to all consuming roots while deduplicating union totals |
| CSS | Report associated emitted CSS and side-effect relationships only where manifest evidence is sufficient; retain explicit attribution limitations |

Keep static import closures, dynamically reachable descendants and actual browser downloads distinct. Dynamic reachability does not mean eager download. Preserve existing lazy loading, Website/Forms, Academy/learner and Storefront behavior, Shared Page Builder rendering, tenant themes, CSS/font contracts, Arabic/English and RTL/LTR.

Website runtime contains draft-preview imports of `PageBuilder.api` and potentially `elearningSettings` (`web/frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.jsx:825–844`), and lazily loads `AcademyBuilderPreviewProvider` at line 468. Preserve and explicitly classify these existing dependencies. Do not indiscriminately extend existing static deny patterns to every dynamic descendant. Reviewed classification and detection of newly exposed forbidden reachability remain required; existing preview dependencies do not grant blanket permission for new edges.

Manifest chunk names alone may not expose every source module in a merged chunk. If module-level attribution cannot be established, report the limitation rather than claiming full isolation. Actual emitted graphs, module attribution accuracy, browser downloads and implementation accuracy remain unverified. Phase 28.2 ran no build and measured no bundle size. Existing thresholds remain unchanged; no new Academy/Storefront budget is approved.

### Future route and documentation coverage

Route checks are separately approved expansion, with categories **EXACT CONFLICT**, **POTENTIAL OVERLAP**, **INTENTIONAL FALLBACK**, **UNKNOWN / REQUIRES REVIEW**. Preserve legacy redirects, Academy/learner, Storefront, Forms and Website catch-all behavior (`web/frontend/src/routes/TenantSiteRoutes.jsx:139–160`). Matching depends on React Router context and specificity, not declaration order alone. Reserved hostname labels are not automatically reserved URL paths. No route generation or discovery is authorized.

Future documentation checks may verify technical owner, canonical lifecycle, supported entry status/consumers, stale paths, integration references, dependencies and QA ownership. New products need reviewed ownership documentation under approved rollout; existing products receive staged inventory, not an immediate universal gate. Shared capabilities need explicit consumer/compatibility review; small internal utilities do not automatically need standalone `MODULE.md`. Machine-readable data requires a concrete approved validator and separate approval; it is not a runtime registry.

## QA, CI, and release impact

Existing checks remain fully effective. Any later implementation follows root `AGENTS.md` and [the merge contract](../../MADAR_AUTO_DEPLOY_MERGE_CONTRACT.md) and [production release policy](../../production-release-policy.md). Exact-source verification and applicable protected-tooling, security, migration and acceptance requirements remain in force. Passing CI grants no deployment authority. Architecture reporting supplements every required root QA report field.

- **Existing architecture checks:** Specific entry/route tests, theme/source and public-bundle audits described above; no verified domain import-boundary gate.
- **Proposed architecture checks:** Source ownership/reachability validation with reviewed legacy allowances, complementary lint and expanded bundle coverage; route/documentation checks are later options.
- **Accountable CI enforcement owner:** PENDING OWNER DECISION.
- **Planned verification milestones:** PENDING OWNER DECISION; candidate stages below are not scheduled commitments.
- **Review trigger/date:** PENDING OWNER DECISION.

Future architecture CI automation is not a prerequisite for Constitution v0.2 adoption; actual activation still requires the applicable governance adoption and release reviews.

### Proposed stages, each requiring separate approval

| Stage | Required work / exit evidence before progression |
|---|---|
| 0 — Ownership classification | Review actual supported contracts, private paths, composition dependencies and legacy candidates; resolve or explicitly retain unknowns |
| 1 — Reviewed baseline | Independently review narrow exact-edge allowances and trusted comparison semantics |
| 2 — Advisory validation | Validate resolver and positive/negative fixtures; observe false positives and unresolved imports without downgrading existing gates |
| 3 — Selective blocking | Demonstrate accuracy; approve trusted baseline; assign maintainer; confirm exception and failure/rollback procedures; complete required QA/release review |
| 4 — Coverage expansion | Separately approve Academy/Storefront graphs, routes, documentation or additional shared contracts based on evidence |

No stage activates automatically upon ADR approval. Security/release requirements cannot be made advisory. Exact invocation location, local command, artifact retention and enforcement thresholds require later review; no workflow change is specified as already approved.

### Future validation matrix — not executed

BLOCK applies only after the specific check is separately approved and activated. Unknown ownership/unresolvable imports are never silently classified as PASS.

| Case | Future expected classification |
|---|---|
| Allowed supported shared API | ALLOW |
| New prohibited product-private import | BLOCK |
| Exact reviewed legacy edge | ALLOW with legacy status visible |
| New forbidden edge in legacy file | BLOCK |
| Hosted import of verified portal-only code | BLOCK |
| New forbidden transitive hosted-to-admin path | BLOCK |
| Permitted literal dynamic import preserving laziness | ALLOW; unresolved expression REQUIRES REVIEW |
| Re-export concealing private dependency | BLOCK |
| Portal-only CSS in hosted graph | BLOCK when classified; otherwise REQUIRES REVIEW |
| Exact conflicting hosted routes | BLOCK after route-check activation; potential overlap REQUIRES REVIEW |
| Intentional Website catch-all | ALLOW |
| Unknown ownership | REQUIRES REVIEW |
| Missing required new-module metadata | BLOCK after scoped rollout; uncovered legacy WARN |
| Approved scoped exception | ALLOW only within scope and validity |
| Expired/unapproved exception for new forbidden use | BLOCK; existing behavior requires recorded review, not automatic deletion |
| Rename/move changing baseline identity | REQUIRES REVIEW; no implicit expansion |
| Test-only dependency | ALLOW under approved test rules; prohibited runtime-to-test edge BLOCK |
| Proposed facade claimed as supported implementation | BLOCK contract validation |

Fixtures must cover direct/transitive differences, resolver failures, baseline drift and protected-root reachability. No fixtures or scripts are created now. Later consumer QA remains proportionate: rendering/forms, historical schemas/responses, themes/RTL/accessibility, routing/lazy loading, tenant/entitlement security and applicable regression/release checks. No unexecuted test is reported as passed.

### Measurement and maintenance

Candidate static measures: prohibited additions, legacy edge count/drift, unresolved imports, false positives, diagnostic quality/time to diagnose, checker duration, exception expiry, source reachability, route findings and stale documentation. Emitted chunk/CSS coverage requires a build; actual downloads require browser measurement; affected-consumer regressions require relevant tests.

No runtime/maintenance budget, accepted false-positive rate, new bundle budget, performance gain or token-saving percentage is established. Measurements and accountable maintenance must precede claims of improvement.

## Rollback, migration, and failure handling

Activated blocking violations must produce failing process status. Advisory findings remain visible. Tool crashes are not successful architecture validation; unknown ownership is not compliance. Diagnostics should show importer/location, resolved target, rule, owners, legacy/exception status and shortest relevant verified chain.

False positives require a reproducible example and reviewed correction. Baseline changes and exceptions cannot silently bypass failures. Formal exceptions remain scoped, approved and time-limited under the existing register; neither baseline nor exception amends higher rules.

Rollback/withdrawal of a new architecture check needs separate authorization, with retained diagnostic evidence and review of affected scope. Existing security, QA and release gates remain unaffected. No persisted data migration or production rollback is authorized. Physical remediation of legacy coupling is a separate compatibility-reviewed task.

## Risks and unresolved questions

### Consequences and trade-offs

Expected benefits are visibility of new forbidden dependencies, preservation of legacy behavior, clearer ownership, detection of hosted portal/admin reachability and better shared-contract review without a universal registry. These are intended outcomes, not measured protection or savings.

Costs include ownership classification, exact-baseline upkeep, resolver fixtures, ambiguous transitive findings, possible CI overhead and false-positive investigation. Legacy coupling remains until separately remediated. Bundle/browser evidence remains necessary; advisory checks alone do not prevent drift.

### Open owner decisions

All remain **PENDING OWNER DECISION**:

1. Exact initial enforcement boundaries.
2. Approved source ownership mapping.
3. Final graph parser/resolver selection and accuracy evidence, following the approved ESLint extraction/bounded-resolution evaluation direction; CSS parser and coverage remain open.
4. Actual baseline file format.
5. Actual immutable policy-bundle implementation, trusted revision selection/distribution, baseline storage and independent review mechanism; remote enforcement and trusted publisher verification remain outstanding.
6. Architecture-CI technical maintainer and accountable enforcement owner.
7. Exception approval/review workflow details, within existing product-owner authority and register constraints.
8. CI activation timing.
9. Advisory calibration period.
10. Accepted false-positive criteria.
11. Runtime and maintenance budget.
12. Manifest module attribution, actual Academy/Storefront emitted graphs and browser downloads, and any additional budgets after measurement; current budgets are unchanged.
13. Route-collision scope.
14. Module-documentation validation rollout order.
15. Rollback authority and procedure within existing higher safeguards.
16. Release integration and required independent approvals.
17. Actual governance-document merge/adoption.

No reviewer identity, commit reference, implementation deadline, release date or repository-wide effective date is inferred. Tooling and coverage accuracy remain unverified until a separately authorized implementation and validation phase.

## Approval record

- **Product-owner decision:** FINAL ADR DOCUMENT APPROVED — LOGICAL ARCHITECTURE ONLY; prior logical enforcement policy and Phase 28.2 technical-direction approvals remain in effect within their recorded scope.
- **Decision date:** 2026-11-06 for the logical policy direction.
- **Approved scope:** Reviewed logical classification, exact-edge legacy preservation, new direct/transitive dependency validation, complementary bundle audits and incremental enforcement direction.
- **Conditions:** Existing security, tenant isolation, QA, CI, migration and release controls remain fully effective. Each implementation/activation stage needs separate approval.
- **Final ADR document status:** APPROVED — LOGICAL ARCHITECTURE ONLY.
- **Final ADR document approval:** APPROVED.
- **Final document approval date:** 2026-11-06.
- **Implementation authorization:** NOT AUTHORIZED.
- **CI activation:** NOT AUTHORIZED.
- **Tooling selection:** NOT AUTHORIZED.
- **Legacy baseline creation:** NOT AUTHORIZED.
- **Repository-wide adoption:** PENDING INDEPENDENT REVIEW AND AUTHORIZED MERGE.
- **Related exception IDs:** None; no exception is created or approved.
- **Related constitutional amendment:** None proposed; Constitution v0.2.1 remains unchanged.
- **Supersedes / superseded by:** None.

### Phase 28.2 technical-direction approval history

- **Event:** PHASE 28.2 LOGICAL TECHNICAL-DIRECTION APPROVAL.
- **Authority:** Madar product owner.
- **Date:** 2026-11-06.
- **Approved scope:** Independently approved immutable policy revision and trusted execution direction; extension of the existing manifest audit with product-root static/dynamic reporting; ESLint JS/JSX extraction feasibility direction plus bounded validated resolution.
- **Excluded:** Final technical tooling selection, repository-control implementation, CSS parser selection, baseline creation, checker development, CI activation, application changes, Git and deployment actions.
- **Approval distinction at this historical event:** This event was separate from the original Phase 27 logical policy approval recorded above. Final complete ADR wording was PROPOSED with final document approval date N/A; implementation and CI activation were NOT AUTHORIZED; repository adoption was pending final approval, independent review and authorized merge. The subsequent final-document approval is recorded separately below.

### Final document approval history

- **Event:** FINAL ADR DOCUMENT APPROVAL.
- **Approval authority:** Madar product owner.
- **Approval date:** 2026-11-06.
- **Approved document:** ADR-FE-007 incorporating Phase 28.3 clarifications A, B and C, following the Phase 28.1 independent full-text review and Phase 28.2 technical-direction investigation. Phase 28.1 identified no BLOCKER, MAJOR or required MINOR correction.
- **Approved scope:** Logical governance for reviewed ownership mapping; exact-edge legacy allowances; source-graph validation of new direct and transitive violations; complementary public/hosted bundle audits; staged advisory-to-selective-blocking enforcement; independently approved immutable policy revision and trusted-execution direction; product-root emitted-graph reporting with static/dynamic distinctions; ESLint JS/JSX extraction as a preferred feasibility direction with bounded, fixture-validated resolution; preservation of backend authorization, tenant security, QA, CI and release gates; and the documented constraints, trade-offs, prerequisites, non-goals and unresolved implementation decisions. No specific ownership map, baseline or validated tool implementation is approved by this scope.
- **Explicitly not approved:** Application implementation, CI checker creation or activation, ownership manifest creation, baseline generation, final parser/resolver selection, CSS parser selection, dependency installation, new bundle budgets, CI workflow modification, source refactoring, repository-wide deployment or adoption.
- **Implementation authorization:** NOT AUTHORIZED.
- **CI activation:** NOT AUTHORIZED.
- **Tooling selection:** NOT AUTHORIZED.
- **Legacy baseline creation:** NOT AUTHORIZED.
- **Repository adoption:** PENDING INDEPENDENT REVIEW AND AUTHORIZED MERGE.

Final document approval does not activate enforcement or establish implementation accuracy. Stop for product-owner review; repository-wide adoption remains pending independent review and authorized merge.
