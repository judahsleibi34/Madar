# Exact checkpoint: independently executed component recovery

Both Node 2 and Node 1 checksum commands completed with exit code 0 and fourteen successful comparisons: thirteen components plus the sealed manifest. Manifest SHA-256 remains `4c3fe669e4c00e3e8221e8db304d55d5a463d6e3e53cfb0209320b3a8bb0feeb`. Neither original backup was changed, supplemented or relabelled. No additional checkpoint was captured.

Node 2 source: `/var/lib/madar-control-plane/normal-local-preparation/checkpoint-20261008T224529Z`.
Node 1 source: `/srv/data2/madar-backups/normal-local-preparation/checkpoint-20261008T224529Z`.

Actual frozen-source executions, retained separately from this summary:

- Two-node checksum record: `.incident-response/normal-production-2026-10-09/actual-two-node-14-file-checksums.json`, SHA-256 `e18f056e21e966a9040f1d44b8a106057ad8c4a16e93bf64cadaaf4e67f4fa62`.
- Node 2 component restore, exit 0, finished 00:18:06 UTC: `actual-coordinated-component-restore-20261009T001806Z.json`, SHA-256 `5f58b5b4e52c04922fcfc8d73e440592a606387151d117d0f575542b0f60ff00` in that directory.
- Independently retrieved Node 1 replica and new database restore, exit 0, finished 00:23:37 UTC: `actual-node1-component-restore-20261009T002337Z.json`, SHA-256 `3f63df60d86bcdf958fe78e734724dd949834c4d9f933cacd2e7f1810435c5fa` in that directory.

The off-host execution read all fourteen existing replica files through the approved SSH alias, verified every received SHA-256 and independently compared every archive entry against recovered quarantine bytes. It restored the received database anew in a disposable networkless PostgreSQL. Node 1 received no writes. The replica is online and unencrypted; no decryption or private SSH key export was needed.

Both executions restored schema115 with original database ownership, object owners and ACLs, eighteen Auth users, eighteen identities, two MFA factors and zero invalid indexes. Saved role attributes/password verifiers and original membership grantors matched independent read-only source queries. PostgreSQL's original `supabase_admin` bootstrap identity was preserved. Cron job launching was disabled and pg_net targeted an absent database throughout the isolated restore. No production database was restored or modified.

All archive bytes were verified, including 129,521 controller files and 58 internal hardlinks materialized as independent files. Restored controller/configuration bytes were never executed or activated. Forty-one recorded image identities were available locally. This does not prove their availability on a bare disaster-recovery host.

The native tar archive omits filesystem extended attributes. This gap was resolved without inventing metadata: the restored database contains the content-type/cache-control values for all 235 objects. All 470 files, including retained duplicate versions, have identical corresponding object payloads. The exact restored database metadata recovered all 940 attributes into a NEW private quarantine, with independent byte/attribute comparison against the restricted source. Original storage and both backup manifests were unchanged. The manifest's `restore_verified:false` flag remains unchanged.

Scope: VERIFIED coordinated component recovery and verified off-host retrieval/restore applicability for those components. Full private Supabase/application runtime, asset delivery, tenant isolation and accepted normal-source/image behavior still require their own genuine execution. These component results do not satisfy those separate gates, issue authorization, or justify a writable cutover. No crash-durability, physically immutable/offline backup or normal-production PASS is claimed.

Earlier failed execution records and quarantines remain preserved. Archive extraction performance, image inspection output overhead and exact PostgreSQL bootstrap/grantor handling were corrected in development; no disputed historical PASS record was consumed. The current emergency installation remains functioning. A fresh exact normal-production authorization is still required before controller/routing/worker/write changes.

Fresh-input inspection found canonical `/var/lib/madar/releases` and proxy state
under the existing madar-owned runtime hierarchy. Some records themselves are
root-owned, but their parents permit the runtime operator to replace them. Their
bytes may therefore be pinned as observed inputs to a NEW root-approved plan;
they are not independently protected authorization or execution evidence. The
new continuation authorization, append-only journal and positive business-write
authority require an entirely root-owned hierarchy. No permissions or existing
records were changed to resolve this distinction.


On 2026-10-09 at 01:50:40 UTC, independently executed frozen source restored the
exact received Node 1 database again and started only four new isolated native
services. Execution `actual-private-native-restore-20261009T015041Z.json` exited
0. It verified all 235 authenticated storage objects (177,589,668 payload bytes),
235 range reads, original MIME/cache metadata, password authentication and MFA
TOTP/AAL2 using a disposable test identity removed before completion. The source
inventory was reverified. No original checkpoint or production data was changed.
The preceding failed connection-at-startup execution is retained separately; a
bounded storage-activation check resolved that failure, with 55 focused unit
regressions passing. This proves native core recovery, not full eleven-service
platform recovery or current normal-source application/tenant acceptance. Those
separate gates remain required before normal authorization.


A NEW root-protected execution completed at 02:10:38 UTC, retained in
`/var/lib/madar-control-plane/normal-local-preparation/native-restore-execution-7qk3iqoh`.
Its `execution.json` SHA-256 is
`1879d81b38146f365110fd9bc6bf753afaa2a43d169cb060ae67695183db2c5f`.
All record files are root-owned mode0600 under the private hierarchy. The actual
supervisor retained its frozen source inventory, raw stdout/stderr, six full
archive byte-verification results and another current read-only fourteen-file
Node 1 checksum inventory, before retaining the actual child exit0. The private
child restored original owners/ACLs and compared role attributes, password
verifiers and grantors against a BEGIN READ ONLY source query. It verified
postgres database ownership, zero invalid indexes, eighteen identities/two
original factors, all235 native assets/headers/ranges and disposable password/MFA
AAL2 authentication. No original backup, production database or evidence changed.
A separate new frozen validator completed with exit0 and checked those bindings.
The record remains explicitly native-core/data recovery, without normal-source
application, tenant, full eleven-service or bare-host acceptance claims. It is
not a recreated historical authorization or a new write permission.

An additional actual private restore exercised both original verified TOTP factors
through password login, challenge and JWT AAL2 verification. Record:
`/var/lib/madar-control-plane/normal-local-preparation/existing-mfa-runner-emk5jg74/actual-execution.json`,
SHA-256 `a48becd2235ceef0b36d8fefa4c0dc383b256570b40d589c3f6a7f5163171e07`,
actual execution exit0, 2026-10-09 03:02:09–03:02:34 UTC. Known disposable
passwords were used only in the private restored accounts; each original password
verifier was restored there afterward. Customer passwords were neither requested
nor used, and no production authentication or customer-data mutation occurred.
This proves existing-factor recovery compatibility, not current-source backend
application acceptance or a real customer entering their password.

A separate current-local read-only reconciliation executed successfully at
03:28:23 UTC, retaining all96 public-table count/SHA-256 roots under a repeatable
read-only PostgreSQL snapshot with schema115. Protected actual execution record:
`/var/lib/madar-control-plane/normal-local-preparation/local-reconciliation-runner-fx_e0aha/actual-execution.json`,
SHA-256 `78036de13840bb3e088ec29f92ddd4db74c81f95d6f2dac0271aeed1f7af2708`.
Snapshot SHA-256 `57dcb02015858928b1eaf3b1dcbfe344a550ce0e4ef25c703cd2bf78df4e07e9`.
Writes remained disabled and no migration, database restore or consumer startup
occurred. This is current-data observation, not cutover authorization.


At 04:47:28 UTC, a new frozen root-private read-only validator independently
checked the original-factor and current-local-reconciliation execution records.
The retained validation is
`/var/lib/madar-control-plane/normal-local-preparation/actual-evidence-validation-_xrgpf90/validation.json`.
The actual subprocess exit was 0 with empty stderr. Validation bound each record
to its original SHA-256, isolated argv, immutable executed source inventory,
actual execution timestamps and retained JSON Lines transcript. The failed
preceding validator is preserved separately; its fixed-source-layout mismatch
was corrected in development without changing either original execution record.
The results prove two original factors in the private restore and a schema115
read-only snapshot of 96 public tables. They expressly do not prove current
application acceptance, a durable source fence or normal-production authority.
