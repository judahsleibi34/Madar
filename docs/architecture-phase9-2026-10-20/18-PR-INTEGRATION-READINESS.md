# Integration and administrator controls

Canonical source order is212→213→214→215→216→217→218. PR212 already includes the
corrected209–211 histories. Do not merge overlapping original PRs mechanically.
PhaseIX PR218 is a draft targeting217;all prior branches and published history
remain intact. New author/committer mappings must both resolve to Saliba-codes.

Refreshed main is `876b65e73ea8ceaf398145d8677019184798a95c`.
GitHub reports protected=false,rulesets=[];the credential has admin=false and
maintain=false. Repository settings are not fixed by source files or CI success.

An administrator must establish an active main ruleset requiring pull requests,
independent approval,stale approval dismissal and restricted bypass/force pushes/
deletion. Verify actual job names and that they run for all protected PR/main
changes before making them required:

- `test-backend` — Backend Check.
- `build-frontend` — Frontend Check.
- `migration-safety` — Migration Safety.
- `build-candidate` — Schema148 Candidate Artifacts (historical name retained).
- `full-provider-staging` — Full Provider Staging (new;require only after validated
  stable behavior and a reviewed exceptional-risk path).

The mobile job remains conditional;do not require it for unrelated PRs. The
artifact and migration/native provider workflows use immutable Action revisions;
workflow credentials are read-only and checkout credentials are not persisted.
Protect production environments and independently installed root policy/issuer
permissions. Ordinary repository credentials must never edit production policy.

The observed auto-deploy timer is disabled/inactive. That alone is not exhaustive
merge-hook/webhook safety proof. Before integration,an independent operator must
verify all timer,webhook,branch-trigger and installed-controller paths. No merge,
production automation activation or deployment is authorized by this report.
