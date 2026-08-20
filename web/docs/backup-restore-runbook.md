# Backup, Restore, and Rollback Runbook

This runbook defines repository-supported logical backups. It does not claim that a production restore has been proven. Operators must approve concrete RPO and RTO values before launch: **RPO: pending operator approval**; **RTO: pending operator approval**.

Each backup contains a PostgreSQL custom-format logical dump, public builder assets, private uploads, generated private artifacts, locally managed avatars, format metadata, and a SHA-256 manifest. Store the resulting directory on encrypted-at-rest storage with access controls and off-host replication. Credentials are supplied only through environment variables and are never written to the backup or logs.

Use `scripts/backup_madar.sh --dry-run` first. For a real backup set `MADAR_BACKUP_DIR`, `MADAR_DATABASE_URL`, and the four source-directory variables when their deployment paths differ from `/app`. The script creates a new timestamped directory and never prunes older backups. Retention must be an explicit operator policy outside this script.

Before every migration, create and verify a backup, record the application image/commit and current migration list, and keep the prior deployable image available. Run `scripts/verify_backup.sh BACKUP_DIRECTORY` before proceeding.

Restore only into an isolated empty test/staging database. Set distinct `MADAR_DATABASE_URL` and `MADAR_RESTORE_DATABASE_URL`, all `MADAR_RESTORE_*_DIR` paths, and `MADAR_RESTORE_CONFIRM_ISOLATED=YES`. Run `scripts/restore_madar.sh --dry-run BACKUP_DIRECTORY`, then the real command. After restore, run migration validation, database/RLS verification, file-count sampling, checksum sampling, authenticated/private-file access tests, and application readiness against the isolated target. Never point the restore command at production or a shared database.

Rollback decision: if a backwards-compatible application defect occurs, redeploy the recorded prior image. If a migration has started, stop writes, assess whether the migration is forward-fixable, and prefer a reviewed forward repair. Restore from the pre-migration backup only for confirmed destructive/corrupting changes and only with incident-command approval, an accepted data-loss window, and a rehearsed isolated restore. Never improvise down-migrations on production.

Run a quarterly isolated restore drill. Record date, backup ID, source commit, restore target, dump and file verification results, elapsed time, observed data loss window, failed checks, owners, and follow-up actions. A drill is complete only when an application instance passes readiness and representative tenant-isolation and private-artifact checks against the restored copy.
