# Recovery assessment

Prior PR211 independent-cluster restore and physical WAL/PITR reports remain
historical component evidence. This session adds durable synthetic provider-role
fence crash/restart and explicit exact-preimage recovery, with original roots
preserved. An interrupted fixture was independently recovered before cleanup.

The retained independently restored native stack is the target for final fresh
source acceptance. Passing there proves application compatibility with restored
Auth/MFA/Storage data, not a newly executed bare-host disaster recovery operation.
Post-freeze component PITR/restore evidence, when executed, is reported in PR212.

Off-host recovery, complete application PITR and coordinated object-version
recovery are NOT established. PostgreSQL WAL cannot restore bytes deleted from
object storage. A future acceptance must test DB-before/object-after creation and
DB-before/object-after deletion, retained object versions/tombstones, corrupt or
missing archives/WAL/objects and exact roles/grants, with independent identity.
No production backup path or artifact was changed; no customer data was copied.
RPO15min/RTO4h remain targets, not certified achievements.
