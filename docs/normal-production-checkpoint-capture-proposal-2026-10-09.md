# New sealed recovery checkpoint: preparation approval

The historical Node 1 copy has the original 12 components, not the extended checkpoint. A full restore remains unproven. This operation captures a fresh snapshot and does not issue restore evidence.

Run only the two source files whose digests appear below, from a root-owned frozen private code snapshot with `python3 -I -B`. Invoke `capture_recovery_checkpoint.py /var/lib/madar-control-plane/normal-local-preparation/checkpoint-<UTC timestamp>`. The new namespace is root-owned mode 0700; the sealed snapshot uses directory mode 0500 and files mode 0400. No existing destination may be overwritten.

- `web/scripts/capture_recovery_checkpoint.py`: `07c686bf39872e78e15ada9f75755ac7453d8768c78810270dccbe39c517eff4`
- `web/deployment/lib/coordinated_checkpoint.py`: `4ef827caf5dae5bf8099cb237ba628f30f1d3dd4a63c3cecf5630d8148d951be`

Exact preparation plan SHA-256: `fd34ffec66558e03a4a39d15aca1b5f720a252cb0717013c6a608c12b3800d04`.

The secret-bearing payload includes the schema115 database and role dump, native storage and function cache, managed application files, native and production configuration, image inventories, schema/ledger/auth metadata, and existing controller/recovery/emergency state. This contains customer backup data and recovery secrets. It excludes SSH private keys. Payload bytes stay in the root-private backup namespace, outside Git; only sanitized execution metadata is retained in the development checkout.

The operation reads PostgreSQL using read-only transactions, verifies both active rollback transactions, all six stopped consumers, the public write fence and unchanged controller/routing/write-authority identities. It checks archive source bytes before and after capture. Overall capture deadline is 600 seconds. Application data uses one consistent pg_dump snapshot; cross-component full restore applicability requires subsequent independent verification, which this operation does not claim.

No routing, workers, schema, business permissions, historical backup/evidence, LATEST pointer, freshness marker, or retention policy changes. No off-host secret transfer is authorized by this plan. On failure, retain the new incomplete preparation directory; do not publish it or modify production. No runtime rollback is necessary because runtime is unchanged.

Automatic approval review rejected the earlier capture into the development workspace because the exact secret-bearing payload and destination were not explicitly authorized. This safer root-private proposal requires explicit approval for the listed payload and destination before execution. Normal writable cutover still requires its own reviewed operation and approval.
