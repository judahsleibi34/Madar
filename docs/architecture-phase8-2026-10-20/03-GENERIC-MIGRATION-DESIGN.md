# Generic migration preparation, not production authorization

The inventory uses immutable Git objects from exact commit SHAs and an explicitly
selected ancestor. Both SQL trees are captured, not reopened during execution.
It rejects changed published bytes, wrong ancestry/remote, nonregular Git modes,
duplicates, gaps, invalid names, mirror mismatches, replacement/grafted history
and excessive input. The historical004/005 names and141→143 branch are narrowly
preserved;142 is not admitted as a runtime destination. Discovery has no future
schema-number list. A configured remote is not authenticated release provenance;
the real controller must independently authenticate source/base/CI evidence.

The plan includes ordered hashes/paths/transitions, source and history identity,
compatibility intent, worker protocols, risk, required gates, recovery policy,
artifact status and deterministic operation digest. Application-only releases
have no invented SQL or unconditional migration backup. Worker protocol changes
escalate to C. Protected code changes require a separate control-plane upgrade.
Plans are canonical JSON, contain no credentials, and issue no authority.

Risk uses pglast7.21's PostgreSQL17 parser, pinned wheels in the CI-only target.
A requires a canonical BEGIN/locked schema check/schema update/COMMIT envelope
and a small isolated permanent-public-table subset with explicit built-in types.
B covers recognized lock/data-sensitive operations; C privileged/worker/security
contracts; D destructive, unknown, dynamic or unsupported nontransactional SQL.
Metadata can increase risk, never reduce it. Even A requires independent native
rehearsal, old/new application compatibility, grants, source, images, staging,
backup/restore, live drift and protected admission. Current historical147–150
SQL is not relabeled routine; its explicit reviewed contracts remain unchanged.

The fixed root-protected policy reader and read-only assessment support a future
routine-eligibility boundary. No independent issuer or production dispatcher is
implemented by them. Missing/expired/mismatched evidence, unprotected source,
wrong origin, stale artifacts and consumed operation block preparation. A match
still returns production_execution_allowed=false. Actual protected automatic
execution, generic coordinated execution, full candidate staging and the full
146→150 controller operation remain incomplete. No profile is registered.

Future synthetic151/152 plans and native execution use no controller edits.
Fixture153-like protocol changes and destructive154-like operations are refused
by the routine rehearsal path. No151+ files are added to Madar's migration trees.
The existing executor's captured SQL and deployment lock are reused on a marked,
networkless disposable database. This is native database evidence only; fixture
policy booleans are not authenticated operational receipts or production grants.
