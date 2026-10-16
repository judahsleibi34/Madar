# Validation log

Baseline commands/results are appended as executed. No unexecuted check is a PASS.

- Host identity and staging SSH/sudo: PASS.
- Source fetch: PASS; baseline876b65e7, dedicated worktree created.
- Fresh staging Docker test build: BLOCKED at public registry DNS; VM lacks default route/resolver. Existing immutable image import initiated; source mounts will be identified explicitly.
- Baseline backend/frontend suite: pending execution.

## Baseline and first hardening validation

- Baseline staging backend: CI workflow command with all fixture mounts, imported `madar-schema136-preparation-test:working`, read-only baseline source overlaid at `/app`, `--network=none --memory=2g --cpus=2 --pids-limit=512`; `python scripts/run_tests_no_external_network.py`: **3574 discovered, 683 skipped, 2891 executed successfully**,44.235s; external attempts/sites empty. Remote evidence `~/architecture-hardening-20261016/baseline-tests.log`.
- Imported test image: `python scripts/verify_installed_constraints.py`: PASS, installed dependencies match current constraints. This proves dependency consistency, not a new base-image build.
- Candidate same hermetic backend suite: **3609 discovered, 683 skipped, 2926 executed successfully**,45.212s; external attempts/sites empty. Remote evidence `candidate-tests.log`.
- New cache race suite against unchanged cache services:5 tests,4 FAIL and1 PASS. After implementation plus cleanup coverage:6 PASS, actual thread/event interleavings; local `/tmp/madar-cache-baseline-regressions.log`.
- First focused invocation:92 tests,2 failures and4 errors. One import depended on discovery adding `/app/tests` to sys.path; three catalog tests and two draft tests had stale commercial fixtures previously invisible to CI. Explicit canonical entitlement fixtures now keep real route gates active. Complete discovery subsequently PASS; production gates were not weakened.
- Runtime configuration focused staging suite:10 PASS, including malformed/unsafe origin lists and CSRF bypass rejection.
- Frontend baseline with copied existing dependency directory: lint PASS;233 files PASS,1713 tests PASS,1 SKIP,116.35s. Dependency directory was older than current lockfile; exact `npm ci` validation follows. Initial command from repository root failed ENOENT; rerun from `web/frontend` succeeded. Sandbox Vitest IPC stalled; bounded2-worker run outside that restriction completed.
- Offline `npm ci` failed ENOTCACHED; online exact lockfile `npm ci --no-audit` then completed successfully.
- Initial backend test launch failed because readonly source overlay lacked nested fixture mountpoints; created empty database/supabase mountpoints and image-equivalent backend symlink in owned staging archive. No source code or existing staging data was changed by that correction.
