# End-user experience and Builder submissions UI audit

## Investigation before implementation

Reviewed the current public Academy, fixed learner shell/dashboard/player/content renderer,
assessment authoring/runtime, credential and CEFR configuration, affiliate/account routes,
independent Forms API/schema and the actual Builder completed/incomplete submissions workspace.
Earlier platform requirements are in attachment29d93669; the current request supplies the
activity/assessment checklist. The original standalone English-course brief and screenshot
are not attached to this turn; the checked-in implementation of the named reference route
is the visual authority. Course-specific counts/scores/CEFR values remain future configuration.

| Journey | Routes/components and authority | Existing coverage / proven gaps |
| --- | --- | --- |
| Visitor | `/academy/:tenant/*` or hosted `/academy/*`; published Builder snapshot, dynamic Form references, tenant login/register, validated return | Arbitrary owner pages including `/exchange` are allowed by Academy schema (reserved prefixes are fixed runtime routes). Published/public/auth returns were repaired in prior pass. Native local public pages/Form are available; external email delivery remains deferred/unverified. |
| Registered, no enrollment | Fixed My Learning dashboard/catalog; canonical tenant membership and enrollment CTA | Empty course state and public course information work; no invented purchase transaction. Programmes/account do not require course enrollment except where actual eligibility requires it. |
| Enrolled student | `/my-learning` → `/courses/:id` → lessons/assessments → certificates; fixed curriculum/locking/progress engine | Next/previous/resume/completion/results/certificates already implemented. Audit native existing enrollment before claiming assessment/certificate E2E. Do not change the player layout. |
| Affiliate-only | `/my-learning/affiliate`, `/affiliate/application`, dedicated referrals/rewards/wallet/withdrawals | Backend membership/affiliate eligibility independent of course enrollment; financial values server-owned. Enabled programme browser journeys locally need clearly labeled fixtures unless existing configuration permits them. |
| Learner + affiliate | Same account identity and separate course/account capabilities | No duplicate engine/store; programme visibility is capability/flag gated. Preserve current dedicated routes. |
| Generic Form visitor | Independent owner Form → any Builder page → published reference → public/access-guarded Form → independent response → owner inbox | Native public Form persistence and retries verified in prior pass; this pass must inspect actual answers in the cloned inbox. Current inbox is a different flat/table workspace than Builder. |

## Activity and assessment investigation

- Authoring supports ordered rich text, audio/video upload, captions, and assessment blocks
  without coding. Audio uses managed media URLs, browser playback/seek/replay controls and
  retry. A text block can present a transcript/vocabulary/communication instructions, but
  there is no transcript toggle/linkage to media or synchronized transcript engine.
- Objective question types are multiple choice, true/false, textual matching and audio-to-text
  matching. Authoring configures question text/options/pairs/audio; server owns answers,
  grading, attempts, passing threshold and required completion. Feedback is attempt result,
  not a per-question immediate-feedback practice engine.
- No picture-target matching schema/renderer, speech recording response, upload/grading
  workflow for speaking, free-text/manual-grade assessment, adaptive bank/randomized subsets,
  or dedicated communication response engine exists. These are missing/partial reusable
  capabilities, not tenant content fixes. Propose scoped future work inside the fixed player;
  do not invent new media/assessment engines in this pass.
- Sections/course/lesson assessment placements and progression rules exist. Attempts snapshot
  published questions; configurable retakes are supported. Retakes do not establish a
  randomized question pool. Templates, course credentials, verification/revocation and
  schema138 section/CEFR milestone credentials exist. Specific CEFR mappings and thresholds
  require future owner/course configuration, not platform defaults.

## Builder UI investigation and proposed faithful reuse

Source route `/builder-responses/projects/:projectId/responses/completed` uses
`PageBuilder/responses/BuilderResponsesPage`, ResponsesHeader/Summary/Sidebar/Toolbar,
ResponsesDataBrowser/Table and Builder data-pages/incomplete-drafts/record-action CSS.
It includes four summary cards, Choose form panel/selector, segmented lifecycle toolbar,
response list/detail, structured answer table, spreadsheet presentation and loading/empty/error
states. The actual latest CSS places the answer list and detail in separate full-width rows.

E-Learning will reuse those presentation components/classes/styles with optional presentation
props that leave Builder defaults intact. Independent Forms APIs supply definitions, immutable
versions, responses, files, read state/notes, filters, pagination and entitled exports. Answers
remain immutable; no Builder edit/delete/status/draft endpoints or project IDs will be used.
Historical field labels must remain version-correct, including changed labels across versions.
Counts must distinguish existing aggregate Forms response counts from bounded page counts.

Builder Incomplete means server-persisted resumable drafts, not unread submitted responses.
Its Filled in statistic measures answered cells, not complete-vs-incomplete draft lifecycle.
Schema141 E-Learning has submitted responses only. Flagged before implementation: display
Completed with an honest no-draft explanation; do not invent Incomplete tabs/counts/lifecycle.
Read/unread remains an independent review filter and state.

## Conflict flagged: prepared Exchange142

142 requires an associated opportunity/form, immutable opportunity context, member eligibility,
separate Exchange decisions/history and capacity accounting. Generic Forms already owns answers,
files, public placement and submissions, but does not provide placement capacity/approval authority.
The specialized `/my-learning/exchange/:id` application entry and opportunity-specific submit API
are not the new default Forms-first page journey. Removing them would affect opportunity discovery,
existing142 context, eligibility/capacity decisions and notification deep links. No142 application,
cleanup, expansion or independent architecture decision is authorized. Preserve the prepared
artifacts and historical review while documenting the conflict. Owner-created `/exchange` pages
continue using generic Form placement and the standard inbox on schema141.

## Validation and implementation results

The audit and scoped UI corrections are complete. No backend API, financial authority,
course-player layout, migration, release metadata, production configuration or tenant/course
configuration was changed. Application schema remains141; all349 migration/release artifacts
match the pre-task checksum baseline. Prepared142 remains unapplied and unchanged.

### Feature coverage matrix

Classification describes the current reusable product. “Verified” includes native HTTP/browser
checks or actual disposable SQL regressions as stated; it does not imply enabled local programme
configuration or live external delivery. The earlier platform-owner brief and this request's
English-course checklist are the available references; the absent original standalone course
brief cannot be represented as a complete independent comparison.

| Reference requirement | Classification | Current implementation and evidence / limitation |
| --- | --- | --- |
| Public Academy and owner-created pages | Fully supported and verified | Published Builder snapshot, tenant resolution and owner-controlled slugs. Native existing published Form page; generic `/exchange` page in browser fixtures. |
| Course information, navigation, English/Arabic/mobile | Fully supported and verified | Native public/learner paths and inbox in en/ar,1440/390; existing catalogue/outline/CTA and fixed learner navigation. |
| Registration/login and destination return | Fully supported and verified | Existing Academy auth, validated tenant-local returns; native test-account login and fixture login return including query/hash. No new accounts created. |
| Email verification and password recovery | Partially supported | Existing global `/verify-email`, `/forgot-password`, `/reset-password`; Academy registration has verification state, but Academy Login offers no direct recovery shortcut. Email delivery and cross-Academy recovery return were not exercised; no mail sent. |
| Students and enrollment management | Fully supported and verified | Owner students/groups/access and canonical membership/enrollment guards; six existing native learner enrollments reused, disposable tenant regressions. |
| Levels/Parts/Topics/materials and generic labels | Fully supported and verified | Owner course structure/content editor and configurable terminology; fixed player remains the runtime. Actual lesson/progress browser reads. |
| Obvious student next action | Supported but UX improvement required | Corrected dashboard's missing-resume-target completion inference. Only server completion facts produce “completed”; unfinished courses link to their course overview. Regression tests verify pending assessment/100%-lesson-progress case. |
| Text, audio playback/replay and video authoring | Fully supported and verified | Existing text/audio/video renderers, tenant-managed media, browser controls and media retry; authoring/runtime tests and SQL contracts. Native selected lesson was read; no claim of native media playback for unconfigured media. |
| Transcript visibility | Partially supported | Caption text and separate text lesson blocks can show transcripts; no transcript toggle, synchronized cues or dedicated transcript authoring field. |
| Vocabulary/expressions/communication instructions | Tenant/course content configuration for later | Rich text and supported objective exercises can express content without coding. No EduHope content inserted. |
| Listening comprehension | Fully supported and verified | Existing `listen_match` audio-to-text matching plus objective questions; managed-media/tenant validation and grading tests. Not a native configured exam in this account. |
| Picture-based listening/matching | Missing platform capability | No image-target matching question schema, authoring control or runtime. Plain textual matching is not picture matching. |
| Immediate per-exercise feedback | Partially supported | Submitted attempt result/score/pass feedback exists. Immediate per-question practice feedback policy/renderer is absent. |
| Practical speaking/recorded responses | Missing platform capability | No student recording/capture, attempt-bound speech upload, manual review or speaking-grade lifecycle. Text instructions alone do not implement this activity. |
| Written/objective exams | Partially supported | Multiple-choice, true/false, matching and listening types supported. Free written answers/manual grading are absent. |
| Section/Part/final assessments and progression | Fully supported and verified | Existing placements, required assessment rules, canonical completion/locking and durable attempt snapshots; disposable SQL regressions. |
| Passing thresholds and retakes | Fully supported and verified | Owner-configured0–100 passing score and up to10,000 attempts or unlimited; server grading/attempt limits. No default course-specific score inserted. |
| Question variation/randomized banks | Missing platform capability | Snapshot-based retakes reuse published questions; no configurable random subset/bank/variation engine. Assessment publication currently supports up to200 questions. |
| Course/milestone/CEFR credentials | Fully supported and verified | Existing templates, canonical issuance, section CEFR milestones, verification/revocation/PDF; schema141 retained SQL suite. Native certificate screen is an empty state, not a completed issuance demonstration. |
| Five CEFR exams, ten levels, exact counts/scores/price | Tenant/course content configuration for later | Configure existing engine where supported; no hardcoded mappings, prices, syllabus or academy opt-in. Speaking/variation requirements remain engine gaps. |
| Affiliate-only and combined learner/affiliate accounts | Fully supported and verified | Dedicated account routes do not require course enrollment; backend/SQL entitlement and membership tests. Enabled application/status/dashboard browser journeys are intercepted fixtures; native programme flags are false. |
| Referral/reward/wallet/withdrawal/transactions | Fully supported and verified | Existing canonical ledger and eligibility/approval authority, owner review, dedicated account views, tenant/financial SQL regressions; synthetic enabled browser lifecycle explicitly labeled. No native payout or live transaction created. |
| Live course payments/provider/payout settlement | External dependency deliberately deferred | Deliberately unconfigured; no provider activation, live commerce simulation or payment changes. |
| Tuition support/institution eligibility | Partially supported | Existing programme eligibility/review and historical workflows are guarded/tested; generic Form intake may be owner-placed. Native flags disabled. Generic intake does not itself replace financial eligibility/review authority. |
| Exchange intake on an owner-created page | Fully supported and verified | Generic schema141 Form/page/inbox needs no142 opportunity link. Fixture `/exchange` exercises ordinary dynamic Builder routing. Existing native `/ui-qa-feedback` exercises the same engine. |
| Specialized Exchange opportunity decisions/capacity | Partially supported | Historical/prepared domain workflow preserved;142/default-entry conflict flagged below. No activation, expansion or independent architecture decision. |
| Notifications/profile | Fully supported and verified | Native dedicated learner screens, existing Madar recipient-bound notification service/preferences/worker and action/deep-link tests. External email/push delivery not proven by these screen checks. |
| Progress/reports/exports | Fully supported and verified | Existing canonical progress and owner reports; entitled Forms CSV keeps immutable snapshots and formula escaping. Native progress read, module/SQL isolation tests; no new reporting engine. |
| Generic Form placement, public/authenticated/enrolled rules | Fully supported and verified | Independent owner definitions, published tenant-owned references, existing server access/entitlement gates. Native guest response plus tenant/access SQL tests; authenticated expiry flow is synthetic. |
| Conditional fields, validation, pages and uploads | Fully supported and verified | Native existing public response/private-file read; generic multi-page conditional/file fixture in four dimensions; actual Forms SQL validation/attachment/idempotency tests. |
| Submission retry and session recovery | Partially supported | Mounted Form retains answers/files/key after401 and retryable failure; verified fixture same-key retry and actual login return. Full-page login navigation requires re-entry of answers/files. No new persisted draft lifecycle. |
| Builder-matched submissions workspace | Fully supported and verified | Shared source components/CSS, native immutable answers, actual reference comparison and keyboard-accessible selection/review buttons. Truthful aggregate/page statistics. |
| Incomplete/resumable E-Learning submissions | Missing platform capability | Schema141 persists submitted responses only. Completed is shown; Incomplete and draft settings are omitted rather than simulated. |

### Requested findings and implementation report

1. **Current end-user architecture.** Public Academy resolves its tenant and published Builder
   snapshot; arbitrary owner-created pages render independent E-Learning Form references.
   Auth returns to validated destinations. Fixed `/my-learning` courses/lessons/assessments/
   certificates and dedicated affiliate/account routes remain separate from public page composition.
   Owner `/e-learning/forms/responses` calls only independent E-Learning Forms APIs for data.
2. **Student E2E findings/fixes.** Native login → dashboard → courses → existing course →
   lesson/progress → certificates/notifications/profile passed in four dimensions. Six existing
   enrollments were reused. Native course inventory shows no assessment placements/results and
   no issued credentials; grading/issuance evidence comes from disposable SQL/tests. The dashboard
   now uses `progress.completion.completed`, not absence of a resume ID, to claim completion.
3. **Learning activities.** Text/audio/video/objective activities and no-code authoring exist.
   Precise missing capabilities are in the matrix; no activity engine or tenant lesson content added.
4. **Assessments/certificates.** Existing placement, grading, retake, completion, credential and
   milestone engines retained. Native unconfigured results/certificates were not fabricated.
   Speaking, manual written grading and question variation require separately scoped work.
5. **Visitor/auth transitions.** Native public Form and owner login verified. Generic synthetic
   login return preserves custom page, query and hash. In-memory retry retains files/answers/key;
   after full navigation users re-enter values. External email/recovery delivery remains untested.
6. **Generic Builder + Forms E2E.** Reused the existing published `/ui-qa-feedback` page and Form
   `1f80bc69-de7f-4e07-8211-944d62fc9bb6`. Read-only SQL verifies its published placement. Browser
   replays existing response `a54f0455-e9fc-491f-9a58-3ddc402286e6` with its original idempotency
   key in four dimensions: HTTP200 and confirmation, still exactly one matching database response.
   The new inbox selects/reads those actual answers. No new Form/page/response/enrollment created;
   creation/placement/republication were not repeated on existing records. A separate synthetic
   owner-created `/exchange` page proves the generic route, conditional fields, file upload,
   multi-page validation,401/retryable error/idempotent retry and login-return UI contracts.
7. **Builder components reused.** `ResponsesHeader`, `ResponsesSummary`, `ResponsesSidebar`,
   `ResponsesToolbar`, `ResponsesDataBrowser`, `ResponsesTable`, spreadsheet presentation and
   data-pages/incomplete-drafts/record/spreadsheet CSS. Optional props preserve Builder defaults;
   source regression tests retain its Completed/Incomplete/settings/edit/delete controls. The
   browser now also preserves zero-valued previews. No Builder data hook or persistence reused.
8. **Visual/behavioral fidelity.** Shared header/four cards/280px form chooser/lifecycle toolbar/
   list/detail/table use source classes. Native computed typography, card backgrounds, padding,
   borders and radii match the actual Builder route in en/ar and1440/390. Styling is identical
   before/after visiting Builder. Default display contains list and table; optional display modes,
   independent filters, pagination, immutable version metadata and notes preserve E-Learning needs.
   Intentional differences: no unsupported draft settings, no answer edit/delete, read/unread
   replaces Builder business statuses, entitled export and version-aware grouped tables. The source
   placeholder response assistant and extra Builder-specific settings are not duplicated.
9. **Completed/Incomplete semantics.** Builder Incomplete is a persisted resumable draft; unread
   is a review state. E-Learning has no such draft authority. Only Completed appears with an
   explicit explanation. Filled in measures answered historical fields on the current page;
   global answer counts use existing server aggregates. Missing definition-list schemas yield
   unknown field counts, not fabricated zero; available matching immutable versions supply counts.
10. **Forms data ownership.** Independent definitions/versions/responses/files/read state/notes
    remain authoritative. Historical renamed fields are separate version-correct columns and
    inline details use each response's immutable schema. Canonical answers are read-only; notes/
    read flags use existing PUT. Private downloads use the scoped response/file endpoint, not
    public URLs. Native existing attachment download passed HTTP200; SQL covers forbidden scopes.
11. **Exchange142 conflict.** The conflict was flagged before UI implementation. Prepared142
    mandates opportunity context, eligibility, decisions/history/capacity beyond generic intake.
    Specialized public application entry/deep links impose that dependency; the default clarified
    journey does not.142 and historical workflows were preserved without application, refactor or
    expansion. Decide separately whether any optional domain review/capacity integration is needed;
    it must not make ordinary Form placement/intake depend on specialized Exchange routes.
12. **Mobile/RTL/accessibility.** Native and fixture journeys passed en/ar at1440 and390; no
    document overflow. Shared CSS plus localized E-Learning copy, logical margins, `dir`, native
    input labels, focus indicators, list buttons and table review buttons are retained. Spreadsheet
    previews now accept locale/direction with unchanged Builder defaults; native popup checks verify
    English/LTR and Arabic/RTL. Formal screen-reader/media-caption compliance was not audited.
13. **Tenant/security.** Existing backend gates, publication separation, version snapshots, owner
    private-file guards and canonical financial authority are unchanged. Inbox request keys/cache
    scope include actor/tenant; stale data is not displayed for a new request. Read/notes metadata
    is fetched for the selected independent response. No client tenant/project/financial authority,
    new application tables or Builder response endpoints introduced.
14. **Tests and evidence.** Focused frontend50 passed; full frontend207 files,1,544 passed/1 skip.
    Focused backend34 and related modules213 passed. Full isolated Docker suite2,951 discovered,
    2,410 passed/541 skipped; no external network attempts. First concurrent full run hit existing
    `test_bounded_query_concurrency...test_catalog_reference_reads_overlap_and_remain_bounded_under_load`
    timing assertion (0.364s vs0.161s bound) while frontend/DB work competed. Its focused3-test group
    passed, then the identical backend image passed the entire suite alone in35.900s; no test or
    backend code was weakened. Disposable schema141 rehearsal299 passed with rollback/preservation
    checks, then removed its database. Lint, backend dependency consistency, production build/API-origin/tenant-bundle audits,
    dependency locks, migration trees/transitions, secret hygiene, forward-release and diff checks
    passed. Two existing013/014 duplicate-content warnings remain. Native SQL confirms141 and
    unchanged349 immutable artifacts. Enabled affiliate application/status/review/dashboard/
    referral/reward/wallet/withdrawal browser lifecycle is intercepted; native disabled flags were
    checked in all four dimensions. Native assessment grading, certificate issuance, live payments,
    mail and push delivery were not demonstrated or configured. No deployment/PR prepared.
15. **Outstanding architecture questions.** Approve scoped fixed-player extensions for picture
    targets, immediate practice feedback, speaking capture/manual review and randomized question
    variation before implementing them. Decide whether media-linked transcript controls are needed.
    Persisted E-Learning drafts require an independent lifecycle/version/file/security design, not
    Builder draft tables. Clarify optional generic submission review versus specialized Exchange
    capacity authority before any142 activation. Tenant-specific programmes, CEFR mappings/course
    content/prices and external providers remain later configuration, as requested.

### Scoped future capability recommendations — no implementation

- **Picture matching:** extend existing validated matching question types with tenant-managed
  target images and alt text inside the fixed assessment renderer. Keep ID-based server grading
  and immutable attempt snapshots; no new course runtime/routes.
- **Immediate practice feedback:** optional practice mode on the existing assessment engine,
  with explicit reveal/retake policy. Do not expose exam answer keys prematurely or infer completion
  from client feedback.
- **Speaking/free-written responses:** attempt-bound private capture/uploads and instructor review,
  quota/MIME/duration guards, immutable submitted evidence and a pending-grade state. Canonical
  completion/credentials must wait for an authorized final grade. This needs approved backend/schema
  scope; generic public Forms are not a substitute for assessment authority.
- **Question variation:** optional published banks/subsets/shuffle policy captured per attempt,
  retaining historical grading snapshots. Course-specific exam configuration remains owner-selected.
- **Drafts/session recovery:** decide whether full-navigation answer preservation is required.
  Persisted drafts need independent tenant/user/session access, expiration, immutable version
  handling and attachment cleanup/quota semantics; do not borrow Builder draft persistence.

### Files changed in this pass

- `web/frontend/src/components/ELearning/LearningFormResponses.jsx`
- `web/frontend/src/components/ELearning/LearningFormSubmissionTables.jsx`
- `web/frontend/src/components/ELearning/learningFormSubmissionData.js`
- `web/frontend/src/components/ELearning/LearningSubmissionReview.jsx` (new)
- `web/frontend/src/components/ELearning/learningFormResponsesContent.js` (new)
- `web/frontend/src/styles/learning-form-responses.css` (new)
- `web/frontend/src/components/ELearning/LearnerDashboard.jsx` and its test
- `web/frontend/src/components/ELearning/LearningFormSubmissions.test.jsx`
- `web/frontend/src/components/PageBuilder/responses/components/ResponsesSidebar.jsx`
- `web/frontend/src/components/PageBuilder/responses/components/ResponsesToolbar.jsx`
- `web/frontend/src/components/PageBuilder/responses/components/ResponsesDataBrowser.jsx`
- `web/frontend/src/components/PageBuilder/responses/components/ResponsesTable.jsx`
- `web/frontend/src/components/PageBuilder/responses/utils/openResponsesSpreadsheetTab.js`
- `web/frontend/src/components/PageBuilder/responses/ResponsesPresentation.test.jsx` (new)
- `web/frontend/src/i18n/locales/en/dashboard.json` and `ar/dashboard.json`
- This report (new).

### Browser artifacts

Transient screenshots/evidence live in `/tmp/end-user-browser/`, with summaries in
`/tmp/end-user-native-result.json`, `/tmp/end-user-journeys-result.json` and
`/tmp/end-user-visual-result.json`. Native and fixture logs are explicitly separate:
`/tmp/end-user-native.log`, `/tmp/end-user-journeys.log`, `/tmp/end-user-native-download.log`,
`/tmp/end-user-form-fixture.log`, `/tmp/end-user-affiliate-browser.log`.
No credentials/environment contents appear in this report or browser evidence.

