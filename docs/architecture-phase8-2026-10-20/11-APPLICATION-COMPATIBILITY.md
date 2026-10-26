# Compatibility is an independent acceptance gate

ClassA means the SQL fits a narrow additive grammar. It does not certify a
running old backend,tenant grants,provider behavior,table size,lock duration or
worker protocol. The plan requires application and worker compatibility plus
staging acceptance independently. Metadata declares a range and protocols but
cannot supply those PASS results or lower the AST classification. Introducing
or changing a protocol escalates to coordinated C. Missing coverage blocks.

Use expand→compatible application→bounded backfill→reader/writer verification→
a later contract release. This follows the separation described in
[GitLab's migration guidance](https://docs.gitlab.com/development/database/avoiding_downtime_in_migrations/).
PostgreSQL success alone does not establish rolling application safety.
[PostgreSQL17 CREATE INDEX](https://www.postgresql.org/docs/17/sql-createindex.html)
describes different locking/recovery behavior for concurrent index creation;
this implementation rejects that nontransactional path instead of weakening
Madar's existing transactional requirement. Ordinary indexes and recognized
ALTER/data operations are not routine A.

Existing147 delivery,148 reservation,149 outbox and150 deletion ownership
contracts and tests remain intact. The active production descriptor is unchanged.
Intermediate147/148/149 NORMAL activation is not authorized. Existing schema150
application/worker compatibility proof remains historical;no fresh full-provider
runtime or browser acceptance is claimed for this phase's final source merely
because backend/frontend CI or minimal future-schema tests pass.

Generic native staging currently covers isolated catalog SQL and retained native
business suites. Automatic old/new full-provider acceptance and candidate runtime
metadata/activation integration remain P1 engineering. Source intent cannot
silently widen a running application's real schema range. No old-image fallback
is safe after an incompatible committed schema merely because the image exists.
