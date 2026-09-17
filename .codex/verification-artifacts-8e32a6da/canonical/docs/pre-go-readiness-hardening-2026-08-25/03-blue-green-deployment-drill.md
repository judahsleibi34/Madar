# Blue/green deployment drill

## Result

**PASS.** G16 is closed by real staging evidence.

The release controller validates a clean candidate SHA, acquires a deployment lock, builds SHA-addressed images, records immutable image IDs, verifies schema compatibility, starts the inactive slot, checks liveness/readiness/deep validation and release identity, switches the loopback traffic target, observes the release, and marks it known-good.

## Proven controls

- Candidate service did not receive active traffic before validation.
- The active slot survived build, dependency, readiness, and pre-switch failures.
- Image tags were resolved and compared with expected image IDs before startup.
- Deployment state and traffic target were durable and queryable.
- A known-bad SHA was suppressed before a rebuild; manual retry is explicit.
- Concurrent deploy invocation was rejected by the release lock.
- Interrupted candidate phases were recovered from durable state.
- Inactive queue consumers remained stopped, preventing duplicate processing.
- Old unused slot networks were preallocated deterministically, and obsolete empty networks were removed.

## Final release identity

| Field | Value |
| --- | --- |
| SHA | `9a3c67e6058768b71100349b89379b2b6052915a` |
| Active slot | blue |
| Build timestamp | `2026-08-25T12:42:27Z` |
| Schema | 83 |
| Backend digest | `sha256:67ba38a4bfbe0387c7d100b6f68458d768627dfb93d85dbc716563768ca7c134` |
| Frontend digest | `sha256:0941db55d35246b4e78ecffedafb0ea46b5ed38a43cd9d042a90863db18d38e2` |

The worker uses the backend release image and reports the same SHA. The retained green slot remains available as the previous known-good release.
