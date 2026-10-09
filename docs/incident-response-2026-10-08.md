# Madar incident investigation — 2026-10-08

Production was inspected read-only. No production source, controller, proxy,
configuration, database, authorization record, checkpoint or container was
modified. No merge, push, reset, migration, cutover or consumer start occurred.
Development changes and test execution originate only from
`/opt/madar-development/repository`.

## Git reconciliation

Fetched origin successfully without reset or history changes.

| Item | Exact identity |
| --- | --- |
| Checkout branch | `recovery/provider402-signin` |
| Checkout HEAD | `7ca0a0241786a974d16b692a05250ed0ac18d8a1` |
| origin/main | `be2925cf4dca5a185a2226860c453fce10248125` |
| origin/recovery/provider402-signin | `7ca0a0241786a974d16b692a05250ed0ac18d8a1` |
| main-only / recovery-only counts | `0 / 1` |
| Initial uncommitted work | None |
| Open PRs | None, verified through GitHub CLI |

The complete remote delta is commit
`7ca0a0241786a974d16b692a05250ed0ac18d8a1`: 33 added lines in
`web/deployment/lib/provider_local_transition_runtime.py` and
`web/backend/tests/test_provider_local_transition.py`. It explicitly sets the
already validated root-owned, non-writable authority directory to 0755 because
the root launcher uses umask 077. The authority file remains 0444. The regression
checks repeated READ_ONLY publication and rejects an untrusted writable directory.
There are no authorization artifacts or checkpoint edits in this branch delta.

All other highlighted fixes are already ancestors of main:

| Fix | Commit |
| --- | --- |
| Bytecode identity / unused-install repair | `be2925cf4dca5a185a2226860c453fce10248125` |
| Emergency automated acceptance | `e0d66a4908efe4c9c4198fdf56712fe76adf5591` |
| SMTP acceptance policy | `6dfcd2b2ec2a46da8ac7d5bddaa76dcc7ee10f39` |
| Local transition / transaction state | `d7570a6b1b09170a26408cc52106e5f9cd63132a` |
| Worker repair / SMTP preparation | `014d664612eab89f50f4051593fb9a511857ab60` |
| Recovery switching proxy publication | `66717f03fc1c07d2c74cab692510819818b14808` |
| Backup connectivity / proxy publication | `5c6b2958984ef83eecf511690b07bf4675cecc50` |

Main is a direct ancestor of recovery, so this original delta has no merge
conflict. Recommend a reviewed, forward-only source integration of the permission
fix and separately reviewed local retry change below. Do not promote recovery
wholesale, reinterpret main ancestry as production authorization, or reuse
be2925-bound records for 7ca0 or any subsequent SHA. Protected installation needs
its own supported transaction; ordinary auto-deploy is not the repair path.

## Independently observed production

Direct public probes bypassing the execution environment HTTP proxy returned
502 for both `https://madarportal.com` and `https://api.madarportal.com`.
The stable proxy container is unhealthy; its systemd service failed its startup
health wait. The execution-environment HTTP proxy initially returned 403; that
was not used as the origin availability result.

Configured upstreams:

```nginx
upstream madar_backend_active { server 10.254.202.4:8000; }
upstream madar_frontend_active { server 10.254.202.5:8080; }
```

Their actual owners are reversed:

| Role | Registered fallback container | Current healthy endpoint |
| --- | --- | --- |
| Backend | `madar-provider402-rehearsal-94750f00e0d3-candidate-local-fallback-backend` | `http://10.254.202.5:8000` |
| Frontend | `madar-provider402-rehearsal-94750f00e0d3-candidate-local-fallback-frontend` | `http://10.254.202.4:8080` |

Backend live, ready, version and recovery endpoints return 200; ready is true,
source is be2925, slot is local-fallback and schema range is exactly 115.
Frontend returns 200. Recovery reports restricted=true and
business_writes_enabled=false. The internal bridge is an internal Docker bridge.
Both containers have restart=unless-stopped and no published host ports.
Descriptor ports 29401/39401 are nominal adapter values, not reachable durable
host endpoints. Durable container identity exists; its observed IP is volatile.

Exact fallback images match the protected contract and image revision labels:
backend `sha256:2ee19aea2599c3e386c2cc9e249d0b7721b4ab3c3f01f5ab358ecdcb88353c8b`;
frontend `sha256:d931354f8c7f0cab2a7a9a0851fe107345147ff50fefb48b62bf7fd7d8b79c5a`.
Labels and original build records support identity; this does not independently
prove reproducibility of every image byte from source.

The retained blue backend is live=200, ready=503; blue frontend=200. Green
8102/3101 refuse connections. Blue is not a verified local-compatible fallback.
Local Supabase containers are healthy. A READ ONLY SQL transaction independently
confirmed live core schema 115.

Both provider recovery and protected local transition record
local_rollback_active. Traffic records local-fallback with database_restore=false.
Protected authority is READ_ONLY; normal_writes_ever_enabled=false. Its directory
is still root-owned 0700 and file 0444, reproducing the permission failure.
All six notification/calendar/deletion consumers are stopped with restart=no.
Auto-deploy timer/service are inactive. Parser/remote services are distinct from
these business consumers and were not changed.

## Root cause and governance blocker

The production adapter intentionally binds prepared rehearsal containers into
production: ProductionRecoveryOperations derives its container prefix from the
protected preparation binding. The naming is not proof of accidental routing
alone. Its switch resolves container-role IPs and persists them in Nginx config.
There is no stable published port or boot-time reconciliation for those addresses.

The host rebooted at 21:43:19 local time. Fallback containers restarted at
18:43:52 UTC and the proxy failed startup at 21:45:12 local. Persisted upstream
bytes still match the protected transition fingerprint, but their current owners
are reversed. Immediate cause is stale role-to-IP routing. Docker address
reassignment across reboot is strongly supported by the restart timeline; no
historical Docker allocation log was available to independently prove the prior
assignment. Restarting only Nginx would retain the wrong upstreams.

All recovery authority under `/run/madar/control-plane-upgrade` is absent:
credential, credential alias, installation witness, contract, schema contract and
interlock. Durable recovery state survives. Existing recovery and normal-local
operations require that volatile authority. The source-only installation repair
is explicitly for an unused installation and cannot repair this active recovery.
Normal upgrade also cannot consume this durable recovery state.

## Evidence classifications

- VERIFIED: observed public outage, role/address mismatch, live local fallback
  health/version/fence, image IDs/revision labels, consumer inhibition, schema115,
  installed controller marker be2925, no bytecode caches, matching inspected
  installed tracked deployment bytes, and transaction/upstream byte fingerprint.
- VERIFIED for current byte integrity only: all files enumerated by both current
  checkpoint manifests match their sizes and SHA256 values. This is not a new
  restore test or provenance authorization.
- UNVERIFIED: the original operator authorization claim. Its root-owned 0600 JSON
  asserts explicit approval but does not independently establish the user approval
  provenance. No conclusion of wrongdoing is drawn.
- UNVERIFIED as independent current-source acceptance: protected aggregate PASS
  claims. Original Auth and private-runtime scripts contain real assertions and
  the historical full CI log records 2137 tests, 236 skips, no external attempts.
  The CI summary alone contains exit/scope rather than an immutable source/test
  input binding. The new permission test is absent from that historical run.
  Current source was tested independently below, without minting production proof.
- INCONSISTENT scope: the Auth script's browser_api_connectivity PASS checks HTTP
  readiness and /login through urllib, not an executed browser/JavaScript flow.
  This cannot serve as independent browser acceptance. Logout evidence explicitly
  excludes revocation of a copied provider refresh token; it proves only the
  recorded browser-cookie/logout scope.
- INCONSISTENT current-runtime claim: local_rollback_active receipts remain byte
  consistent while the stable route is 502. They record a historical completion,
  not current serving health.
- UNVERIFIED for the extended checkpoints: the restore report binds dump
  ce0ed004650d3d586e4aa6100c8a01c54ee027ba16a5b802e3f8a751137d3db4 and source
  36df939dd28e7784cbcdbb8d4c3bae6ec2abadb3. The preserved 13-entry manifest was
  extended to 16 entries for emergency/final/bytecode image records, then the local
  transition checkpoint to 19 entries. Original 13 entries are unchanged. Both
  retain created_at=11:01:05 and restore_verified=true; later manifests have new
  digests/mtimes. The same old restore report is reused. No subsequent independently
  executed restore proof bound to those extended manifests was found.
- INVALID use: treating that historical restore report as proof of a fresh restore
  of the full extended packet, treating HTTP-only checks as browser execution,
  or reusing be2925 authorization for a different SHA without independently proven
  applicability. This does not declare the original underlying backups invalid.

Rollback source has no database restore operation and receipts explicitly record
no restore. No evidence of a stale data restore during runtime rollback was found;
absence of a historical operation cannot be independently certified from these
receipts alone. Original evidence was preserved without rewriting any record.

## Proposed P0 operation — blocked, not authorized or executed

The smallest desired operation is to reconcile ONLY the already registered,
currently healthy restricted local-fallback routing by resolving container roles
again under the deployment/runtime locks, validating images/source/schema/local
provider/write fence and consumer inhibition, publishing these current targets
through the governed proxy controller, testing Nginx, reloading and verifying
public and stable frontend/backend/version/fence and proxy health:

```nginx
upstream madar_backend_active { server 10.254.202.5:8000; }
upstream madar_frontend_active { server 10.254.202.4:8080; }
```

Addresses must be resolved again immediately before mutation, not copied blindly
from this report. Preserve the exact prior upstream and state bytes as immutable
transaction pre-images. Maintain coherent local-transition fingerprints through
that same supported transaction; do not edit protected transaction state manually.

The existing installed provider rollback entrypoint is:

```text
sudo /opt/madar/control-plane/deployment/bin/madar-provider402-recovery rollback
  --approved-contract d011351a6ee90ae13e2e1fc6f8dd391e843c0c07dfa3ce59a190905f3d7ed7b7
```

This is NOT an executable approved repair now: it requires the lost credential
and consumes the disputed activation evidence. It also does not reconcile the
separate normal-local transaction fingerprint record. The installed normal-local
rollback rejects its completed local_rollback_active state. Neither command is a
safe workaround for the missing authority. No supported independently authorized
routing-only reauthorization/repair operation exists in the installed source.
Do not reconstruct /run records, copy retired credentials, reinstall as fresh,
start a cutover, or call adapter internals to bypass those gates.

Affected resources, once supported: active-upstreams.conf, proxy running config
(and possibly the installed proxy service if canonical logging publication is
needed), recovery traffic/phase receipts and coordinated transition fingerprints.
Customer DB/Auth/Storage, application images, worker ownership and business-write
mode must be preserved. Expected impact is recovery sign-in/read availability;
business operations remain fenced. No schema/migration or consumer activation.

Required rollback design for the eventual supported repair: restore the exact
saved routing pre-image through the same governed transaction and validate/reload
Nginx, retaining all failure/audit records and READ_ONLY/consumer inhibition.
That pre-image is currently an outage route, so reverting preserves the safety
boundary but does not restore availability. Prefer a governed retry to newly
resolved verified local fallback; never route to hosted blue or restore a DB.
The existing recovery switch has no automatic upstream pre-image compensation;
this required rollback capability is not claimed to exist today.

Approval must therefore wait for a concrete supported credential-recovery and
state-coherent routing-repair mechanism with independently established authority.
This report does not ask the operator to authorize an operation that bypasses
those requirements. No first production-changing operation was attempted.

## Development repair prepared

The existing recovery permission commit was reviewed and its real root ownership
regression passed in an isolated temporary directory. New uncommitted source
changes allow the existing normal-local rollback to repeat from its completed
local_rollback_active phase, retaining credential/evidence/fingerprint gates,
write fencing, consumer inhibition and current-data semantics. They do not enable
prepare/handoff/switch/finalize from that phase or restore lost credentials.

Focused tests exercise repeated rollback, failed authorization/evidence/fingerprint
checks before mutation, no writes/consumer starts/data restoration, and role-based
endpoint re-resolution after IP reassignment. Policy documents the narrow scope.
These changes do not solve durable addressing or active post-reboot authorization;
those require a reviewed supported repair design before production installation.

Independent development validation: 30 focused tests (one non-root skip), the
skipped root permission test separately PASS, and 154 deployment/control-plane
regressions PASS. Five static dependency/migration/transition/release/secret
checks and diff whitespace checks PASS. Migration validators execute no SQL.
Full hermetic current-source backend suite: 2141 tests, 237 skips, PASS, no external
attempts. The root permission test is among skips and was verified separately.
Installed backend dependency constraints match. No frontend runtime changes were
made; frontend lint/build/audit and production acceptance were not claimed.

Original failed development attempts are preserved: one Docker mount-layout
failure, then an outdated madar-backend-test image missing qrcode/current deps.
The successful run uses retained madar-backend-ci-exact:5c6b2958 with current
tracked backend source and repository contracts mounted read-only, network=none.
The successful runner exited 1 only after its recorded suite/constraint successes
because a local orchestration variable was reused as a Path; recorded suite exit
is 0. This is not a test failure or a production PASS. A comment was added after
that full run without changing execution logic; focused checks are rerun afterward.

Raw command, source-diff identity, image identity, actual suite log and prior
failures are in `.incident-response/2026-10-08/`. These are development evidence
only, not protected authorization receipts. Source work remains uncommitted for
review; no main integration or production installation occurred.
