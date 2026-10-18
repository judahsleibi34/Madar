# Concrete provider adapter: review boundary

The new `schema150_provider_adapter.py` supplies fixed Docker, systemd, internal
SQL and private HTTP effects to `ProviderMaintenance150`. It has no executable
entrypoint, issuer, arbitrary command argument or alternative migration executor.
The schema150 profile and `admitted_manifest` remain deliberately closed. This
is reviewable implementation progress, **not complete operational admission**.

## Implemented source

Every effect requires the existing fresh operation credential, exact source
measurement, exact operation/cluster/inventory binding, and actual held upgrade
and deployment flocks. It never acquires missing coordinator locks. Root-private
inventory and journals are re-read. The adapter refuses all unrelated-container
exclusion references until independent live proofs are implemented.

Positive probes precede fencing. The three native provider URIs must identify
the measured database on its actual shared network with their exact roles.
Duplicate aliases, custom DNS/hosts resolution, URI overrides and foreign
cluster identities fail closed. Service/anonymous/invalid-token HTTP probes
remain separate positive and negative scope checks. No URI/token is logged.
See `provider-database-binding-review.md` for the reproduced resolver-override
failure and corrected tests.

Original full PostgreSQL role attributes, memberships and private roles-only DDL
are captured before effects; temporary NOLOGIN state cannot replace the original
restoration contract. A persistent root-private barrier is created before
systemd drop-ins or container mutations. Effective drop-ins and structured D-Bus
conditions must contain the exact non-triggering **negative** ConditionPathExists
for this operation. Substrings, wrong polarity and trigger conditions are
rejected. Native staging read-only observation established the D-Bus shape;
actual barrier effects still require the privileged acceptance described below.

Effects disable restart and stop only exact measured IDs/specifications. Role
fencing uses a transaction. Existing sessions are observed independently;
NOLOGIN is never treated as disconnection. Surviving known sessions block after a
bounded wait; new/unknown sessions block immediately. The fixed existing host
consumer scan requires a positively visible live database PID and rejects
remaining recognized notification/deletion/calendar consumers at quiescence.
Broader dormant host writers remain an explicit inventory/registration gap.

## Object and backup preimages

`schema150_object_inventory.py` performs real descriptor-based filesystem reads.
Initial capture pins root/mount identity only. After queue, session and role
quiescence, the adapter captures actual bounded, two-pass object content into a
new exclusive private preservation record. The database directory is identity
only; database preservation belongs to the existing database contract. Subsequent
migration boundaries and pre-private role restoration compare that recorded
object preimage. A missing record after schema146 cannot be recreated.

Symlinks, nested mounts, hardlinks, special files, substitutions, observed races,
and oversized/unmeasurable trees fail closed. Fixed conservative limits are
128MiB/file,256MiB content,16,384 entries/root,depth32,60 seconds. This is neither
an atomic filesystem snapshot nor proof that writers are stopped. Volume roots
must be actual host mountpoints linked to measured mounts; completing that
production inventory linkage is still required.

`backup_role_archive` returns original authenticated private DDL only under the
maintenance checks. The ordinary backup/replica/independent-restore pipeline is
**not yet wired** to that archive. No backup success is claimed from this method.

## Private recovery and authority

At schema150, original role attributes can be restored before private native
providers start, while ingress and business workers remain stopped. Published
provider ports are rejected. Existing acceptance and activation boundaries must
supply independently verified database/provider/image/backup/boot evidence.
Those production delegates are **not implemented by a caller PASS flag** and are
not yet connected to the ordinary coordinator. Target authority is required
before candidate worker/ingress activation; the adapter never issues it. The
persistent boot barrier is cleared last. Consumed effects are reconciled through
observations; there is no blanket retry.

## Current evidence and missing integration

Component tests use synthetic Docker/systemd/SQL/positive-credential transports;
real temporary files, journal publication and kernel flocks are exercised. They
are MODEL/FILESYSTEM evidence, not native provider or complete privileged-system
acceptance. Independent tests exposed and retained regressions for initial fence
ordering, post-grant observation, incorrect effective conditions, and provider
resolver overrides. Native guest installation results are recorded separately.

Mandatory remaining engineering: sealed future-candidate publication extension,
exhaustive host/manual writer and alternate-supervisor inventory, authenticated
live exclusions, maintenance-aware ordinary backup/candidate/migration adapters,
private application acceptance, existing write-handoff wiring, boot/proxy recovery,
source inventory installation and full interrupted privileged execution. Keep the
profile unregistered while any of these remains unproven. Migrations001–150,
selected release descriptor and protected issuer are unchanged.

Further independent review reproduced three draft false-positive boundaries:
ambient libpq host-address overrides, active/pending supervisor reconciliation,
and automatic/effective private-provider port publication. Regressions now reject
those states, including secondary-network alias ambiguity. Every measured
supervisor must be inactive/dead with no queued job or main/control PID before
quiescence/private recovery. Private providers must have neither configured nor
effective host publication. These were corrected before operational registration;
no production execution or exploitation was performed.
