# Reproduced ownership failures

The opt-in parent diagnostic test_data_deletion_ownership_database.py was run
unchanged against exactPR214 and schema149. A claimed at attempt1; a fixture-only
PostgreSQL-clock lease expiry permitted B's independent attempt2 claim.083 has
no durable generation. All three required safety assertions failed:

| Mutation by stale A | Observed successor corruption |
| --- | --- |
| _fail_step | B's in_progress request becomes waiting_retry; lease cleared |
| _step_finalize | B's request becomes completed |
| _finish_step | B's processing step becomes completed with A's output |

Root cause: table UPDATE filters use request/step IDs without comparing original
owner,claim epoch,attempt,processing state or database-clock lease. Application
rereads are not ownership authority. Request and step failure writes are separate
transactions. Cancellation also reads eligibility and then separately unfreezes
subjects before updating the request.149's narrower notification cancellation
checks original owner/attempt/live lease and its two native lock-order tests PASS;
it does not repair these surrounding lifecycle mutations.

Severity: high data-integrity risk. PhaseV consumption containment remains
necessary on149. Forward150 must fence every lifecycle transition in PostgreSQL,
revoke direct lifecycle-table writes and reject incompatible consumers. Broad
service-role authority on OTHER application tables remains a distinct trust
boundary: coordinated exclusion of all legacy deletion actors is mandatory.
