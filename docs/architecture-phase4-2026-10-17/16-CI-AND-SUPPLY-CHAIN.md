# CI and repository controls

Read-only API refresh: main protected=false; rulesets=[]; credential admin=false,
maintain=false,push=true. No administration settings were applied.
Actual successful check contexts on9a89f4b6 were `test-backend`,
`build-frontend`, `build-candidate`, all GitHub Actions integration15368.

The unapplied `evidence/recommended-main-ruleset.json` prepares a main-only
ruleset requiring independent approval, latest-push approval, dismissed stale
reviews, resolved threads, all three exact checks, no bypass actors, no deletion
or non-fast-forward update. A separately authorized administrator must review
GitHub API support/organization policy and apply it. Then verify an unreviewed
PR, failed check, force push and deletion are rejected. Protect production
environment secrets and deployment approvals separately. No conditional mobile
check is required by this proposal.

Backend/frontend now check out exact PR head and reject a dirty/different tree.
The artifact workflow checks main-target PRs without path filtering. ZIP
verification and staging Docker import freeze authenticated bytes before use.
No image relabeling, CI forgery or production token issuance is introduced.

Forked PRs receive read-only contents permissions and no persisted checkout
credentials. Third-party setup actions still need a complete immutable-pin
audit; this change preserves their existing behavior.

Ruleset field reference: [GitHub repository rules REST API](https://docs.github.com/en/rest/repos/rules).
The proposal remains unapplied and requires independently authorized administration.
