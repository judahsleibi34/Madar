# Local E-Learning demo data

The development seed uses the generated `web/.env.database.local` only. It
refuses production APP_ENV, hosted connections, unexpected ports, remote Docker
and a missing local Supabase container. The configured `MADAR_TEST_EMAIL` must
have an active owner/admin membership; its current tenant is the only target.
No auth users, invitations, messages, payment records or content blocks are
created. Learner profiles are contact records, with reserved `.invalid` emails.
No production migration automatically inserts demo data.

From the repository root, after local migration 121 is applied:

```bash
web/backend/madar_env/bin/python web/scripts/seed_elearning_demo.py
web/backend/madar_env/bin/python web/scripts/seed_elearning_demo.py --verify
web/backend/madar_env/bin/python web/scripts/seed_elearning_demo.py --cleanup
```

If this terminal has not picked up its Docker group membership, wrap the command
with `sg docker -c '…'`. Running the seed again resets only its identified data
and preserves UUIDs and creation dates. Completion timestamps are regenerated.
Cleanup removes completions, enrollments, lessons, sections, courses and profiles
in foreign-key-safe order, all in one transaction. Stable tenant-scoped IDs,
creator IDs, ownership markers and reserved emails identify the seed. Seed/reset
and cleanup refuse collisions or non-seed content/enrollments within demo
courses, rather than overwriting another tenant's or user-created data. Course
locks and a tenant-specific advisory lock serialize resets with live commands.

| Course | Status | Access | Sections | Lessons | Learners |
| --- | --- | --- | ---: | ---: | ---: |
| English Communication | Published | Paid | 5 | 40 | 22 |
| Digital Marketing Basics | Published | Free | 4 | 24 | 18 |
| Workplace Safety Training | Published | Private | 3 | 15 | 12 |
| Leadership Fundamentals | Draft | Paid | 4 | 20 | 0 |

There are 30 learner profiles and 52 enrollments, with overlapping course
memberships. Leadership stays Draft and has no active enrollments: the backend
requires a published course before enrolling learners. Its sections/lessons mix
Draft and Published for status testing. The other courses have published
sections/lessons, retaining the requested lesson totals as progress denominators.
Free enrollments use Free access; Paid/Private courses use explicit manual
assignment. These are access sources, not claims of payment. Paid/Pending billing
states are intentionally absent because no E-Learning payment model exists.

Completions target 0, 10, 25, 40, 50, 65, 75, 90 and 100 percent. Percentages are
never stored: complete lessons are selected in order, producing uneven section
progress, and the backend derives current percentages from completion records.
Courses with 24/15 lessons round to the nearest whole completed lesson. Published
lessons inside published sections/courses form the eligible denominator;
Draft/Archived records are excluded. Archived learners/enrollments are excluded
from active counts. Completion records restrict lesson deletion and survive
lesson moves within the course.

Courses shows real hierarchy/learner counts and average completion. Manage →
Learners and Progress show real backend reports, including expandable section
and lesson completion. Reloading reads the same database records. Learner
profiles do not grant access to learner-facing pages or create authentication
accounts; learner delivery and content editing remain separate future phases.
