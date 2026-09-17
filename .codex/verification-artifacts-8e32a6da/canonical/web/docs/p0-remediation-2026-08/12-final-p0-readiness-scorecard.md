# Final P0 readiness scorecard

Scores reflect the system that is actually live, not the validated development target.

| Area | Score / 10 | Rationale |
|---|---:|---|
| Credential incident containment | 2.0 | Inventory and plan complete, but no exposed credential is revoked; an additional credential was re-exposed during remediation. |
| Madar runtime DB security | 4.0 | Direct SQL can be eliminated and development tests pass; production still receives catastrophic credentials. |
| Briefedly DB security | 4.0 | Strong tested role architecture exists; production remains superuser/object owner. |
| Backup completeness | 5.0 | Current Madar/Briefedly local recovery points and checksums exist; Mailcow and full Supabase recovery do not. |
| Off-host resilience | 0.0 | No off-host destination, credential, or immutable copy. |
| Restore confidence | 5.0 | Briefedly restore/migration is strong; Madar is partial and Mailcow untested. |
| Briefedly deployment safety | 5.0 | Rehearsal, role split, migration separation, and rollback policy exist; external gates block live execution. |
| Briefedly Ollama security | 5.0 | Strict authenticated HTTPS design/code passes tests; real endpoint validation is unavailable. |
| Test confidence for P0 changes | 8.0 | Backend, PostgreSQL, migration, Compose, and targeted frontend tests are strong; real providers and full Madar platform restore are absent. |
| Overall sensitive-production readiness | **4.0** | The same critical live blast-radius and host-loss blockers remain because safe production gates correctly stopped execution. |

## Go/no-go

### Madar

- Limited beta: **CONDITIONAL GO** only for non-sensitive controlled users while current credentials are urgently contained; not recommended to expand.
- Paying customers: **NO-GO**.
- Sensitive business data: **NO-GO**.

### Briefedly

- Developer testing: **GO** in isolated development/test environments.
- Trusted beta: **NO-GO** on current production runtime.
- Real private Gmail accounts: **NO-GO**.
- Enterprise/business email: **NO-GO**.

### Server

- Production host: **NO-GO** for sensitive expansion until encrypted off-host recovery exists and the exposed credentials are revoked.

## Exit criteria for P0 PASS

- all exposed credentials rotated/revoked and old values proven invalid;
- Madar production runtime no longer receives direct privileged PostgreSQL access;
- Briefedly production runtime is non-superuser/non-owner and migration credentials are separated;
- encrypted verified off-host recovery exists with repeatable scheduling;
- Mailcow coherent recovery point and procedure exist;
- real authenticated Ollama transport passes backend and worker preflight;
- Briefedly controlled migration/deployment reaches head with worker and verified runtime identity.
