# Backup and disaster-recovery audit

## Existing backups

Madar's supported script correctly creates a PostgreSQL custom dump plus builder assets, private uploads, generated artifacts, avatars, metadata, and SHA-256 manifest under umask 077. The 2026-07-31 full backup passed checksum verification during this audit. Later 2026-08-11/12 artifacts are database-only pre-migration dumps. Environment copies exist through 2026-08-13.

No timer/cron, off-host replication, encryption-at-rest evidence, retention enforcement, backup alert, or successful isolated restore drill was found. `backup_freshness` is disabled in readiness. Briefedly has a DB-only backup script but no production backup artifact; one dev dump exists. Mailcow has only pre-install inventory, not mailbox/config/database backup.

Effective full-system RPO is therefore not formally established. The latest demonstrated coherent Madar DB+assets point is 2026-07-31. Briefedly and Mailcow effective catastrophic-loss RPO is "all data since inception" absent external backups. RTO is unknown because no restore drill exists.

## Scenario assessment

| Scenario | Current impact | Current recovery capability | Missing prerequisite |
|---|---|---|---|
| A. Server disk dies | all local apps, mail, configs, assets, Briefedly DB lost | partial old Madar local backup dies with disk | encrypted off-host system backups; rebuild automation |
| B. PostgreSQL corrupts | app outage/data loss | old logical dumps; no PITR | current verified dump/PITR and restore drill |
| C. Deployment breaks | outage | Sleibi rollback; Madar rebuild/reset; Briefedly manual | immutable images and health-gated rollback |
| D. Migration partially succeeds | schema/app mismatch | forward repair or old dump, untested | staged SQL rehearsal, compatibility plan, preflight backup |
| E. Tunnel credential lost | public app outage | credential file only on host | protected off-host credential escrow/reissue runbook |
| F. Mailcow data lost | mailbox loss | none found | Mailcow-consistent DB/vmail/config/keys backup and test |
| G. Tenant deletes everything | logical data loss | whole-system old restore only | tenant snapshots/export, soft-delete/retention, granular restore tooling |
| H. `madar` compromised | host-root via Docker; all local secrets/data | rebuild from trusted media required | role separation, off-host immutable backups, IR plan |
| I. Docker fills disk | DB/mail/app failures | manual cleanup only | disk alerts, log/build-cache policy, separate filesystem/quotas |
| J. Ollama unavailable | Briefedly reports/jobs fail/retry | no alternate provider; current prod old behavior | degraded UX, queue/alert, tested recovery/fallback policy |

## Required recovery design

Daily encrypted off-host backups should include: Madar DB and all four asset classes; Briefedly DB; Mailcow MariaDB/vmail/Redis/config/DKIM/TLS material per vendor procedure; Compose/systemd/deploy scripts; Cloudflare tunnel re-provisioning metadata; secret-store export or separately escrowed secrets; and commit/image digests. Use periodic full plus frequent incremental/PITR appropriate to an approved RPO. Keep backup credentials separate from the host.

Quarterly isolated restore drills must build an empty host/database, restore, run migrations, validate checksums, start services, and exercise representative tenant/private artifact/OAuth-disconnected behavior. Record elapsed RTO and data-loss window; never infer them from script existence.
