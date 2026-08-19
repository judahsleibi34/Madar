# P0 dependency and gate register

P0 remains incomplete. No item below is authorized by this document.

| Requirement | Current evidence | Status | Unblocking event | Then execute |
|---|---|---|---|---|
| Two encrypted rotating copies | drives not available | WAITING FOR BACKUP HARDWARE | drives received, identified, tested, encrypted, keys escrowed | first full copy, disconnect one, verify restore |
| Off-host/offline verification | all current backups on Node A | WAITING FOR BACKUP HARDWARE | separate medium/location available | checksum and restore from that copy |
| Full Supabase-compatible recovery | vanilla PG partial restore only | WAITING FOR PROVIDER AUTHORITY | provider restore/export procedure and target approved | full Auth/PostgREST/Storage/Vault drill |
| Mailcow coherent backup | helper exists; no recovery point | WAITING FOR BACKUP HARDWARE | media plus maintenance window | supported all-component backup and isolated restore |
| Real authenticated Ollama gateway | code/synthetic HTTPS pass; endpoint offline | WAITING FOR OLLAMA | PC/Node B online with gateway/cert/token | backend and worker TLS/auth/model/outage preflight |
| Supabase rotation authority | no provider-side authority in task | WAITING FOR PROVIDER AUTHORITY | authorized operator and provider plan | issue replacements, bounded cutover, revoke and prove old dead |
| Host shared-Postgres credential | exposed and still valid | WAITING FOR MAINTENANCE WINDOW | verified off-host recovery and owner decision | rotate or decommission after consumer proof |
| Madar runtime URL removal | committed in dev only | WAITING FOR MAINTENANCE WINDOW | recovery, replacement credentials, approved window | one-service-at-a-time cutover and tenant smoke tests |
| Briefedly role cutover | clone rehearsal passed; live flags all true | WAITING FOR MAINTENANCE WINDOW | backup/Ollama/provider gates green | create/test roles, migrate consumers, disable legacy login |
| Five Briefedly migrations | clone passed in ~5.4 seconds | WAITING FOR MAINTENANCE WINDOW | same as role cutover; connections drained | migrate as migrator, verify ownership/aggregates |
| Briefedly worker | source/dev healthy; live absent | WAITING FOR OLLAMA | secure model route and migrated DB | start worker, heartbeat/lease/privacy smoke |
| Runtime drift reconciliation | live images dated 2026-08-02 | WAITING FOR MAINTENANCE WINDOW | immutable digests and rollback record | deploy current backend/frontend/worker; record identity |
| Node B placement | hardware not commissioned | WAITING FOR NODE B | commissioning acceptance passes | staging/restore first; no direct production move |

## Gate invariants

- Credential revocation follows—not precedes—replacement proof and physically separate recovery.
- Briefedly migrations do not run until the real Ollama configuration starts both backend and worker.
- Node B commissioning does not collapse into production migration.
- Mailcow modifications or restore operations require their own approved window.
- A local dump, a powered-on second node, or an attached always-online drive is not by itself an off-host/offline recovery solution.

## Closure evidence

Each P0 item requires command/action log, timestamp, operator, precondition, result, old/new identity metadata without values, negative test, rollback/forward-repair result, and links to backup/restore evidence. Update both this document and the master register; never mark P0 complete from code state alone.
