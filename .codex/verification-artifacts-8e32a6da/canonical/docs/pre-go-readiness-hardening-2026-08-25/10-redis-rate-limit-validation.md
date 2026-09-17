# Redis and rate-limit validation

## Runtime configuration

The slot-local staging Redis matches tracked configuration:

| Setting | Effective value |
| --- | --- |
| Persistence | disabled / ephemeral |
| `maxmemory` | 48 MiB |
| Eviction | `noeviction` |
| Container memory limit | 256 MiB |
| Health check | enabled |
| Restart | reviewed Compose policy |

`noeviction` is intentional: security rate-limit state must not be silently evicted to admit requests.

## Outage proof

Stopping active Redis caused `/health/ready` to return 503 with Redis unavailable. A syntactically valid login request returned 503 `protection service unavailable`; it did not fall back to a local permissive limiter. Restart restored readiness to 200 and distributed protection resumed.

The full suite covers login, registration, password reset, MFA, public forms, reservations, quiz attempts, uploads, analytics ingestion, AI routes when configured, and administrative APIs under healthy, exhausted, and unavailable Redis states. Maxmemory/cgroup behavior and recovery were exercised without external traffic.
