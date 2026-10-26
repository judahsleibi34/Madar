# Source integration and administration gates

Canonical corrected integration order:PR212→213→214→215. PR212 already contains
209–211; do not mechanically merge all overlapping original PRs. No main merge,
history rewrite,branch deletion,force push or production release occurred.
PR215 is a draft successor to214. All new published authors AND committers were
verified through GitHub as Saliba-codes; local identity is the requested noreply.

Fresh inspection still shows main876b65e73ea8ceaf398145d8677019184798a95c,
protected=false,rulesets=[],credentialadmin=false. PR214 remains OPEN/unmerged at
80c05aec7cd7efa9d76f61f4eb0e44ec1183d617. Administrator action is required; this
session does not authorize changing repository administration. Actual CI jobs are
test-backend,build-frontend,build-candidate. Required checks must match applicable
workflow triggers; require candidate artifacts for release-sensitive paths without
making absent conditional jobs block unrelated changes indefinitely. Require PRs,
independent approval,stale-review dismissal,no force pushes/deletion,restricted
bypass and protected production environments. Verify rules with a denied direct
push and a PR missing approval/checks after an administrator configures them.

The production auto-deploy timer was inspected read-only and is disabled;this does
not by itself attest every webhook/automation path or authorize a merge. Main
integration and production promotion remain separately controlled decisions.

Local source checks PASS:dependency locks,migration mirrors/order,forward-release
contract and tracked secret-file hygiene. Two historical013/014 duplicate-content
warnings remain intentionally preserved. An additional privileged-client inventory
check FAILS with11unclassified paths; exact PR214 source independently reproduces
the same11,so this is pre-existing inventory debt,not a new lifecycle regression.
Inventory completeness is not authorization correctness. No check/assertion was
weakened to conceal it. Narrow filename hygiene does not prove a historical secret
scan or active credential assessment; no such new broad claim is made here.
