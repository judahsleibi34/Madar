# Maintenance role inputs and native restoration

The protected role-input adapter captures original role SQL from the recorded
provider preimage only after verified complete fencing. It never substitutes a
fresh dump of temporary NOLOGIN settings. Inputs are append-only and bound to
operation/source/controller/inventory/database/schema/preimage hashes. They do
not publish ordinary backup success, replica acceptance or production authority.

`rehearse_maintenance_role_restore.sh` uses two fresh networkless PostgreSQL17
containers,256MiB/0.5CPU each. It captures roles before fencing, changes a runtime
role to NOLOGIN, dumps the database, restores original roles into the independent
cluster, then restores data with ownership and ACLs intact. Native equality
checks include original LOGIN/attributes/password hash/memberships/settings.
Actual SELECT works, owner/grants/data match, and an UPDATE must fail with
SQLSTATE42501. Fenced-current, truncated and wrong-cluster capsule substitutions
reject. All role archives and generated synthetic password material stay in a
root-private temporary directory and are removed. No production paths are used.

The initial UPDATE check accidentally contained invalid SQL; it was corrected
to valid SQL plus an exact42501 assertion and the full native drill passed again.
The drill is not a full application backup/restore or root-authorized capture
operation. Ordinary maintenance object capture, role-aware verified backup
format/replica consumption and combined protected controller integration remain
unfinished. No backup/restore requirement is marked complete from file hashing
alone. Existing application recovery/PITR evidence remains historical, not a new
PhaseVIII exact-source acceptance. Off-host/object-aware PITR remains unproven.
