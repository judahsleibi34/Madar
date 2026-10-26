# Backup-to-migration integration

Reproduced: sealing a150 maintenance backup called `intent_document`, which used
the operational profile selector and rejected the unregistered preparation. The
intent builder now performs exact pure150 contract/manifest validation while all
execution/admission selectors retain their refusal.

The existing backup context now rechecks the root-protected input digest and
actual maintenance archive, original-role/owner/ACL/database/object restore and
replica digest references. It binds the complete fenced provider journal under
its real directory flock, refuses pending/private activation state, rechecks
quiescence and rejects a changed journal before append-only input publication.
No raw role SQL, verifiers, credentials or original preimages enter the witness.

The installed backup verifier receives the same independent expected digest.
Missing/invalid150 digests and unexpected maintenance archives fail closed.
The helper validates the expected manifest before ordinary dump verification.

Also reproduced: maintenance manifest hashing and JSON parsing reopened a mutable
pathname. The existing verifier now opens a bounded regular file once and hashes
and parses those captured bytes. The unchanged mutation reproducer passes.

Initial focused evidence:32 tests passed (source/model/filesystem, not a protected
release). A broader managed-sandbox run had six socket permission errors and a
systemd parser failure; the unchanged312-case controller suite passed on staging,
with10 conditional skips. A native networkless owned PostgreSQL17 drill passed
in20.053s: original roles/owners/ACLs/data/sequences/object bytes restored, and
correct/wrong/malformed installed-verifier digests exercised. This is component
recovery, not full application restore, replica or protected controller execution.
The native snapshot archive was independently hashed before staging extraction:
`bc00044d3fd31ad61130c81f7fe9a188f97b0963b5e62dd567daaf41a925bdaa`.
Private before/after logs are retained outside Git.
