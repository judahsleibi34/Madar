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

No `REHEARSE`, image import, container start, restore, migration, provider request
or mutation of a retained project was executed while adding this wrapper. A
native final-image run and artifact verification remain pending. Process-global
contexts are CLI-local and intended for a single operation per process; this is
not a concurrent server API. These component tests do not certify the privileged
controller installation, host reboot, production replica or operational approval.
