# Learner Course Player and explicit completion

My Learning is a separate authenticated workspace at `/my-learning`, available
under the existing E-Learning navigation. It is separate from owner/admin
course management. Course cards show cover/fallback, real progress, eligible
lesson counts, Continue Learning and completed state. The outline shows
published sections and lessons, section progress, completion and locks.
The lesson page has course context, the same `ContentBlockRenderer` used by
admin preview, ordered Text/Audio/Video, Previous/Next and Mark Complete.
Saved tenant labels, global skeletons, responsive layouts and RTL are reused.

## Existing data and authority

No new tables, percentage fields or renderer copies are introduced. Migration
124 adds guarded service-role-only RPCs over existing user-linked learner
profiles, enrollments, content blocks and `elearning_lesson_completions`.
`get_elearning_progress` remains the single eligible-lesson calculator, including
section totals and percentages. Learner responses extract only the current
user's enrollment row and published sections, without other learner details.

Active session tenant membership, active user/profile/enrollment and published
course/section/lesson relationships are checked server-side. Draft/archived
parents and archived blocks are excluded. Owner/admin status alone does not
grant learner course access: an enrollment is required. Cross-course lesson
IDs and cross-tenant requests are rejected. Learner reads are private/no-store.

Stored section/lesson positions define Continue Learning and prerequisites.
The existing `sequential_progression` flag locks later lessons until every
earlier eligible lesson is complete. Reads, completion and learning media
requests enforce this rule. `allow_locked_content` does not bypass prerequisite
sequence requirements; an additional explicit content-lock model is not added.
When sequence is disabled, any eligible published lesson is available.

Completion requires the learner's explicit POST. Opening never completes a
lesson. The existing model has no started-state, so none is invented. Commands
lock the course against enrollment/structure changes and insert idempotently
into the same completion table used by admin reports. Responses include fresh
lesson, section and course progress; returning to My Learning fetches fresh
cards. Completed courses expose their outline for review.

## APIs

- GET `/elearning/my-learning`: current enrolled published courses, tenant
  settings and bounded pagination (`limit` 1..100, `offset`).
- GET `/elearning/my-learning/courses/{course_id}`: private outline/progress.
- GET `/elearning/my-learning/courses/{course_id}/lessons/{lesson_id}`: guarded
  published lesson and active blocks.
- POST `/elearning/my-learning/courses/{course_id}/lessons/{lesson_id}/completion`:
  explicit idempotent completion using session identity, with audit recording.

Clients never supply tenant, user or enrollment IDs for learner authority.
All new runtime APIs fail closed before schema 125. Earlier administration APIs
retain their original schema gates. The release bridge is 114..125 and pins
`migrations-115-125.json`; prior migrations/manifests remain immutable.

## Media

The shared media renderer and managed `/uploads` delivery pipeline remain.
Private learning attachments additionally verify enrollment, publication,
active block references and sequence prerequisites for ordinary members.
Owner/admin preview remains available. Unrelated files retain their existing
rules; an independently authorized public reference remains public. Shared
media may be consumed if any eligible unlocked lesson references it. Archived
references retain files without granting learner access. Commercial-review
restrictions for uploading remain unchanged. No development upload override is
added to production behavior or used in this phase's browser verification.

## Local validation — 2026-10-04

Used the existing local test account and generated loopback Docker PostgreSQL
configuration. Fresh migrations 001..125 succeeded on a marked disposable
database. Migration 125 DDL/schema-state rollback was verified, followed by 75
SQL tests covering learner authority, draft/archive filtering, sequence,
explicit idempotent completion, shared reports, media locks, cross-course
relationships, client RPC denial and earlier learning lifecycle regressions.
The rehearsal database was removed. The rehearsed migration and version 125
ledger entry were then applied only to the local development database.

Actual Chrome clicks: Dashboard → E-Learning → My Learning → Open Course →
Continue Learning. The regular frontend on port 5173 and API on port 8000
were used with existing stored WAV/WebM fixtures and no media-upload override.
Verified lesson route:
`http://127.0.0.1:5173/my-learning/courses/6edefc21-05b7-41fc-b021-efafe909f1fa/lessons/18bcd4b2-ab93-404e-ab51-d83c7531fc0c`.

Text rendered and actual Audio/Video playback advanced playback time. Opening
left progress at 0%; explicit completion changed it to 50%, unlocked Next and
survived refresh. Continue Learning selected the second lesson; its completion
changed progress to 100% and displayed Completed. The existing admin Course
Progress page showed the same 100% completion. Locked reads/completion,
draft lessons, archived blocks, unenrolled courses, cross-course lesson IDs
and anonymous content/media access were denied. Arabic RTL at 390px had no
horizontal overflow. SQL tests also verify member-level media restrictions
and cross-tenant scope independently of the admin test account.

Screenshots are `/tmp/madar-player-outline.png`, `/tmp/madar-player-lesson.png`,
`/tmp/madar-player-admin-progress.png` and `/tmp/madar-player-mobile.png`.
Both temporary browser courses and their enrollments/content/completions were
deleted using the existing confirmed deletion API. Original tenant settings
were restored; existing users, learner profiles and stored media were preserved.
The verified temporary lesson route is therefore no longer accessible.

Full native backend hermetic runner: 1,818 tests, 126 skipped, zero external
network attempts. Full frontend suite: 173 files, 1,217 passed, one skipped.
Frontend lint, production build with `/api` and API/theme/tenant bundle audits,
all five source release validators, backend `pip check`, and shipped dependency
security audit passed. Existing historical duplicate migration warnings remain.

Docker test-image build/run cannot execute: Docker daemon access is denied to
the execution user. This remains a required CI release gate, not a passed local
check. No production deployment, migration, account change or data mutation was
performed. Assessments, certificates, payment engines and visual academy page
building remain outside this change.
