# Establish Platform Shared Forms Through Staged Logical Independence

**ADR ID:** ADR-FE-002
**ADR namespace:** `ADR-FE-NNN` identifies Madar frontend architecture decisions; historical ADR identifiers outside this namespace are unchanged.
**Status:** APPROVED — LOGICAL ARCHITECTURE ONLY
**Decision owner:** Madar product owner
**Approval authority:** Madar product owner
**Affected business domains:** Platform Shared Forms, Website Forms, E-learning
**Affected technical modules:** Shared Page Builder Forms integration, website hosted form runtime and response management, E-learning form editor/runtime and response management
**Prepared:** 2026-11-06
**Product-owner approval:** LOGICAL DECISION AND FINAL ADR WORDING APPROVED — LOGICAL ARCHITECTURE ONLY
**Approval date:** 2026-11-06
**Final ADR document approval:** APPROVED
**Final document approval date:** 2026-11-06
**Approved scope:** Logical ownership and staged implementation direction for generic frontend Forms capabilities across Madar
**Implementation authorization:** NOT AUTHORIZED
**Repository-wide adoption:** PENDING INDEPENDENT REVIEW AND AUTHORIZED MERGE
**Accountable technical maintainer:** PENDING OWNER DECISION
**Re-evaluation trigger/date:** A proposed physical Forms extraction, a new supported cross-product editor or renderer contract, or a material change to Forms ownership or persistence boundaries
**Constitutional impact:** No constitutional amendment required

## Context and evidence

### Verified current state

- Page Builder currently provides field and form factories in `web/frontend/src/components/PageBuilder/core/PageBuilder.factories.js:25-91`, pure conditional-visibility behavior in `web/frontend/src/components/PageBuilder/runtime/formVisibility.js:1-17`, client-side runtime validation in `web/frontend/src/components/PageBuilder/runtime/formValidation.js:27-105`, and page-navigation behavior in `web/frontend/src/components/PageBuilder/runtime/formPageNavigation.js:1-17`.
- E-learning directly imports Page Builder field creation, `FormsTab`, Page Builder styles, validation, visibility, localization, and page-navigation implementations (`web/frontend/src/components/ELearning/LearningFormEditor.jsx:4-25`; `web/frontend/src/components/ELearning/LearningFormRenderer.jsx:6-11`).
- The E-learning editor adapts its schema into a synthetic Page Builder-shaped `project` and supplies a large set of callbacks to `FormsTab` (`web/frontend/src/components/ELearning/LearningFormEditor.jsx:78-97`; `web/frontend/src/components/ELearning/LearningFormEditor.jsx:193-203`). This demonstrates current implementation coupling; it is not evidence of an approved public Page Builder Forms contract.
- E-learning saves through its own API adapter rather than Page Builder persistence (`web/frontend/src/components/ELearning/LearningFormEditor.jsx:162-172`). Its renderer submits to the E-learning public academy endpoint unless an explicitly supplied product path is used (`web/frontend/src/components/ELearning/LearningFormRenderer.jsx:30-37`).
- The E-learning backend explicitly identifies its persistence as independent, validates its own schema and answers, and gates its own entitlement (`web/backend/services/elearning_forms_service.py:1-68`; `web/backend/services/elearning_forms_service.py:132-180`). Its authenticated and public endpoints use distinct E-learning routers and verify academy publication and access before rendering or submission (`web/backend/routes/elearning_forms_routes.py:1-15`; `web/backend/routes/elearning_forms_routes.py:87-122`).
- Website forms use separate public draft and submission operations in `web/backend/routes/public_site_routes.py:4833-5151`, including website-specific Builder form persistence and historical response handling.

The pure visibility, validation, and navigation behavior does not require a page or project object. This supports a page-independent logical owner for generic Forms semantics. At the same time, the current editor integration, styles, schemas, runtime behavior, and persistence paths are compatibility-sensitive. Immediate extraction would change several consumers and trust boundaries without a verified public contract or complete cross-consumer conformance suite.

### Interpretation adopted by this decision

Madar benefits from one accountable logical owner for reusable frontend Forms semantics while retaining product-specific workflows, response management, backend validation, and persistence. Staged logical independence establishes that ownership without presenting current internal imports as stable public interfaces or authorizing physical restructuring.

### Unknowns retained

- The accountable technical maintainer is `PENDING OWNER DECISION`.
- No cross-product `FormEditor`, `FormRenderer`, persisted `FormSchema`, or other named Shared Forms public interface is approved by this ADR.
- The location, names, packaging, and rollout sequence of future supported interfaces remain subject to evidence, compatibility validation, and separate implementation approval.

## Decision

Madar establishes **Platform Shared Forms** as the logical owner of reusable frontend Forms concepts through staged independence.

### Platform Shared Forms owns

- shared field descriptors and supported field types;
- common form and section presentation concepts;
- conditional visibility semantics;
- client-side UX validation;
- multi-page navigation semantics;
- English/Arabic localization and RTL/LTR behavior;
- common form interaction behavior;
- future reviewed editing primitives and accessible field controls;
- product integration contracts; and
- cross-consumer compatibility expectations.

Future editing primitives and field controls are approved areas of logical responsibility, not existing or approved public contracts.

### Shared Page Builder owns

- embedding forms in authored page and project schemas;
- form blocks and connected form identifiers;
- page placement;
- authored website form-theme integration;
- website preview integration;
- published Page Builder compatibility; and
- Page Builder-specific Forms integration.

Shared Page Builder is a consumer of Platform Shared Forms concepts, not their permanent logical owner.

### Website Forms owns

- website form lifecycle;
- website drafts and submissions;
- website-specific response-management pages;
- historical response presentation;
- website quiz and related business behavior;
- website-facing API operations; and
- product-specific permissions and actions.

### E-learning owns

- learning form lifecycle and versioning;
- academy access and eligibility;
- learning applications and programme workflows;
- E-learning submissions;
- E-learning-specific response-management pages;
- applicant decisions, notes, files, and related actions; and
- learning-facing API operations.

### FastAPI remains authoritative for

- tenant identity and isolation;
- authentication and authorization;
- entitlements and resource access;
- server-side validation;
- product-specific persistence;
- submission visibility and permissions;
- historical versions and records; and
- business-specific processing and decisions.

Frontend module metadata must never become an authorization or persistence authority.

## Staged independence and dependency direction

Logical ownership is approved now. Existing physical files remain in place, existing Page Builder and E-learning reuse is preserved, and existing adapters may remain temporarily. No immediate folder restructuring is required.

The intended logical dependency direction is:

```text
Platform Shared Forms
  <- Shared Page Builder
      <- Website Forms integration

Platform Shared Forms
  <- E-learning Forms integration
```

Future products may consume approved Shared Forms contracts through product-owned adapters. New consumers should use approved shared interfaces only after those interfaces actually exist. Public contracts must be verified before extraction, and compatibility plus cross-consumer tests are required before moving implementations.

Form collection UI may be shared while product response-management pages remain different. A frontend navigation destination is separate from a backend persistence destination. Persistence remains controlled by the relevant authorized FastAPI operation. Untrusted form metadata must not select arbitrary tables, tenants, endpoints, or permissions.

## Non-goals and exclusions

This ADR does **not** authorize:

- replacing `FormsTab`;
- creating a universal `FormEditor`;
- creating a universal `FormRenderer`;
- creating a shared response-management page;
- combining website and E-learning submission tables;
- introducing a common persisted `FormSchema`;
- changing form or field identifiers or historical records;
- changing server-side validation or permissions;
- changing website quiz or learning eligibility rules;
- introducing runtime plugins or new dependencies;
- architecture migration or physical extraction;
- changing application code, schemas, routes, persistence, or deployment; or
- treating any current internal import as an approved public interface solely because it is reusable.

## Alternatives considered

### Shared Page Builder permanently owns generic Forms concepts

Rejected as the long-term logical boundary. Current code location and substantial Page Builder reuse are verified, but page-independent semantics and E-learning consumption show that generic concepts serve more than authored websites. Permanent Page Builder ownership would make product-neutral semantics depend logically on one consumer's authoring workflow.

### Immediate independent Shared Forms extraction

Rejected for this decision. Existing E-learning integration constructs Page Builder-shaped workspace state, current consumers import internal implementations directly, and website and E-learning persistence and validation remain distinct. Immediate extraction would create avoidable compatibility and regression risk before supported contracts and cross-consumer tests are established.

### Staged logical independence

Approved. It establishes accountable logical ownership and future dependency direction while preserving current runtime behavior, physical implementation, data, and release safeguards.

## Ownership and consumers

| Capability | Logical owner | Known consumers or integrations |
|---|---|---|
| Generic frontend form semantics | Platform Shared Forms | Shared Page Builder, Website Forms, E-learning Forms, future reviewed products |
| Authored form embedding and published page compatibility | Shared Page Builder | Website authoring, preview, hosted websites, academy composition |
| Website form workflow and responses | Website Forms | Hosted website runtime, website response-management UI |
| Learning form workflow and responses | E-learning | Academy runtime, owners/instructors, applicants/learners |
| Tenant, access, validation, and persistence authority | FastAPI product operations | All authenticated and public form consumers |

Cross-domain changes require documented review from affected owners. Where an accountable technical maintainer has not been established, preserve existing contracts and behavior under the constitution's preservation-first interim rule.

## Contracts and compatibility

No new public export name or persisted schema is created by this ADR. Before any future implementation is described as a Shared Forms public contract, review must identify its provider, consumers, data shape, versioning, error behavior, localization/accessibility behavior, and compatibility tests.

Any implementation work must preserve or explicitly validate:

- existing published website forms;
- existing E-learning forms;
- historical submissions and version snapshots;
- form and field identifiers;
- conditional-field evaluation;
- multi-page navigation and draft/resume behavior;
- localized labels and options, English/Arabic, and RTL/LTR;
- website quizzes;
- academy eligibility and application flows;
- Page Builder editor, preview, published output, and hosted/public runtime;
- tenant and resource isolation; and
- separate website and E-learning persistence and server-side validation.

Compatibility work must not relabel historical answers with a current schema, silently change stored meaning, or route one product's submissions into another product's persistence.

## Tenant, security, and authorization impact

This logical ownership decision does not change any trust boundary. FastAPI remains the backend authority, including for public access checks, authenticated membership, tenant scope, entitlements, resource ownership, submission visibility, and server-side validation.

Future Shared Forms frontend contracts may express presentation and interaction metadata only. They must not grant access, choose authoritative tenant identity, bypass product-specific eligibility, or direct persistence based on untrusted metadata. Any future change to backend service ownership or authorization architecture requires a separate ADR, security review, compatibility validation, and product-owner approval.

## Commercial and lifecycle impact

This ADR does not define a commercial Forms product, subscription, entitlement, navigation item, or launch state. Platform Shared Forms is a logical shared capability, not a commercial module. E-learning remains under development, and neither its current packaging nor Analytics packaging is changed by this decision.

## Implementation and dependency impact

Implementation is **NOT AUTHORIZED**. This ADR creates no export, adapter, directory, package, dependency, route, registry, plugin, schema, or migration.

A future implementation proposal must inventory current provider and consumer call sites, distinguish public contracts from private implementation, identify affected CSS and state ownership, preserve product adapters and backend boundaries, and obtain the review and authorization required by the constitution and repository workflow.

## QA, CI, and release impact

No application tests were executed for this documentation-only decision. Existing evidence includes:

- `web/frontend/src/components/PageBuilder/runtime/formValidation.test.js` for required values, types, options, files, and aggregate errors;
- `web/frontend/src/components/PageBuilder/runtime/formPageNavigation.test.js` for completed/current page behavior and resumed navigation;
- `web/frontend/src/components/PageBuilder/runtime/formDraftStorage.test.js` for partial answers, resume pages, and draft removal;
- `web/frontend/src/components/PageBuilder/core/PageBuilder.formHandlers.test.js` for form/page placement and disconnection behavior;
- `web/frontend/src/components/ELearning/LearningFormEditor.test.jsx` for Page Builder UI reuse, independent schemas, conditional logic, preview, localization, and RTL;
- `web/frontend/src/components/ELearning/LearningForms.test.jsx` for access, conditional rendering, independent submission, academy binding, historical labels, and Arabic validation;
- `web/frontend/src/components/ELearning/LearningFormSubmissions.test.jsx` for historical versions, files, response grouping, notes, and separation from Builder persistence;
- `web/backend/tests/test_builder_form_drafts.py` and `web/backend/tests/test_builder_form_submissions.py` for website form persistence behavior; and
- `web/backend/tests/test_elearning_forms.py` and `web/backend/tests/test_elearning_forms_database.py` for learning form access, validation, persistence, and database contracts.

Missing conformance coverage includes one declared, supported contract suite run against every Shared Forms consumer because no such public contract is yet approved or implemented. Any future physical extraction or supported editor/renderer contract requires compatibility coverage across website and E-learning consumers before existing implementations move.

- **Existing architecture checks:** Existing form unit, component, backend, tenant/access, publication, localization, RTL, and release checks listed above; architectural boundary enforcement is not claimed.
- **Proposed architecture checks:** Cross-consumer conformance and forbidden-private-import checks require a separately reviewed implementation proposal.
- **Accountable CI enforcement owner:** PENDING OWNER DECISION
- **Planned verification milestones:** PENDING OWNER DECISION
- **Review trigger/date:** A proposed physical extraction or supported cross-product editor/renderer contract; no calendar date approved

All applicable root `AGENTS.md`, security, tenant-authorization, QA, CI, migration, deployment, and production-release requirements remain unchanged.

## Rollback, migration, and failure handling

There is no runtime rollback or data migration because this ADR authorizes no implementation. Before implementation, the product owner may supersede or withdraw this logical decision through the governed ADR process. After any separately authorized persisted or published change, rollback and compatibility requirements must be defined by that change; this ADR grants no production mutation authority.

## Risks and unresolved questions

- Accountable technical maintainer: `PENDING OWNER DECISION`.
- Exact Shared Forms public interfaces, names, and source locations: not approved.
- Whether a shared editor or renderer is justified: unresolved and not required by this decision.
- Physical extraction sequence and legacy-import baseline: not approved.
- Cross-consumer conformance test design and architecture CI accountability: `PENDING OWNER DECISION`.
- Future consumers and any commercial packaging: unresolved.
- Compatibility validation must precede changes to current internal imports, schemas, identifiers, persistence, validation, or runtime behavior.

## Approval record

- **Product-owner decision:** APPROVED
- **Decision date:** 2026-11-06
- **Approved scope:** Platform Shared Forms logical ownership and staged independence only
- **Implementation:** NOT AUTHORIZED
- **Conditions:** Preserve existing runtime behavior and data; preserve all server-side access and validation; require separate review and approval for changes to contracts, physical implementation, or schemas
- **Related exception IDs:** None
- **Related constitutional amendment:** None
- **Supersedes / superseded by:** None

### Final document approval history

- **Event:** FINAL ADR DOCUMENT APPROVAL
- **Authority:** Madar product owner
- **Date:** 2026-11-06
- **Document:** ADR-FE-002
- **Approved scope:** Final wording of the existing logical Platform Shared Forms architecture, including product-specific persistence, compatibility, non-goals, and staged independence.
- **Review basis:** Complete current wording independently reviewed in Phase 29.1.
- **Approval distinction:** This final-wording approval is separate from the earlier logical direction approval recorded above; its historical date and scope remain unchanged.
- **Implementation:** NOT AUTHORIZED
- **Repository adoption:** PENDING INDEPENDENT REVIEW AND AUTHORIZED MERGE
