# Madar E-Learning capabilities and EduHope configuration

Existing implementation remains authoritative. Live payments are unconfigured; no production mutation or deployment is authorized by this work.

| Requirement | Existing files to extend | Missing work |
|---|---|---|
| Students, levels, topics, media | `elearning_participation_service.py`, `elearning_structure_service.py`, `elearning_content_service.py`, existing course screens, migrations 120–126 | Reuse without competing entities; obtain the actual 89-topic content before configuring a tenant |
| Exams and progress | `elearning_assessments_service.py`, assessment placements/completion events (127–128), `ELearningProgressPage.jsx` | Owner aggregates/export; five CEFR placements use existing engine, 70% and retakes |
| Certificates | `elearning_credentials_service.py`, migration 130 | Scoped CEFR issuance using existing immutable credential/PDF/verification engine |
| Notifications | `notification_service.py`, outbox/delivery/preference services, worker, `NotificationProvider.jsx`, `NotificationsPage.jsx` | Transactional targeted learning producers, learner authorization/navigation, development launcher |
| Referrals/rewards | `academy_referral_service.py`, migration 136, `LearnerAccount.jsx` | Purchase/affiliate eligibility, withdrawals, verified-sales eligibility; preserve old tenant behavior unless explicitly enabled |
| Payments/history | `elearning_commerce_service.py`, migration 129 | Provider adapter pending provider choice/configuration; retain server verification and immutable events |
| Affiliates/support/exchange | Existing tenant users, memberships, settings and referral engine | Private applications/review history; affiliate status separate from staff roles |
| Wallet/withdrawals | Existing reward/reversal rows and checkout history | Atomic reservation/payout lifecycle and immutable audit history, no editable balance column |
| Website | `AcademyThemePage.jsx`, Academy Builder profile (132–133) | Existing Builder supports presentation pages; learning/auth routes remain system-owned |
| Settings/navigation | `elearning_settings_service.py`, workspace/sidebar/routes | Tenant-configured programme policy and workflow screens, bilingual labels |

Conflicts: existing referral account issues codes without purchase; local test money must remain separate from payable balances and verified sales; course prices already belong to commerce offerings (do not add a second authoritative price); certificate issuance currently consumes course-only completion. No tenant membership role will become affiliate/admin automatically.

Schema work must use new mirrored migrations, retain immutable 001–138 files and pinned manifests, leave active schema115 release unselected/non-migrating, and fail closed before the new schema. No production orchestration changes are planned. Candidate validation metadata and this policy documentation must change together.

Order: targeted notification integration and learner inbox; opt-in referral eligibility and atomic applications/withdrawals; provider interface once selected (disabled until configured); owner/student screens; scoped certificates and aggregates/export; Builder page verification. Test on a marked disposable PostgreSQL rehearsal before considering application database migration. Tenant-specific course seeding requires the intended course identity and real syllabus, neither supplied yet.

## Implemented extension

- Existing Students, levels/sections, topics/lessons, content blocks, assessment
  attempts, formal completions and credential engine remain the source of truth.
  The Students screen browses existing profiles; course management retains its
  existing enrollment, progression, assessment and certificate screens.
- Owner navigation adds Students, Affiliates, Referrals, Rewards, Tuition Support,
  Exchange Programme, Finance/Transactions/Withdrawals and E-Learning/Reports.
  Existing Notifications and Settings remain in place. Labels are English/Arabic
  and screens use the existing Madar layout with RTL support.
- Private programme applications support submission, review, approval/rejection,
  and affiliate suspension/reactivation, with required terms acceptance and an
  immutable snapshot of configured terms. An affiliate gains referral eligibility,
  never a staff role. Optional Tuition Support information can be made required.
- Wallet values derive from existing verified rewards, reversals and withdrawals.
  Local test money is excluded. Withdrawals reserve available funds and follow
  pending → approved → processing → paid or rejected. Final payout is idempotent;
  rejection releases the reservation. Refunds and reviews serialize on the same
  tenant/user lock, and insufficient balances prevent further payout.
- Support Programme eligibility uses the tenant-configured verified-sales threshold or active-learner rule. Newly configured academies have no default sales threshold. Refunds recalculate
  eligibility and approval rechecks it. Exchange requires an active learner with
  actual course access independently of referral counts. No manual eligibility
  override bypasses these rules.
- Purchase or approved affiliate status can gate configured academy referral codes and attribution.
  Existing attribution constraints retain self-referral, duplicate, tenant and
  direct-only protections. Click counts are rate-limited statistics, never financial
  authority. Legacy academies retain their prior referral behavior unless opted in.
- Owner financial history projects existing payment events, earned/reversed rewards
  and immutable withdrawal history. Currency changes cannot relabel existing academy
  referral history. Review shows the user's role, verified sales, wallet and history.
- Reports reuse existing progress records and provide enrollment/student/activity,
  topic/level/course completion, attempts, average scores, pass rate, certificate,
  application and reward aggregates plus current level/progress distributions.
  Filters include course, student and level, date and status. CSV exports
  escape spreadsheet formula prefixes. Some aggregate totals are independently
  filtered by course/user/date; a level filter selects enrollment rows containing
  that level, rather than limiting all financial or assessment totals to it.
- CEFR configuration attaches A1–C1 to existing section final assessments, requires
  70% and retakes, and issues independent credentials through the existing engine.
  Optional full-course certificates continue through their existing configuration.
- Existing Academy Builder manages public presentation pages and the Theme screen.
  It can supply Home, Course presentation, How It Works, Affiliate, About, Tuition,
  FAQ and Contact content without another page-management system. Authentication
  and learning routes remain reserved system routes. No EduHope copy/content or
  real syllabus was invented or seeded.

## Notifications

Transactional producers cover learner registration/linking, enrollment and status,
manual and paid access changes, topic/level/course completion, exam submission/result,
credential issue/revocation, checkout status, referral attribution, reward creation/
reversal, Tuition Support eligibility changes, programme submission/review and
withdrawal submission/review. Relevant owner events include enrollment, milestones,
course/assessment/lesson/material publication, payment/reward changes and applications.
Sign-in notifications are not added; existing security audit events remain authoritative.
Rewards use the existing earned/reversed lifecycle; no extra reward-approval state
or notification is invented.

They reuse Madar notification events, recipient-bound outbox intents, inbox records,
preferences, delivery queue, consumer, SMTP and push. Deduplication includes recipient
and business identity. Private grades, money and application data are not broadcast.
The new learning category offers in-app/email/push preferences on schema137 onward;
older-schema APIs hide/reject unsupported learning preference changes. Students can
open the existing inbox, and allowlisted tenant-bound deep links reach learning,
certificate, account or programme screens. External channels still need their existing
Madar SMTP/VAPID configuration and user subscription/preferences.

## Schema and endpoints

Mirrored immutable additions:

- `137_connect_learning_notifications.sql`: learning preferences and transactional
  notification functions/triggers; schema136 → 137.
- `138_add_academy_programme_workflows.sql`: `academy_applications` (including immutable
  accepted terms snapshot), `academy_withdrawals`, `academy_workflow_history`,
  `elearning_section_certificates`; referral-code clicks; CEFR credential types;
  guarded wallet/review/report/financial/referral functions; schema137 → 138.

New tables enable RLS with no browser write grants. Service-role writes are also
revoked; mutations use explicit security-definer RPCs with membership, role, tenant,
validation, revision and idempotency checks. Workflow history rejects destructive
updates/deletes. Existing referral, commerce and credential entities are reused.

API routes (all use existing authentication/tenant resolution except public click
and provider-authenticated webhook):

- `/elearning/programmes/account`, `/applications`, `/withdrawals`.
- `/elearning/programmes/management/{application|withdrawal}` and
  `/{id}/review`, plus `/management/members/{user_id}`.
- `/elearning/programmes/reports` with optional CSV export.
- `/elearning/programmes/finance/{referrals|rewards|transactions}`.
- `/elearning/programmes/courses/{course_id}/cefr` (GET/PUT).
- `POST /elearning/payments/webhook` and existing checkout endpoint extended with
  the provider boundary.
- `POST /public/academies/{identifier}/referrals/{code}/click`.

The payment boundary accepts only adapter-verified events, then uses existing atomic
fulfillment, duplicate/event ordering and refund logic. Its adapter registry is empty.
Signature verification and provider reconciliation are requirements of a future
concrete adapter, not completed live integrations. The webhook fails closed with 503
without an adapter. CSRF exemption is limited to this machine callback; browser
commands keep existing authentication, origin and CSRF protections.

## Local state and verification

Local Supabase was upgraded from136 to138 after a fresh disposable rehearsal and
rollback checks. Its prior directly applied135–136 baseline was recorded in the
local CLI ledger alongside137–138. Existing local academy learning notifications
are enabled. Course prices, actual curriculum, CEFR mappings and EduHope opt-in
remain unconfigured, following the user's “leave it” answer.

The original validation used frontend5173 and API8000 with the retained138 local contract,
and the existing notification consumer on8090. External SMTP/push are disabled in
that worker process. Production environment and active schema115 release are unchanged.
No PR, merge, production migration or deployment was performed.

Original implementation validation results (before the139 correction):

- Disposable fresh001–138 migrations, rollback137/138, and SQL business regression
  suite: 94 tests (including inherited existing commerce/credential coverage).
- Focused backend/provider/notification/settings/security/local-launcher/release
  contract/export tests: 125 passed.
- Full frontend suite: 1,415 passed, one existing skip; ESLint passed.
- Frontend build and tenant bundle audit passed. Existing chunk-size advisory remains;
  API-origin audit intentionally skips non-production builds.
- Dependency locks, mirrored migration lineage, source-schema transitions, exact
  retained/active release contracts and secret hygiene checks passed. Historical
  identical013/014 migration warnings remain unchanged.
- Authenticated localhost browser: Reports, Students, Theme render without page errors
  or desktop/mobile report overflow; owner report and private CSV export endpoints200. Worker health reports consuming=true;
  it resolved queued local inbox notifications. This is smoke coverage, not a full
  provider/browser end-to-end certification.

Coverage against requested flows: SQL verifies successful/failed/duplicate payment
fulfillment, direct attribution, self-referral rejection, reward creation and refund
reversal; four-sale eligibility/application; affiliate application/review and sale;
exchange; withdrawal reservation/approval/processing/exactly-once paid/rejection;
recipient deduplication; topic/level/course/exam/result/certificate notification
production; owner/learner and cross-tenant permissions; report and finance queries.
Existing notification tests verify consumer/delivery/preferences behavior. Webhook
unit tests verify unavailable provider, signature rejection and trusted event forwarding.
Real provider checkout/signatures/refunds and all25 browser journeys cannot be verified
until provider and course configuration are supplied. CSV formula escaping and multiline serialization are tested; real-provider
acceptance remains pending.

## Remaining configuration and limits

1. Select a payment provider, implement/register its concrete adapter, supply sandbox
   credentials/webhook secret and validate signed webhooks, reconciliation, provider
   session/redirect validation and refunds against that provider. An environment
   variable or mock test provider does not complete this integration.
2. Enable EduHope/programmes for the chosen academy, review terms, referral reward,
   currency, withdrawal methods/minimum and tuition threshold in existing Settings.
   Automated bank/PayPal payout is not connected: owners record actual external
   payouts through the guarded processing/paid lifecycle.
3. Supply/identify the actual course and89-topic syllabus, configure10 sections and
   five CEFR finals/templates, and set its offering price. These were intentionally
   left untouched. No separate speaking/audio auto-grader was added; existing lesson
   media and supported assessment types remain authoritative.
4. Publish actual public website content through Builder, including programme terms.
   Applications currently accept supporting information as text; private document
   upload and a separate exchange-opportunity management module are not implemented.
   Core application fields remain fixed; the support-information requirement is
   configurable. Searches are within the current paginated page. The report student
   selector currently covers learners linked to user accounts; unlinked profiles
   remain visible in totals and rows. Course selection lists the first50 courses.
5. Configure existing email/browser push transports separately if wanted. Historical
   business events are not replayed automatically. Server-specific backup/deploy,
   production runtime and provider acceptance gates have not been exercised locally.

## Changed file inventory

- `docs/automated-database-migration-architecture.md`
- `docs/eduhope-implementation.md`
- `docs/production-release-policy.md`
- `web/README.md`
- `web/backend/app.py`
- `web/backend/routes/academy_programme_routes.py`
- `web/backend/routes/elearning_academy_routes.py`
- `web/backend/routes/elearning_commerce_routes.py`
- `web/backend/routes/notification_routes.py`
- `web/backend/run_local.py`
- `web/backend/run_local_notifications.py`
- `web/backend/services/academy_programme_service.py`
- `web/backend/services/elearning_commerce_service.py`
- `web/backend/services/elearning_settings_service.py`
- `web/backend/services/learning_payment_provider.py`
- `web/backend/services/notification_action_service.py`
- `web/backend/services/notification_delivery_service.py`
- `web/backend/services/notification_preference_service.py`
- `web/backend/services/request_security.py`
- `web/backend/tests/test_academy_programme_service.py`
- `web/backend/tests/test_academy_programmes_database.py`
- `web/backend/tests/test_elearning_cefr_database.py`
- `web/backend/tests/test_learning_payment_provider.py`
- `web/backend/tests/test_local_database_setup.py`
- `web/backend/tests/test_local_supabase_release_contract.py`
- `web/database/migrations/137_connect_learning_notifications.sql`
- `web/database/migrations/138_add_academy_programme_workflows.sql`
- `web/deployment/releases/migrations-115-138.json`
- `web/deployment/releases/schema-114-138-bridge.json`
- `web/frontend/public/madar-push-sw.js`
- `web/frontend/src/components/DashboardBuilder/DashboardSidebar.jsx`
- `web/frontend/src/components/DashboardBuilder/DashboardSidebar.test.jsx`
- `web/frontend/src/components/DashboardBuilder/ELearningSettingsPage.jsx`
- `web/frontend/src/components/DashboardBuilder/NotificationPreferencesPanel.jsx`
- `web/frontend/src/components/DashboardBuilder/NotificationsPage.jsx`
- `web/frontend/src/components/ELearning/AcademyFinancePage.jsx`
- `web/frontend/src/components/ELearning/AcademyProgrammesPage.jsx`
- `web/frontend/src/components/ELearning/AcademyProgrammesPage.test.jsx`
- `web/frontend/src/components/ELearning/AcademyReportsPage.jsx`
- `web/frontend/src/components/ELearning/AcademyStudentsPage.jsx`
- `web/frontend/src/components/ELearning/AcademyThemePage.jsx`
- `web/frontend/src/components/ELearning/AcademyThemePage.test.jsx`
- `web/frontend/src/components/ELearning/CEFRConfiguration.jsx`
- `web/frontend/src/components/ELearning/ELearningAcademy.jsx`
- `web/frontend/src/components/ELearning/ELearningCertificates.jsx`
- `web/frontend/src/components/ELearning/ELearningLearnerShell.jsx`
- `web/frontend/src/components/ELearning/ELearningPlansPage.jsx`
- `web/frontend/src/components/ELearning/ELearningPlayer.jsx`
- `web/frontend/src/components/ELearning/ELearningTerminologyProvider.jsx`
- `web/frontend/src/components/ELearning/ELearningWorkspace.jsx`
- `web/frontend/src/components/ELearning/LearnerAccount.jsx`
- `web/frontend/src/config/routes.js`
- `web/frontend/src/content/dashboard/settingsContent.js`
- `web/frontend/src/i18n/locales/ar/dashboard.json`
- `web/frontend/src/i18n/locales/en/dashboard.json`
- `web/frontend/src/notifications/notificationActions.js`
- `web/frontend/src/services/elearningAcademy.js`
- `web/frontend/src/styles/academy-theme.css`
- `web/scripts/check_forward_release.py`
- `web/scripts/check_migrations.py`
- `web/scripts/eduhope_candidate.py`
- `web/scripts/rehearse_migration_138.py`
- `web/supabase/migrations/137_connect_learning_notifications.sql`
- `web/supabase/migrations/138_add_academy_programme_workflows.sql`

## Architecture correction report (schema139)

This section supersedes the original schema138 defaults and opt-in naming above.
Madar provides reusable tenant capabilities; EduHope is an eventual consumer of
those capabilities. No academy/course configuration was applied by this correction.

1. **Problems found.** New routes enforced membership/ownership but omitted
   subscription checks; navigation exposed programme modules globally. A brand
   settings key controlled generic workflows and CEFR. History parents were
   polymorphic without foreign keys, and application/withdrawal users lacked
   composite tenant membership references. Migration136 granted direct service-role
   writes to canonical referral facts. Existing finance locks/idempotency and
   targeted notification infrastructure were correct and retained.
2. **Hardcoding found.** `eduhope_enabled`, sales threshold4, withdrawal minimum50,
   predefined regional methods and new-plan draft price30 were platform defaults.
   The draft now uses the existing generic offering behavior; no price is changed.
   Reward configuration starts at0. New support thresholds/minima are unset and
   withdrawal methods empty. Occurrences in immutable137/138, historical descriptor
   names, fixtures and139's legacy compatibility translation are intentional.
   Historical enabled tenants retain their prior effective4/50 behavior as stored
   configuration, without applying those values to newly configured academies.
3. **Generalization.** `programmes_enabled` replaces the brand gate. Support has
   a configurable name and two supported eligibility rules: verified referral
   sales with an explicit threshold, or active course access. Exchange keeps its
   existing tenant application workflow with configurable name/information.
   Internal `tuition` identifiers remain stable for stored applications/event types.
   The eligibility notification uses the configured support name.
4. **Existing entitlement authority.** `entitlement_service.py` and the canonical
   dated commercial ledger remain authoritative for module basis, access periods,
   review, expiration, suspension and operator policy. There is no new plan table,
   subscription system, entitlement cache or financial ledger.
5. **Feature mapping.** Existing `ecommerce` capability groups affiliates,
   referrals, rewards, wallet, withdrawals and transactions; `website_publish`
   groups support/exchange; `data_exports` gates advanced reports/CSV. These are
   mappings to existing Madar modules, not independently priced learning products.
   Basic learning, generic certificates and basic in-app notifications retain
   existing access. Existing external notification channel readiness/preferences
   still govern email/push; no additional paid notification service is introduced.
6. **Backend gates.** Account projections, referral attachment/code issuance,
   application submission/list/review, withdrawals, finance, member financial
   profiles, reports/export and protected settings changes check actual tenant
   entitlements. A capability endpoint projects existing access for the UI.
   Omitted application-kind filters require all relevant module grants, preventing
   an aggregate-list bypass. Review resolves the tenant-bound record before
   checking its kind's entitlement. Wallet support fields, member review history
   and report programme/reward aggregates are also filtered by module grants.
   Payment/refund reconciliation retains its
   historical accounting duty and cannot be blocked merely by plan expiration.
7. **Tenant boundaries.** Active server-side membership determines tenant;
   frontend tenant IDs do not authorize these routes. Affiliate approval belongs
   to `(tenant,user)` application status and never grants a global staff role.
   The same user approved in B remains unapproved in A. Wallet liabilities,
   reward/reversal sources, reservations and paid records remain tenant/user
   scoped. Private notifications retain tenant/resource/recipient context and
   allowlisted navigation. Platform accounts use existing administration paths;
   this correction grants no cross-tenant academy-management bypass.
8. **Database security audit.** Migration137 adds no tables: existing events,
   outbox/preferences/delivery are reused. Migration138 tables are summarized
   below.139 adds stronger foreign keys and SELECT-only service-role access to
   canonical referral facts; owner-run functions/triggers perform mutations.
   Trusted backend service-role SELECT is still privileged, so authenticated
   tenant filtering and guarded RPC boundaries remain essential.
9. **Migration.** Mirrored139 requires138, translates legacy settings and adds
   generated immutable-history parent columns plus composite ownership constraints.
   Existing001–138 SQL and pinned metadata are unchanged. New115–139 manifest and
   114–139 bridge are exact, unselected candidates. Active production115 has no
   selected SQL or migration authority. The local rehearsal exercises115 through
   retained migrations, populated138 financial/configuration/history preservation,
   and transaction rollback without resetting application data.
10. **Configuration.** Existing tenant settings store remains authoritative.
    Names, enable flags, terms, supported referral eligibility, reward amount/
    currency, support model/threshold/information requirement and withdrawal
    minimum/methods are tenant data. Save merges explicit fields into stored typed
    configuration and preserves future keys through the existing atomic RPC.
    Responses redact configuration for unentitled modules; forbidden changes are
    rejected server-side. Disabling a plan preserves historical configuration and
    liabilities rather than deleting them. Enabled withdrawals require explicit
    minima/methods; verified-sales support requires an explicit threshold.
11. **Navigation.** Owner features stay under E-Learning; Finance retains nested
    Transactions/Withdrawals. Sidebar management links require both capability
    and owner/admin permission, fail closed while loading, and use configured
    programme names. Learners see their own programme entry only when a relevant
    programme/finance capability is allowed. Direct URL calls remain backend-gated.
12. **New tests.** Canonical module-resolver API tests cover different A/B grants,
    disabled reads/mutations/export, protected settings, suspension overriding
    operator bypass, permissions, record-kind checks and optional CEFR. SQL tests
    cover A/B application review/read boundaries, finance/referral/report isolation,
    direct reward write denial, different amounts/thresholds/minima, notification
    recipients, composite history/member integrity, active-learner support, and
    same-global-user affiliate isolation. Sidebar tests cover disabled navigation
    and student permissions. Existing workflow/finance/notification/CEFR tests are
    retained; historical settings fixtures exercise compatibility translation.
13. **Validation results.** Final SQL rehearsal:157 passed, including inherited
    regressions, schema115 checkpoint, populated138 upgrade preservation and rollback.
    Affected backend/notification/commercial/local-contract suite:319 passed with
    commercial enforcement enabled. Full frontend:1,425 passed, one existing skip
    across192 files. ESLint, build, API/theme/tenant-bundle audits, dependency locks,
    migration mirrors/lineage/transitions, retained/active release contracts,
    secret hygiene and diff whitespace checks passed. Historical identical013/014
    warnings and existing bundle size advisory remain. Production API-origin audit
    intentionally skips this non-production build. Authenticated localhost Reports,
    Students and Theme render without page errors or desktop/mobile report overflow;
    report and private CSV endpoints200. Frontend5173, API8000 live/ready and
    worker8090 health200; worker consuming=true with external transports disabled.
    Local139 committed and CLI ledger updated; course/offering/checkout/reward/
    application/withdrawal snapshot checks confirm existing records unchanged.
    API and worker now use the explicit retained139 local contract. No PR, merge,
    deployment, production migration or production configuration mutation occurred.
14. **Remaining limits.** No live provider, supporting-document uploads, exchange
    opportunity management or academy/course seeding is introduced. Production
    bridge acceptance, backup/upgrade, host-capacity and production environment
    gates cannot be certified against localhost. The existing local operator
    override keeps commercial enforcement disabled for development; enforced
    different-plan behavior is explicitly tested with the canonical resolver.
    Basic in-app events are deliberately retained for historical financial
    transitions after plan expiry. No generic workflow engine or global wallet
    aggregation is introduced.
15. **EduHope configuration only.** Price30, reward10, support threshold4,
    withdrawal minimum50, Tuition Support wording, actual syllabus and A1–C1 course
    mapping are future tenant/course data. None is seeded here. Legacy already
    enabled configuration preserves its prior values via migration compatibility.
    CEFR is optional; its own A1–C1/assessment validation remains scoped to an
    explicitly configured course/section, while other academies can keep generic
    certificates without enabling any programme.

| Table from138 | Ownership/integrity | Index/uniqueness and audit | Deletion/security |
|---|---|---|---|
| `academy_applications` | Tenant+user membership FK added139; tenant/id parent key | Tenant/user/kind/idempotency uniqueness, one open application per kind, tenant/kind/status review index; terms snapshot and revision | Tenant/user/membership restrict; RLS, no browser writes, service SELECT; guarded submission/review |
| `academy_withdrawals` | Tenant+user membership FK added139; currency and configured methods checked by guarded request | Tenant/user/idempotency uniqueness, tenant/status/time index; reservation and exactly-once paid audit | Restrict deletion; RLS, SELECT-only service; same tenant/user serialization lock as refunds |
| `academy_workflow_history` | Generated application/withdrawal parent columns with composite tenant FKs; tenant/actor membership FK added139 | Append-only prior/new status, actor, time and note; immutable update/delete trigger | Restrict parent/member deletion; RLS/SELECT-only service; polymorphic parent ambiguity closed |
| `elearning_section_certificates` | Composite tenant/course/section and tenant/template FKs | Tenant/course/section PK; unique configured CEFR level per course; existing immutable credential snapshots/event evidence | Restrict section/template deletion; RLS/SELECT-only service; optional owner-admin configuration |

Correction files additionally include `academy_capability_service.py`,
`useAcademyCapabilities.js`, `test_academy_capabilities.py`,
`test_academy_multitenant_database.py`, mirrored139 SQL,
`migrations-115-139.json`, `schema-114-139-bridge.json`, `academy_candidate.py`
and `rehearse_migration_139.py`, plus targeted edits to the existing services,
routes, settings, navigation, translations, validators and policy documents.

The requested isolation checks map to these regressions:

| Requested checks | Evidence |
|---|---|
| 1,2,5,6: affiliate/support/exchange read/review isolation | SQL `test_other_academy_application_ids_cannot_be_reviewed`; tenant-bound list queries and API kind/permission gates |
| 3,4,8: referrals/reward writes/report isolation | SQL `test_referrals_rewards_reports_and_affiliation_do_not_leak`; API export authenticated-tenant test |
| 7,12,13,14: withdrawal isolation and distinct monetary/eligibility configuration | SQL `test_distinct_rewards_thresholds_and_withdrawal_minimums`; original reserve/refund/idempotency tests |
| 9: disabled owner navigation | Sidebar `hides modules that the academy plan does not include` |
| 10,11: disabled API and different academy plans | `test_disabled_owner_endpoints_reject_before_queries`, `test_disabled_member_actions_reject_before_mutation`, real resolver A/B module-set test |
| 15: affiliate status belongs to academy | `test_same_global_user_affiliate_status_is_academy_specific` |
| 16: notification recipient belongs to academy | `test_owner_notifications_are_scoped_and_legacy_flag_normalizes`, existing event/delivery/preference regressions |
| 17: platform/owner/learner boundaries | API permission negative cases and retained E-Learning/tenant authorization tests; existing Platform Administration sidebar destinations remain verified |
| 18: existing academies without programmes | Legacy referral SQL regressions, disabled/default settings tests, optional CEFR test and application-data preservation check |

Trusted service-role direct SELECT is not an academy-user access interface; all
academy-facing reads derive tenant context and enforce backend permissions. SQL
integrity constraints additionally prevent ambiguous tenant-parent ownership.

## Academy owner completion and acceptance (schema140)

1. **Projects/Builder architecture discovered.** The pre-implementation A–J audit
   is [academy-owner-builder-audit.md](academy-owner-builder-audit.md). Shared
   `builder_projects`, page schemas, component registry, routing, site chrome,
   preview and atomic publication already provide a multiple-page website.
   General Forms, reservations, connected datasets and auth components are
   intentionally excluded from the Academy profile.

2. **Academy binding.** Existing `website_settings.academy_editor_project_id`
   and `academy_project_id` bind draft and published Academy projects.
   Tenant/profile composite keys, locked initialization/recovery and atomic
   revision publication remain authoritative. Main website bindings are separate.

3. **Features reused.** Arbitrary Home/About/FAQ/Contact/Terms/Privacy/Programme
   pages, custom page slugs, navigation, header/footer, editor settings and
   rendering reuse the shared Builder. Catalog/course/pricing/instructor and
   personalized Continue Learning components reuse existing learning data.
   Course/auth/member routes remain system-owned.

4. **Builder changes.** Three registry/profile components were added:
   `academyContact`, `academyProgrammeInfo`, `academyExchangeOpportunities`.
   Python and SQL validation permit them only on schema140. Contact uses the
   existing platform contact mechanism rather than enabling general Forms.
   No page, project, header/footer or publishing engine was duplicated.

5. **Dashboard.** `AcademyOwnerOverview` extends `AcademyManagementHub`, also
   accessible through `/e-learning/dashboard`. Guarded tenant aggregates cover
   learners, active learners, enrollments, purchases, revenue by currency,
   affiliates, support eligibility, applications, withdrawals, rewards, wallets,
   certificates and recent learning events. Progress/completion/pass rate reuse
   Reports. Commercial projections hide unavailable modules. Purchases/revenue
   represent currently paid verified checkouts, excluding local simulation;
   certificates count issued records including later revocations. Wallet pending
   values are withdrawal reservations. Rewards/sales show existing earned/reversed
   facts; no fictional pending reward balance was added. Aggregates currently scan
   memberships for wallet/eligibility totals; large academies may need later query
   optimization without changing the accounting source of truth.

6. **Settings.** Existing E-Learning Settings gains per-kind application switches,
   opportunity selection policy and institution configuration. Existing branding,
   currency/rewards, minimum withdrawal/methods, support names/rules/terms,
   registration policy and Learning Plans pricing remain in their existing stores.
   Backend commercial checks protect changed settings; inaccessible retained
   historical values do not prevent unrelated saves. No academy was opted in.

7. **Payment architecture.** Existing provider-neutral checkout, signed webhook
   boundary and immutable SQL payment processing are retained. `PaymentProvider`
   now exposes authenticated reconciliation, and the authenticated reconciliation
   endpoint resolves the provider from the stored tenant checkout, restricts
   buyer/owner/admin access and rejects mismatched provider results. It feeds the
   same verified-event processor, preserving stable event identity/order,
   idempotency, paid/access/referral/reward/notification effects and refund
   reversals. Historical reconciliation remains possible after commercial expiry.
   The provider registry remains empty: live payments are disabled.

8. **Supporting documents.** Existing tuition applications accept PDF/PNG/JPEG
   attachments up to5MiB, ten active files per application. Generated filenames,
   actual-content validation, SHA256 integrity, private Supabase storage and
   existing storage quota reservations/accounting are reused. Applicants can
   upload/remove/replace while submitted/under review; tenant owners/admins can
   inspect/download alongside review. Download is authenticated attachment bytes,
   with private/no-store/nosniff headers. No public URL or Builder asset is created.
   Public buckets fail closed. Removal retains audit metadata and denies future
   access even if storage cleanup fails; failed physical cleanup needs operator
   repair through existing storage operations. Upload/download/removal are audited.

9. **Exchange opportunities.** Tenant owners can create/edit draft, publish, close
   and archive opportunities with descriptions, institution/location, dates,
   timezone-aware deadline, requirements and optional capacity. Revisions reject
   stale edits; archive is terminal. Applications optionally link a tenant-owned
   opportunity, or require it through configuration. Student listing requires
   active learner access, published/open/deadline/capacity eligibility. Approval
   serializes capacity checks. Existing unlinked applications and idempotent
   submission replay remain compatible. Owners can filter applications by opportunity.

10. **Institution verification.** Tenant settings supply institution name, normalized
    email domains and institution/regular labels. Student classification derives
    canonical verified linked user identity, active account and tenant membership,
    not editable learner email or frontend labels. The existing Students screen
    displays status and filters before pagination. PAU names/domains are not hardcoded.

11. **Contact administration.** Existing `contacts` gains optional tenant/project
    scope, email, subject and read state; historical platform contacts remain valid.
    Public submission resolves tenant from the existing site/host resolver and
    requires its bound published Academy project to contain the contact component.
    Composite project/tenant/profile ownership rejects cross-tenant associations.
    The owner inbox searches messages, filters unread, opens messages and marks
    read/unread through tenant-scoped queries. Existing public-contact rate limits
    are reused; request-supplied tenant/project fields are rejected.

12. **Public integration.** Shared published Academy runtime supplies entitled
    programme information and open opportunity DTOs. Application CTAs enter the
    existing learner programme workflow; contact calls the platform mechanism.
    The public contact form disappears when Website capability is unavailable;
    authoring preview remains inert. No fixed named public pages were seeded.

13. **Migration.** Mirrored `140_complete_academy_owner_tools.sql` expands139→140:
    private document metadata, opportunities, optional application opportunity FK,
    scoped contacts, guarded aggregates/classification/workflow functions and
    three allowed Builder types. New private tables use RLS and service SELECT
    with guarded mutation functions. Immutable001–139 SQL is unchanged. The
    checksum-pinned140 manifest/bridge is unselected; active production115 still
    selects no migrations. Both validators and policy documents describe140.
    Local139→140 was applied without reset; existing records' counts/content hashes
    were verified within the migration transaction, and the local ledger recorded140.

14. **Endpoints.** All owner paths derive authenticated tenant context:

    | Method | Path | Access/purpose |
    |---|---|---|
    | GET | `/elearning/owner/dashboard` | Tenant owner/admin aggregates |
    | GET | `/elearning/owner/students` | Owner/admin, institution/regular filtering |
    | GET, POST | `/elearning/owner/exchange` | Entitled owner/admin list/create |
    | PUT | `/elearning/owner/exchange/{id}` | Entitled owner/admin revision update |
    | GET | `/elearning/owner/exchange/available/for-me` | Eligible member open opportunities |
    | GET, POST | `/elearning/owner/applications/{id}/documents` | Authorized read/applicant upload |
    | GET, DELETE | `/elearning/owner/applications/{id}/documents/{document}` | Authorized download/applicant removal |
    | GET | `/elearning/owner/contacts` | Entitled owner/admin scoped search |
    | PUT | `/elearning/owner/contacts/{id}/read` | Entitled owner/admin read state |
    | POST | `/elearning/owner/payments/{checkout}/reconcile` | Checkout buyer or tenant owner/admin |
    | POST | `/public/academies/{identifier}/contact` | Rate-limited bound published contact |

    Existing settings endpoints persist new configuration; existing programme
    management accepts an opportunity filter. UUIDs and strict bounded models are
    validated before queries. Owner/admin checks reuse Madar permissions; platform
    accounts receive no new arbitrary tenant-selection or cross-tenant bypass.

15. **UI.** Existing E-Learning navigation gains overview, entitled exchange
    opportunities and contact submissions. Existing settings, students, programme
    review/student applications and Academy hub are extended. New routes use role
    and capability guards; backend gates remain authoritative. English/Arabic
    labels and existing layout/RTL behavior are reused.

16. **Acceptance.** New SQL tests cover opportunity lifecycle/revisions/eligibility,
    capacity/ownership, document metadata/removal/review lock, canonical institution
    verification and tenant-bound dashboard/contact foreign keys. API tests cover
    plan denial before writes, private applicant/admin authorization, unsafe bytes,
    public bucket refusal, failed-metadata cleanup, module redaction, published
    contact binding and provider reconciliation identity. Frontend tests exercise
    metrics, revision updates, private upload/download, inbox marking, public
    contact entitlement and direct-route owner/plan guards. Existing Builder
    reuse/recovery/publication, tenant, verified payment/refund, notification,
    Reports, settings and commerce regressions are preserved. The Builder fixture
    now explicitly includes an active tenant rather than relying on lifecycle
    enforcement being disabled. Final measured results are recorded below.

17. **External configuration remaining.** Choose and implement/register a concrete
    provider adapter, then supply its API credentials/webhook secret and validate
    real checkout/signatures/refunds/reconciliation. `MADAR_PAYMENT_PROVIDER`
    selects a registered adapter; the variable alone cannot enable payments.
    Configure tenant programmes/terms/eligibility, real curriculum/offering prices,
    optional CEFR mappings, institution domains and actual opportunities when ready.
    Storage must have a private existing asset bucket and healthy quota services.
    Email/push transports and production domain/deployment require separate setup.
    No provider credentials, real curriculum or institution domains were supplied.

18. **Remaining owner-side limitations.** The requested reusable owner tools are
    implemented. A live provider and its end-to-end certification remain external
    work; no live payment claim is made. The local browser test account is a platform
    account, so tenant contact/opportunity journeys are covered by SQL/API/UI tests
    rather than a live populated Academy walkthrough. Final production backup,
    accepted bridge, upgrade and deployment gates cannot be certified locally.
    No production mutation, PR, merge or release was performed.

### Final verification record

- Marked disposable PostgreSQL rehearsal:229 tests passed, including immutable
  fresh history, schema115 checkpoint, populated138→139 and139→140 preservation,
  transactional rollback and existing Builder integration. Rehearsal database removed.
- Backend learning/owner/Builder/notification/commercial/local-release regressions:
  570 tests passed with commercial enforcement explicitly enabled in the test runner.
- Authenticated local browser: owner overview, Students, Settings, Reports and Theme
  rendered without page errors; mobile overview passed. Platform account was denied
  tenant contact UI as required by the existing permission model.
- Local frontend5173, backend8000 and notification worker8090 restarted on explicit
  schema140 development configuration. Worker consumes existing internal notifications;
  SMTP/push remain disabled. Existing local operator entitlement override preserved.
- Final frontend suite:193 files passed,1435 tests passed,1 existing skip.
  ESLint passed. Build passed with API-origin/theme/tenant-bundle audits; the
  production-only bundle-origin check intentionally skips this development build.
  Existing large-chunk warnings remain.
- `check_forward_release.py` passed. `check_migrations.py` passed with only the two
  documented historical013/014 duplicate-content warnings. `git diff --check` passed.

### Form methodology versus response ownership

[The E-Learning Forms boundary](elearning-forms-boundary.md) records the user's
clarification: reuse field/schema/validation/conditional logic/rendering/UX
patterns while preserving independent Builder definitions and submissions.
Current programme responses belong to `academy_applications`; fixed contacts
use scoped platform `contacts`. Neither reads/writes Builder form responses.
The subsequent schema141 pass now implements independent general E-Learning
Forms, without linking Builder response tables. See the
[Forms implementation and verification report](elearning-forms-implementation.md).
The schema140 verification above remains the historical owner-tools record.
