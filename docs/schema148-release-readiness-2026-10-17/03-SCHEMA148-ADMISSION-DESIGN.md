# Exact coordinated admission

New profile5, completed-normal-schema146-148-coordinated-release, reuses the
existing completed-NORMAL coordinator. It is unselected and does not authorize
installation. Source and target are exactly146/148; the only SQL entries are
unchanged147 then148, with immutable mirrors/checksums. The new manifest uses
CURRENT for later exact source binding; the old candidates remain STAGING.

The ordinary automatic loader still refuses coordinated147. The distinct
admitted_manifest function requires the version5 profile, exact manifest digest,
checksum-valid source and fresh existing root-issued authorization. It constructs
the existing LockedMigrationExecutor with a mandatory migration guard; no second
privileged executable, SQL connection factory or authorization issuer is added.

The original upgrade/deploy locks, source provenance, image acceptance, history,
boot supersession, exclusive worker handoff, READ_ONLY authority, current-data
backup/restore/Node1 replica, preservation and append-only execution history
remain authoritative.146 and147 cannot receive NORMAL in the new range.148 needs
sealed SQL/preservation plus all existing completion gates. Root/controller
installation remains a future independently approved operation.

An exact-policy digest binds legacy consumer IDs/images. Root inspects all Docker
notification candidates (unknown images/code count as ambiguous), requires old
consumers stopped with restart=no, and uses the existing kernel to verify the
candidate READ_ONLY. Before backup and each SQL transition it checks native
cluster/schema, processing/expired rows, other active transactions, prepared
transactions and queue locks. Unknown or resurrected consumers refuse. Nothing
resets a delivery, infers provider acceptance or manufactures reconciliation.
The conservative inventory may block a host with unrelated notification code;
that must be resolved with reviewed ownership evidence, never by stopping it.

A new boot proxy gate sorts after the observed146 gate. Missing sealed migration
completion at147 keeps READ_ONLY/maintenance and never calls the old origin actor.
Post147 rollback cannot restore unfenced workers or grants. A consumed executor
journal cannot be silently retried; fresh forward resumption uses the existing
separate authorization and a new immutable executor scope. The database, not an
outdated journal's observed_schema field, determines committed progress.

Production current-data rehearsal, accepted fresh images, complete consumer/host
inventory, exact-source CI and independent approval remain required. Synthetic
native SQL and transport-fixture controller tests are scoped evidence, not full
privileged deployment/reboot acceptance.

Fresh-artifact acceptance additionally authenticates the exact-source GitHub
workflow run and artifact ID/name/attempt/digest, strictly bounded ZIP inventory,
image archive hashes, immutable image IDs and six Dockerfile/dependency-lock
inputs. It requeries latest exact-application Backend Check and Frontend Check
runs independently of artifact-build success. A later failed/running check blocks
admission. Source overlays cannot satisfy this gate. Artifact expiry after seven
days requires a fresh accepted build; retaining bytes does not renew approval.

The optional reviewed unrelated-consumer policy now checks target-native signing
authority and live PostgREST responses plus measured spec/image identity. Manual
host workers and unavailable positive PID visibility block admission. No production
policy was generated or supervisor stopped. The new profile's preservation scope
includes all Auth/Storage tables; historical profile scopes remain unchanged.

The fresh build proves exact accepted artifact identity and locked source inputs,
not bit-for-bit reproducibility across rebuild timestamps/engines. The first
actual cross-engine import demonstrated why configuration and OCI manifest IDs
must be recorded separately. The corrected producer validates both blobs and
selects the native containerd manifest identity before publication. Other archive
layouts/ambiguous multi-platform inventories fail closed pending reviewed support.
