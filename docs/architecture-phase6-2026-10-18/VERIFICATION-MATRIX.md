# Phase VI acceptance matrix

Frozen code candidate36bb910fa028d380a0fb130bb8beeb1b0990bd2d. PASS is limited
to the stated scope;conditional skips are not passes. This report issues no
production authority. Final runtime/source recovery state is in13/15/FINAL-REPORT.
Machine-readable equivalent:VERIFICATION-MATRIX.json.

| Gate | Status | Evidence and limitations |
| --- | --- | --- |
| Git identity | PASS | Every published new author AND committer resolves to Saliba-codes;local requested noreply. |
| Source ancestry | PASS | Dedicated branch preserves exact214 and corrected212→213→214 history;no main merge. |
| Historical migrations | PASS | 001–149 and active146 descriptor unchanged;150 mirrored SHA256 pinned in04. |
| Migration150 SQL | PASS | 38native ownership/upgrade cases;exact149 origin,atomic commit/rollback,actual grants. |
| Original stale-owner defects | PASS | Exact149baseline3FAIL/2PASS;150stale failure/finalization/step successor invariants pass. |
| Request/step ownership | PASS | Original owner/generation/attempt/live DB-clock lease;independent lock/concurrency/crash tests. |
| Cancellation/finalization | PASS | Atomic eligibility/original freeze;authoritative exact ten-step graph;cross-request denial. |
| External effect contract | PARTIAL | Durable canonical intent/confirmation and manual uncertainty;no exactly-once or real integration-revocation claim. |
| Legacy backlog compatibility | PASS | Old source2FAIL/1PASS→3PASS;all pre150nonterminal legacy requests block;no reset or SQLrewrite. |
| Worker compatibility | PASS | Delivery2/outbox2/deletion2;149deletion blocked;each poll;READ_ONLY nonconsuming;actual consuming150restart. |
| Native146→150 transitions | PASS | Captured ordered147/148/149/150 SQL;239hosted native executions including retained commercial and150business regressions. |
| Intermediate operational states | PARTIAL | Source contracts reject unsafe activation;real privileged coordinated operation not executed. |
| Protected release admission | BLOCKED | Version7candidate remains deliberately UNREGISTERED;concrete adapter/coordinator integration unfinished. |
| Provider lifecycle | PARTIAL | Durable ordering model plus actual staging role/session/service fences;no completed protected production adapter. |
| Boot/controller installation | BLOCKED | No full isolated root-owned systemd/install/reboot/authority/proxy handoff acceptance. |
| Source/image integrity | PASS | Exact36bb910f independent appCI/authenticated artifact12136249264 and native runtime hashes;no overlay/relabel. |
| Full-stack candidate | PASS | Exact36bb910f fresh images accepted311.759s at150/2/2/2 on already independently restored database. |
| Auth/MFA | PASS | Native login/rejection,restricted AAL1→AAL2,TOTP,refresh,original restored identity and private provider probes. |
| Storage | PASS | Original metadata/object bytes and private denial;actual object deletion;bounded absence-verifier adversarial tests. |
| Notifications | PASS | Delivery/outbox native ownership regressions and real enqueue/resolve/deliver/replay worker acceptance. |
| Deletion workflow | PASS | Actual user+tenant ten-step completion;two effects each;foreign tenant/object preserved;consuming worker restart. |
| Selected tenant isolation | PARTIAL | Native deletion/business/resource denial and runtime foreign preservation;global broad service role remains residual. |
| Reservations/stock/order/payment | PASS | Native retained assertions rerun at150;synthetic gateway replay only,no live financial effects. |
| Calendar integrity | PARTIAL | Retained atomic-version and authorization/query tests;full recurrence atomicity not established. |
| Independent application restore | PASS | Fresh role-free independent cluster150,original roles/ACL/Auth/MFA/Storage+runtime workers;394.893s at8e17. |
| Backup negative cases | PASS | Missing roles and truncated custom archive reject;single-transaction rollback leaves zero domain tables;owned PGremoved. |
| Provider/database restart fences | PASS | Owned source GoTrue restart denied by NOLOGIN;PGrestart preserved roles/schema/roots;not systemd proof. |
| Full application PITR/object consistency | NOT TESTED | No new150WAL recovery-point/object-consistency acceptance;historical component evidence distinct. |
| Off-host/RPO/RTO | NOT TESTED | Same-VM synthetic drills only;durations do not certify recovery objectives. |
| Current backup/replica | BLOCKED | Synthetic tests do not satisfy protected current-production-data/receiver acceptance. |
| Complete product browser E2E | PARTIAL | Selected auth/MFA/admin/mobile checks;not full forms/builder/assets/ecommerce workflows. |
| Cross-process cache | NOT TESTED | No new multi-process catalog invalidation acceptance in this phase. |
| Alerts/observability | PARTIAL | Ownership/protocol/worker signals and4observer checks;no new complete durable alert delivery/clear pipeline. |
| Performance | NOT TESTED | No representative before/after business benchmark or general speedup claim;only acceptance/drill durations. |
| Frozen candidate CI | PASS | Backend3183PASS829SKIP;native239PASS;frontend1713PASS1SKIP;fresh artifact workflowPASS. |
| Privileged inventory baseline | FAIL | Same11unclassified paths reproduced at exact214;not hidden or changed to force green. |
| Main protection | FAIL | Fresh inspection protected=false,rulesets=[];credential has no administrator right. |
| Independent human review | BLOCKED | Automated review is not independent human approval. |
| Production authorization | BLOCKED | Not issued;no readiness report or staging journal can issue authority. |
| Explicit source recovery/replay | PASS | Original role/service preimages restored and consuming probes passed;completed resume replay rejected with both project container state unchanged. |
| Production safety | PASS | Only bounded schema146/timer read-only inspection;no production mutation/main merge. |
