# Automatic full-provider staging

The new `Full Provider Staging` workflow runs on every PR and main push, with
contents/actions read permissions, pinned checkout/upload Actions and no stored
checkout credential. It downloads only the latest successful exact-source
backend,frontend,migration-safety and fresh-artifact runs. CI source advancement,
failed latest runs,expired/mismatched archives and changed image inputs refuse.
No production secret, environment or dispatch endpoint is available to this job.

`web/staging/integration/full_provider_staging.py` regenerates its plan from
immutable Git source/history and captured mirrored migration bytes. Its fresh
synthetic genesis fixture is separate from current-data migration and recovery
rehearsals. Provider roles,JWT/passwords,TLS,Auth/MFA identities,tenant data and
objects are generated per attempt. No old operational Compose/dotenv or customer
archive is copied. The retained pinned configuration validator now accepts a
numeric target schema as data; historical150 defaults and strict bounds remain.

The only hosts are the identified staging VM or an ephemeral GitHub-hosted runner;
physical production-sensitive hosts explicitly refuse. A single private lease,
source-derived owned namespace,unused loopback ports,absent project resources,
8GiB disk and2.2GiB memory headroom precede effects. Database/admin ports are not
published. Docker resources have fixed labels,images,CPU/RAM/PID/logging bounds,
private networks,read-only application files and restart=no. No source overlay
is allowed. A consumed artifact capture or runtime cannot be adopted or replayed.

Native providers bootstrap their own schemas. The runner stops them and drains
all client sessions/prepared transactions before application SQL. It initializes
an explicitly fresh database to the immutable base target,then applies any planned
forward bytes with bounded lock/statement timeouts and post-commit observation.
This is not restoration or proof of the protected146→150 maintenance operation.

Before application/workers start,the actual database must expose the required
three protocol2 functions. The existing published150 function returns0 at151,so
that future source correctly refuses here. The user selected retaining150 as the
release target;no successor migration or synthetic protocol marker was added.
Destructive ClassD plans cannot use this automatic staging path.

Acceptance reuses actual Auth/MFA/AAL2/refresh/CSRF,Storage/anonymous denial,
notification intent/replay/delivery,tenant read/write isolation,readiness and
synthetic user/tenant deletion probes. Deletion must complete through a consuming
worker,remove native identities/objects,preserve a foreign tenant and survive
worker restart. All11 services and exact image identities must be present.
Only sanitized results are uploaded. Private credentials/journals remain private.
The owned stack stops after acceptance;volumes and private failure state remain.

Source/model validation is not native acceptance. Actual execution results and
exact-source CI links are recorded in the final report after the workflow runs.
The runner issues no authority and leaves schema150 protected admission and
production automation blocked. Browser/product coverage,independent restore,
privileged handoff/reboot and object-aware PITR remain separate gates.


PhaseIX full-provider CI requires the accepted native OCI manifest identities;
it never substitutes build-host configuration IDs after import. A reproduced
classic-store refusal led to explicit empty-daemon containerd-store preparation
only on disposable GitHub runners,with a root-private original configuration
preimage and failure restoration. Physical nodes and the shared staging VM
refuse that preparation. Remaining mutable checkout/setup-node Actions are
pinned to their officially observed commit IDs. Selected native browser checks
use locked dependencies,a synthetic private fixture and verified loopback/source
identity. Bounded progress and sanitized failure reports contain no credentials,
exception messages or raw provider logs;completed evidence follows observed
owned-service shutdown. These CI privileges are not release authority.

A native019b attempt completed Auth/MFA/Storage/notifications/tenant checks and
the authoritative user/tenant deletion assertions,but failed at the supervisor's
project-wide restart wait. That FAIL is retained. Restart now uses the same
supervisor's plain start,then independently binds the stopped/current container,
source labels,image,live database protocols,starting-only bounded health and
consumption. Changed,exited,unhealthy or nonconsuming workers fail immediately.
Final acceptance additionally rejects any unhealthy required component. This
does not infer an unsupported Compose flag without evidence;see the official
[Compose start semantics](https://docs.docker.com/reference/cli/docker/compose/start/).
