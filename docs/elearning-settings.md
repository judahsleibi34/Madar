# E-Learning settings

The tenant workspace sidebar has an expandable E-Learning section with static
Courses, Groups, Instructors and Settings children. `/e-learning` redirects to
`/e-learning/courses`. Sidebar names, page headings and course shell tabs stay
normalized; tenant terminology applies only to content and actions.

Active tenant owners and admins can load and save settings through
`GET /elearning/settings` and `PUT /elearning/settings`. Tenant identity comes
from the session and active membership, never from submitted IDs. Platform
support impersonation is not accepted for these endpoints.

The page reuses dashboard settings classes, theme tokens, the shared API/CSRF
client, lazy workspace routing, and dashboard localization in English and Arabic.
It loads saved values, disables edits while saving, and provides loading, retry,
success, authorization, validation, and save-error feedback.

Configuration covers general identity, tenant-selected terminology, progression
and progress tracking, assessments (integer passing score 0–100), certificates,
and appearance. The platform logo/image can use a validated external HTTPS URL or an uploaded
PNG, JPG, or WebP image up to 5 MB. `POST /elearning/logo/upload` requires a
schema-116 tenant owner/admin and the existing `image_uploads` entitlement. It
shares managed-upload rate limiting, file-signature/content validation, tenant
storage quota reservations, durable storage, registration, audit, and failure
cleanup with the established upload pipeline. Uploading sets the draft logo URL;
Save Changes applies it to tenant settings. Saving verifies the managed image
belongs to the session tenant and has an available registry entry. Saved logos
are retained by asset cleanup without granting anonymous visibility. Replaced,
removed, and abandoned uploads follow the existing retention cleanup rules.

Learning Labels uses native dropdowns in two rows: Learning Content contains
Course, Section, and Lesson labels; Participants contains Learner Group and
Instructor labels. On small screens, fields stack vertically. There are no
hierarchy arrows or example text. The image URL field has no helper text;
file format and size requirements remain beside the upload control. Choices are defined in
`web/frontend/src/config/elearningTerminology.js`:

- Course: Course, Program, Training
- Section: Level, Section, Module, Unit
- Lesson: Lesson, Topic, Chapter, Session
- Group: Group, Class, Cohort, Team, Batch
- Instructor: Instructor, Teacher, Trainer, Tutor, Coach

Selections use the existing tenant-specific `course_label`, `section_label`,
`lesson_label`, `group_label`, and `instructor_label` settings. Option values
are stable English strings; new choices can be added to the registry without a
schema change. Older saved free-text labels remain visible as disabled selected
options until the admin explicitly replaces them. Saving unrelated settings
preserves those labels. There is no custom text entry, drag-and-drop, variable
hierarchy depth, or tenant-specific hardcoded terminology.

Migration 116 creates `elearning_settings`, keyed by tenant, with an extensible
JSON settings document and timestamps. A service-role-only RPC merges validated
settings atomically so future keys survive saves from this page version. RLS and
revoked client grants prevent bypassing the backend authorization layer. Tenant
deletion cascades to its settings. GET supplies neutral defaults for new tenants
without inserting rows; PUT persists configuration. Saving also records an audit
event through the existing audit service.

Before schema 116, GET returns defaults with `available=false`; PUT fails closed
with `elearning_upgrade_required`. The page allows draft editing but disables saving in this interval, and explicitly
notes that those edits have not been saved.
The active release supports schemas 114–120, retains migration 115 unchanged,
and adds 116, 117, 118, 119 and 120 to `migrations-115-120.json`. Release metadata is protected, so
publishing requires the governed control-plane upgrade and backup-first migration
workflow in the release policy. Development does not apply production SQL.

## Course management

`/e-learning/courses` lists tenant courses with covers, names, descriptions,
status, access type, active structure/learner counts and average completion and dates. Create/edit use
the native themed modal. Duplicate creates a Draft copy; Archive preserves the
record and cover. Access defaults to Private; Free/Paid are metadata only.
Managed cover uploads reuse the existing image pipeline, require the image
upload entitlement and enforce PNG/JPG/WebP up to 5 MB. There is no separate
media architecture.

Each card's Manage action opens its course Overview. Overview shows the managed
cover and metadata alongside tenant-labeled structure counts. The normalized
Settings tab opens metadata editing, while Structure manages sections and generic
lessons using the saved labels.
The [content architecture](elearning-content-architecture.md) defines the next
phase's generic lesson with ordered text, audio/voice and video blocks,
extensible types and reuse of the existing managed-media infrastructure.

The shared E-Learning terminology provider reads saved settings once for the
workspace, centralizes singular/plural output and supplies safe defaults. Saved
settings update the provider immediately. Its tenant/user key resets labels and
cached page state when the active tenant changes. The existing settings document
remains the only terminology source. Internal routes, tables and payloads use
normalized course/section/lesson/group/instructor names.

`/e-learning/courses/:courseId` provides normalized Overview, Structure, Learners,
Progress and Settings tabs. Overview shows metadata; Settings edits it. Structure
supports hierarchy management and ordering using tenant labels. Groups
and Instructors have static headings and tenant-labeled management actions.
Lesson content editing, learner-facing delivery, payment processing and
certificates remain future work. Schema 120 adds owner/admin learner profiles,
explicit course assignments and derived progress reports.

`GET/POST /elearning/courses`, `GET/PUT /elearning/courses/{id}`, and
`POST /elearning/courses/{id}/duplicate|archive` enforce active tenant owner/admin
membership through reusable E-Learning permission aliases. Cover upload uses
`POST /elearning/courses/cover/upload`. Session membership supplies tenant IDs;
client tenant overrides are rejected. Updates and actions require the expected
revision and return 409 on stale data. Cross-tenant IDs return 404. Schema 121
adds confirmed `DELETE /elearning/courses/{id}` with an exact course-name check
and expected structure revision. Lists paginate in stable creation/id order.

Migration 117 creates the service-role-only `elearning_courses` table. Before
schema 117, the list returns `available=false` with no rows and course mutations,
details and cover uploads fail closed without querying it. At schema 116,
settings remain usable. Archived covers retain assets; reference checks never
make private assets anonymously visible.

## Local database setup

When the configured hosted database is shared with production, use
`python3 web/scripts/start_local_database.py` with a local Docker Engine, then
start the API with `python run_local.py --local-db` from `web/backend`.
The helper applies pending local migrations, verifies the declared target and
E-Learning tables, and writes a separate ignored `.env.database.local` file.
The launcher requires loopback database/API addresses. Production credentials
and data are not copied; sign up for a separate local account. See the
[local database setup instructions](../web/README.md#isolated-local-database-for-development).

`web/backend/tests/test_elearning_database.py` provides optional real SQL
regressions for schema 117, restricted grants/RLS, settings merge, course defaults,
optimistic revision conflicts, archive, and cross-tenant cover rejection. It runs
only when `ELEARNING_SYNTHETIC_DATABASE_DSN` points to a loopback database marked
`madar-elearning-synthetic-rehearsal`; test fixtures are rolled back. This is
separate from production migration orchestration and does not authorize a
production upgrade.

## Groups and instructors

`/e-learning/groups` and `/e-learning/instructors` provide paginated lists and
create/edit/archive dialogs using the shared theme, global skeletons, English
and Arabic translations, and saved tenant terminology. Groups have a name and
description. Instructor profiles have a name, optional validated email and
biography. Both have Active/Archived status; archived records can be restored
by editing their status. Archive preserves records and requires confirmation.
Email is contact metadata and does not create an account or send an invitation.
Enrollment and assignment to courses are not implemented by this directory.

`GET/POST /elearning/groups|instructors`, `GET/PUT
/elearning/groups|instructors/{id}` and `POST
/elearning/groups|instructors/{id}/archive` require an active tenant owner/admin.
The server supplies tenant and creator IDs; client overrides are rejected.
Updates/archive require expected revisions and reject conflicts with 409;
cross-tenant records return 404. Migration 118 adds both tables with RLS and
service-role-only read/insert/update grants. Before 118, lists return
`available=false` and details/mutations fail closed. Existing settings and
courses continue to work at their original schema gates.

## Course Structure Builder

At schema 119, Structure manages generic sections and lessons with names,
summary descriptions, Draft/Published/Archived status and persisted ordering.
Accessible move-up/down controls reuse the same pattern for both levels.
Lesson moves retain identity within the course. Section duplication includes
its lesson metadata as Draft; lesson duplication creates a Draft copy. Course
duplication continues to copy course metadata only. Actions use themed menus,
modals, confirmation dialogs, responsive cards and global loading skeletons.
Archived sections retain their lessons; active totals exclude archived records
and descendants of archived sections. Section deletion is blocked while any
lesson remains, including archived lessons. Empty section/lesson deletion
requires confirmation checked by the backend.

`GET /elearning/courses/{course_id}/structure` returns a consistent snapshot.
`POST /elearning/courses/{course_id}/structure/commands` accepts an action,
expected structure revision, optional entity ID and validated metadata. The
backend injects tenant/user identity from the active session. A course row lock,
deferred sibling-position constraints and revision checks make edits atomic;
stale edits return 409 and preserve form input for review. Before schema 119,
structure writes are unavailable. `GET /elearning/courses/{course_id}/lessons/{id}`
and `/e-learning/courses/:courseId/lessons/:lessonId` prepare the authorized
Lesson Builder placeholder for ordered mixed content in the next phase.

## Learners and progress

Schema 120 adds contact-only learner profiles (no auth accounts), explicit Free
or Manual assignments and per-lesson completion records. Only published courses
may receive active enrollments. Completion requires an active learner/enrollment
and published course, section and lesson. The same tenant owner/admin boundary
protects `/elearning/learners`, course enrollment commands, completion commands
and course `/progress` reports. Archived profiles/enrollments are excluded from
active counts; completion history protects referenced lessons from deletion.
Progress percentages are calculated from eligible published lessons, never
stored separately. Course cards show batched learner counts and average progress;
Learners and Progress tabs show real reports with section/lesson detail. Operations
fail closed before schema 120. The [development seed](elearning-development-seed.md)
creates only guarded local test data and includes a scoped cleanup command.

## Compact course cards and deletion

Course cards use authenticated theme/typography tokens, small cover thumbnails,
grouped counts, completion bars and accessible icon actions. Delete requires
typing the course name and explicitly warns that structure, enrollments and
completion history are removed permanently. Schema 121 exposes the guarded
owner/admin deletion RPC; earlier schemas disable the action. The RPC checks
course/structure revisions under a course lock and deletes known dependent rows
atomically. Learner profiles remain. Protected future references stop deletion
and roll back all changes. Course deletion does not directly remove cover files.


## Course Progress UI

The static Progress tab uses the existing tenant-scoped
`GET /elearning/courses/{id}/progress` report. Five overview cards show active
enrollment totals, average completion and completed/in-progress/not-started
counts. The searchable table filters name/email and progress status without
changing the course-wide overview. Each row shows backend completion totals,
percentage/status, and the first published section with applicable unfinished
lessons. This section is a suggested continuation, not a tracked visit.
The current report has no last-activity timestamp; the UI shows Unavailable.

View Progress opens the shared dialog for an enrollment already present in the
authorized report, showing course status and eligible lesson completion grouped
by published section. Tenant terminology labels section/lesson content while
Progress stays static. Draft sections and draft lessons are excluded from the
progress view; backend zero-lesson rules are retained (0%, Not started).
There are no progress editing controls or additional schema/API contracts.
The backend verifies course ownership and joins enrollment/learner identities
through tenant/course foreign keys. Existing owner/admin permissions apply.


## Course Learners management (schema 122)

The static Learners tab reads `GET /elearning/courses/{id}/enrollments`, including
suspended and cancelled history. Total Learners counts all retained enrollments;
Active counts active access with active profiles. Completed and Not Started
use the existing lesson-derived progress classification across that history.
Access status (active/suspended/archived) stays separate from completion status;
archived is displayed Cancelled. The table searches name/email and filters both
statuses. Dates and access sources come from enrollment records. Payment and
group cells show Not connected; the group filter is disabled without assigned
records. No purchase or group access source can be granted by this phase.

Enroll Learner searches paginated existing active tenant users through
`GET /elearning/courses/{id}/enrollment-candidates`. It selects up to 100 users
and posts an atomic batch to `/enrollments/users`. No users/auth accounts are
created. The existing learner contact record gains an optional `user_id` link;
legacy seed/contact records remain unchanged. A matching unlinked email profile
may be linked only after validating the selected user's active tenant membership.
Duplicate active enrollment rejects the entire batch. Suspended/cancelled
records reuse their original enrollment IDs and completion history on activation.
Manual is supported for published courses; Free is restricted to Free courses.

`POST /enrollments/{id}/status` handles suspend/reactivate/cancel with expected
status concurrency checks. Suspension/cancellation require confirmation;
reactivation also validates linked-user membership and published course status.
Cancellation archives enrollment, never deletes a Madar user or progress.
The prior enrollment/completion RPC also checks membership of linked users, so
legacy endpoints cannot reactivate or complete for a revoked user.
View Progress and learner-name actions reuse the existing progress dialog and
same backend eligible-lesson calculator. No new enrollment table, account store,
payment processing, group management or lesson content model is added.
Earlier schemas fail closed for management; the existing active-only Progress
tab remains compatible. Production remains untouched; migration 122 is applied
only through the verified local flow during development.


## Structure builder ordering

Structure uses the existing schema-119 hierarchy/RPCs on the verified local
schema 122. No new migration/table is required. Cards show one-based positions
with saved section/lesson labels; forms expose a read-only Position. New records
append to their sibling list. Accessible Move up/down controls persist ordering;
lesson movement selects an unarchived section in the same course. The backend
owns zero-based positions, normalization and optimistic structure revisions;
clients cannot send arbitrary offsets. An Add Section action is also available
below the hierarchy and uses the saved label. Lessons remain generic containers
and open the existing Lesson Builder placeholder; no content editor is added.


## Learner runtime (schema 124)

My Learning now provides published enrolled course consumption, the shared
Text/Audio/Video renderer, sequential prerequisites, explicit lesson completion
and Continue Learning. It uses existing user-linked enrollments and the same
progress calculator as admin reports. See [learner player](elearning-learner-player.md)
for access rules, endpoints, media behavior and local browser verification.
Assessments, certificates, payment engines and visual academy building remain
future work.
