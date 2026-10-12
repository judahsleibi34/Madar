# EduHope local delivery and production boundary

2026-10-12. The actual editable local academy is delivered. This is a local
preview with original provisional teaching content; it is not a production
activation or a claim that the unavailable original89-topic book is complete.

1. **Public URL:** http://127.0.0.1:5180/academy/eduhope-local.
2. **Builder:** http://127.0.0.1:5180/e-learning/landing-page/projects/8947f9ed-d708-48f7-a6cf-1e39c3640484/pages.
3. **Access:** isolated local tenant1. Sign in on port5180 with the native local
   owner access retained in ignored `web/.eduhope-preview.local/owner-credentials.json`.
   Learner fixtures are separate native registrations verified through Mailpit.
   No production account or authentication data was copied. Login sessions and
   passwords are private; neither is Git seed data.
4. **Schema:** retained database `madar_eduhope_preview_144`, marker
   `madar-eduhope-local-preview-v1`. Normal application database remains141.
   Exact141→143 excludes142, then pinned143→144.001–143 SQL and existing active
   release metadata remain unchanged.144 is unselected.
5. **Published Builder routes:** `/`, `/course`, `/how-it-works`,
   `/become-an-affiliate`, `/about`, `/tuition-support`, `/exchange`, `/faq`,
   `/contact`, `/terms`, `/privacy`. Header/footer/CTAs navigate real pages.
6. **Editing:** all11 pages selected in the native Builder. Hero text changed,
   saved and publicly published; original headline restored. Photo changed through
   native managed upload. A palette Text component was added to a controlled new
   page, saved/published, then only that test page removed. Native inline Preview
   site displayed the actual draft. No layout-warning gate was bypassed.
7. **Brand:** exact original owner JPEG, SHA-256
   `1f6147d18f80daa3aefed419dfd260194d1760a1883ec9ed6cf83fc9665f96b5`,
   retained unchanged in `web/seed-data/eduhope/assets/eduhope-original-logo.jpeg`.
   Imported through managed media and set in academy settings/Builder chrome.
   Navy#002A60, academic blue#005088, emerald#088848, white#FFFFFF,
   neutral#F6F7F4. No recreated logo or claimed partnership.
8. **Reusable Builder additions:** image-background educational hero as an existing
   card variant, shared palette/inspector/upload/rendering, responsive geometry,
   theme/RTL support and presentation translation inspector. No EduHope-specific
   React pages. Fixed course detail/login/player remain native. Shared corrections
   preserve overlay geometry on deletion and base-English inspector edits.
9. **Actual E-Learning Form IDs:** Contact
   `ea5d9c87-cdd5-4579-871b-3fdaf089be77`; Affiliate
   `dafab5e0-8297-46e8-beab-b113024efcef`; Tuition
   `219e7bd3-1ca3-4dbe-93c1-d0ccfedb3993`; Exchange
   `569ea7fb-18b6-442f-a466-a5208f1d0070`.
10. **Placements:** respectively Contact, Become an Affiliate, Tuition Support,
    Exchange Builder pages. All four open in the existing Forms editor, with full
    bilingual field definitions/validation and owner workflow binding. Builder
    stores only `academyForm` references. No separate response system.
11. **Actual response flow:** published Contact submitted and rejected through
    Forms Responses (`435f05e8-b298-4004-9546-7a7e26c6182b`). Enrolled learner with
    zero verified sales submitted Exchange and was approved
    (`b3d7fcd9-0e7d-4108-a47e-6d648d578ac3`). New nonbuyer learner submitted actual
    Affiliate Form (`2cc3da2c-d399-4ef0-b8e6-bb91a7fa3daf`); Forms approval and
    existing domain approval persisted atomically. Canonical `academy_can_refer`
    and the native referral-code API confirm authority; learner role retained.
    Zero legacy Exchange application records were created. Tuition remains locked
    with zero verified sales. Four-sale/refund cases are synthetic business fixtures
    in the separate disposable database rehearsal, never fabricated primary-preview
    purchases. General review records do not grant money or a course purchase.
12. **Course:** `535fd927-52a1-441b-be0c-d61751459e38`, one course, ten Levels,
    two Levels per A1/A2/B1/B2/C1 band. The owner lesson editor opens normally.
13. **Topics:**89 clearly provisional/editable records. Exact original owner
    topic titles and book map have not been supplied.
14. **Authored coverage:**10 original demonstration lessons, one per Level,
    published only in this local preview.79 editorial outlines remain Draft.
    Each authored lesson contains original conversation/audio/transcript,
    comprehension, useful expressions, vocabulary with definitions/Arabic/examples,
    picture listening, communication situations/responses and unscored speaking.
15. **Assessments/credentials:**30 published practice activities, one published
    mixed demonstration exam, ten draft Level reviews and five distinct draft
    CEFR65-question banks.62-question shuffled draws guarantee at least57
    objective/written and2–5 speaking questions;70% pass/five retakes. Five
    independent template/configuration pairs exist; official issuance is disabled
    pending educator approval. No official credential was falsely awarded for
    completing one demo lesson. Existing credential hooks/permissions are covered
    by learning/database suites and prior native143 credential acceptance.
16. **Media:**20 intelligible original temporary narrated WAVs, seven original
    code-authored teaching PNG/SVG illustrations, actual logo and licensed
    illustrative adult library hero (Pexels Yan Krukau8199659). Source/license/hash
    recorded in the package. No stock photo is presented as an EduHope student.
    Final human recordings and more realistic advanced teaching photographs need
    owner/educator review. No AI speaking grade.
17. **Business configuration:** academy/course identity; one-time$30USD draft
    offering; direct referral$10; four verified direct-sales Tuition threshold;
    provisional withdrawal minimum$50; EN/AR; enabled Affiliate/Tuition/Exchange;
    verified-purchase or approved-nonbuyer referral authority. Withdrawals/payment
    methods remain disabled/unconfigured. PAU classification is disabled until
    confirmed institutional domains are provided. No multilevel rewards.
18. **Learner navigation:** Home opens the published Builder site; Dashboard
    opens personal overview. Real completion displays10% and1/10 published topics.
    Exchange navigates the actual published generic Form placement, derived from
    current tenant Form bindings. Bound Affiliate/Tuition use the same placements;
    historical applications remain compatible. My submissions is a generic
    recipient-scoped table including Exchange decisions. Capability/settings gates
    hide unavailable features. No tenant-specific sidebar.
19. **Notification proof:** existing Madar event/outbox/preferences/worker only.
    Actual Exchange and Affiliate decisions delivered to their respective learners;
    native links opened their immutable submitted answers/status. Cross-applicant
    response requests returned404; internal notes remained private. The shared
    StrictMode aborted-fetch reuse race was corrected and regression-tested.
    Local continuous in-app worker health8098 is healthy; external email/push off.
20. **Portable seed:** `web/seed-data/eduhope`; canonical importer
    `web/scripts/import_eduhope_seed.py` / `eduhope_learning_import.py`.
    Explicit target tenant, schema/marker/loopback/native-owner guards, logical keys,
    revision checkpoints, managed-media transfer, dry-run and private audit report.
    Git excludes credentials, private responses, learner recordings and finances.
21. **Rerun/recovery:**316 mapped logical resources; full rerun created0 new
    resources. Website owner-edit conflict rejected before mutations. Course
    authoring hash also protects Level/topic/content/question edits. Explicit
    reviewed export adopted native presentation into portable logical references.
    Backup actual restore matched counts/content roots for nine canonical tables.
    A new restore-check database was removed; current preview was not overwritten.
    Provider volumes/database survived actual backend restart. Private filesystem
    artifacts/config/access retained outside `/tmp`, under the ignored local folder.
22. **Screenshots:** public examples in [screenshots](screenshots/).
    Native editor/Forms/decisions/notifications/learning/mobile evidence is private
    in `web/.eduhope-preview.local/evidence/`, with original logs in `/tmp`.
    `public-browser-audit.json` records44 real page/language/viewport combinations.
    Native test scripts used real APIs/database; successful responses were not mocked.
23. **Validation:** full backend3342 executions:2680 passed/662 skipped, no external
    attempts. Frontend1562 passed/one skipped; database144 rehearsal80 passed.
    Full frontend lint/build/public-tenant-bundle audit and dependency audit passed
    (zero vulnerabilities). Release locks/mirrors/transitions/forward/secret checks
    passed; two historical013/014 duplicate-content warnings remain. Final merged
    source validation is recorded below when integration completes.
24. **Exact remaining dependencies:** original89-topic owner map and complete
    official teaching/audio/assessment educator approval; final legal terms/privacy
    approval; institutional domains/PAU verification; real production destination
    ownership/entitlements/schema and governed compatible release/import approval.
    Official79 outlines/finals/CEFR issuance remain unpublished accordingly.
    Live payment/payout provider configuration remains explicitly deferred.
    These limitations do not block the working editable local demonstration.
25. **Production boundary:** owner-provided account mapping retained privately;
    actual tenant/schema are unverified and never guessed. Production was untouched.
    Seed application currently fails closed outside the marked local144 preview.
    Main merge grants no143/144 activation, import or control-plane execution.
    Protected release-artifact changes require the existing governed exact-SHA
    control-plane process; ordinary auto-deploy must not be bypassed.

The individual source/request coverage matrix is
[`requirements.json`](../../web/seed-data/eduhope/requirements.json). It distinguishes
verified local delivery from educator/owner material, real financial/provider
configuration and governed production acceptance. Schema activation is not claimed.
