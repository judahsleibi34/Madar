# Verification matrix — scoped source-freeze evidence

Final exact-head CI/images/runtime/browser receipts are recorded after this source
freeze in the draft PR and final local report, not reassigned from parent images.

| Gate | State | Evidence / limit |
| --- | --- | --- |
|Git identity|PARTIAL|Local author/committer verified each commit;GitHub mapping after push|
|Ancestry|PASS|Complete213/212 preserved;no main merge|
|Exact CI|NOT TESTED|Final head checks require post-freeze receipts|
|Source integrity|PASS|Published001–149 SQL unchanged;new exact combined metadata|
|Release metadata|PASS|Explicit6,146→149,(147,148,149),policy none;ordinary automatic loader rejects|
|Fresh artifacts|NOT TESTED|Parent213 accepted;Phase V exact artifacts require new build|
|Controller|BLOCKED|Provider production adapter deliberately refuses before effects|
|Worker inventory|PARTIAL|Exact-role/source/host validators;complete production supervisor inventory absent|
|Delivery protocol|PASS|Native both-protocol/ACL/reclaim regression cases|
|Outbox protocol|PASS|Native149 generation/expiry/resolution cases|
|Deletion worker|BLOCKED|Protocol guard holds unsafe001–149 consumption;13 focused testsPASS|
|Provider lifecycle|PARTIAL|13 state-machine tests;real six-effect interruption/DBrestart/recovery PASS;not protected production adapter|
|Database migration|PASS|122 native executions incl11new146→149 coordinator cases|
|Intermediate READ_ONLY|PASS|Source gate forbids147/148 grant;native commits remain explicit checkpoints|
|Forward repair|PARTIAL|Native rollback/lost-commit/fresh-forward boundaries PASS;privileged full actor not executed|
|Authentication|PARTIAL|Actual149 parent-image native login/refresh;final Phase V image acceptance pending|
|MFA|PARTIAL|Actual149 parent-image AAL1denial/AAL2/nativeTOTP;not complete productE2E|
|Storage|PARTIAL|Actual149 private object/denial,backup metadata/bytes;not full managed lifecycle|
|Tenant isolation|PARTIAL|Retained native financial/resource scope;not platform-wide|
|Reservations|PASS|Native capacity/replay/reactivation regression cases at148/149|
|Notifications|PASS|Native delivery/outbox protocols and real149 parent worker delivery|
|Deletion ownership|FAIL|3 native stale request/step safety assertions FAIL;2 cancellation serialization casesPASS|
|Backup|PASS|Fenced149 synthetic backup preserves original full roles beforeNOLOGIN|
|Restore|PARTIAL|Independent149 PostgreSQL/object component restore PASS;not full application restore from149 backup|
|PITR|NOT TESTED|No new149 WAL/full-app/object-version acceptance|
|Replica|BLOCKED|No current approved receiver/transfer acceptance|
|Staging|PARTIAL|Separate native149 parent images accepted;final Phase V exact source pending|
|Controller installation|BLOCKED|No installed production adapter/systemd/reboot acceptance|
|Main protection|FAIL|protected=false,rulesets=[];credentialadmin=false|
|Independent review|BLOCKED|Automated reviews do not supply human approval|
|Production authorization|BLOCKED|No fresh independent protected approval;none issued|

Production safety PASS:bounded READ ONLY observations only;schema146. No migration,
restart, installed controller change, write grant, auto-deploy or billing activation.
