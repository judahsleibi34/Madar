# Validation results

All tests were development-only and used test/fake providers or disposable infrastructure. No customer email, production write or external model call occurred.

| Gate | Command | Result |
| --- | --- | --- |
| Backend full | Exact `.github/workflows/backend-check.yml` container mounts/environment, running `python scripts/run_tests_no_external_network.py` in final image | **1003 passed, 0 failed, 0 skipped** in 33.840s; external attempts `[]`; external sites `[]` |
| Quiz focused | `docker run --rm ... madar-backend:development python -m unittest -v tests.test_public_quiz_security` with current migration trees mounted read-only | **8 passed** in 0.002s |
| Frontend unit | `npm test` in `web/frontend` | **117 files passed; 738 tests passed; 1 intentionally skipped; 0 failed** in 142.62s |
| Frontend lint | `npm run lint` | **PASS**, zero errors |
| Frontend production build | `npm run build` | **PASS**; Vite emitted only the known >500 KiB chunk advisory |
| Python syntax | `python3 -m compileall -q web/backend web/deployment/lib` | **PASS** |
| Shell syntax | `bash -n web/scripts/*.sh web/deployment/bin/*` | **PASS** |
| Compose resolution | `docker compose config --quiet` from `web` | **PASS**; expected unset-secret warnings in validation shell |
| Migration mirrors | `python3 web/scripts/check_migrations.py` | **82/82**, errors 0; two known historical duplicate-content warnings (013/014) |
| Diff hygiene | `git diff --check` | **PASS** |
| Disposable migration | PostgreSQL 17 container, apply/rerun 082 plus RPC adversarial exercise | **PASS** after correcting a discovered local-variable ambiguity |
| Backup/off-host tooling | Backend backup tooling suite | **PASS**, including unmounted and wrong-volume refusal |

Two failed focused invocations were harness mistakes and are retained for transparency: the first used `SUPABASE_SERVICE_ROLE_KEY` instead of the application’s `SUPABASE_SERVICE_KEY`; the second mounted migration files one directory too deep. Both failed before the affected test and the corrected 8/8 invocation passed. A later full `unittest discover` invocation also used an unsupported simplified mount layout and discovered only 972 tests; its 13 failures/23 errors were explicit missing `/scripts`, migration/workflow mount, and non-root `/app/uploads` permission failures. Repeating with the exact checked-in CI layout discovered and passed all 1003 tests.

Dependency locks remained consistent. No dependency upgrade or production migration was performed. The final development image provenance check is recorded in the promotion plan/terminal handoff.

Final isolated development runtime evidence: backend image ID `sha256:52ec810d…`, frontend image ID `sha256:5cb5bd0d…`; both OCI revision labels equal `874d035af5f219dac993407e02c5bfc825baaeb1`, both creation labels equal `2026-08-25T05:15:00Z`, both containers are healthy, backend `/health/version` matches, and frontend returned HTTP 200 on loopback port 3001.
