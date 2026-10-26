# Operational signals

New deletion worker emits bounded deletion.ownership_protocol_required and
refuses claims on unavailable/legacy protocol; it does not leak provider errors.
Existing notification queue/ownership/ack metrics remain intact. Private durable
provider event journals expose sequencing/effect uncertainty without metric labels
containing tenant/user identities. Recovery reporting now derives reconciled fault
counts from actual journal records and explicit executed controls; reusing recovery
for backup must not invent fault-injection/restart claims.

PhaseIV's isolated alert503/retry/dedup/recovery delivery is historical. No production
alert destination or durable alert service was activated. Full deletion/backlog/
backup/authority alert delivery remains a follow-up acceptance requirement.
