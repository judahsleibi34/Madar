# Tests and provenance

Implementation source: `1aeed83105723caadc79396c0a29d9d24841d8cc`.
Publication head is later; resolve it from the successor PR. Its own CI/artifact
receipts are required and reported in the PR/final response; earlier source
acceptance is not relabeled as publication-head acceptance.

```bash
PYTHONPATH=web:web/backend/tests python3 -m unittest   test_completed_normal_parent_migration test_completed_normal_runtime   test_completed_normal_execution test_completed_normal_root_credential   test_completed_normal_forward test_migration_executor   test_schema150_provider_adapter test_schema150_actor_inventory   test_schema150_provider_lifecycle test_schema150_admission -q
python3 web/scripts/check_dependency_locks.py
python3 web/scripts/check_migrations.py
python3 web/scripts/check_migration_transitions.py
python3 web/scripts/check_forward_release.py
python3 web/scripts/check_secret_hygiene.py
python3 web/scripts/check_privileged_inventory.py
```

Focused tests:162 passed at implementation source. Six source checks pass;
150 mirrored migrations,0errors,2historical duplicate-content warnings;
78 privileged paths classified. These tests overlap broader suites.

Staging's native host runs `python3 -m unittest discover -s web/backend/tests
-p 'test_completed_normal*.py' -q`. Its receipt is retained privately. The local
managed sandbox could not execute six native socket fixtures and one offline
systemd-parser case; those are environment failures, not hidden passes. The same
suite is executed on staging and fresh CI without weakening checks.

The native150 script's working-source run passed205 executions, including12
schema150 cases. Four earlier parent cases and one late-session completion case
are new; other suites are retained/overlapping. Actual marked database/SQL,
process locks, journal and selected-row preservation are distinct from MODEL
outer authority/backup/runtime boundaries. Final-head CI repeats the native path.

Preserved failures: baseline missing parent method; omitted forward lock;
private recovery omitted candidate; premature ingress attempted a Docker start;
initial staging source-read and helper-import fixture setup failures. Corrected
fixtures/assertions are retained. Raw logs and source overlays are private.

Exact implementation archive SHA256:
`3600fedda664525edbbfc786bacb2dc8cc449405f67adfd2f7ffc836da138c62`.
This is a verified committed source archive, not an authenticated release image.
The earlier working snapshot/overlay are separately identified and never labeled
as a clean Git release. Final CI must build fresh images for its own source SHA.

Always-running jobs: `test-backend`, `build-frontend`, `migration-safety`,
`build-candidate`, `full-provider-staging`. Workflow tokens remain read-only,
Actions pinned, checkout exact-head with no persisted credential. No production
workflow, root automation policy or protected dispatcher was enabled.

## Accepted source6e58dcbe

All five workflows passed for `6e58dcbe03b806f1868e02b166397e581da481a4`:

- [Backend](https://github.com/judahsleibi34/Madar/actions/runs/39485964196).
- [Frontend](https://github.com/judahsleibi34/Madar/actions/runs/39485964202).
- [Migration safety](https://github.com/judahsleibi34/Madar/actions/runs/39485964203).
- [Candidate artifacts](https://github.com/judahsleibi34/Madar/actions/runs/39485964299).
- [Full provider](https://github.com/judahsleibi34/Madar/actions/runs/39485964286).

Backend:4,375collected,3,486passed,889conditional skips,0failures. Separately,
257native PostgreSQL executions passed; these overlap specialized suites and are
not added as unique unit coverage. Frontend:1,713passed,1skipped,233files;
lint/build/dependency checks and audit passed. Migration safety68passed;
root-policy filesystem10passed; native runtime lock ownership4passed. Native
maintenance component restore passed9.328s,including original roles/owner/ACL/
data/sequences and object bytes; metadata activation and replica remainedfalse.

The committed implementation archive's staging controller suite collected345,
335passed/10skipped. Its native150 script passed205executions,including12cutover
cases. A small isolated Docker observation also confirmed declared aliases remain
stable and live endpoints disappear after stop. This is not full candidate or
privileged-controller acceptance. Owned dummy containers/networks were removed
only after exact ID/label checks; retained stacks and guest were unchanged.

Authenticated provider report:artifact12294645733,run39485964286attempt1,
SHA256 `a19e3be8db0c01eb47d9a0879424bc1b978c1797822ecaeea30801a967e24523`.
Its actual downloaded ZIP was hashed before the single bounded JSON was read.
Candidate artifact12293308601,run39485964299attempt1,archive SHA256
`ba1438dc4463f18ee6df69c4a62eb00d8597212e894e2317b1129f005f5d30f3`.
The report binds that authenticated candidate and these actual runtime images:

- Backend:`sha256:a142a5e47cd2650df9a6adf46fc0f5acf5125ce2bc8f7752b816fd718832fa8c`.
- Frontend:`sha256:4a4154c64567af8231fdd28a4f3afbd03cf2475559e4cb4e771ca4c0e18dc7fa`.

All11components accepted; schema150/protocols2/2/2; Auth/MFA/refresh/CSRF/private
Storage/notifications/tenant isolation, both10step real user/tenant deletion
workflows and consuming-worker restart passed. Browser9groups passed,0pageerrors.
Elapsed255.861s,source_overlay_used=false,stopped_after_acceptance=true.
Origin is150, migration_boundaries=[], protected_controller_execution=false,
production_authorized=false. This is fresh genesis, not a protected146upgrade.

This evidence belongs to6e58. The documentation publication is a different SHA
and requires its own fresh CI/images/receipt. The PR/session reports those final
head results separately; no6e58receipt is reused to certify a changed source.
