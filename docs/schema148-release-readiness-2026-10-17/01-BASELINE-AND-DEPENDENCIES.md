# Continuation baseline — 2026-10-17

Baseline: `3fba1c18b310bf0e16c0e6a1540ee8de72b633f4`, complete PR210 head.
PR209 and PR210 remain OPEN/unmerged at their reported SHAs; origin/main is
`876b65e73ea8ceaf398145d8677019184798a95c`. Both existing worktrees are clean
and preserved. New branch: `codex/schema148-release-readiness-20261017`.
Integration order:209 →210 →this continuation; no merge/promotion authorized.

Read-only production inspection verified schema146 and distinguished serving
application/controller identity from Git HEAD. Detailed host, cluster, slot,
container and supervisor observations are retained only in the private operator
handoff, excluded from Git. Production contains unrelated workloads; none may be
treated as disposable. No production writes performed.

Staging: madar-staging,4vCPU,5402MiB RAM,3895MiB available/no swap used at entry,
53GiB free disk. Owned nine-service native project retained; actual observed
schema is verified by subsequent staging evidence, not inferred from marker.
Application source9c084293 from PR210, offline overlay; not an accepted
production image. Unrelated madar-staging-data project preserved.

Previous suites are historical evidence only until rerun. Existing active release
is144..146 target146;147/148 candidates remain unselected. Existing automatic
executor rejects coordinated147. Protected coordinator supports only profiles1–4;
new admission must not widen those historical contracts or reuse consumed authority.

GitHub metadata: main protected=false; token admin=false, push=true. Branch
protection cannot be configured by this identity. Required workflow names are
Backend Check and Frontend Check; exact job contexts must be verified in final CI.

Future commits use Saliba Rishmawi <75858844+Saliba-codes@users.noreply.github.com>,
verified GitHub user ID75858844. Prior published history is preserved.
