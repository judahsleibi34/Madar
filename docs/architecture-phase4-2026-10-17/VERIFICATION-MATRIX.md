# Phase-IV verification matrix

This matrix is frozen with source. Final exact-SHA CI/runtime receipts are recorded
in PR212/213 acceptance updates; no later result is presumed here.

| Area | State | Evidence/limitation |
| --- | --- | --- |
| Git identity | PASS | 14 published first-parent commits through3ab2bd50 resolve author+committer Saliba-codes; final additions require post-push check |
| PR ancestry | PASS | 209→210→211 heads preserved; preview merge tree equals211 |
| Integration | PASS | Separate branch/worktree, conflict-free preview; original PRs/main unchanged |
| Exact-source CI | PARTIAL | 3ab2bd50 three hosted checks PASS; later source-freeze head requires new runs |
| Source integrity | PASS | Historical001–148/release.json unchanged;149 confined to successor |
| Artifact provenance | PARTIAL | Fresh3ab2bd50 CI build PASS; final authenticated archive/runtime acceptance recorded externally |
| Controller | PARTIAL | Forward/SQL/artifact corrections tested; actual privileged boot/install not executed |
| Migration146→148 | PASS | 66 disposable PG tests; before19/2failing cutover becomes21pass |
| Delivery fencing | PASS | 18 native owner/expiry/reclaim/concurrency cases unchanged |
| Worker ownership | PARTIAL | Source consumers reviewed; complete production supervisor inventory/approval not established |
| Provider quiescence | PARTIAL | 16.317s native crash/drain/restart/recovery proof; controller lifecycle BLOCKED |
| Reservations | PASS | Native occupied/reactivation/concurrency cases at148 and149 |
| Financial integrity | PASS | Native order/stock/payment replay/rollback cases; gateway boundary synthetic |
| Tenant isolation | PARTIAL | Native calendar permission and cancellation scope; platform-wide domains incomplete |
| Forms | NOT TESTED | No new full browser concurrent-edit/delete acceptance |
| Builder | PARTIAL | Existing scoped regression evidence; complete publish browser workflow not repeated |
| Assets | PARTIAL | Prior native Storage evidence; final fresh-source smoke recorded externally |
| Cache | PARTIAL | Calendar revocation fixed natively; catalog cross-process invalidation remains incomplete |
| Observability | PARTIAL | Actual loopback signal/delivery/retry/dedup/recovery PASS; no durable production integration |
| Recovery | PARTIAL | Retained independent restore plus provider role recovery; no new off-host full restore |
| PITR | PARTIAL | Prior component proof; final rerun external, full-app/object consistency NOT TESTED |
| Performance | PASS | 501-event baseline fails;180 candidate reads succeed; no general speedup claim |
| Production | PASS | Read-only schema/controller/timer observation only; no unauthorized mutation |
| Operator approval | BLOCKED | Independent protected authorization is explicitly absent |

| Calendar event edits/deletion | PASS | Two native competing-route writes: baseline2FAIL, corrected2PASS, full68-case148 rehearsal PASS; authorization/side-effect transports stubbed; recurrence/children not fully transactional |
