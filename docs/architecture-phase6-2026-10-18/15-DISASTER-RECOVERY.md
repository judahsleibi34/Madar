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
PASS,and actual nonmutating Compose config rendering PASS. Actual restoration
runtime is a separate pending gate until its private report confirms execution.
Same-VM full restore cannot establish independent-host RPO/RTO or object-aware
full application PITR. Missing/corrupt WAL/base backup/object cases remain work.
