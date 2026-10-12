# Latest-main manual release assessment

This is engineering evidence, **not an executable production proposal or
authorization request**. Auto-deploy/Phase3B/VM work is deferred. No production
installation, traffic, worker, authority or database mutation was performed.

## Independently inspected baseline

Fetched canonical GitHub main: `eacfb005230063f792b7f60021b835abb473a142`
(PR188 merge). Exact-SHA GitHub Backend Check run38238952094 and Frontend Check
run38238952166 both completed successfully. Those checks cover that main SHA,
not the additional unmerged release corrections documented below.

Production: GREEN, NORMAL, native schema136, accepted application
`81cebfeb024341cd8d784402ba1f92ed2e63fb3d`, controller/checkout
`dbc26321edda331beb3c59e21fc05a6a250beacf`. The **installed** protected
`attest_compatible_runtime()` passed. Frontend and API readiness returned200;
current three business consumers were healthy. Auto-deploy timer is disabled/
inactive; service static/inactive. All three native backup timers are scheduled.
No new authenticated production mutation was attempted.

## Required schema and source changes

Main's active release descriptor still selects115..136 and migrations116..136.
That descriptor does not activate its newer application features. Latest main
includes generic Forms review requiring144, assessments requiring143, learning
Forms requiring141, owner tools140, programme configuration/workflows138/139,
and learning notifications137. Application-only deployment at136 would retain
upgrade-required responses and unavailable UI capabilities; it is not the
requested complete release.

The intended learning lineage is **136→137→138→139→140→141→143→144**.
Exchange142 is a different branch, not a missing step.143's SQL requires141,
and144 requires143. The newest generic Forms review supports generic Exchange
intake without specialized142 opportunities/decisions. Those142-only features
are explicitly excluded, not silently claimed as deployed.

| SQL | Purpose |
| --- | --- |
|137|Learning notification integration|
|138|Academy programme workflows|
|139|General programme configuration and referral security tightening|
|140|Academy owner tools|
|141|Independent E-Learning Forms|
|143|Learning/assessment capabilities, with142 excluded|
|144|Generic Forms reviews and existing programme associations|

Against installed controllerdbc26321, main changes22 deployment files,66 backend
files and142 frontend files, plus Compose. Application changes include native
owner/programme/Form/assessment routes and services, learner/owner UI, Builder
localization and persistence, learning recording/body limits, request security,
notifications and payment-provider integration. Core Dockerfiles, dependency
locks and backend/frontend workflows are unchanged againstdbc26321; Compose
adds explicit schema exclusion propagation. Deployment changes include the
installer inventory, release deployer, locked executor, exact learning route and
ledger reconciliation. Image identity and functional acceptance are therefore
not transferable from application81cebfeb to latest main.

Minimum configuration: a **manually selected136..144-compatible application,
excluding142**, freshly bound v2 authority, accepted backend/frontend images,
the seven pinned migrations, and a privileged controller/boot/source-role
transition from the protected completed-NORMAL136 origin. Historical recovery
receipts remain immutable DATA. No automatic release mechanism is required.

## Narrow preparation corrections

On `fix/manual-main-schema144-release`, based on exact main above:

- New unselected `learning-136-144-path.json`,
  `migrations-137-144-learning.json`, `schema-136-144-learning-bridge.json`
  compose the unchanged, previously reviewed SQL entries.
- Existing learning authorizer verifies this second exact pinned route;
  arbitrary gaps, modified descriptor/manifest/SQL/mirror/bridge and142 reject.
- Existing release/runtime compatibility permits only the additional reviewed
  136..144 range with142 excluded.
- Existing application v2 authority accepts that exact range only with matching
  runtime bounds/exclusion, root ownership, source/context and fresh grant.
  Legacy115..136 grants cannot authorize it. Native-provider validation carries
  those already-validated bounds; provider recovery fencing remains intact.
- The source validator checks the new descriptor when present. Policy and
  architecture document this unselected candidate and remaining execution gates.

**Active release.json, every historical SQL/mirror and existing migration
descriptor remain unchanged.** No new SQL migration or production grant exists.
This does not implement or claim the final manual handoff/boot transition.

Measured preparation artifact hashes:

| Artifact | SHA256 |
| --- | --- |
|New route descriptor|`ea2654bedb35f38cf7bfb59d5d7f18c82099344de8133f0d0e74efcdb92d9571`|
|Seven-migration manifest|`d1016392aa863d7f8b2197bd1e2b479799ceb0ce5502e61840f41f002878f3c0`|
|Unselected136..144 bridge|`3bfea4deb6d987e9b5a0b631a962bdb2bb6b40a812187089f7ea19ce11437ad1`|

These are source artifacts, not hashes of an approved operation.

## Real current-backup SQL rehearsal

Backup `madar-20261012T073631Z`, manifest
`b90407e75ca64bad894cfc94d784f40c4a0d8e4db8954ba7caded5f0fa2d9e0c`,
was independently checksum-checked: all465 entries passed. Manifest reports
schema136,129 public tables and application81cebfeb. Dump TOC additionally
contains23 Auth and10 Storage table-data entries. Native current database size
is30,485,651 bytes; the entire ordinary backup occupies311,455,744 bytes.

The dump was restored with `pg_restore --exit-on-error` to a current-operation
private container using existing PostgreSQL image
`sha256:f371b5f3f2ac0a05703f33d6e6134515fb2498cab708fb948a0aeb7481467c00`.
It is nonprivileged, read-only, all capabilities dropped, network-none, no host
binds/sockets/devices,768MiB RAM limit and512MiB tmpfs. The executor child shared
only that isolated network namespace, had no capabilities, read-only selected
source/backup mounts,512MiB RAM limit and64MiB tmpfs. Its actual PostgreSQL
authentication used a fresh private password delivered through stdin, not CLI
arguments or production credentials. Roles needed for ownership/ACL restoration
were created without login credentials; this is SQL preservation testing, not
full application/Auth-service acceptance.

The actual `LockedMigrationExecutor` and actual SQL ran. A real division-by-zero
was injected before139 after137/138 committed. The failed stage retained138;
the ordinary executor resumed forward to144 and a subsequent entry executed
no SQL. All162 original public/Auth/Storage tables were compared using original
column projections and canonical row hashes. Only the schema-state row changed.
Owners were preserved. The sole ACL differences were139's explicit reduction of
service_role mutation privileges to SELECT on academy_referral_codes,
academy_referrals and academy_referral_rewards. All unrelated ACLs matched.
There were zero invalid indexes. No payments or workers were activated.

The first strict unchanged-ACL assertion failed because it correctly detected
that tightening. It was investigated against a schema-only restore and exact
139 SQL; the verifier now requires precisely those three new ACLs. No SQL or
application behavior was changed to make the test pass. Early fixture launch/
read-permission failures are retained separately; they occurred before SQL.

Root-private reports and stage records are retained under
`.incident-response/manual-main-release-20261012/`, especially
`private-migrations-v5-stdout.json` and `private-migrations-v5-stderr.log`.
Runner source is separately measured and retained under
`.incident-response/manual-main-release-runner-20261012/`. This evidence covers
the snapshot captured at07:36:31UTC; it does not freeze subsequent customer
writes. Execution must take/verify its fresh current-data backup under fencing.

Focused manifest/executor/authority tests: **22 PASS**. Dependency locks,
SQL namespace/mirrors, transitions, exact learning route, forward-release and
secret hygiene source checks PASS. No exact-image application acceptance or
complete manual136→144 coordinator rehearsal is claimed. The initial host
Python test import failed because host lacks backend dependencies; the focused
suite passed in the existing dependency image with current source mounted.

## Backup, replica and storage

Node1 replica exists at
`/srv/data2/madar-backups/normal-local-production/f39f7cf82913d30d4f8686ae5cd2ca59626d97faadb8557349b9c83cdcbf5b63/madar-20261012T073631Z`.
Its manifest hash matches, and remote `sha256sum -c SHA256SUMS --quiet` exited0.
Node1 available capacity measured910,006,542,336 bytes. No backup pointer or
original backup was modified. The existing protected schema136 completion
attests its prior independent restore; a fresh complete release-specific
post-upgrade backup/restore remains required.

Node2 remains approximately34.94GiB free. Retaining30GiB allows only4.94GiB
additional allocation. Two complete backups at observed size require about
0.58GiB, and private SQL restoration was bounded in RAM. Accepted old image
pair totals1.64GiB; **new image/build-cache peak is not yet measured or approved
as fitting**. Build cache is currently zero. The two old private test storage
trees occupy13,518,659,584 and28,907,077,632 bytes, but contain historical
fixture/evidence resources and are not established as disposable. They were
not deleted. Docker's aggregate reclaimable count is not permission to prune.

## Actual dry-run failure and remaining gates

Installed invocation:

```sh
sudo madar-control-plane-upgrade eacfb005230063f792b7f60021b835abb473a142 --dry-run
```

Exit1, phase `candidate_resolution`, `approved_sha_not_current_origin_main`.
Actual remote main is the requested SHA, but production's cached origin/main
remainsfa1339412fab2b638c0d9836c1b1c3987a066368. Read-only resolution checks both;
no live fetch was performed to suppress the error. Its supported audit identifies
`dry_run_no_mutation`; no candidate controller/application was installed/promoted.

After that binding is addressed in a reviewed complete operation, later guards
remain real prerequisites: historical provider admission still accepts only a
fresh completed-NORMAL115→136 contract, and the installed compatible boot kernel
rejects schemas beyond136. These must be reconciled for this manually authorized
successor, not bypassed or made dependent on enabling auto-deploy.

Before production approval: review/integrate the necessary source fixes; complete
the exact manual controller/source-role, root grant, singleton-worker and boot
transition; establish immutable accepted136/144 application images and their
CI; validate the complete handoff/forward-repair path; prove its storage peak;
freeze one complete operation and pass its final read-only production preflight.
Expected fencing/downtime is **not yet measured**. No final operation/package
hash, executable cutover command or approval request is issued while those
mandatory gates remain unresolved. **Production release ready: NO.**
