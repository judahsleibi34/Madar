# Protected release acceptance: BLOCKED

**Complete protected preserved running146→160 application upgrade: NOT TESTED.**
There is no completion receipt, protected handoff, accepted privileged reboot,
original Auth/MFA/Storage acceptance or public activation for this operation.
The obsolete architecture146→150 operation remains non-executable.

The distinct version8 preparation pins canonical main147–156 and integrity157–160
in `migrations-147-160-coordinated.json`. Published SQL and mirrors are unchanged.
The existing maintenance-first coordinator, concrete provider lifecycle, stopped
candidate sealer, backup context, service-child creation guard and parent-owned
migration dispatcher now carry that exact operation and target. Source and
protocol bindings reject mixtures of the historical and canonical histories.
Delivery2 begins at157, outbox2 at159 and deletion2 only at160; legacy deletion
backlog must be empty through159. Intermediate versions remain READ_ONLY.

Supporting tests (not privileged application acceptance):

```bash
PYTHONPATH=web:web/backend/tests python3 -m unittest \
  test_schema160_release test_completed_normal_maintenance_execution -v
MADAR_CANONICAL_EXECUTOR_TESTS=true BACKEND_TEST_IMAGE=madar-backend-test \
  bash web/scripts/rehearse_data_sources_upgrade_136_156.sh
```

The native mode positively observes146, then uses the existing
`LockedMigrationExecutor` for fourteen real transitions to160 under its actual
advisory lock. It tests foreign-session refusal, lost committed replies at147,
156,157,158,159,160, consumed-attempt refusal, fresh wrong-origin refusal and
all eleven native calendar concurrency/rollback/authorization tests at160.
The backup callback is a test fixture; no protected backup or authority is
claimed. Controller-ordering tests model host/provider/issuer effects.

Remaining executable integration blockers:

1. `schema160_release.admitted_manifest()` and the operational `profile()`
   registry deliberately refuse until full lifecycle acceptance exists.
2. `continue_completed_normal_upgrade.py` supplies public acceptance only;
   measured private preservation and activation guards are still missing.
3. The source-package producer does not publish the original candidate-free
   measured provider inventory; the coordinator's consumer is implemented.
4. The backup context still needs an actual isolated independent receiver,
   authenticated restore evidence and private original-provider acceptance.
5. `CompletedNormalWriteHandoff.guard/grant` assumes running bridge workers;
   it cannot yet verify a stopped/private maintenance candidate and activate
   authority before compatible workers. Backend authority also lacks the exact
   reviewed160 contract. No broad146..160 grant is allowed as a workaround.
6. The child's activate/adopt path still rejects a creation-only receipt and
   assumes READ_ONLY running bridge acceptance. Maintenance worker ownership,
   proxy publication, source-bound boot and forward recovery remain incomplete.

The calendar transaction transport additionally needs securely configured
`MADAR_CALENDAR_DATABASE_DSN` and `MADAR_CALENDAR_DATABASE_SYSTEM_IDENTIFIER`,
validated role scope and connection limits before a real deployment. Native
fixtures exercise the existing Supabase service-role capability; they do not
prove narrow worker credential isolation.

Ordinary Full Provider Staging must continue refusing the Class D plan.
Exceptional protected acceptance is not supplied by the native SQL mode.
Automatic dispatch remains blocked; no production descriptor, authority,
controller, timer, service or routing has been changed.

`BRANCH_PROTECTION: DEFERRED_BY_PROJECT_OWNER`. This owner exception removes
branch protection alone as a gate; it does not satisfy any blocker above or
replace protected production authorization.
