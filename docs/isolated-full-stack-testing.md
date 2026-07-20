# Isolated full-stack security testing

Browser and live RLS checks are staging gates, never production smoke tests. The Playwright configuration has no target default and refuses the `madar.com` host family plus operator-configured production hosts. It also requires explicit attestations for a unique `madar_e2e_` database, clean migration application, a unique run ID, and disabled email/push/webhook delivery.

## Provisioning contract

1. Provision a disposable database or Supabase project used by no other environment. Apply all migrations from an empty baseline; do not reuse a shared schema.
2. Deploy the current frontend, backend, Redis, notification worker, and isolated execution worker against that database. Keep SMTP, web push, webhooks, remote ingestion, and billing callbacks disabled.
3. Copy `e2e.environment.example` to repository-root `.env.test.local`, replace every fixture value, and add every real production hostname to `MADAR_E2E_PRODUCTION_HOSTS`.
4. Create only namespaced fixture tenants/users/projects inside the disposable environment. Use `MADAR_E2E_RUN_ID` in every fixture name and idempotency key.
5. Run `npm run test:e2e:safety` and `npm run test:e2e` from `frontend/`.
6. Run the catalog-only RLS verifier against the disposable database, using a read-only connection where possible: `SUPABASE_DB_URL=... python backend/scripts/verify_rls_grants.py` inside the locked backend container.
7. Delete the disposable database/project as the deterministic cleanup boundary. Preserve only redacted test and catalog reports.

The current checked-in browser test covers published-form runtime geometry. Unit and route suites cover authentication, MFA helpers, builder save/recovery/conflicts, publishing, form and reservation idempotency, asset isolation/lifecycle, project pagination, notification lifecycle, and tenant permissions. A complete browser journey for every one of those flows still requires the disposable full-stack environment and dedicated fixture APIs; it has not been claimed or run by this repository-only phase.

## Required staging workflow inventory

- signup, verification/mock MFA, login, logout;
- create/save/reload, cross-context conflict, recovery, publish and explicit binding;
- anonymous absence of private pages and multi-project member-role enforcement;
- form and reservation replay/conflict behavior and single notification enqueue;
- asset upload, unreference, grace-period cleanup, quotas, and durable artifacts;
- notification success/retry/dead-letter/lease recovery with fake transports;
- direct authenticated privileged writes denied, cross-tenant access denied, backend service path allowed, exact function grants and safe `search_path`.

Do not run until the isolated database, namespaced fixture lifecycle, and fake delivery transports are all available. A missing prerequisite is a staging gate, not permission to point the harness at production.
