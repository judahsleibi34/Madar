# Fresh PhaseVII schema150 acceptance

`web/staging/integration/phase7_schema150_acceptance.py` reuses the existing
schema150 acceptance orchestration and real Auth/MFA/Storage, notification,
reservation/deletion-worker and runtime-image probes. It exposes only `INSPECT`
and `REHEARSE` on the dedicated staging VM. This is a synthetic148 archive
restore followed by migrations149/150, **not** protected146→150 controller
acceptance or production authority.

Fixed namespace:

| Identity | Value |
| --- | --- |
| Project | `madar-schema150-phase7-20261018` |
| Owner | `schema150-phase7-20261018` |
| Database marker | `madar-schema150-phase7-synthetic` |
| HTTP/TLS/provider bindings | loopback23080/23443/23081 |
| Archive origin | unchanged, exact independent synthetic148 origin accepted by the existing149 harness |

The existing150 target context hardcodes21080/21081 after entering its nested149
context. The wrapper replaces that context, installs only the new namespace and
restores all altered150/manage/smoke globals in `finally`;149 globals stay
unchanged. It does not enter the PhaseVI source/recovery contexts or expose their
stop/resume operations. Existing target directories, project resources and
occupied ports refuse a new rehearsal. There is no automatic retry/adoption.

Preparation retains the original archive owner/marker/checksum/path checks and
the immutable migration contracts. Only strict64hex synthetic database/JWT
credential values are retained from the fixed origin. Mutable origin
application/Compose/TLS files are not copied. The existing pinned-template restore
generator creates fresh target configuration/TLS. Its fully resolved plan is
translated to230xx bindings and validated through the unchanged strict restore
validator using an isolated copy with only the fixed public-port translation.
Actual public endpoints must already be230xx; old220xx endpoints cannot pass by
normalization. Every operational Compose invocation rechecks the captured plan
hash and structural validation, rejects project/file/profile overrides and sends
the actual230xx configuration over stdin. No mutable Compose/env path becomes
later execution input.

The source must be an exact clean committed HEAD. The inherited artifact verifier
still requires fresh authenticated CI archives, input hashes and image/source
identity; there is no receipt substitution, overlay build or provenance bypass.
The retained disk/memory minimums are8GiB free and2200MiB available, with existing
bounded service limits. Parent coordination of other VM workloads remains
necessary before running the full stack.

After the parent pins the reviewed commit and its fresh artifacts:

```text
python web/staging/integration/phase7_schema150_acceptance.py INSPECT \
  --source-sha <exact-committed-head> --artifacts <private-staging-home-artifact-directory>
```

`REHEARSE` uses the same arguments and mutates only the new owned synthetic
namespace. It must wait for explicit session coordination of source/artifacts
and memory. Failed attempts preserve their directory, evidence and volumes for
review. The result is recorded privately as `phase7-schema150-acceptance.json`
and explicitly carries `production_authorized=false`.

## Executed evidence and limits

- Read-only staging listener inspection found no conflicts on23080,23443,23081.
  Preparation rechecks current listeners; Docker's actual bind can still fail if
  another process wins the subsequent race, leaving the owned attempt for review.
- New wrapper safety tests: **12 PASS,0 skips**. Tests cover namespace restoration
  on interruption, exact-source/wrong-host/old-target rejection, listener/resource
  conflicts, malicious resolved plans, old endpoint rejection, configuration
  substitution/overrides, archive tampering, origin configuration exclusion and
  generation of the captured230xx plan.
- Retained configuration tests11PASS,149 acceptance safety8PASS,150 restore
  safety21PASS: **52 tests total**, including the12 new cases.
- Compilation and `git diff --check` pass.

At wrapper implementation, no `REHEARSE`, import or provider operation had run.
The subsequent native results below supersede that pending status. Process-global
contexts remain CLI-local and intended for a single operation per process; this
is not a concurrent server API. Component tests do not certify the privileged
controller installation, host reboot, production replica or operational approval.

## Completed native acceptance

Exact source:`b9d826ee70e87a7f3eda89c14a78004b79fd6dab`.
Fresh workflow39137752593,attempt1,artifact12140153655;
archive462,755,903bytes,SHA256
`412bf1f1349c0e0f9ba72bfb3c7b25a5399f339d53ab7378d782bfd92b137e36`.
The historical artifact name is not interpreted as a schema admission.

| Role | Verified image configuration identity |
|---|---|
| Backend and business workers | `sha256:5ced98fb5175125debf6a459d14aefcc5fba38ea8e34bcecd4f3df47f654c8a2` |
| Accepted frontend | `sha256:f0c304c718759d17db0bf6c16fbe0dab41537017c3d73c477c81ed5629454cc1` |

The archive/run/receipt/input hashes and actual imported image IDs/labels were
verified. No source overlay, old-run receipt substitution or image relabeling was
used. The exact clean staging checkout and all retained checkouts were preserved.

`REHEARSE` started2026-10-18T14:59:27Z and exited0 at15:04:42Z. Wall time315.157s;
the application report measured311.042s inside its narrower acceptance scope.
Do not call either time a production RTO or throughput measurement.

Native results:

- Independent148 database, original roles/passwords/memberships and eight object
  files restored; row/sequence and owner/grant/RLS/definer fingerprints matched.
- Captured149/150 SQL committed in order. Preserved business/Auth/Storage rows,
  sequences and prior outbox state matched. Schema/protocols were exactly150/2/2/2.
- Original password/auth identity/TOTP and private Storage bytes remained usable;
  anonymous private-object access was denied. New native Auth/MFA/Storage,
  notifications and application readiness probes passed.
- A real consuming deletion worker completed all ten steps for both a synthetic
  user and tenant, each in one claim attempt, with state
  `completed_with_retained_records`. The actual GoTrue identity and Storage object
  were absent; each request had two confirmed external intents. The foreign
  tenant was preserved. Worker restart retained successful consumption.
- All eleven fixed project services ran. Real external integration revocation,
  host-file deletion and lost external responses were not exercised by this
  runtime probe; native/model failure cases remain distinct evidence.

On2026-10-20, the exact-source browser smoke passed nine groups using Chrome
151.0.7922.34 over a verified loopback-only tunnel:password→restricted MFA, native
TOTP, privileged page/API, secure HttpOnly/SameSite cookies, pending-cookie
removal, script-denied access cookie, authenticated refresh, anonymous admin
denial, and mobile login labels/keyboard/width. No page errors or blocked external
hosts were observed. This is selected browser acceptance, not complete productE2E.

The resumed VM was swapping with1,468MiBavailable. After preserving the results,
only the eleven positively attested PhaseVII services were stopped onOctober20.
Their volumes/configuration/receipts remain. The22 retained source/recovery
containers kept their IDs, images and running/stopped states. Available memory
rose to2,316MiB; the browser tunnel was closed. The new stack is deliberately
**stopped**, not currently advertised as a running release. No production resource
was stopped or modified.

The later MVCC controller-helper correction in58dd5c47 is separate source
evidence. The b9 application/runtime identity above is unchanged and must never
be relabeled as a later commit's full-stack acceptance. This native restored
application result does not establish complete protected146→150 admission,
maintenance journals, write-handoff, real reboot during migrations, off-host
recovery or object-aware full application PITR.
