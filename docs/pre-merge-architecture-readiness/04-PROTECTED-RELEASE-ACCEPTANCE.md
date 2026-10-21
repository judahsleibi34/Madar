# Protected release acceptance: BLOCKED

**Complete preserved running application upgrade: NO.** No completion receipt,
protected handoff, activated candidate or current-source privileged installation
is claimed.

The exact missing connections remain:

1. `CompletedNormalUpgrade._execute` prepares/activates/publishes a bridge before
   entering maintenance. It lacks the maintenance-first150 branch retaining a
   concrete `Schema150ProviderAdapter` across the operation.
2. Candidate inventory pins IDs/specs while candidate configuration contains
   the admission digest that hashes that inventory. Provisional preparation
   and final immutable actual-runtime binding are not connected.
3. `_execute` omits `provider_adapter` from `CompletedNormalBackupContext` and
   from its `migrate` call. A same-operation independent receiver is unproven.
4. Entrypoint acceptance delegates to public serving checks. Preserved original
   private Auth/MFA/Storage acceptance is not wired into the coordinator.
5. `CompletedNormalWriteHandoff.guard/grant` requires a running worker kernel.
   Private acceptance → protected handoff → worker ownership/start → proxy
   activation needs a coherent, authenticated ordering.
6. Maintenance-specific forward resumption/boot completion is not connected to
   those private states and fresh authorization boundaries.

The existing parent-owned `migrate(provider_adapter=...)` integration uses the
actual advisory-locked executor connection. Its native SQL tests passed; this
method alone cannot perform the full operation.

Shortest executable demonstration of the blocker (a passing refusal test):

```bash
PYTHONPATH=web:web/backend/tests python3 -m unittest \
  test_schema150_admission.DeletionAdmissionPreparationTests.test_no_approval_or_caller_adapter_can_enable_preparation -v
```

It verifies `schema150_protected_controller_integration_incomplete`, rejection
by `profile`, and refusal before authority or controller effects. Do not delete
those refusals in anticipation of implementation.
