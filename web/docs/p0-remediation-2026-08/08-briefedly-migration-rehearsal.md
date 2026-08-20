# Briefedly migration rehearsal

## Scope

Source: current production dump from 2026-08-18.

Starting revision: `d8c6b4a2f190`
Target revision: `c8e5f1a3b647`
Pending revisions: five

## Pre-migration integrity

Aggregate-only verification corrected a stale audit assumption: production is not empty. It contains real workspace/email/report data. Eight composite workspace relationship mismatch checks returned zero, so the new ownership constraints did not conflict with observed production relationships.

## Rehearsal sequence and results

1. Restored current production custom dump: pass.
2. Reproduced production Alembic revision and aggregate counts: pass.
3. Prepared owner/migrator/runtime/backup roles: pass.
4. Repeated role preparation to test rerun behavior: pass; four non-DBA roles retained all five prohibited flags as false.
5. Ran runtime credential against Alembic: denied as designed.
6. Ran five upgrades as migrator with explicit owner role: pass.
7. Verified target revision: pass.
8. Verified 16 public application tables owned by owner: pass.
9. Rechecked aggregate counts: preserved.
10. Tested composite workspace FK with a synthetic mismatched row: rejected.
11. Ran Alembic again at head: pass.
12. Ran fresh zero-to-head: pass.
13. Ran head-to-production-revision downgrade and forward upgrade on empty clone: pass.
14. Started backend and worker with runtime role: pass.
15. Ran positive runtime CRUD and negative DDL/admin tests: pass.
16. Finalized legacy bootstrap on clone and proved old role identity could not authenticate: pass.

## Failures found and corrected during rehearsal

### Object reassignment

An initial `REASSIGN OWNED` approach failed because the cluster bootstrap role owns the required `plpgsql` extension. The transaction rolled back safely. The design was corrected to transfer only migration-controlled public objects.

### Alembic transaction boundary

An initial migration run logged upgrades but the clone remained at the starting revision because `SET ROLE` opened an implicit outer transaction that rolled back when the connection closed. `connection.commit()` was added before Alembic’s transactional DDL block. The full rehearsal was repeated successfully.

These failures demonstrate why live production was not used as the first migration target.

## Lock/reversibility assessment

The clone upgrade completed in approximately 5.4 seconds at current data volume. DDL and composite constraints can take stronger locks; a maintenance window and connection drain are still required. Current volume is small, but timing is not a guarantee for later datasets.

Although the empty-clone downgrade works, it drops durable-job/session/export structures and can destroy data created by the new version. Production rollback policy is therefore **forward repair or old-application compatibility before new writes**, not blind downgrade after traffic resumes.

## Production result

Not run. The off-host and real Ollama transport gates remain red.
