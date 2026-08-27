# Backup, restore and disaster recovery

## Ratings

| Capability | Rating | Evidence |
| --- | --- | --- |
| Backup readiness | **FAIL** | Valid local manual capture, but no schedule, freshness gate, off-host/encrypted copy, retention or alert |
| Restore readiness | **BLOCKED** | Historical partial public-schema/files restore passed; full Supabase platform restore requires a compatible/provider-supported target |
| Disaster-recovery readiness | **FAIL** | No replacement-host rebuild, secrets/config escrow proof, accepted RPO/RTO or traffic recovery drill |

## What is real

`scripts/backup_madar.sh` creates a PostgreSQL custom archive plus builder assets, private uploads, generated artifacts and avatars in a hidden staging directory, generates checksums and a completion marker, verifies and atomically renames. `verify_backup.sh` validates the format/manifest. `restore_madar.sh` requires an isolated confirmation, different source/target IDs and uses a single-transaction PostgreSQL restore.

The 2026-08-23 11:16 UTC local generation is complete, 87 MiB, mode `0700` with files `0600`; all 92 checksums pass and `pg_restore --list` sees 1,059 entries. It is a legitimate recovery point, likely created during deployment recovery.

## What is missing

- No Madar backup systemd timer or cron entry; readiness returns `backup_freshness: disabled`.
- No automated retention, disk-exhaustion alert or failure notification.
- No encryption step in the repository tool and no evidence the local destination is encrypted/off-host/immutable.
- Application `.env`, encrypted secret escrow, Cloudflare tunnel config, systemd units, installed deploy scripts, host package/network state and image digests are not captured by this generation.
- The logical dump includes provider-specific Supabase Vault/platform constructs. A prior raw PostgreSQL restore was blocked by `supabase_vault`; a reviewed partial restore excluding four provider objects restored 63 public tables/files and matched checksums, but did not restore Supabase Auth/PostgREST/Storage/Vault as a working service.
- No application instance passed auth, private asset and tenant tests against a fully compatible restored target.
- Runbook explicitly says RPO and RTO await operator approval. A quarterly drill is prescribed but not fully accomplished.

## Required proof

Schedule and monitor backups; keep at least one encrypted off-host generation outside host credentials; include configuration/reprovision manifests; set and approve RPO/RTO; test retention safely. Restore the latest generation into an isolated provider-compatible target, rebuild a clean host from Git/images/config escrow, pass schema/readiness/auth/two-tenant/private-file/worker checks, record elapsed RTO and oldest recoverable timestamp, then destroy the isolated target under approval.

The current snapshot reduces immediate loss risk but does not satisfy production recovery.
