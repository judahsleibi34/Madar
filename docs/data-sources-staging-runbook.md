# Data Sources schema155 staging runbook

This runbook covers a controlled, provider-independent, non-production staging
activation. It grants no authority to select a release, apply a migration, create
a remote bucket, start Vault, or mutate production. Migrations147–155 remain unselected.

## 1. Proven upgrade route

The selected release descriptor is `completed-normal-commercial144-146`, target
schema146. The reviewed route from that target to the Data Sources candidate is:

```text
146→147→148→149→150→151→152→153→154→155
```

The retained full-history rehearsal also proves the earlier governed route from136,
including the deliberate exclusion of schema142. Run these source gates before
requesting staging authority:

```bash
python3 web/scripts/check_migrations.py
python3 web/scripts/check_migration_transitions.py
python3 web/scripts/check_forward_release.py
python3 web/scripts/check_data_sources_staging_chain.py
bash web/scripts/rehearse_data_sources_upgrade_136_155.sh
bash web/scripts/rehearse_vault_transit.sh
```

The last command uses only a disposable PostgreSQL container. It proves a historical
schema136 dump can be restored, applies the entire route through the active146 base,
then the candidate chain, injects a transactional failure in
migrations154 and155, verifies rollback and locking, then reaches155. The Vault command
uses only a digest-pinned disposable dev container and synthetic credentials. Neither
command selects a release or installs a persistent service.

## 2. Environment and storage prerequisites

Use a staging-only Supabase project and service credential. Never copy production
credentials into a rehearsal. Required server-side configuration includes the normal
authenticated runtime contract plus:

```text
APP_ENV=staging
SUPABASE_URL=<staging URL>
SUPABASE_SERVICE_KEY=<secret; server and worker only>
DATA_IMMUTABLE_STORAGE_BACKEND=supabase
DATA_CHECKPOINT_SCRATCH_DIR=/var/lib/madar/checkpoint-scratch
DATA_CHECKPOINT_SCRATCH_MAX_BYTES=1073741824
STORAGE_DISK_FREE_FLOOR_BYTES=<reviewed host floor>
SCHEMA_COMPATIBLE_MIN=<selected bridge minimum>
SCHEMA_COMPATIBLE_MAX=<selected bridge maximum>
```

Create `madar-data-immutable` manually in the staging Supabase project only after
separate authorization. It must be private, must reject anonymous/authenticated
client access, and must be reachable with the staging service role. Apply a
100 MiB per-object ceiling. Object keys are server-generated beneath
`tenant_<tenant id>/...`; clients must never choose or receive provider object keys.

Before migration154, test with synthetic bytes: upload, repeat the identical upload,
stream it to a different process, verify exact byte length and SHA-256, deny another
tenant, simulate timeout/truncation/corruption, and confirm accounting precedes
metadata publication. Attempted deletion of a referenced object must fail. Exercise
an ambiguous response and reconcile from durable reservation/object evidence. Record
bucket policy and test output without recording keys or payloads. The local equivalent
is `python3 web/scripts/rehearse_shared_object_storage.py`; it is not evidence about
real provider latency or policy.

Legacy local spreadsheet/version files remain readable. Do not bulk-migrate them.
Any copy-to-shared-storage project needs a separate inventory, copy/hash verification,
reopen test, rollback plan, and customer-data approval.

## 3. Backup, migration, and application order

1. Confirm exact active release and database schema146; reject any excluded or
   unexpected schema state.
2. Stop Data Sources writers and all three candidate timers. Data Logs is not part
   of this operation.
3. Take a fresh coordinated database backup and independently restore it. Record the
   dump digest and prove the restored `core` contract is146.
4. Re-run every checksum, mirror, transition, forward-release, and full-chain gate
   against the exact staging source package.
5. Select a reviewed compatibility bridge only under separate release authorization.
   Do not run the SQL directly from this document.
6. Apply the approved manifests in the route above under the existing migration lock.
   Check the `core` version after every transition; on failure keep writers stopped,
   preserve executor evidence, and forward-repair or restore only under the release
   policy. Never skip a failed migration.
7. At154 verify the private bucket and shared backend from every app/worker host before
   accepting new incremental history or checkpoints.
8. At155 verify the independently installed, TLS-authenticated, unsealed Vault service,
   least-privilege application identity, audit device, coordinated backups, token
   renewal/revocation, and synthetic provision/rotate/rewrap/revoke failure matrix.
9. Start the application, then the reconciliation timer, checkpoint timer, and scratch
   cleanup timer. Enable one at a time and inspect its first result.

## 4. Worker operation

Source-only units are in `web/deployment/systemd/`:

- `madar-source-ingestion-reconcile.{service,timer}`: one bounded 20-run batch,
  five-minute cadence, 15-minute timeout, 512 MiB memory cap, singleton file lock.
- `madar-dataset-checkpoint-worker.{service,timer}`: one bounded five-job batch,
  one-minute cadence, 30-minute timeout, 1536 MiB cap, singleton file lock.
- `madar-checkpoint-scratch-cleanup.{service,timer}`: removes only stale
  `checkpoint-*` directories beneath the configured root, hourly, 128 MiB cap.

The scratch directory must be owned by `madar`, mode0700, quota-limited, and on an
encrypted-at-rest filesystem. The service account must not have a shell or access to
other application data. Multiple hosts may run database-fenced workers, but each host
retains its local singleton lock. Leases and heartbeats are database-owned; stale
tokens cannot publish. Ambiguous jobs remain visible for operator review rather than
being inferred failed. A non-zero unit result triggers `madar-ops-alert@`; inspect
bounded JSON output and database status without logging records, credentials, object
keys, or exception bodies.

Rollback means disable the candidate timers first, let active leases expire or
terminate workers cleanly, retain ambiguous artifacts/evidence, and return application
traffic only to an image compatible with the observed schema. Expand migrations are
not automatically reversed.

## 5. Acceptance workflow and failure matrix

With synthetic tenants, users, and projects only, prove: authenticated tenant/project
resolution; Data Source and API-resource registration; initial ingestion; incremental
insert/update/delete; current-state correctness; immutable changes; checkpoint request;
materialization in a separate process; private shared artifact; exact-version reopen;
deterministic `/analysis/assist` provenance; and cross-tenant/project denial. Verify
Data Logs files and routes have no diff attributable to the exercise. Raw records must
not be sent to an LLM.

Inject each of these before acceptance: database rollback, lost completion response,
provider timeout, worker termination, concurrent claim, duplicate provider ID,
repeated idempotency key, expired lease, stale token, corrupt/truncated object, quota
release failure, reconstruction error, missing-schema fallback, and cross-scope read.
No partial version may be visible and no failed/ambiguous checkpoint may be `ready`.

Alert for any ambiguous job immediately; for repeated worker failures; for an oldest
pending age greater than two lease periods; for scratch usage above 80% of its quota;
for disk free space approaching `STORAGE_DISK_FREE_FLOOR_BYTES`; for any hash/size
mismatch; and for any bucket-policy or schema-compatibility failure. Backlog thresholds
must be set after measuring staging throughput, not guessed from local fixtures.

## 6. Local measurements and acceptance criteria

The local benchmark is `python3 web/scripts/benchmark_checkpoint_reconstruction.py`.
On 2026-10-20 in the locked backend image it measured:

| Records/events | Reconstruction | Records/s | Python peak | Process RSS | Scratch bytes |
|---:|---:|---:|---:|---:|---:|
| 10,000 | 0.811 s | 12,327.84 | 1,423,296 | 416,931,840 | 940,891 |
| 50,000 | 4.076 s | 12,266.16 | 1,429,587 | 417,206,272 | 4,821,851 |
| 100,000 | 8.273 s | 12,087.71 | 1,435,435 | 417,107,968 | 9,674,077 |

These are simulated in-process database pages and local temporary disk, not PostgreSQL,
network, Supabase, or production-capacity results. The separate 10,000-record bounded
normalization benchmark measured 0.800 s, 12,497 records/s, 17,203,421 Python bytes,
and a 1,547,875-byte change chunk. Real staging must separately record PostgreSQL CPU,
locks, I/O, storage upload/download latency, queue latency, quota growth, and process
RSS at all approved sizes. Current checkpoint safety limits are 100,000 current records,
1,000,000 changes, 100 MiB output, and 1 GiB default scratch. Do not claim million-row
capacity.

Staging passes only when the exact full chain and restore rehearse successfully; all
release and regression gates pass; the real private bucket matrix passes; workers run
and restart under supervision; the synthetic end-to-end and failure matrix pass; Data
Logs remains unchanged; and monitoring/rollback evidence is reviewed. Production still
requires a separate exact-source approval, backup, real-provider staging evidence, and
release selection.

## 7. C2 local HTTP and credential acceptance

The C2 source candidate implements the generic transport described in
`docs/data-sources-api-connectivity.md`, but registers only an exact-test loopback
fixture. Run its fixture/security tests in the locked backend environment. Do not set
`MADAR_TEST_HTTP_PROVIDER_URL` in staging or production; a local fixture is not
real-provider evidence. Schema155 and the Vault Transit boundary now provide the
candidate encrypted tenant/source-scoped service, but remain unselected and do not
authorize a real destination. The hardened template requires a separate installation
review, manual Shamir unseal procedure, Vault Agent bootstrap, protected audit and
Raft filesystems, and coordinated encrypted backups.

Schema156 now provides an unselected one-shot scheduler candidate using the existing
leases and fences. OAuth, webhooks, and named providers remain separate milestones and
require their own replay, signature, revocation, and incident tests.

## 8. C3 automatic synchronization candidate

Schema156 adds a disabled-by-default schedule per existing API source resource. The
one-shot `run_automatic_source_sync.py` dispatcher claims a bounded batch in
PostgreSQL, executes through the existing fenced incremental ingestion path, and
enqueues an exact-revision checkpoint after a successful commit. Its timer uses
`Persistent=false`, so downtime cannot create an unbounded catch-up burst; successful
and failed attempts calculate one next eligible run from the current database time.

Do not install or enable `madar-automatic-source-sync.timer` during source review.
Before staging enablement, rehearse the combined Vault, PostgreSQL, loopback HTTP,
immutable storage and checkpoint workflow; two-dispatcher claims; worker termination;
lost completion responses; 401/403, 429, 5xx and timeout handling; sealed Vault and
credential revocation; per-tenant/provider limits; and backlog behavior after a long
outage. Choose operational limits from measured staging throughput and provider terms.

## 9. C3 browser-to-worker local rehearsal

Run `bash web/scripts/rehearse_data_sources_browser_e2e.sh` only on a development
host with the locked backend image and frontend browser dependencies already present.
The script creates random loopback ports, a private Docker network, temporary Vault
Transit state, and a tmpfs PostgreSQL database. It first verifies the browser fallback
against a physical schema141 database, then applies the candidate 143–156 chain and
runs the authorized Data Sources onboarding, encrypted credential, schedule,
incremental synchronization, checkpoint, isolation, revocation, mobile, and Data Logs
checks. All provider data and credentials are synthetic; the fixture is available only
under `APP_ENV=test` and cannot select or activate a release.

The rehearsal is local acceptance evidence, not staging or production evidence. It
does not authorize a real provider, persistent timer, hosted endpoint, migration
selection, or production Vault configuration. Retain its screenshot artifact path and
test output with the review record, and investigate any cleanup or secret-redaction
failure before proceeding.
