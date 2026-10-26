# External outcome contract

Intent commits before each external effect and binds the original live request,
step,generation and attempt to a canonical stable target key. Renewing an already
expired claim is rejected. Provider calls occur outside PostgreSQL row locks.
The configured Supabase HTTP timeout defaults to30s; an intent requires at least
30s remaining after the request's live lease is renewed to5minutes. Integration
revocation uses a10s HTTP client. Future timeout changes need this budget reviewed.

A response may be lost after the provider accepted deletion. The worker never
infers absence from free-form error text: only structured404/410 or exact known
absence codes qualify. Unconfirmed durable intent blocks automatic reclamation
and becomes manual intervention. No automatic destructive resend,replayed
successor acknowledgement,or exactly-once external claim is made. The final
verification reads provider absence before the authoritative completion RPC.
Provider verification unavailability is explicit,not silently ignored.

Intent confirmation atomically updates scoped resource/subject state,effect
confirmation,registry state and storage quota. Filesystem deletion opens each
parent beneath pinned directory FDs with O_NOFOLLOW; a parent swap cannot redirect
unlink to another tenant's file. Unrecognized storage categories and shared
published builder assets are fail-closed review cases.

No public arbitrary reconciliation/SQL escape hatch is introduced. An approved
operator must independently establish uncertain provider outcomes and perform
reviewed owner-controlled repair; complete operator reconciliation tooling is
unfinished. A stale in-flight external call cannot be undone by database fencing.
Old consumers and broad service-role callers must be excluded during cutover;
this migration does not revoke platform-wide provider grants.

Storage absence verification now traverses substring-search pages in stable name
order,with100 results/page and a1000-result bound. An existing exact object on a
later page rejects finalization; malformed or exhausted listings fail closed.
A new adversarial test failed against a8fac208's single-page verifier and passes
with the repair. This is an application correction; published migration150 bytes
and checksum remain unchanged. Concurrent provider mutation is still constrained
by frozen subject ownership and the maintenance/consumer authority contract; a
paginated absence read is not a database transaction with object storage.
