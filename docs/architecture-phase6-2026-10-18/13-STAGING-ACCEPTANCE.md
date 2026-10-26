# Fresh native150 acceptance harness

New schema150_acceptance.py defaults to INSPECT and refuses production hostname,
ambiguous source,existing attempts/unverified archive ownership,digest/mirror
mismatch,wrong image identity,source overlays and insufficient memory/disk.
It creates only madar-schema150-phase6-20261018 on loopback21080/21443/21081.
Existing148/149 projects remain unchanged. Temporary imported helper globals are
restored in finally; source/runtime secrets stay in private staging files.

The origin is an authenticated SYNTHETIC independent148 recovery archive,including
original roles/passwords/memberships,Auth/MFA,Storage metadata/object bytes and
business rows. Captured149/150 SQL executes only in the new marked cluster.
Preservation roots,protocol150/2/2/2,exact fresh source-bound backend/frontend
images and code hashes are independently checked. No source overlay may pass.

After native Auth/MFA/Storage/notification/readiness probes,the harness creates
new GoTrue identities and real synthetic object bytes,submits user/tenant deletion
through service-role PostgREST,and requires the actual consuming worker to finish
all ten steps and confirm effects. Auth/object absence and foreign tenant/object
preservation are checked independently. A real deletion-worker restart must show
consuming=true. A stopped worker is not positive acceptance.

Execution at a8fac208586a331d79ce5d02cc5adf32410d57f3 PASS (305.324s),using
fresh authenticated artifact12135995156 from GitHub run39124278251. Runtime
backend/worker image06cb727a1912e96abdf72b28e1abe782f7efd7b08f752763e14b9bc0a8c0130b;
frontend6156891f830d69092150942db439c7ea57b8188ff202771049ad590ea4f2d17b.
Original Auth identity/password/TOTP/private object survived restoration. Native
login rejection,invalidJWT,CSRF,restrictedMFA,AAL1/AAL2,refresh,private Storage,
notification replay/worker delivery and readiness passed. Both synthetic deletion
requests finished all ten steps on their first attempt,with two confirmed external
effects each; real GoTrue identities and Storage bytes were absent. Foreign tenant
and object remained unchanged. Source overlays were false; markers150/2/2/2.
The private schema150-acceptance.json records full code hashes and limitations.
Subsequent application corrections need new exact-source images/acceptance.
It is not a full146 protected-controller rehearsal,off-host recovery,application
PITR,real integration-token revocation,or complete browser product coverage.
Destructive ambiguity/lease/crash scenarios are separate native tests. An
interrupted attempt is preserved/stopped only after exact project attestation;
it cannot be overwritten or silently marked accepted.

## Final fresh candidate acceptance

Exact36bb910fa028d380a0fb130bb8beeb1b0990bd2d fresh locked CI images passed
schema150_candidate_refresh.py REHEARSE on the already independently restored
owned150cluster in311.759s. Before activation,the SAME database system identity,
original roles/grants/rows/sequences/object bytes were preserved. No database
restore,migration or source overlay occurred during this refresh;the independent
full restoration at8e17remains distinct evidence. Auth/MFA/Storage/notification
acceptance and original identity/password/TOTP/private object preservation passed.

Actual live worker completed user and tenant deletion,all ten steps,first request
attempt,two confirmed effects each;both terminal states are
completed_with_retained_records. Actual Auth identities/Storage bytes were absent,
foreign tenant preserved,and worker restart consumption passed. Integration
revocation,host-file deletion and lost external response remain outside this
full-stack happy-path fixture. The private final schema150-candidate-refresh.json
binds source,run39128295629,images and runtime code hashes.

Browser exact36bb910f acceptance also PASS:Chromium151.0.7922.34,nine groups
(password→restrictedMFA,nativeTOTP,adminpage/API,Secure/HttpOnly/SameSitecookies,
pendingcookie removal,script cannot read accesscookie,authenticated refresh,
anonymous admin denied,mobile labels/keyboard/width),zero page errors and zero
external hosts. Temporary loopback SSH tunnel was closed after validation.

## Explicit source recovery and final resource state

Final36bb910f harness RESUME-SOURCE executed successfully against authenticated
originala8fac208 source artifacts,under shared SOURCE→TARGET locks. Original
role/service preimages were restored,preservation checkpoint verified,and positive
provider/actual worker-consumption probes passed. It stopped ONLY the positively
owned recovery target first;all final36bbtarget volumes,private configuration,
journals and acceptance evidence remain retained. The original source remains
a8fac208 at150/2/2/2,active;it was not relabeled/upgraded to36bb. Accepted final
36bb150candidate is deliberately stopped after LIVE acceptance to bound VMmemory.
Do not describe that final stopped state as positive consumption evidence;the
positive native/browser/worker-restart proof preceded the resource handoff.

```text
python3 web/staging/integration/schema150_candidate_refresh.py REHEARSE \
  --artifacts "$HOME/phase6-ci-36bb910f" \
  --source-sha 36bb910fa028d380a0fb130bb8beeb1b0990bd2d \
  --origin-artifacts "$HOME/phase6-ci-8e17a128"
python3 web/staging/integration/schema150_application_restore.py RESUME-SOURCE \
  --artifacts "$HOME/phase6-ci-36bb910f" \
  --source-sha 36bb910fa028d380a0fb130bb8beeb1b0990bd2d \
  --origin-artifacts "$HOME/phase6-ci-a8fac208" \
  --origin-source-sha a8fac208586a331d79ce5d02cc5adf32410d57f3
```

Repeated completed RESUME-SOURCE was then actually invoked and rejected with
restore150_source_resume_already_consumed. Source AND target container identities,
images,running state,start timestamps and restart counts were unchanged across
the rejected call. No source/target restart or replay was hidden. Final observed
staging headroom:2929MiB available memory,19.47GiB free disk. Unrelated projects
were preserved;no broad Docker cleanup was performed.
