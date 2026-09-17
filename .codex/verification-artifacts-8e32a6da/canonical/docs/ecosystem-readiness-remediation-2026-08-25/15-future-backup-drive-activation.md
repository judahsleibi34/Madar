# Future encrypted backup-drive activation

Status: **BLOCKED ON PHYSICAL BACKUP DRIVES.** Do not substitute cloud storage, another machine or an unencrypted destination.

## One-time preparation after media arrives

- [ ] Assign each dedicated drive a stable filesystem/LUKS identity and record serial/UUID/label in the offline asset register.
- [ ] Create encrypted media using the approved Node 1 procedure; record recovery material custody separately from the drive and host.
- [ ] Generate or select an `age` recipient; store only public recipients in the root-readable recipients file. Keep private identity offline with at least two authorized custodians and a tested emergency retrieval procedure.
- [ ] Create an explicit mount point that is otherwise empty. Configure `MADAR_OFFHOST_MOUNT`, expected volume identity and recipients-file path in a root-owned mode-0600 environment file.
- [ ] Confirm `replicate_backup_offhost.sh` refuses the empty unmounted directory and a mounted drive with the wrong identity.
- [ ] Set a free-space floor/retention count sized from measured dump+asset growth. Never use `/`, `/home`, a repository or unresolved environment variable as destination.

## Installation (future controlled change)

- [ ] Review but do not edit templates in place: `madar-backup.service/.timer`, `madar-backup-verify.service/.timer`, `madar-offhost-backup.service/.timer`, and `madar-ops-alert@.service`.
- [ ] Install reviewed copies into systemd, run `systemd-analyze verify`, reload, but initially start each service manually rather than enabling timers.
- [ ] Generate a local format-3 backup; verify manifest, TOC, checksums and completion marker.
- [ ] Mount/unlock the exact drive; verify `mountpoint` and `findmnt` target equality plus expected volume identity.
- [ ] Run replication. It must encrypt to a temporary file on the mounted filesystem, atomically rename, write a checksum for the final name and revalidate at destination.
- [ ] Unmount/re-mount, verify ciphertext checksum, decrypt to isolated temporary storage and run `verify_backup.sh` on plaintext.
- [ ] Only after two successful manual cycles enable the timers. Ensure missing/unmounted/wrong media fails non-zero and triggers the approved alert hook.

## Rotation and retention

- [ ] Maintain at least two drives and rotate one physically off-host according to the accepted RPO schedule.
- [ ] Retention deletion applies only inside the validated mounted destination and only after a new verified copy. Monitor free space before copy.
- [ ] Rotate recipients by adding the new recipient, producing/validating a fresh backup, proving restore with the new private identity, then retiring the old identity only after every retained backup is either re-encrypted or intentionally expired.
- [ ] Never destroy the only identity capable of decrypting retained backups. Record every custody/rotation event.

## Required restore drill

- [ ] Select a verified off-host generation without using the live host copy.
- [ ] Restore to an isolated replacement environment using `07-backup-preparation.md`.
- [ ] Validate login/AAL2, tenant isolation, public sites/snapshots/assets, forms/quizzes, reservations, analytics, notification states, workers and new backup generation.
- [ ] Record measured RPO/RTO, missing provider prerequisites and corrective actions. G18 remains BLOCKED until this drill passes.
