# Security review and failure evidence

Evidence levels here are distinct:SOURCE/MODEL, NATIVE DATABASE, NATIVE
FILESYSTEM, NATIVE SERVICE, PRIVILEGED ISOLATED SYSTEM and PRODUCTION READ-ONLY
OBSERVATION. Automated independent review is not human operational approval.

## Confirmed application and admission defects

| Component | Confirmed failure | Correction and evidence |
|---|---|---|
| Academy document and learning form uploads | A real PostgreSQL metadata RPC committed, then its response was lost. Application exception cleanup deleted the referenced private bytes. | Retain bytes/quota after any attempted metadata RPC with uncertain acknowledgement; return bounded503 and original operation identity. Old native cases2 FAIL; repaired2 PASS. Focused service tests and native CI pass. See`private-upload-integrity.md`. |
| Schema150 cursor-based quiescence helper | A transaction's cached activity snapshot could accept zero after a new writer connected, or retain a client after server exit. | Refresh the current session's statistics snapshot before every unchanged strict observation. Real PostgreSQL17 before1 FAIL/1 ERROR; after5 PASS. Published SQL unchanged. See`06-QUIESCENCE-SNAPSHOT-REGRESSION.md`. |
| Schema150 cursor MVCC snapshot | REPEATABLE READ/SERIALIZABLE could hide a pending request committed by a writer that had exited, despite fresh activity statistics. | Reject those isolation levels before queue observation. Four native before/after cases and two full-schema hosted regressions;see`10-MVCC-OBSERVATION-REGRESSION.md`. |

The upload defect is a data-integrity risk. No investigation established affected
production records; no production repair was performed. The fix can retain
unreferenced staged bytes after a definite but unreadable rejection. That bounded
trade-off needs reconciliation and quota handling, not destructive cleanup based
on a transport exception. The native byte-store fixture is a real private
filesystem paired with actual service-role PostgreSQL, not a native StorageAPI
lost-response test. Existing synthetic provider acceptance is reported separately.

## Draft adapter failures reproduced before publication/admission

Independent reviews found and corrected these implementation boundaries with
focused adversarial tests. They were defects in the draft continuation, not
evidence of exploitation or installed production-controller vulnerabilities:

- Ambient libpq host-address parameters could override a validated provider URI.
  Inspect actual environment and reject unsupported `PG*` overrides. Restrict
  provider network identity, aliases and resolver configuration as well.
- Supervisor reconciliation previously inferred quiescence from an installed
  condition. Require inactive/dead state, no queued job and zero main/controlPIDs.
- Configured `PublishAllPorts` or effective Docker host bindings could expose a
  supposedly private provider. Reject both configuration and runtime publication.
- A secondary-network alias could make the measured database identity ambiguous.
  Require the exact single database network and unique alias binding.
- Initially reachable effects did not cover every declared private/active state.
  Reject impossible provider, candidate, proxy and restart-policy declarations
  before fencing, instead of accepting an operation that cannot finish.
- First-effect ordering, effective condition polarity and post-grant observation
  needed explicit tests. Boot barrier precedes effects; conditions must be exact
  negative non-triggering conditions; target authority is verified, never issued.

Final independent review at exactb9d826ee reran110 scoped component tests with
zero failures/errors/skips. It found no further reproducible authority/source
substitution or disclosure in the reviewed paths. This is SOURCE/MODEL plus real
temporary filesystem/journal/kernel-flock evidence. It does not establish native
provider effects or complete operational controller safety.

## Actual privileged-system evidence and retained failures

The dedicated KVM guest ran the real root-owned installer and systemd. An actual
reboot retained the negative-condition test barrier and disabled deployment
timers. A later atomic replacement installed182 exact source files, including
the new schema150 helpers, frombd0c614c. Guest bootstrap source, replacement
source and final application source are different identities; none is relabeled.
See`02-ISOLATED-PRIVILEGED-VM.md` for exact sources and observations.

The initial QEMU launch failed before guest execution because daemonization
conflicted with retained seccomp spawn denial. A narrowly verified repair used
foreground process management without weakening seccomp. Original consumed
attempt and archive/disk/seed identities were retained. A raw rootPython probe
created unwanted bytecode before an identity refusal; its evidence and backup
were retained, then actual atomic replacement restored a clean installed tree.
A full coordinator CLI negative probe stopped at an earlier synthetic environment
ownership guard. It is not credited as a complete CLI authorization acceptance.
The supported narrower root/source/missing-approval/missing-lock refusals were
observed separately. No real approved release or issuer was invoked.

The guest is powered off. The staging host was not rebooted. Native systemd
barrier behavior on a harmless test unit is not actual ingress, provider, worker
or complete schema150 boot acceptance. Full native interrupted installation,
migration, candidate, private recovery, write handoff and proxy matrix remains
incomplete. Missing engineering keeps operational admission closed.

## Elevated credentials and reconciliation remain open

The reviewed78-path inventory has no unexplained omissions; each new entry maps
its real router/service/RPC boundary. This does not certify every service-role
path or tenant boundary. Service-role bypassRLS remains a reason for narrow,
tested RPC authorization rather than a reason to disable providers wholesale.

Deletion ownership uses protocol2, generations, database-clock leases, restricted
direct lifecycle writes and durable external intent. The worker still has broad
provider/service credentials for legitimate deletion steps. A dedicated narrow
identity or broker and controlled credential cutover are **not implemented**.
No production credential was replaced or rotated. An external timeout is not
proof of failure; database fencing cannot undo an already sent provider request.
Uncertain deletion/upload effects still require an independently authorized,
auditable provider-evidence reconciliation workflow. No unrestricted repair
endpoint or arbitrary SQL/shell helper was added.

No new historical-secret investigation or platform-wide authorization certificate
is claimed. Private metadata, raw role archives, journals, synthetic passwords,
JWTs and MFA secrets remain outside Git. Published evidence contains identities,
hashes, bounded counts and limitations rather than credentials/customer records.
