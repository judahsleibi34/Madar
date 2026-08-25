# Backup and restoration preparation

## Local backup format

`web/scripts/backup_madar.sh` writes into a hidden incomplete directory under restrictive umask, creates a PostgreSQL custom-format dump, validates its TOC, archives configured storage, inventories configuration names without values, records release/build/database/schema identities, writes JSON and human manifests, generates SHA-256 checksums and writes `BACKUP_COMPLETE` last. Only then is the directory atomically renamed. A trap removes incomplete state.

`verify_backup.sh` requires format version 3, complete status, expected files, redacted configuration metadata, matching checksums and readable `pg_restore --list`. `verify_latest_backup.sh` additionally enforces freshness. Partial output cannot pass.

No production backup was generated or altered during remediation.

## Restoration sequence

Use an isolated replacement host/network:

1. Obtain the encryption identity/private key through the documented two-person custody process; never copy it into the repository.
2. Verify encrypted media identity and ciphertext checksum, decrypt to an access-controlled temporary filesystem, then run `verify_backup.sh` before restore.
3. Provision the recorded immutable release images or rebuild and digest-verify the recorded Git SHA. Install reviewed Compose/systemd/proxy configuration; reconstruct secrets from the separate credential inventory/manager.
4. Create an empty compatible PostgreSQL target, verify server/extension requirements, run `pg_restore --list`, restore roles/schema/data, apply only release-compatible forward migrations, and check `application_schema_state`.
5. Restore assets preserving restrictive ownership/modes. Verify every manifest-listed path and checksum. Do not restore over a running service.
6. Recreate Redis as ephemeral coordination/rate-limit state unless a future manifest explicitly declares durable Redis data. Start workers only after database/storage validation.
7. Recreate Cloudflare tunnel credentials/config from the separately secured provider account; the backup contains references/inventory, not secret values. Do not switch traffic yet.
8. Validate login/admin AAL2, two-tenant isolation, hostname/site/publication/chrome identity, public assets, ordinary forms and quiz attempts, reservations, analytics, notification channel states, workers, storage quota, backup freshness, audit logging and release identity.
9. Run a signed operator acceptance checklist, record RPO/RTO, then perform a separately approved traffic cutover.

Provider auth identities, OAuth/provider tokens, Cloudflare credentials and SMTP/VAPID material require independent secured custody. A database dump alone is not a complete service restore.

## Current classification

- Software preparation: **completed and tested in development**.
- Physical encrypted off-host copy: **BLOCKED ON PHYSICAL BACKUP DRIVES**.
- Full isolated replacement-host restore: **not yet proven**.

Off-host encrypted backup activation is externally blocked on arrival of the dedicated backup drives. The software path is prepared but is not production-validated until physical media and a restore drill are completed.
