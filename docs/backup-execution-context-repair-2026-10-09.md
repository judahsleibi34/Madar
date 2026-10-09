# Normal backup execution-context correction

The consumed plan `5b11d248ac69807d9cdd47a36451859709cba3ca734b5ad77e7f4a0af54de92a`
reached NORMAL verification, then compensated to restricted current-data recovery.
Its original journal retains only `RuntimeError`; the original child error output
was not retained. Do not infer an exact historical exception from a later probe.

Read-only and real implementation reproductions established three deterministic
backup blockers: private-file validation rejects the nonsecret 0644 canonical
path contract; the UID/GID 1000 child with no supplementary groups cannot discover
the native database through Docker; and scoped retention count 1 is rejected by
the ordinary backup's minimum-two policy. Docker discovery failure precedes any
PostgreSQL connection and does not establish database connectivity failure.

The path contract alone now uses nonprivate loading after protected root-owned
file validation. Secrets retain private validation. The governed root operation
resolves the healthy unpublished native database and hands a sealed anonymous,
root-owned, expiring address descriptor to the backup child. The child receives
no Docker permission, supplementary group or new privilege. Provider helpers
validate the descriptor; the coordinator re-resolves the address after capture.
The new scope uses retention count 2 and removes no existing backup. Backup
sessions default to read-only. A production-equivalent read-only database,
credential and managed-file gate runs before staging and before the write grant.
Only fixed error codes are propagated; raw child output is not published.

Actual private engineering execution: `/tmp/madar-backup-context-proof-7c816c14a7fe`.
The root-issued child was UID/GID 1000, groups empty, no-new-privileges enabled,
and Docker access denied. The real backup and a separate networkless native
PostgreSQL restore passed: schema 115, 96 public tables, 18 Auth users, four
managed file sets (200/5/8/10 files), and 235 provider objects checksum verified.
This test artifact is not a fresh production backup or artifact acceptance.
The complete scheduled wrapper ran against an isolated release-state fixture
matching the actual recovery version; no production release state was changed.
The current production database was neither written nor restored. The independent
supervisor execution SHA-256 is
`a40062b02dc7dc1e71467ebe2975930b60436354220514a197e6e4309ae16221`.

Source-inventory SHA-256:
`b71edb3965a6fd31b7d740c79622ccb7d8f4e4a2ca7e952e0f1ad615923f73f5`.
Backup checksum-file SHA-256:
`54f6b347bd6ecbcfa734184ef27e5595560a755a30805ad0bb74703429b8d8c8`.

Public recovery remains HTTP 200, writes disabled and all six consumers stopped.
The database is authoritative, including any legitimate writes during the brief
NORMAL interval. Read-only reconciliation confirms the same database container,
the same 96-table inventory, and one changed public-table root since pre-grant.
Its current snapshot SHA-256 is
`9dd3f936e085627f5093465b28226c95f014f9efa1e3b0b4db5d5aed15eab5e5`.
No historical checkpoint is restored over it.

No production retry is authorized by this document. The next exact operation
must bind the POST-publication compensated state and the installed continuation
resources. Existing prepublication retry gates must not be bypassed or represented
as passing for this different state.
