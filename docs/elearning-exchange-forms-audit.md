# Exchange applications through E-Learning Forms

## Pre-implementation audit (2026-10-11)

Completed before implementation. Source: migration140, migration141,
academy_owner_service/routes, academy_programme_service/routes,
elearning_forms_service/routes, AcademyExchangeOpportunities,
AcademyProgrammesPage, AcademyDataBlock, LearningFormRenderer and the Forms inbox.
Read-only local database inspection reports core141, zero Exchange applications
and zero opportunities. This is local evidence only, not a production inventory.

### A. Retain

Tenant-owned opportunities retain title, descriptions, institution/location,
dates, deadline, requirements, capacity and lifecycle/revision. Exchange requires
active tenant membership and an active learner with a currently accessible active
enrollment. Existing capability gates require programme flags and website rights.
Migration140 serializes submissions and approvals on the opportunity row.
Capacity counts **approved** legacy applications, not pending submissions.
Legacy owner reviews remain required for historical operations.

### B. Duplication

academy_submit_application stores a fixed set of Exchange questions in
academy_applications.details. AcademyProgrammesPage independently renders them.
This duplicates the independent Forms field schema, validation, runtime, files,
immutable versions and responses. Builder Exchange cards currently link to that
specialized learner form. The owner shortcut points to the specialized inbox.

### C. Historical compatibility

Existing academy_applications Exchange records, details, history, tenant scoping
and owner review must survive unchanged. Schema142 will reject new specialized
Exchange submissions while preserving exact historical idempotent replays.
Affiliate and Support submission/review implementations remain unchanged.
Existing legacy opportunities remain editable/closable/archivable; publishing
a new or newly activated opportunity requires an active associated Form.

### D. New flow

Owner selects an independent E-Learning Form; its questions use the existing
editor. Learner opportunity detail uses the existing renderer and upload/
conditional-validation pipeline. A response stores answers/files/version once,
with immutable nullable opportunity context. A lightweight Exchange decision
references that response and stores only status/revision/reviewer/note.
Read/unread and Forms notes remain distinct from Exchange approval.

The existing Forms inbox accepts an opportunity filter; owner shortcuts and
notifications reach those same response records. Builder only presents links.
Forms notifications remain the single submission pipeline with an opportunity
title; decisions emit Exchange domain notifications. Application and approval
checks run under the opportunity lock. Approved legacy and Forms-backed records
both consume places; pending records do not. No generic Forms submission can
create an Exchange decision without validated opportunity context.

### E. Schema requirement

141 has no opportunity-to-form association or response opportunity context and
its immutable response trigger excludes any undeclared context. Storing these
in editable questions/answers, notes or legacy details would undermine ownership
and immutable history. Therefore an additive migration142 is necessary: composite
tenant/form and tenant/opportunity foreign keys, immutable response context,
minimal decision/history storage and guarded functions. Migrations001–141 and
their existing release artifacts remain immutable. The142 candidate remains
unselected; production115 and deployment/migration orchestration are unchanged.

## Implementation and validation

### 1. Existing architecture

Migration140 owns opportunities and legacy application details/history. The old
learner form used fixed Exchange questions; public Builder cards linked to it.
Independent Forms arrived in141. The pre-implementation findings above remain
an audit record, not a claim about production inventory.

### 2. Duplication removed

The learner no longer renders specialized Exchange questions. New legacy API
submissions reject immediately, including on141;142 also retires direct SQL
submission while retaining exact historical idempotent replays. The generic
Forms validation/file pipeline is the single answer submission engine.

### 3. Opportunity model retained

Existing opportunity fields, optimistic revision and draft/published/closed/
archived lifecycle remain. Capacity cannot be reduced below approved places.
The form association cannot change after an opportunity has received responses.

### 4. Form association

Nullable application_form_id has a composite tenant/form foreign key. The guarded
owner function rejects unknown, foreign and archived forms. Publishing requires
an active Form; backend publication/association additionally requires existing
Exchange and Forms entitlements. Legacy records gain null associations without
rewriting their data.

### 5. Response and context

Forms retain immutable answers, files, version, tenant and member.142 adds an
immutable nullable opportunity_id. Composite foreign keys enforce tenant scope;
Exchange context requires an authenticated member. A member has one response per
opportunity. Generic submissions without opportunity context remain generic Form
responses and do not create an Exchange application or decision.

### 6. Domain decisions

academy_exchange_decisions references a Forms response and stores only status,
revision, reviewer, timestamp and internal note. Its immutable history records
submitted → under_review → approved/not_approved transitions. Owner/admin
membership is server-derived. Forms read/unread and notes grant no approval.
Internal review notes are excluded from the learner projection.

### 7. Capacity

Approved legacy applications plus approved Forms decisions consume places.
Pending/under-review applications do not reserve capacity. Submission, availability
and both approval paths serialize on the same opportunity row. A real two-connection
race verified that two pending applications for capacity1 produce exactly one
approval and one42501 rejection. Historical approvals also block new approvals.

### 8. Legacy compatibility

Historical details, workflow history and review endpoints remain tenant-scoped
and unchanged. A clearly labeled historical applications shortcut remains in the
opportunities page. No legacy answers were migrated, deleted or copied. Affiliate
and Support submission/review behavior remains intact; the retained141 suite
runs before the142 upgrade, and142 tests exercise historical replay/review and
unchanged Affiliate submission.

### 9. Owner UX

Exchange navigation now opens Opportunities. The editor provides Application
Form, Create Form and Edit Selected Form through the existing independent editor.
Return navigation preserves unsaved opportunity values and selects the edited
Form. Empty/unavailable Forms states are explicit. View Applications links to
Forms responses with both form_id and opportunity_id filters. Historical reviews
have an explanatory banner, rather than a second new submission inbox.

### 10. Learner UX

/my-learning/exchange lists available opportunities; /:opportunityId shows detail,
requirements, deadline, capacity and Apply. Apply uses LearningFormRenderer with
its existing conditional validation, uploads, RTL and success state. Submitted
members see domain status instead of another application form. Closed/full
opportunities remain accessible to their existing applicant through the precise
notification/detail link. The fixed course player implementation is unchanged.

### 11. Builder/public behavior

Existing Exchange cards and programme links lead to the opportunity route;
guests use the existing academy login returnTo flow. Builder remains presentation.
Public opportunities require existing Exchange and Forms capability and142;
their associated Form must be active. No Builder form storage is accessed.

### 12. Forms inbox

The same response appears in the aggregate inbox, associated Form inbox and
opportunity-filtered shortcut. Filters, search, pagination, read/unread, files,
notes and entitled CSV export share existing APIs. An opportunity-filter notice
can clear that context; selecting another Form clears the opportunity filter.
Response detail embeds the minimal Exchange decision/history section.

### 13. Notifications

The existing learning_form_response pipeline emits one owner event per recipient
with “New Exchange application for <title>” and the exact Forms response path.
Existing configured learner confirmation behavior remains. Exchange review emits
learning_exchange_<status> through Madar's canonical event/outbox/preferences
pipeline. Client and server allowlists now admit only the bounded Exchange UUID
and Forms response UUID routes; tenant and URL checks remain.

### 14. Entitlements

Existing programme flags and website_publish govern Exchange; Forms entitlements
govern association, activation, rendering/submission and response management.
Publication also requires the existing public_form_links runtime capability, so
an unusable Form cannot be activated. Missing142 returns an upgrade-required error. No parallel plan or entitlement
store was introduced. Historical legacy reviews do not require Forms. Loss of Exchange review entitlement
suppresses its decision section without blocking independently entitled Forms history.

### 15. Security

Database and service tests cover foreign associations/context/review, required
membership, closed/archive/deadline/capacity rejection, denied direct service-role
decision writes, immutable response context/history, and same-tenant inbox filters.
Raw frontend IDs provide no authority. The multipart parser, private storage,
file validation, quota accounting and cleanup remain the shared Forms pipeline.
No new answers enter academy_applications or builder_form_submissions.

### 16. Schema/release

Mirrored142 is additive and necessary for the relationships and domain decisions.
All345 pre-existing migration/release artifacts match their prior SHA256 baseline;
001–141 are untouched. Exact new142 manifest/bridge/helper pins extend immutable
history; both source validators still reject unknown future namespaces and SQL
changes. The active production115 descriptor is unchanged and selects no SQL.
Deployment and automatic migration orchestration are unchanged.

The local application database remains141.142 was applied only to a marked,
disposable rehearsal database, with populated141 preservation and transactional
rollback verified. The explicit local launcher recognizes the142 contract but
does not perform an upgrade. No production migration or local programme opt-in
was performed.

### 17. Files and routes

Backend: academy_exchange_service (new), academy_owner_service/routes,
elearning_forms_service/routes, academy_programme_service (Exchange-only retirement),
elearning_academy_service public projection and notification_action_service.
New member routes: GET /elearning/owner/exchange/opportunities/{id},
POST /elearning/owner/exchange/opportunities/{id}/responses. New owner decision:
PUT /elearning/owner/exchange/responses/{response_id}/decision. Existing Forms list
and export accept opportunity_id; response detail exposes guarded Exchange context.

Frontend: LearnerExchange and ExchangeResponseDecision (new), owner opportunities,
shared Form editor/renderer/inbox/detail, programme legacy presentation, learner
shell/routes, owner navigation, Builder AcademyDataBlock, notification allowlist
and English/Arabic strings. LearnerAccount also gains its missing academyPath
import: a pre-existing lint error in the empty-course profile branch, unrelated to
Exchange, with no finance or Affiliate behavior change.

Release: mirrored142, new migrations-115-142.json/schema-114-142-bridge.json,
exchange_forms_candidate, source validators, explicit local contract selection,
rehearse_migration_142 and the three mandatory release-policy documents.
Tests: new Exchange service/SQL/UI cases, precise notification routes, intentional
retired-form and navigation assertions, and retained-source tampering coverage.

### 18. Test evidence

- Focused isolated backend:70 passed; related backend modules:196 passed.
- Full intended Docker backend CI:2944 discovered,2403 passed,541 skipped;
  zero failures/errors and zero external connection attempts/sites. Image96e10c23473d.
- Disposable database rehearsal:299 retained141 tests plus8 new142 tests passed;
  populated141 preservation, rollback and concurrent approval verified.
- Frontend:206 files,1523 passed,1 skipped; focused new UI:6 passed.
- ESLint, production build with same-origin /api enforcement, dependency locks,
  migration mirrors/transitions, secret hygiene, forward release source and
  diff whitespace checks pass. pip check reports no broken requirements.
- Two existing duplicate-content migration warnings for013/014 remain unchanged.

### 19. Native versus fixture browser evidence

Chrome authenticated natively with the existing local testing account. Native
Exchange availability returned403 for the existing disabled programme; the local
application database remains141. No account-specific workaround or opt-in was made.

The enabled owner → Form submit → same Forms inbox → owner approve → learner status
flow used explicitly labeled in-memory API fixtures. It passed English and Arabic
at1440px and390px, including owner editor/Form selection, opportunity detail,
conditional required-field hiding, Forms confirmation, response/decision and legacy
presentation. There were no page errors or page overflow; private review notes
were absent from learner detail. Screenshots: /tmp/exchange-qa; browser log:
/tmp/exchange-browser.log. These fixtures demonstrate browser UX/API requests,
not native HTTP-to-database persistence. SQL authority was independently exercised
on the real disposable142 database.

### 20. Remaining boundaries

The source implementation and all final regression gates pass, including the
complete backend rerun after the entitlement corrections. Native enabled HTTP end-to-end verification requires an explicit
local142 upgrade/contract selection and an already configured Exchange programme;
this task deliberately leaves application configuration/data unchanged. Production
activation requires the governed release/backup/upgrade process. Existing legacy
programme reports remain views of historical specialized records; new Exchange
applications and decisions are authoritative in Forms and their review context.
No payment/provider/EduHope/course configuration or opportunity content was seeded.
