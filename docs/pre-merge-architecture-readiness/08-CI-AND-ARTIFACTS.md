# CI and exact-source evidence

Baseline:1113c43364df632cc3376821cc6223a44af07822. Implementation:
83dce3da2204980d5d89fc071cf1fc9fbe0b5cd0. Local tests exercised the resulting
implementation bytes; the review-document commit must receive fresh CI.
Resolve publication HEAD with `git rev-parse HEAD` and use only workflow runs
whose `head_sha` equals it. This document is not a later-source CI attestation.

Local commands/results:

| Command | Result and scope |
|---|---|
| `PYTHONPATH=web:web/backend/tests python3 -m unittest discover -s web/backend/tests -p 'test_completed_normal*.py' -v` |351passed,10skipped; MODEL/SOURCE CONTRACT and owned process tests |
| Focused executor/provider/inventory/staging modules |146passed; MODEL/SOURCE CONTRACT and owned filesystem tests |
| `bash web/scripts/rehearse_migration_150.sh` |208native SQL executions passed; model authority/backup boundaries |
| `bash web/scripts/rehearse_migration_policy.sh` |10native isolated policy-filesystem cases passed |
| `bash web/scripts/rehearse_maintenance_role_restore.sh` |Native original roles/ACL/data restore passed |
| `python3 web/staging/integration/phase9_maintenance_backup.py REHEARSE` |Native component restore passed; no replica/full application proof |
| Migration/mirror/transition/dependency-lock checks |PASS; known historical013/014 duplicate-content warnings retained |

The host and old local backend image lacked the pinned parser. Those initial
plans correctly failed closed with `postgresql_parser_unavailable`; they are not
the substantive classification evidence. A separately hash-verified pglast7.21
(PostgreSQL17) run confirms all four migrations remain Class D. See the dossier.

Fresh CI status, run/attempt IDs and candidate artifact identities are recorded
after publication in the private integration receipt and PR220 checks. The
existing Full Provider Staging failure must remain visible until genuine
exceptional protected acceptance exists. No old image receipt is relabeled.

Private raw evidence: `/opt/madar-development/evidence/integration/pre-merge-readiness-20261021/`.
