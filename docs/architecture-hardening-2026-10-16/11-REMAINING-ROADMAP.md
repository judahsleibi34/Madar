# Prioritized remaining work

These are unimplemented acceptance gates, not completed tasks. Proposed production
operations require their existing separate approval even when code is ready.

| Priority | Work | Dependencies / acceptance |
| --- | --- | --- |
| P0 response | Any newly confirmed cross-tenant, auth, financial or destructive release defect | Reproduce safely with synthetic data; fix before promotion. None newly confirmed here; audit remains incomplete. |
| P1 | Fence notification acknowledgements to lease/claim generation | New mirrored versioned RPC migration, old-worker compatibility, stale-owner concurrency/crash tests; existing release migration approval. |
| P1 | Enforce reviewed main branch rules | Repository admin; reviews, required actual CI checks, block force pushes/deletion, restrict bypass; verify via API. |
| P1 | Complete tenant/runtime-role defense in depth | All routes/jobs/storage/cache writes mapped; native cross-tenant mutations and pooling tests; service-role compatibility maintained, no blanket production RLS flip. |
| P1 | Native reservation/order/payment integrity matrix | Concurrent capacity/inventory, decimal snapshots, duplicate webhook/refund events; no live charges; database and provider failures injected. |
| P1 | Full restored application and off-host DR | Isolated cluster/roles/Auth/MFA/storage, restored app login/business acceptance, independent host loss; measured RPO/RTO and WAL integrity, restore without source cluster. |
| P1 | Commercial enforcement decision | Operator approves customer impact/grace/holds; verify paid/trial/unpaid states before any production flag change. No automatic charging. |
| P1 | Governed fresh-build/release acceptance | Fresh locked images, provenance, required CI, exact-image native tests, protected-controller compatibility, backup and existing approvals; no promotion from this session. |
| P1 | Public tenant browser/managed filesystem parity | Staging public-domain build config and isolated host routing, published synthetic form/site, old/new managed assets, durable upload mounts and restart/restore acceptance. |
| P1 | Performance coverage and supported capacity | Repeated randomized runs, representative fixtures/endpoints, SQL plans/roundtrip profiling, SSD comparison, latency/error/resource confidence; admin read still misses250ms target. |
| P2 | Cache invalidation across workers | Bounded event/version strategy; no cross-tenant keys, race/Redis failure tests and TTL fallback. |
| P2 | Complete authenticated E2E coverage | Synthetic registration/onboarding/forms/commerce/calendar/learning/deletion plus stale edits/deleted-record races, accessibility/network interruption. |
| P2 | Native worker/delivery coverage | Calendar/deletion/ingestion/parser workers, provider idempotency/backoff/dead letters/graceful shutdown and tenant ownership. |
| P2 | Useful bounded production signals | Integrate existing observability; queue age/dead letters, Redis memory/latency, backup age/failures, request/db pressure; alert drill and cardinality budget. |
| P2 | Supply-chain expansion | Real dependency/container/secret scanners with reviewed pins, required check wiring/provenance; retain lock integrity and least-privileged tokens. No claim full scanner coverage already exists. |
| P2 | Enterprise connector foundation | Inspect domain-specific external adapters before a registry; synthetic cursor/idempotency/outbox/conflict/field-authority/loop tests; no customer credentials. |
| P2 | Athena inference/tool boundary | Explicit authorized allowlist, cancellation/timeouts/usage accounting/tenant retrieval tests, isolated inference resources; no unrestricted SQL or production GPU changes. |
| P3 | Documentation/operational simplification | Reconcile historical provider/schema notes, maintain exact current acceptance references, remove only proven obsolete artifacts through owned cleanup. |

Hardware proposal: stage OLTP on SSD for representative latency, keep HDD for
backup/archive unless measured otherwise. This needs capacity/placement planning;
no VM relocation or production disk change was attempted. Two nodes are not HA;
no automatic promotion without quorum/fencing design.
