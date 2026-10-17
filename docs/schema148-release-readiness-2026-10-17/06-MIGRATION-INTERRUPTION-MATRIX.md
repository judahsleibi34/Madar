# Interruption evidence and required behavior

Command: `BACKEND_TEST_IMAGE=madar-schema136-preparation-test:working bash
web/scripts/rehearse_migration_148.sh`, on the dedicated VM. The new suite executes
19 native tests against independent marked146 clones, then5 upgrade,17 fencing
and22 business tests. Authorization and supervisor transport are explicit
fixtures; SQL, locks, connections, executor journals and process exits are real.

| Stage | Actual test/evidence | Outcome / boundary |
|---|---|---|
| Active/expired processing | live_processing, expired_uncertain_provider_outcome | Rejected before147, no reset |
| Legacy resurrection | running_or_resurrected_old_supervisor; supervisor_resurrection_between_commits | Guard refuses;146 or committed147 retained |
| Active DB transaction/locks | legacy_transaction_and_queue_lock; competing_legacy_claim | Admission rejects or native SQL lock serializes |
| Race after check | lock_race_after_quiescence; test148_lock_timeout | Five-second timeout;146 or147 retained |
| Source/manifest/schema mismatch | checksum_failure; wrong_schema_identity; admission tamper cases | Refuses; checksum before backup/connect |
| Executor crash before SQL | real_executor_crash_before_sql | Process exits80; DB146, consumed attempt cannot replay |
| Executor crash after147 COMMIT | real_executor_crash_after147_commit | Process exits81; DB147 despite stale running journal |
| SQL/connection failure147 | sql_failure_before147_commit; upgrade disconnect/rollback suite | Transaction rolls back146 DDL/grants |
| Failure148 |148_disconnect;148_lock_timeout; missing147_prerequisite |147 fencing survives; no partial reservation changes |
| Fresh forward scope | fresh_forward_attempt_retains147_and_applies_only148 | Verified DB progress, only148 applied |
| Replay148 | rehearsal shell repeated exact SQL | Refuses expected_schema_147;148 unchanged |
| Auth/Storage preservation | root_preservation_includes_all_auth_storage_tables | Sessions/extra metadata included; later auth mutation detected |
| Provider accepted/crash | fencing provider_acceptance_crash; stable_idempotency_key test | At-least-once duplicate risk exposed; stable provider key deduplicates fixture |
| All coordinator effects | test_every_interrupted_effect_revokes_or_keeps_read_only | Source transport fixtures; target authority withheld/revoked |

The coordinator tests cover backup/candidate/source/quiescence/migration/grant/
promotion/worker/post-validation effect interruptions at source interfaces. They
are not real privileged installation, systemd reboot or production replica tests.
Current-data acceptance, actual protected credential consumption, full supervisor
restart behavior and production proxy promotion are BLOCKED/NOT TESTED here.
Do not label fixture-only rows full production PASS.
