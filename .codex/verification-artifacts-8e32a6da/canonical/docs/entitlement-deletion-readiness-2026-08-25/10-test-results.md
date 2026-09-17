# Validation results

| Area | Command / evidence | Result |
| --- | --- | --- |
| Backend full | CI-equivalent locked image, `python scripts/run_tests_no_external_network.py` | 1,032 passed; 0 failed; 0 unexpected skips; 47.664s |
| External network guard | Same backend run | `EXTERNAL_ATTEMPTS []`, `EXTERNAL_SITES []` |
| Focused changed/adjacent modules | entitlement, deletion, account/tenant lifecycle, admin safety/routes, deployment contract | 88 passed; 0 failed; 0 skipped; 0.435s |
| Frontend unit | `npm test -- --run` | 117 files; 738 passed; 1 intentional skip; 138.40s |
| Frontend lint | `npm run lint` | PASS |
| Frontend production build | `npm run build` | PASS in 5.47s; existing chunk-size advisory only |
| Migration parity | `python3 web/scripts/check_migrations.py` | 83/83; 0 errors; two unchanged historical duplicate-content warnings |
| PostgreSQL 17 | `web/scripts/rehearse_migration_083.sh` | PASS; forward apply and rerun |
| Python syntax | `python3 -m compileall -q web/backend` | PASS |
| Diff whitespace | `git diff --check` | PASS before report commit |
| Development runtime | Compose project `madar_dev`; version/readiness/frontend/image labels | Backend/frontend healthy; SHA `09e4076566b27a42dedee414ae9abe20c062e63b`; readiness 200 on schema 81 bridge; deletion worker disabled; frontend 200 |

The PostgreSQL rehearsal covers full-batch mapping, exact mapping replay, unique entitled rows/add-ons, user and tenant freeze, fixed step/subject capture, duplicate-request rejection, retention deferral, service-role isolation, schema identity, worker double-claim rejection, and expired-lease crash recovery.

Focused deletion tests cover self/owner/admin authorization, exact AAL2, cross-user status hiding, step replay, transient and late provider failure, verification mismatch, provider object replay, path traversal, symlink refusal, unknown-storage manual intervention, cancellation boundary, tenant/public-state removal, retained classes, and redacted metrics.

The lifecycle-gate suite also distinguishes the explicit schema-81/82 bridge from dependency failure: only a recognized absent `lifecycle_state` column plus an authoritative 81/82 schema record permits service continuity; generic database errors deny.

No real Google, Microsoft, SMTP, AI, customer endpoint, or other external provider was contacted.
