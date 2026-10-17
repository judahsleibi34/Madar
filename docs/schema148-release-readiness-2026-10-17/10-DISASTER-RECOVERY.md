# Independent recovery and remaining DR boundaries

New independent_recovery.py is staging-host-only, explicit INSPECT/REHEARSE,
and refuses existing/ambiguous targets. It captures only the owned synthetic
native stack, pauses its writers, retains private database/role/object archives,
then resumes the source. Each fresh attempt uses separate PostgreSQL initdb,
volumes, networks and loopback19080/19443/19081. PostgreSQL system identifiers
must differ and Auth/Storage application roles must be absent before restoration.

It restores role attributes/passwords/memberships, database rows/sequences,
owners/ACLs/RLS/security-definer configuration and object bytes. Hashes never
expose role passwords, user records, cookies, MFA secrets or object contents.
Capture/database/object checkpoints precede application startup. The restored
application then validates original password/TOTP/private object access, fresh
native Auth/MFA/CSRF/Storage/worker/API flows and22 native business tests.

No failed target is overwritten or automatically retried. Attempts1–3 are
explicit new scopes; all prior archives/volumes remain. A live earlier recovery
project blocks a fresh attempt. Errors stop only the attested target project;
the original source stack is resumed. Missing checkpoints require investigation,
not a fabricated restoration PASS. Production and unrelated staging are untouched.

Initial actual drills: attempt1 restored roles/grants/data but stopped before
application startup on unsupported Compose create --no-deps. Corrected the flag.
Attempt2 restored original identity/TOTP/private objects, then correctly rejected
the test's old18080 Origin at restored19080 with403. The smoke now derives its
Origin from the explicit application base; backend CSRF controls are unchanged.
Fresh attempt3 PASS:177 tables,21 sequences,8 objects, original password/TOTP/
private-object access and all fresh Auth/MFA/CSRF/worker/API checks;22 restored
native business tests executed without skips. Total115.19s; independent system
identifier7697415265751089186 versus source7697097132868993059. See evidence/
independent-recovery.json and restored-business-summary.txt. Application source
4f2c31aea7a10e33d337f506763258afa7e4419c. These failures are
staging-tool/test targeting corrections, never relabeled full recovery success.

This remains same-VM independent-cluster recovery, not off-host/bare-host, PITR,
full product browser certification, live gateway settlement or production RPO/RTO.
Application images initially remain offline source overlays, separately identified
from fresh CI candidate artifacts and privileged production acceptance.

## Physical base backup and named-target WAL recovery

Separate network-none PostgreSQL17 containers verified a real pg_basebackup with
pg_verifybackup, archived WAL and recovered to a named point before a synthetic
delete. Source rows became[2,3]; restored rows remained[1,2], with recovery paused
at the requested point. Incomplete base backup, missing WAL and corrupt WAL all
refused recovery acceptance/writability.66.84s component drill; source/targets
removed after ownership checks, small owned volumes retained for review. No
promotion, quorum/failover, off-host archiving, PITR full-app or production RPO/RTO
claim follows. See pitr_rehearsal.py and sanitized evidence/pitr.json.

Real restored-app Chromium151 acceptance PASS: native login/TOTP, AAL2 admin,
authenticated browser refresh, anonymous admin denial, Secure/HttpOnly/SameSite
cookies, pending-cookie removal, script cookie isolation and mobile labels/Tab/
width;0 page errors,0 external hosts. This is selected browser coverage, not all
Forms/builder/checkout E2E. Temporary synthetic credentials/tunnel were removed.
