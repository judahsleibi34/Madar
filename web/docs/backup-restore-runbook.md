# Backup, Restore, and Rollback Runbook

This runbook defines repository-supported logical backups. It does not claim that a production restore has been proven. Operators must approve concrete RPO and RTO values before launch: **RPO: pending operator approval**; **RTO: pending operator approval**.

Each new backup contains a PostgreSQL custom-format logical dump, local public uploads (the legacy `builder-assets` file-set name), private uploads, generated private artifacts, locally managed avatars, provider-object bytes/metadata, format metadata, and a SHA-256 manifest. Provider storage is separate from local uploads. The format-3 extension requires provider-object recovery by default and records `platform_recovery_proven=false`. Credentials never enter a backup or its logs.

Use `scripts/backup_madar.sh --dry-run` first. Set `MADAR_BACKUP_DIR`, standard libpq variables, and `MADAR_STORAGE_ROOT` (production: `/var/lib/madar/storage`). The four real source directories are `uploads`, `private_uploads`, `private_generated_charts`, and `avatar_uploads`; explicit per-set variables remain supported. Provide `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` for provider snapshots. A deliberately isolated local-only test may set `MADAR_PROVIDER_BACKUP_REQUIRED=false`; such a backup is not complete production recovery coverage. No source directories are created by backup tooling.

The scheduled service runs as `madar`, loads `/etc/madar/backup.env` and the canonical production path contract, and receives production provider settings through systemd `LoadCredential`. Its safe parser handles both equals and legacy colon assignments. Database dump validation, complete SHA256 coverage, provider inventory stability and object hashes must pass before a staging directory is renamed into its final backup ID. Provider changes require a fresh retry; there is no partial completion. The local `LATEST` marker and the separate nonsecret `/var/lib/madar/backup-state/latest.json` are atomically replaced only after verification. Creation time, not verifier run time, determines freshness.

Operational scripts and units are installed by the governed exact-SHA control-plane installer, with root ownership, source/hash checks and previous-file backups. Installation leaves scheduling disabled until a fresh backup and readiness are proven. Enable `madar-backup.timer` (02:15 UTC plus up to 15 minutes jitter), `madar-backup-verify.timer` (08:00/20:00 UTC), and `madar-node1-backup.timer` (04:45 UTC) after those gates. Each service retains the operations-alert failure hook. Local creation/retention and replication serialize on a private backup-root lock.

Recovery layers:

Every provider-inclusive backup also compares non-soft-deleted builder registry
hashes against the captured local/provider bytes. Missing active or referenced
assets and content mismatches fail closed. Historical unreferenced records whose
bytes were already absent are preserved in the database and disclosed by hashed
keys/counts in `builder_registry_coverage`; they are not silently called recovered
or deleted. The September 7 baseline contains four such July records with no
actual or published references and no matching retained backup bytes.

1. Local verified backup: private mode-0700 backup root.
2. Automated Node 1 online off-host copy: `replicate_latest_node1.py`, using strict noninteractive SSH through `madar-node1-lan`. This is online and mutable, not offline or immutable.
3. Existing age-encrypted removable/offline media: `replicate_latest_offhost.sh` and `replicate_backup_offhost.sh`, with the existing mount/volume identity gates. No connected removable media means this layer is not proven.

Node 1 configuration is `/etc/madar/node1-backup.env` (root-owned mode 0600), with `MADAR_NODE1_FILESYSTEM_UUID` set from the independently attested disk and optional `MADAR_NODE1_KEEP_COUNT=90`. The destination is fixed to `/srv/data2/madar-backups`; receiver validation requires `/dev/sdc1`, ext4, `/srv/data2`, the configured UUID, real path components, current-user ownership and private permissions. `/srv/data1` and `/srv/data2/docker` are outside scope. Remote copies use private staging, exact source SHA256 manifest comparison, exhaustive integrity verification and atomic publication. Reruns verify identical existing copies; conflicting content fails. SSH host checking remains strict. Timeouts, limited service retries, capacity reserve and failure alerts bound failures.

Conservative retention defaults are 30 local and 90 Node 1 managed copies, configured by `MADAR_BACKUP_KEEP_COUNT` and `MADAR_NODE1_KEEP_COUNT`. Minimum two; current/latest and the newest configured number of verified managed backups are always retained. Historical backups, incomplete paths, unknown entries and symlinks are not adopted or deleted. Deletion is confined to direct timestamp-named children with `retention_managed=true`, complete valid manifests and matching hashes, using symlink-resistant removal. There is currently ample capacity; monitor growth and adjust counts explicitly.

`restore_madar.sh` requires a new explicit `MADAR_RESTORE_PROVIDER_DIR` for provider-inclusive backups and reconstructs bytes/metadata locally without writing to the provider. The pinned-image networkless `rehearse_backup.py` independently restores the complete database, checks recorded schema/table count and invalid indexes, and reconstructs both local sets and provider data with hashes. This does not restore Supabase services, credentials, ACLs, Vault keys or prove platform readiness. Temporary copies are removed after verification.

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
