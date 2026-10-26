# Full protected release acceptance — NOT EXECUTED

**DID THE FULL PROTECTED146→150 UPGRADE EXECUTE? NO.**
**PROTECTED RELEASE ENGINEERING: INCOMPLETE.**

No complete-operation command, protected completion receipt, independent test
write handoff or preserved running application upgrade exists for this source.
Operational profile150 and `schema150_release.admitted_manifest` remain blocked.
The new integration methods cannot bypass those refusals.

## Actual native SQL execution

On positively identified madar-staging, owned source under
`/home/staging-admin/madar-final-release-20261020`, the existing command ran:

```bash
BACKEND_TEST_IMAGE=madar-schema136-preparation-test:working   timeout 600s bash web/scripts/rehearse_migration_150.sh
```

The command creates a separately marked PostgreSQL17 cluster, constructs146,
clones owned synthetic databases, and removes only its created database container.
The adapter callback uses the existing executor's real advisory-locked cursor.
New cases invoke `CompletedNormalUpgrade.migrate`, its actual root credential
context and existing `run_migration`, using real process flocks/SQL/journals.
Published147–150 SQL completes; selected original Auth-user, Storage metadata and
application rows survive; protocols are2/2/2. Ordinary active-slot state remains
byte-identical and unpromoted. A child cannot claim its parent's process lock.

**MODEL boundaries:** operational admission/profile, root source ownership,
authority issuance, backup verification, container/model observations, supervisor
and object effects. The test's literal synthetic credential is not an independent
issuer. It is never installed as operational authority. Auth/MFA provider behavior,
object bytes, actual private services, worker ownership, proxy promotion and NORMAL
writes are not exercised by these SQL cases.

All five6e58workflows passed. Fresh-provider CI is a separate genesis150 application test. Its receipt explicitly
reports `protected_controller_execution=false`, `production_authorized=false`.
It cannot satisfy this preserved146 application acceptance gate.
