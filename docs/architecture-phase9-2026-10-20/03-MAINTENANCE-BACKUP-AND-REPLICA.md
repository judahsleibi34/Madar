# Maintenance-aware ordinary backup integration

The existing CompletedNormalBackupContext and active_recovery_backup pipeline now
have a concrete-provider maintenance path. It retains the adapter's independent
authority,held coordinator locks,protected journal and actual quiescence checks.
Ordinary scheduled backups keep their live-release/provider validation. The new
path does not attempt HTTP provider checks after those providers are fenced.
The operation remains unregistered;there is no new CLI,issuer or SQL executor.

Original roles come from the pre-fence journal. A new root-private copy of the
ordinary dump/file output receives those roles,an original role snapshot,source/
controller/origin/candidate/configuration references,and descriptor-captured
non-database object roots. Database volume bytes are never walked. Root/file
mode,UID/GID and xattrs are retained in the archive;the current byte drill does
not activate that metadata on this host. Secrets needed for application
configuration remain a separately required escrow gate.

The inner manifest digest is persisted append-only in protected operation state.
Restore and replica consumers require that independent digest. Current NOLOGIN
attributes,truncation,object changes,wrong source/schema and missing context must
refuse. Partial copies and consumed records cannot silently overwrite prior
attempts. Privileged original-role material is never written through a runtime-
owned backup ancestor. Ownership handoff happens behind the private parent before
atomic ordinary publication,not by recursive chown below the public backup root.

Independent restore uses the original bootstrap role,original role SQL and a
CREATE DATABASE archive;it does not strip owners or ACLs. It compares all role
attributes/password verifiers,memberships,global/database-specific settings,
database and object ownership/ACLs,data and sequence state. ACL item order is
canonicalized while preserving every grantee/privilege/grantor token and the
NULL-versus-empty distinction. Native backup-only schema146 fixtures have passed
actual original-role and data/object recovery. These fixtures are not full
application/provider acceptance or a protected production operation.

The append-only receiver accepts150 only with an independently supplied
maintenance manifest digest;historical supported profiles remain unchanged.
Actual Node1/current-production replica readiness is not certified by a local
codec/unit test. No production backup or replica configuration was changed.

Validation commands and retained intermediate failures are recorded in the final
phase report. The initial native wrapper incorrectly used a host dump filename
inside its database container;it was corrected to stream the actual archive.
A subsequent strict fingerprint mismatch exposed only ACL array ordering;all
privileges remain compared after canonicalization. No assertion was removed.

References:[PostgreSQL17 pg_dumpall](https://www.postgresql.org/docs/17/app-pg-dumpall.html),
[prior boundaries](../architecture-phase8-2026-10-20/FINAL-REPORT.md).
