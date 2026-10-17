# Exact coordinated146→149 strategy

Choose Strategy A: one newly authorized maintenance operation, with immutable
147,148,149 executed consecutively by the existing locked executor. Schemas147
and148 are READ_ONLY checkpoints, never ordinary NORMAL destinations. The148
outbox/deletion compatibility defects and the149 worker's refusal to consume148
make a normal two-operation cutover inappropriate.

Introduce an explicit new profile; preserve the historical146→148 profile,
active release.json, old authorization/receipts and all001–149 SQL bytes. Ordinary
automatic manifest admission still rejects coordinated migrations. Exact source,
artifact, controller, database, backup/restore/replica and single-use authorization
remain mandatory. After any committed147 step, recovery is forward with old
workers fenced; no rollback to unfenced writers or replayed credentials.

Provider quiescence must have a persistent, operation-bound lifecycle. Its staging
role proof alone is insufficient. Positive credential probes precede fencing;
ingress/supervisors/object writers/roles/sessions and boot must remain closed through
preservation. No provider or deletion lifecycle gap becomes PASS by adding a
profile. Missing adapters/evidence must reject before privileged execution.
