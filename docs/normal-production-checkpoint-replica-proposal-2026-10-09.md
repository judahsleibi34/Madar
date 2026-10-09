# Append-only Node 1 checkpoint replica: preparation approval

The approved new capture completed and an independent second measurement verified every component size and SHA-256. It has 13 components, 5,855,927,255 payload bytes, schema115, a sealed manifest and no restore PASS claim.

Exact plan SHA-256: `90a09eb357ec2ec35458400c0e88921d306224bd9e1a3ace3bcbd9e757a5f849`.

- `web/scripts/transfer_recovery_checkpoint.py`: `00a079a2abfa9b938393bb08e5e3f78657d089857534d94ea7b25bdf97e5cee8`
- `web/scripts/checkpoint_replica.py`: `0da2eae8bd95b46c571a3c82021c33e91e12f7adcb80bdbb9f3c9c3228642f19`

Execute only a root-owned frozen copy of these files using `python3 -I -B transfer_recovery_checkpoint.py <exact receiver SHA-256>`, after hash-checking this exact plan and both source files. The sender reads `/var/lib/madar-control-plane/normal-local-preparation/checkpoint-20261008T224529Z`, rechecks manifest `4c3fe669e4c00e3e8221e8db304d55d5a463d6e3e53cfb0209320b3a8bb0feeb` and every component, and streams this payload over the existing pinned SSH alias `madar-node1-lan` as user madar. No private SSH key material is displayed, exported or copied.

The receiver creates only `/srv/data2/madar-backups/normal-local-preparation/checkpoint-20261008T224529Z`, requiring filesystem UUID `aafa8641-ab59-4927-9146-c1f9bf9abf3f`, trusted ancestors, owner UID1000, private directories and regular file inventory. Before transfer, read-only inspection verified 923GB available and historical LATEST still pointing to the October8 11:01 checkpoint. The new namespace does not yet exist.

This is an **unencrypted online SSH replica**, not an offline or physically immutable backup. The approved capture payload includes customer database/role dumps, managed and native storage, native/production/recovery secrets, controller/protected records and image/schema/auth/ledger inventories. Explicit approval is required to transfer that exact sensitive payload to this new destination. The existing approved SSH connection previously covered read-only discovery; checkpoint capture approval explicitly excluded off-host transfer.

The receiver rejects links, traversal, special/sparse members, duplicate names, >64 files or >40GiB. It validates the full exact manifest inventory, seals files0400/directory0500, publishes using Linux RENAME_NOREPLACE, fsyncs the destination parent and independently hashes the published destination again. Its actual stdout is retained as transport/checksum evidence only, never as restore proof. Overall transfer watchdog: 1200 seconds.

No LATEST, freshness marker, retention, pruning, historical backup, configuration, production database/schema, routing, worker or write-authority change. On failure, retain the exclusively created `.checkpoint-20261008T224529Z.incomplete` directory; never overwrite it or repeat automatically. If publication completed but the SSH receipt was lost, discover and verify the exact existing destination read-only before any further action. No runtime rollback is required; public service continues unchanged. Full independent restore verification and the final writable cutover remain separately gated.
