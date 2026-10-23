# Concrete integration changes and remaining boundary

The existing root coordinator now owns both required locks during each root
credential window, including after a User=madar service released its deployment
lock. Real descriptor ownership is checked before authority issuance. A borrowed
lock is retained; an acquired window is released even if issuer/effect/credential
cleanup fails. Credential collisions preserve prior evidence and refuse before
issuance. `control_plane_upgrade.acquire_lock` closes descriptors on contention.

A concrete provider callback now connects the existing migration executor cursor
to `ProviderMaintenance150.migration_entry`. Only pinned147/148/149/150 transition
metadata/checksums are accepted. It observes the executor's actual session-level
advisory lock in pg_locks and uses that cursor for fresh statistics/MVCC, cluster,
schema, processing/session/prepared/background-writer and real protocol checks.
Unknown clients remain rejected. The callback neither runs migration SQL nor
issues authority; the existing executor retains SQL custody and commit handling.

The complete150 coordinator is still not executable: preparation/publish order,
exact candidate/inventory construction, backup/receiver/configuration binding,
private current-data provider acceptance, protected target handoff, activation and
boot/proxy recovery are not jointly integrated. `profile()` and150 admission remain
blocked. These tested edges do not constitute a complete root-controller release.

## Native SQL vertical slice

The existing147–150 rehearsal now invokes the concrete provider callback from the
existing locked executor over full published146-origin SQL fixtures. Seven cases
verify selected original rows, grants/protocols, four lost commit acknowledgements
and actual process exits after147/150. Authorization and host/backup/activation
remain MODEL boundaries; this does not satisfy the full privileged release gate.

## Runtime lock ownership mismatch

Source review and four real-filesystem staging cases confirmed that the old
provider verifier demanded root ownership for the deployment lock and its entire
ancestry, while the existing deployment service runs asmadar and creates/opens
that private runtime lock underUMask0077. Only the fixed deployment-lock path now
uses the existing readonly_configuration operator-owned runtime-file rule. All
other lock paths remain root-private. Regular-file, inode and actual process
flock checks remain mandatory. The tests reject unsafe modes, symlinks, replaced
inodes and an unlocked descriptor; four cases passed under actual staging file
metadata. The operator-name mapping is a test fixture, not an installed account
or production authority. The new native CI step exercises these four cases on
the disposable runner. Container tests lacking an owned home skip them explicitly.
