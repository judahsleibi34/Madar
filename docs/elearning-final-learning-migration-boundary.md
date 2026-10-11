# Final learning capabilities: historical migration preparation

This document records the approved preparation phase. The actual143 implementation, final source pins and native validation now supersede its execution-disabled status; see [the final implementation report](elearning-final-learning-implementation.md).

Date: 2026-10-11. Status: **learning-only route approved; guarded preparation implemented; execution disabled**.

This is a concrete investigation and proposed release path, not a completed
implementation or a seed-readiness claim. No learning capability, application API, SQL migration, payment configuration or
tenant content was changed. The follow-up adds a reserved path descriptor and
fail-closed migration-loader/source-gate preparation; existing release descriptors
remain unchanged. Existing uncommitted work is preserved.

## Why implementation stopped

Section 17 of the implementation request says:

> If migration142 conflicts with the next required learning schema migration, stop and document the minimal safe migration/release path before changing versioned artifacts.

The conflict is real. A read-only connection to the loopback application database
confirmed `application_schema_state`, core contract, at **141**. All 349 migration
and release artifacts still match the checksum baseline from the previous pass.
The prepared Exchange142 migration remains unchanged and unapplied in this local
database. This verification does not assert the state of other installations.

Evidence:

- `web/database/migrations/127_create_elearning_assessments.sql`: question validation
  permits only `multiple_choice`, `true_false`, `matching`, `listen_match`. Config
  objects reject unknown keys. Matching targets permit IDs and text labels only.
- That migration's attempt constraint permits only `in_progress` and `submitted`.
  Submitted attempts must already have numeric results and a non-null pass/fail
  fact. Answers require non-null earned points. Submission immediately calculates
  the official result, so an honest pending-human-review state cannot fit this
  contract.
- Existing submission validation has no written response or owned recording
  response. Its fallback treats other types as matching; adding frontend controls
  or widening Python types alone would not implement these capabilities.
- `web/scripts/exchange_forms_candidate.py` pins the exact mirrored Exchange142
  SQL, manifest and bridge. Replacing142 would invalidate retained history.
- `web/scripts/check_forward_release.py` requires the exact001–142 namespace.
- `web/scripts/check_migration_transitions.py` requires each migration's predecessor
  to be its number minus one.
- `web/deployment/lib/migration_executor.py`, `MigrationManifest.load`, rejects
  transitions unless `from_schema + 1 == to_schema`, and rejects non-contiguous
  manifests. A143 SQL file guarded at141 is therefore **not supported** by current
  execution machinery, even if source validators alone were adjusted.

Adding ordinary143 would require142, which the request expressly prohibits.
Skipping142, rewriting its SQL, manually setting the schema marker, or relaxing
validators globally would violate the existing release contract. No such action
was taken. There is no currently accepted migration path satisfying every constraint.

## Proposed minimal explicit release decision

Preserve001–142 SQL and every existing descriptor byte-for-byte. The owner approved preparing a separate **learning-only141→143 bridge**, selecting only the new learning
transition after the retained prefix through141. Exchange142 must remain an
unselected candidate, never a dependency of this learning bridge.

This is a proposed narrowly governed contract extension, not an already valid
migration or permission to apply one. The preparation is now authorized. Final execution still requires complete
versioned artifacts and passing release gates:

1. Read the automatic migration architecture and merge/deployment contract in
   addition to the production release policy before implementing release changes.
2. Inventory consumers of consecutive versions: manifest validation, source gates,
   executor, schema selection/compatibility, rehearsal, rollback and forward repair.
   Extend only the exact checksum-pinned141→143 candidate path; retain rejection
   of arbitrary gaps, duplicate numbers, mismatched guards and unknown manifests.
3. Pin mirrored143 SQL and a new manifest/bridge. Keep active production115's
   non-migrating contract unchanged. Preserve the existing141 and142 candidates.
   Do not advertise compatibility for schema142 unless a separate bridge and
   preservation rehearsal demonstrate it. Numeric version comparison alone
   cannot prove compatibility between branches.
4. Rehearse141→143 on disposable data, including old attempts, answers, Forms,
   Builder, credentials, financial history and rollback/forward-repair behavior.
   Prove the executed SQL list excludes142; prove unknown paths still reject.
5. Update production policy and automatic migration architecture together with
   accepted contract changes. Run all applicable release checks and their tests.
6. Complete the learning vertical slice in an isolated143 instance before selecting
   a local application contract. No production migration or deployment is granted.

An alternative is formal retirement/archival of the never-applied Exchange142
candidate and a newly allocated linear learning142. That would require evidence
about every affected installation and an explicit decision about preservation of
the immutable candidate namespace. It is **not authorized by this request** and
was not done. Applying the existing142 first is expressly excluded.

The owner approved preparation of the explicit141→143 route. The decision is
resolved; activation remains disabled until the complete learning SQL and its
release contract are finalized. Do not treat this document as a gate bypass.

## Reuse and schema extension design

The following is the concrete implementation scope after that decision. Names
and payloads are proposals, not existing endpoints or production guarantees.

| Area | Existing authority / extension point | Required extension |
| --- | --- | --- |
| Course hierarchy and fixed player | Structure/content services; `ELearningPlayer`; `ContentBlockRenderer` | Add activity renderers inside the existing lesson dispatch, preserving curriculum and player layout. |
| Assessment authoring/runtime | Assessments service/routes, `AssessmentBuilder`, `AssessmentQuestions`, `AssessmentBlockRenderer`; SQL127/128 | Extend existing question model and canonical attempts; no second assessment engine. |
| Picture listening | Existing audio matching and tenant-managed media references | Image targets with media IDs and alternative text; server validation, retained snapshot references and ID-based grading. |
| Practice | Canonical assessment attempts and lesson completion calculator | Explicit practice mode, feedback/retry settings and optional lesson requirements; exclude practice from official exam pass and credential eligibility. |
| Speaking practice | Fixed lesson renderer | Local record/stop/playback/re-record; finish requirement only when configured. No review item or pronunciation score. |
| Graded speaking | Canonical question/answer/attempt snapshot | Private assessment-owned recording metadata and authenticated streaming; never Builder assets or Forms response tables. |
| Written answers | Canonical answer ledger | Immutable bounded text plus manual-review state; no keyword grading. |
| Manual review | Existing active tenant membership and course/group instructor assignments | Bounded pending queue and scoped review actions; immutable decision history, revision checks and transactional finalization. |
| Mixed exams | Existing server submission/grading transaction | Auto-grade objective items; hold official totals/pass until required manual decisions are complete. |
| Pools/retakes | Existing private attempt snapshot and max-attempt limits | Server-selected subsets and order frozen per attempt; retained content, rubric, answer keys and media survive author edits/deletion. |
| Transcripts | Existing media caption plus content authoring | Explicit optional transcript and accessible visibility control, not synchronized captions. Resolve storage validation in the same learning schema. |
| Progress/credentials | Existing placement, completion and credential functions; SQL128/130/138/139 | Consume finalized graded results only, preserving independent section/CEFR issuance. |
| Notifications | SQL137 business events, Madar outbox/delivery/preferences | Submission, review-required, final result and credential events with recipient-scoped links; no new delivery engine. |

### Canonical lifecycle and compatibility

Preserve historical submitted objective attempts and their scores. Keep the existing
finalized status compatible where possible; introduce pending review without
changing old records into new unfinished states. Snapshot activity mode, question
selection/order, answer keys, maximum points, rubric and recording limits when
the server starts the attempt. A client must never supply its own score, pass,
review decision or completion fact.

Submission stores immutable written/recording responses, computes objective
credits and moves mixed attempts to pending review. Manual credits remain unknown
until accepted review decisions exist. Required reviews finalize once under the
attempt lock; concurrency/repeated requests return the accepted result or an
explicit revision conflict. Only the finalization transaction supplies official
totals and invokes existing progression/credential evaluation. Pending items
must not unlock subsequent work or issue certificates. Attempt limits must include
pending submissions, rather than allowing unlimited attempts while review waits.

Practice results may satisfy an explicitly configured lesson condition but must
never masquerade as an official milestone assessment pass. Practice recordings
remain local unless a genuine durable requirement is designed and authorized;
graded recordings are server-owned. Optional/manual question behavior must be
explicitly configured and snapshotted rather than inferred from missing answers.

### Recording and review security

Reuse storage quota reservation/accounting and durable object storage plumbing,
with an assessment-specific category, private key namespace and ownership table.
Existing Forms uses shared storage helper functions, but its response/file tables
must not become assessment storage. Recordings need composite tenant/attempt/
question ownership, byte signatures, verified duration, size/MIME limits, hash,
reservation identity and durable cleanup/reconciliation for partial failures.
No public Builder upload URL is acceptable for learner recordings.

Authorize every upload/download/review against active account, tenant, course and
current access. Reviewers must be tenant owners/admins or instructors assigned to
the relevant course/group; assignment tables already exist in126, but assessment
author routes currently require owner/admin. Therefore an assigned-instructor
review gate must be implemented, not presumed to exist. A learner cannot grade
their own work; instructor removal, suspension and access revocation must be
checked again at playback and decision time. Preserve historical recordings and
review decisions according to explicit retention policy, without deleting them
when authors change question banks.

The browser recorder must stop microphone tracks and revoke preview object URLs
on cancellation/unmount. Handle permission denial, unsupported MIME/device,
interruption, max duration/size and failed upload/retry with accessible en/ar
messages. Server media inspection, not browser-reported duration, is authoritative.

### Owner and learner acceptance slice

Owner: existing course authoring → audio/transcript → picture listening practice →
speaking practice → mixed milestone assessment → bank selection and retake policy →
publish → assigned reviewer queue and immutable review detail.

Learner: enroll using safe existing test access → listen/replay/toggle transcript →
match pictures and receive configured practice feedback → record/playback/re-record
practice → complete lesson → submit objective, written and private speaking answers →
see pending review → receive finalized result → continue/receive eligible credential.

Prove failing then permitted retake with changed frozen question selection. Include
English/Arabic desktop/mobile and keyboard interaction. Reuse existing notification
preferences and verify reviewer/learner deep links cannot cross tenants.

## Seed-readiness and verification status

Existing reusable hierarchy, placement, configurable pass threshold/attempt limits
and section/CEFR credential engines are extension points. This pass has **not**
demonstrated a configured ten-Part/89-topic course, five milestone exams/certificates,
or a50-question mixed exam with2–5 speaking questions. No original course was seeded.

New picture practice, recorder, private graded recording, written/manual review,
mixed pending lifecycle, varied pools, transcript controls and owner review UI are
**not implemented**. The requested real author→learner→review→progress→certificate
journey cannot run on the current schema. No fixture screenshot or existing objective
test result is evidence that this new journey works.

Verification in this investigation:

- Read-only native local database: schema141; existing generic published Form and
  its idempotent response remain intact.
- All349 migration/release artifact checksums unchanged.
- Migration-tree check:142 mirrored migrations, zero errors; two retained historical
  duplicate-content warnings for013/014.
- Forward-release source and migration-transition checks: PASS.
- Existing focused learning regressions: **24 passed**, zero failures/errors,
  zero external network attempts. Used the intended Docker CI command/environment
  with assessments, content, placements, credential service/routes and player
  modules selected through the repository's network guard.
- Dependency locks, tracked secret hygiene and `git diff --check`: PASS.

No application code changed, so the previous full-suite results are historical
baseline evidence, not new-capability validation. A fresh full backend/frontend
run, new schema rehearsal and real mixed-assessment browser acceptance are deferred
until implementation is permitted and exists. Seed readiness remains **NO**.

After the release decision, tests must cover foreign-tenant IDs/media/review,
forged grading/completion, reviewer self-grading, assignment revocation,
idempotent uploads/submissions/finalization, conflicting review revisions,
question-bank edits/deletion after start, missing media, auth expiry, denied
microphone, quota failure, cleanup recovery, entitlements and pending-review
progress/credential exclusion. Use the repository's network-isolated Docker CI
runner, focused/module/full backend layers, disposable database rehearsal,
frontend suite/lint/build, release/source gates and actual isolated browser/API/DB
journeys. Keep native and fixture evidence separately labeled.

## Approved follow-up: preparation delivered

The new source-pinned `learning-141-143-path.json` records the approved route,
excludes142 and reserves canonical SQL/manifest names. It contains no executable
SQL or migration manifest, has null digests and `execution_authority: false`.
There is no empty migration that merely advances the schema marker.

The manifest loader now routes only a141→143 gap through a dedicated authorization
helper. The shipped reserved descriptor rejects it. Future finalization requires
reviewed source pins, exact manifest identity/digest, a single143 entry, exact SQL
digest and byte-identical mirrors. Unknown gaps, added Exchange entries and
arbitrary manifest paths reject. The executor explicitly excludes142, and the
automatic coordinator checks the same manifest schema path before backup/SQL
work. Ordinary consecutive manifests retain their existing behavior.

New source checks reject descriptor tampering and premature143 SQL/manifest
creation. Existing namespace and transition gates still reject unreviewed143
artifacts. Production policy, automatic migration architecture and merge contract
are updated with the same preparation boundary.

The tests distinguish the shipped non-executable reservation from a simulated
future finalized descriptor. The latter proves only loader/executor path behavior
with fake SQL/database:141 applies143 only,142 rejects without SQL,143 resumes
without replay, and verified backup remains mandatory. It is not a native schema
rehearsal or evidence that learning features exist.

Before finalization: implement complete learning SQL; update the exact143 source
gates/transition contract; implement branch-aware application feature and release
compatibility fences (143 does not imply142); adapt governed CLI-ledger
reconciliation without inventing an applied142 row; prove backup/recovery,
control-plane provenance and preservation in the intended disposable rehearsal.
No143 application contract or automatic-production bridge is selected here.

### Follow-up checks and actual changes

Changed: migration executor and its new dedicated path helper; automatic
coordinator schema rejection; control-plane installer dependency list; reserved
route JSON; reservation source checker and integration into migration/forward
source checks; new branch/import regression tests; release, migration,
control-plane and merge policy documentation. No application API or frontend
behavior changed.

Focused preparation/controller checks:45 passed. Related recovery/control-plane
modules:187 passed. The first full run exposed a standalone privileged-import
regression introduced by this change; the helper import now supports both trusted
standalone and package loading, covered by an isolated-interpreter test.
Final full backend suite: **2,418 passed,541 skipped,zero failures/errors**
(2,959 discovered), with zero external network attempts. The skips retain the
repository's existing disposable-database/environment requirements.

Native database read confirms141. All349 pre-existing migration/release checksums
remain unchanged; the only added descriptor is the non-executable reservation.
Migration/forward/transition/reservation checks, dependency locks, secret hygiene,
shell syntax and diff whitespace checks pass. No SQL changed or ran, so there is
no143 database rehearsal. No frontend changed, so frontend tests/lint/build and
browser checks were not repeated for this preparation. Governed production
installation and native143/mixed-assessment acceptance remain unperformed.
