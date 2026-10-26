# Failure evidence and recovery boundaries

| Case | Evidence class | Observed result |
|---|---|---|
| Foreign-database idle client | NATIVE DATABASE | Old guard accepted;unchanged assertion failed. Corrected cluster-wide guard rejects. |
| Foreign prepared transaction | NATIVE DATABASE | Old guard reported0;native assertion failed. Corrected count rejects;owner rolled the prepared fixture back. |
| Replication-mode SQL writer | NATIVE DATABASE | Actual `walsender` updated/read a fixture then rolled it back;old guard admitted it. Corrected guard rejects. |
| NULL/unknown/background/parallel leader | NATIVE SQL CLASSIFICATION | Unknown/NULL/orphan/foreign-leader cases count;own PID-bound parallel/core housekeeping cases exclude. |
| Operator evidence substitution | FILESYSTEM / MODEL BOUNDARY | Old checksum/reopen path parsed replacement JSON. Single captured hash/parse preserves authenticated data. FIFO/symlink/oversize fail. |
| Archive substitution/labels/OCI identity | FILESYSTEM / NATIVE CI ARCHIVE | Tampering,wrong source/image/build/API origin and partial reuse reject. Real9932 archive captured/verified. |
| Nested tooling after base advancement | REAL TEMPORARY GIT / POLICY MODEL | Omitted helper regression failed;complete nested tooling pin changes digest and rejects old policy. |
| Missing/mismatched roles,objects or maintenance manifest | FILESYSTEM / NATIVE BACKUP COMPONENT | Restore requires independently expected inner digest;no success from archive existence. Native owner/ACL/role/settings/data/sequence/object-byte restore passed. |
| ClassD automatic staging | MODEL / SOURCE | Refuses before lease/artifact preparation;preserved assertion exposed an initial test-layout ordering error,then passed after early denial. |
| Failed latest exact-head backend CI | ACTUAL CI | Full-provider preparation refused;no provider stage ran at8dda. |
| Classic image store | NATIVE SERVICE | At4b6e,imported archive could not resolve accepted native manifest ID. Refused before providers. IDs were not substituted. |
| Native150 deletion worker restart wait | NATIVE SERVICE |019b reached all native application/deletion assertions,then failed supervisor wait. Failure retained;strict independent restart observation added. |
| Production metadata ownership mismatch | PRODUCTION READ-ONLY TARGET OBSERVATION | Additional metadata query stopped before SQL;no retry/bypass. Raw operational data stays private. |

Source/model and native component results overlap;do not sum them as unique
coverage. Original negative assertions remain in the repository. Private evidence
retains failing and passing logs under the owned PhaseIX evidence directories.
The final matrix distinguishes exact-head CI and source-specific native results.

The complete privileged failure matrix is **NOT TESTED** in this phase:controller
crash between committed147/148/149/150,private provider recovery/handoff failures,
worker/proxy activation interruption and boot/reboot at each boundary. The
unregistered operation must not execute until those paths are integrated.

Generic minimal-fixture tests retain actual child-process interruption,lost COMMIT
observation,wrong history/drift/backup/source/policy/replay refusal. Those are not
full provider/controller recovery or WAL/object-aware PITR. No consumed authority
was replayed,no live queue was reset and no backup was restored over production.
