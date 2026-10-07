# Provider402 sign-in recovery

This profile is separate from ordinary deployment, automatic migration,
forward repair and schema recovery. Merely merging this source never activates
it. The installed controller guard continues to require privileged review.

`MADAR_RECOVERY_PROFILE=provider402-signin` selects an application-enforced
positive allowlist. All unreviewed routes, including GET/RPC routes, return 503
`provider_recovery_read_only`. Only existing-user Auth/session/MFA operations,
health/status, existing account/tenant/project reads and mediated assets are
admitted. Account lifecycle provisioning, implicit website-settings creation,
admin impersonation, signup, email reset, MFA enrollment/removal and uploads
remain unavailable. Existing tenant and AAL2 checks still run. SDK egress
additionally denies provider writes except reviewed session/security operations
inside the admitted Auth request context. No business table or RPC write is
approved. Workers refuse startup even when their normal enabled flag is true.

The recovery transaction in `web/deployment/lib/provider_recovery.py` requires
an independently collected, exact-SHA contract. Both hosted Auth and REST must
actually return 402; source schema must be 115. Unknown or unrelated readiness
failures stop recovery. Stale hosted-era backup freshness is permissible only
with a newly verified local checkpoint, without changing the old marker. Local
Auth/REST/Storage, image provenance, private network, loopback ports, linkage,
AAL2, isolation, write fence and a live local-compatible rollback runtime must
all validate before any mutation. Release schema and rollback ranges are
exactly 115, migration policy/class `none`, with no manifest key present.

The state machine owns deploy/runtime locks, writes a durable separate interlock
before candidate work, requires workers inhibited in both slots before traffic,
and writes explicit `RECOVERY` worker authority. Normal deployment and migration
credentials cannot take over this operation. Errors preserve the interlock and
select only the attested local rollback runtime. A process crash requires
operator diagnosis; there is no unattended retry or automatic recovery exit.

Rollback changes runtime/routing only and reuses the current local database and
Auth sessions. Never restore an old database checkpoint over sessions accepted
since recovery activation, and never use hosted HTTP as the fallback. Synthetic
test-account cleanup remains deferred.

## Activation boundary

The application fences and transaction library alone do not authorize a
production adapter or controller bootstrap installation. Production activation
must remain blocked until a protected adapter collects fresh evidence, binds
its one-time credential to this profile and rehearsal, prepares a live local
fallback without replacing serving production, and exercises the existing
protected traffic driver. Human exact-image login/MFA tests are also required.
A fake operations adapter or past human tests are not evidence for production
activation. No command should be improvised to bypass the installed guard.

## Protected infrastructure implementation

The fixed-path `madar-provider402-recovery` root launcher clears the caller
process environment and accepts only an operation plus the approved complete
contract digest. It cannot select an arbitrary Docker endpoint, shell driver,
production directory, credential or callback URL. Root-staged bootstrap code
must come from the existing trusted canonical-remote bundle staging and protected
filesystem preflight; running a caller-writable repository copy with sudo is
not the trusted installation procedure.

Preparation requires root-protected exact contract, verified local checkpoint
and exact-image rehearsal evidence including human Auth. It creates a separate
provider402 credential/interlock. Passive fallback registration precedes
installation. Installation then reuses the existing staging, installer dry run,
backup and installed-controller verification, with auto-deploy service/timer
quiesced and runtime-masked. The root transition receipt binds the original
controller hash to its approved new immutable source; it permits no environment,
upstream, release-state or worker-authority discrepancy. The interlock remains
on installation failure; automation does not resume itself.

The activation transaction takes the deploy lock, guards the known provider402
origin again, inhibits both blue/green consumer sets with restart policy `no`,
and persists RECOVERY authority before preparing the recovery candidate. The
separate recovery traffic driver accepts only the contract candidate or its
registered passive local fallback. Normal traffic switching, migrations and
auto-deployment reject the durable recovery interlock, even when authorization
credentials are absent. Unknown interrupted phases require operator review.

Candidate and fallback use separate private Docker bridges, the same protected
local-provider configuration, and shared persistent recovery Redis. Their
frontend `backend` aliases cannot cross-route. The only helper is the isolated
HTTP parser; no notification, calendar or deletion consumer is created. Rollback
changes only traffic/runtime; local PostgreSQL/Auth state and recovery Redis
remain intact, preserving newly accepted sessions. No hosted HTTP fallback,
checkpoint restoration or worker reactivation occurs.

These are implementation rules, not evidence of completed activation readiness.
The ignored validation report must prove live production-shaped fixture traffic,
rollback and exact-image operator Auth before approving production use.

### Protected provider402 phase separation

`PREPARE_AND_REHEARSE` runs through the fixed-path `madar-provider402-prepare`
launcher and a root-protected private-resource adapter. It checks exact source,
images, schema115, no migrations, actual provider402 origin/provenance, a verified
checkpoint, private target health and source write-fence validation. It does not
require human Auth or completed runtime rollback evidence to start the private
candidate and fallback. It cannot mutate production traffic, worker authority,
configuration or slots. Preparation receipts do not authorize activation.

`AUTHORIZE_ACTIVATION` requires all fifteen completed rehearsal gates, including
human Auth, MFA/AAL2, tenant isolation, business write denial, both-slot worker
inhibition, traffic/interruption rehearsal, passive fallback, runtime-only local
rollback and failure injections. A root-protected receipt binds the exact source,
image IDs, schema contract, checkpoint, provider402 evidence, production
fingerprints and completed rehearsal digest. Changing an input invalidates it.

`ACTIVATE_RECOVERY`, controller installation, credential issuance and production
traffic changes independently require that completed receipt. No fixture switch,
environment flag or Phase-1 receipt waives it. Normal deployment, schema recovery,
forward repair and migration checks remain unchanged. Recovery rollback changes
only runtimes using the current local provider; it never restores a checkpoint
over accepted Auth sessions and never routes to hosted Supabase HTTP.

### Fresh provider402 bootstrap ordering

Initial installation is a root-only operation from trusted protected source,
bound to the complete exact contract and completed rehearsal record. It retains
the canonical current-origin/main resolver, staging, static preflight, installer
dry run, checkpoint/provenance validation and production locks. It does not
require a bearer credential before the installer can issue one. Installation
and installed-controller attestation precede an exclusive protected installation
witness and one-time contract-bound credential. An existing credential/interlock
or installation witness rejects fresh installation rather than refreshing it.
No untrusted/non-root entrypoint can issue the credential.

Subsequent activation authorization and runtime operations require that
credential/interlock. Phase 2 still requires all exact rehearsal gates; Phase 3
still independently requires Phase-2 authorization. Installation never switches
traffic, starts consumers or executes migrations. There is no skip-auth flag or
arbitrary-ref resolver. Normal deployment/upgrade authorization is unchanged.

A root-written pending installation interlock is armed before quiescing/install.
It contains no bearer token and authorizes no runtime operation. Ordinary
mutators fail closed while it exists. Only successful installation attestation
can advance this exact interlock to the issued one-time credential; failure
retains the pending interlock for operator review. No prior credential is reused.
