# Backup, Restore, and Rollback Runbook

This runbook defines repository-supported logical backups. It does not claim that a production restore has been proven. Operators must approve concrete RPO and RTO values before launch: **RPO: pending operator approval**; **RTO: pending operator approval**.

Each backup contains a PostgreSQL custom-format logical dump, public builder assets, private uploads, generated private artifacts, locally managed avatars, format metadata, and a SHA-256 manifest. Store the resulting directory on encrypted-at-rest storage with access controls and off-host replication. Credentials are supplied only through environment variables and are never written to the backup or logs.

Use `scripts/backup_madar.sh --dry-run` first. For a real backup set `MADAR_BACKUP_DIR`, the standard libpq variables (`PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`, and `PGSSLMODE` where required), and the four source-directory variables when their deployment paths differ from `/app`. The password is carried only in process environment and never appears in a command argument. The script creates a new timestamped directory and never prunes older backups. Retention must be an explicit operator policy outside this script.

Before every migration, create and verify a backup, record the application image/commit and current migration list, and keep the prior deployable image available. Run `scripts/verify_backup.sh BACKUP_DIRECTORY` before proceeding.

Restore only into an isolated empty test/staging database. Set distinct non-secret `MADAR_SOURCE_DATABASE_ID` and `MADAR_RESTORE_DATABASE_ID` values, the `MADAR_RESTORE_PG*` connection variables, all `MADAR_RESTORE_*_DIR` paths, and `MADAR_RESTORE_CONFIRM_ISOLATED=YES`. Run `scripts/restore_madar.sh --dry-run BACKUP_DIRECTORY`, then the real command. After restore, run migration validation, database/RLS verification, file-count sampling, checksum sampling, authenticated/private-file access tests, and application readiness against the isolated target. Never point the restore command at production or a shared database.

Rollback decision: if a backwards-compatible application defect occurs, redeploy the recorded prior image. If a migration has started, stop writes, assess whether the migration is forward-fixable, and prefer a reviewed forward repair. Restore from the pre-migration backup only for confirmed destructive/corrupting changes and only with incident-command approval, an accepted data-loss window, and a rehearsed isolated restore. Never improvise down-migrations on production.

Run a quarterly isolated restore drill. Record date, backup ID, source commit, restore target, dump and file verification results, elapsed time, observed data loss window, failed checks, owners, and follow-up actions. A drill is complete only when an application instance passes readiness and representative tenant-isolation and private-artifact checks against the restored copy.


## Automated isolated logical recovery rehearsal

`python3 web/scripts/rehearse_backup.py /absolute/verified/backup --postgres-image
supabase/postgres@sha256:<reviewed-image-digest>` creates a uniquely named,
network-disabled, non-root PostgreSQL container with bounded CPU, memory,
processes and tmpfs data. It restores the complete dump with fail-on-error and
one transaction, verifies schema and index metadata, copies all four file sets
into private disposable storage, checks every copied file, and removes only its
own target. Use an image with all source extensions, including `supabase_vault`
for managed Supabase backups; plain PostgreSQL is insufficient for those dumps.
The invoking user needs Docker access and read access to the backup. The
container runs as the image's named nobody account (65534:65534). A private
temporary dump copy permits non-root reads without changing backup permissions.
That copy is removed after the rehearsal. No database credentials are inherited.

An optional `--migration /absolute/regular/file.sql` applies only inside this
new disposable target. Verify its canonical filename and pinned manifest first.
Missing paths, directories and symlinks fail before Docker runs. Explicit
read-only `--mount` arguments never let Docker create a directory for a missing
SQL source. This prevents the September 1 ad-hoc rehearsal's `/migration.sql`
file-versus-directory failure.

The result proves logical database/file recovery. It does not prove a complete
Supabase replacement platform: dumps omit cluster roles, ACLs and ownership,
and Vault/application encryption keys and provider configuration require
separate escrow. The harness's NOLOGIN API role prerequisites are for replaying
stored policies only; run the RLS/grants verifier after the separately reviewed
authorization bootstrap and prove application readiness before accepting full
service recovery. Never suppress a full-restore failure by selecting only
`public` or `auth` schemas.
