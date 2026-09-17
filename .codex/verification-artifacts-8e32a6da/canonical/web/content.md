# Madar — Complete Client Content and Pitch Reference

## 1. Document Purpose

This document is the definitive source for describing, demonstrating, and pitching Madar to prospective clients, partners, and stakeholders. It consolidates the product's verified capabilities, business value, suitable use cases, operational strengths, and honest boundaries. It is intended to support presentations, proposals, website copy, brochures, demonstrations, onboarding material, and industry-specific pitches without allowing marketing language to outrun the product.

This reference was prepared from repository snapshot `dc3f50f` on the `builder-backend` branch and reviewed on 21 July 2026. Evidence was checked across the frontend, backend routes and services, database migrations, tests, Compose configuration, and operational documentation.

Operator records confirm that migrations 054–057 have been manually applied and verified in the current Supabase production database: 054 adds form-submission idempotency, 055 adds the builder asset registry, 056 adds storage quota accounting, and 057 adds project-site permissions. Because manual SQL Editor execution may not appear in the Supabase CLI migration ledger, operators must retain separate execution evidence. Every new environment must still apply these migrations in order and independently verify its schema, grants, data boundaries, and runtime behavior.

Madar is in late beta. Capability status is used consistently:

- **AVAILABLE:** implemented and suitable for a controlled client demonstration or late-beta use; this does not imply that every deployment has enabled every optional service.
- **BETA:** implemented and usable with stated limits, configuration requirements, acceptance testing, or controlled rollout.
- **INTERNAL:** an operational or administrative capability that strengthens service delivery but is not normally marketed on its own.
- **MANUAL:** a workflow completed with operator or administrator assistance rather than end-to-end automation.
- **DISABLED:** code exists but is intentionally unavailable until a stated security or infrastructure condition is met.
- **PLANNED:** partial or future work that must not be presented as currently available.

Billing is explicitly outside the current product offer. Madar has no integrated payment gateway, provider checkout, automated subscription collection, invoicing, refunds, or customer payment portal. Existing plan and feature-state screens support a manual/beta commercial process only.

Terminology used throughout:

- **Organization/client:** the business, NGO, team, or institution adopting Madar.
- **Tenant:** the organization's isolated workspace and data boundary inside Madar.
- **Staff/workspace user:** a person who signs in to operate the organization's Madar workspace.
- **Customer:** a visitor who interacts with the organization's public site, form, or reservation workflow.
- **Member:** a customer who creates an account for a particular organization's site and may receive project-specific access.

## 2. Executive Summary

Madar is a connected digital operations platform for small and growing organizations. It brings website creation, public forms, reservation requests, member access, response management, private data preparation, reporting, visualization, and assisted analysis into one tenant-controlled workspace.

Instead of maintaining a website in one tool, collecting requests in another, tracking customers in messages, and moving spreadsheets between disconnected services, an organization can design its public experience and operate the workflows behind it from the same platform. Staff can build multi-page sites visually, add forms and booking blocks, preview and publish a selected project, review incoming submissions and reservations, manage site members, and turn uploaded spreadsheets into structured reports and charts.

Madar is designed for organizations that need useful digital workflows but may not have a dedicated development or data team. It combines approachable interfaces with server-enforced tenant isolation, protected member pages, secure account controls, durable records, recovery-aware editing, private file handling, and operational health tooling.

The product is in late beta. Its strongest current proposition is a controlled, configured workspace that connects public engagement with internal follow-up and data understanding. Payments remain external or manual, delivery channels such as email and web push depend on deployment configuration, and advanced infrastructure-dependent capabilities must be confirmed during onboarding.

## 3. One-Sentence Description

- **Plain-language:** Madar helps an organization build its website, collect customer requests, manage bookings and members, and understand its data from one workspace.
- **Professional sales:** Madar is a multi-tenant digital operations platform that connects no-code publishing, customer workflows, and practical data analysis.
- **Technical:** Madar is a tenant-isolated SaaS platform combining a visual site and workflow builder, authenticated public runtime, durable form and reservation services, and private analytics tooling.
- **Arabic-market-friendly English:** Madar gives growing organizations one clear workspace to build their digital presence, serve customers, and turn day-to-day data into useful decisions, with English and Arabic interface support.
- **Short tagline:** **Build. Engage. Understand.**

## 4. The Problems Madar Solves

### Disconnected tools and repeated work

Organizations often assemble a website, form service, booking inbox, membership list, spreadsheets, and reporting tool separately. Staff copy data between them, lose context, and struggle to identify which record belongs to which public experience. Madar connects published projects, forms, reservations, members, datasets, and reports inside one tenant workspace.

### Websites that are difficult to update

Small teams may depend on a developer for routine changes or leave outdated information online. Madar's Page Builder lets staff create projects and pages, arrange content, manage navigation and branding, preview changes, and publish a validated draft without editing code.

### Forms scattered across services

When forms live outside the main site, branding, ownership, follow-up, and response history become fragmented. Madar embeds custom forms into published projects, stores submissions with a field snapshot and publication provenance, and provides staff views for filtering, reviewing, and updating response status.

### Reservation requests managed through messages

Bookings handled through messaging threads are easy to duplicate or overlook. Madar provides public date-request and fixed-slot reservation blocks, durable records, duplicate protection, cancellation support, and an internal reservation workspace. It is a reservation-request workflow, not a payment or calendar-sync product.

### Public customers disconnected from protected content

Organizations may need some pages open to everyone and others available only to approved members. Madar supports organization-specific public-site accounts, active or disabled memberships, project-specific roles, and server-side enforcement for protected page, protected form, and reservation capabilities.

### Spreadsheets that are hard to prepare and interpret

Operational data often arrives as inconsistent CSV or Excel files. Madar can privately upload supported files, inspect their structure, profile quality, prepare cleaning actions, export cleaned data, run predefined analyses, and generate charts. This gives nontechnical staff a guided path from file to insight.

### Limited access to useful analysis

Many teams know what they want to understand but not how to calculate or visualize it. Madar provides templated finance, operations, HR, program-monitoring, and form-response analyses, plus bounded assisted and AI-supported statistical questions where configured.

### Difficulty publishing reliable digital workflows

Saving, retrying, and publishing are often treated as invisible technical details until data is lost. Madar includes autosave, explicit save, recovery snapshots, revision conflict handling, canonical publish validation, versioned public content, and idempotent form and reservation submission.

### Inconsistent operational visibility

Teams need to know whether their service is healthy and whether queues, storage, or backups require attention. Madar includes internal health signals, protected metrics, queue and disk indicators, storage accounting, and backup/restore tooling. These are operational controls that require configured monitoring and operator procedures.

## 5. Who Madar Is For

### Small and medium businesses

Suitable for businesses that need a branded site, inquiry forms, booking requests, customer accounts, and a clearer way to review operational data without maintaining several separate systems.

### Service businesses and consultants

Suitable for publishing services, collecting structured briefs, scheduling consultation requests, tracking lead status, and analyzing demand by service, period, or customer segment.

### Training providers

Suitable for course pages, registration or assessment forms, session reservation requests, participant-only resources, response tracking, attendance summaries, and bilingual form experiences.

### NGOs and community organizations

Suitable for program pages, surveys, beneficiary or activity data collection, member access, and predefined monitoring reports such as target achievement, disaggregation, baseline/endline change, partner summaries, and feedback status. Madar does not claim donor-standard or regulatory certification.

### Hospitality and event organizations

Suitable for presenting venues, rooms, services, menus, or events and receiving dated inquiries or fixed-slot reservation requests. Payment, live inventory distribution, channel-manager integration, and automated capacity optimization are not current offerings.

### Clinics and appointment-based organizations

Suitable for general informational pages and appointment-request workflows. Madar must not be presented as a certified medical-record system, diagnostic tool, or healthcare-compliance solution.

### Educational and membership organizations

Suitable for public information, registration, protected member pages, project-specific access roles, surveys, quizzes in controlled beta, and response analysis. It is not currently a full learning-management system.

### Internal teams collecting and analyzing data

Suitable for teams that receive spreadsheets and need repeatable preparation, quality inspection, finance/HR/operations summaries, visualizations, and downloadable results within a private workspace.

### Small retailers and local providers

Suitable for branded catalog-like pages, contact and request forms, customer registration, service reservations, and simple operational analysis. Madar does not currently provide e-commerce checkout, inventory management, or integrated payments.

## 6. Core Value Proposition

| Pillar | Client benefit | Relevant capabilities | Example outcome | Status |
|---|---|---|---|---|
| **Build** | Create a professional digital experience without writing application code. | Multi-project Page Builder, pages, sections, content blocks, forms, reservations, themes, header/footer, English/Arabic content support. | A training center updates course pages and registration questions internally. | AVAILABLE |
| **Publish** | Move from draft to a controlled, versioned public experience. | Preview, validated publishing, explicit live-project binding, protected-page filtering, publication version/hash, revalidation caching. | Staff preview a campaign site, publish it, and keep another draft project private. | AVAILABLE |
| **Collect** | Capture structured customer requests in the context of the site that generated them. | Custom forms, reservation blocks, validation, honeypot and rate limits, durable records, retry-safe idempotency. | A service business receives one reliable inquiry even if the visitor's connection retries. | AVAILABLE |
| **Operate** | Give staff one place to follow up on customers, members, submissions, and reservations. | Response dashboard, statuses, filters, pagination, reservation status management, member activation and project roles, notifications. | An operations manager moves a request from New to Contacted and reviews upcoming reservations. | AVAILABLE / BETA |
| **Understand** | Turn operational files into usable summaries and visuals. | CSV/Excel upload, preview, cleaning, quality reports, predefined analysis, charts, report canvas, assisted analysis. | An NGO converts a beneficiary spreadsheet into target and disaggregation summaries. | AVAILABLE / BETA |
| **Secure** | Keep each organization's workspace and private content separated and controlled. | Tenant authorization, row-level security, backend-only privileged writes, protected member pages, secure sessions, CSRF/origin checks, MFA, audit events, private storage. | A member of one organization cannot use the same account to access another tenant's protected project. | AVAILABLE |
| **Recover** | Reduce the operational cost of mistakes, conflicts, and infrastructure failures. | Autosave, recovery snapshots, revision conflict review, durable queues, storage accounting, health checks, backup/restore tooling. | A staff member can recover unsaved builder work or resolve an edit conflict instead of silently overwriting it. | AVAILABLE / INTERNAL |
| **Grow** | Add projects and workflows within a consistent platform rather than rebuilding the operating model each time. | Paginated project management, reusable form templates, role assignments, reporting catalog, configurable quotas and service modules. | A consultant launches separate project sites while keeping ownership and administration in one tenant. | BETA |

## 7. Complete Product Capability Catalogue

### 7.1 No-Code Page Builder — AVAILABLE

Madar's Page Builder is the main authoring workspace for websites and lightweight business applications. An organization can manage multiple projects, open a project-specific workspace, and create a site from structured pages rather than a single fixed template.

Confirmed capabilities include:

- create, list, open, update, archive, and paginate active projects;
- create, duplicate, rename, reorder, and delete pages, while preventing deletion of the final page;
- choose a default/home page, set clean page paths, control navigation visibility, and detect invalid or duplicate routes;
- build pages from sections, rows, one-to-four-column layouts, or directly positioned elements;
- add headings, text, buttons, images, cards, lists, dividers, embeds, metrics, multiple carousel/gallery styles, forms, login/registration blocks, and reservation blocks;
- edit text, typography, alignment, spacing, colors, backgrounds, borders, sizes, and responsive layout properties;
- configure button actions for internal page navigation, validated external links, and messages;
- configure site header and footer visibility, brand, logo, contact information, navigation, and descriptive content;
- apply theme tokens and form-specific visual settings while preserving public-runtime rendering;
- use starter projects and form templates to accelerate common setups;
- save manually and autosave to the server with a visible state;
- retain a local recovery snapshot without making browser storage the authoritative project database;
- detect concurrent edits, attempt a bounded safe merge, and ask the user to resolve genuine conflicts;
- preview the exact selected project through a project-specific route;
- validate and publish a canonical schema with an expected revision;
- explicitly choose which published project represents the live site;
- unpublish with safeguards that prevent breaking an active site binding;
- preserve publication version, timestamp, schema hash, and ETag metadata;
- keep archived projects out of normal editing and public delivery.

The client benefit is control: staff can change content and workflows while the platform protects against common causes of lost work, stale publishing, invalid routes, and accidental project substitution. Responsive behavior is supported through fluid runtime styles and layout controls; device-specific perfection should still be reviewed in preview before launch.

The builder also contains workflow and quiz-design concepts. Form quizzes, conditional rules, and workflow steps should be presented as **BETA** because some behaviors are configuration- or review-dependent, and “mock notification” is explicitly not a real delivery action.

### 7.2 Public Business Websites — AVAILABLE

Each tenant can configure a unique site identifier and publish one explicitly selected project as its live public experience. The current canonical route is platform path-based, using the organization's site identifier; automated custom-domain provisioning is not a current offering.

Public sites support:

- multi-page navigation and a selected homepage;
- responsive presentation of builder content and theme-controlled branding;
- configured site header, footer, logo, contact email, phone, and description;
- validated images, links, media, embeds, and content blocks;
- public forms and reservation components bound to the same live project;
- public registration and login blocks for organization-specific site members;
- pages visible anonymously and protected pages delivered only after server authorization;
- project-specific roles for capabilities on protected content;
- public content revalidation through versioned ETags, reducing stale-content risk;
- private/no-store responses for protected pages;
- safe public errors that do not expose drafts or internal implementation details.

The public runtime deliberately exposes only the active published project, not whichever project happened to be published most recently. Drafts, draft revisions, private-page content, and unrelated tenant projects are not sent to anonymous visitors.

### 7.3 Forms and Data Collection — AVAILABLE

Organizations can create forms within a project and place them on one or more pages. The form editor supports sections/pages, titles, descriptions, success messages, required fields, help text, placeholders, answer choices, field ordering, duplication, and visual theming.

Confirmed form types include short text, paragraph, email, phone, number/money, date, dropdown, radio, checkboxes, yes/no, and status-style choices. A file field exists in the editor, but durable public attachment handling should be treated as **BETA** and confirmed for the intended deployment before demonstration. Forms can be English, Arabic, or bilingual, with localized labels and options. JSON/data-only form import and reusable templates are available for prepared workflows.

Public submission protections include:

- lookup against the currently bound published project and form definition;
- required-field and schema-aware validation;
- bounded field count, answer length, and payload size;
- an anti-bot honeypot and public rate limiting;
- a server-side field snapshot so historical answers retain their original meaning;
- publication and project provenance;
- a client-generated idempotency key stored only as a hash;
- identical retries returning the original submission;
- a stable conflict when the same key is reused for different answers;
- a concurrency-safe database uniqueness boundary;
- notification creation only once for a replayed logical submission.

Staff can view submissions by project and form, use bounded pagination, inspect an individual response, filter the workspace, and update statuses such as New, Contacted, and Closed. Status changes are tenant-scoped and audited.

Quiz settings, scoring, conditional logic, and multi-page behavior are implemented in the authoring/runtime path but should be described as **BETA** until the exact client flow has been acceptance-tested. Manual-review scoring remains manual by design.

### 7.4 Reservations and Booking Workflows — AVAILABLE

Madar supports two general reservation experiences: open date/time requests and configured fixed slots. A project can place reservation blocks alongside its normal content and forms.

The workflow supports:

- customer name and contact details;
- date, time, party/quantity, notes, and timezone-aware request data where configured;
- fixed-slot selection defined by the published block;
- durable, tenant- and project-bound reservation records;
- hashed idempotency keys and payload hashes for safe retry behavior;
- database protection against concurrent duplicate submissions and exclusive slot collisions;
- reservation statuses managed by authenticated staff;
- tenant-scoped listing, filtering, pagination, and detail views;
- cancellation links based on non-guessable tokens;
- notification/outbox creation for reservation events;
- validation that the reservation block belongs to the active published project.

Madar should be pitched as a reliable booking-request and reservation-management workflow. It does not currently claim calendar synchronization, payment collection, automated reminders, resource optimization, or integration with external hotel/restaurant channel systems.

### 7.5 Customer and Member Accounts — AVAILABLE / BETA

Madar distinguishes workspace users from public-site members. Workspace users operate Madar on behalf of the client. Site members register or are managed for a particular tenant's public experience and do not automatically become Madar workspace users.

Confirmed capabilities include:

- public-site registration, login, logout, and session status;
- tenant-specific membership records linked to authenticated identity;
- active and disabled membership states, with disabled status overriding permissions;
- customer/member listing in a selected project workspace;
- administrator-created membership records where authorized;
- project-specific role definitions and membership-to-project-role assignments;
- stable role IDs rather than trusting editable role names;
- server-side capabilities for viewing protected pages, submitting protected forms, and making reservations;
- owner/admin authorization for role assignment changes;
- audit events for membership and role changes;
- fail-closed behavior for unknown roles or capabilities;
- cross-project behavior allowing one tenant member to hold different roles in different projects.

Basic protected member access is **AVAILABLE**. Project-specific roles are **AVAILABLE / BETA**: migration 057 is applied and operator-verified in the current Supabase production database, while each new environment must apply and verify it independently and the capability set remains intentionally narrow rather than a general-purpose permissions engine.

### 7.6 Data Upload and Management — AVAILABLE

The data workspace accepts private `.csv`, `.xls`, and `.xlsx` uploads. JSON is not a supported direct local upload format and must not be advertised as one. Remote URL ingestion contains guarded code paths but is intentionally disabled unless a deployment supplies enforced, DNS-pinned egress controls.

The upload flow provides:

- user- and tenant-scoped private storage;
- managed paths that are not controlled by the original filename;
- content-type and extension validation;
- configurable size, row, column, worksheet, cell, and decompression limits;
- streamed handling and bounded preview for large CSV files;
- stricter size rejection for Excel files that cannot be safely chunked;
- worksheet and compressed-archive checks designed to reject oversized or suspicious workbooks;
- dataset metadata, column names, row counts, and partial preview;
- authenticated reading and export;
- formula-injection neutralization in spreadsheet exports;
- path-containment and cross-user access protection;
- quota reservation and disk-space preflight where the required storage schema and operational configuration are verified.

Uploads remain private; they are not served from the public asset directory. Large or complex files may be rejected with guidance to reduce or convert them. The safe limits are a reliability feature, not an “unlimited data” promise.

### 7.7 Data Cleaning and Preparation — AVAILABLE

Madar guides users through understanding and preparing a dataset before analysis. The workspace can inspect a file, identify column types, calculate descriptive statistics, report missing values, generate a quality/prepare report, apply selected cleaning actions, and export the cleaned result.

Confirmed preparation behavior includes:

- header normalization and duplicate-header handling;
- conversion of numeric, money, date, Boolean, category, and multi-choice data;
- recognition and normalization of Arabic and Persian digits;
- removal of common currency, percentage, thousands, and spacing symbols during numeric conversion;
- missing-value inspection and configurable handling;
- whitespace and case normalization for text/category values;
- Boolean value mapping;
- duplicate and quality indicators;
- preservation of a preview so users can review the result before exporting;
- safe spreadsheet export that prevents values from being interpreted as formulas.

The value is practical: a nontechnical user can make inconsistent operational files analysis-ready through explicit, reviewable steps instead of an opaque one-click transformation.

### 7.8 Analysis and Reporting — AVAILABLE / BETA

Madar separates deterministic, templated analysis from AI-assisted analysis. The deterministic catalog is suitable for repeatable business reporting and does not require a generative provider.

Confirmed analysis families include:

- **Finance:** profit-and-loss summary, calculated profit, budget versus actual, expense and revenue grouping, monthly/daily summaries, cash flow, top expenses, ratios, negative-value checks, transaction summary, cost per beneficiary, and donor funding summaries.
- **Operations:** department summaries, top items, average price, item counts, revenue by item, and quantity by department.
- **Human resources:** workforce, compensation, and attendance summaries.
- **Program monitoring/NGO:** indicator progress, target achievement, beneficiary and disaggregation summaries, baseline/endline change, activity completion, survey questions, location, partner, vulnerability, complaint/feedback, case status, and attendance rate.
- **Forms:** response overview, answer distribution, numeric summaries, rating summaries, multi-select summaries, and column suggestions.
- **Custom assisted calculations:** bounded offline questions and custom metrics such as sums, rates, and grouped indicators.

Outputs can include key metrics, tables, charts, and explanatory summaries. Users can assemble results into a report canvas, edit report text and properties, add report elements, and export or retain generated artifacts privately. Report composition and complex document output should be presented as **BETA**, especially for layout-sensitive client deliverables.

### 7.9 Data Visualization — AVAILABLE

The visualization workspace can profile selected columns, guide users toward compatible inputs, and generate private charts. Confirmed chart types are:

- bar;
- line;
- scatter;
- histogram;
- box;
- violin;
- frequency/count;
- pie;
- heatmap.

Users can select axes and series, group data, choose palettes, configure titles and labels, adjust orientation where relevant, and generate visual output. The system performs column compatibility checks and provides user-safe errors when a chart cannot be created.

Generated charts are stored outside the public file tree and served through authenticated routes with private caching, safe content disposition, and restrictive handling for HTML output. Persistent Compose volumes, tenant/user path scope, quotas, and retention controls support durability when configured.

### 7.10 AI-Assisted Analysis — BETA

Madar's AI analysis is a bounded statistical assistant, not a general unrestricted chatbot. A user can ask a natural-language question about an authorized dataset. The service first profiles the dataset, omits sensitive columns from the provider-facing compact profile, asks the configured planner for a constrained analysis plan, validates that plan, and executes supported calculations.

Confirmed protections and limits include:

- tenant/user ownership checks before analysis;
- daily message and generated-code usage reservations;
- per-plan row and profiled-column limits;
- blocking requests to dump raw files, all rows, or complete datasets;
- blocking requests to reveal identifying or sensitive values;
- aggregate-focused responses;
- planner output validation against allowed columns and operations;
- output length and result validation;
- a mock provider for safe testing and explicit provider configuration;
- provider abstraction for additional providers, although not every named provider adapter is complete;
- generated code disabled by default in production;
- when enabled, an isolated subprocess protocol with time, memory, process, filesystem, environment, network-attempt, and output controls.

Important limitations: responses may be incomplete or inaccurate and require human review; Madar does not provide professional financial, medical, legal, or safeguarding advice; raw private datasets are not intended to be sent wholesale to a model; some providers require separately approved external configuration; OpenAI and DeepSeek provider names exist in configuration but must not be presented as operational adapters without deployment evidence; and local generated execution must remain disabled unless its isolation guard is enabled and verified.

### 7.11 Notifications — AVAILABLE / BETA

Madar includes a user notification center with unread counts, mark-one-read, mark-all-read, and browser-push enrollment controls. Event services can create in-app notifications and enqueue delivery work in a durable outbox.

The outbox supports:

- deduplication keys and idempotent event creation;
- accepted channels limited to internal, email, and web push;
- bounded leased batches;
- configurable concurrency;
- retry with exponential backoff and bounded jitter;
- maximum-attempt handling and a dead state;
- lease recovery after a worker interruption;
- safe shutdown;
- structured failure codes and redacted logging;
- queue depth, oldest pending age, failed, dead, and sent metrics;
- worker health endpoints.

Internal notification records are **AVAILABLE**. The dedicated delivery worker and external email/web-push channels are **BETA** and deployment-dependent. If SMTP or push credentials are absent, the worker reports a visible configuration/delivery failure and does not falsely mark the notification sent. Universal real-time or guaranteed delivery must not be promised.

### 7.12 Branding and Website Settings — AVAILABLE

Tenant staff can configure a site identifier, brand/store name, logo, contact email, phone, description, header/footer content, and theme settings. Account settings also cover staff name, phone, email-related identity, avatar, password, and MFA where applicable.

Branding controls validate subdomain-like identifiers, contact values, image types, and URL schemes. Managed logo/image uploads accept PNG, JPEG, and WebP; SVG is rejected. The builder's theme tokens allow coherent colors and surfaces across pages, forms, and the public runtime. English and Arabic application content and bilingual form content support regional presentations, but the language scope of each client implementation should be confirmed during discovery.

### 7.13 File and Asset Management — AVAILABLE / BETA

Madar manages builder images rather than trusting customer-controlled filesystem paths. Uploaded images receive randomized storage keys and are registered with tenant, uploader, MIME type, size, checksum, status, timestamps, and retention metadata.

Client-relevant protections include:

- PNG, JPEG, and WebP signature/type validation and SVG rejection;
- tenant ownership and no cross-tenant asset reuse;
- generated filenames and traversal-resistant storage paths;
- immutable SHA-256 checksums;
- reference reconciliation against saved project schemas;
- active versus unreferenced lifecycle status;
- a grace period before physical cleanup;
- bounded, dry-run-first cleanup that rechecks references and checksums;
- refusal to delete unknown unmanaged files automatically;
- tenant and optional user quota accounting;
- atomic storage reservations for concurrent uploads;
- disk free-space safety floor;
- release and reconciliation after deletion or failed upload;
- a tenant storage usage endpoint and near-capacity signal.

Managed uploads are suitable for client use. Migrations 055–056 are applied and operator-verified in the current Supabase production database, but full lifecycle, quota, and cleanup operation remains **BETA** because every environment must independently verify writable non-root volume ownership, persistence across container recreation, quota enforcement, disk free-space thresholds, and scheduled, monitored cleanup/reconciliation jobs.

### 7.14 Administration — AVAILABLE / BETA

**Tenant administration** covers project creation and archive management, site settings, branding, forms, submissions, reservations, member status, project roles, datasets, generated outputs, assets, and storage usage. The exact menu available depends on account type and enabled features.

**Platform/system administration** includes paginated user management, account status and lifecycle actions, controlled user-type changes, billing feature-state administration, MFA policy controls, audit events, and temporary support access based on an expiring user-approved code.

Controlled support access is an internal support safeguard, not a normal client self-service feature. It is time-bound, audited, restricted from sensitive routes, and requires a permission code. It should be discussed only when explaining support and governance.

Tenant operations are **AVAILABLE**. Some advanced platform administration and plan-state handling are **INTERNAL** or **MANUAL**. Plan screens do not establish automated billing.

### 7.15 Security and Privacy — AVAILABLE / INTERNAL

Madar uses layered controls designed to reduce common web, tenant-isolation, and data-handling risks. Client-relevant controls confirmed in the repository include:

- a tenant context for server-side authorization;
- PostgreSQL row-level security and removal of direct authenticated privileged writes;
- backend-only service-role operations for sensitive mutations;
- HttpOnly authentication cookies and production secure-cookie requirements;
- signed, session-bound CSRF tokens and origin validation for browser writes;
- rate limits for authentication, public submissions, uploads, analysis, and visualization;
- request and payload size limits;
- admin MFA and AAL2 checks for sensitive administrative actions;
- status checks for active, disabled, pending, and deleted accounts;
- protected member pages filtered on the server, not merely hidden in the interface;
- project-scoped site roles with fail-closed capabilities;
- audit events with sensitive metadata removed;
- file signature, type, path, and spreadsheet-formula protections;
- private dataset and generated-artifact storage;
- validated URLs and rejection of dangerous schemes;
- retry-safe idempotency for forms and reservations;
- least-privilege database functions with fixed search paths;
- safe error responses and route-level frontend error recovery;
- Content Security Policy and browser security headers;
- non-root, read-only, capability-dropped containers with resource limits.

These controls support a credible security posture; they are not a guarantee against every incident and do not constitute a regulatory certification. Client-specific compliance, retention, residency, risk, and assurance requirements require a separate assessment.

### 7.16 Reliability and Operations — INTERNAL / BETA

Reliability is built into the product workflow as well as its deployment tooling:

- builder autosave, manual save, unload protection, recovery snapshots, and conflict resolution;
- revision-checked project writes and atomic validated publishing;
- explicit live-project selection and safeguards around archive/unpublish;
- versioned public schemas, hashes, ETags, and private/no-store member content;
- durable form submissions and reservations with replay protection;
- leased notification queues with retry, dead-letter, metrics, and recovery;
- durable mounts for public assets, private uploads, and generated charts;
- liveness, readiness, degraded component states, and protected Prometheus-style metrics;
- correlation IDs, security event IDs, bounded-cardinality request metrics, and structured redacted logs;
- checks for database, authentication service, Redis, schema version, storage writability/free space, notification worker/backlog, backup freshness, MFA policy, remote ingestion, and AI execution guards;
- logical PostgreSQL and file backup scripts with SHA-256 manifests;
- isolated-target restore verification, rollback guidance, and quarterly drill templates;
- digest-pinned container images, locked dependencies, health checks, bounded logs, and non-root runtime users.

These controls strengthen service delivery but depend on operator configuration and discipline. Repository backup tooling does not prove that a production restore has succeeded; approved RPO/RTO, encrypted off-site retention, real monitoring, and periodic isolated restore drills remain operational requirements.

## 8. How Madar Works — Client Journey

1. **Create the workspace.** The organization signs up or receives a tenant workspace. Its owner and staff accounts are separated from public-site customer accounts.
2. **Configure the identity.** Staff add the organization's site identifier, brand, logo, contact details, description, theme, and account security settings.
3. **Build the experience.** In the Page Builder, staff create a project, add pages and navigation, arrange content, and configure responsive visual presentation.
4. **Add business workflows.** Staff add forms, reservation blocks, registration/login blocks, protected pages, and the project roles needed for members.
5. **Preview and review.** The team opens the project-specific preview, tests navigation and forms, reviews mobile behavior, and resolves any save or route warnings.
6. **Publish deliberately.** Madar saves the latest revision, validates it, publishes a versioned schema, and explicitly binds the selected published project to the organization's public site.
7. **Serve customers.** Visitors browse public pages, submit a form or reservation request, or create a tenant-site member account for protected content.
8. **Operate internally.** Staff review submissions and reservations, change statuses, manage members and roles, and receive internal notifications. Configured delivery workers can extend selected notifications to email or web push.
9. **Understand the data.** The organization uploads CSV or Excel files, reviews quality, applies cleaning steps, runs templated reports, creates charts, and asks bounded assisted-analysis questions.
10. **Maintain control.** Tenant authorization, audit trails, private storage, idempotent records, recovery tools, health signals, quotas, and backup procedures protect the workflow behind the interface.

This journey is the key presentation narrative: Madar connects what an organization publishes, what customers do, what staff manage, and what leaders learn.

## 9. Example Client Scenarios

### 9.1 Consulting business

- **Problem:** Leads arrive through unstructured messages, service pages are hard to update, and the team cannot compare demand across offerings.
- **Madar setup:** A branded multi-page site with service cards, consultant profiles, an inquiry form, and a consultation reservation block.
- **Customer interaction:** A visitor chooses a service, submits a structured brief, and requests a date/time.
- **Staff workflow:** Staff review inquiries, mark them Contacted or Closed, and manage reservation status in one tenant workspace.
- **Insight outcome:** Exported response data can be summarized by service, month, status, and customer segment.
- **Boundary:** Proposal signing, video meetings, invoicing, and payment remain external.

### 9.2 Training center

- **Problem:** Course information, registrations, participant lists, and feedback are spread across pages and spreadsheets.
- **Madar setup:** Course pages, bilingual registration forms, session-request slots, member-only resources, and a feedback survey.
- **Customer interaction:** Learners register, request a session, and sign in for protected information.
- **Staff workflow:** Staff manage member status, review registrations, update response status, and export participant data.
- **Insight outcome:** Attendance, rating, question-distribution, and response-overview templates help the center review delivery.
- **Boundary:** Madar is not a full LMS; video learning, certificates, graded automation, and payments require separate arrangements.

### 9.3 NGO survey and reporting workflow

- **Problem:** Program teams collect data in separate forms and spend significant effort cleaning files before donor or management reports.
- **Madar setup:** Public or member-only survey pages, structured bilingual forms, tenant roles, and private data-analysis workspace.
- **Customer interaction:** Participants submit bounded forms through the relevant published project.
- **Staff workflow:** Staff review submissions, export data, upload supporting spreadsheets, inspect missing values, and apply explicit cleaning actions.
- **Insight outcome:** Target achievement, beneficiary, disaggregation, baseline/endline, location, partner, feedback, and attendance reports create a repeatable analysis starting point.
- **Boundary:** Human validation remains required, and Madar does not claim compliance with a donor framework or safeguarding standard.

### 9.4 Restaurant or event reservation workflow

- **Problem:** Reservation requests arrive through calls and messages, leading to duplicates and inconsistent details.
- **Madar setup:** Menu/event pages, galleries, contact details, and fixed-slot or date-request reservation blocks.
- **Customer interaction:** A visitor selects a date or available configured slot, provides contact and party details, and receives the page's confirmation state.
- **Staff workflow:** Staff review, filter, and update reservation status; duplicate retries do not create duplicate logical bookings.
- **Insight outcome:** Reservation exports can show demand by date, slot, party size, or status.
- **Boundary:** Live table inventory, deposits, calendar synchronization, and automated reminders are not included.

### 9.5 Hotel or guesthouse inquiry workflow

- **Problem:** A small property needs a polished online presence and consistent inquiry information without a full booking engine.
- **Madar setup:** Property pages, room galleries, amenities, location/contact sections, and a stay-request form or reservation block.
- **Customer interaction:** A guest submits dates, party size, and notes.
- **Staff workflow:** The property reviews the request and confirms availability manually through its chosen channel.
- **Insight outcome:** Staff can analyze inquiry periods, sources captured in form fields, party size, and request status.
- **Boundary:** This is not real-time room inventory, channel management, payment, or instant confirmed booking.

### 9.6 Clinic appointment-request workflow

- **Problem:** General appointment requests arrive in inconsistent messages and staff repeatedly ask for basic scheduling details.
- **Madar setup:** Informational service pages, a minimal appointment-request form, fixed slots where appropriate, and protected general member resources.
- **Customer interaction:** A visitor requests a date/time and supplies only the agreed nonclinical details.
- **Staff workflow:** Authorized staff review and follow up through the clinic's approved process.
- **Insight outcome:** Aggregated request volume and timing can support staffing discussions.
- **Boundary:** Do not collect clinical records without a separate assessment. Madar is not a certified medical-record, diagnostic, emergency, or healthcare-compliance system.

### 9.7 Membership or community portal

- **Problem:** Public information and member-only resources are mixed, while access is managed informally.
- **Madar setup:** Public landing pages, registration/login blocks, protected pages, active/disabled memberships, and project-specific roles.
- **Customer interaction:** A visitor registers, then accesses only content allowed by the server-side membership and role rules.
- **Staff workflow:** Owners/admins manage member status and role assignments and can use protected forms for member workflows.
- **Insight outcome:** Form-response summaries help the organization understand participation and feedback.
- **Boundary:** The role capability set is intentionally focused; complex organizational hierarchies or approval engines require product review.

### 9.8 Small retailer or local service provider

- **Problem:** The organization needs a visual catalog, contact workflow, and simple business reporting but not a full commerce stack.
- **Madar setup:** Branded pages, product/service cards and carousels, inquiry forms, registration, and reservation requests.
- **Customer interaction:** Visitors browse and submit a request rather than completing checkout.
- **Staff workflow:** Staff manage inquiries and export results for follow-up.
- **Insight outcome:** Finance and operations templates can summarize separately uploaded sales/cost files.
- **Boundary:** Inventory, order fulfillment, taxes, checkout, and payment processing remain external.

### 9.9 Internal company data-analysis portal

- **Problem:** Managers receive inconsistent monthly files and depend on an analyst for every summary.
- **Madar setup:** A private tenant workspace with controlled staff accounts, private upload storage, cleaning recipes, report templates, and charts.
- **Customer interaction:** There may be no public workflow; the value is internal.
- **Staff workflow:** Users upload CSV/Excel files, inspect quality, clean data, run finance/HR/operations summaries, and prepare a report canvas.
- **Insight outcome:** Repeatable metrics and visualizations reduce the time between receiving data and discussing it.
- **Boundary:** This is guided analysis, not an unrestricted data warehouse, real-time BI pipeline, or guaranteed substitute for professional analysts.

## 10. Key Differentiators

### More than a website builder

Madar does not stop when a page is published. The same project can contain forms, reservations, member access, and protected pages, and the same workspace lets staff operate the records those pages generate.

### More than a form builder

Forms live within a versioned public project and retain form-field and publication context. Staff can manage statuses, members, reservations, and analysis without exporting every interaction to an unrelated tool.

### More than a booking form

Reservation blocks share the organization's brand, member and project boundary, internal management view, notifications infrastructure, and data-analysis environment. Madar remains honest that it is not yet a payment-enabled calendar ecosystem.

### More than a spreadsheet

Spreadsheets are accepted as private inputs, then inspected, bounded, cleaned, analyzed, visualized, and exported through guided workflows. Ownership and authorization are part of the service rather than an informal file-sharing convention.

### More than a dashboard

Madar connects the public action that creates data with the internal workflow and the resulting analysis. It is not only a final chart layer over a separate operating process.

### More than a chatbot

AI assistance is constrained to authorized dataset profiles and validated statistical plans. Deterministic reports and cleaning remain available without relying on generative output, and unsafe raw-data or sensitive-value requests are blocked.

### One tenant-controlled operating context

The most credible distinction is connection: projects, public experiences, member access, responses, reservations, datasets, assets, and operational safeguards are designed around the same organization boundary.

## 11. Benefits by Stakeholder

### Business owner

- A clearer digital presence and customer journey without commissioning every change.
- One view of incoming requests and the data behind them.
- Reduced dependence on disconnected tools for core late-beta workflows.
- Better control over what is published and which project is live.

### Operations manager

- Structured form and reservation records instead of fragmented conversations.
- Status, filters, pagination, cancellation, and notification workflows.
- Retry protection that reduces duplicate records.
- Storage, queue, and service-health indicators for operational follow-up.

### Staff member

- Guided interfaces for editing pages, reviewing responses, and preparing data.
- Autosave and recovery when editing a project.
- User-safe errors and route recovery instead of exposed technical traces.
- English/Arabic interface support.

### Data analyst or nontechnical analyst

- Private CSV/Excel intake, previews, data-quality reports, and cleaning actions.
- Repeatable domain templates and configurable charts.
- Exportable results and a report composition workspace.
- Bounded AI assistance without making it the only analysis path.

### Organization administrator

- Tenant-scoped projects, settings, members, roles, and access controls.
- Account status, MFA, audit events, and protected administration paths.
- Quota and asset lifecycle controls where deployed.
- Clear separation between staff accounts and public-site members.

### End customer or site member

- A coherent branded site rather than links scattered across services.
- Responsive pages, forms, and reservation requests.
- Safe retry behavior on unreliable connections.
- A member account for authorized protected content when the organization enables it.

## 12. Pitch Versions

### 12.1 Ten-Second Pitch

Madar lets organizations build their site, run customer workflows, and understand their data from one secure workspace.

### 12.2 Thirty-Second Elevator Pitch

Madar is a connected platform for small and growing organizations. You can visually build and publish a multi-page website, add forms, reservation requests, and member-only pages, manage the records those workflows create, then upload your operational data to clean, analyze, and visualize it. Instead of stitching together a website builder, forms, messages, and spreadsheets, your team works within one tenant-controlled platform.

### 12.3 Two-Minute Pitch

Most growing organizations do not have one digital problem; they have several connected problems managed in separate tools. Their website is difficult to update, inquiries arrive through forms or messages, reservations are tracked manually, member access is inconsistent, and useful data sits in spreadsheets that are hard to interpret.

Madar brings those workflows together. Staff can build a branded, multi-page site without coding, add public forms or booking-request blocks, create protected pages for members, preview changes, and deliberately choose which project goes live. When customers interact, Madar keeps durable, tenant-scoped submissions and reservations with validation and duplicate protection. Staff review and update those records from the same workspace.

The platform also helps teams move from collection to understanding. They can privately upload CSV or Excel data, inspect quality, apply explicit cleaning steps, run finance, operations, HR, program-monitoring, and form-response analyses, and create charts or reports. A bounded AI assistant can support statistical questions when configured, but deterministic reports remain central.

Madar is in late beta, so we are precise about scope: payments are external, delivery channels such as email depend on deployment configuration, and advanced infrastructure is confirmed during onboarding. The current value is tangible—a connected, controlled environment for publishing, customer operations, and practical data insight.

### 12.4 Five-Minute Client Presentation Narrative

Start with the reality inside many small and growing organizations. The public website may be managed by one supplier, forms by another service, bookings through messaging, customer access in a spreadsheet, and reporting in files that only one person understands. Each tool may work, but the organization carries the cost of moving information, repeating work, and losing context.

Madar is designed around that connected context. Every client receives an isolated tenant workspace. Staff accounts operate that workspace; customers and members interact with the organization's published site. That separation is important because it gives the organization a clear ownership and access boundary.

The first part of Madar is **Build and Publish**. In the Page Builder, staff can create multiple projects and multi-page sites, control navigation and branding, add text, images, cards, galleries, metrics, and calls to action, and place forms, registration, or reservation blocks directly in the experience. Autosave, recovery, revision-aware conflict handling, preview, and validated publishing make the workflow safer than simply editing a browser document. Publishing is deliberate: the organization chooses the live project, and public content is versioned.

The second part is **Collect and Operate**. A form submission is not an anonymous piece of data detached from its origin. Madar verifies that the form belongs to the live project, stores a snapshot of the field definition, records publication provenance, limits abusive payloads, and prevents duplicate retries. Reservations receive similar protection. Staff can then filter records, inspect details, update statuses, manage members, and assign project-specific access roles. Protected pages are enforced by the server instead of being merely hidden in the menu.

The third part is **Understand**. Teams can upload private CSV and Excel files, review data quality and missing values, normalize common formats—including Arabic numerals and money values—and export cleaned results. They can run predefined finance, operations, HR, program-monitoring, and form-response reports or build bar, line, scatter, histogram, box, violin, frequency, pie, and heatmap visualizations. Where approved, an AI assistant can help answer bounded statistical questions without exposing the complete raw dataset to an unrestricted chatbot workflow.

Behind those interfaces, Madar includes tenant isolation, secure cookies, CSRF and origin defenses, MFA for sensitive administration, audit events, private storage, quotas, health signals, durable notification queues, and backup/restore tooling. We present those as protections and operational practices, not as absolute guarantees.

Madar is currently best adopted through a guided late-beta engagement: identify one meaningful workflow, configure it safely, train the team, validate it in a pilot, and expand from evidence. It does not yet include integrated payments, guaranteed external notification delivery, or automatic custom-domain provisioning. For the right organization, however, it already provides something valuable: one connected place to build the public experience, operate the customer journey, and learn from the resulting data.

### 12.5 Technical Decision-Maker Pitch

Madar is a React/FastAPI multi-tenant platform with a backend trust boundary and PostgreSQL/Supabase persistence. Privileged writes are backend-mediated, tenant authorization and RLS are layered, browser sessions use HttpOnly cookies with CSRF/origin defenses, sensitive admin routes require AAL2, and public protected content is server-filtered. Builder writes are revision-aware; publishing validates and atomically stores a canonical schema with version/hash/ETag identity. Public forms and reservations use durable hashed idempotency scopes. Private datasets and generated artifacts are separated from public assets. The platform includes non-root hardened containers, protected metrics, readiness degradation, queue operations, quotas, and backup/restore scripts. Late-beta gates remain for independent migration verification in each new environment, staging RLS verification, parser-worker isolation, configured delivery providers, restore drills, storage-volume operations, and external observability.

### 12.6 Nontechnical Business Owner Pitch

Madar gives your team one place to manage the parts of your digital business that usually become scattered. You can update your website, add a contact form or reservation request, give approved customers access to private pages, review what people submit, and turn your spreadsheets into clearer reports and charts. Your team does not need to edit code, and we begin with a guided pilot rather than asking you to replace every tool at once. Payments and some external delivery services remain separate today, so the scope is agreed honestly before launch.

### 12.7 NGO/Community Organization Pitch

Madar helps an organization connect outreach, participation, and reporting. Build bilingual public or member pages, collect structured surveys and registrations, manage responses and member access, then privately prepare and analyze program data. Built-in reports cover indicators, target achievement, beneficiaries, disaggregation, baseline/endline change, activities, partners, locations, feedback, cases, and attendance. Madar supports repeatable monitoring workflows, while human review, safeguarding procedures, donor requirements, and regulatory obligations remain with the organization and its approved processes.

## 13. Recommended Demo Flow

The ideal demonstration is 10–15 minutes and uses a dedicated, synthetic tenant—not production or customer data.

| Step | What to show | What to say | Client benefit | Backup plan |
|---|---|---|---|---|
| 1. Login/workspace | Sign in and open the tenant dashboard. | “This staff account operates one isolated organization workspace.” | Clear ownership and separation. | Use screenshots of the dashboard shell if auth staging is unavailable. |
| 2. Project chooser | Show several projects and open one. | “You can manage multiple initiatives without mixing drafts.” | Scalable organization. | Open a prepared project URL directly. |
| 3. Page Builder | Select a page and edit a heading, image, or theme. | “Routine content changes happen visually, with autosave and recovery.” | Less technical dependency. | Use a pre-recorded 60-second builder clip. |
| 4. Form/reservation | Add or edit a form question or reservation block. | “The customer workflow is part of the site, not an external link.” | Connected brand and data. | Show an already configured block. |
| 5. Preview | Open the project-specific preview and navigate pages. | “Preview uses the same runtime model as the public experience.” | Safer review before publishing. | Use a prepared preview tab. |
| 6. Publish/bind | Show the publish panel and selected live project; avoid mutating a shared environment. | “Publishing is versioned and the live project is chosen explicitly.” | Controlled go-live. | Demonstrate with screenshots and explain that live mutation is disabled in the demo. |
| 7. Public site | Open the synthetic public site. | “This is what customers see: branded pages and connected workflows.” | Coherent customer journey. | Use a static recorded walkthrough. |
| 8. Submit | Send a synthetic form or reservation with a unique test key. | “Validation and retry protection keep one logical request.” | Reliable collection. | Show a prepared response record if fixture writes are unavailable. |
| 9. Internal response | Open submissions/reservations and change a synthetic status. | “Staff follow up from the same workspace.” | Operational clarity. | Show list/detail screenshots. |
| 10. Upload data | Upload a small synthetic CSV and show preview/quality. | “Private files are checked, bounded, and kept outside public assets.” | Safer data intake. | Use a preloaded dataset fixture. |
| 11. Analyze/visualize | Run one templated report and create one chart. | “Madar moves from raw spreadsheet to a repeatable answer.” | Faster insight. | Show saved report/chart artifacts. |
| 12. Security/member access | Show a protected page as anonymous, then as an authorized member. | “Private content is enforced by the server, not hidden only in the menu.” | Trustworthy access control. | Use a two-pane recording from isolated staging. |

Demo discipline: pre-create all fixtures, disable external delivery, never use real customer information, and do not publish or alter a shared site. If a feature depends on environment-specific migration verification, storage operations, or a provider, say “This is available in configured beta deployments” and use a recorded proof rather than improvising.

## 14. Presentation Slide Outline

### Slide 1 — Madar: Build. Engage. Understand.

- **Purpose:** Establish the category and promise.
- **Key messages:** One tenant-controlled platform connecting digital presence, customer workflows, and data insight.
- **Suggested visual:** Three connected panels: site, operations inbox, analysis chart.
- **Speaker notes:** Avoid “everything platform.” Lead with connection and control.

### Slide 2 — The Cost of Disconnected Work

- **Purpose:** Make the client's current friction visible.
- **Key messages:** Website edits, forms, messages, member lists, and spreadsheets live apart; context and time are lost between them.
- **Suggested visual:** A fragmented tool map with manual arrows.
- **Speaker notes:** Use the client's own examples discovered before the pitch.

### Slide 3 — One Connected Workflow

- **Purpose:** Introduce Madar's model.
- **Key messages:** Build and publish; collect and operate; clean, analyze, and visualize.
- **Suggested visual:** Customer journey flowing into a staff workspace and insight layer.
- **Speaker notes:** Emphasize that all three stages respect the same tenant boundary.

### Slide 4 — Build the Public Experience

- **Purpose:** Show Page Builder value.
- **Key messages:** Multiple projects/pages, visual content, navigation, themes, forms, reservations, preview, recovery-aware saving.
- **Suggested visual:** Builder screenshot with page tree and canvas.
- **Speaker notes:** Demonstrate one small change rather than listing every element.

### Slide 5 — Publish with Control

- **Purpose:** Differentiate draft from live content.
- **Key messages:** Validated publish, explicit live-project selection, versioned public content, protected pages.
- **Suggested visual:** Draft → preview → validated version → live site.
- **Speaker notes:** Explain that another draft does not silently replace the live project.

### Slide 6 — Turn Visits into Structured Work

- **Purpose:** Show forms and reservations.
- **Key messages:** Branded forms, booking requests, validation, duplicate protection, durable records.
- **Suggested visual:** Public form beside staff response list.
- **Speaker notes:** State clearly that reservations do not include payment or external calendar sync.

### Slide 7 — Serve Customers and Members

- **Purpose:** Explain account separation and protected content.
- **Key messages:** Public visitors, tenant-site members, active/disabled status, project roles, server-enforced access.
- **Suggested visual:** Public page and locked member page with role gate.
- **Speaker notes:** Clarify that members are not workspace administrators.

### Slide 8 — From Spreadsheet to Usable Data

- **Purpose:** Introduce the data workflow.
- **Key messages:** Private CSV/Excel upload, preview, quality checks, cleaning actions, safe export.
- **Suggested visual:** File → quality profile → cleaned table.
- **Speaker notes:** Highlight bounded handling and review rather than “automatic perfection.”

### Slide 9 — Reports and Visual Insight

- **Purpose:** Make analysis concrete.
- **Key messages:** Finance, operations, HR, NGO/program, form-response templates; nine chart families; report composition.
- **Suggested visual:** A metric, a chart, and a report page from synthetic data.
- **Speaker notes:** Choose the analysis family closest to the prospect.

### Slide 10 — Assisted Analysis with Boundaries

- **Purpose:** Position AI responsibly.
- **Key messages:** Natural-language statistical questions, safe profile, sensitive-column omission, validated plans, usage/output limits.
- **Suggested visual:** Question → validated plan → aggregate answer.
- **Speaker notes:** Say explicitly that it is not a general chatbot or professional adviser.

### Slide 11 — Security Designed into the Workflow

- **Purpose:** Build confidence without absolutes.
- **Key messages:** Tenant isolation, backend authorization, secure sessions, protected content, MFA, audit events, private storage, idempotency.
- **Suggested visual:** Layered shield around tenant, identity, data, and operations.
- **Speaker notes:** Avoid compliance claims; offer a technical review for client-specific requirements.

### Slide 12 — Operational Resilience

- **Purpose:** Show maturity behind the interface.
- **Key messages:** Autosave/recovery, versioning, health checks, queue retries, quotas, durable volumes, backup/restore tools.
- **Suggested visual:** Recovery timeline or health-status panel.
- **Speaker notes:** Separate code capability from configured operations and tested restore drills.

### Slide 13 — Use Cases That Fit Today

- **Purpose:** Help the client recognize itself.
- **Key messages:** Services, training, NGOs, membership, hospitality inquiries, appointments, and internal analysis.
- **Suggested visual:** Six simple industry/workflow cards.
- **Speaker notes:** Use “appointment request” and “reservation request,” not regulated or payment-enabled claims.

### Slide 14 — Guided Late-Beta Implementation

- **Purpose:** Set realistic adoption expectations.
- **Key messages:** Discovery, configured pilot, synthetic testing, training, acceptance, controlled launch, monitored expansion.
- **Suggested visual:** Five-stage onboarding roadmap.
- **Speaker notes:** Explain which provider or infrastructure dependencies are decided during discovery.

### Slide 15 — Current Boundaries

- **Purpose:** Establish trust through clarity.
- **Key messages:** No payment gateway; external delivery configuration required; path-based site URL; strict file limits; no compliance or uptime guarantee.
- **Suggested visual:** “Available now / configured beta / not offered yet” columns.
- **Speaker notes:** Do not hide this slide. Use it to focus the pilot on deliverable value.

### Slide 16 — Next Step: Prove One Workflow

- **Purpose:** Convert interest into a safe action.
- **Key messages:** Discovery call, workflow assessment, tailored demo, limited beta pilot, success criteria.
- **Suggested visual:** A single selected customer journey with a “pilot” marker.
- **Speaker notes:** Do not promise self-service paid signup or fixed pricing before commercial review.

## 15. Objections and Answers

### “Why not use WordPress?”

WordPress can be a strong content-management choice. Madar is relevant when the requirement goes beyond publishing pages and includes connected forms, reservation records, member permissions, internal response management, private dataset preparation, and analysis in one tenant context. If the need is only a conventional marketing site with a large plugin ecosystem, WordPress may be the simpler fit.

### “Why not use Google Forms?”

Google Forms is efficient for standalone collection. Madar connects the form to the organization's branded published project, preserves project/version context, manages responses and statuses in the tenant workspace, supports protected member workflows, and links collection to analysis. For a simple one-off survey, a standalone form tool may still be appropriate.

### “Why not manage bookings through WhatsApp?”

Messaging is convenient but becomes hard to search, standardize, deduplicate, and report on. Madar captures consistent fields in durable reservation records and gives staff a managed status view. WhatsApp or another channel can remain the human follow-up method; Madar does not currently claim an official messaging integration.

### “Can it handle our data?”

Madar supports private CSV, XLS, and XLSX workflows with configurable size and complexity limits, previews, cleaning, templates, and charts. Suitability depends on file size, structure, sensitivity, and reporting needs. We validate representative files in a controlled pilot rather than promise unlimited scale.

### “Is our information private?”

Madar separates tenants, enforces access in the backend and database, keeps datasets and generated artifacts outside public storage, and protects member pages on the server. No platform can promise absolute security; retention, hosting, compliance, and deployment controls must be reviewed for the client's risk profile.

### “Do we need technical staff?”

Routine page, form, reservation, response, and analysis tasks are designed for guided nontechnical use. Initial configuration, advanced branding, infrastructure, integrations, and governance may require Madar support or the client's technical team.

### “Can customers create accounts?”

Yes. A published tenant site can provide registration and login, and active members can receive project-specific access. Member accounts are distinct from staff workspace accounts.

### “Does it support payments?”

No integrated payment gateway exists today. Payment collection, checkout, invoices, refunds, subscriptions, and financial reconciliation remain external or manual. The architecture may support a future reviewed integration, but it is not a current offering.

### “Does it send emails?”

Madar has email-capable services and a durable delivery queue, but real email depends on correctly configured SMTP/provider infrastructure and worker deployment. Internal notifications may be available without email. We do not promise universal or guaranteed email delivery.

### “Can we use our own domain?”

The current canonical public address is platform-hosted and path-based using the organization's configured site identifier. Custom-domain automation is not complete. A custom-domain requirement must be reviewed as deployment/infrastructure scope and must not be assumed.

### “What happens if something goes wrong?”

Builder work has autosave, recovery snapshots, unload warnings, and conflict handling. Public records are durable and retry-safe. The platform includes health signals, audit events, queues, and backup/restore tools. Actual recovery objectives depend on configured backups, monitoring, operators, and rehearsed restore procedures.

### “Is it ready for production?”

Madar is in late beta and suitable for controlled client pilots and configured deployments whose migration, security, backup, monitoring, delivery, and staging gates have passed. It should not be presented as universally production-ready independent of deployment evidence.

### “Can it replace all our current systems?”

No responsible assessment can promise that. Madar can consolidate specific website, collection, reservation-request, member-access, and data-analysis workflows. Discovery should identify what to keep, connect, replace, or defer.

## 16. Frequently Asked Questions

### Setup and workspaces

**How is an organization set up?**  
A tenant workspace is created through onboarding, then staff configure identity, branding, projects, workflows, members, and security. A guided beta setup is recommended.

**Can one organization manage multiple projects?**  
Yes. Projects are separately listed and paginated, with their own drafts, pages, forms, roles, publishing state, and archive lifecycle.

**Can multiple staff edit a project?**  
The platform has revision-aware saving and conflict handling. Operational roles for workspace editing remain intentionally limited; agree staff responsibility and test concurrent editing during onboarding.

### Publishing and websites

**Can we preview before launch?**  
Yes. The builder provides a project-specific preview using the public runtime model.

**Can we choose which project is live?**  
Yes. The live-site binding is explicit and protected against accidental archive or unpublish.

**Does Madar support multiple pages and navigation?**  
Yes, including a default page, clean paths, navigation visibility, headers, footers, and protected pages.

**Does it support mobile visitors?**  
The public runtime and editor include responsive behavior and controls. Each client design should be reviewed on target devices before launch.

**Can we use a custom domain?**  
Not through an automated self-service flow today. The canonical address is platform-hosted and path-based; custom infrastructure must be scoped separately.

### Forms and reservations

**What form fields are supported?**  
Text, paragraph, email, phone, number/money, date, dropdown, radio, checkboxes, yes/no, and status-style options are supported. Public file attachments and advanced logic should be confirmed as beta scope.

**Can forms be bilingual?**  
Yes. The editor supports English, Arabic, and bilingual labels/options and direction-aware form content.

**How are duplicate submissions handled?**  
The browser reuses an idempotency key for an automatic retry; the server hashes it and returns the original record for an identical replay. A different payload with the same key is rejected.

**Are reservations instantly confirmed?**  
They are durable requests/records and may use configured fixed slots, but business confirmation remains dependent on the client's workflow. No payment or external calendar confirmation is implied.

**Can a customer cancel?**  
Reservation cancellation through a protected tokenized link is supported where the block/workflow exposes it.

### Members and access

**Can a site have public and private pages?**  
Yes. Anonymous responses exclude protected content; active authorized members request protected pages through server-side access checks.

**Can the same member have different access in two projects?**  
Yes. Project-specific role assignments are implemented, and migration 057 is applied and operator-verified in the current Supabase production database. Each new environment must still apply and verify that migration before offering the capability.

**Can access be disabled?**  
Yes. A disabled membership overrides project permissions.

### Data and analysis

**Which files can we upload?**  
CSV, XLS, and XLSX. Direct JSON upload and unrestricted remote URL ingestion are not current advertised capabilities.

**Is there a file-size limit?**  
Yes. Limits are configurable and differ by format; Excel is more strictly bounded than chunked CSV. Quotas and disk safety floors also apply.

**Can Madar clean data automatically?**  
It can inspect data and apply explicit cleaning actions. Users should review conversions and outputs rather than assume every ambiguity can be resolved automatically.

**Can results be exported?**  
Yes, including cleaned datasets and generated chart/report outputs where the selected workflow supports them. Spreadsheet exports neutralize formula-like values.

**What can the AI assistant see?**  
The intended provider payload is a compact profile of allowed, non-sensitive columns—not a wholesale raw dataset. Strict prompts block raw-data dumps and sensitive-value lookup. Provider configuration and client data policy still require review.

**Is AI always available?**  
No. It depends on enabled configuration, provider credentials, usage limits, dataset size, and safety checks. Deterministic analysis remains available independently.

### Storage, security, and support

**Where are files stored?**  
Public builder assets are separated from private datasets and generated artifacts. Exact infrastructure is deployment-specific and should be documented during onboarding.

**Is storage unlimited?**  
No. Tenant/user quotas, upload limits, retention policies, and disk safety thresholds protect service stability.

**Is MFA available?**  
Yes, with stronger AAL2 enforcement for sensitive admin operations. Deployment policy must be configured and verified.

**Are actions audited?**  
Important authentication, security, administrative, publishing, status, membership, and role actions create audit events with sensitive metadata excluded.

**How are backups handled?**  
Repository tooling can back up the logical database and relevant file categories with SHA-256 manifests and restore into an isolated target. The operator must schedule backups, store them securely, approve RPO/RTO, and complete restore drills.

**What support is available?**  
Support scope is agreed commercially. The platform includes a controlled, time-limited, audited support-access mechanism, but it is not used without the relevant approval flow.

**Can existing content or data be migrated?**  
Structured content, forms, and supported files can be prepared for import, but migration complexity varies. A representative sample should be assessed before promising scope or timing.

**How do notifications work?**  
Internal notifications are stored in Madar. Email and web push require configured providers and a healthy worker; failed deliveries remain visible for retry or operator handling.

## 17. Implementation and Onboarding

### Recommended onboarding process

1. **Discovery:** identify organization type, target users, current tools, pain points, data sensitivity, and success criteria.
2. **Workflow mapping:** map the customer journey from public page to form/reservation/member action, staff follow-up, and reporting.
3. **Tenant setup:** create the isolated workspace, owners, staff accounts, security settings, and deployment-specific service configuration.
4. **Branding:** configure site identifier, brand, logo, contact details, theme, languages, header, and footer.
5. **Site construction:** build project pages, navigation, responsive layouts, and content using synthetic or approved material.
6. **Workflow construction:** configure forms, reservation blocks, statuses, protected pages, members, and project roles.
7. **Data setup:** validate representative CSV/Excel files, define cleaning actions, choose report templates, and establish safe retention/quota rules.
8. **Staff training:** train each role on the exact tasks it performs, including recovery and escalation.
9. **Isolated testing:** test authentication, publishing, access boundaries, retries, records, exports, delivery configuration, backup, and browser workflows with synthetic data.
10. **Launch acceptance:** obtain client approval, record limitations and owners, select the live project, and deploy through the reviewed release process.
11. **Support and improvement:** monitor agreed signals, review usage and data quality, refine workflows, and expand only after the pilot is stable.

### Small implementation example

A single public project with five pages, one inquiry form, one date-request block, basic branding, two staff users, and one standard report. This is appropriate for a focused pilot. An example planning range might be one to three weeks after content and approvals are ready; it is not a contractual promise.

### Medium implementation example

A bilingual multi-page site with several forms, fixed-slot reservations, member registration, two protected sections, project roles, response dashboards, and one imported operational dataset with cleaning/report templates. An example planning range might be three to eight weeks, depending on content, acceptance, and infrastructure.

### Complex implementation example

Multiple projects, substantial content migration, several member roles, complex forms, sensitive datasets, report design, delivery-provider setup, custom infrastructure needs, and formal security/restore acceptance. This requires phased discovery and a proof of concept before timeline or production commitments.

Commercial pricing, implementation dates, support hours, data retention, and service objectives must be agreed separately; they are not implied by this product reference.

## 18. Current Limitations and Honest Boundaries

- **No payment gateway:** Madar does not process online payments, cards, checkout, refunds, invoices, subscriptions, or customer billing portals.
- **Manual/beta billing:** plan and feature-state behavior supports internal/manual administration only; paid entitlement enforcement must not be marketed as automated billing.
- **External notification dependencies:** email and web-push delivery require provider credentials, enabled worker deployment, monitoring, and tested templates. Delivery is not universal or guaranteed.
- **Platform-hosted canonical site URL:** the current canonical public site uses a platform path and configured site identifier. Automated custom-domain provisioning is not complete.
- **Remote dataset ingestion disabled:** code paths exist, but production enablement requires enforced DNS-pinned egress and redirect validation. It is not a client-facing current feature.
- **Parsing isolation incomplete:** CSV/Excel parsing has strong bounds and temporary workspace controls but still runs in the web process. A true parser worker remains an infrastructure requirement; readiness should expose the production gap.
- **Generated execution conditional:** generated code is disabled by default and may be enabled only with the isolated worker guard; it is not an unrestricted code notebook.
- **Strict file limits:** file size, decompression ratio, worksheets, rows, columns, cells, preview, quotas, and disk floors are deliberately bounded.
- **Provider variation:** AI, SMTP, push, metrics collection, and backup freshness depend on approved deployment configuration. Not every configured AI provider name has a complete adapter.
- **Migration record varies by environment:** migrations 054–057 are manually applied and operator-verified in the current Supabase production database. New environments must apply and verify them independently. Manual SQL Editor execution may not appear in the Supabase CLI migration ledger, so the ledger alone is not sufficient evidence.
- **Storage operations remain environment-dependent:** the registry and quota implementation exists, but every environment must verify writable ownership for the non-root runtime, persistence across container recreation, public/private volume separation, quota enforcement, disk thresholds, and cleanup/reconciliation scheduling and monitoring.
- **Restore proof pending:** backup and restore tooling is tested with local fixtures, but no production restore drill is claimed. RPO and RTO await operator approval.
- **Staging workflows incomplete:** unit and route coverage is broad, but the full browser/RLS workflow inventory still requires an isolated staging database and deterministic fixtures.
- **No compliance certification claim:** Madar is not presented as certified for healthcare, finance, education, government, donor, privacy, or security standards.
- **No guaranteed uptime SLA:** health checks and operational tools exist, but uptime and support commitments require a separate agreement and operating environment.
- **Focused permissions:** site member permissions cover current protected page/form/reservation needs; Madar is not a speculative enterprise authorization suite.
- **Advanced form/report features remain beta:** quizzes, conditional logic, durable public file attachments, complex report layouts, and workflow automation require use-case acceptance testing.
- **No broad integration promise:** calendar sync, CRM/ERP replacement, messaging integrations, mobile apps, webhooks to customer systems, and marketplace ecosystems are not current general offerings.

## 19. Feature Status Matrix

| Area | Capability | Client benefit | Status | Suitable for demo? | Dependency or limitation | Evidence location |
|---|---|---|---|---|---|---|
| Workspace | Tenant onboarding and membership | Isolated organization setup | AVAILABLE | Yes | Requires configured auth/database | `backend/services/onboarding_service.py`, `backend/tests/test_onboarding_routes.py` |
| Accounts | Signup, verification, login, refresh, logout, password lifecycle | Complete account journey | AVAILABLE | Yes | Email verification depends on auth/email configuration | `backend/routes/auth_routes.py`, `backend/routes/password_routes.py` |
| Accounts | Secure cookie sessions and CSRF/origin checks | Reduces session and cross-site request risk | AVAILABLE | Explain | Deployment origins/cookies must be correct | `backend/services/request_security.py`, `backend/tests/test_security_foundation.py` |
| Accounts | MFA and AAL2 admin protection | Stronger sensitive administration | AVAILABLE | Yes, prepared | Production enforcement is configured | `backend/routes/mfa_routes.py`, `backend/tests/test_admin_mfa_aal2_enforcement.py` |
| Builder | Multi-project CRUD, archive, pagination | Organize multiple initiatives | AVAILABLE | Yes | Archived projects are excluded from normal editing; no project-restore workflow is claimed | `backend/routes/builder_routes.py`, `frontend/src/components/PageBuilder/workspace/BuilderProjectChooser.jsx` |
| Builder | Multi-page structure and navigation | Build complete sites | AVAILABLE | Yes | Routes are validated before publish | `frontend/src/components/PageBuilder/core/PageBuilder.routing.js` |
| Builder | Content blocks and responsive layout | Flexible visual pages | AVAILABLE | Yes | Preview on target devices | `frontend/src/components/PageBuilder/core/PageBuilder.constants.js`, `PageBuilder.elementRenderer.jsx` |
| Builder | Header, footer, theme, branding | Consistent client identity | AVAILABLE | Yes | Some external media must pass URL policy | `PageBuilder.siteChrome.jsx`, `PageBuilder.theme.js` |
| Builder | Autosave, manual save, recovery, unload guard | Reduces lost work | AVAILABLE | Yes | Browser recovery is advisory; server is authoritative | `PageBuilder.saveCoordinator.js`, `PageBuilder.recovery.js` |
| Builder | Revision conflicts and bounded merge | Prevents silent overwrite | AVAILABLE | Yes, prepared | Genuine conflicts require user choice | `PageBuilder.conflict.js`, `BuilderConflictResolution.jsx` |
| Builder | Preview and public-runtime parity | Review before launch | AVAILABLE | Yes | Use selected project route | `frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.jsx` |
| Publishing | Canonical validated publish | Safer, consistent live schema | AVAILABLE | Explain/show | Requires migrations through 053 | `backend/routes/builder_routes.py`, `database/migrations/052_publish_validated_builder_schema.sql` |
| Publishing | Explicit live-project binding | No accidental “latest project” swap | AVAILABLE | Yes | Bound project cannot be casually archived/unpublished | `docs/public-site-security-contract.md` |
| Publishing | Version/hash/ETag caching | Reliable revalidation | AVAILABLE | Explain | Cache behavior is deployment/edge aware | `backend/routes/public_site_routes.py`, `backend/tests/test_builder_form_submissions.py` |
| Public site | Public multi-page runtime | Branded customer experience | AVAILABLE | Yes | Canonical URL is platform path-based | `frontend/src/routes/TenantSiteRoutes.jsx` |
| Public site | Protected member pages | Server-enforced private content | AVAILABLE | Yes, prepared | Unknown role visibility fails closed | `backend/routes/public_site_routes.py`, `docs/public-site-security-contract.md` |
| Forms | Form editor, sections, templates, bilingual content | Tailored data collection | AVAILABLE | Yes | Advanced logic/quiz behaviors are beta | `frontend/src/components/PageBuilder/tabs/FormsTab.jsx` |
| Forms | Standard field types and validation | Structured, higher-quality responses | AVAILABLE | Yes | Public file attachments require beta confirmation | `PageBuilder.constants.js`, `PageBuilder.runtime.jsx` |
| Forms | Public durable submissions | Reliable record capture | AVAILABLE | Yes, isolated | Rate and payload limits apply | `backend/routes/public_site_routes.py`, `test_builder_form_submissions.py` |
| Forms | Hashed idempotency and concurrency safety | Avoid duplicate retries | AVAILABLE | Yes | Migration 054 is applied and operator-verified in the current production database; new environments verify independently | `database/migrations/054_add_form_submission_idempotency.sql` |
| Forms | Response list/detail/status | Staff follow-up workflow | AVAILABLE | Yes | Status set is intentionally bounded | `backend/routes/builder_routes.py`, `BuilderResponsesPage.jsx` |
| Forms | Quiz, conditional logic, form import | Richer guided forms | BETA | Prepared only | Acceptance-test exact behavior; manual scoring stays manual | `FormsTab.jsx`, `PageBuilder.quiz.js` |
| Reservations | Date requests and fixed slots | Structured booking requests | AVAILABLE | Yes | Not a payment/calendar engine | `ReservationBlock.jsx`, `backend/routes/public_site_routes.py` |
| Reservations | Retry/slot collision protection | Avoid duplicate or colliding records | AVAILABLE | Yes, isolated | Uses database functions/migrations | `database/migrations/046_harden_public_reservations.sql` |
| Reservations | Staff list/detail/status/cancellation | Operational booking follow-up | AVAILABLE | Yes | External reminders not included | `backend/routes/builder_routes.py`, `ReservationsTab.jsx` |
| Members | Tenant-site registration/login | Customer accounts for a client's site | AVAILABLE | Yes | Distinct from workspace users | `backend/routes/public_site_routes.py` |
| Members | Active/disabled membership | Immediate access control | AVAILABLE | Yes | Disabled overrides capabilities | `backend/services/site_permission_service.py` |
| Members | Project roles and assignments | Different access by project | AVAILABLE / BETA | Yes, prepared | Migration 057 is applied and operator-verified; focused permission scope and environment verification remain | `database/migrations/057_add_project_site_permissions.sql` |
| Data | Private CSV/XLS/XLSX upload | Bring operational files into one workspace | AVAILABLE | Yes | Strict format/size bounds | `backend/data_analysis/services.py` |
| Data | Large CSV streaming preview | Handle larger flat files more safely | AVAILABLE | Yes with small fixture | Full analysis still has memory/row bounds | `backend/tests/test_large_dataset_processing.py` |
| Data | Remote URL ingestion | Potential future ingestion path | DISABLED | No | Requires pinned egress infrastructure | `backend/data_analysis/io/data_reading.py`, `readiness_service.py` |
| Cleaning | Inspection, missing/quality/statistics reports | Understand data before changing it | AVAILABLE | Yes | User reviews recommended actions | `backend/data_analysis/routes/cleaning_routes.py` |
| Cleaning | Type/money/Boolean/Arabic numeral normalization | Prepare inconsistent data | AVAILABLE | Yes | Ambiguous values require review | `backend/data_analysis/cleaning/data_cleaning.py` |
| Cleaning | Cleaned export and formula protection | Reuse results safely | AVAILABLE | Yes | Export sizes are bounded | `backend/tests/test_spreadsheet_security.py` |
| Analysis | Finance and operations templates | Repeatable business summaries | AVAILABLE | Yes | Input columns must map correctly | `backend/data_analysis/core/analysis_catalog.py` |
| Analysis | HR, NGO/program, and form templates | Domain-relevant reporting | AVAILABLE | Yes | No regulatory/donor certification | `backend/data_analysis/core/analysis_catalog.py` |
| Analysis | Custom/offline metrics | Guided bespoke calculations | BETA | Yes, prepared | Bounded supported operations | `backend/data_analysis/assisted/assisted_analysis.py` |
| Reports | Report canvas and exports | Assemble findings for communication | BETA | Yes, prepared | Complex layout acceptance required | `DataAnalysisWorkspace/components/ReportBuilderStep.jsx` |
| Visualization | Nine chart families | Turn data into understandable visuals | AVAILABLE | Yes | Compatibility and output limits apply | `DataAnalysisWorkspace/dataAnalysis.helpers.js` |
| Visualization | Private generated chart serving | Keep analytical artifacts protected | AVAILABLE | Yes | Durable volume must be mounted | `backend/data_analysis/routes/visualization_routes.py` |
| AI | Natural-language statistical planning | Easier aggregate questions | BETA | Only configured fixture | Provider, limits, human review | `backend/data_analysis/ai/service.py` |
| AI | Sensitive/raw-data prompt blocking | Reduces inappropriate disclosure | BETA | Explain | No safety system is an absolute guarantee | `backend/tests/test_ai_analysis_strictness.py` |
| AI | Isolated generated execution | Contain optional generated calculations | BETA / DISABLED BY DEFAULT | No live provider | Requires isolation flag and production guard | `backend/workers/generated_code_worker.py` |
| Notifications | In-app list and read state | Central staff alerts | AVAILABLE | Yes | UI fallback data must not be mistaken for delivery proof | `NotificationsPage.jsx`, `notification_routes.py` |
| Notifications | Outbox deduplication, retry, dead letter | Durable delivery operations | BETA | Fake transport only | Worker and migrations/provider config required | `backend/workers/notification_worker.py` |
| Notifications | Email and web push | Extend alerts beyond app | BETA | No real send | SMTP/push credentials and monitoring required | `notification_delivery_service.py` |
| Branding | Site identifier, logo, brand, contact, theme | Client-controlled presentation | AVAILABLE | Yes | Validated media/URL inputs | `SettingsPage.jsx`, `website_routes.py` |
| Assets | Managed image upload and tenant paths | Safer reusable visual assets | AVAILABLE | Yes | PNG/JPEG/WebP only; SVG rejected | `backend/routes/builder_routes.py`, `test_builder_asset_upload.py` |
| Assets | Registry, references, grace cleanup | Predictable lifecycle | BETA | Explain | Migration 055 is applied and verified; durable volumes, cleanup scheduling, and monitoring remain environment-dependent | `asset_registry_service.py` |
| Storage | Quotas, reservations, disk floor, usage | Protect capacity and prevent races | BETA | Explain | Migration 056 is applied and verified; non-root volume ownership, persistence, thresholds, and operator policy require per-environment proof | `storage_quota_service.py` |
| Storage | Durable public/private/generated volumes | Survive container recreation | INTERNAL | Explain | Host/orchestrator volume durability required | `docker-compose.yml` |
| Administration | Tenant response/member/project management | Day-to-day operational control | AVAILABLE | Yes | Role-aware workspace access | `frontend/src/routes/UserWorkspaceRoutes.jsx` |
| Administration | Platform user and account controls | Govern the SaaS environment | INTERNAL | No ordinary demo | System admin and MFA restrictions | `backend/routes/admin_user_routes.py` |
| Support | User-approved temporary account access | Controlled troubleshooting | INTERNAL | Explain only | Expiring code, audit, route restrictions | `admin_account_access_service.py` |
| Billing | Plan/feature-state administration | Supports manual beta commercial handling | MANUAL | Only with disclaimer | No gateway or automated billing | `backend/services/billing_service.py`, `docs/production-operations-runbook.md` |
| Security | Tenant authorization, RLS, backend-only writes | Cross-client separation | AVAILABLE | Explain | Live RLS verification is a deployment gate | `backend/tests/test_authorization_matrix.py`, migrations 050/053 |
| Security | Audit events and redaction | Accountability without logging secrets | AVAILABLE | Explain | External log retention is deployment-specific | `backend/services/audit_service.py` |
| Security | Rate/body/file/URL controls | Reduce abuse and unsafe input | AVAILABLE | Explain | Correct production configuration required | `request_body_limits.py`, `rate_limit_service.py` |
| Resilience | Route error boundaries and recovery UI | Friendly recovery from frontend faults | AVAILABLE | Yes, forced fixture | Redacted logging needs collection | `frontend/src/components/common/RouteErrorBoundary.jsx` |
| Observability | Live/ready/degraded health | Faster operational diagnosis | INTERNAL | Explain | Dependencies must be configured | `backend/services/readiness_service.py` |
| Observability | Protected Prometheus-style metrics and correlation | Monitor requests, queues, storage, backups | INTERNAL | Explain | External scraper/alerts not included | `observability_service.py` |
| Backup | Logical DB plus file backup and checksums | Recoverable backup sets | INTERNAL | Dry-run only | Operator scheduling, encryption, off-host storage | `scripts/backup_madar.sh`, `verify_backup.sh` |
| Restore | Isolated restore verification and rollback runbook | Safer recovery preparation | INTERNAL | Fixture only | Real restore drill and approved RPO/RTO pending | `scripts/restore_madar.sh`, `docs/backup-restore-runbook.md` |
| Deployment | Non-root hardened containers and CSP | Reduced container/edge attack surface | INTERNAL | Explain | Environment-specific edge/TLS configuration | `docker-compose.yml`, `security_headers.conf.template` |
| Testing | Isolated E2E/RLS safety guard | Prevent tests targeting production | INTERNAL | Safety check only | Full staging fixture harness still required | `docs/isolated-full-stack-testing.md` |

## 20. Claims We Can Safely Make

1. Madar brings website creation, customer workflows, and data analysis into one tenant-controlled platform.
2. Organizations can create and manage multiple Page Builder projects from one workspace.
3. Madar supports multi-page public sites with navigation, branding, forms, reservation blocks, and member access.
4. Staff can preview a selected project before publishing it.
5. Publishing validates a canonical project schema and records version information.
6. Organizations explicitly choose which published project represents their live site.
7. Anonymous visitors do not receive protected page content in the public-site payload.
8. Protected content is enforced on the server rather than hidden only in the interface.
9. Public form submissions are linked to the active published project and retain a field-definition snapshot.
10. Public form retries are idempotent so one logical submission creates one record in the verified current deployment; new environments must independently verify migration 054.
11. Reservations are durable, tenant-scoped, and protected against duplicate retry and configured slot collision.
12. Staff can review and update form-submission and reservation statuses.
13. Public-site member accounts are separate from Madar workspace accounts.
14. A tenant member can receive different role assignments in different projects through the implemented focused permissions model.
15. Madar supports private CSV, XLS, and XLSX data workflows with strict safety limits.
16. Users can inspect, clean, and export data through guided, explicit actions.
17. Madar includes finance, operations, HR, program-monitoring, and form-response analysis templates.
18. Madar can generate bar, line, scatter, histogram, box, violin, frequency, pie, and heatmap visualizations.
19. Generated dataset charts are served through authenticated private routes.
20. AI-assisted analysis is bounded to statistical workflows and blocks requests for raw dataset dumps and sensitive-value lookup.
21. Madar uses backend authorization and row-level security as layered tenant-isolation controls.
22. Sensitive browser writes use CSRF and origin protections alongside HttpOnly session cookies.
23. Sensitive administrative actions can require MFA/AAL2.
24. Builder autosave, recovery snapshots, and conflict handling reduce the risk of lost or overwritten work.
25. Durable notification jobs support retry, dead-letter handling, lease recovery, and queue metrics when the worker is configured.
26. Managed builder assets use randomized tenant-scoped paths, checksums, reference tracking, and grace-period cleanup.
27. Storage quota reservations and disk safety floors are implemented, and migration 056 is applied and operator-verified in the current Supabase production database.
28. Madar provides liveness, readiness, degraded component states, structured logs, correlation IDs, and protected metrics.
29. Backup tooling covers the logical database and relevant public/private file categories with SHA-256 manifests.
30. Madar is a credible late-beta platform for controlled pilots; deployment readiness is verified per environment rather than assumed.

## 21. Claims We Must Not Make Yet

- “Madar includes an integrated payment gateway” or “Madar automates billing.”
- “Customers can complete paid checkout, subscriptions, invoices, refunds, or chargebacks in Madar.”
- “Email and web-push notifications are always delivered” or “real-time delivery is guaranteed.”
- “Madar is certified compliant” with any medical, financial, privacy, government, education, donor, or security standard.
- “Madar is unhackable,” “completely secure,” or “guarantees privacy.”
- “Madar provides unlimited storage, unlimited users, unlimited uploads, or unlimited data analysis.”
- “Madar accepts every file type” or “can process any dataset size.”
- “Madar AI is unrestricted, always accurate, or a substitute for a professional adviser.”
- “Madar sends full private datasets safely to any AI provider.”
- “All configured AI providers are fully implemented.”
- “Remote URL data ingestion is available in production.”
- “All parsing is isolated outside the web process.”
- “Custom domains are provisioned automatically.”
- “Madar guarantees zero downtime, a particular uptime, or a recovery time” without a signed, supported operating agreement.
- “Production restores have been proven” until an isolated restore drill has succeeded with recorded evidence.
- “Madar replaces every CRM, ERP, booking, learning, medical, hospitality, finance, or business system.”
- “Madar includes calendar synchronization, automated reminders, or capacity optimization.”
- “Madar includes native mobile applications.”
- “Every advanced form workflow is production-ready,” especially quizzes, conditional logic, and public attachments without client acceptance testing.
- “A repository feature is operationally deployed” merely because its code or migration exists.

## 22. Client Discovery Questions

### Organization and goals

- What type of organization are you, and what service do you provide?
- Who owns the digital customer journey today?
- What would a successful pilot change for customers, staff, and management?
- Which current process creates the most delay, duplication, or lost information?

### Current tools and public presence

- What website, forms, booking, messaging, spreadsheet, and reporting tools do you use?
- Which tools must remain, and which are candidates for replacement?
- How many public sites or initiatives do you need?
- What pages, navigation, media, branding, and contact information are required?
- Is a platform-hosted path acceptable, or is a custom domain mandatory?
- Which languages and right-to-left layouts are required?

### Forms, reservations, and members

- What information must each form collect, and what information must it never collect?
- Which fields are required, and what validation or consent wording is needed?
- Do you need open date requests, configured fixed slots, or both?
- Who confirms reservations, and through which external channel?
- Do customers need accounts or protected pages?
- What project roles and access decisions are genuinely required?
- What are the status stages and escalation rules for staff follow-up?

### Data and reporting

- Which file formats, sizes, row counts, languages, and column types do you use?
- Does the data contain personal, financial, health, safeguarding, or other sensitive information?
- What cleaning is currently done manually?
- Which metrics, reports, charts, and exports drive decisions?
- Which analyses must be deterministic, and where is AI assistance acceptable?
- What human review or sign-off is required?

### Team, security, and operations

- How many staff need workspace access, and what responsibilities do they have?
- Is MFA required for owners or administrators?
- What audit, retention, deletion, backup, residency, or incident requirements apply?
- What storage and growth expectations should quotas reflect?
- Who approves publishing and role changes?
- Who will own content, response operations, data quality, and platform administration?

### Integrations, notifications, and commercial boundaries

- What email, web-push, messaging, calendar, CRM, or analytics integrations are expected?
- Which notifications must be in-app, email, or push, and what delivery expectation is acceptable?
- Do you expect online payment or automated billing? If yes, can it remain external during the pilot?
- Is there an approved AI provider and data-processing policy?
- What staging environment and test fixtures are available?
- What launch window, support model, and acceptance process do you need?

## 23. Tailoring the Pitch

### Business owner

Lead with reduced fragmentation, control over the public experience, structured leads/bookings, and faster insight. Show one end-to-end customer journey. Keep infrastructure detail in reserve. State payment and support boundaries early.

### NGO or community organization

Lead with bilingual engagement, protected member access, survey/registration workflows, data quality, beneficiary and target reporting, and safe aggregate analysis. Ask about safeguarding, consent, donor formats, and sensitive data before demonstrating uploads or AI.

### Hospitality client

Lead with visual pages, galleries, contact details, date requests, fixed slots, and organized staff follow-up. Describe it as inquiry/reservation management, not a real-time booking engine. Ask about inventory, deposits, calendar/channel sync, and confirmation procedures.

### Service provider or consultant

Lead with service pages, structured briefs, consultation requests, response status, and demand analysis. Show how one public action becomes an internal record and then a report.

### Training center

Lead with course pages, bilingual registration, participant accounts, protected resources, session requests, feedback, and attendance/rating analysis. Be clear that video learning, certificates, grading automation, and payment are not included by default.

### Data-heavy organization

Lead with private ownership boundaries, file limits, preview, quality checks, explicit cleaning, deterministic report catalog, chart outputs, and export safety. Discuss representative file testing, parser isolation, retention, AI policy, and staging before the visual demo.

### Technical buyer

Lead with the backend trust boundary, tenant/RLS enforcement, revision-aware writes, atomic publishing, idempotency, private storage, workers, readiness, metrics, container hardening, dependency locks, and the exact staging/restore gates. Do not obscure per-environment migration verification, storage operations, or external dependencies.

### Nontechnical buyer

Lead with the journey: build the site, collect a request, manage it, and understand the data. Use plain language and one real workflow. Translate security into access control and recovery benefits; avoid acronyms unless asked.

## 24. Suggested Call to Action

- **Discovery call:** “Let's map one customer journey and identify where Madar can remove the most fragmentation.”
- **Workflow assessment:** “Share a sample page, form, reservation process, and non-sensitive spreadsheet so we can assess fit and boundaries.”
- **Tailored live demo:** “We will configure a synthetic demo around your industry and show the complete journey from public interaction to internal insight.”
- **Limited beta onboarding:** “Start with one tenant, one project, defined staff roles, and measurable acceptance criteria.”
- **Pilot workspace:** “Use a controlled workspace with synthetic or approved low-risk data before planning a broader launch.”
- **Proof of concept:** “Test the highest-risk requirement—such as member permissions, a representative file, or a reporting template—before committing to implementation.”

No call to action should imply self-service paid signup, integrated checkout, or automatic production deployment.

## 25. Internal Presenter Notes

### What to emphasize

- The connected journey from site to customer action to staff operation to analysis.
- Explicit tenant ownership and the distinction between staff and public members.
- Practical late-beta workflows that can be shown end to end.
- Recovery, idempotency, protected pages, and private data handling as business reliability benefits.
- The availability of deterministic reports alongside bounded AI assistance.
- Honest scoping as a strength: Madar is adopted around a proven workflow, not a vague promise to replace everything.

### What not to demonstrate without preparation

- Publishing, unpublishing, archive, or role changes in any shared or production environment.
- Real SMTP, web push, webhook, or customer notification delivery.
- Real customer datasets or AI calls involving sensitive information.
- Large Excel files, advanced quiz logic, public file attachments, complex report layouts, or generated code without an acceptance-tested fixture.
- Custom-domain behavior, payments, billing automation, external calendar/CRM integration, or unsupported provider adapters.
- Admin support-access features as if they are ordinary tenant functionality.

### Features that need seeded demo data

- At least two projects to demonstrate project selection and live binding.
- A five-page branded project with public and protected pages.
- One bilingual contact/registration form and one reservation block.
- Synthetic submissions in New, Contacted, and Closed states.
- Synthetic reservations across dates/statuses.
- Three site members with active, disabled, and distinct project-role states.
- A small, non-sensitive CSV with intentional missing values, Arabic digits, categories, money, dates, and enough rows for charts.
- Saved finance or NGO analysis outputs and one generated chart.
- Fake notification queue records for success, retry, and dead-letter explanation.

### How to handle beta limitations

Use three phrases consistently:

- “Available in the current late-beta product” for demonstrated, configured workflows.
- “Available in configured beta deployments” for workers, AI providers, quotas, focused project permissions, and other environment- or infrastructure-dependent features.
- “Planned or separately scoped; not a current offering” for payments, automated domains, broad integrations, parser-worker completion, and unsupported adapters.

Never turn a limitation into an implied delivery date. Record it as a discovery item with an owner and acceptance condition.

### Demo safety

- Use dedicated synthetic accounts, tenants, project IDs, subdomains, and files.
- Keep email, push, webhook, and billing callbacks disabled.
- Never display environment variables, infrastructure addresses, logs containing identifiers, or browser storage from another environment.
- Keep a pre-recorded walkthrough, screenshots, and exported sample report ready.
- If a live step fails, acknowledge it, switch to the prepared artifact, and explain the verified behavior without repeatedly retrying risky actions.
- Do not use production as a demo fixture.

### When to say “planned”

Say “planned” when the repository has only a partial interface, disabled pathway, missing provider adapter, missing operational deployment, or an unresolved product decision. A table, configuration name, or UI label is not enough evidence of an available feature.

## 26. Final Consolidated Pitch

Growing organizations rarely struggle with only one digital task. They may need a better website, but they also need to collect customer information, manage reservation requests, control member access, follow up on responses, and make sense of the spreadsheets created by daily operations. When each need is handled by a separate tool, staff become the integration layer: copying information, reconciling versions, searching messages, and rebuilding the same context for every report.

Madar is a connected digital operations platform designed to reduce that fragmentation. It gives each organization an isolated tenant workspace where staff can build its public experience, operate the workflows behind it, and turn resulting data into useful insight.

The journey begins with Madar's visual Page Builder. Staff can create multiple projects and multi-page sites, control navigation and branding, arrange text, images, cards, galleries, metrics, and calls to action, and add forms, member registration, protected pages, or reservation blocks without writing application code. Manual save, autosave, local recovery snapshots, unload protection, and revision conflict handling help protect work in progress. A project-specific preview lets the team review the same runtime model used publicly. When the content is ready, Madar validates and publishes a versioned schema, and the organization explicitly selects which published project represents its live site.

Publishing is only the beginning. Public forms are bound to the active project and validated against their published definitions. Madar stores durable submissions with a snapshot of the fields and the publication context that generated them. Hashed idempotency protects automatic retries so one logical action does not become several records. Reservation workflows provide the same kind of structure for open date requests or configured fixed slots, with tenant-scoped records, status management, collision protection, and cancellation support. Staff can review responses and reservations, filter records, update statuses, and use internal notifications from the same workspace.

Organizations can also give customers their own site-member accounts. Public pages remain open, while protected content is delivered only after server-side membership and permission checks. Active or disabled status and project-specific roles make it possible for one member to receive different access in different projects. These customer accounts remain separate from the staff accounts that operate Madar.

Madar then connects operations to understanding. Staff can privately upload CSV or Excel files, review a bounded preview, inspect missing values and quality, normalize common data types—including Arabic numerals and money fields—and export cleaned results. A deterministic analysis catalog covers finance, operations, human resources, NGO and program monitoring, and form-response reporting. Users can create bar, line, scatter, histogram, box, violin, frequency, pie, and heatmap visualizations and retain generated outputs privately. Where configured, a bounded AI assistant can help with statistical questions, while blocking requests to expose full raw datasets or sensitive identifying values. AI supports review; it does not replace professional judgment.

The platform's safeguards are part of the proposition. Tenant authorization, row-level security, backend-mediated privileged writes, secure cookies, CSRF and origin checks, MFA for sensitive administration, audit events, private storage, file validation, quotas, idempotency, and protected pages reduce common operational and security risks. Builder recovery, atomic publishing, durable queues, health signals, structured metrics, container hardening, and backup/restore tooling support reliable service operations. These are concrete controls, not claims of absolute security, compliance, uptime, or guaranteed recovery.

Madar is in late beta, and the offer is deliberately honest. There is no integrated payment gateway or automated billing. Email and web-push delivery depend on configured infrastructure. The canonical public address is currently platform-hosted, remote data ingestion remains disabled, parsing has strict limits, and some advanced form, permission, AI, storage, and report capabilities require controlled rollout and staging verification. Production restore drills and environment-specific monitoring remain operational responsibilities.

For the right organization, those boundaries do not diminish the current value; they make the path to value clearer. Madar is best introduced through a guided pilot focused on one meaningful journey: publish a credible site, collect a real kind of request using synthetic or approved data, give staff an efficient way to operate it, and produce one decision-ready insight. Once that workflow is proven, the organization can expand from a connected foundation instead of adding another disconnected tool.

Madar's promise is practical: **build the experience, engage customers, operate the work, and understand the data—within one controlled platform.**
