# Generic E-Learning Forms review — isolated144 acceptance

2026-10-12. The user authorized preparation and isolated rehearsal only. The mirrored143→144 candidate is prepared and validated, remains unselected, and has not been applied to the normal application or production. This report covers Forms review; it does not claim completion of the larger EduHope website, course or customer-import task.

## Investigation before adding SQL

Schema141 already provides independent tenant-scoped E-Learning Form definitions, immutable versions, submitted answers, private file metadata, read state and internal notes. Those stores remain authoritative. Builder only places an `academyForm` reference; its submission tables are never queried for E-Learning responses.

The existing138/139 programme authority already validates memberships, programme flags, verified-sale eligibility, referral activation and withdrawal accounting through `academy_review`, `academy_wallet` and related functions. It cannot persist an ordinary Form decision or associate that decision transactionally with an application: the generic decision/history and response association were missing. Schema143 adds assessment capabilities, not general Forms review. The excluded142 Exchange decision system is neither a dependency nor executed.

Accordingly144 adds only review metadata/history and a nullable composite tenant/response reference on existing `academy_applications`. Bound applications contain a reference and terms acceptance, not copied answers or attachments. The retained domain review implementation is called in the same PostgreSQL transaction. No new public Form engine, specialized Exchange intake, hardcoded field definitions, financial benefit grant or payment adapter was added.

A real service-role settings request also exposed139's invoker normalization trigger calling a private helper without permission.144 changes that existing empty-search-path trigger to security-definer execution; the helper remains private. The isolated native settings save and a service-role/helper-denial database test both passed. Migration139 was not edited.

## Actual admin-to-applicant workflow

1. The academy owner creates a Form at E-Learning → Forms → Manage forms, using the shared Builder Forms editor. General review is the default. An optional workflow binding and an owner-chosen required single-option terms checkbox connect an authenticated Form to Affiliate, Tuition Support or generic Exchange intake. Labels, fields, pages, choices and conditional logic stay configurable.
2. Academy Builder places that existing tenant-owned Form on a public page and publishes the reference. It stores no response answers.
3. The authenticated applicant submits. Submission persists immutable answers and initializes `submitted`; it grants no Affiliate privilege or financial benefit. Bound eligibility is enforced by both the backend and SQL.
4. The owner opens Forms → Form submissions, reviews the original response and records a reason with the displayed revision. Decisions persist reviewer, timestamp, status and append-only history. General Forms support `under_review`, `approved` and `not_approved`; Affiliate approvals additionally support suspension/reactivation through the existing authority.
5. A bound Affiliate/Tuition decision invokes the retained domain service atomically. A stale revision, missing eligibility, permission revocation or domain error leaves both decision states unchanged. An exact retry is deduplicated. Existing programme records link back to the original Forms response rather than present a second response editor or attachment flow.
6. Madar's existing event/outbox worker delivers the applicant's in-app notification according to existing preferences. Its secured `/my-learning/form-responses/{id}` link displays only that applicant's status and original answers. Internal notes, reviewer information and private history are omitted. Anonymous ordinary submissions remain reviewable, but have no authenticated recipient for an in-app decision notification.

## Native isolated evidence

The frontend runs at `http://127.0.0.1:5180`, backend8010 and isolated provider55440–55443. The marked database is `madar_eduhope_preview_144`. Fictional local owner/applicant accounts were created through native signup, actual Mailpit verification and native login, without Auth-admin confirmation bypasses or production identities.

Both a general Form and an explicitly bound Affiliate Form were created through the real E-Learning Forms page, placed/published by the native Builder API, and submitted through the public browser renderer. No request interception supplied successful API responses.

- General response `505b2e71-0faa-4281-a142-603189ec409a`: owner recorded Under review → Approved in Forms Responses; applicant saw the decision and immutable answers, without the internal review note. The existing worker delivered the notification and its private link opened the correct response.
- Affiliate response `b49ed74d-3686-4fc6-b2f3-be9dbd571b2e`: before approval, Form/domain states were both submitted and `academy_can_refer` was false. After owner approval through Forms Responses, both states were approved at revision2 and canonical referral authority was true. The membership remained `learner`. Domain details contained only `form_response_id` and `terms_accepted`. One immutable Form decision and one Form event existed. The retained domain event also follows the existing programme notification behavior.
- Native API checks: exact approval retry returned `duplicate`; applicant attempted decision returned403; another user's applicant projection returned404; anonymous applicant projection returned401. The applicant projection omitted internal notes/reviewer data.
- The worker was initially absent in this separate preview, so events were queued but not visible. Bounded batches of the existing worker delivered them with zero failures. External email and browser push were disabled. Delivery and secured deep links were then confirmed in the browser.

Private local evidence and screenshots are in `/tmp/madar-eduhope-preview`: `native-review-evidence.json`, `native-affiliate-before.json`, `forms-editor-native.png`, `forms-owner-decision.png`, `forms-applicant-decision.png`, `forms-applicant-notifications.png`, `forms-affiliate-editor-native.png`, `forms-affiliate-owner-approved.png`, `forms-affiliate-applicant-approved.png`, and `forms-affiliate-applicant-notifications.png`. Credentials/cookies remain private and are not seed data or repository content.

## Exact path, preservation and tests

`web/scripts/rehearse_migration_144.py` creates a separately marked disposable database, applies001–141, verifies populated historical contracts, executes only the pinned141→143 learning transition, rejects142, and then validates the pinned143→144 transition. It verifies real backups, complete transaction rollback and executor re-entry. It removes the disposable database afterward.

The populated143 fixture includes an existing Form, immutable version/answers, read state, internal notes and private file metadata. Their complete rows remain identical through144 rollback, execution and re-entry. Backfill creates only a submitted review at revision1, with no invented historical decision. Existing Forms and Builder independence are covered separately.

Final checks:

| Check | Result |
| --- | --- |
| Full locked backend CI command | 3,339 tests: 2,677 passed, 662 skipped; no failures/errors or external network attempts |
| Marked PostgreSQL rehearsal | 80 test executions passed, including inherited compatibility tests |
| Concurrent reviewers | One commit, one stale-revision rejection; one Form decision/domain transition |
| Tuition four-sale/refund integration | Submission and Under review accepted after four verified fixture sales; refund blocked approval and preserved both states/revisions |
| Exchange | Independent active enrollment required; no specialized application created;142 decision tables absent |
| Full frontend | 1,557 passed, one skipped |
| Frontend lint/build | Passed, including tenant bundle audit |
| Migration mirrors/transitions, forward release, dependency locks, secret-file hygiene, diff whitespace | Passed |
| Historical013/014 duplicate-content warnings | Two retained warnings, no new migration errors |

The full backend suite excludes live-database tests by its normal environment; the separate80-test PostgreSQL rehearsal supplies database evidence. The initial full frontend run caught an unintended palette-order change; the implementation restored existing ordering without weakening the test. An initial backend run exposed a legacy Exchange fixture's missing schema142 mock; the fixture now explicitly models142, preserving its historical assertion.

Candidate SQL SHA256: `ac3f67a144f515e341414732fc23f202f015625b07fb377d9fb416c40cf289f2`.
Manifest SHA256: `11efbeb21be68611d2a06d5e93b6f20f560905e9b64075654889d46581f8eb34`.
Bridge SHA256: `728c766698e0755de90af0b60fee131e69f674c3c7dbb46a153380ea42f56fc7`.
The source validator pins these artifacts; active main115→136 metadata remains unchanged.

Both migration trees'001–143 files were compared byte-for-byte with HEAD, including excluded142. The normal application was read-only verified at141; isolated preview at144. No application or production migration was executed.

## Remaining boundaries

- Application141 activation, release selection, production installation and customer import are not authorized by this rehearsal. Production configuration, governed exact-SHA upgrade, backups, images, traffic and worker acceptance remain untested here and were not bypassed.
- Tuition's atomic decision/eligibility path is proven with real PostgreSQL transactions and synthetic verified-sale fixtures in the disposable rehearsal. A full native browser Tuition approval with genuine payment-provider sales is not claimed; payments remain unconfigured.
- External notification delivery was deliberately not exercised. Production must run its existing worker and configure any desired external channels. The integration respects notification preferences.
- The larger EduHope task remains in progress: portable importer, website/course publishing, original logo binary, final curriculum/media/exam quality, complete customer acceptance and destination verification are outstanding. No source-only seed draft is presented as a finished customer academy.

The authorized isolated144 preparation/rehearsal is complete. No activation approval is requested by this report.
