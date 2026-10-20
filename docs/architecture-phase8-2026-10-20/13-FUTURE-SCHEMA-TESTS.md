# Future source and native database evidence

2026-10-20:31 source/AST/plan/policy tests passed locally. They use actual Git
repositories and the PostgreSQL17 parser. A staging run passed the same31 tests
plus8 real PostgreSQL cases: two sequential future migrations with preserved
data, completed-operation replay, wrong origin, missing backup, failed SQL
transaction rollback, competing session lock, lost COMMIT acknowledgement with
independent observation/new remainder plan, and coordinated/destructive refusal.
No tests skipped. Actual pg_dump archive was restored into a separate database
and its preserved data checked before execution. This is a minimal fixture,
not full-provider staging or a privileged controller installation/release.

Command: `timeout 180 bash web/scripts/rehearse_generic_migrations.sh`, using the
retained Python3.12 test image with source mounted read-only and a separately
hash-verified PostgreSQL17 parser wheel. Limits: PostgreSQL384MiB/0.5CPU,
tester384MiB/0.75CPU, no published ports, network namespace isolated from other
services. The owned database container was removed by exact-label cleanup.
The initial native run completed39 tests in25.131s; source changed afterward,
so final exact-source evidence must be regenerated. Logs remain private.

The COMMIT-reply test executes a real transaction through the existing executor,
then injects a client exception after the first COMMIT. A fresh connection sees
151, the second migration has not run, and the consumed attempt cannot replay.
A new inspected plan151→152 completes on a new attempt. This does not certify
protected forward repair or reusing production authorization. No production
operation was attempted.

An additional private temporary clone based on72f066c9 added synthetic151 with
matching mirrors and committed the fixture locally. Both actual repository
validators (`check_migrations.py` and `check_migration_transitions.py`) passed
with151 files per tree, without a schema151 dispatcher/candidate/profile. The
temporary clone was removed and no real migration151 was published. This proves
generic source acceptance, not runtime compatibility or production eligibility.

Subsequent native expansions passed52 cases,then57 cases in90.236s. The latest
run is38 source/AST/plan/policy cases plus19 native PostgreSQL cases,zero skips.
Missing backup now uses a physically absent directory rather than an injected
verifier failure. Corrupted pg_dump bytes and wrong-cluster metadata are also
refused before SQL;schema150 and the absence of the new table remain asserted.
Both namespace-spoofing regressions are retained;see the security report for the
one deliberately failing pre-fix diagnostic and corrected refusal evidence.

Actual candidate-path evidence used an unpublished temporary Git source with
baseline150 and new151/152 SQL,verified source hashes,matching mirrors and
compatibility intent. The shared candidate script reported PASS,observed150→152,
and production_authorized=false. Its first attempt refused unreadable synthetic
source-directory permissions;only that owned public-source directory's mode was
corrected,then the full actual candidate plus44-case run passed. No authority,
SQL or ownership gate was weakened. The fixture is not real Madar151/152 source.
