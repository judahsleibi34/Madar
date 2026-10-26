# Follow-up baseline

PR209 remains open/unmerged; main876b65e7. This separate worktree/branch is based
on PR209 headf65aa4722674cd63dbebbc5139a35a67e99ecee9. Follow-up PR will target
PR209's branch to isolate review and must land after that dependency. No original
worktree changes were discarded. Primary madar-gpu is production/read-only;
verified staging madar-staging has4vCPU/5402MiB,3956MiB available,53GiB disk free.
No production actions are authorized by this work.

Baseline evidence retained in PR209:3630 hermetic backend tests/683 skips PASS;
1713 frontend tests/one skip PASS; native stale attempt1 acknowledgement after
attempt2 reclamation FAIL. Full baseline suites are not reclassified as newly
executed here. New migration147 is coordinated/unselected and will not be
admitted to the automatic executor as forward-compatible.
