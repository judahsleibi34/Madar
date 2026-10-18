# Phase VI baseline — 2026-10-18

Parent PR214 is OPEN/unmerged at80c05aec7cd7efa9d76f61f4eb0e44ec1183d617.
Fetch completed before work; origin/main remains876b65e73ea8ceaf398145d8677019184798a95c.
Separate worktree/branch:codex/schema150-deletion-integrity-20261018.
Prior worktrees and uncommitted work were preserved. New author/committer identity
is Saliba Rishmawi,75858844+Saliba-codes@users.noreply.github.com.

Primary host identity verified before development. Dedicated staging identity,
passwordless sudo, existing owned projects and capacity were inspected read-only:
4vCPU,5402MiB RAM,approximately2970MiB available,29GiB disk free. No existing
project was destroyed/recreated. Production mutation and main integration remain
prohibited; prior production146 observations are historical until refreshed.

Independent native baseline used EXACT parent214 source, disposable PostgreSQL17,
network none,768MiB/.75CPU/128PIDs/tmpfs1GiB and an ownership-label-checked cleanup.
Synthetic service_role has BYPASSRLS, matching the application trust boundary.
Schema149,notification delivery2,outbox2:5 tests,3FAIL,2PASS,0errors/skips,1.449s.
The initial fixture without BYPASSRLS produced4PASS/1ERROR; it is preserved and
excluded from accepted reproduction. No retained staging/provider/customer data
was used. Raw evidence and exact script are private under
/home/madar/phase6-baseline-native-20261018/; no credentials are published here.

Canonical source dependency remains212→213→214→PhaseVI. Earlier overlapping PRs
must not be mechanically merged. No main merge or production operation is
performed or authorized by this branch.

Later bounded production inspection used an explicit READ ONLY transaction and
2s statement timeout to observe core schema146. The auto-deploy timer is disabled.
No production write/service/controller mutation followed. These observations do
not authorize release or attest every webhook/controller/replica acceptance gate.
