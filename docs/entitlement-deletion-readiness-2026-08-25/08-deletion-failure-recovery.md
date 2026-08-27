# Deletion failure and recovery

| Failure | Durable behavior | Completion rule |
| --- | --- | --- |
| Worker crash before claim | Request remains claimable | No effect |
| Worker crash during a step | Lease expires; another worker reclaims | Completed steps are not replayed |
| Auth/storage/OAuth timeout | Safe error code, bounded retry, backoff | Cannot complete until retry and verification succeed |
| Provider object/identity already absent | Idempotent success | Verified again where provider lookup is available |
| Unknown storage category/path escape/symlink | Permanent manual intervention plus alert hook | Never false-green |
| Retry/attempt exhaustion | `failed_manual_intervention` | Operator must investigate; no automatic completion |
| DB row gone but Auth deletion pending | DB step stays completed; Auth resumes late | Verification requires both states |
| Verification finds a DB/provider/storage orphan | `mismatch`, retry, alert after exhaustion | Finalize refuses unverified request |
| Optional retention date in future | `waiting_retention`, frozen, not claimed | Eligible only after due timestamp |
| Concurrent worker | Database skip-locked claim and lease | One live lease only |

Provider-neutral alert hooks receive bounded event/error codes for manual intervention. Operational metrics expose backlog state and oldest age without target content. The worker health state distinguishes startup/poll failure from process liveness.

Recovery procedure: inspect the protected request/steps/resources, correct the external or policy condition, clear only the specific safe retry/manual state through a future controlled operator procedure, then allow the same request to resume. Creating a replacement request for the same target is not the default recovery path because the original manifests are the durable evidence.
