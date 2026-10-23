# Candidate archive capture

The existing completed-NORMAL coordinator captures fresh CI artifact bytes before
candidate preparation, while both existing upgrade and deployment locks are held.
Fresh existing authorization, the measured source, protected admission ancestry,
API-requeried artifact/run/attempt and latest exact-source backend/frontend checks
remain required. No new executor, credential issuer or production CLI was added.

The authenticated snapshot is copied into a new private admission directory and
fsynced before publication of its immutable seal. Actual OCI manifest/config
hashes and source/build/API-origin labels are independently checked, in addition
to the outer API artifact digest and receipt/archive checksums. Image expansion,
member count and retained metadata have fixed bounds. No images are loaded and no
services, workers, proxy or write authority are activated by capture.

The seal binds the operation context, plan, database, source/controller, migration
manifest, images, provenance file, artifact digest and workflow run/attempt.
Subsequent provenance checks requery GitHub and consume the protected retained
archive. Once capture is attempted, missing/partial/corrupt state cannot fall back
to operator-owned input or be overwritten. Existing historical attempts without
capture records retain their historical validation; no receipts were rewritten.

The new execution connection applies to the existing fresh-artifact profiles.
Schema150 still fails operational admission. Capturing two application image
archives does not prove the missing complete schema150 runtime configuration,
provider/worker inventory, private acceptance, handoff and boot integration.
Those gates remain PARTIAL/BLOCKED rather than being inferred from image health.

Validation includes adversarial synthetic OCI/ZIP tests, modeled coordinator
ordering/refusal, and a real authenticated 462,845,660-byte CI archive at
`9932e088bdfb69f29a5f3897cebe140d7fe8a8ac`. Its native capture/OCI verification
passed in 6.965 seconds on Node2 without Docker import or production access.
This is candidate-file acceptance, not privileged controller execution or
full-provider staging. Final-head CI evidence is recorded separately.

PhaseIX also reproduces and closes a checksum/read race in operator evidence:
the read-only evidence loader now hashes and parses one bounded regular-file
byte capture, with no-follow/nonblocking descriptor opening. Changed paths,
same-inode replacement after capture, FIFO/symlink and oversized inputs cannot
substitute parsed admission data. This strengthens existing evidence validation;
it creates no approval and leaves all operational blockers intact.
