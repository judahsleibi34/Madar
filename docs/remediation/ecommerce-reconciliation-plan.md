# Current-workspace reconciliation audit and implementation plan

Authorized workspace: /opt/madar-development/repository (pwd and Git top-level verified).
Branch Saliba-Branch, initial HEAD e04cc2237053e62c48d15a71ee5c46efc0149309.
Preserve existing staged deletion of 666.txt; exclude it from the remediation commit.
Old corrective checkout remains read-only; its clean status recorded. Its commit
11ca164a is a separate child of 25ce4796, which is an ancestor of current HEAD.
The production fd91ddf SHA is unavailable in both repositories; ancestry is unknown.
Current development contains 259 changed files since the shared base, including
MFA, brands, multi-category, deletion, managed assets/runtime and commercial work.

Schema baseline: migrations001..115 mirrored in database/supabase; core115.
106 is delivery fees,108 brands,109 order totals,110 durable notifications,
111 category memberships,112 safe product deletion,113 asset visibility,
114 public runtime,115 commercial authority/holds. New migration116.
Current release bridge114..115, target115, rollback bound114; preserve commercial
115 and expand reviewed active manifest to115+116 rather than rewrite history.

Remaining bugs: V1 UUID upserts precede semantic cleanup; V2 only adds presentation.
Frontend hydration splits combined values with fresh UUIDs and positional codes.
Full saves perform independent row/category/tag/asset/aggregate/status writes.
Variant route reloads whole tenant twice. Every23505 maps to slug/SKU.
Current aggregate reads already parallelize; section/preload APIs must remain.
Brands are tenant-composite FK entities with denormalized name; categories ordered
join rows plus compatibility primary FK. Registry counts site, taxonomy, products,
variants and project refs; preserve these semantics and historical media.

Implementation:
1. Adapt stable helpers while preserving newer merchant validation, preload,
   categories/brands, upload feedback and native configurable topologies. Make
   legacy splitting explicit, deterministic, stock-conserving and idempotent.
2. New116 V3 canonical reconciliation, deferred final-valid semantic swaps,
   retained historical membership and service-only access; no history deletion.
3. Atomic create/update/variant commands including categories/tags/brand/status
   and current registry accounting; keep cache invalidation post-commit.
4. Separate catalog and inventory version guards. Descriptive unchanged-stock
   saves preserve live quantities; edited stock requires its version to match.
   Legacy unversioned clients remain accepted with documented limitations.
5. Structured precise conflicts and safe existing-framework diagnostics/timings.
6. Current-source backend/frontend regression suites; synthetic PostgreSQL115→116
   preservation, real uniqueness/rollback/checkout/delete/media/concurrency tests.
7. Current release manifest/checksum/schema/policy gates and detailed handoff.

No production access, mutation, deployment, push, merge, or old-checkout writes.
