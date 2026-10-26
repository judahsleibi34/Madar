# Cross-process cache consistency

Native two-process regression proves the calendar permission-bearing cache could
retain private details after another process downgraded a calendar role.
The combined bootstrap payload now recomputes authoritative access and data on
every request, keeps private/no-store and reports X-Calendar-Cache:miss. Existing
in-flight-fill protections remain in their modules; no Redis assumption is added.

This corrects the security boundary without introducing a broker or probabilistic
invalidation guarantee. It increases read workload;501-event measurements are
reported explicitly. Public catalog/process-local TTL invalidation is still
incomplete across processes. Checkout stock/prices remain database-authoritative
and pass native concurrency tests, so Redis is not financial authority.

Platform cache consistency is PARTIAL. Further work needs tenant-safe distributed
versioning or explicit documented TTL contracts, Redis outage/restart tests and
multi-process invalidation evidence. No general consistency claim is made.
