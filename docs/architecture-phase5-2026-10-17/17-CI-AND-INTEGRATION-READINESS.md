# Exact source CI and canonical integration

Canonical development dependency: corrected preview212 → outbox successor213 →
this Phase V branch. Original209–211 are preserved historical reviews already
contained in212; do not mechanically merge overlapping PRs or rewrite their heads.
No source integration or production deployment was performed. Main/automation
must be rechecked before any independently approved future merge.

Backend/frontend/artifact workflow filters now include the213 dependency branch,
so this follow-up can receive all three actual checks. Exact PR-head checkout,
clean-tree guards, read-only tokens, unpersisted credentials, locked dependencies
and authenticated fresh-image archive acceptance remain unchanged. Artifact
workflow's historical schema148 name does not attest a schema; actual candidate
source, image IDs and runtime149 protocols are checked separately.

The working-source broad backend run passed3089 tests with788 conditional skips
(3877collected,49.508s), with external_attempts=[] and external_sites=[]. It used
the existing locked test image and public source mounts, NOT a fresh accepted
release image. Three opt-in native deletion invariants FAIL and remain release
blockers; five diagnostic cases are not counted as fixed by conditional skips.
Final immutable-head CI, frontend and fresh-image results must be recorded after
source freeze, never reassigned from parent213 or the working-source run.

Main protection remains a separately controlled administrator action. Reuse the
PhaseIV proposed ruleset with actual test-backend/build-frontend/build-candidate
contexts; never require a path-filtered check that cannot run. Independent human
review and fresh protected production approval cannot be supplied by these tests.
