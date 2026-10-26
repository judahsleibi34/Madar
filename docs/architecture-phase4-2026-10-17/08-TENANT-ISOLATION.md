# Tenant and authorization evidence

New native coverage uses actual GoTrue sessions and two independent API processes:
an editor sees private calendar details; owner downgrade to availability leaves
tenant membership unchanged; the candidate immediately masks private events while
the baseline discloses its stale cached details.501-event acceptance also checks
that every authenticated response preserves the expected event count.

Calendar review batching retains tenant/disposition and authorized-event filters.
Unit fixtures include another tenant, an unauthorized event and released review;
none enters the global newest50 result. Successor149 cancellation derives user/
tenant scope from the database request and preserves unrelated tenant work.

The runtime service role still bypasses RLS. No blanket role/RLS rewrite was
made. Original selected builder read/write and revoked-membership staging tests
are prior evidence until rerun against the final fresh source. Forms, assets,
orders, billing, learning and AI need broader native authenticated mutation
coverage. This is PARTIAL platform coverage, not a complete isolation proof.
