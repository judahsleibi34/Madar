# Security scope and remaining trust

Confirmed parent149 defects:stale request failure cleared a successor's lease;
stale finalization completed its request;stale step completion overwrote successor
output. Their unchanged parent diagnostics were3FAIL/2PASS.150 request/step
mutations now require original ID,owner,generation,attempt,processing state and
live database-clock lease atomically; native adversarial tests exercise all three.
This is a corrected high-integrity boundary,not an RLS-only assertion.

Runtime service_role is BYPASSRLS in native tests. Lifecycle INSERT/UPDATE/DELETE/
TRUNCATE and old/helper execution are denied;reviewed owner functions use fixed
search paths and qualified objects. Cross-request/tenant identity,canonical
subject/resource/key ownership,overlapping deletion enrollment,foreign resources,
last-owner preservation,cancellation and original grant boundaries are tested.
Actual user/tenant staging deletion independently preserves a foreign tenant and
its Storage object. Notification/reservation/payment selected isolation checks
are rerun;platform-wide tenant mutation isolation is still PARTIAL.

The global service role retains broad authority on other business/provider tables.
An arbitrary caller holding that credential or an old worker can still bypass
application conventions outside these protected lifecycle interfaces. A dedicated
scoped deletion credential or broker and complete legacy consumer exclusion remain
P1 follow-up. No blanket provider grant rewrite is attempted. Native test role
impersonation proves database grants,but is not an arbitrary credential containment
proof or a complete production process inventory.

A later source review reproduced false-positive object absence on the second
Storage search page. Bounded sorted pagination now rejects existing objects,
malformed pages and incomplete scans. Real native acceptance must be rerun for
that source change. The restored-app tooling is staging-only and defaults to
INSPECT; it never issues protected production approval or arbitrary production SQL.

No new dependency,credential rotation,historical rewrite,production state change
or raw private evidence publication occurred. Tracked filename hygiene PASS does
not certify historical credential absence. The extra privileged inventory check
has11pre-existing missing classifications,independently reproduced on PR214.
