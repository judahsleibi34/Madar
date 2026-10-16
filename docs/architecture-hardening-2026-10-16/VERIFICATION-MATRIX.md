# Verification matrix

Statuses are scoped to the requirement, not just existence of a test. PARTIAL
means selected evidence passed but coverage needed for full acceptance remains.
Commands/results are in09-TEST-RESULTS.md and sanitized evidence in `evidence/`.

| Area | Status | Evidence / limitation |
| --- | --- | --- |
| Authentication | PASS | Native GoTrue valid/invalid password, invalid JWT, refresh, portal login; selected supported local flow |
| MFA | PASS | Native TOTP, restricted password handoff, pending replay denial, AAL1 admin denial/AAL2 admission and TLS browser checks |
| Authorization | PARTIAL | Selected native builder/admin denial and full hermetic suite; complete privileged surface audit pending |
| Tenant isolation | PARTIAL | Two native tenants, bidirectional builder IDOR404/path403/query spoof denied; all writes/jobs/storage domains incomplete |
| Database integrity | PARTIAL | Actual115/145/146 commercial SQL and native durable intent replay; full critical transaction matrix incomplete |
| Reservations | NOT TESTED | No native concurrent capacity drill executed; existing conditional/unit coverage does not satisfy this gate |
| E-commerce | PARTIAL | Hermetic regressions/cache races and SQL commercial pricing; no native order/inventory concurrency acceptance |
| Payments | PARTIAL | Commercial synthetic ledger/idempotency tests; no full native gateway duplicate/refund effect drill or live charge |
| Forms | PARTIAL | Previously omitted draft tests now collected; native concurrent edit/delete/stale-write acceptance pending |
| Website builder | PARTIAL | Native project read isolation; full publish/host/custom-domain write isolation pending |
| Assets | PARTIAL | Native private object denial, legacy synthetic avatar bytes, restore byte checks; full managed upload/GC/quota matrix pending |
| Workers | PARTIAL | Actual notification consumption, replay, expired lease/retry/dead letter; no stale-owner fence/all-worker crash matrix |
| Cache | PARTIAL | Thread/route tenant race, clear and wrong-tenant tests PASS; multi-process invalidation incomplete |
| Redis | PASS | Owned staging48MiB/noeviction under128MiB, no published ports; controlled login503/readiness/recovery drill; not full OOM endurance |
| Staging | PARTIAL | Deployed native schema146/API/frontend/worker, health and actual interactions; external/all-worker/full edge parity incomplete |
| Backup | PASS | Actual synthetic logical DB/object archives, hashes and source fingerprints; no production backup certification |
| Restore | PARTIAL |177 tables/21 sequences/four objects/three MFA factors into independent copies; same cluster roles, not full restored-app/offsite/PITR |
| API | PARTIAL | Hermetic suite plus native selected success/error/authorization contracts; whole API not exercised natively |
| Frontend | PARTIAL | Exact npm ci/lint/build/1713 tests and native Chromium login/MFA/mobile; full product Playwright absent |
| Performance | PARTIAL | Same-stack baseline/candidate selected reads, zero errors, quotas/throttling recorded; targets/coverage/confidence incomplete |
| CI | PASS | Hosted Backend38849623975/Frontend38849623985 on0cb384ab, fresh locked build/tests/SQL rehearsals; final report head status available in PR |
| Release | PASS | Source forward/mirror/transition checks and no protected/controller/migration/descriptor change; no promotion exercised |
| Observability | PARTIAL | Existing logs/request IDs/route metrics/health retained; staging CPU/query-cost evidence added; alerts/full signal drills pending |
| Production | PASS | Only read-only host/metadata/configuration observations; no authorized boundary crossed or production mutation performed |
