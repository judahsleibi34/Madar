# Establish Independent Data Analysis and Business Intelligence Domains over Shared Data and Deterministic Analytics

**ADR ID:** ADR-FE-003
**ADR namespace:** `ADR-FE-NNN` identifies Madar frontend architecture decisions; historical ADR identifiers outside this namespace are unchanged.
**Status:** APPROVED — LOGICAL ARCHITECTURE ONLY
**Decision owner:** Madar product owner
**Approval authority:** Madar product owner
**Affected business domains:** Data Analysis, Business Intelligence, Website Forms, E-learning, and future source-product domains
**Affected technical modules:** Data Projects, Data Analysis Workspace, Data Sources, Business Intelligence Workspace, dataset/version services, deterministic analytics, and BI reporting services
**Prepared:** 2026-11-06
**Product-owner approval:** LOGICAL DECISION AND FINAL ADR WORDING APPROVED — LOGICAL ARCHITECTURE ONLY
**Approval date:** 2026-11-06
**Final ADR document approval:** APPROVED
**Final document approval date:** 2026-11-06
**Approved scope:** Logical domain and shared-capability ownership
**Implementation authorization:** NOT AUTHORIZED
**Repository-wide adoption:** PENDING INDEPENDENT REVIEW AND AUTHORIZED MERGE
**Accountable technical maintainers:** PENDING OWNER DECISION
**Re-evaluation triggers:** A proposed physical domain extraction; a new shared analytics contract; changes to dataset/version ownership; a proposed unified chart/report capability; cross-product AI integration; or changes to authorization or deployment boundaries
**Constitutional impact:** No constitutional amendment required

## Context and evidence

### Verified current state

- Data Projects currently reuse Page Builder project creation, persistence, and routing. A data project is identified through `workspaceKind: "data"` or a legacy data-project slug (`web/frontend/src/components/DataProjects/DataProjectsPage.jsx:5-15`, `web/frontend/src/components/DataProjects/DataProjectsPage.jsx:74-91`).
- The Data Analysis Workspace is hosted within the Page Builder workspace graph and receives a project, user, project identifier, and form-related callbacks (`web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/components/DataAnalysisWorkspace.jsx:92-123`; `web/frontend/src/components/PageBuilder/tabs/DataTab.jsx:1-12`).
- Data Analysis provides interactive source selection, upload/reopen, cleaning and inspection, ad hoc analysis, visualization authoring, deterministic assistance, and browser-local report drafts (`web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/components/DataAnalysisWorkspace.jsx:1404-1625`; `web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/components/DataAnalysisWorkspace.jsx:1689-1840`; `web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/components/ReportBuilderStep.jsx:153-260`).
- Business Intelligence has a distinct frontend workspace. It consumes project datasets and immutable versions, runs deterministic metrics, and manages persistent dashboards, widgets, sharing, scheduled reports, exports, delivery, and retention (`web/frontend/src/components/BusinessIntelligence/BusinessIntelligenceWorkspace.jsx:536-690`; `web/frontend/src/components/BusinessIntelligence/BusinessIntelligenceWorkspace.jsx:697-824`; `web/frontend/src/components/BusinessIntelligence/BusinessIntelligenceWorkspace.jsx:879-930`).
- FastAPI registers data, cleaning, analysis, and visualization routers behind normal-user authentication (`web/backend/app.py:567-572`). The shared storage-scope function verifies the path user, authenticated tenant/user context, the `data_import` entitlement, and the account work fence (`web/backend/data_analysis/routes/data_routes.py:211-229`).
- Persistent project dataset metadata and immutable versions are tenant/project/creator scoped (`web/backend/services/project_dataset_service.py:102-168`; `web/backend/services/project_dataset_service.py:188-260`). Data Analysis and BI both use these identities.
- The deterministic analysis engine validates configured domains and methods (`web/backend/data_analysis/router.py:14-71`). Version-aware assistance resolves an authorized immutable dataset version and returns provenance (`web/backend/data_analysis/routes/analysis_routes.py:194-248`). BI widget and report execution reuse the same deterministic analysis service (`web/backend/services/bi_dashboard_service.py:313-390`; `web/backend/services/bi_reporting_service.py:534-650`).
- Data Analysis chart requests use a visualization `chart_config`, while BI widgets persist a narrower widget type, deterministic `analysis_spec`, layout, and display options (`web/backend/data_analysis/routes/visualization_routes.py:60-113`; `web/backend/data_analysis/routes/data_routes.py:123-141`). These are existing separate contracts.
- Data Analysis reports are editable documents stored in tenant/user/project-scoped browser IndexedDB (`web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/utils/datasetStorage.js:178-238`). BI reports are server-generated immutable snapshots with exact version vectors and private artifacts. They are not one report-persistence contract.
- Website form responses are currently converted from Page Builder frontend project state into CSV before dataset upload (`web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/components/DataAnalysisWorkspace.jsx:123-135`; `web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/components/DataAnalysisWorkspace.jsx:1542-1579`). No equivalent authorized cross-product E-learning source contract was found.

### Lifecycle and release status

Persistent project datasets require candidate schema 147 (`web/backend/services/project_dataset_service.py:14-21`). Persistent BI dashboards, automated reporting, private sharing, and delivery/retention require candidate schemas 163, 164, 165, and 166 respectively (`web/backend/services/bi_dashboard_service.py:1-17`; `web/backend/services/bi_reporting_service.py:1-42`; `web/backend/services/bi_sharing_service.py:1-15`; `web/backend/services/bi_report_delivery_service.py:1-23`).

These candidates are source implementations, not an active release selection. Existing release policy states that the active selection remains schema 146 and that candidate presence does not authorize migration, worker activation, deployment, or persistent-environment mutation (`docs/production-release-policy.md:2996-3045`; `docs/MADAR_AUTO_DEPLOY_MERGE_CONTRACT.md:1564-1605`).

### AI readiness evidence

- The Athena frontend calls deterministic `/analysis/assist` or its immutable-version form, not the LLM route (`web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/utils/versionAwareAnalysis.js:1-16`; `web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/components/DataAnalysisWorkspace.jsx:1807-1840`).
- `AssistedAnalysis` implements offline rules and allowlisted metrics (`web/backend/data_analysis/assisted/assisted_analysis.py:13-114`).
- A separate `/analysis/ai` route implements authorization, preflight checks, server-side token reservation/finalization, and provider-failure handling (`web/backend/data_analysis/routes/analysis_routes.py:261-388`).
- The AI service limits rows and profiles, excludes sensitive columns, validates planner output, and constrains execution (`web/backend/data_analysis/ai/service.py:93-225`).
- Real OpenAI and DeepSeek planner calls explicitly raise `not implemented yet` (`web/backend/data_analysis/ai/planner.py:89-100`). No current frontend caller of `/analysis/ai`, streaming protocol, agent framework, cancellation protocol, or AI job framework was found.

Accordingly, AI and LLM functionality is under development, is not production-ready, and is not integrated into the live product experience.

## Decision

Madar establishes independent **Data Analysis** and **Business Intelligence** logical domains. Both consume a platform-owned **Shared Data & Deterministic Analytics** capability through staged independence.

This decision establishes logical ownership and dependency direction. It does not move files, activate schemas, create public interfaces, or authorize implementation.

### Platform Shared Data & Deterministic Analytics owns

- logical contracts for dataset and source identity;
- immutable dataset versions;
- authorized data retrieval and exploration;
- provenance and bounded execution;
- deterministic statistical analysis; and
- common analytical result envelopes.

Existing backend functions and route shapes are evidence for these logical responsibilities. This ADR does not declare every current backend helper or frontend import to be a supported public contract.

### Data Analysis domain owns

- interactive source preparation;
- the data-cleaning user experience;
- exploratory analysis;
- ad hoc statistical workflows;
- exploratory visualization authoring;
- local report drafts; and
- Data Analysis-specific presentation, including the current deterministic Athena experience.

### Business Intelligence domain owns

- persistent dashboards and widgets;
- dataset-version binding policies;
- BI sharing and permissions UX;
- scheduled reporting;
- immutable report snapshots;
- exports, delivery, and retention; and
- BI-specific charts and presentation.

### Source product domains own

Website Forms, E-learning, and every other source product retain ownership of their source records, business semantics, visibility rules, and access decisions. Future cross-product source integration must use a reviewed, backend-authorized data contract. It must not read another product's frontend state, browser cache, or persistence tables as an authorization substitute.

### FastAPI remains authoritative for

- tenant, user, and resource authorization;
- dataset and source access;
- entitlements and operational availability;
- processing and persistence;
- versioning and provenance;
- private report artifacts; and
- execution constraints.

Frontend navigation, route presence, module metadata, chart configuration, dataset references, and AI presentation must never become authorization authorities.

## Staged independence and dependency direction

Logical ownership is approved now. Existing physical files, Page Builder-backed data projects, routes, adapters, and working behavior remain in place until separately reviewed and authorized.

The approved logical direction is:

```text
Source product domains
    -> reviewed FastAPI source/data contracts
        -> Platform Shared Data & Deterministic Analytics
            <- Data Analysis
            <- Business Intelligence
            <- future reviewed product consumers
```

Data Analysis and BI remain independent consumers. Neither product owns the other's private presentation or workflow. Shared behavior is limited to contracts whose cross-consumer use and compatibility have been verified.

## AI readiness boundary

- AI is under development.
- AI is not currently production-ready or integrated into the live product experience.
- Athena currently uses deterministic assistance.
- LLM provider implementation is incomplete.
- No shared frontend AI framework is approved.
- No streaming, agent, cancellation, or AI-job framework is approved.
- No AI deployment, commercialization, provider activation, or production integration is authorized.

AI architecture requires a separate future decision based on actual product requirements, provider and security validation, privacy controls, entitlement and metering policy, failure behavior, and cross-product evidence.

## Non-goals and exclusions

This ADR does **not** authorize:

- moving Analytics, Data Projects, Data Sources, or BI files;
- changing Page Builder-backed data projects;
- combining Data Analysis and BI into one product;
- unifying chart specifications;
- unifying report builders or report persistence;
- changing dataset identifiers or version semantics;
- changing API routes, authentication, entitlements, or access checks;
- activating candidate database schemas;
- launching BI or AI commercially;
- changing commercial subscriptions or product packaging;
- introducing dependencies, services, workers, infrastructure, or provider credentials;
- implementing a module or plugin registry;
- changing frontend/backend deployment topology;
- changing source-product persistence or directly consuming Forms/E-learning frontend state as an authorization mechanism; or
- treating an existing internal implementation as a public frontend contract solely because multiple features use it.

## Alternatives considered

### Option A — One combined Analytics and BI business domain

Rejected. Current navigation groups these capabilities and backend routes are consolidated, but their responsibilities differ: Data Analysis is exploratory and interactive, while BI owns governed persistent dashboards and reporting. Combining ownership would make BI candidate lifecycle and reporting concerns part of routine Data Analysis work and increase unrelated development context.

### Option B — Independent Data Analysis and BI domains with direct integration

Rejected as the complete model. It preserves product separation but does not assign accountable ownership for dataset identities, immutable versions, provenance, exploration, and the deterministic execution engine already consumed by both domains. Direct private dependencies would leave these contracts implicit.

### Option C — Independent domains consuming shared platform contracts

Approved with staged independence. Only dataset/source identity, immutable versions, authorized exploration, provenance, bounded deterministic execution, and common result envelopes are approved as shared logical responsibilities. Chart authoring, report persistence, dashboards, BI delivery, and AI presentation remain product-specific unless separately justified.

## Ownership and consumers

| Capability | Logical owner | Known consumers |
|---|---|---|
| Dataset/source identity and immutable versions | Platform Shared Data & Deterministic Analytics | Data Analysis, Data Sources, BI, future reviewed products |
| Authorized exploration and deterministic execution | Platform Shared Data & Deterministic Analytics | Data Analysis, BI widgets, BI report execution |
| Interactive preparation and exploration | Data Analysis | Data-workspace users |
| Ad hoc visualization and local report drafts | Data Analysis | Data-workspace users and browser-local archive |
| Persistent dashboards, sharing, and reports | Business Intelligence | BI owners and authorized same-tenant members when candidate capabilities are available |
| Source-record semantics and access | Respective source product | Authorized analytics ingestion only through future reviewed adapters |
| Tenant/access/persistence authority | FastAPI | Every frontend and worker consumer |

Accountable technical maintainers for the three approved logical owners remain `PENDING OWNER DECISION`. Until assigned, preserve existing behavior, contracts, and release constraints.

## Contracts and compatibility

### Existing implementation evidence

- **Dataset identity/version:** `persistent_dataset_id`, `dataset_version_id`, version number, kind, hash, and project identity are returned by project dataset routes (`web/backend/data_analysis/routes/data_routes.py:393-467`).
- **Source metadata:** project data-source routes cover registry, capability discovery, credentials, ingestion, resources, webhooks, and synchronization (`web/backend/data_analysis/routes/data_routes.py:977-1942`).
- **Exploration:** immutable-version exploration uses allowlisted columns, filters, sorting, and bounded paging (`web/backend/data_analysis/routes/data_routes.py:470-485`).
- **Deterministic analysis:** `/analysis/run`, `/analysis/assist`, and version-bound assistance are implemented (`web/backend/data_analysis/routes/analysis_routes.py:128-258`).
- **BI definitions:** dashboards persist version-bound widget definitions and validated deterministic analysis specifications (`web/backend/services/bi_dashboard_service.py:61-148`; `web/backend/services/bi_dashboard_service.py:208-280`).
- **BI reporting:** scheduled runs capture exact version vectors, immutable definition/result snapshots, warnings, and private artifacts (`web/backend/services/bi_reporting_service.py:258-388`; `web/backend/services/bi_reporting_service.py:534-650`).
- **BI sharing:** server-side access distinguishes owner, viewer, and editor within tenant/project scope (`web/backend/services/bi_sharing_service.py:56-120`).

### Proposed public-contract status

This ADR creates no public frontend package, entry point, export, schema, or adapter. The following remain future work requiring separate review:

- a documented frontend dataset/source identity interface;
- a versioned common analytical result envelope for product consumers;
- source-product adapters for Website Forms, E-learning, or other domains;
- compatibility rules for adding deterministic operations;
- any cross-product chart, report, or AI interface.

Before any interface is declared public, its provider, consumers, data shape, versioning, errors, access assumptions, localization/accessibility obligations, and compatibility tests must be documented.

### Compatibility requirements

Any future implementation must preserve or explicitly validate:

- existing dataset identities and immutable versions;
- tenant/project/uploader isolation;
- content hashes, provenance, and version selection;
- existing deterministic analytical behavior and result interpretation;
- saved local analysis/report drafts where they remain supported;
- BI dashboard revisions, widget bindings, version policies, report vectors, and historical snapshots;
- private report and chart artifact authorization;
- Website Forms and E-learning source ownership and permissions;
- Arabic/English and RTL/LTR behavior;
- accessibility, keyboard use, responsive behavior, and supported themes; and
- every applicable QA, CI, security, migration, deployment, and release protection.

## Tenant, security, and authorization impact

This logical decision changes no trust boundary. FastAPI remains authoritative. Dataset, source, dashboard, report, and AI requests must retain authenticated tenant/user/resource checks and applicable entitlements. Shared frontend contracts may carry identities and presentation data but must not grant access or choose authoritative tenant scope.

Source-product integrations must obtain data through product-authorized backend operations. Untrusted metadata must not select arbitrary tables, tenants, endpoints, storage paths, providers, or permissions. Private files and reports remain non-public, scope checked, and protected against path traversal.

Any future change to tenant identity, authorization, entitlement semantics, backend service ownership, sharing boundaries, or deployment authority requires separate architecture and security review plus product-owner approval.

## Commercial and lifecycle impact

Data Analysis, BI, and AI lifecycle or commercial packaging is not decided by this ADR. BI and AI remain under development. Existing routes, navigation, capability identifiers, catalog entries, source candidates, or tests do not establish commercial launch or final packaging.

No subscription, add-on, entitlement, navigation visibility, provider availability, or product launch state changes. AI deployment, commercialization, and provider activation remain unauthorized.

## Implementation and dependency impact

Implementation is **NOT AUTHORIZED**. This ADR creates no source move, API change, schema selection, migration, dependency, worker, adapter, registry, shared package, chart/report unification, or deployment change.

Future implementation proposals must identify the exact existing provider and consumer call sites; classify current imports and route shapes as public or private; define compatibility and legacy baselines; preserve product-owned source semantics; and obtain the required security, QA, release, and product-owner approvals.

## QA, CI, and release impact

No application tests were executed for this documentation-only decision. Existing evidence includes:

- `web/frontend/src/components/DataProjects/DataProjectsPage.test.jsx` for data-project listing and creation;
- `web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/components/DataSourceStep.test.jsx` and `DataSourceRegistryPanel.test.jsx` for persistent datasets and source registry behavior;
- `web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/utils/datasetStorage.test.js` for tenant/user/project-scoped browser archives;
- `web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/components/DataAnalysisWorkspace.versionAnalysis.test.js` for immutable-version assistant requests;
- `web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/components/DataWorkspaceChatbot.test.jsx` for the current deterministic assistant UX;
- `web/frontend/src/components/PageBuilder/DataAnalysisWorkspace/components/ReportBuilderStep.archive.test.jsx` for local report-draft persistence;
- `web/frontend/src/components/BusinessIntelligence/BusinessIntelligenceWorkspace.test.jsx` for immutable selection, deterministic metrics, stale-response handling, dashboards, accessibility, Arabic/RTL, sharing, reports, and delivery;
- `web/backend/tests/test_project_datasets.py` and `test_versioned_analytics.py` for dataset isolation, exact versions, provenance, bounded querying, and scalable execution;
- `web/backend/tests/test_data_upload_privacy.py`, `test_generated_charts_privacy.py`, and `test_authorization_matrix.py` for private storage and tenant/user authorization;
- `web/backend/tests/test_bi_dashboard_service.py`, `test_bi_reporting_service.py`, `test_bi_report_export_service.py`, and `test_bi_report_delivery_service.py` for BI validation, version vectors, private exports, delivery, revocation, and retention; and
- `web/backend/tests/test_ai_usage_routes.py`, `test_ai_token_metering.py`, and `test_ai_analysis_strictness.py` for AI authorization, metering, provider-failure handling, and safety restrictions.

Existing tests do not prove candidate schemas are active, real LLM providers work, cross-product Forms/E-learning source contracts exist, or a shared frontend analytics API has been implemented.

- **Existing architecture checks:** Existing unit, component, backend, authorization, privacy, candidate-schema, release-policy, RTL, and accessibility checks; automated logical domain-boundary enforcement is not claimed.
- **Proposed architecture checks:** Shared-contract compatibility, source-adapter authorization, and forbidden-private-dependency checks require separately reviewed implementation and a legacy baseline.
- **Accountable CI enforcement owner:** PENDING OWNER DECISION
- **Planned verification milestones:** PENDING OWNER DECISION
- **Review trigger/date:** The re-evaluation triggers in this ADR; no calendar date approved

Candidate schemas 147 and 163–166 retain separate release governance. This ADR must not select, apply, activate, deploy, or authorize them. All root `AGENTS.md`, security, tenant-authorization, QA, CI, migration, deployment, and production-release requirements remain unchanged.

## Rollback, migration, and failure handling

There is no runtime rollback, data migration, schema activation, or deployment because this ADR authorizes no implementation. Before implementation, this logical decision may be superseded or withdrawn only through the governed ADR process.

Any future persisted or published change must define compatibility, failure handling, migration, and rollback limits in its own approved change. Candidate-schema activation requires the existing release workflow and cannot be inferred from this ADR.

## Risks and unresolved questions

- Accountable technical maintainers for Shared Data & Deterministic Analytics, Data Analysis, and BI: `PENDING OWNER DECISION`.
- Exact public contract names, ownership documents, source locations, and versions: not approved.
- Whether BI will become an independent commercial product: unresolved.
- Whether Website Forms and E-learning require first-class authorized analytics-source adapters: unresolved.
- Long-term support policy for browser-local Data Analysis reports: unresolved.
- Dataset sharing beyond creator ownership and existing BI resource sharing: unresolved.
- The permanent `ai_analytics` entitlement and metering policy: unresolved.
- LLM provider, privacy, streaming, cancellation, job, and cross-product integration architecture: not approved.
- Physical extraction, legacy dependency classification, compatibility milestones, and architecture CI accountability: not approved.
- Candidate schema activation and production readiness remain governed release decisions outside this ADR.

## Approval record

- **Product-owner decision:** APPROVED
- **Decision date:** 2026-11-06
- **Approved scope:** Independent Data Analysis and Business Intelligence logical domains consuming a platform-owned Shared Data & Deterministic Analytics capability through staged independence
- **Implementation:** NOT AUTHORIZED
- **AI readiness:** UNDER DEVELOPMENT — not production-ready or integrated into the live product experience
- **Conditions:** Preserve all existing behavior, data/version meaning, server-side authorization, source-product ownership, compatibility requirements, candidate-schema release restrictions, and QA/release protections; require separate review and approval for physical changes or new contracts
- **Related exception IDs:** None
- **Related constitutional amendment:** None
- **Supersedes / superseded by:** None

### Final document approval history

- **Event:** FINAL ADR DOCUMENT APPROVAL
- **Authority:** Madar product owner
- **Date:** 2026-11-06
- **Document:** ADR-FE-003
- **Approved scope:** Separate Data Analysis and BI domains with shared data/version/provenance and deterministic analytics capabilities.
- **Review basis:** Complete current wording independently reviewed in Phase 29.1.
- **Approval distinction:** This final-wording approval is separate from the earlier logical direction approval recorded above; its historical date and scope remain unchanged.
- **Implementation:** NOT AUTHORIZED
- **Repository adoption:** PENDING INDEPENDENT REVIEW AND AUTHORIZED MERGE
