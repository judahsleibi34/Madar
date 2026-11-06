# Establish Separate Reservations and Calendar Domains with Controlled Read-Only Integration

**ADR ID:** ADR-FE-004
**ADR namespace:** `ADR-FE-NNN` identifies Madar frontend architecture decisions; historical ADR identifiers outside this namespace are unchanged.
**Status:** APPROVED — LOGICAL ARCHITECTURE ONLY
**Decision owner:** Madar product owner
**Approval authority:** Madar product owner
**Affected business domains:** Shared Page Builder, Reservations, Calendar / Planning, and hosted/public website delivery
**Affected technical modules:** Page Builder reservation authoring and rendering, hosted reservation runtime, reservation APIs and persistence, Calendar workspace, events, tasks, reminders, access control, and external synchronization
**Prepared:** 2026-11-06
**Product-owner approval:** LOGICAL DECISION AND FINAL ADR WORDING APPROVED — LOGICAL ARCHITECTURE ONLY
**Approval date:** 2026-11-06
**Final ADR document approval:** APPROVED
**Final document approval date:** 2026-11-06
**Approved scope:** Logical ownership, dependency direction, preservation of the existing reservation-to-calendar projection, and staged implementation only
**Implementation authorization:** NOT AUTHORIZED
**Repository-wide adoption:** PENDING INDEPENDENT REVIEW AND AUTHORIZED MERGE
**Accountable technical maintainers:** PENDING OWNER DECISION
**Re-evaluation triggers:** A new cross-product booking capability; reservation rescheduling; reservation reminders; writable Calendar synchronization of bookings; a material change to reservation availability; a new shared scheduling interface; or changes to the existing projection contract
**Constitutional impact:** No constitutional amendment required

## Context and evidence

### Verified current state

- Page Builder authors reservation definitions as `reservationBlock` elements, including flexible or restricted booking modes, dated time slots, weekly repetition, per-session capacity, and composed form items (`web/frontend/src/components/PageBuilder/tabs/ReservationsTab.jsx:204-323`; `web/frontend/src/components/PageBuilder/blocks/reservationAvailability.js:7-84`).
- Reservation definitions can be placed by reference through `connectedReservationBlockId`; resolution preserves the referenced element and falls back to the placement when necessary (`web/frontend/src/components/PageBuilder/core/PageBuilder.reservations.js:12-39`, `web/frontend/src/components/PageBuilder/core/PageBuilder.reservations.js:55-71`).
- The hosted runtime resolves the reservation definition, renders the shared `ReservationBlock`, and submits a public builder event with an idempotency key (`web/frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.jsx:1638-1707`, `web/frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.jsx:2203-2237`; `web/frontend/src/components/PageBuilder/services/PageBuilder.publicApi.js:127-149`).
- FastAPI resolves the published project and block, checks public entitlement and resource access, validates custom answers, configured slots, and seats, then persists a reservation and returns a cancellation token (`web/backend/routes/public_site_routes.py:5172-5241`, `web/backend/routes/public_site_routes.py:5257-5357`). Public token-based cancellation is a separate endpoint (`web/backend/routes/public_site_routes.py:5360-5438`).
- Authenticated reservation management is tenant-scoped and entitlement-checked. Existing routes list or retrieve bookings and update reservation status (`web/backend/routes/builder_routes.py:2072-2185`).
- Reservations persist in `builder_reservations`, with tenant, project, block, customer, time, status, payload, and field-snapshot data (`web/database/migrations/044_create_builder_reservations.sql:9-31`).
- Calendar has separate persistence for calendars, memberships, events, attendees, event reminders, tasks, dependencies, connections, conflicts, and invitation review (`web/database/migrations/061_create_calendar_platform.sql:6-209`). Calendar events and tasks have distinct write models and recurrence rules (`web/backend/routes/calendar_routes.py:641-732`).
- Calendar bootstrap reads `builder_reservations`, converts each visible booking to a `source_type: "reservation"` item with a synthetic `reservation::` identifier, and marks it `read_only: true`; it does not insert a `calendar_events` row (`web/backend/routes/calendar_routes.py:475-575`, `web/backend/routes/calendar_routes.py:1242-1274`). The frontend includes these projections in Calendar views and refuses to open them for event editing (`web/frontend/src/components/DashboardBuilder/ReservationCalendarPage.jsx:679-685`, `web/frontend/src/components/DashboardBuilder/ReservationCalendarPage.jsx:759-765`).
- Calendar access requires active tenant membership and the `internal_calendar` entitlement. Calendar, event, task, project-reference, and task-owner lookups remain tenant-scoped and capability-checked (`web/backend/routes/calendar_routes.py:123-130`, `web/backend/routes/calendar_routes.py:171-279`).
- Calendar owns event mutations, recurrence, tasks, task reminders, and task synchronization (`web/backend/routes/calendar_routes.py:1374-1430`, `web/backend/routes/calendar_routes.py:1444-1669`). External synchronization is modeled against Calendar connections and events rather than reservation records (`web/database/migrations/061_create_calendar_platform.sql:158-195`).

### Functionality not established as implemented

Bounded repository searches performed for this decision did not establish:

- a reservation rescheduling endpoint or reservation-owned rescheduling lifecycle;
- a reservation-specific reminder model or delivery pipeline;
- E-learning appointment booking;
- a writable Calendar reservation event or synchronization path; or
- a general shared Scheduling Engine.

The public reservation response returns a cancellation token, but the inspected hosted submission call does not retain or present that response (`web/backend/routes/public_site_routes.py:5349-5357`; `web/frontend/src/components/PageBuilder/runtime/TenantSiteRuntime.jsx:1665-1695`). Therefore an end-to-end public cancellation user experience is not established by the inspected frontend path.

## Decision

Madar establishes **Reservations** and **Calendar / Planning** as separate logical business domains with a narrow, explicit, read-only integration from Reservations into Calendar.

Reservation remains a Shared Page Builder component for authoring, configuration, placement, preview, and hosted visual presentation. Reservations owns booking and availability semantics. Calendar / Planning consumes an authorized projection for display without taking ownership of the booking lifecycle.

This is a logical ownership and dependency-direction decision. It does not move files, rename APIs or schemas, create a public interface, change application behavior, or authorize implementation or migration.

### Shared Page Builder owns

- reservation-block presentation;
- reservation editor integration;
- block placement in authored pages;
- shared schema and rendering mechanics;
- preview and hosted-rendering integration; and
- compatibility of persisted Page Builder content.

Shared Page Builder does not own authoritative reservation persistence, tenant authorization, capacity enforcement, or booking-state transitions.

### Reservations owns

- booking definitions and semantics;
- reservation availability configuration rules;
- the booking lifecycle;
- capacity and seat-allocation behavior;
- reservation statuses;
- cancellation semantics;
- reservation-specific business adapters; and
- public booking behavior.

Frontend validation and presentation do not substitute for authoritative FastAPI validation.

### Calendar / Planning owns

- calendar event management;
- internal tasks and agenda;
- event and task recurrence;
- event and task reminders;
- Calendar access controls;
- external calendar integrations;
- Calendar-specific synchronization behavior; and
- Calendar presentation and views.

Internal Tasks remain within Calendar / Planning unless a future approved decision changes ownership.

### FastAPI remains authoritative for

- tenant and resource authorization;
- booking persistence;
- capacity enforcement;
- slot and availability validation;
- idempotency;
- reservation status transitions;
- public cancellation;
- Calendar event and task persistence;
- Calendar permissions and visibility;
- external provider authorization; and
- synchronization and conflict handling.

Frontend metadata, Page Builder content, and Calendar presentation must never grant backend permission or replace server-side validation.

## Contracts and compatibility

### Reservations-to-Calendar integration contract direction

The existing direction is preserved:

```text
Reservations
    |
    | authorized read-only reservation projection
    v
Calendar / Planning
```

- A reservation remains a reservation record.
- Displaying a reservation in Calendar must not automatically create a `calendar_events` record.
- Calendar may display only fields authorized by the backend projection.
- Calendar must not silently mutate booking state.
- Reservation status changes remain controlled by Reservations services.
- Calendar event changes remain controlled by Calendar services.
- Cross-domain integration must use explicit, documented contracts.
- No shared reservation/Calendar persistence model is approved.

The current projection is existing implementation evidence, not a newly declared permanent public API. Any proposal to formalize or change its fields, version, authorization, errors, time semantics, or compatibility policy requires documented consumer review and the applicable approval.

### Shared-contract policy

- Shared date/time utilities may be reused only when their semantics are compatible and verified for every consumer.
- Reservation availability and Calendar free/busy availability are separate business concepts. Reservation availability controls bookable offerings; Calendar availability limits or communicates Calendar occupancy according to Calendar authorization and privacy rules.
- Reservation weekly date patterns, Calendar event RRULEs, and task recurrence are not automatically interchangeable.
- A generalized Scheduling Engine is not approved.
- A shared Calendar UI library is not required by this decision.
- A new cross-domain scheduling contract requires demonstrated consumers, an accountable owner, explicit semantics, compatibility review, and proportionate tests.

### Page Builder contracts and compatibility

Any later implementation must preserve or explicitly migrate, validate, and approve changes to:

- existing `reservationBlock` identifiers;
- existing reservation configuration schemas and defaults;
- `connectedReservationBlockId` references;
- published website schemas and historical reader behavior;
- historical booking records, field snapshots, and submitted data;
- existing availability, weekly-slot, capacity, and seat behavior;
- hosted/public booking rendering and submission;
- tenant-authored themes and authored-output isolation;
- Arabic/English and RTL/LTR behavior;
- responsive behavior, keyboard use, and accessibility; and
- Page Builder editor, preview, published-site, and hosted-runtime parity.

Page Builder must not become authoritative for reservation persistence, tenant authorization, commercial entitlement, or public-resource permission.

## Alternatives considered

### Option A — One combined Scheduling domain

Rejected. Reservations, Calendar events, internal tasks, and provider-synchronized items have distinct persistence, authorization, data meaning, and lifecycles. Current source evidence does not justify a generalized shared Scheduling Engine.

### Option B — Separate Reservations and Calendar without an explicit integration-contract direction

Viable but not selected. It preserves domain separation but is less explicit about the existing read-only projection and the review required for future cross-domain contracts.

### Option C — Separate domains with narrowly shared contracts

Selected. It records existing logical separation, preserves the read-only projection, and permits only demonstrated, compatibility-reviewed shared contracts. It implies no broad scheduling abstraction.

## Ownership and consumers

| Capability | Logical owner | Known consumers | Contract status |
|---|---|---|---|
| Reservation authoring and block rendering mechanics | Shared Page Builder | Website authoring, preview, hosted runtime | Existing implementation; persisted compatibility applies |
| Booking and reservation availability semantics | Reservations | Hosted visitors, reservation management, Calendar projection | Existing implementation; no new public frontend interface approved |
| Read-only reservation projection | Reservations provides; Calendar / Planning consumes | Calendar workspace | Existing backend integration; formal public contract/versioning remains unapproved |
| Calendar events, recurrence, access, and synchronization | Calendar / Planning | Authenticated Calendar users and provider adapters | Existing implementation |
| Internal tasks, agenda, and task reminders | Calendar / Planning | Authenticated Calendar users and provider adapters | Existing implementation; future ownership change requires a decision |
| Date/time utilities | Current implementation owner at each call site | Reservations and Calendar where separately used | Reuse permitted only after semantic compatibility review |

Accountable technical maintainers for Shared Page Builder reservation integration, Reservations, and Calendar / Planning are `PENDING OWNER DECISION`.

## Tenant, security, and authorization impact

This decision changes no trust boundary. FastAPI remains the authority for authenticated tenant context, public resource access, permissions, entitlements, persistence, availability, capacity, statuses, and Calendar visibility.

The reservation projection must remain tenant-scoped and backend-filtered. Calendar must not infer permission from a synthetic identifier, `source_type`, visibility metadata, route presence, or UI state. Public booking and cancellation must retain their existing published-resource checks, rate limits, token handling, validation, and server-side write controls.

Any future writable reservation integration, service-ownership change, authorization change, shared persistence, or provider synchronization of bookings requires separate security review, compatibility validation, and explicit product-owner approval.

## Commercial and lifecycle impact

This ADR does not decide or change subscriptions, product packaging, entitlement identifiers, navigation visibility, launch state, hosted exposure, or deployment independence. Current `reservations`, `reservation_management`, and `internal_calendar` checks are implementation evidence, not authorization to redefine commercial packaging.

## Implementation and dependency impact

Implementation is **NOT AUTHORIZED**. This ADR creates no source move, extraction, adapter, package, registry, endpoint, schema, migration, dependency, or automated boundary check.

Future work must first identify exact provider and consumer call sites; classify interfaces as existing, adapter-required, or proposed; document data shape, authorization, time-zone behavior, errors, versioning, and compatibility; and preserve a legacy baseline. A direct import into another domain's private implementation requires the governance review or exception defined by the constitution.

## Non-goals and exclusions

This decision does **not** authorize:

- physical file moves or extraction;
- API, route, identifier, or schema renaming;
- a generalized Scheduling Engine;
- shared Reservations/Calendar storage;
- replacement of reservation blocks;
- writable reservation projections;
- changes to reservation or Calendar availability semantics;
- changes to commercial subscriptions or entitlements;
- changes to backend authorization;
- new dependencies or plugin infrastructure;
- migration, release, deployment, or production mutation; or
- any application or configuration modification.

## QA, CI, and release impact

No application tests, builds, servers, migrations, or deployments were executed for this documentation-only decision. Existing relevant evidence includes:

- `web/frontend/src/components/PageBuilder/blocks/ReservationBlock.test.jsx`, `ReservationBlock.responsive.test.js`, `reservationAvailability.test.js`, and `reservationForm.test.js` for rendering, authored form behavior, availability, Arabic/RTL, accessibility-related markup, and responsive contracts;
- `web/frontend/src/components/PageBuilder/tabs/ReservationsTab.test.jsx`, `ReservationBlockBuilder.test.jsx`, `ReservationEditor.i18n.test.jsx`, and `reservationRepeat.test.js` for authoring, connections, weekly rules, localization, and RTL behavior;
- `web/frontend/src/components/PageBuilder/core/PageBuilder.reservations.test.js` and `PageBuilder.reservationPalette.test.js` for block lookup, connected references, and placement;
- `web/frontend/src/components/PageBuilder/runtime/reservationSubmission.test.js` for idempotency keys and submission error mapping;
- `web/frontend/src/components/DashboardBuilder/CalendarReservationsTable.test.jsx`, `ReservationCalendarPage.tasks.test.jsx`, and `ReservationCalendarPage.connections.test.jsx` for reservation presentation, Calendar/tasks behavior, and connection workflows;
- `web/frontend/src/components/DashboardBuilder/utils/calendarEventTime.test.js`, `calendarTaskSchedule.test.js`, and `calendarWorkspaceCache.test.js` for time-zone conversion, task recurrence/scheduling, and scoped workspace caching;
- `web/backend/tests/test_builder_reservations.py`, `test_reservation_seats.py`, and `test_reservation_seats_postgres.py` for public booking/cancellation behavior, status/capacity rules, idempotency, concurrency, and seat enforcement;
- `web/backend/tests/test_reservation_integrity_release_contract.py` for reservation capacity release-contract evidence;
- `web/backend/tests/test_calendar_routes.py`, `test_calendar_authorization_service.py`, `test_calendar_event_concurrency_database.py`, and `test_calendar_mutation_service.py` for Calendar projection, access matrices, recurrence, mutation, and concurrency behavior;
- `web/backend/tests/test_calendar_reminder_service.py` and `test_calendar_task_sync_queue.py` for event/task reminders and task-provider queues; and
- `web/backend/tests/test_calendar_inbound_sync.py` and `test_calendar_oauth.py` for external-provider synchronization, tenant scoping, and authorization state.

These files are evidence of existing coverage; they were not executed in this phase and are not reported as passing.

Explicit compatibility/QA gaps remain for reservation rescheduling, reservation-specific reminders, end-to-end public cancellation UX, writable or synchronized Calendar reservation behavior, and any new cross-domain scheduling contract. Any future change must also select relevant tenant/resource authorization, published-schema, hosted-runtime, Arabic/RTL, accessibility, responsive, time-zone/DST, concurrency, and release checks.

- **Existing architecture checks:** Existing reservation, Page Builder, hosted-runtime, Calendar, authorization, concurrency, reminder, synchronization, RTL, accessibility-related, and release-contract tests; automated enforcement of this logical boundary is not claimed.
- **Proposed architecture checks:** Any new projection-contract, forbidden-private-dependency, or compatibility checks require separate implementation approval and an approved legacy baseline.
- **Accountable CI enforcement owner:** PENDING OWNER DECISION
- **Planned verification milestones:** PENDING OWNER DECISION
- **Review trigger/date:** The re-evaluation triggers in this ADR; no calendar review date approved

All root `AGENTS.md`, constitution, security, tenant-authorization, QA, CI, migration, deployment, and production-release requirements remain unchanged.

## Rollback, migration, and failure handling

There is no runtime rollback, data migration, or deployment because no implementation is authorized. Before implementation, this logical decision may be superseded or withdrawn only through the governed ADR process.

Any future persisted, published, or cross-domain contract change must define compatibility, partial-failure behavior, migration, rollback limits, projection failure handling, and recovery in its separately approved change. This ADR does not authorize production data mutation.

## Risks and unresolved questions

- Accountable technical maintainers for Shared Page Builder reservation integration, Reservations, and Calendar / Planning: `PENDING OWNER DECISION`.
- Exact public contract name, schema, owner, version, errors, and compatibility window for the reservation projection: not approved.
- Whether and how the hosted runtime should retain and present public cancellation credentials: unresolved.
- Reservation rescheduling semantics and ownership details: unresolved beyond Reservations being the booking-lifecycle owner.
- Reservation-specific reminder policy, channels, recipients, and delivery ownership: unresolved.
- Whether a future E-learning appointment capability will consume Reservations or define separate semantics: unresolved.
- Whether any future booking may synchronize to an external provider: unresolved and requires re-evaluation.
- Whether Internal Tasks should later become a separate Work Management domain: unresolved; Calendar / Planning remains the current logical owner.
- Architecture CI accountability and implementation milestones: `PENDING OWNER DECISION`.
- No generalized Scheduling Engine, shared Calendar UI library, physical extraction, or implementation schedule is approved.

## Approval record

- **Product-owner decision:** APPROVED — Option C, separate Reservations and Calendar / Planning domains with narrowly shared contracts
- **Decision date:** 2026-11-06
- **Approved scope:** Logical ownership, dependency direction, preservation of the existing read-only reservation-to-Calendar projection, and staged implementation only
- **Implementation:** NOT AUTHORIZED
- **Conditions:** Preserve existing Page Builder and published-content compatibility, separate persistence and lifecycles, FastAPI authority, read-only projection behavior, tenant/resource authorization, availability semantics, historical data, RTL/accessibility requirements, and all QA/release protections
- **Repository adoption:** PENDING INDEPENDENT REVIEW AND AUTHORIZED MERGE
- **Related exception IDs:** None
- **Related constitutional amendment:** None
- **Supersedes / superseded by:** None

### Final document approval history

- **Event:** FINAL ADR DOCUMENT APPROVAL
- **Authority:** Madar product owner
- **Date:** 2026-11-06
- **Document:** ADR-FE-004
- **Approved scope:** Separate Reservations and Calendar logical business domains, Shared Page Builder presentation integration, and authorized read-only reservation projection.
- **Review basis:** Complete current wording independently reviewed in Phase 29.1.
- **Approval distinction:** This final-wording approval is separate from the earlier logical direction approval recorded above; its historical date and scope remain unchanged.
- **Implementation:** NOT AUTHORIZED
- **Repository adoption:** PENDING INDEPENDENT REVIEW AND AUTHORIZED MERGE
