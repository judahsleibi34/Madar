# Lesson Builder validation — 2026-10-04

Implemented ordered Text, Audio/Voice and Video blocks inside the existing
Structure → Open Lesson route. Settings, navigation, course management and
participation services are reused. Production was not accessed or changed.
The existing local test account was reused; no account was created.

## Completed checks

| Check | Result |
| --- | --- |
| Dependency lock validator | Pass; dependency manifests/lockfiles unchanged |
| Migration tree validator | Pass; 124 mirrored migrations; only existing 013/014 historical warnings |
| Migration transition validator | Pass |
| Forward release validator | Pass; active bridge 114..123 |
| Tracked secret hygiene | Pass |
| Complete native backend hermetic runner | 1,796 tests; pass, 109 skipped; zero external-network attempts |
| Native backend dependency consistency | Pass; `pip check` found no broken requirements |
| Disposable local SQL rehearsal | 58 tests passed, including existing Structure/participation/enrollment/deletion regressions |
| Frontend locked install (`npm ci`) | Pass |
| Frontend lint | Pass |
| Complete frontend tests | 172 files; 1,209 passed, one skipped |
| Production build | Pass with `VITE_API_URL=/api` and `MADAR_REQUIRE_PRODUCTION_API_URL=true`; API-origin, theme and public-tenant bundle audits passed |
| Shipped dependency audit | Pass; `npm audit --omit=dev --audit-level=high` reports zero vulnerabilities |
| Real local Chrome verification | Pass on desktop and 390px Arabic RTL |

The native backend run uses `scripts/run_tests_no_external_network.py`, an empty
isolated environment file, loopback placeholder Supabase credentials and a
`/tmp` repository layout corresponding to CI's read-only mounts. It runs the
entire suite, including release/control-plane tests. SQL suites skipped by that
runner execute separately against a marked disposable loopback database;
other optional database/environment skips remain governed by their test guards.

All migrations 001..124 applied from scratch in a new disposable database on
the local Docker PostgreSQL server. Migration 124's complete DDL/schema-state
transaction was rolled back and its absence verified before forward application.
SQL checks cover media ownership/type/status, tenant/course/lesson/block scope,
concurrent revision conflicts, ordering, duplicate content, archive/restore,
confirmed deletion, protected-reference rollback and tenant purge including
managed media. The marked database was removed afterward. The rehearsed
migration then advanced only the generated loopback development database from
123 to 124 and recorded version 124 in its local Supabase migration ledger.
Production migration history and prior tracked SQL/manifests were not edited.

Chrome created a temporary lesson containing Text → Audio → Text → Video,
uploading an actual PCM WAV and browser-recorded WebM through the real backend.
Refresh persistence, edit persistence, ordering, duplication, cancellation and
confirmation of archive, permanent deletion, media decoding, reusable private
preview, anonymous media denial, saved Learning Labels and RTL/mobile overflow
were verified. Temporary courses/content were removed through the existing
confirmed course-deletion API. Unattached managed files remain under the normal
retention/cleanup policy. Temporary browser-test servers were stopped.

## Limits and remaining release gates

Docker daemon access is denied to the execution user, and noninteractive sudo
requires a password. Consequently the workflow's Docker test-image build/run
and that image's `pip check` were not executed. The complete native hermetic run
is evidence of test behavior, not an assertion that the Docker CI gate passed.
Docker CI remains required before release.

The ordinary local test tenant returned the expected `commercial_review_required`
403 on managed media upload. Browser media verification therefore used a
separate loopback API/frontend with Madar's existing temporary development
commerce override. Authentication, owner/admin permissions, schema gates,
media validation, quota reservations, private storage and asset delivery remained
active. The regular local servers/configuration and the tenant's commercial
records were left unchanged. Regular media uploads continue to require valid
commercial access. No payment engine or commercial assignment was added.

An initial audit attempt inside the restricted sandbox failed with registry DNS
unavailability. Retrying outside that sandbox succeeded; the final shipped
production-dependency audit passed. `npm ci` also reported development-package
advisories; no unrelated dependency update was performed.

The active manifest/compatibility update changes protected release metadata.
An eventual production release requires the existing governed control-plane
upgrade, accepted bridge, verified backup and forward-only migration contract.
No PR, merge, deployment, control-plane upgrade or production migration was
performed by this development task.

## Visible frontend integration follow-up

Verified through actual Chrome clicks from Dashboard → E-Learning → Courses →
Manage → Structure → lesson name, and again through Open / Edit Content. The
Structure row now exposes that action directly as well as in its existing
menu. Lesson Builder shows the saved contextual labels, Course / Structure
breadcrumb, lesson name, Preview, Add Block choices and exact empty state.
Active cards now include confirmed permanent deletion alongside editing,
duplication, ordering and archiving. Obsolete placeholder translations were
removed and the duplicate tooltip describes copied content correctly.

The ordinary local server (without changing its configuration) visibly rendered
Understanding Digital Channels at:
`http://127.0.0.1:5173/e-learning/courses/7309485a-06fe-5aab-9ec7-dc35351297b4/lessons/1544895d-ad0e-53e3-bcaf-070c08eb6575`.
Both lesson-entry paths and Back to Structure worked. Screenshots:
`/tmp/madar-builder-entry.png` and `/tmp/madar-builder-add-block.png`.

Full media verification reused the existing local account and Docker database
through isolated loopback servers with the existing development commerce
override described above. Browser clicks reached:
`http://127.0.0.1:5174/e-learning/courses/8d34d079-cb0c-48d6-8bfa-441a440110e0/lessons/d341a35e-a68c-4b1a-975d-1bb9afe43dfa`.
Created real Text, Audio/WAV, Text and Video/WebM blocks, refreshed and verified
persistence, reordered and refreshed again, edited and refreshed, duplicated,
archived, restored, and confirmed deletion of an active block. Audio/video
metadata decoded, private preview rendered the saved blocks, and anonymous
media requests remained denied. Desktop and 390px Arabic RTL screenshots are
`/tmp/madar-content-desktop.png` and `/tmp/madar-content-mobile.png`; Structure
entry screenshot is `/tmp/madar-builder-structure.png`. The temporary course
and content were deleted through the existing confirmed API after verification.

All 60 focused builder/workspace tests and the full frontend suite passed.
Frontend lint and the production build with API/theme/tenant bundle audits
passed. All five release-policy source validators passed; historical migration
warnings remain unchanged. This follow-up changes only frontend integration,
copy, styling and regression tests, reusing the existing content APIs and tables.
The existing Docker-image release gate limitation still applies. Production
was not accessed or changed.
