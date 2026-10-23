# Exact implementation-source test evidence

Source `4e86d57c2b0d7564dce06cd2d757ce669ed1c5a8`:

| Scope | Result | CI |
|---|---|---|
| Backend unit/source/model/filesystem |3,455 passed;884 conditional skips;4,339 discovered;0 failures|[Backend](https://github.com/judahsleibi34/Madar/actions/runs/39437098586)|
| Retained/native SQL including new150 slice |252 executions passed;7 new150 boundary/crash cases|Same backend workflow|
| Generic safety/rehearsal |68 passed:40Git/parser/policy +28native DB|[Migration Safety](https://github.com/judahsleibi34/Madar/actions/runs/39437098593)|
| Root-policy filesystem |10 passed|Same workflow|
| Native runtime lock metadata |4 passed; actual owner/modes/inode/symlink/flock, synthetic operator-name fixture|Same workflow|
| Ordinary maintenance backup/independent component restore |PASS,9.335s; no replica/full application/object-metadata activation|Same workflow|
| Frontend |1,713 passed;1 skipped;233 test files;lint/build/audit PASS;build1.25s|[Frontend](https://github.com/judahsleibi34/Madar/actions/runs/39437098457)|
| Fresh candidate |PASS|[Candidate](https://github.com/judahsleibi34/Madar/actions/runs/39437098491)|
| Full providers/browser |PASS,11 components,9 browser groups,326.731s;owned stack stopped|[Native providers](https://github.com/judahsleibi34/Madar/actions/runs/39437099004)|

Staging working-snapshot evidence is separate:321 completed-NORMAL cases
(311passed,10skipped),69 control-plane cases,71 combined hook/lock cases,9native
quiescence/callback cases,and200 executions in the final150 rehearsal script.
These overlap CI and are not an aggregate unique-test count. Native backup also
passed on staging in20.053s. The local managed sandbox initially denied six socket
cases and a systemd parser case; unchanged staging tests passed. Four actual-owner
cases skip on the managed filesystem/container without an appropriate owned home;
the native CI/staging owner tests run and pass rather than counting those skips.

Exact commands:

```bash
python scripts/run_tests_no_external_network.py
bash web/scripts/rehearse_migration_150.sh
bash web/scripts/rehearse_generic_migrations.sh
bash web/scripts/rehearse_migration_policy.sh
python3 web/staging/integration/phase9_maintenance_backup.py REHEARSE
PYTHONPATH=web:web/backend/tests python3 -m unittest test_schema150_lock_ownership -v
python3 web/scripts/check_dependency_locks.py
python3 web/scripts/check_migrations.py
python3 web/scripts/check_migration_transitions.py
python3 web/scripts/check_forward_release.py
python3 web/scripts/check_secret_hygiene.py
python3 web/scripts/check_privileged_inventory.py
```

Backend/frontend commands use their existing isolated CI jobs and locks. Native
commands run only on positively identified owned disposable targets with existing
CPU/RAM/PID/time limits. The actual full-provider command remains the existing
`full_provider_staging.py REHEARSE --source-sha ... --history-base-sha ... --artifacts ...`.
The retained history check reports150 mirrors,0errors and the two historical013/014
content-duplicate warnings. Privileged inventory remains78 classified application
files,not complete host-writer certification. Migrations001–150 are unchanged.
Migration150 SHA256 remains
`63d4d0c7af93bd3c3e93158a2e281b41eed23b83bfafd4b3f1ba22313533b722`.

Before-fix assertion logs are retained privately for the150 intent rejection,
maintenance hash/read race, unlocked root entry/descriptor leaks and actual runtime
lock owner mismatch. Earlier ac03 full-provider run39435933949 was canceled as
superseded; no PASS is claimed for it. The first449 implementation's five workflows
passed but are not substituted for this changed source. No full privileged150
operation, independent handoff, current-head guest reboot or full restored app was
executed. Performance timings are individual synthetic observations,not production
capacity,zero downtime,RPO/RTO or general speedup claims.

## Authenticated native runtime identity at4e

The independently downloaded staging ZIP is artifact12273392411 from
run39437099004,attempt1,digest
`sha256:613ddf9fb0032e9410eca7ddb51663367e82caf719d2ac27b10f2b8611977b45`.
The accepted candidate is artifact12273141563 from run39437098491,attempt1,
digest `sha256:746c3c03a925ec42309ee88e2965b1709aac6d37d5c4dc024423fc9375d66ba3`.

Backend image:
`sha256:0e827fb40d62df1fbc5ea86a820decc3c2233cfdfcc14fabef2ec50fba39749d`.
Frontend image:
`sha256:9f16d5b384ea337ed9d5cc1da65926c97387ec48c8d3f4aa369816a5b9852f60`.

Actual schema150,delivery/outbox/deletion protocols2/2/2. Native login/MFA/refresh/
CSRF/Storage/notifications/readiness and tenant read/write isolation passed. Both
user and tenant deletion completed all ten steps,removed actual synthetic Auth
identities/Storage objects,and preserved the foreign tenant. Consuming-worker
restart passed. Nine selected browser groups passed with0page errors. All11
components were running,health checked where configured. No source overlay was
used and the owned stack stopped before completion publication.

The receipt explicitly states protected_controller_execution=false and
production_authorized=false. This is fresh synthetic genesis,not a preserved-data
146→150 protected upgrade or restored application. External integration revocation,
host-file deletion and lost external-response reconciliation were not exercised.
These runtime identities apply only to4e; a later publication SHA requires fresh
artifacts and acceptance,reported in the session response and PR checks.
