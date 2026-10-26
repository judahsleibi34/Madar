# Integration and administrator prerequisites

Draft successor:[PR217](https://github.com/judahsleibi34/Madar/pull/217),targeting
PR216's branch. Canonical corrected history remains212→213→214→215→216→217.
PR212 already contains209–211; do not merge overlapping original PRs mechanically.
Main remains876b65e73ea8ceaf398145d8677019184798a95c. No merge,force push,branch
removal,production descriptor change or production controller install occurred.
Recheck automation/webhooks/timers before any later independently approved merge.

Observed GitHub administration:main protected=false,rulesets=[],credential
admin=false. This is FAIL for unattended production integration. No repository
setting was changed. Administrator actions,not performed here:

1. Create an active branch ruleset targeting refs/heads/main. Require pull
   requests and at least one independent approving reviewer;dismiss stale
   approvals and require review of the latest push. Restrict bypass explicitly.
2. Require the actual contexts `test-backend`,`build-frontend`,`migration-safety`
   and `build-candidate`;require an up-to-date branch. All PR base branches run
   these checks. Migration Safety fails if the independently selected base is
   not an ancestor;update the preview through a normal reviewed merge,not force
   rewriting published history. Do not require a job that cannot run.
3. Block force pushes and branch deletion. Restrict direct/bypass pushes and
   administrator exceptions. Confirm the intended GitHub App owns each context.
4. Establish a protected production environment with independently approved
   reviewers/deployment sources and controlled credentials. No production job
   or credential was activated here. Source/build CI is read-only.
5. Test an unreviewed PR,failed/missing/stale checks,late push,force push,deletion,
   unauthorized bypass and a legitimate reviewed PR. Verify effective rules
   through the API after applying;do not infer success from a prepared JSON file.

Main-push builds/plans do not deploy. A successful artifact receipt does not
prove protected integration,live backup,full candidate acceptance or authority.
Schema150 remains unregistered. The current draft is useful for independent
code review;the complete corrected release is NOT READY for production or
operator execution until its remaining engineering and external gates close.
