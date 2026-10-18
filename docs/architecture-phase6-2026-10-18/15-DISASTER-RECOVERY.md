# Actual150 full application restoration harness

schema150_application_restore.py adds staging-only INSPECT(default),REHEARSE and
explicit RESUME-SOURCE. No production host/path/controller,automatic customer
restore,PITR or off-host transport is implemented. Original source and target
artifact directories/SHAs are authenticated separately. An old source receipt
cannot authorize or relabel a new target image.

REHEARSE verifies source150/2/2/2,accepted original images/container IDs,positive
provider identity and exact local credentials. It captures original full role DDL
and service/role preimages durably BEFORE fencing. Known ingress/writers/providers
stop with restart=no;roles becomeNOLOGIN;identified established sessions drain;
unknown clients/login roles,prepared transactions,processing queues/orphan steps,
queue locks or other object-volume writers refuse. NOLOGIN alone is insufficient.

Rows/sequences,owners/grants/RLS/definers,original roles/passwords/memberships and
object-byte inventory bind the captured logical backup. The independent target
starts role-free on a different PostgreSQL system identifier. It restores the
original preimage roles before database ownership/ACLs and object bytes;strict
preservation/protocol/denied-direct-grant checks precede provider activation.
Fresh target source/code/images must match its own authenticated artifacts.
Original identity,password,TOTP,private objects,new native Auth/MFA/Storage/
notification probes and actual user+tenant deletion must work after restoration.
Source fences and row/sequence/object roots are re-observed AFTER target acceptance.

Target Compose is regenerated from checksum-pinned committed templates,fixed
settings and cross-checked live source credential values. Mutable origin YAML,
dotenv,gateway/TLS files are never copied. Effective11service configuration is
validated for exact images,own volumes,readonly bindings,internal networks,
loopback22080/22443/22081,local provider endpoints,restart=no and resource bounds.
Captured resolved JSON is consumed over stdin on every Compose operation;alternate
file/project/profile/env override forms reject. Source database lookup uses
attested container labels,not editable origin Compose. Symmetric object-volume
bind ancestry is checked;arbitrary privileged/socket/host-root actors remain
outside this same-VM proof. Secrets/role DDL/raw artifacts remain private.

RESUME-SOURCE explicitly stops the attested recovery target first,then restores
only recorded original roles/container IDs and verifies provider/worker access.
The source stays original a8fac208;resumption is not an upgrade/relabeling. A lost
resume reply can reconcile the same preimages,but cannot claim old roots after
legitimate reopened writes. Completed resume cannot replay. Failed acceptance
retains source barriers,owned target volumes and evidence;no implicit write reopen.

After fresh source/image and independent backend/frontend CI verification,on
madar-staging only:

```text
python3 web/staging/integration/schema150_application_restore.py INSPECT \
  --artifacts "$HOME/<fresh-target-artifacts>" --source-sha <exact-target-sha> \
  --origin-artifacts "$HOME/phase6-ci-a8fac208" \
  --origin-source-sha a8fac208586a331d79ce5d02cc5adf32410d57f3
```

Use the same exact arguments with REHEARSE,then separately RESUME-SOURCE. Inspect
preserves existing attempts;rehearsal refuses reuse. Source-only safety validation:
49tests PASS (restore/config/native150/prior149 safety/image checks),compilation
PASS,and actual nonmutating Compose config rendering PASS. Actual full restoration executed and PASS at exact8e17a128c0fadfc0f2eb6de95ab35f4a588240d1:
394.893s,independent new PostgreSQL system identifier,original role/password/
membership and owner/ACL/RLS/definer roots,all rows/sequences and object bytes
verified before activation. Original identity/password/TOTP/private object and new
native Auth/MFA/Storage/notifications passed;actual restored user+tenant deletion
completed all ten steps with two confirmed effects each and foreign tenant/object
preserved. Worker restart consumption passed. Source quiescence and unchanged
rows/sequences/objects were re-observed after target acceptance. No source overlay.
Fresh images6da42a7eee965644bf320ea055415b995755b80c2ac7f08a2739507058bd1416
and a149c259d53bba072bd545cc9e9bad92b253ec672ae66c02f73473c94a65d682 came from
run39126113202/artifact12135754482. Browser nine auth/admin/mobile checks also PASS.

Same-VM full restore cannot establish independent-host RPO/RTO or object-aware
full application PITR. Missing/corrupt WAL/base backup/object cases remain work.

## New source after a consumed restore attempt

schema150_candidate_refresh.py separately accepts fresh source/images on the fixed
already-restored150project. Default INSPECT;REHEARSE requires authenticated fixed
8e17origin images/full-restore report,exact prepared container IDs/images,source
labels and live scoped credentials. It creates a NEW private runtime;the consumed
restore directory/report remains unchanged. Known target writers stop,processing/
sessions/locks/object writers must be absent,and same cluster/rows/sequences/
roles/ACL/object roots must survive infrastructure recreation before provider
activation. Original and new native identity/MFA/Storage/notification/deletion and
code/image identity probes run again. It reports same-database refresh explicitly,
not another database restore,migration,PITR or production authority.

Fixed-project directory flock serializes DIFFERENT candidate SHAs before origin
attestation through effects/cleanup. Original restoration/resumption holds SOURCE;
resumption takes TARGET second,so it cannot stop a concurrent refresh. Locks require
current-user0700directories,no symlink,inode/device stability and nonblocking
exclusion;no replaceable lockfile. Initial identity substitution rejects before
stopping anything. Cleanup can stop known surviving owned actors after a partial
failure without requiring everyservice still exist. Disk≥8GiB and availableRAM
≥1300MiB are mandatory before effects. No original a8fac source is selected by
refresh. Use the updated harness for explicit RESUME-SOURCE so it shares TARGET
arbitration.89combined admission/recovery safety tests PASS before source freeze;
actual fresh candidate refresh remains a separate runtime gate.
