# Security verification scope

The changes correct failure-state/resource handling and object-capture
availability. Tests preserve single-use attempts, checksum-captured SQL,
root-private authority boundaries, unknown-actor refusal, candidate identity,
strict protocols, symlink/inode/mode checks and object-byte preservation.

Focused executor/provider/inventory/staging tests:146passed. Controller suite:
361collected,351passed,10conditional skips. Root-policy filesystem:10passed.
Counts overlap with backend CI and are not combined as unique coverage.

The48df165c generic regression suite passed74cases:45source/model and29native
PostgreSQL. It fixes source-plan evidence substitution and a native origin race;
neither establishes privileged authority or full application acceptance.

Native SQL regression exercises notification/outbox/deletion ownership,
reservation, inventory/order/payment and calendar invariants. It does not prove
that every application authorization path is safe or that real provider effects
were reconciled. The broad subsystem adversarial review requested for readiness
is incomplete; no independent security approval is claimed.

Residual issues include broad deletion-worker service-role exposure, uncertain
external-effect reconciliation, missing full protected handoff/activation proof,
and incomplete full-application recovery. Their existence is not resolved by
passing ownership RPC tests. Do not enlarge credentials or replay destructive
effects to overcome them.

No production credential, role archive, private journal, customer record or
synthetic private authority is included in this package.

## Audit remediation: credential scanning

The tracked-file check now scans file contents for private-key headers, GitHub
and AWS credential formats and JWT-shaped tokens, including tests and documents.
Failures report only path, line and type; chunk boundaries cannot hide a token.
It does not follow tracked symlinks into operator files. This is current-tree
prevention, not certification of arbitrary opaque passwords, binary formats or
historical credential activity. The separate bounded history scanner retains
candidate references privately under the canonical development evidence roots;
it no longer requires a home-directory workspace. Historical pattern candidates
still require classification rather than being counted as confirmed leaks.
