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
