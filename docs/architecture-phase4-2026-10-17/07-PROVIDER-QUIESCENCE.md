# Provider writer quiescence

Notification quiescence does not fence GoTrue refresh/MFA/session/audit writes,
Storage metadata/object writes, PostgREST writers or existing pooled sessions.
A point-in-time absence of transactions is insufficient.

The separate `database.provider_quiescence` readiness gate is mandatory. Missing
evidence stays NOT TESTED; staging evidence cannot satisfy production.
`provider_quiescence_rehearsal.py` defaults INSPECT and mutates only its own
network-none labelled synthetic PG17 fixture. The native drill proved durable
NOLOGIN after child exit83, denial of new connections, continued old-session
capability until explicit drain, rollback of uncommitted changes, restart-persistent
fencing, unchanged Auth/MFA/Storage/business roots and explicit exact-role recovery.
It completed16.317s. An interrupted earlier fixture was separately recovered.

This is a prerequisite proof, not a production adapter. A production design
must bind every service/supervisor/credential path, preserve role preimages in
backup/recovery, drain sessions and prepared transactions, reconcile probes and
maintenance health, protect object bytes, and hold restrictions across boot and
forward repair. Current consumer guards need live PostgREST probes, so simply
stopping providers would violate their contract. No arbitrary table exclusions
or volatility allowances were added. Controller integration remains BLOCKED.
