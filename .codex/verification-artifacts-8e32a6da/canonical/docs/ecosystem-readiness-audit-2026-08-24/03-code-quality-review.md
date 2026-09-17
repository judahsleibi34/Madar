# Code quality and general review

## Strengths

- Domain-specific validation is unusually extensive: publication shape, tenant context, idempotency, upload signatures, remote-fetch SSRF controls, parser isolation, notification leases, OAuth state, and entitlement catalog contracts all have focused tests.
- API errors are generally structured and sanitized. Request IDs propagate through the backend and external responses.
- Database RPCs encode important cross-request invariants instead of relying solely on frontend checks.
- Dependencies and base images are pinned; parallel migration trees are mechanically compared.

## Correctness and maintainability findings

`builder_routes.py` (2,960 lines), `public_site_routes.py` (2,719), `calendar_routes.py` (2,352), `auth_routes.py` (1,314), and the PageBuilder workspace (more than 8,000 lines) combine validation, persistence, state transitions, presentation contracts and compatibility behavior. The concentration made the quiz/public-runtime drift and bootstrap snapshot exception easier to introduce and harder to see.

Business rules still have deliberate compatibility paths:

- entitlement fallback grants nearly the whole catalog (`services/entitlement_service.py:23-29,153-173,176-264`);
- public-runtime entitlement dependency failures keep an existing site online (`:416-440`);
- publication code retains a test/legacy non-RPC fallback (`routes/builder_routes.py:1472-1557`);
- several cleanup operations are best-effort multi-call compensation rather than transactions.

The latter is particularly visible in public-site signup cleanup and admin account deletion. Supabase Auth deletion, application rows, tenant cascade, remote Storage objects and host files cannot be committed atomically. Failures can leave partial identities or orphaned content.

## Frontend

The production web build succeeds, theme contract passes, edge-header audit passes, and routing/auth state uses HttpOnly cookies rather than browser tokens. Large PageBuilder and CSS bundles remain a performance/maintainability concern. The build reported chunks over 500 KiB; notable uncompressed assets include the 521 KiB Three.js vendor chunk, 634 KiB PageBuilder CSS, and 1.28 MiB main CSS.

Two PageBuilder renderer assertions fail deterministically: saved two-column alignment and authored behind-text artwork Y placement. Web lint also fails with four errors: three in `PageBuilderIconPicker.jsx` (Fast Refresh export, component creation during render, constant binary expression) and one ref-during-render error in `PageBuilder.jsx:7837`. These are real release-gate failures, not environmental warnings.

The tracked Expo mobile client is a prototype. Its login page states “Login screen comes next” and has no real authentication/API integration. It must remain classified as unreleased roadmap.

## API quality

Authentication and public mutation routes use explicit Pydantic limits and rate-limit categories. Forms and reservations support hashed idempotency and request-conflict detection. Some list APIs have explicit pagination, but large builder/calendar modules still contain fixed limits and compatibility lookups rather than a uniform cursor/error schema. No breaking contract was reproduced against production.

## Latent work

Material unfinished signals are the entitlement grandfathering, mobile placeholder login, unscheduled storage reconciliation, disabled backup freshness, future OCR/Drive products, and OpenAI planner branch that explicitly raises “not implemented.” Ordinary exception marker classes and UI placeholder text were not counted as defects.
