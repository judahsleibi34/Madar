# Restore drill results

## Madar

### Full raw PostgreSQL attempt

Result: **blocked as expected** in a vanilla PostgreSQL 17 container because the production dump requires the provider-specific `supabase_vault` extension and vault schema. No production state was affected.

### Reviewed partial restore

A reviewed TOC excluded exactly four provider-specific vault entries: the vault schema, extension, extension comment, and vault secret data. A standard no-login `authenticated` role was created only inside the disposable clone so policy DDL could restore.

Result: **pass for public application schema and filesystem recovery**.

Verified by aggregate/metadata only:

- 63 public tables restored;
- expected RLS enabled on tenant, user, builder project, asset, form, reservation, storage, and notification-preference tables;
- 10 tenants, 10 users, 7 builder projects, 85 asset registry rows, and 95 storage-object rows;
- all backed-up builder, private-upload, generated-artifact, and avatar counts matched their restored directories;
- checksum manifest passed.

Limitation: the full Supabase Auth/PostgREST/Storage/Vault platform was not restored, so application startup against this raw clone is not a faithful full-service drill. Full Madar DR requires a compatible Supabase restore target or provider-supported recovery procedure.

## Briefedly

### Production clone

Result: **pass**.

- Production backup restored structurally.
- Starting revision reproduced as `d8c6b4a2f190`.
- Aggregate row counts matched production before and after migration.
- Five migrations upgraded the clone to `c8e5f1a3b647` in approximately 5.4 seconds.
- All 16 public tables were owned by `briefedly_owner` after role preparation/migration.

### Fresh rebuild

Result: **pass**.

- Empty PostgreSQL upgraded from zero to current head.
- Head downgraded to the production revision and upgraded forward again on an empty clone.
- Alembic rerun at head completed safely.

### Application/worker and role verification

Result: **pass in production-shaped configuration**.

- Backend became healthy using runtime credentials.
- Worker started and wrote its heartbeat; two retention jobs completed successfully.
- The manually launched worker preflight inherited the backend image’s HTTP healthcheck and therefore displayed unhealthy in Docker; actual production Compose already overrides this with the correct heartbeat-file healthcheck.
- Runtime CRUD passed and runtime DDL/admin operations failed.
- Migrator-only migration passed.
- Backup-role `pg_dump` and archive listing passed.

One initial backup-role test targeted `/dev/null`, which caused a filesystem synchronization error while a loose shell harness printed a success marker. The test was corrected and repeated to a real temporary file; the corrected run passed. Only the corrected run is accepted as evidence.

## Mailcow

No destructive/full restore drill was run. Required maintenance procedure:

1. record Mailcow version/commit and dirty custom configuration inventory;
2. pin/inspect the supported backup image/tool rather than accepting an unreviewed floating pull;
3. choose BACKUP_LOCATION with restrictive ownership and sufficient space;
4. run the supported consistency-aware backup during an approved window;
5. separately archive custom repository modifications, DKIM, TLS, cryptographic, and deployment configuration under encryption;
6. transfer and verify off-host;
7. restore to an isolated replacement host with no production MX traffic;
8. verify MariaDB, mailbox counts, crypt keys, DKIM identity, Redis-dependent state where required, and service startup;
9. only then document an effective Mailcow RPO/RTO.

## Replacement-host target

The recovery target remains: an empty replacement host rebuilt from Git/image identities, encrypted configuration escrow, systemd/Compose definitions, off-host backups, and documented provider re-provisioning. Current evidence does not yet meet that target.
