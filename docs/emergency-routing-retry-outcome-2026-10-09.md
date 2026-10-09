# Madar routing-only recovery restored

The exact approved source and plan passed read-only preflight, then the documented
hash-gated bootstrap was executed once with the actual fresh operator approval.
It exited 0. No compensation was needed.

Approved source SHA256:
2bc41971b5f8db7c8ddf32449f812d916a997099fa8d67646514743fc4305a14
Approved canonical plan SHA256:
cca3c29eae4a720243497a9bc7a351f76d17d321b40a9279431e8f932347fbae

Actual protected audit:
- Fresh authorization issued 2026-10-08T21:22:21.524995+00:00.
- Reconciliation started 21:22:24.072326 UTC.
- Three consecutive complete successful rounds sustained for 28.54 seconds;
  convergence elapsed 41.645 seconds, within the 180-second bound.
- Reconciliation completed 21:23:07.020625 UTC.

Independent post-execution read-only verification:
- https://madarportal.com/: HTTP 200.
- https://api.madarportal.com/: HTTP 200.
- Frontend /api/health/ready and backend /health/ready: HTTP 200.
- Production proxy Docker health: healthy.
- Backend release be2925cf4dca5a185a2226860c453fce10248125, local-fallback,
  exact approved image/configuration/container identities unchanged.
- Registered backend 10.254.202.5:8000, frontend 10.254.202.4:8080; routing uses
  unchanged verified relay ports, not these ephemeral Docker IP literals.
- Native local Supabase DB, Envoy, Auth, REST and storage healthy; schema 115
  verified with explicit BEGIN READ ONLY / ROLLBACK.
- Both original protected transactions remain local_rollback_active.
- Recovery reports restricted=true, business_writes_enabled=false; public
  nonexistent-path POST probes denied with provider_recovery_read_only.
- All six business consumers stopped, restart=no.
- Original protected inputs and all preserved installation hashes unchanged.
- Current maintenance preimage retained with its approved hash.
- Installed retry source matches approved hash; new status active and startup
  gate verified.
- No customer-data writes, database restore, migration, image rebuild, worker
  start, normal cutover or Docker cleanup occurred during the approved retry.

The original helper, authorization, status, service, first drop-in and audit remain
byte-identical. The new sibling retry namespace, fresh authorization/audit, and
additive 91 startup-gate drop-in are retained. Prior failure evidence remains
preserved. The per-connection role verification continues to handle Docker IP
reassignment; no actual reboot or application-container restart was performed.

Exact executed command/tool completion and actual read-only verification output
are recorded in .incident-response/emergency-routing-retry-2026-10-09/
approved-execution.json and actual-post-verification.json. This document is an
incident summary, not replacement historical authorization or acceptance proof.

Normal writable production remains blocked pending independent historical
authorization/checkpoint restore applicability review, governed active-transaction
repair and permission/source integration, normal acceptance and separate explicit
cutover approval. Public routing restoration grants none of those permissions.
Incident work stopped after outcome verification and evidence recording.
