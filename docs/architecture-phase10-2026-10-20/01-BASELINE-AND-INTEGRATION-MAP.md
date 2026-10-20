# Phase X baseline and actual integration edges

Parent: draft PR218 at `cc1b97a3cc031f3104f3c8d1d018f41a8f08ce7b`.
Main: `876b65e73ea8ceaf398145d8677019184798a95c`, protected=false, rulesets=[]
at the refreshed GitHub observation. No source integration or production effects.
The dedicated branch is `codex/phase10-protected-controller-integration-20261020`.
Existing worktrees/evidence and staging services are retained.

The development host is madar-gpu. Staging identity and sudo were verified;
4 vCPUs, 5,402 MiB RAM, approximately 2,425 MiB available and 11 GiB free disk.
Several retained provider stacks run there. No additional full stack is started.

| Edge | Existing caller/callee and constraint | Phase X state |
|---|---|---|
| Entry and authority | Frozen `continue_completed_normal_upgrade.py` → `CompletedNormalBootActor` → `CompletedNormalUpgrade`; root credentials, source measurement, historical receipts and two operation locks | Retained; profile150 remains unregistered |
| Candidate | Coordinator seals CI archive, then service prepare → staged-runtime seal; subsequent activate/publish/adopt assumes bridge-first serving | Private maintenance ordering still incomplete |
| Maintenance | `ProviderMaintenance150` → concrete `Schema150ProviderAdapter` effects; complete exact inventory, original preimages, durable barrier, held locks | Not called by complete150 coordinator |
| Backup capture | `CompletedNormalBackupContext(provider_adapter=...)` → existing `capture_and_replicate` → ordinary dump, original roles, object capture, native restore and append-only receiver | Existing capture preserved |
| Backup to migration | `seal_migration_inputs` → pure `intent_document` and root-private credential inputs | Repaired150 preparation intent and independent inner digest/provider-journal binding |
| Installed verifier | `verify_migration_backup` → measured installed `backup_support.py verify` | Independent maintenance digest now transported and enforced |
| SQL | Existing `run_migration` → `LockedMigrationExecutor`; service child requires its own deploy lock and registered profile | Concrete provider callback now uses the executor's actual advisory-locked cursor; parent/provider full operation remains unwired |
| Private providers | Concrete private role/provider recovery → acceptance/activation delegates | Complete current-data acceptance delegates not wired |
| Write handoff | Existing `CompletedNormalWriteHandoff` verifies fresh source/schema/boot/artifact authority |150 private acceptance/target handoff not integrated |
| Completion/recovery | Existing compatible boot actor, worker ownership, proxy and forward repair | Complete150 interruption/reboot lifecycle not proven |

No new controller, arbitrary SQL runner, issuer or CLI execution bypass is added.
A source-backed preparation intent is metadata, not admission. The child executor
still rejects an unregistered150 operation. No test-domain authority was issued
for a complete release. Future151 remains incompatible with published150's
strict deletion protocol; no historical SQL is modified.

## Tested lock integration correction

`CompletedNormalUpgrade.root_credential` now reacquires deploy.lock after service
execution and verifies actual ownership of both coordinator locks before issuing
a temporary credential. It releases only its own window, preserving a borrowed
parent descriptor. Collision/issuer/effect/cleanup failures remain fenced. Native
filesystem tests reproduced prior unlocked entry and leaked contended descriptors.

`Schema150ProviderAdapter.migration_guard` is now a callback for the existing
`LockedMigrationExecutor`, not another executor. It validates the immutable150
transition/checksum and actual current-session advisory lock, then passes that
cursor through the existing provider lifecycle. A separate psql observer would
incorrectly classify the migration connection as a foreign writer. Real native
SQL/locks plus journal/flock passed9 tests; host effects/authority remain model
fixtures in those tests. No PID/name exemptions, registration or authority issued.
