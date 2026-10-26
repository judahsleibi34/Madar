# Recovery evidence: categories remain separate

| Category | PhaseIX acceptance |
|---|---|
|Independent original-role/database restore|PASS component:actual fresh cluster,original attributes/password verifiers,memberships/settings,owners/ACLs,data and sequences compared|
|Independent native object-byte restore|PASS component:authenticated archive bytes restored into quarantine;metadata retained but not activated|
|Complete restored Auth/MFA/Storage/application/worker stack|NOT TESTED at91a;fresh full-provider genesis is not restoration|
|Interrupted protected maintenance/journal/authority restoration|NOT TESTED;actual combined coordinator/boot/handoff paths incomplete|
|WAL/PITR before/between/after147–150|NOT TESTED in this phase;no claim from ordinary logical backup/process-kill tests|
|Object-aware PITR/off-host disaster recovery|NOT TESTED;missing/extra/deleted/uncommitted object reconciliation and complete independent host recovery remain|

The maintenance manifest distinguishes current fenced runtime roles from their
recorded original restoration state. Its independent expected digest is mandatory
for restore/replica consumers. Database create/owner/ACL information is retained.
No generic broad grants are restored to undo150's restrictions. Missing roles,
changed digests or object bytes fail rather than being normalized into success.

Configuration hashes identify separately required escrow;they do not contain
recovered credentials. Current-production backup/replica/restore readiness and
RPO/RTO are uncertified. Historical PhaseVI application restoration and prior PITR
results remain useful historical evidence,not current-head acceptance. No
production dump,backup artifact or recovery target was changed or overwritten.
