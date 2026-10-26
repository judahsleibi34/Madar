# Confirmed catalog-verification defect and source integrity

## P8-01 — MEDIUM, conditional catalog digest substitution — corrected in source

Component: `completed_normal_database.database_structure_digest` and generic
`migration_drift.observe`. The shared aggregate called unqualified PostgreSQL
functions under the caller's session search path. A function in an earlier
untrusted schema could return an old expected digest while the catalog changed.

Preconditions: unsafe session search_path explicitly puts an attacker-writable
schema before pg_catalog; ability to create a matching shadow function; a caller
uses that namespace for verification. This is a confirmed synthetic false
negative, not evidence of production exploitation or a general authority bypass.
Schema150 admission and generic production dispatch remain closed.

Native reproduction: capture the original digest; create public.sha256(bytea)
returning that digest; SET search_path=public,pg_catalog; inspect the catalog.
The unchanged ownership-safety assertion failed: the modified catalog returned
the original hash. One native diagnostic failed before correction. No production
function was created or executed for this reproduction.

Fix: pin pg_catalog transaction-locally before identity/catalog queries in the
existing helper, generic observer and protected migration connection's read-only
identity probe; schema-qualify pg_control_system. Existing metadata aggregation,
historical SQL001–150, authorization and receipt formats are preserved. No role
setting or installed production code is modified. The same native assertion now
passes. The first correction exposed psycopg's first-result behavior for SET plus
SELECT; those statements are now consumed separately and the regression passed.

Regression: the native shadow-function assertion is retained, alongside changed
protocol-function-before-execution refusal, read-only transaction and catalog/ACL
drift cases. Existing23 customer/migration/commercial source tests passed after
the query correction. Full exact-head CI remains a separate required acceptance.

A bounded read-only observation of the production native administrator session
found schema146, no explicit pg_catalog-after-other-schemas configuration, and
no public.sha256(bytea). Raw settings remain private. This is one observed
session, not proof about every connection. No production mutation occurred.
Controller installation/activation still requires separate protected review.

## Source and artifact boundaries

Discovery authenticates captured Git objects, SHA256 SQL and exact mirror bytes
against an independently selected ancestor. A remote URL is only an identity
sanity check. The normal official checkout URL without .git was initially rejected
in CI; its exact alias was added after observing the actual checkout command.
Other repositories still reject. Git replacement/graft history, path tricks,
executable/symlink SQL, gaps and changed published bytes reject. External Git diff
and text conversion helpers are explicitly disabled. A real local helper fixture
is never executed by planning. Duplicate JSON keys and nonfinite values reject.

The PostgreSQL17 parser is exact/hash-locked and CI-only, not a new production
application dependency. Missing/wrong parser fails restrictive. AST analysis is
not proof of tenant/application/lock compatibility. Root controller/parser
identity must be independently authenticated; CI/source code cannot authorize
itself. No production dispatcher or second issuer was introduced.

Fresh images retain the existing authenticated run/attempt/archive/OCI/source
contract. The historical artifact workflow identity is preserved; main pushes
now build exact integrated-source artifacts without deploying. Required backend,
frontend, artifact and migration checks run on all PR bases. No PR target event,
production secret, persisted checkout credential or automatic production action
was added. Main remains unprotected; an administrator must establish controls.

## P8-02 — MEDIUM, conditional disposable-marker redirection — corrected in source

Components: generic `migration_rehearsal.connect` and shared test
`disposable_database_support.connect_disposable_database`. With the same unsafe
session namespace, an unqualified current_database() lookup could select a
second marked database's comment while connected to an unmarked database.
Preconditions include that namespace ordering, a shadow function and another
marked database. The native negative fixture explicitly demonstrates the old
lookup returning the wrong marker. No production database was used or marked.

Both connection helpers now pin pg_catalog first through PostgreSQL startup
options and explicitly qualify the current-database function/operator. The
protected migration connection uses the same fixed namespace. Provider internal
SQL and customer/reconciliation snapshots pin their namespace before catalog,
role or checksum observations. No role attributes are changed by these helpers.
The unchanged no-fixture-writes-before-marker rule remains enforced. Native tests
show both corrected helpers refusing the unmarked database before any fixture
write. The complete staged suite passed52 cases:35 source/AST/plan/policy tests
and17 native database cases. That run includes actual historical identity/hash
SQL under hostile namespace, real child-process kill, row-lock/ACL/drift checks.
Source/component regression tests109 passed. These overlapping runs are not
summed as unique platform coverage. Fresh CI is required for the new source.

These findings invalidate prior source acceptance for the affected helpers until
the corrected source passes its own CI/controller review. They do not justify an
unapproved production install, role change, migration or service restart. No
secret exposure, credential rotation requirement or customer-data loss was found
by these synthetic reproductions or the bounded production metadata check.
