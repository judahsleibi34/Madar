# E-Learning enrollment, groups and instructor assignments

Verified locally on 2026-10-04. Production was not accessed or changed. The
existing local Docker PostgreSQL database on loopback port 54322 is now at
schema 125. Earlier migration files and manifests remain unchanged.

## Available UI

- Course management has Learners, Groups and Instructors tabs alongside the
  existing content and progress tabs.
- Course Learners shows independent source types, originating groups,
  enrollment status, progress percentage and completed/eligible lesson counts.
  The enrollment picker checks the chosen source, so Manual and Free can
  coexist with Group grants. Remove Manual Access and Remove Free Access
  revoke only that source.
  Suspension/reactivation continues to use the existing enrollment model.
- Group names open Overview, Members, Courses and Instructors. Members are
  selected from existing tenant users, with search, bulk selection and paging.
  Course assignments grant access to members and subsequent member additions.
- Instructor names open Overview, Courses and Groups. Profiles may link to an
  existing tenant user; assignments never create learner enrollments.
- Existing My Learning, publication/sequential rules, media authorization,
  shared block renderer and progress reports consume the centralized grants.

## Data and access

Migration 125 backfills existing Manual/Free enrollments and adds the missing
membership, assignment and grant relationships with composite tenant foreign
keys, RLS, uniqueness and guarded transactional commands. Group grants retain
the source group identity. Manual, Free and separate Group grants are additive;
suspension/cancellation overrides them. Source revocation preserves enrollment
and completion history. Purchase is reserved and cannot be issued.

Group summaries call the existing progress engine in a compact mode, skipping
lesson-level JSON. Grants created during temporary course unpublication are
retained, while publication continues to gate learner access.

## Chrome verification

Local origin: `http://127.0.0.1:5173`. Started through the normal E-Learning
sidebar, then Groups, group detail, assignments, My Learning and Course Manage.
Exact routes verified in the final run:

```text
/e-learning/groups/1c1bd3b2-d1b0-4e3f-8a5e-3965ff101ebf/courses
/e-learning/instructors/851f2b03-b129-44dc-9649-f970769329ab/courses
/e-learning/courses/e90989c5-bec1-44fd-9396-16176a83ea19/learners
/e-learning/courses/e90989c5-bec1-44fd-9396-16176a83ea19/progress
/my-learning/courses/e90989c5-bec1-44fd-9396-16176a83ea19/lessons/76879e60-89e8-41ad-9e72-d7c1327aa53d
```

The existing local owner account was learner A. Because it was the only active
user in this tenant, three tagged temporary development users were created
before using the existing-user pickers. All tagged users, courses, groups,
instructors and unused new learner profiles were removed after verification.
These exact fixture routes therefore no longer resolve after cleanup.

Verified:

1. Three members gained course access through a Group assignment.
2. The course appeared in My Learning. Learner A read the existing Text renderer,
   explicitly completed a lesson, and retained 50% progress after refresh.
   Learner B's completion history was prepared through the existing guarded
   completion RPC for the access-removal scenario.
3. Course Learners/Progress reflected the enrolled users and completions.
4. A linked instructor appeared in both course and group assignments without
   receiving learner enrollment.
5. Adding Manual to A, then removing A from the Group, retained Manual access
   and progress.
6. Removing the course from Group A ended B's Group-only access and retained
   the completion history.
7. C had grants from Group A and Group B. Removing Group A retained access via B.
8. Regranting access reused enrollment/completions; refresh retained progress.
9. Removing A's final source returned 404 from the learner course endpoint.
   Rejoining the assigned Group restored access without resetting progress.
10. Invalid target, unconfirmed removal and anonymous requests were rejected.
11. Arabic RTL at 390px rendered member management without page overflow.
12. From Course Learners, Suspend Access retained both Manual and Group grants
    and the existing completion, while course and completion endpoints returned
    404 and My Learning omitted the course. Repeating the Group assignment and
    membership did not override suspension. Suspension persisted after refresh.
13. From the same table, Reactivate restored runtime access and the course in
    My Learning. The same enrollment retained 50% progress and one of two
    eligible lessons completed after another refresh.

Screenshots retained locally:

- `/tmp/madar-grants-group-courses.png`
- `/tmp/madar-grants-instructor.png`
- `/tmp/madar-grants-course-learners.png`
- `/tmp/madar-grants-course-progress.png`
- `/tmp/madar-grants-mobile-rtl.png`
- `/tmp/madar-grants-suspended.png`
- `/tmp/madar-grants-reactivated.png`

## Validation

| Check | Result |
| --- | --- |
| Backend hermetic suite | 1,857 run; 1,697 passed, 160 skipped; no external network attempts |
| Frontend suite | 174 files; 1,223 passed, 1 skipped |
| Disposable database suite | 109 passed; migrations 001–125, transaction rollback and cleanup verified |
| Tenant/security regressions | Real foreign tenant users/courses/groups/instructors rejected; permission, spoofed scope, atomic bulk rollback and direct-write restrictions verified |
| Grant regressions | Manual + Group, Free + Group, two Groups, last-source loss, progress restoration and suspension/cancellation verified |
| Frontend lint and production build | Passed; API-origin and public tenant bundle audits passed |
| Production dependency audit | Zero npm vulnerabilities |
| Backend dependency consistency | `pip check` passed |
| Release validators | Migration parity/transitions, checksums, forward compatibility, dependency locks and secret hygiene passed |
| Working-tree whitespace | `git diff --check` passed |
| Local DB cleanup/ledger | Exact final migration 125 recorded; tagged fixtures absent |

Docker production-image validation is blocked by OS permission to access
`/var/run/docker.sock`. The production configuration validator was invoked but
cannot pass here: the intended `/etc/madar/production.env` is absent and the
isolated-E2E example is not a configured release environment. Those operational
gates must pass in the intended release environment before release readiness
can be claimed. No release gates were bypassed, and nothing was deployed.
