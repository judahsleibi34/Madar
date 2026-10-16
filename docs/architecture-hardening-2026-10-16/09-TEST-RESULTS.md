# Executed validation and limitations

Application-bearing candidate:27860bf2d9174fb315acbb64b0bd26b3b9bc87a5.
Baseline:876b65e73ea8ceaf398145d8677019184798a95c. Later report-only changes do
not alter application code. Full private logs are retained on staging under
`~/architecture-hardening-20261016/` and `~/madar-hardening-20261016/`.

## Backend and source gates

| Execution | Result |
| --- | --- |
| Baseline hermetic unittest discovery |3574 discovered,683 skipped,2891 executed PASS,44.235s |
| Final fresh-archive hermetic discovery |3630 discovered,683 skipped,2947 executed PASS,44.848s |
| Final focused cache/catalog races/contracts |31 PASS,0.109s |
| Staging orchestration safety |8 PASS,0.849s |
| Migration115 actual disposable SQL |32 PASS,4.518s |
| Migration145 actual disposable SQL |8 PASS,1.934s |
| Migration146 actual disposable SQL |8 continuity plus4 pricebook PASS |
| Dependency locks |PASS |
| Mirrored migrations and transition checks |PASS, historical013/014 duplicate-content warnings only |
| Forward release source contract |PASS |
| Tracked secret-file hygiene and git diff --check |PASS; not full historical secret scanning |

Backend command is CI's `python scripts/run_tests_no_external_network.py` with
all workflow fixture mounts. It runs in an imported current-constraints-verified
Python test image, no network,2CPU/2GiB/PID512. A fresh exact Git archive is mounted
read-only; nested database/supabase mountpoints and image-equivalent backend
symlink were created only in the owned test archive. The final archive prevents
stale deleted test modules being collected. External-attempt guard completed
successfully. The683 unchanged skips include environment-dependent database,
Docker, provider and E2E cases; they are not counted as successful execution.
Native and actual SQL checks cover selected skipped categories separately.

Source commands:

```bash
python3 web/scripts/check_dependency_locks.py
python3 web/scripts/check_migrations.py
python3 web/scripts/check_migration_transitions.py
python3 web/scripts/check_forward_release.py
python3 web/scripts/check_secret_hygiene.py
git diff --check
```

Actual SQL commands on the verified staging VM, with local Docker socket and
`BACKEND_TEST_IMAGE=madar-schema136-preparation-test:working`:

```bash
bash web/scripts/rehearse_migration_115.sh
bash web/scripts/rehearse_migration_145.sh
bash web/scripts/rehearse_migration_146.sh
```

## Frontend

Exact-lock `npm ci --no-audit` completed. Then:

```bash
npm run lint
npm test -- --maxWorkers=2
MADAR_REQUIRE_PRODUCTION_API_URL=true VITE_API_URL=/api npm run build
npm audit --omit=dev --audit-level=high
```

Lint PASS.233 test files PASS,1713 tests PASS,1 SKIP,113.60s. Production build
PASS, public bundle audit4 universal preloads/17 entry/39 renderer chunks and
505862 public CSS bytes; dist about44MiB. Audit reports0 shipped dependency
vulnerabilities. These are build outputs, not page load or accessibility scores.
No frontend application source changed afterward; full suite was not repeatedly
rerun without a reason. Production dependency audit does not cover all backend,
container or development dependencies.

## Native integration and browser

Executable commands and deployment source are in08-STAGING-DEPLOYMENT.md.
`smoke.py`, `tenant_smoke.py`, `worker_recovery.py`, `redis_failure.py` and
`restore.py` execute real isolated services. Sanitized evidence contains the
assertions actually reached. Real Chromium151.0.7922.34 TLS portal login/TOTP/admin,
Secure/HttpOnly/SameSite cookies, pending-cookie removal, script cookie denial,
mobile labels/Tab/no horizontal overflow: PASS,0 page errors and0 external hosts.
The test explicitly accepts only the staging self-signed certificate. Full
repository Playwright/product E2E remains NOT TESTED without its published
synthetic fixtures. Selected browser checks are not complete accessibility proof.

## Failures found and corrected

- Four of five cache tests failed against baseline implementations; all passed
  after fencing plus cleanup coverage. New public direct-fill regressions pass.
- Initial focused tests had2 failures/4 errors from import-path and stale
  entitlement fixtures that had never been discovered. Canonical fixtures and
  normal CI discovery fixed them without weakening runtime enforcement.
- Initial cache-only command used identical placeholder anon/service keys;
  startup rejected them correctly. Correct CI distinct placeholders passed.
- An offline npm install missed cached dependencies; online exact npm ci passed.
  Initial frontend command from repo root failed ENOENT; correct cwd passed.
  Restricted sandbox Vitest IPC stalled; bounded two-worker run succeeded.
- Native provider setup exposed auth function ownership, storage schema grants,
  TCP init readiness, nginx read-only temp path and internal bridge publication
  issues. They were fixed before acceptance. Restore helper DAC/stdin failures
  were corrected and independent copies retained; successful restore was rerun.
- Migration146 initially selected an earlier synthetic pricebook window. Scoped
  transactional fixture isolation fixed the test while preserving selection and
  pricing assertions. Production domain semantics were not changed.
- One benchmark overlapped CI load and is discarded, not acceptance evidence.
  The admin-count optimization had no stable measured benefit and was withdrawn.

No unresolved newly introduced test regression remains in executed checks.
Unexecuted/external/production gates remain explicitly incomplete.


## Hosted fresh-build acceptance and final provenance

[Backend Check38849623975](https://github.com/judahsleibi34/Madar/actions/runs/38849623975)
and [Frontend Check38849623985](https://github.com/judahsleibi34/Madar/actions/runs/38849623985)
PASS on0cb384abe7caa98b8bae09ffe4cdeef20d2a0fc3. Backend fresh locked test image
build passed,3630 tests/683 skips/57.380s, external attempts/sites empty, pip check
PASS, actual SQL 115:32 / 145:8 / 146:8+4 PASS. Frontend exact npm ci/lint/build/audit
PASS,233 files/1713 tests PASS/one skip. This closes the fresh test-build evidence
gap; offline native staging still reuses its verified dependency base.

The final provenance-only rebuild0c591b8f preserved identical application code.
Eight orchestration tests PASS (1.857s), runtime/image source labels agree,
readiness true, all nine owned services running. Correct build timestamp/base mode
and image ID are recorded in evidence/staging-final-status.json. Full application
smokes/performance remain explicitly bound to27860bf2, not relabeled as a fresh
execution on an artifact that differs only in metadata/tooling.
