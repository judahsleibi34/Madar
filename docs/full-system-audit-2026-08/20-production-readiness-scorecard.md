# Production-readiness scorecard

Scores are evidence-weighted 0–10. A passing test or strong code path does not offset catastrophic credential/recovery risk.

| Area | Score | Rationale |
|---|---:|---|
| Madar application security | 6.0 | strong middleware/auth/input controls; superuser credential and hostile-file gap |
| Madar tenant isolation | 7.5 | strong scoped routes, grants, publication identity and atomicity; backend compromise bypasses all |
| Madar reliability | 5.0 | workers/health/resources exist; flaky readiness, deploy and backup gaps |
| Madar data integrity | 6.5 | atomic publication/reservation/quota/jobs and current schema; restore/rebuild unproven |
| Madar observability | 5.0 | good metrics/readiness/log primitives; no collector/alerts |
| Madar deployment safety | 3.5 | non-atomic rebuild/reset, no migrations/readiness, no immutable rollback |
| Briefedly application security | 5.0 | current source strong; running production is old/unhardened |
| Briefedly workspace isolation | 7.0 | scoped dependencies/composite FKs strong; current prod lacks latest constraint migration |
| Briefedly Gmail/OAuth security | 6.0 | encrypted tokens/one-time state/owner guard; prod drift, no PKCE/revocation retry |
| Briefedly AI security | 5.5 | evidence validation/prompt isolation strong; transport identity and deployment mismatch |
| Briefedly privacy | 3.0 | good current lifecycle code but absent production worker/schema/backups |
| Briefedly reliability | 2.5 | no prod worker, old schema, likely next-deploy startup failure, no alerts/backups |
| Server hardening | 4.0 | modern OS/loopback apps/home permissions; privilege concentration/root-only gaps |
| Network security | 5.0 | Cloudflare and loopback origins strong; firewall/IPv6/SSH not verified, broad mail ports |
| Container security | 6.0 | Madar/current source excellent; stale Briefedly and Docker-socket/legacy services |
| Database security | 2.0 | two confirmed application superuser paths dominate |
| Backup/recovery | 1.5 | old verified Madar backup only; no schedule/off-host/mail/restore drill |
| Secrets management | 2.5 | file modes mostly good; excessive scope, history/hardcode, transcript incident |
| Monitoring | 2.5 | local primitives exist, no external collection or alerts |
| Incident response | 3.5 | Briefedly security runbook and some docs; no full host/customer exercise/process |
| **Overall production readiness** | **4.0** | suitable for controlled engineering work, not sensitive commercial production |

## Explicit go/no-go decisions

### Madar

- Limited beta: **CONDITIONAL GO**, only after credential/DB-role/off-host-backup P0s, basic monitoring, and explicit non-sensitive beta limits.
- Paying customers: **NO-GO** until P0/P1, restore drill, deployment rollback, privacy operations, and green E2E/security regressions.
- Sensitive business data: **NO-GO** until the above plus independent penetration/tenant review and incident exercise.

### Briefedly

- Developer testing: **GO** with synthetic/dev-only accounts and no private mailbox.
- Trusted beta: **NO-GO** until runtime/schema/worker/Ollama/DB privilege/backups are reconciled.
- Real private Gmail accounts: **NO-GO**.
- Enterprise/business email: **NO-GO**; requires all P0/P1 plus formal privacy/security/IR/SLO controls.

### Server

As a sensitive multi-tenant production host: **NO-GO**. It may continue as a controlled development/beta host only with explicit acceptance and immediate P0 work. The decisive conditions are least privilege, recoverability, effective firewall/SSH verification, deploy separation, legacy-service ownership, and monitoring.
