# Remaining integration, operator and independent gates

**Existing protected146→150 release executable: NO.**

P0/P1 engineering, in order:

1. Complete150 admission/preflight and maintenance-specific coordinator ordering.
   Current `_execute` remains bridge-first, with prepare/activate/publish/adopt
   before SQL.150 requires fenced providers and a sealed private candidate.
2. Bind exact candidate runtime/configuration and complete writer inventory to
   that order, including stopped/manual/timer/recovery actors and object writers.
   The staged candidate's exact identities must be sealed without retroactively
   changing an admitted inventory or accepting unknown actors.
3. Invoke the existing executor/provider callback while the actual coordinator
   owns both locks. The historical service child obtains its own deploy lock;
   root/provider guard ownership cannot be assumed across that process boundary.
4. Bind actual original-role backup, restoration/configuration escrow and a
   positively identified synthetic receiver to one operation; no replica PASS
   was fabricated. Production receiver readiness is separately controlled.
5. Wire actual original Auth/MFA/Storage/tenant preservation and private provider
   acceptance before the existing independent write handoff. Provider startup,
   a healthy backend or an authenticated archive is not write authority.
6. Complete accepted-worker ownership/consumption, proxy route and boot-barrier
   ordering, durable interruption observation, fresh authority and forward repair.
7. Execute the full root-owned isolated operation and selected real guest reboots,
   then connect generic plans and an independent compatible test policy to that
   same executor. Keep150 unregistered until its engineering gates are met.

P1 security remains: narrow deletion credentials and uncertain external-effect
reconciliation. P2 remains: full restored-application acceptance, object-aware
PITR/off-host recovery and measured production recovery objectives. No P3 feature
or infrastructure expansion was introduced.

Independent controls: administrator-managed main protection/protected environments,
independent code review, current-production backup/replica/restore acceptance,
approved controller installation and fresh protected production authorization.
Main protection remains absent; do not confuse this with completed engineering.
Require the actual always-running jobs `test-backend`, `build-frontend`,
`migration-safety`, `build-candidate` and `full-provider-staging`; exclude conditional
mobile checks from unrelated PR requirements. No repository settings were changed.

Canonical integration remains212→213→214→215→216→217→218→219;212 includes209–211.
Do not mechanically merge overlapping PRs. Recheck actual timers/webhooks and
protected authority before any later integration. No main merge is authorized.

Operator scope: INSPECT/check source and report gates; PREPARE exact artifacts;
REHEARSE only positively identified owned synthetic targets with resource bounds.
EXECUTE remains reserved for the existing protected controller after independent
acceptance/authorization. No150 execution command or bypass is enabled here.
