# Independent E-Learning Forms implementation

Implemented and verified on 2026-10-11. The investigation before implementation is
in [the Forms audit](elearning-forms-audit.md); the ownership contract is in
[the Forms boundary](elearning-forms-boundary.md). This feature adds configurable
forms to the existing Academy/E-Learning architecture. Programme applications,
contacts, assessments and Builder submissions keep their existing ownership.

## 1. Existing Builder architecture

Builder definitions are embedded in project schemas: ordered sections and fields,
string field IDs, types, options, defaults, help text and equality show/hide rules.
Its runtime validates visible fields, supports page navigation and inert previews,
and omits hidden answers. Responses use `builder_form_submissions` with project
and version context. Builder's file runtime stores file metadata rather than
uploading bytes. Project mutation, collection connections and draft storage are
Builder-specific. The audit identified these boundaries before implementation.

## 2. Reused helpers and rendering patterns

The learning editor calls pure `createField`, taking only its supported field
properties. Rendering reuses `getRuntimeFieldError`, `getModernFieldPlaceholder`
and `getFormPageNavigationItems`. Ordered equality visibility was extracted into
`runtime/formVisibility.js` and is also used by the existing Builder runtime.
Learning visibility resolves only preceding visible fields. Each renderer has
its own DOM ID prefix so multiple forms can coexist on one page. The dedicated
learning renderer follows Builder's field/page/preview patterns without importing
its connected persistence state. Existing API, CSRF, rate limiting, commercial,
audit, notification, private-byte storage and quota infrastructure are reused.

## 3. Persistence kept independent

No learning route reads or writes Builder submissions, collection records,
Builder form IDs or Builder drafts. The new editor has no Builder autosave key.
An Academy Builder page stores only a learning form UUID. Its project/page/chrome
and publication records remain Builder-owned, while submitted data remains
learning-owned. Database tests check independence in both directions.

## 4. Definition schema and lifecycle

`elearning_forms` owns UUID, tenant, name, status, current version, creator and
timestamps. `elearning_form_versions` owns immutable `(tenant, form, version)`
schema snapshots. JSON contains title/description, ordered sections/fields,
logicRules, access, pageMode, submit/success copy and notification switches.
Supported types: short text, paragraph, email, phone, number, dropdown, radio,
checkboxes, date and file. Fields support required, options, default, placeholder,
help text and supported numeric/text limits. File defaults are rejected.

Create, edit, duplicate, active/inactive, archive and restore are supported.
Duplication creates an independent inactive form with a new UUID. Every saved
change increments the version, including lifecycle changes; expected-version
checks reject concurrent/stale edits. There is no permanent deletion endpoint.
The initial definition is inactive until its owner activates it. Response counts
and unread counts accompany the owner list; lists fetch all forms in batches.

## 5. Responses and historical versions

`elearning_form_responses` stores tenant, form UUID, immutable version, answers,
optional signed member identity, submission timestamp, idempotency key/hash,
read timestamp and owner notes. Composite foreign keys enforce ownership.
Only read status and notes can change. Removing fields, renaming, editing,
archiving or duplicating a definition does not rewrite existing answers.
The inbox and CSV export use the response's original schema snapshot.
Identical retries are deduplicated; conflicting keys and stale versions fail.

## 6. Conditional logic and validation

Rules use `sourceFieldId`, `targetFieldId`, `operator: equals`, comparison value
and `show`/`hide`. Rules run in order with trimmed string equality, following
Builder's model. Sources must precede targets; files cannot be sources. This
prevents cycles and hidden values driving later conditions. Hidden required
fields are not required and supplied hidden answers are discarded server-side.
Both renderer and server enforce supported required/type/options/limits rules;
the server additionally rejects unknown fields and forged file descriptors.
Validation is independent of the browser and targets field IDs for UI errors.

## 7. Academy Builder integration

`academyForm` is an Academy component with `academy.formId` only. Its inspector
lists the current tenant's nonarchived definitions; its editor preview is inert.
Published rendering fetches the learning form endpoint and uses the shared
learning renderer. Public requests must resolve an enabled Academy and its
published, tenant-bound Academy Builder project, which must reference that form.
Backend profile validation, the Builder save gate and a database project trigger
reject foreign tenant form references. Empty editor placeholders are supported.
The palette appears only with the existing Forms capability.

## 8. Forms navigation

An entitled academy owner can start from E-Learning Settings. The nested Forms
menu appears when the tenant has an active form, an archived form, or responses.
Only inactive unused forms leave it hidden. All Responses, Manage Forms and
form-specific inbox links are generated dynamically. Archived labels and
historical inactive forms remain navigable while access is entitled. Owner
changes refresh the navigation. Support/exchange/affiliate navigation follows
the existing capability plus relevant tenant programme switches.

## 9. Response management

The owner inbox offers all/form-specific responses, search, date range, unread
and guest/authenticated filters, pagination, submission identity/timestamp,
original labels/answers, private downloads, read/unread and notes. CSV export
uses the same tenant-scoped filters and includes `schema_snapshot`, preserving
historical field interpretation. CSV cells are guarded against spreadsheet
formula injection. Export above 10,000 rows fails explicitly; narrow filters.
No application approvals, generic statuses or workflow side effects are added.

## 10. Private files

`elearning_form_files` owns immutable metadata, tenant/response/field IDs, safe
filename, MIME, size, SHA256 and private key. Actual bytes are uploaded with the
response; JSON cannot claim somebody else's file. PDF, PNG and JPEG content is
checked, with up to 5 MiB per file, lower owner-configured limits, ten files,
one per field, and a 20-million-pixel image ceiling. The existing request-body
middleware also applies its aggregate limit (12 MiB by default).

Keys are `elearning-private/tenant_{tenant}/response_{response}/{file}` in the
existing storage bucket, which must be private. There are no public download
URLs or Builder asset registry entries. Storage uses existing quota reservations
under `elearning_form`; authenticated owner downloads verify tenant, response,
file and content hash. Original filenames are not used as storage paths.
Failures/duplicate retries clean staged bytes and quota entries; cleanup failures
are logged for repair and do not mask the original failure. File metadata
persists with response history; no removal/permanent deletion UI is provided.

## 11. Notifications

The submission transaction reuses `learning_notify_owners` and
`enqueue_learning_notification`, with `learning_form_response` and optional
`learning_form_confirmation` events. Owner actions point to the Forms inbox.
The existing learning notification switch, recipient preferences, internal
consumer, channel readiness and deduplication remain authoritative. Signed
members can receive optional confirmations; guests receive browser confirmation
without an unverified email identity. Local worker delivery is internal only;
SMTP/push are disabled in the local launcher pending external configuration.

## 12. Commercial access

The existing Forms module supplies `forms` for create/edit/use,
`public_form_links` for public rendering/submission, `response_management` for
owner history/inbox and `data_exports` for CSV. Academy capability responses map
Forms to `forms`, and exports to the existing reports/data-exports capability.
Server checks remain authoritative, including direct endpoint calls. Expiration
retains history and attachments but does not introduce a new entitlement bypass.
The explicit preexisting local operator entitlement override is preserved;
commercial regression tests exercise enforcement enabled and disabled cases.

## 13. Tenant and access security

Owner endpoints reuse existing E-Learning management authorization. Queries
scope tenant plus IDs; mutations run owner/admin membership-checked SQL functions.
Composite version/response/member foreign keys and restricted RPC/table grants
provide database enforcement. Browser roles have no direct new table access.
Public identity is resolved from the bound Academy, never a submitted tenant ID.
Authenticated forms require a matching member; enrolled forms require an active
eligible enrollment in that tenant. CSRF/origin/body/rate protections are reused.
Private responses/downloads use no-store caching. Audits cover owner mutations,
review, export and download; submission metadata is durable and immutable.

## 14. Migration and local runtime

Mirrored `141_add_elearning_forms.sql` is the only new Forms migration; 001–140
are unchanged. Its locked guard requires schema140, performs the changes in a
transaction, and advances the core contract to141. Exact checksums are recorded
in `migrations-115-141.json`, `schema-114-141-bridge.json` and the candidate helper.
Source validators accept this exact additional unselected candidate. The active
production `release.json` remains schema115/non-migrating and selects no SQL.

The disposable rehearsal checks fresh001–141 history, retained115 upgrades,
transactional rollback, populated140 application/payment preservation and domain
regressions. The application localhost database was upgraded140→141 only after
these checks. Counts and full-content hashes of existing learning, programme,
financial, contact, website, Builder project/submission/draft records matched.
The local Supabase migration ledger was updated and PostgREST schema reloaded.
No production data, release selection, tenant account kind, course price,
curriculum or programme configuration was changed.

## 15. Endpoints

Paths below are backend paths, reached through `/api` in the frontend:

| Method | Path | Behavior |
| --- | --- | --- |
| GET / POST | `/elearning/forms` | Tenant list / create |
| GET / PUT | `/elearning/forms/{uuid}` | Definition / versioned update |
| POST | `/elearning/forms/{uuid}/duplicate` | Independent inactive copy |
| GET | `/elearning/forms/responses` | Filtered tenant inbox |
| GET | `/elearning/forms/responses/export` | Filtered CSV with snapshots |
| GET / PUT | `/elearning/forms/responses/{uuid}` | Snapshot detail / read and notes |
| GET | `/elearning/forms/responses/{response}/files/{file}` | Authorized private download |
| GET | `/public/academies/{identifier}/forms/{uuid}` | Bound published form |
| POST | `/public/academies/{identifier}/forms/{uuid}/responses` | Validated JSON/multipart submission |

## 16. Verification

- Backend regression suite: **593 passed**, covering learning, academy, Builder,
  notifications, commercial authority and local/release contracts. The 17 focused
  Forms service/API cases cover validation, conditional omission, private upload
  cleanup, endpoint ownership, public binding, CSV snapshots and denial cases.
- Full frontend suite: **194 files passed, 1,447 tests passed, one existing skip**.
  The final renderer ID-prefix/navigation refresh received a further focused run:
  **12 Forms tests passed**. These cover independent submission, inert preview,
  sidebar/history, owner editor and Academy selector/preview/public rendering.
- Disposable SQL rehearsal: **292 passed**. It includes
  Forms lifecycle/history, guest/member/enrolled restrictions, two-way Builder
  independence, foreign project references, response/file ownership, private
  browser-role denial, unread counts and learning notifications.
- ESLint passed; final touched components additionally passed ESLint. Production
  build passed with `MADAR_REQUIRE_PRODUCTION_API_URL=true VITE_API_URL=/api`,
  including API-origin, theme, bundle-origin and public tenant bundle audits.
- `check_migrations.py`, `check_migration_transitions.py`,
  `check_forward_release.py`, dependency locks, secret hygiene and diff checks
  passed. The two known013/014 historical duplicate-content warnings remain.
- Native localhost browser: academy dashboard, Students, Settings, Reports,
  Theme and mobile dashboard rendered without page errors. The original smoke stopped at tenant Forms visibility. The subsequent owner UI
  correction found that the frontend skipped capability lookup for platform labels
  even when backend tenant membership already authorized management. That frontend
  bug is corrected without permission grants. See `elearning-owner-ui-correction.md`
  for the real testing-account create/publish/submit/review flow. Isolated intercepted browser
  fixtures checked Forms editor/save, immutable response detail, nested menu,
  conditional visible-only submission and mobile editor without writing real
  forms or changing that account. Server enforcement was tested separately.
- Backend live/ready, frontend and notification worker health returned **200**.
  Backend and worker run the explicit schema141 local contract.

## 17. Limits and release gates outside localhost

This implementation supports the ten field types and ordered equality logic
above, not Builder's advanced collections, quizzes, arbitrary expressions,
reservations or workflow automation. Definitions allow up to ten pages,
100 fields and 200 rules; schema/payload sizes are bounded. There is no saved
submission draft, anonymous response download, guest email confirmation, antivirus
service or permanent history deletion. Storage and total request limits apply.
Existing Forms commercial policy controls historical access after expiry.

Owner visibility now follows backend capability and tenant membership authority
for every signed-in account. The existing local testing account is authorized by
that backend response; the owner UI correction browser flow created an explicit
QA form/page and responses through normal APIs. No account permissions were changed.
SMTP/push/provider configuration, actual payments and curriculum remain outside
this feature. Docker image/staging deployment, production-config/host-capacity,
backup verification and production release/governed upgrade gates have not been
run against a production host. Local success grants no deployment authority.
