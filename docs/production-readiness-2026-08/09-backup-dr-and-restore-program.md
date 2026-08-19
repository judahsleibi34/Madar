# Backup, disaster recovery, and restore program

## Recovery architecture

Use at least two rotating encrypted drives. Drive A may be attached only for a scheduled backup and verification; Drive B is normally disconnected and preferably stored at another physical location. Rotation and custody are logged. Node B can validate restores but is never the sole backup.

```text
consistent source capture -> hidden staging generation -> checksums/manifest
 -> client-side encryption -> drive A/B generation -> verify from destination
 -> atomic success marker -> disconnect/custody -> isolated restore drill
```

Encryption keys are escrowed separately from nodes/drives, with two-person break-glass access and a tested recovery copy. A host compromise must not be able to delete all generations. Do not place plaintext `.env` on a drive.

## Coverage

| System | Capture | Required restore proof |
|---|---|---|
| Madar | provider-compatible DB plus builder/private/generated/avatar assets, registry/metadata, schema state | Supabase Auth/PostgREST/Storage/Vault-compatible target, tenant counts, auth, asset reconciliation |
| Briefedly | logical custom dump now; evaluate base backup/WAL after RPO approval | production-revision restore, migration, least-privilege runtime, aggregate consistency |
| Mailcow | supported all-component backup/cold standby: MariaDB, vmail, crypt, Redis where required, Rspamd/Postfix, config/custom changes, DKIM/TLS | isolated initialized Mailcow, mailbox counts, crypt/DKIM identity, service and mail-flow tests |
| host/config | Compose, systemd, deploy tooling, Git SHAs/image digests/SBOM, firewall/SSH evidence, package inventory | empty-host rebuild without copying undocumented state |
| providers | Cloudflare/Tailscale/Supabase/Google reprovision metadata and encrypted secret escrow | revoke/reissue/re-enroll tabletop and selected safe drills |

## Backup generation contract

Every successful generation records timestamp, source host, dataset categories, aggregate counts/sizes, SHA-256 tree/root, encryption key ID, DB/schema revisions, Git/image identity, tool version, destination drive/object ID, verification, and success. No customer content or secret values in logs/manifests.

Madar backup format 2 now builds under a hidden `.incomplete` path, checksums content including `BACKUP_COMPLETE`, verifies it, and atomically renames to the final generation. Failed staging directories are never “latest good”; operators inspect and remove them only through a separately reviewed retention action.

## Retention and prune safety

Recommendation pending capacity/RPO approval: 7 daily, 5 weekly, 12 monthly generations across rotations, with at least one known-good on each drive. More frequent DB captures may be necessary. Prune only after a new generation and restore sample pass; never prune both copies in one operation; prune identity cannot overwrite/delete the disconnected copy.

## PostgreSQL strategy

### Briefedly

- Logical custom dumps are adequate for schema portability and current small volume but set RPO only at dump frequency.
- Add encrypted physical base backup + WAL archiving/PITR only after archive destination, monitoring, retention, restore tooling, and timeline drill exist.
- A standby improves availability, not backup integrity, because corruption/deletion can replicate. With two nodes, Mailcow/SaaS isolation is higher priority than an unmonitored hot replica.
- Recommended staged target: 6-hourly logical dumps initially; then evaluate daily base backup plus continuous WAL if approved RPO is materially below six hours.

### Madar/Supabase

A public-schema dump is not full recovery. Obtain provider-supported backup/export/PITR and restore semantics for Auth, internal schemas, Storage metadata/objects, PostgREST, Vault, roles, extensions, and keys. Rehearse on a compatible project/target; document which provider settings are recreated rather than restored.

## Mailcow execution gate

Installed version is tag `2026-05c` with pre-existing custom changes. Official Mailcow documentation retrieved 2026-08-19 supports `helper-scripts/backup_and_restore.sh`, initialized-empty-host restore, and a cold-standby script using `mariabackup` for consistent SQL. The cold-standby script uses `rsync --delete` and has no versioning, so its destination must be snapshotted/versioned and never be the only copy. References: [cold standby](https://docs.mailcow.email/backup_restore/b_n_r-coldstandby/), [restore](https://docs.mailcow.email/backup_restore/b_n_r-restore/), [export options](https://docs.mailcow.email/backup_restore/b_n_r-backup-export/).

Inspect/pin helper image/tool behavior, protect credentials from process arguments, preserve dirty custom configuration, and execute in an approved window. No Mailcow backup runs in this phase.

## Drill cadence and measurements

- Monthly DB-only restore for both applications.
- Quarterly application restore including files, roles, queues, auth/provider stubs, and representative metadata.
- Twice-yearly replacement-host drill, plus after major architecture/schema change.
- Mailcow quarterly isolated restore once procedure is certified.
- Measure actual oldest recoverable timestamp (RPO) and elapsed decision-to-service time (RTO); recommendations are not commitments.

## Failure detection

Backup job exits non-zero on capture, checksum, encryption, transfer, destination verification, or success-marker failure. Monitor last local success, last physically separate copy, last disconnected/off-site rotation, and last successful restore drill independently. A fresh local backup must not mask a stale off-site copy.

Status: local Madar/Briefedly captures and partial restores exist; physically separate copies, Mailcow recovery, full Supabase recovery, schedule, and alerts remain `BLOCKED BY HARDWARE`/`BLOCKED BY P0`.
