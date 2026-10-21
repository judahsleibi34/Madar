# Recovery evidence and limits

At implementation83dce3da, the existing bounded native scripts executed with
new synthetic, uniquely labeled, disposable PostgreSQL containers:

```bash
bash web/scripts/rehearse_maintenance_role_restore.sh
python3 web/staging/integration/phase9_maintenance_backup.py REHEARSE
```

Original LOGIN/attributes/password verifier, memberships/settings, database
owner/ACLs, data/sequences and object bytes were independently restored.
Incorrect/fenced/truncated role material, wrong cluster, missing/wrong expected
manifest digest and unauthorized table UPDATE were rejected.

The component backup/restore report returned PASS in8.702seconds. It explicitly
reports `replica_verified=false`, `native_object_metadata_activated=false` and
`protected_controller_execution=false`. Synthetic Auth/MFA rows do not establish
authentication or MFA functionality on a restored full provider/application.

The native150 rehearsal exercises actual committed SQL boundaries, process
interruptions, lost acknowledgements, selected original-row preservation and
fresh database observations. Its issuer/backup/provider-supervisor boundaries
remain fixtures. No SQL replay or database rollback is authorized by these tests.

The74-case generic suite at48df165c additionally rejects actual150→151
advancement during backup before applying152. It retains committed151, records
the failed locked-origin check and refuses reuse of the consumed attempt.

An independent operational receiver, complete restored application, current-head
privileged boot/reboot, WAL/object-aware PITR, off-host recovery and current
production recovery acceptance remain unproven. No RPO/RTO is certified.
