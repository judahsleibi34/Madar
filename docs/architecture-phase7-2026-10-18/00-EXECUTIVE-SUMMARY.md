# Phase VII: implementation and acceptance boundary

Conclusion: **NOT READY for production**. Draft PR216 contains real source-level
controller progress, reproduced integrity repairs and actual isolated privileged
installation/reboot evidence. It does not complete the protected schema146→150
operation. Production remains unchanged and operational150 admission remains
deliberately unregistered.

Implemented a concrete fixed-effect provider adapter, strict actor/resource
inventory, original-role and bounded object preimages, persistent boot fencing,
session observation/drain refusal, private provider recovery boundaries and a
read-only private operator status command. The adapter cannot issue authority or
execute caller-selected SQL/commands. Independent review strengthened resolver,
supervisor, port-publication, condition-ordering and declared-state checks.

Reviewed and classified all eleven privileged-client omissions. The unchanged
checker now passes78 paths, with per-path authorization evidence. This is inventory
closure, not platform-wide tenant authorization certification. During review, a
real lost-acknowledgement upload defect was reproduced: committed metadata could
reference private bytes deleted by exception cleanup. The repair retains uncertain
bytes/quota and operation identity; focused native and regression tests pass.

An independent KVM guest ran the actual root-owned installer, exact file checks,
atomic replacement and refusal probes. A real guest reboot retained the persistent
test barrier; deployment timers remained disabled. The later replacement installed
182 files frombd0c614c. These are genuine privileged-system observations, with
different source identities explicitly retained. They are not a complete release,
provider fence, write-handoff or migration-reboot rehearsal. The guest is powered
off and its disks/evidence retained.

Exact application/controller sourceb9d826ee passed backend CI3,338/833 skipped,
243 native PostgreSQL executions and frontend1,713/1 skipped. Fresh authenticated
images were built for that source. A separate fixed PhaseVII staging namespace
passed native restored-application acceptance without modifying retained
PhaseVI projects. Both real synthetic deletion workflows, original identities,
MFA/Storage, notifications and readiness passed. Nine browser groups subsequently
passed. The stack was then deliberately stopped to release staging memory;
volumes/evidence remain. See`fresh-schema150-acceptance.md` for exact identities.

PostgreSQL investigation also reproduced transaction-local activity statistics
reusing stale zero/one client counts. The source helper now refreshes its own
statistics snapshot before every unchanged strict observation. Five native cases
and the fresh CI harness pass. The specific earlier hosted native rejection had
no exact counter recorded; its cause remains unproven rather than retrospectively
attributed to this defect.

Resumption onOctober20 reproduced a second helper issue:REPEATABLE READ and
SERIALIZABLE retained stale queue rows even with fresh activity statistics. The
helper now requires a fresh statement snapshot and rejects those isolation
levels. Four native before/after cases establish the correction; see
`10-MVCC-OBSERVATION-REGRESSION.md`. New source CI is distinct from b9 runtime
acceptance:corrected3fde3ef1 passed backend3,338/835 skipped,native245 and
frontend1,713/1 skipped;its fresh authenticated artifact passed actual staging
INSPECT without image import. Historical SQL and production remain unchanged.

Release-critical engineering remains: sealed future-candidate publication,
exhaustive dormant/manual writers and alternate supervisors, maintenance-aware
ordinary backup/replica/restore with original roles, coordinator/candidate/private
acceptance/write-handoff integration, and full interrupted boot/proxy forward
repair. Scoped deletion credentials and authorized uncertain-effect reconciliation
remain unfinished. Main is still unprotected; independent review, current-data
recovery evidence and fresh protected operator approval remain separate gates.

Use`VERIFICATION-MATRIX.json` for explicit gate states,`07-CI-AND-INTEGRATION.md`
for exact CI and administrator actions,`08-SECURITY-AND-FAILURE-EVIDENCE.md` for
retained failures and limits, and`05-OPERATOR-RUNBOOK-AND-ROADMAP.md` for safe
operator capabilities and prioritized acceptance criteria. No main merge,
production migration/restart/controller installation or write-authority issuance
was performed.
